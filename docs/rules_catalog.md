# Rules catalog

Payment integrity = finding improper payments (overpayments, duplicates, ineligible members, coding errors) before
payment (pre-pay) or after (post-pay recovery). These rules are simplified teaching versions.

| Flag | Reason code | Logic | Known limitation |
|---|---|---|---|
| `flag_duplicate` | DUPLICATE_LINE | Same member, provider, service date, procedure and billed amount as an earlier line (ordered by claim_id, line_id). First occurrence stays clean | Legitimate repeat services on one day (e.g. bilateral procedures) would be flagged; real edits use modifiers |
| `flag_overbilled` | OVERBILLED | billed per unit > 3 x reference allowed per unit for the procedure | Reference is the data's own median unless a fee schedule is supplied; threshold is arbitrary |
| `flag_code_mismatch` | PROC_DX_MISMATCH | Procedure is in `procedure_dx_rules` and the diagnosis starts with none of its allowed prefixes; missing diagnosis on a governed procedure is flagged | Pairings are invented for the demo, not clinical policy |
| `flag_outside_coverage` | OUTSIDE_COVERAGE | Service date not inside any eligibility span (null end = open); members with no eligibility are flagged | One span per member; no gaps/COB |
| `flag_invalid_amount` | INVALID_AMOUNT | units <= 0, billed <= 0, paid < 0, or paid > billed (nulls are not flagged here; silver expectations handle nulls) | |

## Silver expectations (structural, drop to quarantine)

claim_id, line_id, member_id, service_date and billed_amount must be present. Logged-only checks: units > 0, paid_amount >= 0.

## How to extend (good portfolio additions)

- Unbundling: procedure pairs that should be billed together.
- Provider outlier detection: z-score of billed per procedure by specialty (window functions).
- Pre-pay vs post-pay split: apply rules to `claim_status = 'PENDING'` vs `'PAID'`.
