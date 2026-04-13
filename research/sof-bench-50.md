# SQL-on-FHIR vs Python Parser — Benchmark (n=50 bundles)

## Ingest (parse bundles → query-ready form)

| Approach       | Time (s) | Loaded                       |
|----------------|---------:|------------------------------|
| Python parser  |    0.53  | 50 PatientRecord objects |
| SQL-on-FHIR    |    1.02  | SQLite rows: patient=50, condition=303, medication_request=320, observation=9089, encounter=1394 |

## Query latency (median of 3 runs, ms)

| Query                                | Python (ms) | SQL (ms) | Δ (×)  | Same answer? |
|--------------------------------------|------------:|---------:|-------:|-------------:|
| Top 10 SNOMED conditions             |        0.10 |     0.10 |   0.9× |      ✓       |
| Top 10 RxNorm medications            |        0.08 |     0.15 |   0.5× |      ✓       |
| Patients on NSAID/anticoagulant      |        0.17 |     0.17 |   1.0× |      ✓       |
| Active condition × active medication |        0.08 |     0.39 |   0.2× |      ✓       |
| Avg BMI ≥ 2 readings                 |        0.46 |     1.47 |   0.3× |      ✓       |
| **Total**                            |        0.90 |     2.29 |   0.4× |              |

## Query code surface (lines of non-trivial logic)

| Query                                | Python LOC | SQL LOC |
|--------------------------------------|-----------:|--------:|
| Top 10 SNOMED conditions             |          9 |       6 |
| Top 10 RxNorm medications            |          7 |       5 |
| Patients on NSAID/anticoagulant      |          8 |       8 |
| Active condition × active medication |         11 |       7 |
| Avg BMI ≥ 2 readings                 |         12 |      10 |

