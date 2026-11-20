Columns: tiered points, Flexible Bilt Cash, $200, $400, $600   (E established, - not available, U unresolved)

| Finding | Case | Day | 88d1cdf | branch | branch, unapproved | branch flags |
|---|---|---|---|---|---|---|
| A1 | opened 2026-03-10 only, nothing else recorded | 2027-05-11 | `UUUUU` | `UUUUU` | `UUUUU` | ANNIVERSARY_NOT_RECORDED, ELECTION_NOT_RECORDED |
| A1 | same, a year later | 2028-01-01 | `UUUUU` | `UUUUU` | `UUUUU` | ANNIVERSARY_NOT_RECORDED, ELECTION_NOT_RECORDED |
| A1 | Legacy left 2027-09-05, no issuer anniversary: the $600 | 2028-06-01 | `E---E` | `UUUUU` | `UUUUU` | ANNIVERSARY_NOT_RECORDED, ELECTION_TERMS_UNVERIFIED |
| A1 | same with the issuer's anniversary (control) | 2028-06-01 | `E---E` | `E---E` | `UUUUU` | ELECTION_SUPERSEDED |
| A2 | Legacy Election, no Flexible Bilt Cash record | 2027-05-01 | `-EEE-` | `UUUUU` | `UUUUU` | ELECTION_TERMS_UNVERIFIED |
| A2 | Legacy Election while Housing-only was active | 2027-05-01 | `-EEE-` | `UUUUU` | `UUUUU` | ELECTION_NOT_PERMITTED |
| A2 | Legacy Election with Flexible Bilt Cash shown (control) | 2027-05-01 | `-EEE-` | `-EEE-` | `UUUUU` | - |
| A3 | switch requested 06-10, effective 06-15 (cycle day 15): day 06-12 | 2026-06-12 | `E-EE-` | `E-EE-` | `UUUU-` | - |
| A3 | same: day 06-15 | 2026-06-15 | `-EEE-` | `-EEE-` | `UUUU-` | - |
| A3 | request day typed as the start (cycle day 15) | 2026-06-12 | `-EEE-` | `UUEE-` | `UUUU-` | ELECTION_EFFECTIVE_DATE_INVALID |
| A3 | exit recorded effective on its request day | 2027-08-25 | `E----` | `UUUUU` | `UUUUU` | ELECTION_EFFECTIVE_DATE_INVALID |
| ok-None | Legacy Election with no start date | 2027-07-01 | `-EEE-` | `UUUUU` | `UUUUU` | ELECTION_TERMS_UNVERIFIED |
