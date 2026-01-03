"""Parsing + canonicalization for PHQ-8 juror outputs."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from vibe_check.schemas.scoring import (
    MAX_EVIDENCE_SNIPPET_CHARS,
    MAX_EVIDENCE_SNIPPET_WORDS,
    PHQ8ItemScore,
    PHQ8Report,
    TokenUsage,
)

PHQ8_ITEMS: tuple[str, ...] = (
    "anhedonia",
    "depressed_mood",
    "sleep",
    "fatigue",
    "appetite",
    "guilt",
    "concentration",
    "psychomotor",
)


class ParseError(ValueError):
    """Model output could not be parsed or canonicalized into a PHQ8Report."""


class SchemaError(ParseError):
    """Model output parsed but failed schema validation."""


def _extract_first_json_object(text: str) -> Any:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start == -1:
        raise ParseError("No JSON object found in output")

    depth = 0
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    raise ParseError("Could not parse JSON object from output")


def _truncate_snippet(snippet: str) -> str:
    cleaned = snippet.strip()
    if len(cleaned) > MAX_EVIDENCE_SNIPPET_CHARS:
        cleaned = cleaned[:MAX_EVIDENCE_SNIPPET_CHARS].rstrip()

    words = cleaned.split()
    if len(words) > MAX_EVIDENCE_SNIPPET_WORDS:
        cleaned = " ".join(words[:MAX_EVIDENCE_SNIPPET_WORDS]).rstrip()
    return cleaned


def _canonicalize_evidence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        raise ParseError("evidence must be a string or list of strings")

    snippets: list[str] = []
    for raw in candidates:
        text = str(raw).strip()
        if not text:
            continue
        snippets.append(_truncate_snippet(text))
        if len(snippets) >= 3:
            break
    return snippets


def _canonicalize_item(item_name: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ParseError(f"{item_name} must be an object")

    score_raw = raw.get("score")
    if score_raw is None:
        raise ParseError(f"{item_name}.score must be 0..3")
    try:
        score = int(score_raw)
    except (TypeError, ValueError) as e:
        raise ParseError(f"{item_name}.score must be 0..3") from e
    if score not in (0, 1, 2, 3):
        raise ParseError(f"{item_name}.score must be 0..3")

    confidence_raw = raw.get("confidence")
    if confidence_raw is None:
        raise ParseError(f"{item_name}.confidence is required")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError) as e:
        raise ParseError(f"{item_name}.confidence must be 0..1") from e

    insuff = raw.get("insufficient_evidence", raw.get("insuff_evidence", False))
    insufficient_evidence = bool(insuff)

    evidence = _canonicalize_evidence(raw.get("evidence"))

    return {
        "score": score,
        "confidence": confidence,
        "evidence": evidence,
        "insufficient_evidence": insufficient_evidence,
    }


def parse_phq8_report(
    raw_output: Any,
    *,
    model_id: str,
    run_number: int,
    usage: TokenUsage | None = None,
    scored_at: datetime | None = None,
) -> PHQ8Report:
    """Parse model output into a validated `PHQ8Report` (canonical totals, bounded evidence)."""
    payload: Any = raw_output
    if isinstance(payload, str):
        payload = _extract_first_json_object(payload)

    if not isinstance(payload, dict):
        raise ParseError("Top-level output must be a JSON object")

    if "items" in payload and isinstance(payload["items"], dict):
        merged = dict(payload)
        merged.update(payload["items"])
        payload = merged

    missing = [item for item in PHQ8_ITEMS if item not in payload]
    if missing:
        raise ParseError(f"Missing PHQ-8 items: {missing}")

    items: dict[str, PHQ8ItemScore] = {}
    for item in PHQ8_ITEMS:
        try:
            items[item] = PHQ8ItemScore(**_canonicalize_item(item, payload[item]))
        except ValidationError as e:
            raise SchemaError(f"Invalid item schema for {item}") from e

    mentions_self_harm = bool(
        payload.get(
            "mentions_self_harm",
            payload.get("self_harm", False),
        )
    )
    self_harm_evidence = _canonicalize_evidence(payload.get("self_harm_evidence"))

    total_score = sum(int(items[item].score) for item in PHQ8_ITEMS)

    data: dict[str, Any] = {
        "model_id": model_id,
        "run_number": run_number,
        **items,
        "total_score": total_score,
        "mentions_self_harm": mentions_self_harm,
        "self_harm_evidence": self_harm_evidence,
        "usage": usage,
        "scored_at": scored_at or datetime.utcnow(),
    }

    try:
        return PHQ8Report(**data)
    except ValidationError as e:
        raise SchemaError("Output did not validate as PHQ8Report") from e
