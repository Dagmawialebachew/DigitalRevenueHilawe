import { useEffect, useState } from 'react'
import { bootstrap, BootstrapResponse, downloadApprovedPlan, FollowUpAnswers, Language, saveCountry, saveLanguage, startRenewal, submitFollowUpCheckin } from './api'
import { copy } from './copy'
import IntakeFlow from './IntakeFlow'
import ProfileCheckoutFlow from './ProfileCheckoutFlow'
import { getTelegramWebApp, hapticSelect, initializeTelegramShell } from './telegram'

const regions = [
  ['ETHIOPIA', '🇪🇹', 'ኢትዮጵያ', 'Ethiopia'],
  ['UNITED_STATES', '🇺🇸', 'ዩናይትድ ስቴትስ', 'United States'],
  ['EUROPE', '🇪🇺', 'አውሮፓ', 'Europe'],
  ['UAE', '🇦🇪', 'ዱባይ / UAE', 'Dubai / UAE'],
  ['OTHER', '🌍', 'ሌላ አገር', 'Other'],
] as const

type LoadState =
  | { status: 'loading' }
  | { status: 'outside-telegram' }
  | { status: 'coming-soon' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: BootstrapResponse; initData: string }

export default function App() {
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  const [language, setLanguage] = useState<Language>('AM')
  const [saving, setSaving] = useState(false)
  const [otherCountry, setOtherCountry] = useState('')
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)

  async function load() {
    setState({ status: 'loading' })
    const telegram = initializeTelegramShell()
    if (!telegram?.initData) {
      setState({ status: 'outside-telegram' })
      return
    }

    try {
      const data = await bootstrap(telegram.initData)
      setLanguage(data.user.language)
      setState({ status: 'ready', data, initData: telegram.initData })
    } catch (error) {
      const code = error instanceof Error ? (error as Error & { code?: string }).code : undefined
      if (code === 'MEAL_PLAN_COMING_SOON') {
        setState({ status: 'coming-soon' })
        return
      }
      setState({ status: 'error', message: error instanceof Error ? error.message : 'Unable to open Meal Plan' })
    }
  }

  useEffect(() => { void load() }, [])

  const text = copy[language]

  async function changeLanguage(next: Language) {
    if (next === language) return
    hapticSelect()
    setLanguage(next)
    if (state.status !== 'ready') return
    try {
      await saveLanguage(state.initData, next)
      setState({ ...state, data: { ...state.data, user: { ...state.data.user, language: next } } })
    } catch {
      // Keep the visual switch responsive. Bootstrap re-syncs on next open.
    }
  }

  async function submitCountry(region: string) {
    if (state.status !== 'ready') return
    if (region === 'OTHER' && !otherCountry.trim()) {
      setSelectedRegion('OTHER')
      return
    }

    setSaving(true)
    hapticSelect()
    try {
      const result = await saveCountry(state.initData, region, region === 'OTHER' ? otherCountry : undefined)
      setState({
        ...state,
        data: {
          ...state.data,
          intake: {
            ...state.data.intake,
            country_required: false,
            country: result.country,
            state: result.intake_state,
            current_step: state.data.intake.current_step || 'WELCOME',
          },
        },
      })
      setSelectedRegion(null)
    } catch (error) {
      setState({ status: 'error', message: error instanceof Error ? error.message : 'Unable to save country' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <span className="signal-line" />
          <div><strong>HILAWE</strong><small>MEAL PLAN</small></div>
        </div>
        <div className="language-switch" aria-label="Language">
          <button className={language === 'AM' ? 'active' : ''} onClick={() => void changeLanguage('AM')}>አማ</button>
          <span />
          <button className={language === 'EN' ? 'active' : ''} onClick={() => void changeLanguage('EN')}>EN</button>
        </div>
      </header>

      {state.status === 'loading' && <LoadingCard language={language} />}

      {state.status === 'outside-telegram' && (
        <section className="center-card compact">
          <div className="status-orb">TG</div>
          <h1>{text.title}</h1>
          <p>{text.openTelegram}</p>
        </section>
      )}

      {state.status === 'coming-soon' && (
        <section className="center-card compact">
          <div className="status-orb">H</div>
          <h1>{language === 'AM' ? 'የCoach Hilawe የምግብ ፕላን በቅርቡ ይመጣል' : 'Coach Hilawe Meal Plans are coming soon'}</h1>
          <p>
            {language === 'AM'
              ? 'ለእርስዎ የተዘጋጀውን የምግብ ፕላን ልምድ የመጨረሻ ዝግጅት ላይ ነን። ዝግጁ ሲሆን በCoach Hilawe Bot እናሳውቃለን።'
              : "We’re putting the finishing touches on your personalized meal-plan experience. We’ll announce it through Coach Hilawe Bot when it’s ready."}
          </p>
          <button className="primary-button" onClick={() => getTelegramWebApp()?.close?.()}>
            {language === 'AM' ? 'ወደ Coach Hilawe Bot ተመለስ' : 'Return to Coach Hilawe Bot'}
          </button>
        </section>
      )}

      {state.status === 'error' && (
        <section className="center-card compact">
          <div className="status-orb error">!</div>
          <h1>{text.connectionIssue}</h1>
          <p>{state.message}</p>
          <button className="primary-button" onClick={() => void load()}>{text.retry}</button>
        </section>
      )}

      {state.status === 'ready' && state.data.order && (
        <PaymentOrderFlow language={language} data={state.data} initData={state.initData} onRefresh={() => void load()} />
      )}

      {state.status === 'ready' && !state.data.order && state.data.intake.country_required && (
        <section className="content-panel">
          <p className="eyebrow">{text.eyebrow}</p>
          <h1>{text.countryTitle}</h1>
          <p className="lead">{text.countryBody}</p>
          <div className="country-grid">
            {regions.map(([region, emoji, am, en]) => (
              <button key={region} className={`country-card ${selectedRegion === region ? 'selected' : ''}`} disabled={saving} onClick={() => { setSelectedRegion(region); if (region !== 'OTHER') void submitCountry(region) }}>
                <span>{emoji}</span><strong>{language === 'AM' ? am : en}</strong>
              </button>
            ))}
          </div>
          {selectedRegion === 'OTHER' && (
            <div className="other-country">
              <input value={otherCountry} onChange={(event: { target: { value: string } }) => setOtherCountry(event.target.value)} placeholder={text.otherPlaceholder} maxLength={80} autoFocus />
              <button className="primary-button" disabled={saving || otherCountry.trim().length < 2} onClick={() => void submitCountry('OTHER')}>{saving ? '…' : text.save}</button>
            </div>
          )}
        </section>
      )}

      {state.status === 'ready' && !state.data.order && state.data.renewal?.fresh_reassessment && (
        <section className="renewal-banner">
          <p className="eyebrow">RENEWAL · FRESH CHECK</p>
          <strong>{language === 'AM' ? 'የቀድሞውን PDF አንደግምም።' : 'We are not rebuying the old PDF.'}</strong>
          <span>{language === 'AM' ? 'የአሁኑ ክብደት፣ ግብ፣ ምግብ ምርጫ እና የጤና መረጃ እንደገና ይረጋገጣል።' : 'Your current weight, goal, food preferences and health information are checked again before the next plan.'}</span>
        </section>
      )}

      {state.status === 'ready' && !state.data.order && !state.data.intake.country_required && ['COUNTRY_REQUIRED','INTAKE_IN_PROGRESS'].includes(state.data.intake.state) && (
        <IntakeFlow
          key={state.data.intake.public_id}
          initData={state.initData}
          language={language}
          firstName={state.data.user.first_name}
          initialAnswers={state.data.intake.answers}
          initialStep={state.data.intake.current_step}
          assessmentComplete={false}
          onAssessmentComplete={() => void load()}
        />
      )}

      {state.status === 'ready' && !state.data.order && state.data.intake.state === 'HEALTH_REVIEW_REQUIRED' && (
        <HealthReviewHold language={language} flags={state.data.health_review?.flags || []} onRefresh={() => void load()} />
      )}

      {state.status === 'ready' && !state.data.order && state.data.intake.state === 'HEALTH_DECLINED' && (
        <HealthDeclined language={language} />
      )}

      {state.status === 'ready' && !state.data.order && ['PROFILE_READY','CHECKOUT_READY'].includes(state.data.intake.state) && (
        <ProfileCheckoutFlow
          key={`${state.data.intake.public_id}-phase4`}
          initData={state.initData}
          language={language}
          firstName={state.data.user.first_name}
          answers={state.data.intake.answers}
          profile={state.data.intake.nutrition_profile}
          intakeState={state.data.intake.state}
        />
      )}

      <footer>Coach Hilawe · Personalized Nutrition</footer>
    </main>
  )
}

function HealthReviewHold({ language, flags, onRefresh }: { language: Language; flags: string[]; onRefresh: () => void }) {
  return (
    <section className="health-hold-stage">
      <div className="health-shield large">+</div>
      <p className="eyebrow">HEALTH REVIEW · REQUIRED</p>
      <h1>{language === 'AM' ? 'ፕላንዎ ከመዘጋጀቱ በፊት ተጨማሪ ግምገማ ያስፈልጋል' : 'Your profile needs an extra review before we continue'}</h1>
      <p className="lead">{language === 'AM' ? 'ከሰጡት የጤና መረጃ ውስጥ አንዱ በCoach Hilawe የMeal Planner safety gate መሠረት በሰው እንዲገመገም ይፈልጋል። የመረጃዎ ሁሉ ተቀምጧል። በዚህ ደረጃ ምንም ክፍያ አይወሰድም። ከተፈቀደ በTelegram መልዕክት እናሳውቅዎታለን።' : 'One of your health answers triggered Coach Hilawe’s safety gate. Your assessment is saved and no payment is collected at this stage. If you are approved to continue, we will notify you on Telegram.'}</p>
      <div className="technical-card"><span className="pulse-dot" /><div><small>STATUS</small><strong>Medical / Qualified Review</strong></div></div>
      {flags.length > 0 && <details className="technical-details"><summary>{language === 'AM' ? 'የreview ምልክቶች' : 'Review flags'}</summary><div>{flags.map((flag) => <span key={flag}><b>{flag.replace(/_/g, ' ')}</b></span>)}</div></details>}
      <button className="secondary-button wide" onClick={onRefresh}>{language === 'AM' ? 'Status እንደገና ፈትሽ' : 'Refresh status'}</button>
    </section>
  )
}

function HealthDeclined({ language }: { language: Language }) {
  return <section className="health-hold-stage"><div className="status-orb error">!</div><p className="eyebrow">HEALTH REVIEW</p><h1>{language === 'AM' ? 'ይህ ጥያቄ በአሁኑ የMeal Plan አሰራር ውስጥ አይቀጥልም' : 'This profile is outside the current meal-plan workflow'}</h1><p className="lead">{language === 'AM' ? 'ምንም ክፍያ አልተወሰደም። ተጨማሪ መረጃ ካስፈለገ Coach Hilawe በTelegram ያነጋግርዎታል።' : 'No payment has been collected. Coach Hilawe can contact you on Telegram if additional guidance is appropriate.'}</p></section>
}

function PaymentOrderFlow({ language, data, initData, onRefresh }: { language: Language; data: BootstrapResponse; initData: string; onRefresh: () => void }) {
  const order = data.order!
  const payment = data.payment
  const plan = data.plan
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const [renewing, setRenewing] = useState(false)
  const settlement = payment?.settlement_amount && payment?.settlement_currency
    ? (payment.settlement_currency === 'ETB' ? `${Number(payment.settlement_amount).toLocaleString()} Br` : `$${Number(payment.settlement_amount).toLocaleString()}`)
    : (order.currency === 'ETB' ? `${Number(order.amount).toLocaleString()} Br` : `$${Number(order.amount).toLocaleString()}`)

  const state = order.state
  const waiting = state === 'AWAITING_PAYMENT'
  const paymentReview = state === 'PAYMENT_REVIEW'
  const building = ['PAYMENT_APPROVED', 'GENERATION_QUEUED', 'GENERATING'].includes(state)
  const coachReview = ['REVIEW_PENDING', 'CHANGES_REQUESTED'].includes(state)
  const delivery = ['APPROVED', 'DELIVERY_PENDING'].includes(state)
  const active = ['ACTIVE', 'RENEWAL_DUE'].includes(state)
  const failed = state === 'GENERATION_FAILED'

  const title = waiting
    ? (language === 'AM' ? 'ክፍያዎን ለማጠናቀቅ ደረሰኙን በTelegram ይላኩ' : 'Send your receipt in Telegram to complete payment')
    : paymentReview
      ? (language === 'AM' ? 'የክፍያ ደረሰኝዎ በመፈተሽ ላይ ነው' : 'Your payment receipt is being checked')
      : building
        ? (language === 'AM' ? 'የግል የምግብ ፕላንዎ እየተገነባ ነው' : 'Your personalized Meal Plan is being built')
        : coachReview
          ? (language === 'AM' ? 'ፕላንዎ አሁን በCoach review ላይ ነው' : 'Your plan is now in Coach review')
          : delivery
            ? (language === 'AM' ? 'ፕላንዎ ተፈቅዷል — ለእርስዎ በማድረስ ላይ ነው' : 'Your plan is approved — delivery is being completed')
            : active
              ? (language === 'AM' ? 'የግል የምግብ ፕላንዎ ዝግጁ ነው' : 'Your personalized Meal Plan is ready')
              : failed
                ? (language === 'AM' ? 'የፕላን ዝግጅት በቴክኒካዊ ምክንያት ቆሟል' : 'Plan preparation hit a technical issue')
                : (language === 'AM' ? 'የMeal Plan ትዕዛዝዎ' : 'Your Meal Plan order')

  const body = waiting
    ? (language === 'AM' ? 'የክፍያ መመሪያውን በBot ልከንልዎታል። “Send receipt” የሚለውን ተጭነው screenshot ይላኩ።' : 'The bot has sent your payment instructions. Tap “Send receipt” there and send a clear screenshot.')
    : paymentReview
      ? (language === 'AM' ? 'ደረሰኙ በautomation እና በreview ይረጋገጣል። Mini Appን ክፍት ማቆየት አያስፈልግም።' : 'Your receipt is going through verification and review. You do not need to keep this Mini App open.')
      : building
        ? (language === 'AM' ? 'Hilawe engine የእርስዎን nutrition targets፣ የምግብ ምርጫዎች፣ fasting፣ budget እና 3/4/5-meal structure በመጠቀም ፕላኑን እየገነባ ነው።' : 'The Hilawe engine is building the plan from your approved nutrition targets, food preferences, fasting rules, budget and meal structure.')
        : coachReview
          ? (language === 'AM' ? 'DOCX እና PDF ተዘጋጅተው ለCoach review ተልከዋል። Coach እስኪፈቅደው ድረስ ምንም ፋይል ለእርስዎ አይላክም።' : 'The DOCX and PDF have been generated and sent for Coach review. Nothing is released to you until a reviewer approves a specific version.')
          : delivery
            ? (language === 'AM' ? 'Coach review ተጠናቋል። የተፈቀደው PDF በTelegram እና Mini App ላይ እየተከፈተ ነው።' : 'Coach review is complete. The approved PDF is being unlocked in Telegram and the Mini App.')
            : active
              ? (plan?.detail_source === 'DOCUMENT_OVERRIDE'
                  ? (language === 'AM' ? 'Coach በእጅ ያስተካከለው የመጨረሻ PDF የፕላንዎ authoritative version ነው።' : 'The Coach-edited PDF is the authoritative final version of your plan.')
                  : (language === 'AM' ? 'Coach የፈቀደው የመጨረሻ PDF ከታች ይገኛል። Telegram ላይም ተልኮልዎታል።' : 'Your Coach-approved final PDF is available below and has also been sent to you in Telegram.'))
              : failed
                ? (language === 'AM' ? 'ፕላንዎ አልጠፋም። ቡድኑ ችግሩን አይቶ እንደገና ሊያስኬደው ይችላል።' : 'Your order is safe. The team can inspect the failure and queue the generation again.')
                : ''

  const stepPaymentDone = !waiting && !paymentReview
  const stepBuildDone = coachReview || delivery || active
  const stepReviewDone = delivery || active
  const stepReady = active

  async function downloadPlan() {
    setDownloading(true)
    setDownloadError('')
    try {
      const { blob, filename } = await downloadApprovedPlan(initData)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Unable to download the approved PDF')
    } finally {
      setDownloading(false)
    }
  }

  async function beginRenewal() {
    setRenewing(true)
    setDownloadError('')
    try {
      await startRenewal(initData)
      onRefresh()
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Unable to start renewal')
    } finally {
      setRenewing(false)
    }
  }

  return <section className={`phase5-payment-stage ${active ? 'plan-ready-stage' : ''}`}>
    <p className="eyebrow">ORDER · {state.replace(/_/g, ' ')}</p>
    {active && <div className="completion-mark">✓</div>}
    <h1>{title}</h1>
    <p className="lead">{body}</p>
    <div className="payment-amount-card"><small>{language === 'AM' ? 'PLAN / ORDER VALUE' : 'PLAN / ORDER VALUE'}</small><strong>{settlement}</strong></div>
    {plan && <div className="approved-version-card"><span>APPROVED VERSION</span><strong>V{plan.version_number}</strong><small>{plan.detail_source === 'DOCUMENT_OVERRIDE' ? 'COACH EDITED' : 'HILAWE ENGINE + COACH REVIEW'}</small></div>}
    {waiting && <div className="bank-stack">{(data.payment_accounts || []).map((bank) => <div className="bank-card" key={bank.code}><div><small>{bank.code}</small><strong>{bank.name}</strong></div><code>{bank.account}</code><span>{bank.holder}</span></div>)}</div>}
    <div className="review-delivery-timeline">
      <div><span className={stepPaymentDone ? 'done' : 'active'}>{stepPaymentDone ? '✓' : '1'}</span><small>PAYMENT</small></div><i />
      <div><span className={stepBuildDone ? 'done' : building ? 'active' : ''}>{stepBuildDone ? '✓' : '2'}</span><small>BUILD</small></div><i />
      <div><span className={stepReviewDone ? 'done' : coachReview ? 'active' : ''}>{stepReviewDone ? '✓' : '3'}</span><small>COACH REVIEW</small></div><i />
      <div><span className={stepReady ? 'done' : delivery ? 'active' : ''}>{stepReady ? '✓' : '4'}</span><small>READY</small></div>
    </div>
    {active && plan?.pdf_available && <button className="primary-button tall" disabled={downloading} onClick={() => void downloadPlan()}>{downloading ? '…' : (language === 'AM' ? 'የተፈቀደውን PDF ክፈት ↓' : 'Open approved PDF ↓')}</button>}
    {active && plan?.coach_username && <a className="coach-contact-button" href={`https://t.me/${plan.coach_username.replace('@', '')}`}>{language === 'AM' ? `💬 ${plan.coach_username} አነጋግር` : `💬 Contact ${plan.coach_username}`}</a>}
    {active && !plan?.pdf_available && <p className="inline-warning">{language === 'AM' ? 'PDFው Telegram ላይ ተልኳል፤ Mini App local storage copy አሁን አይገኝም።' : 'The PDF was delivered in Telegram, but the Mini App storage copy is not currently available.'}</p>}
    {active && data.followup?.due_checkin && <FollowUpCheckinCard language={language} initData={initData} checkin={data.followup.due_checkin} onComplete={onRefresh} />}
    {active && data.renewal?.available && <div className="renewal-card"><small>RENEWAL WINDOW</small><strong>{language === 'AM' ? 'ቀጣዩን ፕላን በአዲስ መረጃዎ ይጀምሩ' : 'Start the next plan from updated information'}</strong><p>{language === 'AM' ? `የአሁኑ ፕላን ${data.renewal.days_remaining ?? 0} ቀን ቀርቶታል። አዲሱ intake ከባዶ የጤና/ምግብ መረጃ ይጠይቃል።` : `Your current plan has ${data.renewal.days_remaining ?? 0} day(s) left. Renewal starts a fresh safety and food-preference assessment.`}</p><button className="primary-button" disabled={renewing} onClick={() => void beginRenewal()}>{renewing ? '…' : (language === 'AM' ? 'የቀጣዩን ፕላን አዘጋጅ →' : 'Prepare my next plan →')}</button></div>}
    {downloadError && <div className="inline-error">{downloadError}</div>}
    <button className="secondary-button wide" onClick={onRefresh}>{language === 'AM' ? 'Status እንደገና ፈትሽ' : 'Refresh status'}</button>
  </section>
}

function FollowUpCheckinCard({ language, initData, checkin, onComplete }: { language: Language; initData: string; checkin: NonNullable<NonNullable<BootstrapResponse['followup']>['due_checkin']>; onComplete: () => void }) {
  const [weight, setWeight] = useState('')
  const [adherence, setAdherence] = useState(85)
  const [hunger, setHunger] = useState(3)
  const [energy, setEnergy] = useState(3)
  const [digestion, setDigestion] = useState(3)
  const [training, setTraining] = useState(3)
  const [healthChange, setHealthChange] = useState(false)
  const [healthNotes, setHealthNotes] = useState('')
  const [avoid, setAvoid] = useState('')
  const [prefer, setPrefer] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  if (checkin.status !== 'DUE') {
    return <div className="followup-card"><small>WEEK {checkin.week_number} FOLLOW-UP</small><strong>{checkin.status.replace(/_/g, ' ')}</strong><p>{language === 'AM' ? 'መረጃዎ ተቀምጧል። ከCoach review ወይም revision በኋላ status ይቀየራል።' : 'Your update is saved. Status will change after Coach review or revision processing.'}</p></div>
  }

  async function submit() {
    const currentWeight = Number(weight)
    if (!Number.isFinite(currentWeight) || currentWeight < 30 || currentWeight > 300) {
      setError(language === 'AM' ? 'ትክክለኛ የአሁኑ ክብደት ያስገቡ።' : 'Enter a valid current weight.')
      return
    }
    if (healthChange && healthNotes.trim().length < 3) {
      setError(language === 'AM' ? 'የጤና ለውጡን በአጭሩ ይግለጹ።' : 'Briefly describe the health change.')
      return
    }
    setSaving(true); setError(''); setResult('')
    const answers: FollowUpAnswers = {
      current_weight_kg: currentWeight, adherence_percent: adherence,
      hunger_rating: hunger, energy_rating: energy, digestion_rating: digestion, training_rating: training,
      health_change: healthChange, health_change_notes: healthNotes,
      foods_to_avoid: avoid, foods_to_prioritize: prefer, notes,
    }
    try {
      const response = await submitFollowUpCheckin(initData, answers)
      if (response.status === 'REVIEW_REQUIRED') {
        setResult(language === 'AM' ? 'መረጃዎ ተቀምጧል። የጤና/ለውጥ መረጃው automationን አቁሞ Coach review ላይ ሄዷል።' : 'Saved. A health/change signal stopped automation and routed this check-in to Coach review.')
      } else if (response.revision_request_id) {
        setResult(language === 'AM' ? 'መረጃዎ ተቀምጧል። በቁጥጥር የሚደረግ revision ተጀምሯል፤ አዲሱ ፕላን ከCoach approval በፊት አይላክም።' : 'Saved. A conservative revision has been queued; the new version will not be released before Coach approval.')
      } else {
        setResult(language === 'AM' ? 'መረጃዎ ተቀምጧል። በዚህ ሳምንት የፕላን ለውጥ አላስፈለገም።' : 'Saved. No conservative plan change was needed this week.')
      }
      window.setTimeout(onComplete, 1200)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to submit follow-up')
    } finally { setSaving(false) }
  }

  const rating = (label: string, value: number, setter: (v: number) => void) => <div className="rating-row"><span>{label}</span><div>{[1,2,3,4,5].map((n) => <button key={n} className={value === n ? 'selected' : ''} onClick={() => setter(n)}>{n}</button>)}</div></div>

  return <div className="followup-card">
    <small>WEEK {checkin.week_number} · FOLLOW-UP</small>
    <strong>{language === 'AM' ? 'የዚህ ሳምንት ሁኔታዎን ያዘምኑ' : 'Update this week before we revise anything'}</strong>
    <p>{language === 'AM' ? 'አዲስ የጤና ለውጥ ካለ ካሎሪ/ምግብ automation ወዲያውኑ ይቆማል።' : 'Any new health change immediately blocks automated calorie/food revision.'}</p>
    <label className="followup-field"><span>{language === 'AM' ? 'የአሁኑ ክብደት (kg)' : 'Current weight (kg)'}</span><input type="number" min="30" max="300" step="0.1" value={weight} onChange={(e) => setWeight(e.target.value)} /></label>
    <label className="followup-field"><span>{language === 'AM' ? `ፕላኑን የተከተሉት: ${adherence}%` : `Plan adherence: ${adherence}%`}</span><input type="range" min="0" max="100" step="5" value={adherence} onChange={(e) => setAdherence(Number(e.target.value))} /></label>
    {rating(language === 'AM' ? 'ረሃብ' : 'Hunger', hunger, setHunger)}
    {rating(language === 'AM' ? 'ኃይል' : 'Energy', energy, setEnergy)}
    {rating(language === 'AM' ? 'Digestive comfort' : 'Digestion', digestion, setDigestion)}
    {rating(language === 'AM' ? 'Training' : 'Training', training, setTraining)}
    <div className="health-change-toggle"><span>{language === 'AM' ? 'አዲስ የጤና፣ መድሀኒት ወይም symptom ለውጥ አለ?' : 'Any new health, medication or symptom change?'}</span><button className={healthChange ? 'danger-selected' : ''} onClick={() => setHealthChange(!healthChange)}>{healthChange ? (language === 'AM' ? 'አዎ' : 'YES') : (language === 'AM' ? 'አይ' : 'NO')}</button></div>
    {healthChange && <label className="followup-field"><span>{language === 'AM' ? 'የጤና ለውጡን ይግለጹ' : 'Describe the health change'}</span><textarea value={healthNotes} onChange={(e) => setHealthNotes(e.target.value)} maxLength={700} /></label>}
    <label className="followup-field"><span>{language === 'AM' ? 'ከቀጣዩ version ማስወገድ የሚፈልጉት ምግብ (optional)' : 'Foods to avoid next version (optional)'}</span><input value={avoid} onChange={(e) => setAvoid(e.target.value)} maxLength={300} /></label>
    <label className="followup-field"><span>{language === 'AM' ? 'ብዙ ማየት የሚፈልጉት ምግብ (optional)' : 'Foods to prioritize (optional)'}</span><input value={prefer} onChange={(e) => setPrefer(e.target.value)} maxLength={300} /></label>
    <label className="followup-field"><span>{language === 'AM' ? 'ሌላ ማስታወሻ (optional)' : 'Other notes (optional)'}</span><textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} /></label>
    {result && <div className="followup-result">{result}</div>}
    {error && <div className="inline-error">{error}</div>}
    <button className="primary-button tall" disabled={saving} onClick={() => void submit()}>{saving ? '…' : (language === 'AM' ? 'የሳምንቱን update ላክ' : 'Submit weekly update')}</button>
  </div>
}

function LoadingCard({ language }: { language: Language }) {
  return (
    <section className="center-card compact">
      <div className="loader-ring" />
      <h1>{language === 'AM' ? 'የምግብ ፕላንዎን በመክፈት ላይ' : 'Opening your Meal Plan'}</h1>
      <p>{language === 'AM' ? 'የTelegram መለያዎን በደህንነት በማረጋገጥ ላይ…' : 'Securely verifying your Telegram session…'}</p>
    </section>
  )
}
