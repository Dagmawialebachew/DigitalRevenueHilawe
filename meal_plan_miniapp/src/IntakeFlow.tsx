import { useEffect, useMemo, useRef, useState } from 'react'
import { completeAssessment, IntakeAnswers, Language, saveIntakeAnswers } from './api'
import {
  activityOptions,
  allergyOptions,
  budgetOptions,
  cuisineOptions,
  dietaryPatternOptions,
  fastingOptions,
  foodOptions,
  goalOptions,
  intakeCopy,
  Option,
  trainingOptions,
} from './intakeContent'
import {
  hapticError,
  hapticLight,
  hapticMedium,
  hapticSelect,
  hapticSuccess,
  syncTelegramBackButton,
} from './telegram'
import TopProgressBar from './TopProgressBar'

type Props = {
  initData: string
  language: Language
  firstName: string
  initialAnswers: IntakeAnswers
  initialStep: string | null
  assessmentComplete: boolean
  onAssessmentComplete: () => void
}

type Step =
  | 'WELCOME' | 'AGE' | 'SEX' | 'BODY' | 'GOAL' | 'TARGET_WEIGHT' | 'ACTIVITY'
  | 'TRAINING' | 'CUISINE' | 'DIETARY_PATTERN' | 'BUDGET' | 'FASTING' | 'LIKES' | 'DISLIKES'
  | 'ALLERGIES' | 'INTOLERANCES' | 'HEALTH_PREGNANCY' | 'HEALTH_EATING'
  | 'HEALTH_KIDNEY_LIVER' | 'HEALTH_DIABETES' | 'HEALTH_CLINICIAN_DIET'
  | 'HEALTH_GI' | 'HEALTH_UNEXPLAINED_WEIGHT' | 'HEALTH_OTHER'
  | 'ASSESSMENT_COMPLETE'

const validSteps = new Set<Step>([
  'WELCOME', 'AGE', 'SEX', 'BODY', 'GOAL', 'TARGET_WEIGHT', 'ACTIVITY', 'TRAINING',
  'CUISINE', 'DIETARY_PATTERN', 'BUDGET', 'FASTING', 'LIKES', 'DISLIKES', 'ALLERGIES', 'INTOLERANCES',
  'HEALTH_PREGNANCY', 'HEALTH_EATING', 'HEALTH_KIDNEY_LIVER', 'HEALTH_DIABETES',
  'HEALTH_CLINICIAN_DIET', 'HEALTH_GI', 'HEALTH_UNEXPLAINED_WEIGHT', 'HEALTH_OTHER',
  'ASSESSMENT_COMPLETE',
])

const progressOrder: Step[] = [
  'AGE', 'SEX', 'BODY', 'GOAL', 'TARGET_WEIGHT', 'ACTIVITY', 'TRAINING', 'CUISINE',
  'DIETARY_PATTERN', 'BUDGET', 'FASTING', 'LIKES', 'DISLIKES', 'ALLERGIES', 'INTOLERANCES',
  'HEALTH_PREGNANCY', 'HEALTH_EATING', 'HEALTH_KIDNEY_LIVER', 'HEALTH_DIABETES',
  'HEALTH_CLINICIAN_DIET', 'HEALTH_GI', 'HEALTH_UNEXPLAINED_WEIGHT', 'HEALTH_OTHER',
]

function asStep(value: string | null, complete: boolean): Step {
  if (complete) return 'ASSESSMENT_COMPLETE'
  const normalized = String(value || '').toUpperCase() as Step
  return validSteps.has(normalized) ? normalized : 'WELCOME'
}

