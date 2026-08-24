const API_BASE = (import.meta.env.VITE_MEAL_API_BASE_URL || '').replace(/\/$/, '')

type ApiErrorBody = {
  error?: { code?: string; message?: string; details?: unknown }
}

export type Language = 'AM' | 'EN'
export type IntakeAnswers = Record<string, unknown>
export type NutritionProfile = {
  bmr_kcal: number
  tdee_kcal: number
  goal_adjustment_fraction: number
  target_kcal: number
  protein_g_per_kg: number
  protein_g: number
  fat_fraction: number
  fat_g: number
  carbs_g: number
  activity_factor: number
  fasting_protein_multiplier: number
  health_gate?: string
  source_version: string
}

export type BootstrapResponse = {
  ok: true
  phase: number
  user: {
    telegram_id: number
    first_name: string
    username: string | null
    language: Language
  }
  intake: {
    public_id: string
    state: string
    current_step: string | null
    version: number
    answers: IntakeAnswers
    nutrition_profile: Partial<NutritionProfile>
    assessment_complete: boolean
    source?: string
    country_required: boolean
    country: null | {
      region: string
      name: string | null
      label: string
    }
  }
  health_review?: null | {
    status: string
    flags: string[]
    requested_at: string | null
    resolved_at: string | null
  }
  order?: null | {
    id: number
    public_id: string
    state: string
    duration_days: number
    service_type: string
    meals_per_day: number
    start_date: string
    ends_on: string
    currency: 'ETB' | 'USD'
    amount: string
  }
  payment?: null | {
    id: number
    status: string
    expected_amount: string
    expected_currency: 'ETB' | 'USD'
    settlement_amount: string | null
    settlement_currency: 'ETB' | 'USD' | null
    proof_submitted: boolean
    verification: Record<string, unknown>
  }
  plan?: null | {
    version_number: number
    status: string
    detail_source: 'STRUCTURED' | 'DOCUMENT_OVERRIDE' | string
    approved_at: string | null
    delivered_at: string | null
    pdf_available: boolean
    docx_available: boolean
    coach_username: string
  }
  followup?: {
    enabled: boolean
    due_checkin: null | { id: number; week_number: number; status: string; due_at: string; submitted_at: string | null; health_change: boolean }
    history: { week_number: number; status: string; due_at: string; submitted_at: string | null }[]
  }
  renewal?: {
    available: boolean
    fresh_reassessment?: boolean
    days_remaining?: number
    source_order_id?: number | null
  }
  payment_accounts?: PaymentAccount[]
}

export type PaymentAccount = {
  code: 'CBE' | 'BOA' | string
  name: string
  account: string
  holder: string
}

export type CheckoutPrice = {
  id: number | null
  currency: 'ETB' | 'USD' | null
  amount: string | null
  label: string | null
}

export type PriceOption = {
  id: number
  duration_days: 7 | 14 | 30
  service_type: 'PLAN' | 'FOLLOW_UP'
  currency: 'ETB' | 'USD'
  amount: string
  label: string | null
}

export type FastingSeasonOverlap = {
  rule_id: string
  name: string
  start_date: string
  end_date: string
  overlap_start: string
  overlap_end: string
  overlap_days: number
}

export type FastingCalendarContext = {
  pattern: string
  seasonal_selected: boolean
  coverage_years: number[]
  overlaps: FastingSeasonOverlap[]
}

async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    let code = 'REQUEST_FAILED'
    let details: unknown
    try {
      const parsed = (await response.json()) as ApiErrorBody
      message = parsed.error?.message || message
      code = parsed.error?.code || code
      details = parsed.error?.details
    } catch {
      // Preserve generic message if the server returned non-JSON text.
    }
    const error = new Error(message) as Error & { code?: string; details?: unknown }
    error.code = code
    error.details = details
    throw error
  }

  return (await response.json()) as T
}

export function bootstrap(initData: string) {
  return post<BootstrapResponse>('/api/meal/bootstrap', { init_data: initData })
}

export function saveLanguage(initData: string, language: Language) {
  return post<{ ok: true; language: Language }>('/api/meal/language', { init_data: initData, language })
}

