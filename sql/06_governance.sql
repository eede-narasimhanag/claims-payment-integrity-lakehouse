-- Unity Catalog governance examples. Not run against a live workspace by the scaffold author.
-- Free Edition has one user and no account groups, so masking/grants are shown for the
-- pattern; screenshot whatever your workspace allows. Replace group names with real ones.

-- Documentation and tags (discoverability + lineage context)
COMMENT ON TABLE workspace.gold.fact_claim_line IS
  'Claim lines with payment-integrity flags. Synthetic data only.';
ALTER TABLE workspace.gold.fact_claim_line SET TAGS ('domain' = 'claims', 'data_classification' = 'synthetic');
ALTER TABLE workspace.gold.dim_member SET TAGS ('domain' = 'membership', 'contains_identifiers' = 'true');

-- Column mask: only auditors see raw member IDs
CREATE OR REPLACE FUNCTION workspace.gold.mask_member_id(member_id STRING)
RETURN CASE WHEN is_account_group_member('claims_auditors') THEN member_id
            ELSE sha2(member_id, 256) END;

ALTER TABLE workspace.gold.fact_claim_line
  ALTER COLUMN member_id SET MASK workspace.gold.mask_member_id;

-- Row filter: analysts only see paid claims; auditors see everything
CREATE OR REPLACE FUNCTION workspace.gold.claim_status_filter(claim_status STRING)
RETURN is_account_group_member('claims_auditors') OR claim_status = 'PAID';

ALTER TABLE workspace.gold.fact_claim_line
  SET ROW FILTER workspace.gold.claim_status_filter ON (claim_status);

-- Least-privilege grants
GRANT USE CATALOG ON CATALOG workspace TO `claims_analysts`;
GRANT USE SCHEMA, SELECT ON SCHEMA workspace.gold TO `claims_analysts`;
-- Analysts get no access to bronze/silver:
-- (no GRANT on workspace.bronze / workspace.silver)

-- Lineage: open Catalog Explorer > gold.fact_claim_line > Lineage and screenshot it for docs/.
