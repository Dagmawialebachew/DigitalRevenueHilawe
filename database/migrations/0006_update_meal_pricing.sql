-- Migration 0006: Update Coach Hilawe Meal Plan Pricing
-- Updates ETB prices for Ethiopia (3,000, 4,000, 6,500, 8,000) and ensures USD prices for US, Europe, and UAE ($19, $29, $49, $79).
-- Existing active prices are deactivated with effective_to=NOW(), and new prices are inserted as active.

UPDATE meal_pricing
SET is_active = FALSE, effective_to = NOW()
WHERE is_active = TRUE;

INSERT INTO meal_pricing (region, duration_days, service_type, currency, amount, label) VALUES
  -- Ethiopia (ETB)
  ('ETHIOPIA', 7, 'PLAN', 'ETB', 3000.00, 'Ethiopia 7-Day Plan'),
  ('ETHIOPIA', 14, 'PLAN', 'ETB', 4000.00, 'Ethiopia 14-Day Plan'),
  ('ETHIOPIA', 30, 'PLAN', 'ETB', 6500.00, 'Ethiopia 30-Day Plan'),
  ('ETHIOPIA', 30, 'FOLLOW_UP', 'ETB', 8000.00, 'Ethiopia 30-Day Follow-Up'),

  -- United States (USD)
  ('UNITED_STATES', 7, 'PLAN', 'USD', 19.00, 'United States 7-Day Plan'),
  ('UNITED_STATES', 14, 'PLAN', 'USD', 29.00, 'United States 14-Day Plan'),
  ('UNITED_STATES', 30, 'PLAN', 'USD', 49.00, 'United States 30-Day Plan'),
  ('UNITED_STATES', 30, 'FOLLOW_UP', 'USD', 79.00, 'United States 30-Day Follow-Up'),

  -- Europe (USD)
  ('EUROPE', 7, 'PLAN', 'USD', 19.00, 'Europe 7-Day Plan'),
  ('EUROPE', 14, 'PLAN', 'USD', 29.00, 'Europe 14-Day Plan'),
  ('EUROPE', 30, 'PLAN', 'USD', 49.00, 'Europe 30-Day Plan'),
  ('EUROPE', 30, 'FOLLOW_UP', 'USD', 79.00, 'Europe 30-Day Follow-Up'),

  -- UAE (USD)
  ('UAE', 7, 'PLAN', 'USD', 19.00, 'UAE 7-Day Plan'),
  ('UAE', 14, 'PLAN', 'USD', 29.00, 'UAE 14-Day Plan'),
  ('UAE', 30, 'PLAN', 'USD', 49.00, 'UAE 30-Day Plan'),
  ('UAE', 30, 'FOLLOW_UP', 'USD', 79.00, 'UAE 30-Day Follow-Up');