function num(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function str(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

export default function IntakeFlow({
  initData,
  language,
  firstName,
  initialAnswers,
  initialStep,
  assessmentComplete,
  onAssessmentComplete,
}: Props) {
  const text = intakeCopy[language]
  const [answers, setAnswers] = useState<IntakeAnswers>(initialAnswers)
  const [step, setStep] = useState<Step>(asStep(initialStep, assessmentComplete))
  const [direction, setDirection] = useState<'forward' | 'backward'>('forward')
  const [saving, setSaving] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  const isCommittingRef = useRef(false)

  const chapter = chapterIndex(step)
  const progress = useMemo(() => {
    if (step === 'WELCOME') return 0
    if (step === 'ASSESSMENT_COMPLETE') return 100
    const index = progressOrder.indexOf(step)
    return Math.max(3, Math.round(((index + 1) / progressOrder.length) * 100))
  }, [step])

  // Synchronize Telegram's native top-left BackButton
  useEffect(() => {
    const isNested = step !== 'WELCOME' && step !== 'ASSESSMENT_COMPLETE'
    const cleanup = syncTelegramBackButton(isNested, goBack)
    return cleanup
  }, [step, answers])

  async function commit(patch: IntakeAnswers, next: Step) {
    if (isCommittingRef.current) return
    isCommittingRef.current = true
    setSaving(true)
    setError('')
    setDirection('forward')
    try {
      await saveIntakeAnswers(initData, patch, next)
      setAnswers((previous) => ({ ...previous, ...patch }))
      setStep(next)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (cause) {
      hapticError()
      setError(cause instanceof Error ? cause.message : 'Unable to save your answer')
      throw cause
    } finally {
      setSaving(false)
      isCommittingRef.current = false
    }
  }

  async function finish(patch: IntakeAnswers) {
    if (isCommittingRef.current) return
    isCommittingRef.current = true
    setSaving(true)
    setError('')
    hapticMedium()
    setDirection('forward')
    try {
      await saveIntakeAnswers(initData, patch, 'ASSESSMENT_COMPLETE')
      const merged = { ...answers, ...patch }
      await completeAssessment(initData)
      setAnswers(merged)
      setStep('ASSESSMENT_COMPLETE')
      hapticSuccess()
      onAssessmentComplete()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (cause) {
      hapticError()
      setError(cause instanceof Error ? cause.message : 'Unable to complete your assessment')
      throw cause
    } finally {
      setSaving(false)
      isCommittingRef.current = false
    }
  }

  function goBack() {
    if (saving || isCommittingRef.current) return
    const previous = previousStep(step, answers)
    if (previous) {
      hapticSelect()
      setError('')
      setDirection('backward')
      setStep(previous)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  if (step === 'WELCOME') {
    return (
      <section className="intake-stage welcome-stage">
        <TopProgressBar active={saving || starting} />
        <CoachHero firstName={firstName} language={language} />
        <p className="eyebrow">COACH HILAWE · PERSONAL NUTRITION</p>
        <h1>{text.introTitle}</h1>
        <p className="lead">{text.introBody}</p>
        <div className="value-list">
          {text.introPoints.map((point) => <div key={point}><span>✓</span><strong>{point}</strong></div>)}
        </div>
        <button
          className={`primary-button tall ${starting ? 'is-loading' : ''}`}
          disabled={starting || saving}
          onClick={() => {
            if (starting || isCommittingRef.current) return
            setStarting(true)
            hapticMedium()
            setDirection('forward')
            setStep('AGE')
          }}
        >
          {starting ? (
            <>
              <span className="button-spinner inverted" />
              <span>{text.start}</span>
            </>
          ) : (
            <>
              <span>{text.start}</span> <span>→</span>
            </>
          )}
        </button>
      </section>
    )
  }

  if (step === 'ASSESSMENT_COMPLETE') {
    return (
      <section className="completion-stage">
        <TopProgressBar active={saving} />
        <div className="completion-mark">✓</div>
        <p className="eyebrow">ASSESSMENT · COMPLETE</p>
        <h1>{text.completeTitle}</h1>
        <p className="lead">{text.completeBody}</p>
        <div className="technical-card">
          <span className="pulse-dot" />
          <div><small>NEXT SYSTEM STAGE</small><strong>Health Gate + Nutrition Profile</strong></div>
        </div>
        <p className="demo-note">{text.completeDemo}</p>
      </section>
    )
  }

  return (
    <section className="intake-stage">
      <TopProgressBar active={saving} />
      <Progress chapter={chapter} chapters={text.chapters} progress={progress} />
      {chapterGuide(step, language, firstName)}
      <div key={step} className={`step-animated-shell ${direction}`}>
        {renderStep(step, { language, answers, commit, finish, saving, text })}
      </div>
      {error && <div className="inline-error">{error}</div>}
      <div className="intake-footer-row">
        <button className="back-button" onClick={goBack} disabled={saving}>← {text.back}</button>
        <span className={`save-state ${saving ? 'active' : ''}`}>{saving ? text.saving : text.saved}</span>
      </div>
    </section>
  )
}

type RenderContext = {
  language: Language
  answers: IntakeAnswers
  commit: (patch: IntakeAnswers, next: Step) => Promise<void>
  finish: (patch: IntakeAnswers) => Promise<void>
  saving: boolean
  text: typeof intakeCopy.AM | typeof intakeCopy.EN
}

function renderStep(step: Step, ctx: RenderContext) {
  switch (step) {
    case 'AGE': return <AgeStep {...ctx} />
    case 'SEX': return <SexStep {...ctx} />
    case 'BODY': return <BodyStep {...ctx} />
    case 'GOAL': return <ChoiceStep key="GOAL" title={ctx.text.goalTitle} body={ctx.text.goalBody} options={goalOptions[ctx.language]} selected={str(ctx.answers.primary_goal)} onSelect={(value) => ctx.commit({ primary_goal: value }, 'TARGET_WEIGHT')} disabled={ctx.saving} />
    case 'TARGET_WEIGHT': return <TargetStep {...ctx} />
    case 'ACTIVITY': return <ChoiceStep key="ACTIVITY" title={ctx.text.activityTitle} body={ctx.text.activityBody} options={activityOptions[ctx.language]} selected={str(ctx.answers.activity_level)} onSelect={(value) => ctx.commit({ activity_level: value }, 'TRAINING')} disabled={ctx.saving} />
    case 'TRAINING': return <TrainingStep {...ctx} />
    case 'CUISINE': return <ChoiceStep key="CUISINE" title={ctx.text.cuisineTitle} body={ctx.text.cuisineBody} options={cuisineOptions[ctx.language]} selected={str(ctx.answers.cuisine_style)} onSelect={(value) => ctx.commit({ cuisine_style: value }, 'DIETARY_PATTERN')} disabled={ctx.saving} />
    case 'DIETARY_PATTERN': return <ChoiceStep key="DIETARY_PATTERN" title={ctx.text.dietaryTitle} body={ctx.text.dietaryBody} options={dietaryPatternOptions[ctx.language]} selected={str(ctx.answers.dietary_pattern)} onSelect={(value) => ctx.commit({ dietary_pattern: value }, 'BUDGET')} disabled={ctx.saving} />
    case 'BUDGET': return <ChoiceStep key="BUDGET" title={ctx.text.budgetTitle} body={ctx.text.budgetBody} options={budgetOptions[ctx.language]} selected={str(ctx.answers.grocery_budget)} onSelect={(value) => ctx.commit({ grocery_budget: value }, 'FASTING')} disabled={ctx.saving} />
    case 'FASTING': return <FastingStep {...ctx} />
    case 'LIKES': return <FoodSelectStep key="likes" {...ctx} mode="likes" />
    case 'DISLIKES': return <FoodSelectStep key="dislikes" {...ctx} mode="dislikes" />
    case 'ALLERGIES': return <AllergyStep {...ctx} />
    case 'INTOLERANCES': return <IntoleranceStep {...ctx} />
    case 'HEALTH_PREGNANCY': return <HealthYesNo key="HEALTH_PREGNANCY" {...ctx} field="health_pregnancy_postpartum_lactating" question={ctx.text.pregnancyQ} next="HEALTH_EATING" />
    case 'HEALTH_EATING': return <HealthYesNo key="HEALTH_EATING" {...ctx} field="health_eating_disorder_concern" question={ctx.text.eatingQ} next="HEALTH_KIDNEY_LIVER" />
    case 'HEALTH_KIDNEY_LIVER': return <HealthYesNo key="HEALTH_KIDNEY_LIVER" {...ctx} field="health_kidney_liver_disease" question={ctx.text.kidneyQ} next="HEALTH_DIABETES" />
    case 'HEALTH_DIABETES': return <HealthYesNo key="HEALTH_DIABETES" {...ctx} field="health_diabetes_or_glucose_medication" question={ctx.text.diabetesQ} next="HEALTH_CLINICIAN_DIET" />
    case 'HEALTH_CLINICIAN_DIET': return <HealthYesNo key="HEALTH_CLINICIAN_DIET" {...ctx} field="health_clinician_prescribed_diet" question={ctx.text.clinicianDietQ} next="HEALTH_GI" />
    case 'HEALTH_GI': return <HealthYesNo key="HEALTH_GI" {...ctx} field="health_severe_gi_condition" question={ctx.text.giQ} next="HEALTH_UNEXPLAINED_WEIGHT" />
    case 'HEALTH_UNEXPLAINED_WEIGHT': return <HealthYesNo key="HEALTH_UNEXPLAINED_WEIGHT" {...ctx} field="health_unexplained_weight_change" question={ctx.text.unexplainedQ} next="HEALTH_OTHER" />
    case 'HEALTH_OTHER': return <OtherHealthStep {...ctx} />
    default: return null
  }
}

function Progress({ chapter, chapters, progress }: { chapter: number; chapters: readonly string[]; progress: number }) {
  return (
    <div className="progress-shell">
      <div className="progress-meta"><span>{chapters[chapter] || chapters[0]}</span><span>{progress}%</span></div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
    </div>
  )
}

function CoachHero({ firstName, language }: { firstName: string; language: Language }) {
  const image = String(import.meta.env.VITE_COACH_IMAGE_URL || '').trim()
  return (
    <div className="coach-hero">
      <div className="coach-image-shell">
        {image ? <img src={image} alt="Coach Hilawe" /> : <div className="coach-placeholder">H</div>}
      </div>
      <div className="coach-caption">
        <small>COACH HILAWE</small>
        <strong>{language === 'AM' ? `${firstName || 'እንግዳ'}, ይህን ፕላን እንደ እውነተኛ ህይወትዎ እናዘጋጀው።` : `${firstName || 'Welcome'}, let’s make this plan fit your real life.`}</strong>
      </div>
    </div>
  )
}

function chapterGuide(step: Step, language: Language, firstName: string) {
  const note = (() => {
    if (step === 'GOAL') return language === 'AM' ? 'ጥሩ። አሁን የሰውነትዎን መረጃ አውቀናል፤ የሚሄዱበትን አቅጣጫ እንያዝ።' : 'Good. We have your starting body data; now let’s lock the direction.'
    if (step === 'CUISINE') return language === 'AM' ? 'አሁን ፕላኑን በእውነት የእርስዎ እናድርገው። የማይወዱትን ምግብ መግደድ ጥሩ ፕላን አይደለም።' : 'Now we make it yours. A plan that forces food you hate is not a useful plan.'
    if (step === 'HEALTH_PREGNANCY' || step === 'HEALTH_EATING') return language === 'AM' ? 'የመጨረሻው ክፍል ነው። እነዚህ ጥያቄዎች ፕላኑ በራስ-ሰር መቀጠል ይችላል ወይስ ተጨማሪ ግምገማ ያስፈልጋል ለማወቅ ናቸው።' : 'Last section. These answers determine whether the process can continue routinely or needs additional review.'
    return ''
  })()
  if (!note) return null
  return (
    <div className="coach-guide-strip">
      <div className="mini-coach">H</div>
      <p><small>COACH HILAWE</small>{firstName ? <strong>{note}</strong> : <strong>{note}</strong>}</p>
    </div>
  )
}

function QuestionHeader({ title, body }: { title: string; body: string }) {
  return <div className="question-header"><h2>{title}</h2><p>{body}</p></div>
}

function ChoiceStep({
  title,
  body,
  options,
  selected,
  onSelect,
  disabled,
}: {
  title: string
  body: string
  options: Option[]
  selected: string
  onSelect: (value: string) => Promise<void> | void
  disabled: boolean
}) {
  const [pendingValue, setPendingValue] = useState<string | null>(null)
  const lockedRef = useRef(false)

  async function handlePick(val: string) {
    if (disabled || lockedRef.current) return
    lockedRef.current = true
    setPendingValue(val)
    hapticMedium()
    try {
      await onSelect(val)
    } catch {
      setPendingValue(null)
      lockedRef.current = false
    }
  }

  const isLocked = Boolean(pendingValue || disabled)

  return (
    <>
      <QuestionHeader title={title} body={body} />
      <div className={`option-stack ${isLocked ? 'locked' : ''}`}>
        {options.map((option) => {
          const isSelected = selected === option.value || pendingValue === option.value
          const isPending = pendingValue === option.value
          return (
            <button
              key={option.value}
              type="button"
              disabled={isLocked && !isPending}
              className={`choice-card ${isSelected ? 'selected' : ''} ${isPending ? 'pending-active' : ''}`}
              onClick={() => void handlePick(option.value)}
            >
              {option.icon && <span className="option-icon">{option.icon}</span>}
              <div>
                <strong>{option.title}</strong>
                {option.body && <p>{option.body}</p>}
              </div>
              {isPending ? (
                <span className="choice-indicator loading">
                  <span className="button-spinner" />
                </span>
              ) : (
                <span className="choice-indicator">→</span>
              )}
            </button>
          )
        })}
      </div>
    </>
  )
}

function SubmitBar({
  onClick,
  disabled = false,
  loading = false,
  label,
  savingLabel,
}: {
  onClick: () => Promise<void> | void
  disabled?: boolean
  loading?: boolean
  label: string
  savingLabel: string
}) {
  const [submitting, setSubmitting] = useState(false)
  const lockRef = useRef(false)

  async function handlePress() {
    if (disabled || loading || submitting || lockRef.current) return
    lockRef.current = true
    setSubmitting(true)
    hapticMedium()
    try {
      await onClick()
    } finally {
      lockRef.current = false
      setSubmitting(false)
    }
  }

  const inProgress = Boolean(loading || submitting)

  return (
    <div className="scroll-end-action-bar">
      <button
        type="button"
        className={`primary-button tall ${inProgress ? 'is-loading' : ''}`}
        disabled={disabled || inProgress}
        onClick={() => void handlePress()}
      >
        {inProgress ? (
          <>
            <span className="button-spinner inverted" />
            <span>{savingLabel}</span>
          </>
        ) : (
          <>
            <span>{label}</span>
            <span>→</span>
          </>
        )}
      </button>
    </div>
  )
}

function AgeStep(ctx: RenderContext) {
  const [age, setAge] = useState(num(ctx.answers.age, 25))
  const valid = validNumber(age, 10, 100) && Number.isInteger(age)
  return (
    <>
      <QuestionHeader title={ctx.text.ageTitle} body={ctx.text.ageBody} />
      <NumberCard value={age} onChange={(value) => setAge(Math.round(value))} min={10} max={100} suffix={ctx.text.years} />
      <SubmitBar
        disabled={!valid}
        loading={ctx.saving}
        label={ctx.text.continue}
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ age }, 'SEX')}
      />
    </>
  )
}

function SexStep(ctx: RenderContext) {
  const [pendingSex, setPendingSex] = useState<'MALE' | 'FEMALE' | null>(null)
  const lockedRef = useRef(false)

  async function pickSex(sex: 'MALE' | 'FEMALE') {
    if (ctx.saving || lockedRef.current) return
    lockedRef.current = true
    setPendingSex(sex)
    hapticMedium()
    try {
      if (sex === 'MALE') {
        await ctx.commit({ calculation_sex: 'MALE', health_pregnancy_postpartum_lactating: false }, 'BODY')
      } else {
        await ctx.commit({ calculation_sex: 'FEMALE' }, 'BODY')
      }
    } catch {
      lockedRef.current = false
      setPendingSex(null)
    }
  }

  const isMale = ctx.answers.calculation_sex === 'MALE' || pendingSex === 'MALE'
  const isFemale = ctx.answers.calculation_sex === 'FEMALE' || pendingSex === 'FEMALE'
  const isLocked = Boolean(pendingSex || ctx.saving)

  return (
    <>
      <QuestionHeader title={ctx.text.sexTitle} body={ctx.text.sexBody} />
      <div className={`two-choice-grid ${isLocked ? 'locked' : ''}`}>
        <button
          type="button"
          className={`big-choice ${isMale ? 'selected' : ''} ${pendingSex === 'MALE' ? 'pending-active' : ''}`}
          onClick={() => void pickSex('MALE')}
          disabled={isLocked && pendingSex !== 'MALE'}
        >
          <span>♂</span>
          <strong>{ctx.text.male}</strong>
          {pendingSex === 'MALE' && <span className="button-spinner" style={{ marginTop: 8 }} />}
        </button>
        <button
          type="button"
          className={`big-choice ${isFemale ? 'selected' : ''} ${pendingSex === 'FEMALE' ? 'pending-active' : ''}`}
          onClick={() => void pickSex('FEMALE')}
          disabled={isLocked && pendingSex !== 'FEMALE'}
        >
          <span>♀</span>
          <strong>{ctx.text.female}</strong>
          {pendingSex === 'FEMALE' && <span className="button-spinner" style={{ marginTop: 8 }} />}
        </button>
      </div>
    </>
  )
}

function BodyStep(ctx: RenderContext) {
  const [height, setHeight] = useState(num(ctx.answers.height_cm, 170))
  const [weight, setWeight] = useState(num(ctx.answers.current_weight_kg, 70))
  const valid = validNumber(height, 100, 250) && Number.isInteger(height) && validNumber(weight, 25, 350)
  return (
    <>
      <QuestionHeader title={ctx.text.bodyTitle} body={ctx.text.bodyBody} />
      <div className="measurement-grid">
        <CompactNumber label={ctx.text.height} value={height} onChange={setHeight} min={100} max={250} suffix="cm" step={1} />
        <CompactNumber label={ctx.text.currentWeight} value={weight} onChange={setWeight} min={25} max={350} suffix="kg" step={0.5} />
      </div>
      <SubmitBar
        disabled={!valid}
        loading={ctx.saving}
        label={ctx.text.continue}
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ height_cm: height, current_weight_kg: weight }, 'GOAL')}
      />
    </>
  )
}

