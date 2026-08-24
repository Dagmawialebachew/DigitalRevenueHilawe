-- Phase 1: additive-only storage for the Coach Hilawe personalized meal-plan domain.
-- This migration intentionally does not alter legacy workout/payment/product tables.

CREATE TABLE IF NOT EXISTS meal_intakes (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    language VARCHAR(2) NOT NULL DEFAULT 'AM' CHECK (language IN ('AM','EN')),
    country_region VARCHAR(32) CHECK (country_region IS NULL OR country_region IN ('ETHIOPIA','UNITED_STATES','EUROPE','UAE','OTHER')),
    country_name TEXT,
    state VARCHAR(40) NOT NULL DEFAULT 'COUNTRY_REQUIRED' CHECK (state IN (
        'COUNTRY_REQUIRED','INTAKE_IN_PROGRESS','HEALTH_REVIEW_REQUIRED','HEALTH_APPROVED',
        'HEALTH_DECLINED','PROFILE_READY','CHECKOUT_READY','CLOSED','CANCELLED'
    )),
    source VARCHAR(40) NOT NULL DEFAULT 'BOT_MENU',
    answers JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(answers) = 'object'),
    nutrition_profile JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(nutrition_profile) = 'object'),
    current_step TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    last_saved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_meal_intakes_one_open_per_user
    ON meal_intakes(user_id) WHERE closed_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_meal_intakes_state ON meal_intakes(state, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_meal_intakes_user ON meal_intakes(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS meal_health_reviews (
    id BIGSERIAL PRIMARY KEY,
    intake_id BIGINT NOT NULL UNIQUE REFERENCES meal_intakes(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','DECLINED')),
    flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT,
    reviewer_telegram_id BIGINT,
    decision_notes TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_health_reviews_pending
    ON meal_health_reviews(requested_at) WHERE status='PENDING';

CREATE TABLE IF NOT EXISTS meal_pricing (
    id BIGSERIAL PRIMARY KEY,
    region VARCHAR(32) NOT NULL CHECK (region IN ('ETHIOPIA','UNITED_STATES','EUROPE','UAE','OTHER')),
    duration_days INTEGER NOT NULL CHECK (duration_days IN (7,14,30)),
    service_type VARCHAR(20) NOT NULL CHECK (service_type IN ('PLAN','FOLLOW_UP')),
    currency VARCHAR(3) NOT NULL CHECK (currency IN ('ETB','USD')),
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ,
    label TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (service_type <> 'FOLLOW_UP' OR duration_days = 30),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_meal_pricing_effective_key
    ON meal_pricing(region, duration_days, service_type, effective_from);
CREATE INDEX IF NOT EXISTS ix_meal_pricing_lookup
    ON meal_pricing(region, duration_days, service_type, is_active);

CREATE TABLE IF NOT EXISTS meal_quotes (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    intake_id BIGINT NOT NULL REFERENCES meal_intakes(id) ON DELETE CASCADE,
    region VARCHAR(32) NOT NULL DEFAULT 'OTHER' CHECK (region IN ('ETHIOPIA','UNITED_STATES','EUROPE','UAE','OTHER')),
    country_name TEXT NOT NULL,
    duration_days INTEGER NOT NULL CHECK (duration_days IN (7,14,30)),
    service_type VARCHAR(20) NOT NULL CHECK (service_type IN ('PLAN','FOLLOW_UP')),
    currency VARCHAR(3) CHECK (currency IS NULL OR currency IN ('ETB','USD')),
    amount NUMERIC(12,2) CHECK (amount IS NULL OR amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','CONFIRMED','EXPIRED','CANCELLED')),
    set_by BIGINT,
    confirmed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (service_type <> 'FOLLOW_UP' OR duration_days = 30),
    CHECK (status <> 'CONFIRMED' OR (currency IS NOT NULL AND amount IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_meal_quotes_pending ON meal_quotes(created_at) WHERE status='PENDING';
CREATE INDEX IF NOT EXISTS ix_meal_quotes_intake ON meal_quotes(intake_id, created_at DESC);

CREATE TABLE IF NOT EXISTS meal_orders (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    intake_id BIGINT NOT NULL UNIQUE REFERENCES meal_intakes(id) ON DELETE CASCADE,
    state VARCHAR(40) NOT NULL DEFAULT 'CHECKOUT_READY' CHECK (state IN (
        'CHECKOUT_READY','AWAITING_PAYMENT','PAYMENT_REVIEW','PAYMENT_APPROVED','GENERATION_QUEUED',
        'GENERATING','GENERATION_FAILED','REVIEW_PENDING','CHANGES_REQUESTED','APPROVED',
        'DELIVERY_PENDING','ACTIVE','RENEWAL_DUE','EXPIRED','CANCELLED'
    )),
    duration_days INTEGER NOT NULL CHECK (duration_days IN (7,14,30)),
    service_type VARCHAR(20) NOT NULL CHECK (service_type IN ('PLAN','FOLLOW_UP')),
    meals_per_day INTEGER NOT NULL CHECK (meals_per_day IN (3,4,5)),
    start_date DATE NOT NULL,
    ends_on DATE NOT NULL,
    region VARCHAR(32) NOT NULL CHECK (region IN ('ETHIOPIA','UNITED_STATES','EUROPE','UAE','OTHER')),
    country_name TEXT,
    currency VARCHAR(3) NOT NULL CHECK (currency IN ('ETB','USD')),
    amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    pricing_id BIGINT REFERENCES meal_pricing(id) ON DELETE SET NULL,
    quote_id BIGINT REFERENCES meal_quotes(id) ON DELETE SET NULL,
    current_plan_version_id BIGINT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    paid_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (service_type <> 'FOLLOW_UP' OR duration_days = 30),
    CHECK (ends_on >= start_date)
);
CREATE INDEX IF NOT EXISTS ix_meal_orders_user ON meal_orders(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_meal_orders_state ON meal_orders(state, updated_at DESC);
CREATE INDEX IF NOT EXISTS ix_meal_orders_expiry ON meal_orders(ends_on) WHERE state IN ('ACTIVE','RENEWAL_DUE');

CREATE TABLE IF NOT EXISTS meal_payments (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    expected_amount NUMERIC(12,2) NOT NULL CHECK (expected_amount >= 0),
    expected_currency VARCHAR(3) NOT NULL CHECK (expected_currency IN ('ETB','USD')),
    settlement_amount NUMERIC(12,2) CHECK (settlement_amount IS NULL OR settlement_amount >= 0),
    settlement_currency VARCHAR(3) CHECK (settlement_currency IS NULL OR settlement_currency IN ('ETB','USD')),
    exchange_rate NUMERIC(18,6) CHECK (exchange_rate IS NULL OR exchange_rate > 0),
    bank_code VARCHAR(30),
    proof_file_id TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','VERIFYING','APPROVED','REJECTED')),
    verification_reference TEXT,
    verification_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT UNIQUE,
    processed_by BIGINT,
    approved_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_payments_order ON meal_payments(order_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_meal_payments_status ON meal_payments(status, created_at);

CREATE TABLE IF NOT EXISTS meal_plan_versions (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN (
        'DRAFT','REVIEW_PENDING','CHANGES_REQUESTED','APPROVED','DELIVERED','SUPERSEDED','FAILED'
    )),
    source VARCHAR(30) NOT NULL DEFAULT 'GENERATED' CHECK (source IN ('GENERATED','MANUAL_REPLACEMENT','REVISION')),
    plan_json JSONB,
    detail_source VARCHAR(30) NOT NULL DEFAULT 'STRUCTURED' CHECK (detail_source IN ('STRUCTURED','DOCUMENT_OVERRIDE')),
    engine_version TEXT,
    dataset_version TEXT,
    settings_version TEXT,
    generation_seed TEXT,
    review_chat_id BIGINT,
    review_message_id BIGINT,
    approved_by BIGINT,
    approved_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(order_id, version_number)
);
CREATE INDEX IF NOT EXISTS ix_meal_plan_versions_order ON meal_plan_versions(order_id, version_number DESC);
CREATE INDEX IF NOT EXISTS ix_meal_plan_versions_review ON meal_plan_versions(status, created_at) WHERE status IN ('REVIEW_PENDING','CHANGES_REQUESTED');

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_meal_orders_current_plan_version'
    ) THEN
        ALTER TABLE meal_orders
            ADD CONSTRAINT fk_meal_orders_current_plan_version
            FOREIGN KEY (current_plan_version_id) REFERENCES meal_plan_versions(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS meal_generation_jobs (
    id BIGSERIAL PRIMARY KEY,
    public_id UUID NOT NULL UNIQUE,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    plan_version_id BIGINT REFERENCES meal_plan_versions(id) ON DELETE SET NULL,
    job_type VARCHAR(20) NOT NULL CHECK (job_type IN ('INITIAL','REGENERATE','REVISION')),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    stage VARCHAR(30) NOT NULL DEFAULT 'QUEUED' CHECK (stage IN (
        'QUEUED','TARGETS','FOOD_MATCHING','WEEK_STRUCTURE','PORTION_TUNING','SWAPS','GROCERIES',
        'DOCUMENTS','REVIEW_HANDOFF','COMPLETE'
    )),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT NOT NULL UNIQUE,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_generation_jobs_claim
    ON meal_generation_jobs(status, created_at) WHERE status='PENDING';
CREATE INDEX IF NOT EXISTS ix_meal_generation_jobs_order
    ON meal_generation_jobs(order_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_meal_generation_one_running_per_order
    ON meal_generation_jobs(order_id) WHERE status='RUNNING';

CREATE TABLE IF NOT EXISTS meal_plan_artifacts (
    id BIGSERIAL PRIMARY KEY,
    plan_version_id BIGINT NOT NULL REFERENCES meal_plan_versions(id) ON DELETE CASCADE,
    artifact_type VARCHAR(10) NOT NULL CHECK (artifact_type IN ('DOCX','PDF')),
    storage_backend VARCHAR(30) NOT NULL DEFAULT 'LOCAL',
    storage_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    content_sha256 CHAR(64),
    byte_size BIGINT CHECK (byte_size IS NULL OR byte_size >= 0),
    telegram_file_id TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(plan_version_id, artifact_type)
);
CREATE INDEX IF NOT EXISTS ix_meal_artifacts_version ON meal_plan_artifacts(plan_version_id);

CREATE TABLE IF NOT EXISTS meal_plan_reviews (
    id BIGSERIAL PRIMARY KEY,
    plan_version_id BIGINT NOT NULL REFERENCES meal_plan_versions(id) ON DELETE CASCADE,
    reviewer_telegram_id BIGINT NOT NULL,
    action VARCHAR(30) NOT NULL CHECK (action IN ('APPROVE','REQUEST_CHANGES','REGENERATE','REPLACE_FILES','COMMENT')),
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_plan_reviews_version ON meal_plan_reviews(plan_version_id, created_at DESC);

CREATE TABLE IF NOT EXISTS meal_deliveries (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    plan_version_id BIGINT NOT NULL REFERENCES meal_plan_versions(id) ON DELETE CASCADE,
    channel VARCHAR(30) NOT NULL CHECK (channel IN ('TELEGRAM_DOCUMENT','MINI_APP')),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','SENT','FAILED')),
    idempotency_key TEXT NOT NULL UNIQUE,
    telegram_message_id BIGINT,
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_deliveries_pending ON meal_deliveries(created_at) WHERE status='PENDING';

CREATE TABLE IF NOT EXISTS meal_checkins (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    week_number INTEGER NOT NULL CHECK (week_number BETWEEN 1 AND 5),
    status VARCHAR(30) NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED','DUE','SUBMITTED','REVIEW_REQUIRED','CLOSED','MISSED')),
    due_at TIMESTAMPTZ NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    health_change BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    reviewed_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(order_id, week_number)
);
CREATE INDEX IF NOT EXISTS ix_meal_checkins_due ON meal_checkins(due_at) WHERE status IN ('SCHEDULED','DUE');

CREATE TABLE IF NOT EXISTS meal_revision_requests (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES meal_orders(id) ON DELETE CASCADE,
    checkin_id BIGINT REFERENCES meal_checkins(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','IN_REVIEW','GENERATION_QUEUED','COMPLETED','CANCELLED')),
    reason TEXT,
    requested_by BIGINT,
    resulting_plan_version_id BIGINT REFERENCES meal_plan_versions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_revisions_pending ON meal_revision_requests(created_at) WHERE status IN ('PENDING','IN_REVIEW','GENERATION_QUEUED');

CREATE TABLE IF NOT EXISTS meal_audit_events (
    id BIGSERIAL PRIMARY KEY,
    entity_type VARCHAR(40) NOT NULL,
    entity_id TEXT NOT NULL,
    event_type VARCHAR(80) NOT NULL,
    actor_type VARCHAR(30) NOT NULL,
    actor_telegram_id BIGINT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_meal_audit_entity ON meal_audit_events(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_meal_audit_created ON meal_audit_events(created_at DESC);
