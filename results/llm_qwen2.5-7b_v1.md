### LLM qwen2.5:7b, prompt v1

| Field | Correct | Accuracy | Made-up values |
|---|---|---|---|
| date | 19/20 | 95% | 1 |
| time | 20/20 | 100% | 0 |
| clinic | 18/20 | 90% | 0 |
| address | 19/20 | 95% | 0 |
| **all 4 fields right** | 16/20 | 80% | |

Mistakes:

- #1 (letter) clinic: expected `Dunmore Community Hospital`, got `Ophthalmology Outpatient Clinic`
- #8 (letter) date: expected `None`, got `2026-12-07`
- #11 (letter) clinic: expected `Corrieden Cottage Hospital`, got `Physiotherapy Department`
- #19 (sms) address: expected `3 Croft Road, Millbank, FK99 1BC`, got `3 CROFT ROAD, MILLBANK, FK9 91BC`
