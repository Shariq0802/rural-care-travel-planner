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

## Journey planning (Week 2)

The app plans the bus trip to the appointment, and the way home, and replans when a bus is late or cancelled.

| Endpoint | What it does |
|---|---|
| `GET /stops` | Bus stops, with a flag for **request stops** (the passenger must signal the driver) |
| `GET /places?q=` | Match a clinic name (for example from `/extract`) to the nearest bus stop |
| `POST /plan` | Latest bus that arrives `buffer_minutes` (default 15) before the appointment, earlier buses as safer alternatives, and the bus home |
| `POST /replan` | Bus late or cancelled: keep it, pick the next bus, or say "late" and suggest community transport |

`/replan` status: `on_time` (late, but still fine), `replanned` (another bus works), `tight` (arrives before the appointment but inside the buffer), `late` (no bus works: community transport and tell the clinic).
Every response has a short `message` that can be read out loud, and step-by-step `steps` for the journey.

**Timetable data.** `data/gtfs_sample/` is a **made-up** rural route 42 (6 stops, 14 trips, few buses, several request stops) in standard GTFS format, built by `data/build_gtfs_sample.py`. It loads into Postgres on first start, or with `python -m app.load_gtfs <folder>`. Real GTFS data can replace it. Times are local times; a trip after midnight is not handled yet.

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

Settings (environment variables, see `.env.example`): `OLLAMA_MODEL`, `PROMPT_VERSION` (`v1`, `v2` or `v3`), `EXTRACTOR` (`llm` or `baseline`).

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

Run: `python -m eval.evaluate --extractor baseline|llm --prompt v1|v2|v3`

**Baseline (simple regular expressions)** — measured:

| Field | Correct | Accuracy | Made-up values |
|---|---|---|---|
| date | 16/20 | 80% | 1 |
| time | 17/20 | 85% | 0 |
| clinic | 18/20 | 90% | 0 |
| address | 20/20 | 100% | 0 |
| **all 4 fields right** | **12/20** | **60%** | |

Baseline fails on: letter date taken instead of appointment date, rescheduled appointments, times in words, and a week-only date.

**LLM (`qwen2.5:7b`, run locally with Ollama)** — measured on the same 20 messages:

| Prompt | date | time | clinic | address | all 4 right | made-up values |
|---|---|---|---|---|---|---|
| Baseline (regex) | 80% | 85% | 90% | 100% | 12/20 | 1 |
| v1 (instructions only) | 95% | 100% | 90% | 95% | 16/20 | 1 |
| v2 (instructions + 3 examples) | 100% | 100% | 90% | 95% | 17/20 | 0 |
| v3 (v2 + 2 rules + 2 examples) | 100% | 100% | 95% | 100% | 19/20 | 0 |

What v1 and v2 got wrong:
- **Clinic (#1, #11):** the model gave the department ("Physiotherapy Department") instead of the building ("Corrieden Cottage Hospital").
- **Address (#19):** the model mis-copied a postcode written in capitals (`FK99 1BC` became `FK9 91BC`).
- **Made-up date (#8, v1 only):** it invented a date from "in the week of 7 December". Examples in v2 fixed this.

v3 fixed all three v2 mistakes but caused one new one: #9, "Rosemount Physio" was returned as `null` because the new "building, not service" rule made the model treat a physio practice as a service. Net result: 17/20 to 19/20. Tuning further on these same 20 messages would be overfitting, so I stopped here.

v3 adds a rule to give the facility not the department, a rule to copy addresses exactly, and two new examples (not from the test set).

### Safety check: "found in the message?"

After the model answers, the API checks that the clinic and address are written word-for-word in the original message. If not, it adds a warning so the person or carer looks at it again. This catches mis-copied text such as the postcode error above. It does not check dates or times.

## Limits

- 20 messages is a small test set. It shows the approach works, not that it is ready for real use.
- The few-shot examples in prompts v2 and v3 are not in the test set. But the v3 rules were written after seeing the v2 mistakes, so the 20 messages are no longer a fully fair test for v3. A fresh set of unseen messages is needed to confirm it.
- The address check is lenient (containment), so it cannot catch extra words in the address.
- Tables are created at start-up. Migrations (Alembic) are not set up yet.

## Tests

```bash
python -m pytest -q
```

The tests use a fake Ollama server, so they run without a model.

## Next

Community transport booking, login and roles, GDPR items, simulated live journey alerts ("bus arriving, signal the driver", "your stop is next"), then the Flutter app.