function TargetStep(ctx: RenderContext) {
  const current = num(ctx.answers.current_weight_kg, 70)
  const [target, setTarget] = useState(num(ctx.answers.target_weight_kg, current))
  const valid = validNumber(target, 25, 350)
  return (
    <>
      <QuestionHeader title={ctx.text.targetTitle} body={ctx.text.targetBody} />
      <NumberCard value={target} onChange={setTarget} min={25} max={350} suffix="kg" step={0.5} />
      <div className="current-reference"><span>{ctx.text.currentWeight}</span><strong>{current} kg</strong></div>
      <SubmitBar
        disabled={!valid}
        loading={ctx.saving}
        label={ctx.text.continue}
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ target_weight_kg: target }, 'ACTIVITY')}
      />
    </>
  )
}

function TrainingStep(ctx: RenderContext) {
  const [days, setDays] = useState(num(ctx.answers.training_days_per_week, 3))
  const initialType = str(ctx.answers.training_type, days === 0 ? 'NOT_TRAINING' : '')
  const [trainingType, setTrainingType] = useState(initialType)
  const activeType = days === 0 ? 'NOT_TRAINING' : trainingType === 'NOT_TRAINING' ? '' : trainingType
  return (
    <>
      <QuestionHeader title={ctx.text.trainingTitle} body={ctx.text.trainingBody} />
      <div className="day-selector">
        {[0,1,2,3,4,5,6,7].map((day) => (
          <button
            key={day}
            type="button"
            className={days === day ? 'active' : ''}
            onClick={() => {
              hapticLight()
              setDays(day)
              if (day === 0) setTrainingType('NOT_TRAINING')
            }}
          >
            {day}
          </button>
        ))}
      </div>
      <div className="selector-caption">{days} {ctx.text.daysPerWeek}</div>
      {days > 0 && (
        <div className="chip-grid training-chips">
          {trainingOptions[ctx.language].filter((item) => item.value !== 'NOT_TRAINING').map((option) => (
            <button
              key={option.value}
              type="button"
              className={activeType === option.value ? 'selected' : ''}
              onClick={() => {
                hapticMedium()
                setTrainingType(option.value)
              }}
            >
              {option.title}
            </button>
          ))}
        </div>
      )}
      <SubmitBar
        disabled={days > 0 && !activeType}
        loading={ctx.saving}
        label={ctx.text.continue}
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ training_days_per_week: days, training_type: days === 0 ? 'NOT_TRAINING' : activeType }, 'CUISINE')}
      />
    </>
  )
}

