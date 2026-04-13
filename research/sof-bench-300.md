# SQL-on-FHIR vs Python Parser — Benchmark (n=300 bundles)

## Ingest (parse bundles → query-ready form)

| Approach       | Time (s) | Loaded                       |
|----------------|---------:|------------------------------|
| Python parser  |    3.86  | 300 PatientRecord objects |
| SQL-on-FHIR    |    7.18  | SQLite rows: patient=300, condition=2151, medication_request=2565, observation=59537, encounter=10570 |

## Query latency (median of 3 runs, ms)

| Query                                | Python (ms) | SQL (ms) | Δ (×)  | Same answer? |
|--------------------------------------|------------:|---------:|-------:|-------------:|
| Top 10 SNOMED conditions             |        1.48 |     0.60 |   2.5× |      ✓       |
| Top 10 RxNorm medications            |        0.55 |     0.65 |   0.9× |      ✓       |
| Patients on NSAID/anticoagulant      |        1.16 |     0.96 |   1.2× |      ✓       |
| Active condition × active medication |        1.69 |     4.43 |   0.4× |      ✓       |
| Avg BMI ≥ 2 readings                 |        7.00 |    10.44 |   0.7× |      ✓       |
| **Total**                            |       11.89 |    17.09 |   0.7× |              |

## Query code surface (lines of non-trivial logic)

| Query                                | Python LOC | SQL LOC |
|--------------------------------------|-----------:|--------:|
| Top 10 SNOMED conditions             |          9 |       6 |
| Top 10 RxNorm medications            |          7 |       5 |
| Patients on NSAID/anticoagulant      |          8 |       8 |
| Active condition × active medication |         11 |       7 |
| Avg BMI ≥ 2 readings                 |         12 |      10 |

