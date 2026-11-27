"""Number-level grounding validator (D-4)."""

import re
from typing import Any, Dict, List, Set

TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})\b")
NUM_PATTERN = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
LIST_MARKER_PATTERN = re.compile(r"(?m)^\s*\d+[\.\)]\s+")


def _extract_tool_numbers(obj: Any, out: Set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(abs(float(obj)))
    elif isinstance(obj, str):
        # Extract hours from time-window strings returned by engine tools (e.g. "18:00-22:00")
        for m in TIME_PATTERN.finditer(obj):
            out.add(float(int(m.group(1))))
    elif isinstance(obj, dict):
        for v in obj.values():
            _extract_tool_numbers(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _extract_tool_numbers(item, out)


def _extract_text_numbers(text: str) -> List[tuple[float, int]]:
    """Return list of (abs_value, decimal_places) from prose, treating HH:MM as HH."""
    cleaned = LIST_MARKER_PATTERN.sub("", text)
    results: List[tuple[float, int]] = []

    def _time_repl(m: re.Match) -> str:
        hr = int(m.group(1))
        results.append((float(hr), 0))
        return " "

    cleaned = TIME_PATTERN.sub(_time_repl, cleaned)

    for raw in NUM_PATTERN.findall(cleaned):
        norm = raw.replace(",", "")
        try:
            val = abs(float(norm))
        except ValueError:
            continue
        dp = len(norm.split(".")[1]) if "." in norm else 0
        results.append((val, dp))
    return results


def _matches_any(val: float, dp: int, pool: Set[float]) -> bool:
    for ref in pool:
        if round(ref, dp) == round(val, dp) or abs(ref - val) < 1e-6:
            return True
    return False


def check(
    reply: str,
    tool_outputs: List[Any],
    kb_outputs: List[Any] | None = None,
    user_text: str = "",
) -> Dict[str, Any]:
    """Verify every number in reply against tool_outputs; report KB-only numbers separately."""
    engine_nums: Set[float] = set()
    _extract_tool_numbers(tool_outputs, engine_nums)

    kb_nums: Set[float] = set()
    if kb_outputs:
        for item in kb_outputs:
            if isinstance(item, dict) and "text" in item:
                for v, _ in _extract_text_numbers(item["text"]):
                    kb_nums.add(v)
            elif isinstance(item, list):
                for sub in item:
                    if isinstance(sub, dict) and "text" in sub:
                        for v, _ in _extract_text_numbers(sub["text"]):
                            kb_nums.add(v)

    user_nums = {v for v, _ in _extract_text_numbers(user_text)}

    reply_nums = _extract_text_numbers(reply)
    checked_numbers: List[float] = []
    ungrounded: List[float] = []
    from_documents: List[float] = []

    for val, dp in reply_nums:
        # Ignore small counting integers 0-5 and numbers typed by the user
        if dp == 0 and 0 <= val <= 5:
            continue
        if _matches_any(val, dp, user_nums):
            continue

        checked_numbers.append(val)
        if _matches_any(val, dp, engine_nums):
            continue
        if _matches_any(val, dp, kb_nums):
            from_documents.append(val)
            continue
        ungrounded.append(val)

    return {
        "grounded": len(ungrounded) == 0,
        "numbers": checked_numbers,
        "ungrounded": ungrounded,
        "from_documents": from_documents,
    }
