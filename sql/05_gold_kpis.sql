-- Gold KPI queries: CTEs + window functions. Tables come from notebooks 03 and 04.
-- Catalog assumed to be `workspace`.

-- 1) Monthly flagged paid amount with running total and month-over-month change
WITH monthly AS (
    SELECT date_trunc('month', service_date) AS month,
           SUM(CASE WHEN is_flagged THEN paid_amount ELSE 0 END) AS flagged_paid,
           SUM(paid_amount)                                      AS total_paid
    FROM workspace.gold.fact_claim_line
    GROUP BY 1
)
SELECT month,
       flagged_paid,
       ROUND(100 * flagged_paid / NULLIF(total_paid, 0), 2)                    AS flagged_pct_of_paid,
       SUM(flagged_paid) OVER (ORDER BY month)                                 AS running_flagged_paid,
       flagged_paid - LAG(flagged_paid) OVER (ORDER BY month)                  AS mom_change
FROM monthly
ORDER BY month;

-- 2) Providers ranked by flagged paid amount within specialty (current provider version)
WITH provider_flags AS (
    SELECT f.provider_id,
           COUNT(*)                                              AS lines,
           SUM(CASE WHEN f.is_flagged THEN 1 ELSE 0 END)         AS flagged_lines,
           SUM(CASE WHEN f.is_flagged THEN f.paid_amount ELSE 0 END) AS flagged_paid
    FROM workspace.gold.fact_claim_line f
    GROUP BY f.provider_id
),
ranked AS (
    SELECT p.specialty, pf.provider_id, pf.lines, pf.flagged_lines, pf.flagged_paid,
           ROUND(100 * pf.flagged_lines / pf.lines, 2) AS flagged_rate_pct,
           RANK() OVER (PARTITION BY p.specialty ORDER BY pf.flagged_paid DESC) AS rank_in_specialty
    FROM provider_flags pf
    JOIN workspace.gold.dim_provider p
      ON p.provider_id = pf.provider_id AND p.is_current
)
SELECT * FROM ranked WHERE rank_in_specialty <= 5 ORDER BY specialty, rank_in_specialty;

-- 3) Duplicate claim pairs: each flagged copy next to the line it repeats
WITH keyed AS (
    SELECT *, ROW_NUMBER() OVER (
                 PARTITION BY member_id, provider_id, service_date, procedure_code, billed_amount
                 ORDER BY claim_id, line_id) AS occurrence
    FROM workspace.gold.fact_claim_line
)
SELECT c.member_id, c.provider_id, c.service_date, c.procedure_code, c.billed_amount,
       o.claim_id AS original_claim, c.claim_id AS duplicate_claim, c.paid_amount AS duplicate_paid
FROM keyed c
JOIN keyed o
  ON  o.member_id = c.member_id AND o.provider_id = c.provider_id
  AND o.service_date = c.service_date AND o.procedure_code = c.procedure_code
  AND o.billed_amount = c.billed_amount AND o.occurrence = 1
WHERE c.occurrence > 1
ORDER BY c.service_date;

-- 4) Rule hit overview
SELECT * FROM workspace.gold.rule_summary ORDER BY flagged_paid_amount DESC;

-- 5) SCD2 history check: members who changed state
SELECT member_id, state, effective_start, effective_end, is_current
FROM workspace.gold.dim_member
WHERE member_id IN (SELECT member_id FROM workspace.gold.dim_member GROUP BY member_id HAVING COUNT(*) > 1)
ORDER BY member_id, effective_start
LIMIT 50;
