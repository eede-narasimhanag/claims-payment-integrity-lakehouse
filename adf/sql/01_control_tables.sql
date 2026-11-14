-- Azure SQL Database control plane for the metadata-driven ADF framework (T-SQL).
-- Not executed by the scaffold author: run it in your own Azure SQL DB and fix any errors.

CREATE SCHEMA ctl;
GO

CREATE TABLE ctl.ingestion_config (
    config_id        INT IDENTITY(1,1) PRIMARY KEY,
    source_name      VARCHAR(100)  NOT NULL UNIQUE,   -- e.g. claim_lines
    source_type      VARCHAR(30)   NOT NULL,          -- http | blob | sql
    source_path      VARCHAR(500)  NOT NULL,          -- relative URL / folder / table
    target_folder    VARCHAR(200)  NOT NULL,          -- ADLS path under raw/
    file_format      VARCHAR(20)   NOT NULL DEFAULT 'csv',
    watermark_column VARCHAR(100)  NULL,              -- NULL = full load
    last_watermark   VARCHAR(50)   NULL,
    is_active        BIT           NOT NULL DEFAULT 1
);
GO

CREATE TABLE ctl.pipeline_run_log (
    run_log_id    BIGINT IDENTITY(1,1) PRIMARY KEY,
    pipeline_run_id VARCHAR(100) NOT NULL,
    source_name   VARCHAR(100)  NOT NULL,
    status        VARCHAR(20)   NOT NULL,             -- STARTED | SUCCEEDED | FAILED
    rows_read     BIGINT        NULL,
    rows_written  BIGINT        NULL,
    error_message VARCHAR(4000) NULL,
    logged_at_utc DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE PROCEDURE ctl.usp_log_run
    @pipeline_run_id VARCHAR(100), @source_name VARCHAR(100), @status VARCHAR(20),
    @rows_read BIGINT = NULL, @rows_written BIGINT = NULL, @error_message VARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO ctl.pipeline_run_log (pipeline_run_id, source_name, status, rows_read, rows_written, error_message)
    VALUES (@pipeline_run_id, @source_name, @status, @rows_read, @rows_written, @error_message);
END;
GO

-- Call only after a successful copy so a failed run is retried from the same watermark.
CREATE PROCEDURE ctl.usp_update_watermark @source_name VARCHAR(100), @new_watermark VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    UPDATE ctl.ingestion_config SET last_watermark = @new_watermark WHERE source_name = @source_name;
END;
GO

-- Idempotent upsert from a staging table (reruns never duplicate lines)
CREATE SCHEMA curated;
GO
CREATE TABLE curated.claim_line (
    line_id VARCHAR(60) NOT NULL PRIMARY KEY, claim_id VARCHAR(40) NOT NULL, member_id VARCHAR(60) NOT NULL,
    provider_id VARCHAR(60) NULL, service_date DATE NOT NULL, procedure_code VARCHAR(20) NULL,
    diagnosis_code VARCHAR(20) NULL, units INT NULL, billed_amount DECIMAL(12,2) NULL,
    allowed_amount DECIMAL(12,2) NULL, paid_amount DECIMAL(12,2) NULL, load_date DATE NULL
);
GO
-- curated.claim_line_stg is created by the ADF Copy activity (sink option: auto-create table)
-- with the CSV columns as text. SQL Server resolves table names inside a procedure when it
-- first runs, so this procedure can be created before the staging table exists.
CREATE PROCEDURE curated.usp_upsert_claim_line
AS
BEGIN
    SET NOCOUNT ON;
    MERGE curated.claim_line AS t
    USING curated.claim_line_stg AS s ON t.line_id = s.line_id
    WHEN MATCHED THEN UPDATE SET
        t.claim_id = s.claim_id, t.member_id = s.member_id, t.provider_id = s.provider_id,
        t.service_date = TRY_CONVERT(DATE, s.service_date), t.procedure_code = s.procedure_code,
        t.diagnosis_code = s.diagnosis_code, t.units = TRY_CONVERT(INT, s.units),
        t.billed_amount = TRY_CONVERT(DECIMAL(12,2), s.billed_amount),
        t.allowed_amount = TRY_CONVERT(DECIMAL(12,2), s.allowed_amount),
        t.paid_amount = TRY_CONVERT(DECIMAL(12,2), s.paid_amount), t.load_date = TRY_CONVERT(DATE, s.load_date)
    WHEN NOT MATCHED BY TARGET THEN INSERT
        (line_id, claim_id, member_id, provider_id, service_date, procedure_code, diagnosis_code,
         units, billed_amount, allowed_amount, paid_amount, load_date)
    VALUES (s.line_id, s.claim_id, s.member_id, s.provider_id, TRY_CONVERT(DATE, s.service_date),
            s.procedure_code, s.diagnosis_code, TRY_CONVERT(INT, s.units),
            TRY_CONVERT(DECIMAL(12,2), s.billed_amount), TRY_CONVERT(DECIMAL(12,2), s.allowed_amount),
            TRY_CONVERT(DECIMAL(12,2), s.paid_amount), TRY_CONVERT(DATE, s.load_date));
END;
GO
