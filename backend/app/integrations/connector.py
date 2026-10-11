"""Universal API connector ("Dodaj własne API").

An integration's ``config_json`` describes the call; nothing provider-specific
lives in code::

    {"type": "rest" | "graphql" | "rss" | "openai_compatible",
     "role": "photo_source" | "text_source" | "ai_provider" | "fact_source" | "export_target" | "agency" | "storage",
     "request": {"method": "GET", "url": "https://api.x/search?q={query}", "headers": {}, "query": {"page": "{page}"},
                 "body": "<jinja2 template, sandboxed>", "graphql_query": "...", "timeout_s": 15,
                 "pagination": {"type": "none|offset|page|cursor|link", "param": "page", "cursor_path": "$.next", "max_pages": 1}},
     "auth": {"type": "none|header|query|bearer|basic|oauth2_cc", "name": "X-Api-Key", "username": "...",
              "token_url": "...", "client_id": "...", "scope": "..."},
     "mapping": {"items": "$.results[*]", "fields": {"url": "$.url", "rights_owner": "$.creator"}},
     "allow_private": false}

The secret (API key / password / OAuth client secret) is stored encrypted in
``secret_ref``.  Templates run in a Jinja2 sandbox without filesystem or env.
"""
from __future__ import annotations
import ipaddress, json, os, socket, time
from typing import Any, Optional
from urllib.parse import urlparse, urlencode, urlsplit, urlunsplit, parse_qsl
from xml.etree import ElementTree as ET

from ..ai.secrets_store import decrypt

ROLE_CONTRACTS: dict[str, list[str]] = {
    "photo_source": ["url", "thumb_url", "title", "rights_owner", "license", "license_url", "width_px", "height_px", "source_page", "credit_line", "captured_at"],
    "text_source": ["title", "lead", "body", "published_at", "author", "url", "language"],
    "ai_provider": ["text", "input_tokens", "output_tokens"],
    "fact_source": ["claim", "value", "source_url", "date"],
    "agency": ["title", "body", "url", "published_at", "image_url"],
    "export_target": ["status", "remote_id", "url"],
    "storage": ["key", "url"],
}
MAX_BYTES = 8 * 1024 * 1024


class ConnectorError(RuntimeError):
    pass


def local_mode() -> bool:
    return os.getenv("ZECRO_LOCAL_MODE", "false" if os.getenv("VERCEL") else "true").lower() in {"1", "true", "yes", "on"}


def check_url(url: str, *, allow_private: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConnectorError("URL must be http(s)")
    if allow_private and local_mode():
        return
    host = parsed.hostname.lower()
    if host in {"localhost"} or host.endswith(".local") or host.endswith(".internal"):
        raise ConnectorError("private/localhost addresses are blocked in cloud mode")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        return  # unresolvable here; the request itself will fail
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ConnectorError("private addresses are blocked in cloud mode")


def _render(template: Any, params: dict[str, Any]) -> Any:
    if isinstance(template, dict):
        return {k: _render(v, params) for k, v in template.items()}
    if isinstance(template, list):
        return [_render(v, params) for v in template]
    if not isinstance(template, str):
        return template
    if "{{" in template or "{%" in template:
        from jinja2.sandbox import SandboxedEnvironment
        return SandboxedEnvironment(autoescape=False).from_string(template).render(**params)
    out = template
    for key, value in _flatten(params).items():
        out = out.replace("{" + key + "}", "" if value is None else str(value))
    return out


def _flatten(params: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in params.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, name + "."))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    flat.update(_flatten(item, f"{name}[{i}]."))
                else:
                    flat[f"{name}[{i}]"] = item
            flat[name] = ", ".join(str(v) for v in value if not isinstance(v, dict))
        else:
            flat[name] = value
    return flat


_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _auth(cfg: dict, secret: Optional[str], headers: dict, query: dict, session) -> Optional[tuple]:
    auth = cfg.get("auth") or {}
    kind = auth.get("type", "none")
    if kind == "none":
        return None
    if not secret:
        raise ConnectorError("this integration requires a secret (API key / password)")
    if kind == "header":
        headers[auth.get("name") or "X-Api-Key"] = (auth.get("prefix") or "") + secret
    elif kind == "query":
        query[auth.get("name") or "api_key"] = secret
    elif kind == "bearer":
        headers["Authorization"] = f"Bearer {secret}"
    elif kind == "basic":
        return (auth.get("username") or "", secret)
    elif kind == "oauth2_cc":
        cache_key = f"{auth.get('token_url')}|{auth.get('client_id')}"
        token, expiry = _TOKEN_CACHE.get(cache_key, ("", 0.0))
        if time.time() >= expiry - 30:
            check_url(auth["token_url"], allow_private=bool(cfg.get("allow_private")))
            r = session.post(auth["token_url"], data={"grant_type": "client_credentials", "client_id": auth.get("client_id"),
                                                     "client_secret": secret, **({"scope": auth["scope"]} if auth.get("scope") else {})}, timeout=15)
            if r.status_code >= 400:
                raise ConnectorError(f"OAuth token endpoint HTTP {r.status_code}")
            j = r.json()
            token, expiry = j["access_token"], time.time() + float(j.get("expires_in", 3600))
            _TOKEN_CACHE[cache_key] = (token, expiry)
        headers["Authorization"] = f"Bearer {token}"
    else:
        raise ConnectorError(f"unknown auth type {kind}")
    return None


