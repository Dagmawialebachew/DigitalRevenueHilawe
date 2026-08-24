import { useEffect, useMemo, useState } from 'react'
import { DayPicker as GregorianDayPicker } from 'react-day-picker'
import { DayPicker as EthiopicDayPicker } from 'react-day-picker/ethiopic'
import {
  FastingCalendarContext,
  getCheckoutOptions,
  IntakeAnswers,
  Language,
  NutritionProfile,
  previewCheckout,
  PriceOption,
  startPayment,
} from './api'
import { hapticSelect } from './telegram'

type Props = {
  initData: string
  language: Language
  firstName: string
  answers: IntakeAnswers
  profile: Partial<NutritionProfile>
  intakeState: string
}

type Step = 'PROFILE' | 'MEALS' | 'START' | 'DURATION' | 'SERVICE' | 'SUMMARY'

type Config = {
  meals_per_day: 3 | 4 | 5
  start_date: string
  duration_days: 7 | 14 | 30
  service_type: 'PLAN' | 'FOLLOW_UP'
}

const text = {
  AM: {
    profileEyebrow: 'የእርስዎ የአመጋገብ መገለጫ',
    profileTitle: (name: string) => `${name}፣ የNutrition Profileዎ ዝግጁ ነው`,
    profileBody: 'እነዚህ ቁጥሮች በዕድሜዎ፣ ቁመትዎ፣ ክብደትዎ፣ የቀን እንቅስቃሴዎ እና በመረጡት ግብ መሠረት ተሰልተዋል። ይህ የምግብ ፕላንዎን ለመገንባት የምንጠቀምበት መነሻ ነው።',
    kcalExplain: 'kcal በቀን ሰውነትዎ ለግብዎ የሚፈልገውን የምግብ ኃይል ይወክላል። ቁጥሩ የመጨረሻ የህክምና ውጤት ሳይሆን ለፕላን የሚያገለግል የተዋቀረ መነሻ ነው።',
    continue: 'ቀጥል',
    mealsTitle: 'በቀን ስንት ጊዜ መመገብ ለእርስዎ ይመቻል?',
    mealsBody: 'የምግብ ብዛቱ የቀኑን ካሎሪ እና ፕሮቲን በምግቦቹ መካከል እንዴት እንደምንከፋፍል ይቀይራል። በተግባር ሊከተሉት የሚችሉትን ይምረጡ።',
    startTitle: 'ፕላንዎን መቼ መጀመር ይፈልጋሉ?',
    startBody: 'እያንዳንዱ ፕላን ከመላኩ በፊት ይገመገማል። ስለዚህ የመጀመሪያው ቀን ከነገ ጀምሮ ሊሆን ይችላል።',
    tomorrow: 'ነገ', nextMonday: 'ቀጣይ ሰኞ', chooseDate: 'ሌላ ቀን ይምረጡ',
    durationTitle: 'ፕላኑን ለስንት ቀን ይፈልጋሉ?',
    durationBody: 'ሁሉም አማራጮች በእርስዎ መረጃ ላይ የተመሰረቱ ናቸው። 14 እና 30 ቀን እቅዶች የ7 ቀን ዋና መዋቅሩን ከተዘጋጁ የምግብ ለውጦች (swaps) ጋር ይዞራሉ።',
    d7: '7 ቀን', d14: '14 ቀን', d30: '30 ቀን',
    serviceTitle: 'የ30 ቀን ፕላንዎን እንዴት ይፈልጋሉ?',
    serviceBody: 'መደበኛው ፕላን አንድ የተገመገመ የ30 ቀን ስርዓት ይሰጣል። Follow-Up ደግሞ በየሳምንቱ አጭር check-in እና አስፈላጊ ሲሆን ማስተካከያ ያካትታል።',
    planOnly: 'Meal Plan', followUp: 'Meal Plan + Follow-Up',
    summaryTitle: 'የፕላንዎ ማጠቃለያ',
    summaryBody: 'ክፍያ ከመጀመሩ በፊት የመረጡትን ነገር አንድ ጊዜ ያረጋግጡ።',
    prepareCheckout: 'ወደ ክፍያ ዝግጅት ቀጥል',
    pricingMissing: 'የዚህ አማራጭ ዋጋ በdemo database ውስጥ ገና አልተዘጋጀም። ይህ የpricing configuration ችግኝ ነው፤ የእርስዎ መረጃ አልጠፋም።',
    manualPricing: 'አገርዎ “Other” ስለሆነ ዋጋው በእጅ ይረጋገጣል። ምንም ክፍያ አሁን አይወሰድም።',
    checkoutReady: 'የክፍያ ዝግጅት ደረጃ ዝግጁ ነው',
    checkoutDemo: 'Phase 4 እዚህ ይቆማል። Phase 5 የCBE / Abyssinia የክፍያ እና verification flowን ያገናኛል።',
    loadingPrice: 'የዋጋ ማስተካከያን በመፈተሽ ላይ…',
    back: 'ተመለስ',
  },
  EN: {
    profileEyebrow: 'YOUR NUTRITION PROFILE',
    profileTitle: (name: string) => `${name}, your nutrition profile is ready`,
    profileBody: 'These targets were calculated from your age, height, weight, activity and selected goal. They are the structured starting point used to build your personalized meal plan.',
    kcalExplain: 'Daily kcal represents the food energy target used to structure your plan. It is a planning estimate, not a medical diagnosis or guarantee.',
    continue: 'Continue',
    mealsTitle: 'How many meals fit your day?',
    mealsBody: 'Meal frequency changes how your daily energy and protein are distributed. Choose the structure you can realistically follow.',
    startTitle: 'When would you like to start?',
    startBody: 'Every plan is reviewed before release, so the earliest selectable start is tomorrow.',
    tomorrow: 'Tomorrow', nextMonday: 'Next Monday', chooseDate: 'Choose another date',
    durationTitle: 'How long should we prepare your plan for?',
    durationBody: 'Every option is personalized. The 14- and 30-day products rotate the core 7-day structure with planned swaps rather than pretending every day must be completely unrelated.',
    d7: '7 days', d14: '14 days', d30: '30 days',
    serviceTitle: 'How would you like your 30-day plan?',
    serviceBody: 'The standard plan gives you one reviewed 30-day system. Follow-Up adds short weekly check-ins and adjustments when needed.',
    planOnly: 'Meal Plan', followUp: 'Meal Plan + Follow-Up',
    summaryTitle: 'Your plan summary',
    summaryBody: 'Confirm the structure you selected before we prepare checkout.',
    prepareCheckout: 'Prepare checkout',
    pricingMissing: 'Pricing for this option has not been configured in the demo database yet. Your assessment is saved; this is a pricing configuration issue only.',
    manualPricing: 'Because your country is under Other, the price requires manual confirmation. No payment is collected yet.',
    checkoutReady: 'Checkout preparation is ready',
    checkoutDemo: 'Phase 4 stops here. Phase 5 connects the CBE / Abyssinia payment and verification flow.',
    loadingPrice: 'Checking pricing configuration…',
    back: 'Back',
  },
} as const

