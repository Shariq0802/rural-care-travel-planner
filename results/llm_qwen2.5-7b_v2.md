### LLM qwen2.5:7b, prompt v2

| Field | Correct | Accuracy | Made-up values |
|---|---|---|---|
| date | 20/20 | 100% | 0 |
| time | 20/20 | 100% | 0 |
| clinic | 18/20 | 90% | 0 |
| address | 19/20 | 95% | 0 |
| **all 4 fields right** | 17/20 | 85% | |

Mistakes:

- #1 (letter) clinic: expected `Dunmore Community Hospital`, got `Ophthalmology Outpatient Clinic`
- #11 (letter) clinic: expected `Corrieden Cottage Hospital`, got `Physiotherapy Department`
- #19 (sms) address: expected `3 Croft Road, Millbank, FK99 1BC`, got `3 Croft Road, Millbank, FK9 91BC`
