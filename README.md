# Rural Care Travel Planner — appointment extraction (Week 1)

Part of an accessible travel planner for blind and partially sighted people in rural Scotland who need to reach health appointments by bus.

This part reads an **appointment letter or SMS** and pulls out the **date, time, clinic and address** using an open-source LLM (run locally with Ollama). A person or carer then **confirms** the details before anything is planned.

## How it works

```
letter / SMS text ──► POST /extract ──► LLM (Ollama) ──► checks (valid date? valid HH:MM?)
                                                         │
                                  draft details ◄────────┘
                                        │
                     person or carer checks ──► POST /extract/{id}/confirm ──► saved in Postgres
```

- **Open-source model, runs locally.** No letter text leaves the machine.
- **Forced JSON.** Ollama structured output makes the model return the 4 fields only.
- **Checks after the model.** Impossible dates or non-`HH:MM` times become `null` with a warning.
- **Human in the loop.** Every result has `needs_confirmation: true`.
- **Privacy.** The letter text is never saved. Only the extracted fields are stored.
- **No guessing.** If a date or time is not exact (for example "in the week of 7 December"), the answer must be `null`.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d                 # Postgres on port 5432
ollama pull qwen2.5:7b               # open-source model (about 4.7 GB)

uvicorn app.main:app --reload        # API on http://localhost:8000/docs
```

Try it:

```bash
curl -s -X POST localhost:8000/extract -H 'content-type: application/json' -d '{
  "text": "Reminder: your appointment at Glenview Medical Practice, 4 Mill Lane, Glenview, KY99 2CD is on Thu 12 Nov at 2:40pm.",
  "reference_date": "2026-11-10"
}'
```

Settings (environment variables, see `.env.example`): `OLLAMA_MODEL`, `PROMPT_VERSION` (`v1` or `v2`), `EXTRACTOR` (`llm` or `baseline`).

## Test data

`data/letters.json` has **20 made-up** letters and SMS messages (no real patient data), built by `data/build_dataset.py`. They include hard cases:

| Case | Example |
|---|---|
| Several dates, only one is the appointment | letter date, "last seen" date |
| Rescheduled appointment | the **new** date and time are correct |
| Missing year | "Friday, 18th December" |
| Relative date | "tomorrow at 3pm" |
| Time in words | "half past two in the afternoon" |
| Not enough information | "in the week of 7 December" → must be `null` |
| Missing address | SMS with no address → must be `null` |
| Distractors | phone numbers, bus numbers, directions |
| Messy text | ALL CAPS, lower-case text-speak |

### How it is marked

- `date` and `time`: exact match.
- `clinic` and `address`: match after lower-casing and removing punctuation. Counts as right if equal, one contains the other, or word overlap is at least 60%.
- If the right answer is `null`, returning a value counts as a **made-up value**.

## Results

Run: `python -m eval.evaluate --extractor baseline|llm --prompt v1|v2`

**Baseline (simple regular expressions)** — measured:

| Field | Correct | Accuracy | Made-up values |
|---|---|---|---|
| date | 16/20 | 80% | 1 |
| time | 17/20 | 85% | 0 |
| clinic | 18/20 | 90% | 0 |
| address | 20/20 | 100% | 0 |
| **all 4 fields right** | **12/20** | **60%** | |

Baseline fails on: letter date taken instead of appointment date, rescheduled appointments, times in words, and a week-only date.

**LLM (`qwen2.5:7b`)** — _to be filled in after running on a machine with Ollama:_

| Prompt | date | time | clinic | address | all 4 right | made-up values |
|---|---|---|---|---|---|---|
| v1 (instructions only) | | | | | | |
| v2 (instructions + 3 examples) | | | | | | |

## Limits

- 20 messages is a small test set. It shows the approach works, not that it is ready for real use.
- The few-shot examples in prompt v2 are not in the test set.
- The address check is lenient (containment), so it cannot catch extra words in the address.
- Tables are created at start-up. Migrations (Alembic) are not set up yet.

## Tests

```bash
python -m pytest -q
```

The tests use a fake Ollama server, so they run without a model.

## Next (Week 2)

Bus timetable data, journey planning to the clinic, and replanning when a bus is late or cancelled.