def _jsonpath(expr: str, data: Any) -> list[Any]:
    from jsonpath_ng.ext import parse
    return [m.value for m in parse(expr).find(data)]


def _first(expr: str, data: Any) -> Any:
    if expr.startswith("$"):
        found = _jsonpath(expr, data)
        return found[0] if found else None
    if isinstance(data, ET.Element):
        node = data.find(expr)
        if node is None:
            return data.get(expr.lstrip("@")) if expr.startswith("@") else None
        return (node.text or "").strip() or node.get("url") or node.get("href")
    return data.get(expr) if isinstance(data, dict) else None


def map_response(payload: Any, mapping: dict[str, Any], role: str) -> tuple[list[dict], list[dict]]:
    """Return (items, errors).  Errors are per field so the panel can show them."""
    items_expr = mapping.get("items") or "$"
    fields = mapping.get("fields") or {}
    if isinstance(payload, ET.Element):
        nodes = payload.findall(items_expr if not items_expr.startswith("$") else ".//item")
    else:
        nodes = _jsonpath(items_expr, payload) if items_expr != "$" else [payload]
        if len(nodes) == 1 and isinstance(nodes[0], list):
            nodes = nodes[0]
    out, errors = [], []
    for index, node in enumerate(nodes):
        row: dict[str, Any] = {}
        for field, expr in fields.items():
            try:
                row[field] = _first(expr, node) if isinstance(expr, str) else expr
            except Exception as exc:
                errors.append({"item": index, "field": field, "error": str(exc)})
        missing = [f for f in ("url",) if role == "photo_source" and not row.get(f)]
        for f in missing:
            errors.append({"item": index, "field": f, "error": "required field is empty"})
        out.append(row)
    unknown = [f for f in fields if f not in ROLE_CONTRACTS.get(role, fields)]
    for f in unknown:
        errors.append({"item": None, "field": f, "error": f"field is not part of the {role} contract"})
    return out, errors


def execute(integration: dict, params: Optional[dict[str, Any]] = None, *, raw: bool = False) -> dict[str, Any]:
    import requests
    cfg = dict(integration.get("config_json") or integration.get("config") or {})
    params = {"limit": 10, "page": 1, "lang": "pl", **(params or {})}
    req = cfg.get("request") or {}
    kind = cfg.get("type", "rest")
    secret = decrypt(integration.get("secret_ref")) if integration.get("secret_ref") else integration.get("_secret")
    session = requests.Session()
    url = _render(req.get("url") or cfg.get("base_url") or "", params)
    check_url(url, allow_private=bool(cfg.get("allow_private")))
    headers = {k: str(v) for k, v in _render(req.get("headers") or {}, params).items()}
    headers.setdefault("User-Agent", "Zecro/1.0 (+https://zecro.pl)")
    query = {k: v for k, v in _render(req.get("query") or {}, params).items() if v not in (None, "")}
    basic = _auth(cfg, secret, headers, query, session)
    method = (req.get("method") or ("POST" if kind == "graphql" else "GET")).upper()
    body = None
    if kind == "graphql":
        body = json.dumps({"query": req.get("graphql_query", ""), "variables": _render(req.get("variables") or {}, params)})
        headers.setdefault("Content-Type", "application/json")
    elif req.get("body"):
        body = _render(req["body"], params)
        headers.setdefault("Content-Type", "application/json")
    pag = req.get("pagination") or {"type": "none"}
    pages = max(1, int(pag.get("max_pages", 1)))
    items, errors, raw_samples = [], [], []
    next_url: Optional[str] = None
    for page_index in range(pages):
        target = next_url or url
        q = dict(query)
        if pag.get("type") in {"page", "offset"} and page_index:
            q[pag.get("param", "page")] = (params["page"] + page_index) if pag["type"] == "page" else page_index * int(params["limit"])
        if q:
            parts = urlsplit(target)
            target = urlunsplit(parts._replace(query=urlencode({**dict(parse_qsl(parts.query)), **q})))
        check_url(target, allow_private=bool(cfg.get("allow_private")))
        r = session.request(method, target, headers=headers, data=body, auth=basic, timeout=float(req.get("timeout_s", 15)),
                            allow_redirects=False, stream=True)
        if r.is_redirect:
            raise ConnectorError("redirect blocked; configure the final URL")
        content = r.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(content) > MAX_BYTES:
            raise ConnectorError("response exceeds size limit")
        if r.status_code >= 400:
            raise ConnectorError(f"HTTP {r.status_code}: {content[:200]!r}")
        ctype = r.headers.get("Content-Type", "")
        if kind == "rss" or "xml" in ctype:
            payload: Any = ET.fromstring(content)
            raw_samples.append(content[:4000].decode("utf-8", "replace"))
        else:
            payload = json.loads(content.decode("utf-8"))
            raw_samples.append(payload)
        rows, errs = map_response(payload, cfg.get("mapping") or {}, cfg.get("role", "photo_source"))
        items.extend(rows)
        errors.extend(errs)
        if pag.get("type") == "cursor" and not isinstance(payload, ET.Element):
            next_url = _first(pag.get("cursor_path", "$.next"), payload)
            if not next_url:
                break
        elif pag.get("type") == "link":
            link = r.links.get("next", {}).get("url")
            if not link:
                break
            next_url = link
    result = {"status": "ready", "items": items, "errors": errors, "count": len(items)}
    if raw:
        result["raw"] = raw_samples[0] if len(raw_samples) == 1 else raw_samples
    return result