function FastingStep(ctx: RenderContext) {
  const [fasting, setFasting] = useState(str(ctx.answers.orthodox_fasting, ''))
  const existingFish = typeof ctx.answers.fish_during_fast === 'boolean' ? ctx.answers.fish_during_fast : null
  const [fish, setFish] = useState<boolean | null>(existingFish)
  const isSeasonal = fasting === 'SEASONAL' || fasting === 'WED_FRI_AND_SEASONAL'
  const [confirmedSeasonal, setConfirmedSeasonal] = useState(Boolean(ctx.answers.orthodox_fasting && isSeasonal))
  const needsFish = fasting !== '' && fasting !== 'NONE'

  function handleSelectFasting(val: string) {
    hapticMedium()
    setFasting(val)
    if (val === 'NONE') setFish(false)
    if (val === 'SEASONAL' || val === 'WED_FRI_AND_SEASONAL') {
      setConfirmedSeasonal(false)
    } else {
      setConfirmedSeasonal(true)
    }
  }

  return (
    <>
      <QuestionHeader title={ctx.text.fastingTitle} body={ctx.text.fastingBody} />
      <div className="option-stack compact-options">
        {fastingOptions[ctx.language].map((option) => (
          <button
            key={option.value}
            type="button"
            className={`choice-card ${fasting === option.value ? 'selected' : ''}`}
            onClick={() => handleSelectFasting(option.value)}
          >
            <div><strong>{option.title}</strong></div>
            <span className="radio-dot" />
          </button>
        ))}
      </div>

      {isSeasonal && (
        <div className="seasonal-fasting-alert-card">
          <div className="alert-header">
            <span className="alert-icon">🌿</span>
            <strong>
              {ctx.language === 'AM'
                ? 'ወቅታዊ ጾም ማረጋገጫ · ጾመ ጽጌ'
                : 'Seasonal Fasting Confirmation · Tsige Fast'}
            </strong>
          </div>
          <p className="alert-text">
            {ctx.language === 'AM'
              ? 'በቅርቡ የሚጀምር ጾመ ጽጌ (ከጥቅምት 6 እስከ ኅዳር 5 / መስከረም 26 – ኅዳር 5) ይገናኛል። ፕላኑ በዚህ ወቅት በሙሉ ከእንስሳት ተዋጽኦ ነፃ የሆኑ የጾም ምግቦችን ያካትታል። በዚህ ሁኔታ ይቀጥል?'
              : 'Tsige Fasting starts in a few days (Oct 6 – Nov 14 / Meskerem 26 – Hidar 5). Your plan will automatically feature 100% plant-based fasting meals during this period. Do you wish to continue with this setting?'}
          </p>
          <div className="alert-actions">
            <button
              type="button"
              className="alert-btn change"
              onClick={() => {
                hapticSelect()
                setFasting('')
                setConfirmedSeasonal(false)
              }}
            >
              {ctx.language === 'AM' ? '🔄 ምርጫ ቀይር' : '🔄 Change Selection'}
            </button>
            <button
              type="button"
              className={`alert-btn confirm ${confirmedSeasonal ? 'confirmed' : ''}`}
              onClick={() => {
                hapticMedium()
                setConfirmedSeasonal(true)
              }}
            >
              {confirmedSeasonal
                ? (ctx.language === 'AM' ? '✓ ተረጋግጧል' : '✓ Confirmed')
                : (ctx.language === 'AM' ? '✓ ይስማማኛል · ቀጥል' : '✓ I Agree · Continue')}
            </button>
          </div>
        </div>
      )}

      {needsFish && (!isSeasonal || confirmedSeasonal) && (
        <div className="conditional-card">
          <strong>{ctx.text.fishFast}</strong>
          <YesNo value={fish} onChange={setFish} text={ctx.text} />
        </div>
      )}
      <SubmitBar
        disabled={!fasting || (isSeasonal && !confirmedSeasonal) || (needsFish && fish === null)}
        loading={ctx.saving}
        label={ctx.text.continue}
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ orthodox_fasting: fasting, fish_during_fast: needsFish ? fish : false }, 'LIKES')}
      />
    </>
  )
}