export function saveCountry(initData: string, region: string, countryName?: string) {
  return post<{
    ok: true
    country: { region: string; name: string | null; label: string }
    intake_state: string
  }>('/api/meal/country', { init_data: initData, region, country_name: countryName || null })
}

export function saveIntakeAnswers(initData: string, answers: IntakeAnswers, currentStep: string) {
  return post<{ ok: true; current_step: string; version: number; saved: IntakeAnswers }>(
    '/api/meal/intake/answers',
    { init_data: initData, answers, current_step: currentStep },
  )
}

export function completeAssessment(initData: string) {
  return post<{
    ok: true
    state: string
    current_step: string
    version: number
    assessment_complete: true
    outcome: string
    flags?: string[]
    nutrition_profile?: NutritionProfile
  }>('/api/meal/intake/complete', { init_data: initData })
}

export function getCheckoutOptions(initData: string) {
  return post<{
    ok: true
    pricing_mode: 'AUTOMATIC' | 'MANUAL'
    prices: PriceOption[]
    country_name?: string | null
  }>('/api/meal/checkout/options', { init_data: initData })
}

export function previewCheckout(
  initData: string,
  configuration: {
    meals_per_day: 3 | 4 | 5
    start_date: string
    duration_days: 7 | 14 | 30
    service_type: 'PLAN' | 'FOLLOW_UP'
  },
) {
  return post<{
    ok: true
    pricing_status: 'READY' | 'MANUAL_REVIEW_REQUIRED' | 'NOT_CONFIGURED'
    configuration: {
      meals_per_day: number
      start_date: string
      ends_on: string
      duration_days: number
      service_type: string
    }
    price?: CheckoutPrice | null
    pricing_id?: number
    quote_id?: number
    quote_public_id?: string
    state: string
    fasting_calendar: FastingCalendarContext
  }>('/api/meal/checkout/preview', { init_data: initData, ...configuration })
}


export function startPayment(
  initData: string,
  configuration: {
    meals_per_day: 3 | 4 | 5
    start_date: string
    duration_days: 7 | 14 | 30
    service_type: 'PLAN' | 'FOLLOW_UP'
  },
) {
  return post<{
    ok: true
    already_started?: boolean
    order: {
      id: number
      public_id: string
      state: string
      duration_days?: number
      service_type?: string
      meals_per_day?: number
      start_date?: string
      currency?: 'ETB' | 'USD'
      amount?: string
    }
    payment: null | {
      id: number
      status: string
      expected_amount?: string
      expected_currency?: 'ETB' | 'USD'
      settlement_amount?: string
      settlement_currency?: 'ETB' | 'USD'
    }
    payment_accounts: PaymentAccount[]
    telegram_instruction_sent?: boolean
  }>('/api/meal/payment/start', { init_data: initData, ...configuration })
}


export async function downloadApprovedPlan(initData: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}/api/meal/plan/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ init_data: initData }),
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const parsed = (await response.json()) as ApiErrorBody
      message = parsed.error?.message || message
    } catch {
      // Keep generic message.
    }
    throw new Error(message)
  }
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^";]+)"?/i)
  return { blob: await response.blob(), filename: match?.[1] || 'Hilawe-Meal-Plan.pdf' }
}
export type FollowUpAnswers = {
  current_weight_kg: number
  adherence_percent: number
  hunger_rating: number
  energy_rating: number
  digestion_rating: number
  training_rating: number
  health_change: boolean
  health_change_notes?: string
  foods_to_avoid?: string
  foods_to_prioritize?: string
  notes?: string
}

export function submitFollowUpCheckin(initData: string, answers: FollowUpAnswers) {
  return post<{
    ok: true
    already_submitted?: boolean
    status: string
    outcome?: string
    kcal_delta?: number
    reasons?: string[]
    revision_request_id?: number | null
  }>('/api/meal/followup/checkin', { init_data: initData, answers })
}

export function startRenewal(initData: string) {
  return post<{ ok: true; fresh_reassessment: true; source_order_id: number; intake: BootstrapResponse['intake'] }>(
    '/api/meal/renewal/start',
    { init_data: initData },
  )
}
