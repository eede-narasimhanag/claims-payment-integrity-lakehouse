# Data model

## Canonical claim line (`silver_claim_line`, input to the rules)

| Column | Type | Notes |
|---|---|---|
| claim_id | string | One claim has 1-3 lines |
| line_id | string | Unique per line; business key for upserts |
| member_id | string | Synthea patient Id (or generated) |
| provider_id | string | Synthea provider Id (or generated) |
| service_date | date | |
| procedure_code | string | Demo codes `PR100`..`PR600`; not CPT/HCPCS |
| diagnosis_code | string | ICD-10-CM style, e.g. `E11.9` |
| units | int | |
| billed_amount / allowed_amount / paid_amount | decimal(12,2) | |
| place_of_service, claim_status | string | |
| load_date | date | Batch date, used by SCD2 and watermarks |

## Other inputs

- `eligibility`: member_id, coverage_start, coverage_end (blank = open-ended)
- `members`: member_id, birth_date, gender, state, load_date
- `providers`: provider_id, name, specialty, state, load_date
- `procedure_dx_rules`: procedure_code, dx_prefix (allowed diagnosis prefixes per procedure)

## Gold

- `dim_member`, `dim_provider`: SCD2 (`attr_hash`, `effective_start`, `effective_end`, `is_current`)
- `fact_claim_line`: canonical columns + `flag_duplicate`, `flag_overbilled`, `flag_code_mismatch`,
  `flag_outside_coverage`, `flag_invalid_amount`, `flag_count`, `is_flagged`, `flag_reasons`
- `rule_summary`: flagged lines and paid amount per rule

## Using real Synthea files

The generator only reads `Id` (and optionally `BIRTHDATE`, `GENDER`, `STATE`, `NAME`, `SPECIALITY`) from
Synthea's `patients.csv` / `providers.csv`. **Check these headers against the files your Synthea version produces**
(enable CSV export in `synthea.properties`) and adjust `load_people()` if they differ. Synthea's own claim files are not
reshaped here because the project needs labelled anomalies.

## Reference: what the amounts mean

- **Billed**: what the provider charged. **Allowed**: contracted/maximum payable. **Paid**: what the plan paid.