function FoodSelectStep(ctx: RenderContext & { mode: 'likes' | 'dislikes' }) {
  const isLikes = ctx.mode === 'likes'
  const field = isLikes ? 'liked_foods' : 'disliked_foods'
  const otherField = isLikes ? 'liked_foods_other' : 'disliked_foods_other'
  const [selected, setSelected] = useState<string[]>(list(ctx.answers[field]))
  const [searchQuery, setSearchQuery] = useState('')
  const title = isLikes ? ctx.text.likesTitle : ctx.text.dislikesTitle
  const body = isLikes ? ctx.text.likesBody : ctx.text.dislikesBody

  const currentOptions = foodOptions[ctx.language]
  const otherLanguage: Language = ctx.language === 'AM' ? 'EN' : 'AM'
  const altOptions = foodOptions[otherLanguage]
  const altByValue = useMemo(() => new Map(altOptions.map((opt) => [opt.value, opt])), [altOptions])
  const currentByValue = useMemo(() => new Map(currentOptions.map((opt) => [opt.value, opt])), [currentOptions])

  function toggle(value: string) {
    hapticLight()
    setSelected((items) => (items.includes(value) ? items.filter((item) => item !== value) : [...items, value]))
  }

  function clearAll() {
    hapticLight()
    setSelected([])
  }

  const cleanQuery = searchQuery.trim().toLowerCase()

  const displayedOptions = useMemo(() => {
    if (!cleanQuery) {
      return currentOptions.filter((opt) => opt.popular)
    }
    return currentOptions.filter((opt) => {
      const alt = altByValue.get(opt.value)
      const hay = `${opt.title} ${opt.value} ${alt?.title || ''}`.toLowerCase()
      return hay.includes(cleanQuery)
    })
  }, [cleanQuery, currentOptions, altByValue])

  return (
    <>
      <QuestionHeader title={title} body={body} />

      {/* Selected Foods Pill Tray */}
      {selected.length > 0 && (
        <div className="selected-food-tray">
          <div className="selected-food-header">
            <span>
              <strong>{ctx.text.selectedPills}</strong> ({selected.length})
            </span>
            <button type="button" className="clear-all-button" onClick={clearAll}>
              {ctx.text.clearAll}
            </button>
          </div>
          <div className="selected-pills-list">
            {selected.map((val) => {
              const opt = currentByValue.get(val)
              const label = opt ? opt.title : val
              return (
                <button
                  key={val}
                  type="button"
                  className="selected-pill"
                  onClick={() => toggle(val)}
                  title="Remove"
                >
                  <span>{label}</span>
                  <span className="pill-remove-icon">✕</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Real-time Search Box */}
      <div className="food-search-box">
        <span className="food-search-icon" aria-hidden="true">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </span>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={ctx.text.searchFood}
          maxLength={60}
          autoComplete="off"
          spellCheck={false}
        />
        {searchQuery && (
          <button
            type="button"
            className="food-search-clear"
            onClick={() => setSearchQuery('')}
            aria-label={ctx.text.clearSearch}
          >
            ✕
          </button>
        )}
      </div>

      {/* Section Header */}
      <div className="food-grid-header">
        <span>{cleanQuery ? `${ctx.text.allFoods} (${displayedOptions.length})` : ctx.text.popularFoods}</span>
        {!cleanQuery && <small>{ctx.text.tapToDiscover}</small>}
      </div>

      {/* Food Chips Grid or Empty Search State */}
      {displayedOptions.length > 0 ? (
        <div className="chip-grid food-chips">
          {displayedOptions.map((option) => {
            const isSelected = selected.includes(option.value)
            return (
              <button
                key={option.value}
                type="button"
                className={`food-chip ${isSelected ? 'selected' : ''}`}
                onClick={() => toggle(option.value)}
              >
                {isSelected && <span className="chip-check">✓ </span>}
                {option.title}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="food-search-empty">
          <p>{ctx.text.noFoodFound}</p>
          <button type="button" className="clear-search-btn" onClick={() => setSearchQuery('')}>
            {ctx.text.clearSearch}
          </button>
        </div>
      )}

      {/* Standardized Mutex SubmitBar — clears otherField in backend */}
      <SubmitBar
        loading={ctx.saving}
        label={
          selected.length === 0
            ? (ctx.language === 'AM' ? 'ምንም የለም · ቀጥል' : 'None / Skip · Continue')
            : (ctx.language === 'AM' ? `${selected.length} ተመርጧል · ቀጥል` : `${selected.length} Selected · Continue`)
        }
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ [field]: selected, [otherField]: '' }, isLikes ? 'DISLIKES' : 'ALLERGIES')}
      />
    </>
  )
}

function AllergyStep(ctx: RenderContext) {
  const [selected, setSelected] = useState<string[]>(list(ctx.answers.food_allergies))
  const [other, setOther] = useState(str(ctx.answers.allergy_other))
  const initialSevere = typeof ctx.answers.health_anaphylactic_food_allergy === 'boolean' ? ctx.answers.health_anaphylactic_food_allergy : null
  const [severe, setSevere] = useState<boolean | null>(initialSevere)
  const hasAllergy = selected.length > 0 || other.trim().length > 0

  function toggle(value: string) {
    hapticLight()
    setSelected((items) => (items.includes(value) ? items.filter((item) => item !== value) : [...items, value]))
  }

  return (
    <>
      <QuestionHeader title={ctx.text.allergiesTitle} body={ctx.text.allergiesBody} />
      <div className="chip-grid food-chips">
        {allergyOptions[ctx.language].map((option) => (
          <button key={option.value} type="button" className={selected.includes(option.value) ? 'selected' : ''} onClick={() => toggle(option.value)}>
            {option.title}
          </button>
        ))}
      </div>
      <label className="text-card">
        <span>{ctx.text.optional}</span>
        <input value={other} onChange={(event: { target: { value: string } }) => setOther(event.target.value)} placeholder={ctx.text.other} maxLength={300} />
      </label>
      {hasAllergy && (
        <div className="conditional-card safety">
          <strong>{ctx.text.severeAllergy}</strong>
          <YesNo value={severe} onChange={setSevere} text={ctx.text} />
        </div>
      )}
      <SubmitBar
        disabled={hasAllergy && severe === null}
        loading={ctx.saving}
        label={
          !hasAllergy
            ? (ctx.language === 'AM' ? 'ምንም አለርጂ የለም · ቀጥል' : 'No Allergies · Continue')
            : (ctx.language === 'AM' ? `${selected.length || 1} ተመርጧል · ቀጥል` : `${selected.length || 1} Selected · Continue`)
        }
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ food_allergies: selected, allergy_other: other, health_anaphylactic_food_allergy: hasAllergy ? severe : false }, 'INTOLERANCES')}
      />
    </>
  )
}

function IntoleranceStep(ctx: RenderContext) {
  const [selected, setSelected] = useState<string[]>(list(ctx.answers.food_intolerances))
  const [other, setOther] = useState(str(ctx.answers.intolerance_other))

  function toggle(value: string) {
    hapticLight()
    setSelected((items) => (items.includes(value) ? items.filter((item) => item !== value) : [...items, value]))
  }

  const next: Step = ctx.answers.calculation_sex === 'FEMALE' ? 'HEALTH_PREGNANCY' : 'HEALTH_EATING'

  return (
    <>
      <QuestionHeader title={ctx.text.intoleranceTitle} body={ctx.text.intoleranceBody} />
      <div className="chip-grid food-chips">
        {allergyOptions[ctx.language].map((option) => (
          <button key={option.value} type="button" className={selected.includes(option.value) ? 'selected' : ''} onClick={() => toggle(option.value)}>
            {option.title}
          </button>
        ))}
      </div>
      <label className="text-card">
        <span>{ctx.text.optional}</span>
        <input value={other} onChange={(event: { target: { value: string } }) => setOther(event.target.value)} placeholder={ctx.text.other} maxLength={300} />
      </label>
      <SubmitBar
        loading={ctx.saving}
        label={
          selected.length === 0 && !other.trim()
            ? (ctx.language === 'AM' ? 'ምንም ችግር የለም · ቀጥል' : 'None / Skip · Continue')
            : (ctx.language === 'AM' ? `${selected.length || 1} ተመርጧል · ቀጥል` : `${selected.length || 1} Selected · Continue`)
        }
        savingLabel={ctx.text.saving}
        onClick={() => ctx.commit({ food_intolerances: selected, intolerance_other: other }, next)}
      />
    </>
  )
}

function HealthYesNo(ctx: RenderContext & { field: string; question: string; next: Step }) {
  const existing = typeof ctx.answers[ctx.field] === 'boolean' ? Boolean(ctx.answers[ctx.field]) : null
  const [pendingVal, setPendingVal] = useState<boolean | null>(null)
  const lockedRef = useRef(false)

  async function pick(val: boolean) {
    if (ctx.saving || lockedRef.current) return
    lockedRef.current = true
    setPendingVal(val)
    hapticMedium()
    try {
      await ctx.commit({ [ctx.field]: val }, ctx.next)
    } catch {
      setPendingVal(null)
      lockedRef.current = false
    }
  }

  const isNo = (existing === false && pendingVal === null) || pendingVal === false
  const isYes = (existing === true && pendingVal === null) || pendingVal === true
  const isLocked = Boolean(pendingVal !== null || ctx.saving)

  return (
    <div className="health-question-stage">
      <div className="health-shield">+</div>
      <p className="eyebrow">{ctx.text.healthIntro}</p>
      <h2>{ctx.question}</h2>
      <p className="health-explainer">{ctx.text.healthBody}</p>
      <div className={`yes-no large ${isLocked ? 'locked' : ''}`}>
        <button
          type="button"
          disabled={isLocked && pendingVal !== false}
          className={`${isNo ? 'selected' : ''} ${pendingVal === false ? 'pending-active' : ''}`}
          onClick={() => void pick(false)}
        >
          {pendingVal === false ? <span className="button-spinner" /> : ctx.text.no}
        </button>
        <button
          type="button"
          disabled={isLocked && pendingVal !== true}
          className={`${isYes ? 'selected yes' : ''} ${pendingVal === true ? 'pending-active' : ''}`}
          onClick={() => void pick(true)}
        >
          {pendingVal === true ? <span className="button-spinner inverted" /> : ctx.text.yes}
        </button>
      </div>
    </div>
  )
}

function OtherHealthStep(ctx: RenderContext) {
  const existing = typeof ctx.answers.health_other_important_change === 'boolean' ? Boolean(ctx.answers.health_other_important_change) : null
  const [choice, setChoice] = useState<boolean | null>(existing)
  const [details, setDetails] = useState(str(ctx.answers.health_other_details))

  return (
    <div className="health-question-stage">
      <div className="health-shield">+</div>
      <p className="eyebrow">{ctx.text.healthIntro}</p>
      <h2>{ctx.text.otherHealthQ}</h2>
      <p className="health-explainer">{ctx.text.healthBody}</p>
      <YesNo value={choice} onChange={(val) => { hapticMedium(); setChoice(val) }} text={ctx.text} large />
      {choice === true && (
        <label className="text-card health-details">
          <span>{ctx.text.otherHealthDetails}</span>
          <textarea value={details} onChange={(event: { target: { value: string } }) => setDetails(event.target.value)} maxLength={300} rows={4} />
        </label>
      )}
      {choice !== null && (
        <SubmitBar
          disabled={Boolean(choice && details.trim().length < 3)}
          loading={ctx.saving}
          label={ctx.text.continue}
          savingLabel={ctx.text.saving}
          onClick={() => ctx.finish({ health_other_important_change: choice, health_other_details: choice ? details : '' })}
        />
      )}
    </div>
  )
}

function YesNo({ value, onChange, text, disabled = false, large = false }: { value: boolean | null; onChange: (value: boolean) => void; text: RenderContext['text']; disabled?: boolean; large?: boolean }) {
  return (
    <div className={`yes-no ${large ? 'large' : ''} ${disabled ? 'locked' : ''}`}>
      <button
        type="button"
        disabled={disabled}
        className={value === false ? 'selected' : ''}
        onClick={() => {
          if (disabled) return
          hapticMedium()
          onChange(false)
        }}
      >
        {text.no}
      </button>
      <button
        type="button"
        disabled={disabled}
        className={value === true ? 'selected yes' : ''}
        onClick={() => {
          if (disabled) return
          hapticMedium()
          onChange(true)
        }}
      >
        {text.yes}
      </button>
    </div>
  )
}

function validNumber(value: number, min: number, max: number): boolean {
  return Number.isFinite(value) && value >= min && value <= max
}

function parseNumberDraft(raw: string): number {
  const normalized = raw.replace(',', '.')
  if (!normalized || normalized === '.') return Number.NaN
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : Number.NaN
}

function useNumberDraft(initialValue: number, onChange: (value: number) => void) {
  const [draft, setDraft] = useState(String(initialValue))

  function type(raw: string) {
    if (!/^\d*(?:[.,]\d*)?$/.test(raw)) return
    setDraft(raw)
    onChange(parseNumberDraft(raw))
  }

  function setNumeric(value: number) {
    const rounded = Math.round(value * 100) / 100
    setDraft(String(rounded))
    onChange(rounded)
  }

  return { draft, type, setNumeric }
}

function NumberCard({ value, onChange, min, max, suffix, step = 1 }: { value: number; onChange: (value: number) => void; min: number; max: number; suffix: string; step?: number }) {
  const input = useNumberDraft(value, onChange)
  function update(delta: number) {
    hapticLight()
    const current = parseNumberDraft(input.draft)
    const base = Number.isFinite(current) ? current : min
    input.setNumeric(Math.min(max, Math.max(min, base + delta)))
  }
  return (
    <div className="number-card">
      <button type="button" onClick={() => update(-step)}>−</button>
      <label>
        <input
          type="text"
          inputMode={step < 1 ? 'decimal' : 'numeric'}
          pattern={step < 1 ? '[0-9]*[.,]?[0-9]*' : '[0-9]*'}
          value={input.draft}
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => input.type(event.target.value)}
        />
        <span>{suffix}</span>
      </label>
      <button type="button" onClick={() => update(step)}>+</button>
    </div>
  )
}

function CompactNumber({ label, value, onChange, min, max, suffix, step }: { label: string; value: number; onChange: (value: number) => void; min: number; max: number; suffix: string; step: number }) {
  const input = useNumberDraft(value, onChange)
  return (
    <label className="compact-number">
      <span>{label}</span>
      <div>
        <input
          type="text"
          inputMode={step < 1 ? 'decimal' : 'numeric'}
          pattern={step < 1 ? '[0-9]*[.,]?[0-9]*' : '[0-9]*'}
          value={input.draft}
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => input.type(event.target.value)}
        />
        <small>{suffix}</small>
      </div>
    </label>
  )
}

function chapterIndex(step: Step): number {
  if (['AGE','SEX','BODY'].includes(step)) return 0
  if (['GOAL','TARGET_WEIGHT'].includes(step)) return 1
  if (['ACTIVITY','TRAINING'].includes(step)) return 2
  if (['CUISINE','DIETARY_PATTERN','BUDGET','FASTING','LIKES','DISLIKES','ALLERGIES','INTOLERANCES'].includes(step)) return 3
  return 4
}

function previousStep(step: Step, answers: IntakeAnswers): Step | null {
  const map: Partial<Record<Step, Step>> = {
    AGE: 'WELCOME', SEX: 'AGE', BODY: 'SEX', GOAL: 'BODY', TARGET_WEIGHT: 'GOAL', ACTIVITY: 'TARGET_WEIGHT',
    TRAINING: 'ACTIVITY', CUISINE: 'TRAINING', DIETARY_PATTERN: 'CUISINE', BUDGET: 'DIETARY_PATTERN', FASTING: 'BUDGET', LIKES: 'FASTING',
    DISLIKES: 'LIKES', ALLERGIES: 'DISLIKES', INTOLERANCES: 'ALLERGIES', HEALTH_EATING: 'INTOLERANCES',
    HEALTH_KIDNEY_LIVER: 'HEALTH_EATING', HEALTH_DIABETES: 'HEALTH_KIDNEY_LIVER', HEALTH_CLINICIAN_DIET: 'HEALTH_DIABETES',
    HEALTH_GI: 'HEALTH_CLINICIAN_DIET', HEALTH_UNEXPLAINED_WEIGHT: 'HEALTH_GI', HEALTH_OTHER: 'HEALTH_UNEXPLAINED_WEIGHT',
  }
  if (step === 'HEALTH_PREGNANCY') return 'INTOLERANCES'
  if (step === 'HEALTH_EATING' && answers.calculation_sex === 'FEMALE') return 'HEALTH_PREGNANCY'
  return map[step] || null
}
