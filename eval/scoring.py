"""How extractor answers are marked.

- date, time: must match exactly.
- clinic, address: text match after lower-casing and removing punctuation.
  A match is: equal, or one contains the other, or word overlap (Jaccard) >= 0.6.
- If the right answer is null, the extractor must also return null.
  Returning a value there counts as a "made-up value" (hallucination).
"""
import re

FIELDS = ("date", "time", "clinic", "address")
TEXT_FIELDS = ("clinic", "address")


def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def text_match(expected, predicted):
    if expected is None and predicted is None:
        return True
    if expected is None or predicted is None:
        return False
    e, p = norm(expected), norm(predicted)
    if not e or not p:
        return False
    if e == p or e in p or p in e:
        return True
    ew, pw = set(e.split()), set(p.split())
    return len(ew & pw) / len(ew | pw) >= 0.6


def field_match(field, expected, predicted):
    if field in TEXT_FIELDS:
        return text_match(expected, predicted)
    return expected == predicted


def score_one(expected, predicted):
    """Return {field: bool} for one sample."""
    return {f: field_match(f, expected.get(f), predicted.get(f)) for f in FIELDS}


def summarise(rows):
    """rows: list of dicts with 'expected', 'predicted', 'correct'. Returns per-field stats."""
    n = len(rows)
    summary = {}
    for f in FIELDS:
        right = sum(1 for r in rows if r["correct"][f])
        made_up = sum(1 for r in rows if r["expected"].get(f) is None and r["predicted"].get(f) is not None)
        summary[f] = {"correct": right, "total": n, "accuracy": right / n if n else 0.0, "made_up": made_up}
    all_right = sum(1 for r in rows if all(r["correct"].values()))
    summary["all_fields"] = {"correct": all_right, "total": n, "accuracy": all_right / n if n else 0.0}
    return summary
