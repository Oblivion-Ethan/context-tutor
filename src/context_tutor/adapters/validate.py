from __future__ import annotations


VALID_STATUS = {"draft", "reviewed", "retired"}
MAX_TEXT = 600


def normalize_analysis(payload: dict) -> tuple[dict, list[str]]:
    """Validate and normalize an adapter result before it enters the library."""
    errors: list[str] = []
    sense = str(payload.get("sense") or "").strip()
    if not sense:
        errors.append("missing sense")
    if sense.startswith("适配器调用失败") or sense.startswith("适配器返回格式不可解析"):
        errors.append("adapter error")
    if len(sense) > MAX_TEXT:
        errors.append("sense too long")
        sense = sense[:MAX_TEXT]

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
        errors.append("confidence not numeric")
    confidence = max(0.0, min(1.0, confidence))

    status = str(payload.get("status") or "draft")
    if status not in VALID_STATUS:
        errors.append(f"invalid status: {status}")
        status = "draft"

    collocations = payload.get("collocations") or []
    if not isinstance(collocations, list):
        errors.append("collocations not a list")
        collocations = []
    collocations = [str(item).strip() for item in collocations if str(item).strip()][:3]

    return (
        {
            "sense": sense,
            "why": str(payload.get("why") or "").strip(),
            "collocations": collocations,
            "register": str(payload.get("register") or "").strip(),
            "example": str(payload.get("example") or "").strip(),
            "confidence": confidence,
            "status": status,
        },
        errors,
    )
