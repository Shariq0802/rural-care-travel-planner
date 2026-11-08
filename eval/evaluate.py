"""Test an extractor on the 20 made-up messages and print a per-field accuracy table.

Examples (run from the project root):
  python -m eval.evaluate --extractor baseline
  python -m eval.evaluate --extractor llm --prompt v1
  python -m eval.evaluate --extractor llm --prompt v2
Results are saved to results/<name>.json and results/<name>.md
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app import config
from app.extractor_baseline import extract_baseline
from app.extractor_llm import LLMError, extract_llm
from eval.scoring import FIELDS, score_one, summarise

ROOT = Path(__file__).resolve().parent.parent


def run(extractor, prompt, model, data_path):
    samples = json.loads(Path(data_path).read_text(encoding="utf-8"))
    rows = []
    for s in samples:
        ref = date.fromisoformat(s["reference_date"])
        try:
            if extractor == "baseline":
                predicted, warnings = extract_baseline(s["text"], ref)
            else:
                predicted, warnings = extract_llm(s["text"], ref, model=model, prompt_version=prompt)
        except LLMError as exc:
            print(f"sample {s['id']}: {exc}", file=sys.stderr)
            predicted, warnings = {f: None for f in FIELDS}, [str(exc)]
        rows.append(
            {
                "id": s["id"],
                "kind": s["kind"],
                "expected": s["expected"],
                "predicted": predicted,
                "warnings": warnings,
                "correct": score_one(s["expected"], predicted),
            }
        )
    return rows


def to_markdown(title, summary, rows):
    lines = [f"### {title}", "", "| Field | Correct | Accuracy | Made-up values |", "|---|---|---|---|"]
    for f in FIELDS:
        s = summary[f]
        lines.append(f"| {f} | {s['correct']}/{s['total']} | {s['accuracy']:.0%} | {s['made_up']} |")
    a = summary["all_fields"]
    lines.append(f"| **all 4 fields right** | {a['correct']}/{a['total']} | {a['accuracy']:.0%} | |")
    lines += ["", "Mistakes:", ""]
    wrong = [r for r in rows if not all(r["correct"].values())]
    if not wrong:
        lines.append("- none")
    for r in wrong:
        for f in FIELDS:
            if not r["correct"][f]:
                lines.append(
                    f"- #{r['id']} ({r['kind']}) {f}: expected `{r['expected'].get(f)}`, got `{r['predicted'].get(f)}`"
                )
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--extractor", choices=["baseline", "llm"], default="llm")
    p.add_argument("--prompt", default=config.PROMPT_VERSION, help="v1 or v2 (llm only)")
    p.add_argument("--model", default=config.OLLAMA_MODEL)
    p.add_argument("--data", default=str(ROOT / "data" / "letters.json"))
    p.add_argument("--name", default=None, help="output file name (default is built from the options)")
    args = p.parse_args()

    rows = run(args.extractor, args.prompt, args.model, args.data)
    summary = summarise(rows)

    if args.extractor == "baseline":
        title, name = "Baseline (regular expressions)", "baseline"
    else:
        safe_model = args.model.replace(":", "-").replace("/", "-")
        title, name = f"LLM {args.model}, prompt {args.prompt}", f"llm_{safe_model}_{args.prompt}"
    name = args.name or name

    md = to_markdown(title, summary, rows)
    print(md)

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / f"{name}.json").write_text(json.dumps({"title": title, "summary": summary, "rows": rows}, indent=2))
    (out / f"{name}.md").write_text(md)
    print(f"saved results/{name}.json and results/{name}.md")


if __name__ == "__main__":
    main()
