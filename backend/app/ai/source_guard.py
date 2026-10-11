"""Two-pass source guard for generated copy.

Pass 1 (deterministic): numbers, dates, quotes and proper names in the output
must be present in the source (Polish inflection tolerated by stem prefix).
Pass 2 (AI, optional): sentence-by-sentence verification against the source.
A variant with any ``unsupported`` item cannot be approved without an editor.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class GuardFlag:
    value: str
    status: str
    source_excerpt: Optional[str] = None
    reason: Optional[str] = None
    kind: str = "value"


@dataclass
class GuardResult:
    status: str
    flags: list[GuardFlag]
    unsupported: list[str]
    provenance: dict[str, Any] = field(default_factory=dict)
    sentences: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "unsupported": self.unsupported, "flags": [f.__dict__ for f in self.flags],
                "sentences": self.sentences, "provenance": self.provenance}


_NUMERIC = re.compile(r"(?<![\w,.])\d+(?:[  ]\d{3})*(?:[,.]\d+)?(?:\s?%)?|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")
_QUOTED = re.compile(r"„[^”\"]{3,}[”\"]|“[^”]{3,}”|\"[^\"]{3,}\"")
_NAME_TOKEN = r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:-[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?"
_NAMES = re.compile(rf"(?<![.!?]\s)(?<!^)\b{_NAME_TOKEN}(?:\s+{_NAME_TOKEN})+")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[ ]", " ", text or "")).strip().casefold()


def _stem(word: str) -> str:
    word = word.casefold()
    return word[: max(4, len(word) - 3)] if len(word) > 5 else word


def _num_key(value: str) -> str:
    return re.sub(r"[  ]", "", value).replace(",", ".").rstrip("%").strip()


def _supported(value: str, kind: str, source: str) -> bool:
    src = _norm(source)
    if kind == "number":
        key = _num_key(value)
        return any(_num_key(m.group(0)) == key for m in _NUMERIC.finditer(source or ""))
    if kind == "quote":
        inner = _norm(value.strip("„”“\""))
        return inner in src
    tokens = [t for t in re.findall(r"\w+", value) if len(t) > 1]
    src_tokens = set(_stem(t) for t in re.findall(r"\w+", source or ""))
    return bool(tokens) and all(_stem(t) in src_tokens for t in tokens)


def deterministic_guard(output: str, source: str) -> GuardResult:
    flags: list[GuardFlag] = []
    seen = set()
    for kind, regex in (("number", _NUMERIC), ("quote", _QUOTED), ("name", _NAMES)):
        for match in regex.finditer(output or ""):
            value = match.group(0).strip()
            if (kind, value) in seen:
                continue
            seen.add((kind, value))
            ok = _supported(value, kind, source)
            flags.append(GuardFlag(value=value, kind=kind, status="supported" if ok else "unsupported",
                                   reason=None if ok else "brak w materiale źródłowym"))
    unsupported = [f.value for f in flags if f.status == "unsupported"]
    return GuardResult("unsupported" if unsupported else "supported", flags, unsupported,
                       {"source_guard": "deterministic-v2"})


def guard_generated_text(output: str, source: str, *, provider: str = "deterministic-local", ai_pass: bool = False,
                         project_id: Optional[str] = None) -> GuardResult:
    result = deterministic_guard(output, source)
    result.provenance["provider"] = provider
    if not ai_pass:
        return result
    try:
        from .runtime import run_task
        from .schemas import FactCheck
        checked = run_task("fact_guard", "fact_guard", {"output": output, "source": source}, FactCheck, project_id=project_id)
        result.sentences = checked.data["sentences"]
        result.provenance["ai_pass"] = checked.provenance
        bad = [s["sentence"] for s in result.sentences if s["status"] != "supported"]
        for sentence in bad:
            result.flags.append(GuardFlag(value=sentence, kind="sentence", status="unsupported",
                                          reason=next((s.get("problem") for s in result.sentences if s["sentence"] == sentence), "")))
        result.unsupported += bad
        result.status = "unsupported" if result.unsupported else "supported"
    except Exception as exc:  # AI pass unavailable: say so, keep deterministic result
        result.provenance["ai_pass"] = {"status": "unavailable", "reason": str(exc)[:300]}
    return result
