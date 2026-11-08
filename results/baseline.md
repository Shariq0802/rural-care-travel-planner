### Baseline (regular expressions)

| Field | Correct | Accuracy | Made-up values |
|---|---|---|---|
| date | 16/20 | 80% | 1 |
| time | 17/20 | 85% | 0 |
| clinic | 18/20 | 90% | 0 |
| address | 20/20 | 100% | 0 |
| **all 4 fields right** | 12/20 | 60% | |

Mistakes:

- #1 (letter) date: expected `2026-11-24`, got `2026-11-02`
- #4 (letter) date: expected `2026-11-17`, got `2026-11-10`
- #4 (letter) time: expected `11:00`, got `14:00`
- #5 (letter) date: expected `2026-11-19`, got `2026-11-03`
- #7 (letter) time: expected `14:30`, got `None`
- #8 (letter) date: expected `None`, got `2026-12-07`
- #15 (letter) time: expected `10:15`, got `None`
- #19 (sms) clinic: expected `Millbank Health Centre`, got `None`
- #20 (sms) clinic: expected `Mill Road Surgery`, got `None`
