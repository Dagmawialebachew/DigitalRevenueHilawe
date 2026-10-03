-- Migration 0007: Add Tsige Tsom (ጾመ ጽጌ) to verified Ethiopian Orthodox fasting calendar
-- Meskerem 26 to Hidar 5 (October 6 to November 14).
-- Essential for clients ordering meal plans in October/November.

INSERT INTO nutrition_fasting_calendar(
    rule_id, fast_name, rule_type, start_date, end_date, fish_default,
    client_override_allowed, verified_for_year, verification_status, notes,
    dataset_version, source_payload, updated_at
)
SELECT
    v.rule_id, v.fast_name, 'Annual occurrence', v.start_date, v.end_date, FALSE,
    TRUE, v.calendar_year::TEXT, 'VERIFIED_RULESET', v.notes,
    'HILAWE_MEAL_OS_V1.3_2026-08-17',
    jsonb_build_object(
        'Rule ID', v.rule_id,
        'Fast Name', v.fast_name,
        'Rule Type', 'Annual occurrence',
        'Weekday', NULL,
        'Start Date', v.start_date::TEXT,
        'End Date', v.end_date::TEXT,
        'Fish Default', 'No',
        'Client Override Allowed', 'Yes',
        'Verified For Year', v.calendar_year::TEXT,
        'Verification Status', 'VERIFIED_RULESET',
        'Notes', v.notes
    ),
    NOW()
FROM (VALUES
    ('FAST-TSIGE-2026', 'Tsige / Flower Fast (ጾመ ጽጌ)', 2026, DATE '2026-10-06', DATE '2026-11-14', 'Annual fast from Meskerem 26 to Hidar 5 (October 6 to November 14).'),
    ('FAST-TSIGE-2027', 'Tsige / Flower Fast (ጾመ ጽጌ)', 2027, DATE '2027-10-06', DATE '2027-11-14', 'Annual fast from Meskerem 26 to Hidar 5 (October 6 to November 14).'),
    ('FAST-TSIGE-2028', 'Tsige / Flower Fast (ጾመ ጽጌ)', 2028, DATE '2028-10-06', DATE '2028-11-14', 'Annual fast from Meskerem 26 to Hidar 5 (October 6 to November 14).'),
    ('FAST-TSIGE-2029', 'Tsige / Flower Fast (ጾመ ጽጌ)', 2029, DATE '2029-10-06', DATE '2029-11-14', 'Annual fast from Meskerem 26 to Hidar 5 (October 6 to November 14).')
) AS v(rule_id, fast_name, calendar_year, start_date, end_date, notes)
ON CONFLICT(rule_id) DO UPDATE SET
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    verification_status = 'VERIFIED_RULESET',
    updated_at = NOW();
