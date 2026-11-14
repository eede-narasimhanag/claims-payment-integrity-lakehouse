# Interview notes: how to talk about this project

Be accurate about what you built: personal project, synthetic data, scaled for a free tier.

## 30-second pitch

"I built a claims payment-integrity lakehouse on Databricks and Azure. Claims, member, provider and eligibility data land in a
medallion architecture; silver enforces structural data quality; gold applies tested rules that flag duplicates, overbilling,
diagnosis/procedure mismatches and billing outside coverage, with SCD2 dimensions and Unity Catalog governance. Rules are a
PySpark package covered by pytest and run in CI."

## Domain vocabulary to be fluent in

- Claim vs claim line; billed / allowed / paid; member, provider (NPI), eligibility, coverage span.
- Adjudication: the process that decides if and how much to pay (eligibility check, edits, pricing).
- Payment integrity: pre-pay (stop before paying) vs post-pay (recover after paying); duplicates, unbundling, upcoding, coordination of benefits.
- Code sets: ICD-10 (diagnoses), CPT/HCPCS (procedures; licensed), NPI (provider IDs); FHIR/HL7 for exchange.
- RCM (revenue cycle management), claims denials, remittance.

## Questions to prepare

1. Why flag instead of drop? (reviewers need the evidence; legitimate repeats exist)
2. How do you make loads idempotent? (Auto Loader checkpoints, upsert by line_id, watermark after success)
3. How does SCD2 work in your MERGE? (double-staged rows: one to close, one to insert)
4. What did you tune and how did you measure it? (only answer with numbers you really measured)
5. Where would this break at 100x scale? (broadcast reference joins, skew on provider, small files, cluster sizing)
6. How would you test a pipeline? (unit tests on pure functions, small fixtures, expectations in prod)
7. What would you change for real PHI? (encryption, private networking, audit logging, BAAs, access reviews; not claimed here)
8. How do Delta features help? (ACID, schema evolution, time travel, OPTIMIZE/clustering)

## Things not to claim

- Production healthcare experience from this project, HIPAA compliance, or real-world rule accuracy.
- Any number you have not measured yourself.
