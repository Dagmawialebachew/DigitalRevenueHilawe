-- Rolling, operational Ethiopian Orthodox fasting calendar.
--
-- The source workbook intentionally shipped annual rows without dates.  These
-- occurrence rows are immutable, year-specific facts used by checkout and the
-- generation engine.  Coverage is tracked separately so "no overlap" can be
-- distinguished from "calendar data is missing".

CREATE TABLE IF NOT EXISTS nutrition_fasting_calendar_coverage (
    calendar_year INTEGER PRIMARY KEY CHECK (calendar_year BETWEEN 2000 AND 2200),
    status TEXT NOT NULL CHECK (status IN ('VERIFIED_COMPLETE','PENDING_REVIEW')),
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    verified_at TIMESTAMPTZ,
    notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'VERIFIED_COMPLETE' OR verified_at IS NOT NULL)
);

INSERT INTO nutrition_fasting_calendar_coverage(
    calendar_year,status,source_name,source_url,verified_at,notes
) VALUES
    (2026,'VERIFIED_COMPLETE','Bahire Hasab + 2026 EOTC monastery calendar',
     'https://www.debreenqueotc.org/church-calendar',NOW(),
     'Movable dates cross-checked against the published 2026 church calendar.'),
    (2027,'VERIFIED_COMPLETE','Bahire Hasab rolling calendar',
     'https://senbete.com/when-is-fasika-ethiopian-easter.html',NOW(),
     'Movable dates derived from the published Fasika/Lent/Nineveh table; fixed seasons use EOTC rules.'),
    (2028,'VERIFIED_COMPLETE','Bahire Hasab rolling calendar',
     'https://senbete.com/when-is-fasika-ethiopian-easter.html',NOW(),
     'Movable dates derived from the published Fasika/Lent/Nineveh table; fixed seasons use EOTC rules.'),
    (2029,'VERIFIED_COMPLETE','Bahire Hasab rolling calendar',
     'https://senbete.com/when-is-fasika-ethiopian-easter.html',NOW(),
     'Movable dates derived from the published Fasika/Lent/Nineveh table; fixed seasons use EOTC rules.')
ON CONFLICT(calendar_year) DO NOTHING;

-- Each occurrence carries the original field names in source_payload because
-- the audited generation loader reconstructs its in-memory dataset from that
-- JSON document.  The normalized columns remain authoritative for overlap SQL.
INSERT INTO nutrition_fasting_calendar(
    rule_id,fast_name,rule_type,start_date,end_date,fish_default,
    client_override_allowed,verified_for_year,verification_status,notes,
    dataset_version,source_payload,updated_at
)
SELECT
    v.rule_id,v.fast_name,'Annual occurrence',v.start_date,v.end_date,FALSE,
    TRUE,v.calendar_year::TEXT,'VERIFIED_RULESET',v.notes,
    'HILAWE_MEAL_OS_V1.3_2026-08-17',
    jsonb_build_object(
        'Rule ID',v.rule_id,
        'Fast Name',v.fast_name,
        'Rule Type','Annual occurrence',
        'Weekday',NULL,
        'Start Date',v.start_date::TEXT,
        'End Date',v.end_date::TEXT,
        'Fish Default','No',
        'Client Override Allowed','Yes',
        'Verified For Year',v.calendar_year::TEXT,
        'Verification Status','VERIFIED_RULESET',
        'Notes',v.notes
    ),
    NOW()
FROM (VALUES
    ('FAST-NINEVEH-2026','Fast of Nineveh',2026,DATE '2026-02-02',DATE '2026-02-04','Three-day movable fast.'),
    ('FAST-LENT-2026','Great Lent',2026,DATE '2026-02-16',DATE '2026-04-11','55 days through the day before Fasika; includes Holy Week.'),
    ('FAST-APOSTLES-2026','Apostles'' Fast',2026,DATE '2026-06-01',DATE '2026-07-11','Begins the Monday after Pentecost and ends before the Apostles feast.'),
    ('FAST-FILSETA-2026','Filseta / Assumption Fast',2026,DATE '2026-08-07',DATE '2026-08-21','Fixed annual fast.'),
    ('FAST-NATIVITY-2026-2027','Nativity / Prophets Fast',2026,DATE '2026-11-24',DATE '2027-01-06','Cross-year fast ending before Genna.'),

    ('FAST-NINEVEH-2027','Fast of Nineveh',2027,DATE '2027-02-22',DATE '2027-02-24','Three-day movable fast.'),
    ('FAST-LENT-2027','Great Lent',2027,DATE '2027-03-08',DATE '2027-05-01','55 days through the day before Fasika; includes Holy Week.'),
    ('FAST-APOSTLES-2027','Apostles'' Fast',2027,DATE '2027-06-21',DATE '2027-07-11','Begins the Monday after Pentecost and ends before the Apostles feast.'),
    ('FAST-FILSETA-2027','Filseta / Assumption Fast',2027,DATE '2027-08-07',DATE '2027-08-21','Fixed annual fast.'),
    ('FAST-NATIVITY-2027-2028','Nativity / Prophets Fast',2027,DATE '2027-11-25',DATE '2028-01-07','Cross-year fast ending before Genna in the Ethiopian leap-year cycle.'),

    ('FAST-NINEVEH-2028','Fast of Nineveh',2028,DATE '2028-02-07',DATE '2028-02-09','Three-day movable fast.'),
    ('FAST-LENT-2028','Great Lent',2028,DATE '2028-02-21',DATE '2028-04-15','55 days through the day before Fasika; includes Holy Week.'),
    ('FAST-APOSTLES-2028','Apostles'' Fast',2028,DATE '2028-06-05',DATE '2028-07-11','Begins the Monday after Pentecost and ends before the Apostles feast.'),
    ('FAST-FILSETA-2028','Filseta / Assumption Fast',2028,DATE '2028-08-07',DATE '2028-08-21','Fixed annual fast.'),
    ('FAST-NATIVITY-2028-2029','Nativity / Prophets Fast',2028,DATE '2028-11-24',DATE '2029-01-06','Cross-year fast ending before Genna.'),

    ('FAST-NINEVEH-2029','Fast of Nineveh',2029,DATE '2029-01-29',DATE '2029-01-31','Three-day movable fast.'),
    ('FAST-LENT-2029','Great Lent',2029,DATE '2029-02-12',DATE '2029-04-07','55 days through the day before Fasika; includes Holy Week.'),
    ('FAST-APOSTLES-2029','Apostles'' Fast',2029,DATE '2029-05-28',DATE '2029-07-11','Begins the Monday after Pentecost and ends before the Apostles feast.'),
    ('FAST-FILSETA-2029','Filseta / Assumption Fast',2029,DATE '2029-08-07',DATE '2029-08-21','Fixed annual fast.'),
    ('FAST-NATIVITY-2029-2030','Nativity / Prophets Fast',2029,DATE '2029-11-24',DATE '2030-01-06','Cross-year fast ending before Genna.')
) AS v(rule_id,fast_name,calendar_year,start_date,end_date,notes)
ON CONFLICT(rule_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS ix_nutrition_fasting_occurrence_dates
    ON nutrition_fasting_calendar(start_date,end_date)
    WHERE verification_status='VERIFIED_RULESET';