def call_custom_ai(route, system: str, user: str, schema: Any):
    """AI provider defined through the universal connector."""
    from ..models.database import db
    integration = db.get_integration(route.integration_id) if route.integration_id else None
    if not integration:
        raise ConnectorError("custom AI integration not found")
    cfg = dict(integration.get("config_json") or {})
    if cfg.get("type") == "openai_compatible":
        from ..ai.runtime import _call_openai_compatible
        return _call_openai_compatible(route, system, user, schema, [], None, None)
    out = execute(integration, {"system": system, "prompt": user, "schema": json.dumps(schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema or {})})
    if not out["items"]:
        raise ConnectorError("custom AI returned no mapped text")
    row = out["items"][0]
    from ..ai.runtime import _strip_json
    return _strip_json(str(row.get("text", ""))), row.get("input_tokens"), row.get("output_tokens")


# ---------------------------------------------------------------- OpenAPI
def import_openapi(spec: dict[str, Any], role: str = "photo_source") -> dict[str, Any]:
    servers = [s.get("url") for s in spec.get("servers", []) if s.get("url")] or ([f"https://{spec['host']}{spec.get('basePath', '')}"] if spec.get("host") else [])
    contract = ROLE_CONTRACTS.get(role, [])
    operations = []
    for path, methods in (spec.get("paths") or {}).items():
        for method, op in (methods or {}).items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            op = op or {}
            params = [{"name": p.get("name"), "in": p.get("in"), "required": bool(p.get("required"))} for p in op.get("parameters", []) if isinstance(p, dict)]
            schema = _response_schema(spec, op)
            items_path, props = _find_array(spec, schema, "$")
            suggestion = {f: f"$.{_best_match(f, props)}" for f in contract if _best_match(f, props)}
            operations.append({"method": method.upper(), "path": path, "operation_id": op.get("operationId"), "summary": op.get("summary"),
                               "parameters": params, "suggested_request": {"method": method.upper(), "url": (servers[0] if servers else "") + path},
                               "suggested_mapping": {"items": items_path, "fields": suggestion} if items_path else None})
    return {"status": "ready", "servers": servers, "operations": operations}


def _deref(spec: dict, node: Any) -> Any:
    seen = 0
    while isinstance(node, dict) and "$ref" in node and seen < 20:
        ref = node["$ref"].lstrip("#/").split("/")
        node = spec
        for part in ref:
            node = node.get(part, {})
        seen += 1
    return node


def _response_schema(spec: dict, op: dict) -> dict:
    responses = op.get("responses") or {}
    ok = responses.get("200") or responses.get(200) or next(iter(responses.values()), {})
    ok = _deref(spec, ok)
    content = ok.get("content") or {}
    media = content.get("application/json") or next(iter(content.values()), {}) if content else {}
    return _deref(spec, (media or {}).get("schema") or ok.get("schema") or {})


def _find_array(spec: dict, schema: dict, path: str, depth: int = 0) -> tuple[Optional[str], list[str]]:
    schema = _deref(spec, schema)
    if depth > 5 or not isinstance(schema, dict):
        return None, []
    if schema.get("type") == "array":
        item = _deref(spec, schema.get("items") or {})
        return path + "[*]", list((item.get("properties") or {}).keys())
    for name, prop in (schema.get("properties") or {}).items():
        found, props = _find_array(spec, prop, f"{path}.{name}", depth + 1)
        if found:
            return found, props
    return None, []


SYNONYMS = {"url": ["url", "image_url", "src", "link", "href"], "thumb_url": ["thumbnail", "thumb", "preview"],
            "rights_owner": ["creator", "author", "photographer", "owner", "artist", "user"], "license": ["license", "licence", "rights"],
            "license_url": ["license_url", "license_link"], "width_px": ["width"], "height_px": ["height"], "title": ["title", "name", "headline"],
            "source_page": ["foreign_landing_url", "page_url", "html_url", "landing"], "body": ["body", "content", "text"],
            "lead": ["summary", "description", "lead"], "published_at": ["published", "date", "created"], "author": ["author", "byline", "creator"]}


def _best_match(field: str, props: list[str]) -> Optional[str]:
    lowered = {p.lower(): p for p in props}
    for candidate in SYNONYMS.get(field, [field]):
        if candidate in lowered:
            return lowered[candidate]
    for candidate in SYNONYMS.get(field, [field]):
        for low, orig in lowered.items():
            if candidate in low:
                return orig
    return None
