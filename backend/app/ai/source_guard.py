"""Conservative deterministic source guard for generated copy."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

@dataclass
class GuardFlag:
    value: str
    status: str
    source_excerpt: str | None = None
    reason: str | None = None

@dataclass
class GuardResult:
    status: str
    flags: list[GuardFlag]
    unsupported: list[str]
    provenance: dict[str, Any]

_NUMERIC = re.compile(r"(?<!\w)(?:\d+(?:[,.]\d+)?|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})(?!\w)")
_QUOTED = re.compile(r'“[^”]+”|„[^”]+”|"[^"]+"')
_NAMES = re.compile(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]*(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻ-]*)+")

def _evidence(value: str, source: str) -> bool:
    norm=lambda x: re.sub(r"[^\wąęółśżźćń ]", " ", x.casefold())
    target=norm(value).split(); hay=norm(source)
    if value.casefold().strip().isdigit():
        return bool(re.search(rf"(?<!\w){re.escape(value.strip())}(?!\w)", source))
    if value.casefold() in source.casefold(): return True
    return bool(target and all(token in hay for token in target if len(token)>2))

def guard_generated_text(output: str, source: str, *, provider: str = "deterministic-local") -> GuardResult:
    values=[]
    for regex in (_NUMERIC, _QUOTED, _NAMES): values.extend(match.group(0) for match in regex.finditer(output or ""))
    flags=[]; unsupported=[]
    for value in dict.fromkeys(values):
        supported=_evidence(value, source or "")
        flags.append(GuardFlag(value=value,status="supported" if supported else "unsupported",source_excerpt=value if supported else None,reason=None if supported else "value is absent from supplied source"))
        if not supported: unsupported.append(value)
    return GuardResult(status="unsupported" if unsupported else "supported", flags=flags, unsupported=unsupported, provenance={"provider":provider,"source_guard":"deterministic-v1"})