function tomorrowISO() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return localISO(d)
}

function nextMondayISO() {
  const d = new Date()
  const day = d.getDay()
  let delta = (8 - day) % 7
  if (delta === 0) delta = 7
  d.setDate(d.getDate() + delta)
  if (localISO(d) < tomorrowISO()) d.setDate(d.getDate() + 7)
  return localISO(d)
}

function localISO(d: Date) {
  const y = d.getFullYear()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${day}`
}

function dateFromISO(value: string): Date {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(year, month - 1, day, 12)
}

function formatGregorian(value: string, language: Language): string {
  return new Intl.DateTimeFormat(language === 'AM' ? 'am-ET' : 'en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  }).format(dateFromISO(value))
}

function formatEthiopian(value: string, language: Language): string {
  return new Intl.DateTimeFormat(language === 'AM' ? 'am-ET-u-ca-ethiopic' : 'en-US-u-ca-ethiopic', {
    year: 'numeric', month: 'long', day: 'numeric', calendar: 'ethiopic',
  }).format(dateFromISO(value))
}

function DualDate({ value, language }: { value: string; language: Language }) {
  return <span className="dual-date"><strong>{formatEthiopian(value, language)}</strong><small>{formatGregorian(value, language)}</small></span>
}

function CalendarPicker({ value, min, language, onChange }: { value: string; min: string; language: Language; onChange: (value: string) => void }) {
  const [calendar, setCalendar] = useState<'ETHIOPIAN' | 'GREGORIAN'>(language === 'AM' ? 'ETHIOPIAN' : 'GREGORIAN')
  const selected = dateFromISO(value)
  const minimum = dateFromISO(min)
  const common = {
    mode: 'single' as const,
    selected,
    defaultMonth: selected,
    disabled: { before: minimum },
    onSelect: (date: Date | undefined) => { if (date) onChange(localISO(date)) },
  }
  return <div className="calendar-picker-shell">
    <div className="calendar-toggle" role="group" aria-label="Calendar system">
      <button type="button" className={calendar === 'ETHIOPIAN' ? 'selected' : ''} onClick={() => setCalendar('ETHIOPIAN')}>የኢትዮጵያ</button>
      <button type="button" className={calendar === 'GREGORIAN' ? 'selected' : ''} onClick={() => setCalendar('GREGORIAN')}>Gregorian</button>
    </div>
    {calendar === 'ETHIOPIAN'
      ? <EthiopicDayPicker {...common} numerals={language === 'AM' ? 'geez' : 'latn'} />
      : <GregorianDayPicker {...common} />}
    <div className="calendar-selection"><small>{language === 'AM' ? 'የተመረጠው ቀን' : 'SELECTED DATE'}</small><DualDate value={value} language={language} /></div>
  </div>
}

function FastingCalendarPanel({ context, language }: { context: FastingCalendarContext | undefined; language: Language }) {
  if (!context?.seasonal_selected || context.overlaps.length === 0) return null
  return <div className="fasting-overlap-panel">
    <div className="fasting-overlap-heading"><span>✦</span><div><small>{language === 'AM' ? 'የጾም ቀናት' : 'FASTING CALENDAR'}</small><strong>{language === 'AM' ? 'ከፕላንዎ ጋር የሚገናኝ' : 'Overlapping your plan'}</strong></div></div>
    {context.overlaps.map((season) => <div className="fasting-season-card" key={season.rule_id}>
      <strong>{season.name}</strong>
      <DualDate value={season.overlap_start} language={language} />
      {season.overlap_end !== season.overlap_start && <><span className="date-separator">→</span><DualDate value={season.overlap_end} language={language} /></>}
      <em>{season.overlap_days} {language === 'AM' ? 'የጾም ቀናት በፕላኑ ውስጥ' : `fasting day${season.overlap_days === 1 ? '' : 's'} in this plan`}</em>
    </div>)}
  </div>
}

function formatPrice(price: PriceOption | undefined) {
  if (!price) return '—'
  const amount = Number(price.amount)
  return price.currency === 'ETB' ? `${amount.toLocaleString()} Br` : `$${amount.toLocaleString()}`
}

export default function ProfileCheckoutFlow({ initData, language, firstName, answers, profile, intakeState }: Props) {
  const t = text[language]
  const saved = (answers.plan_configuration || {}) as Partial<Config>
  const [step, setStep] = useState<Step>(intakeState === 'CHECKOUT_READY' && saved.duration_days ? 'SUMMARY' : 'PROFILE')
  const [config, setConfig] = useState<Config>({
    meals_per_day: saved.meals_per_day || 4,
    start_date: saved.start_date || tomorrowISO(),
    duration_days: saved.duration_days || 30,
    service_type: saved.service_type || 'PLAN',
  })
  const [prices, setPrices] = useState<PriceOption[]>([])
  const [pricingMode, setPricingMode] = useState<'AUTOMATIC' | 'MANUAL'>('AUTOMATIC')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Awaited<ReturnType<typeof previewCheckout>> | null>(null)
  const [paymentResult, setPaymentResult] = useState<Awaited<ReturnType<typeof startPayment>> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    void getCheckoutOptions(initData)
      .then((response) => { setPrices(response.prices); setPricingMode(response.pricing_mode) })
      .catch((cause) => setError(cause instanceof Error ? cause.message : 'Unable to load pricing'))
  }, [initData])

  const selectedPrice = useMemo(
    () => prices.find((item) => item.duration_days === config.duration_days && item.service_type === config.service_type),
    [prices, config.duration_days, config.service_type],
  )

  function go(next: Step) { hapticSelect(); setError(''); setStep(next); window.scrollTo({ top: 0, behavior: 'smooth' }) }

  async function submit() {
    setLoading(true); setError(''); hapticSelect()
    try {
      const response = await previewCheckout(initData, config)
      setResult(response)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to prepare checkout')
    } finally { setLoading(false) }
  }

  async function beginPayment() {
    setLoading(true); setError(''); hapticSelect()
    try {
      const response = await startPayment(initData, config)
      setPaymentResult(response)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to start payment')
    } finally { setLoading(false) }
  }

  if (paymentResult) {
    const payment = paymentResult.payment
    const settlement = payment?.settlement_amount && payment?.settlement_currency
      ? (payment.settlement_currency === 'ETB' ? `${Number(payment.settlement_amount).toLocaleString()} Br` : `$${Number(payment.settlement_amount).toLocaleString()}`)
      : '—'
    return <section className="phase5-payment-stage">
      <div className="completion-mark">✓</div>
      <p className="eyebrow">PAYMENT · READY</p>
      <h1>{language === 'AM' ? 'የክፍያ መመሪያዎ ወደ Telegram ተልኳል' : 'Your payment instructions are ready in Telegram'}</h1>
      <p className="lead">{language === 'AM' ? 'ከታች ካሉት CBE ወይም Abyssinia አካውንቶች ወደ አንዱ የተጠቀሰውን መጠን ያስተላልፉ። ከዚያ Telegram ውስጥ “Send receipt” ቁልፍን ተጭነው screenshot ይላኩ።' : 'Transfer the amount below to either CBE or Bank of Abyssinia. Then return to Telegram, tap “Send receipt,” and send a clear screenshot.'}</p>
      <div className="payment-amount-card"><small>{language === 'AM' ? 'የሚልኩት መጠን' : 'AMOUNT TO TRANSFER'}</small><strong>{settlement}</strong></div>
      <div className="bank-stack">{paymentResult.payment_accounts.map((bank) => <div className="bank-card" key={bank.code}><div><small>{bank.code}</small><strong>{bank.name}</strong></div><code>{bank.account}</code><span>{bank.holder}</span></div>)}</div>
      <div className="payment-next-card"><span className="pulse-dot" /><div><small>TELEGRAM</small><strong>{language === 'AM' ? 'ደረሰኙን በBot ይላኩ' : 'Send the receipt in the bot'}</strong></div></div>
      <p className="demo-note">{language === 'AM' ? 'Mini Appን መዝጋት ይችላሉ። ክፍያው ሲረጋገጥ ሁኔታው በራሱ ይቀየራል።' : 'You can close the Mini App. When payment is approved, the order status will update automatically.'}</p>
    </section>
  }

  if (result) {
    return <section className="phase4-stage checkout-result">
      <div className={`completion-mark ${result.pricing_status === 'READY' ? '' : 'soft'}`}>{result.pricing_status === 'READY' ? '✓' : '…'}</div>
      <p className="eyebrow">CHECKOUT · {result.pricing_status.replace(/_/g, ' ')}</p>
      <h1>{result.pricing_status === 'READY' ? t.checkoutReady : result.pricing_status === 'MANUAL_REVIEW_REQUIRED' ? t.manualPricing : t.pricingMissing}</h1>
      {result.price?.amount && <div className="hero-price">{result.price.currency === 'ETB' ? `${Number(result.price.amount).toLocaleString()} Br` : `$${Number(result.price.amount).toLocaleString()}`}</div>}
      <div className="summary-grid compact-summary">
        <Summary label={language === 'AM' ? 'ቀናት' : 'Duration'} value={`${config.duration_days}`} />
        <Summary label={language === 'AM' ? 'ምግብ / ቀን' : 'Meals / day'} value={`${config.meals_per_day}`} />
        <Summary label={language === 'AM' ? 'መጀመሪያ' : 'Starts'} value={`${formatEthiopian(result.configuration.start_date, language)} / ${formatGregorian(result.configuration.start_date, language)}`} />
        <Summary label={language === 'AM' ? 'አገልግሎት' : 'Service'} value={config.service_type === 'FOLLOW_UP' ? 'Follow-Up' : 'Meal Plan'} />
      </div>
      <FastingCalendarPanel context={result.fasting_calendar} language={language} />
      <p className="lead checkout-note">{result.pricing_status === 'READY' ? (language === 'AM' ? 'ዋጋዎ ተረጋግጧል። ቀጥለው የCBE / Abyssinia የክፍያ መመሪያዎን ይክፈቱ።' : 'Your price is confirmed. Continue to open the CBE / Abyssinia payment instructions.') : result.pricing_status === 'MANUAL_REVIEW_REQUIRED' ? t.manualPricing : t.pricingMissing}</p>
      {result.pricing_status === 'READY' && <button className="primary-button tall" disabled={loading} onClick={() => void beginPayment()}>{loading ? '…' : (language === 'AM' ? 'ወደ ክፍያ ቀጥል →' : 'Continue to payment →')}</button>}
      <button className="secondary-button wide" onClick={() => setResult(null)}>← {t.back}</button>
    </section>
  }

  return <section className="phase4-stage">
    <div className="phase4-progress"><span className={step === 'PROFILE' ? 'active' : 'done'}>01</span><i /><span className={['MEALS','START'].includes(step) ? 'active' : ['DURATION','SERVICE','SUMMARY'].includes(step) ? 'done' : ''}>02</span><i /><span className={['DURATION','SERVICE'].includes(step) ? 'active' : step === 'SUMMARY' ? 'done' : ''}>03</span><i /><span className={step === 'SUMMARY' ? 'active' : ''}>04</span></div>

    {step === 'PROFILE' && <>
      <p className="eyebrow">{t.profileEyebrow}</p>
      <h1>{t.profileTitle(firstName)}</h1>
      <p className="lead">{t.profileBody}</p>
      <div className="nutrition-hero"><small>DAILY ENERGY</small><strong>{profile.target_kcal ?? '—'}</strong><span>kcal / day</span></div>
      <div className="macro-grid">
        <Metric label="PROTEIN" value={`${profile.protein_g ?? '—'} g`} />
        <Metric label="CARBS" value={`${profile.carbs_g ?? '—'} g`} />
        <Metric label="FAT" value={`${profile.fat_g ?? '—'} g`} />
      </div>
      <p className="explain-box">{t.kcalExplain}</p>
      <details className="technical-details"><summary>{language === 'AM' ? 'Technical details ይመልከቱ' : 'View technical details'}</summary><div><span>BMR <b>{profile.bmr_kcal ?? '—'} kcal</b></span><span>TDEE <b>{profile.tdee_kcal ?? '—'} kcal</b></span><span>Activity factor <b>{profile.activity_factor ?? '—'}</b></span><span>Source <b>Hilawe Meal OS v1.3</b></span></div></details>
      <button className="primary-button tall" onClick={() => go('MEALS')}>{t.continue} →</button>
    </>}

    {step === 'MEALS' && <>
      <h1>{t.mealsTitle}</h1><p className="lead">{t.mealsBody}</p>
      <div className="meal-count-grid">{([3,4,5] as const).map((count) => <button key={count} className={config.meals_per_day === count ? 'selected' : ''} onClick={() => setConfig({ ...config, meals_per_day: count })}><strong>{count}</strong><span>{language === 'AM' ? 'ምግቦች / ቀን' : 'meals / day'}</span><small>{count === 3 ? (language === 'AM' ? 'ትልቅ ምግብ፣ ጥቂት ጊዜ' : 'Larger meals, fewer eating times') : count === 4 ? (language === 'AM' ? '3 ዋና ምግቦች + 1 snack' : '3 main meals + 1 snack') : (language === 'AM' ? 'ትንሽ ትንሽ በብዙ ጊዜ' : 'Smaller meals spread through the day')}</small></button>)}</div>
      <FlowButtons back={() => go('PROFILE')} next={() => go('START')} backText={t.back} nextText={t.continue} />
    </>}

    {step === 'START' && <>
      <h1>{t.startTitle}</h1><p className="lead">{t.startBody}</p>
      <div className="start-date-grid">
        <button className={config.start_date === tomorrowISO() ? 'selected' : ''} onClick={() => setConfig({ ...config, start_date: tomorrowISO() })}><strong>{t.tomorrow}</strong><DualDate value={tomorrowISO()} language={language} /></button>
        <button className={config.start_date === nextMondayISO() ? 'selected' : ''} onClick={() => setConfig({ ...config, start_date: nextMondayISO() })}><strong>{t.nextMonday}</strong><DualDate value={nextMondayISO()} language={language} /></button>
      </div>
      <p className="calendar-label">{t.chooseDate}</p>
      <CalendarPicker value={config.start_date} min={tomorrowISO()} language={language} onChange={(start_date) => setConfig({ ...config, start_date })} />
      <FlowButtons back={() => go('MEALS')} next={() => go('DURATION')} backText={t.back} nextText={t.continue} />
    </>}

    {step === 'DURATION' && <>
      <h1>{t.durationTitle}</h1><p className="lead">{t.durationBody}</p>
      <div className="duration-grid">{([7,14,30] as const).map((days) => {
        const p = prices.find((item) => item.duration_days === days && item.service_type === 'PLAN')
        return <button key={days} className={config.duration_days === days ? 'selected featured' : ''} onClick={() => setConfig({ ...config, duration_days: days, service_type: 'PLAN' })}>
          <span>{days === 7 ? t.d7 : days === 14 ? t.d14 : t.d30}</span><strong>{pricingMode === 'MANUAL' ? (language === 'AM' ? 'ዋጋ ይረጋገጣል' : 'Manual quote') : formatPrice(p)}</strong><small>{days === 7 ? 'CORE WEEK' : days === 14 ? '2-WEEK ROTATION' : 'FULL MONTH SYSTEM'}</small>
        </button>
      })}</div>
      <FlowButtons back={() => go('START')} next={() => go(config.duration_days === 30 ? 'SERVICE' : 'SUMMARY')} backText={t.back} nextText={t.continue} />
    </>}

    {step === 'SERVICE' && <>
      <h1>{t.serviceTitle}</h1><p className="lead">{t.serviceBody}</p>
      <div className="service-grid">
        <button className={config.service_type === 'PLAN' ? 'selected' : ''} onClick={() => setConfig({ ...config, service_type: 'PLAN' })}><span>01</span><strong>{t.planOnly}</strong><small>{formatPrice(prices.find((item) => item.duration_days === 30 && item.service_type === 'PLAN'))}</small></button>
        <button className={config.service_type === 'FOLLOW_UP' ? 'selected premium' : ''} onClick={() => setConfig({ ...config, service_type: 'FOLLOW_UP' })}><span>+</span><strong>{t.followUp}</strong><small>{pricingMode === 'MANUAL' ? (language === 'AM' ? 'ዋጋ ይረጋገጣል' : 'Manual quote') : formatPrice(prices.find((item) => item.duration_days === 30 && item.service_type === 'FOLLOW_UP'))}</small><em>{language === 'AM' ? 'ሳምንታዊ check-in + አስፈላጊ ማስተካከያ' : 'Weekly check-ins + adjustments when needed'}</em></button>
      </div>
      <FlowButtons back={() => go('DURATION')} next={() => go('SUMMARY')} backText={t.back} nextText={t.continue} />
    </>}

    {step === 'SUMMARY' && <>
      <p className="eyebrow">PLAN CONFIGURATION</p><h1>{t.summaryTitle}</h1><p className="lead">{t.summaryBody}</p>
      <div className="summary-grid">
        <Summary label={language === 'AM' ? 'ቀናት' : 'Duration'} value={`${config.duration_days}`} />
        <Summary label={language === 'AM' ? 'ምግብ / ቀን' : 'Meals / day'} value={`${config.meals_per_day}`} />
        <Summary label={language === 'AM' ? 'መጀመሪያ' : 'Start date'} value={`${formatEthiopian(config.start_date, language)} / ${formatGregorian(config.start_date, language)}`} />
        <Summary label={language === 'AM' ? 'አገልግሎት' : 'Service'} value={config.service_type === 'FOLLOW_UP' ? 'Meal Plan + Follow-Up' : 'Meal Plan'} />
      </div>
      <div className="summary-price"><span>{language === 'AM' ? 'ዋጋ' : 'PRICE'}</span><strong>{pricingMode === 'MANUAL' ? (language === 'AM' ? 'በreview ይረጋገጣል' : 'Manual confirmation') : formatPrice(selectedPrice)}</strong></div>
      {pricingMode === 'AUTOMATIC' && !selectedPrice && <p className="inline-warning">{t.pricingMissing}</p>}
      {pricingMode === 'MANUAL' && <p className="inline-warning">{t.manualPricing}</p>}
      <button className="primary-button tall" disabled={loading} onClick={() => void submit()}>{loading ? t.loadingPrice : `${t.prepareCheckout} →`}</button>
      <button className="back-button centered" onClick={() => go(config.duration_days === 30 ? 'SERVICE' : 'DURATION')}>← {t.back}</button>
    </>}
    {error && <div className="inline-error">{error}</div>}
  </section>
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric-card"><small>{label}</small><strong>{value}</strong></div> }
function Summary({ label, value }: { label: string; value: string }) { return <div><small>{label}</small><strong>{value}</strong></div> }
function FlowButtons({ back, next, backText, nextText }: { back: () => void; next: () => void; backText: string; nextText: string }) { return <div className="flow-buttons"><button className="secondary-button" onClick={back}>← {backText}</button><button className="primary-button" onClick={next}>{nextText} →</button></div> }
