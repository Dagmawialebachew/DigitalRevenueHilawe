import { useMemo, useState } from 'react'
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
import { hapticSelect } from './telegram'

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
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const chapter = chapterIndex(step)
  const progress = useMemo(() => {
    if (step === 'WELCOME') return 0
    if (step === 'ASSESSMENT_COMPLETE') return 100
    const index = progressOrder.indexOf(step)
    return Math.max(3, Math.round(((index + 1) / progressOrder.length) * 100))
  }, [step])

  async function commit(patch: IntakeAnswers, next: Step) {
    if (saving) return
    setSaving(true)
    setError('')
    hapticSelect()
    try {
      await saveIntakeAnswers(initData, patch, next)
      setAnswers((previous) => ({ ...previous, ...patch }))
      setStep(next)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save your answer')
    } finally {
      setSaving(false)
    }
  }

  async function finish(patch: IntakeAnswers) {
    if (saving) return
    setSaving(true)
    setError('')
    hapticSelect()
    try {
      await saveIntakeAnswers(initData, patch, 'ASSESSMENT_COMPLETE')
      const merged = { ...answers, ...patch }
      await completeAssessment(initData)
      setAnswers(merged)
      setStep('ASSESSMENT_COMPLETE')
      onAssessmentComplete()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to complete your assessment')
    } finally {
      setSaving(false)
    }
  }

  function goBack() {
    const previous = previousStep(step, answers)
    if (previous) {
      hapticSelect()
      setError('')
      setStep(previous)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  if (step === 'WELCOME') {
    return (
      <section className="intake-stage welcome-stage">
        <CoachHero firstName={firstName} language={language} />
        <p className="eyebrow">COACH HILAWE · PERSONAL NUTRITION</p>
        <h1>{text.introTitle}</h1>
        <p className="lead">{text.introBody}</p>
        <div className="value-list">
          {text.introPoints.map((point) => <div key={point}><span>✓</span><strong>{point}</strong></div>)}
        </div>
        <button className="primary-button tall" onClick={() => setStep('AGE')}>{text.start} <span>→</span></button>
      </section>
    )
  }

  if (step === 'ASSESSMENT_COMPLETE') {
    return (
      <section className="completion-stage">
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
      <Progress chapter={chapter} chapters={text.chapters} progress={progress} />
      {chapterGuide(step, language, firstName)}
      {renderStep(step, { language, answers, commit, finish, saving, text })}
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
    case 'GOAL': return <ChoiceStep title={ctx.text.goalTitle} body={ctx.text.goalBody} options={goalOptions[ctx.language]} selected={str(ctx.answers.primary_goal)} onSelect={(value) => ctx.commit({ primary_goal: value }, 'TARGET_WEIGHT')} disabled={ctx.saving} />
    case 'TARGET_WEIGHT': return <TargetStep {...ctx} />
    case 'ACTIVITY': return <ChoiceStep title={ctx.text.activityTitle} body={ctx.text.activityBody} options={activityOptions[ctx.language]} selected={str(ctx.answers.activity_level)} onSelect={(value) => ctx.commit({ activity_level: value }, 'TRAINING')} disabled={ctx.saving} />
    case 'TRAINING': return <TrainingStep {...ctx} />
    case 'CUISINE': return <ChoiceStep title={ctx.text.cuisineTitle} body={ctx.text.cuisineBody} options={cuisineOptions[ctx.language]} selected={str(ctx.answers.cuisine_style)} onSelect={(value) => ctx.commit({ cuisine_style: value }, 'DIETARY_PATTERN')} disabled={ctx.saving} />
    case 'DIETARY_PATTERN': return <ChoiceStep title={ctx.text.dietaryTitle} body={ctx.text.dietaryBody} options={dietaryPatternOptions[ctx.language]} selected={str(ctx.answers.dietary_pattern)} onSelect={(value) => ctx.commit({ dietary_pattern: value }, 'BUDGET')} disabled={ctx.saving} />
    case 'BUDGET': return <ChoiceStep title={ctx.text.budgetTitle} body={ctx.text.budgetBody} options={budgetOptions[ctx.language]} selected={str(ctx.answers.grocery_budget)} onSelect={(value) => ctx.commit({ grocery_budget: value }, 'FASTING')} disabled={ctx.saving} />
    case 'FASTING': return <FastingStep {...ctx} />
    // These adjacent screens share an implementation but must not share local
    // selection state. Distinct keys make React remount the control when the
    // mode changes, so dislikes initialize from disliked_foods rather than the
    // selections held by the preceding likes screen (and vice versa on Back).
    case 'LIKES': return <FoodSelectStep key="likes" {...ctx} mode="likes" />
    case 'DISLIKES': return <FoodSelectStep key="dislikes" {...ctx} mode="dislikes" />
    case 'ALLERGIES': return <AllergyStep {...ctx} />
    case 'INTOLERANCES': return <IntoleranceStep {...ctx} />
    case 'HEALTH_PREGNANCY': return <HealthYesNo {...ctx} field="health_pregnancy_postpartum_lactating" question={ctx.text.pregnancyQ} next="HEALTH_EATING" />
    case 'HEALTH_EATING': return <HealthYesNo {...ctx} field="health_eating_disorder_concern" question={ctx.text.eatingQ} next="HEALTH_KIDNEY_LIVER" />
    case 'HEALTH_KIDNEY_LIVER': return <HealthYesNo {...ctx} field="health_kidney_liver_disease" question={ctx.text.kidneyQ} next="HEALTH_DIABETES" />
    case 'HEALTH_DIABETES': return <HealthYesNo {...ctx} field="health_diabetes_or_glucose_medication" question={ctx.text.diabetesQ} next="HEALTH_CLINICIAN_DIET" />
    case 'HEALTH_CLINICIAN_DIET': return <HealthYesNo {...ctx} field="health_clinician_prescribed_diet" question={ctx.text.clinicianDietQ} next="HEALTH_GI" />
    case 'HEALTH_GI': return <HealthYesNo {...ctx} field="health_severe_gi_condition" question={ctx.text.giQ} next="HEALTH_UNEXPLAINED_WEIGHT" />
    case 'HEALTH_UNEXPLAINED_WEIGHT': return <HealthYesNo {...ctx} field="health_unexplained_weight_change" question={ctx.text.unexplainedQ} next="HEALTH_OTHER" />
    case 'HEALTH_OTHER': return <OtherHealthStep {...ctx} />
    default: return null
  }
}

function Progress({ chapter, chapters, progress }: { chapter: number; chapters: readonly string[]; progress: number }) {
  return (
    <div className="progress-shell">
      <div className="progress-meta"><span>{chapters[chapter] || chapters[0]}</span><span>{progress}%</span></div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
      <div className="chapter-dots" aria-hidden="true">{chapters.map((_, index) => <i key={index} className={index <= chapter ? 'active' : ''} />)}</div>
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

function ChoiceStep({ title, body, options, selected, onSelect, disabled }: { title: string; body: string; options: Option[]; selected: string; onSelect: (value: string) => void; disabled: boolean }) {
  return (
    <>
      <QuestionHeader title={title} body={body} />
      <div className="option-stack">
        {options.map((option) => (
          <button key={option.value} disabled={disabled} className={`choice-card ${selected === option.value ? 'selected' : ''}`} onClick={() => onSelect(option.value)}>
            {option.icon && <span className="option-icon">{option.icon}</span>}
            <div><strong>{option.title}</strong>{option.body && <p>{option.body}</p>}</div><span className="choice-indicator">→</span>
          </button>
        ))}
      </div>
    </>
  )
}

function AgeStep(ctx: RenderContext) {
  const [age, setAge] = useState(num(ctx.answers.age, 25))
  const valid = validNumber(age, 10, 100) && Number.isInteger(age)
  return (
    <>
      <QuestionHeader title={ctx.text.ageTitle} body={ctx.text.ageBody} />
      <NumberCard value={age} onChange={(value) => setAge(Math.round(value))} min={10} max={100} suffix={ctx.text.years} />
      <button className="primary-button tall" disabled={ctx.saving || !valid} onClick={() => ctx.commit({ age }, 'SEX')}>{ctx.text.continue} →</button>
    </>
  )
}

function SexStep(ctx: RenderContext) {
  return (
    <>
      <QuestionHeader title={ctx.text.sexTitle} body={ctx.text.sexBody} />
      <div className="two-choice-grid">
        <button className={`big-choice ${ctx.answers.calculation_sex === 'MALE' ? 'selected' : ''}`} onClick={() => ctx.commit({ calculation_sex: 'MALE', health_pregnancy_postpartum_lactating: false }, 'BODY')} disabled={ctx.saving}><span>♂</span><strong>{ctx.text.male}</strong></button>
        <button className={`big-choice ${ctx.answers.calculation_sex === 'FEMALE' ? 'selected' : ''}`} onClick={() => ctx.commit({ calculation_sex: 'FEMALE' }, 'BODY')} disabled={ctx.saving}><span>♀</span><strong>{ctx.text.female}</strong></button>
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
      <button className="primary-button tall" disabled={ctx.saving || !valid} onClick={() => ctx.commit({ height_cm: height, current_weight_kg: weight }, 'GOAL')}>{ctx.text.continue} →</button>
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
      <button className="primary-button tall" disabled={ctx.saving || !valid} onClick={() => ctx.commit({ target_weight_kg: target }, 'ACTIVITY')}>{ctx.text.continue} →</button>
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
        {[0,1,2,3,4,5,6,7].map((day) => <button key={day} className={days === day ? 'active' : ''} onClick={() => { setDays(day); if (day === 0) setTrainingType('NOT_TRAINING') }}>{day}</button>)}
      </div>
      <div className="selector-caption">{days} {ctx.text.daysPerWeek}</div>
      {days > 0 && <div className="chip-grid training-chips">{trainingOptions[ctx.language].filter((item) => item.value !== 'NOT_TRAINING').map((option) => <button key={option.value} className={activeType === option.value ? 'selected' : ''} onClick={() => setTrainingType(option.value)}>{option.title}</button>)}</div>}
      <button className="primary-button tall" disabled={ctx.saving || (days > 0 && !activeType)} onClick={() => ctx.commit({ training_days_per_week: days, training_type: days === 0 ? 'NOT_TRAINING' : activeType }, 'CUISINE')}>{ctx.text.continue} →</button>
    </>
  )
}

function FastingStep(ctx: RenderContext) {
  const [fasting, setFasting] = useState(str(ctx.answers.orthodox_fasting, ''))
  const existingFish = typeof ctx.answers.fish_during_fast === 'boolean' ? ctx.answers.fish_during_fast : null
  const [fish, setFish] = useState<boolean | null>(existingFish)
  const needsFish = fasting !== '' && fasting !== 'NONE'
  return (
    <>
      <QuestionHeader title={ctx.text.fastingTitle} body={ctx.text.fastingBody} />
      <div className="option-stack compact-options">{fastingOptions[ctx.language].map((option) => <button key={option.value} className={`choice-card ${fasting === option.value ? 'selected' : ''}`} onClick={() => { setFasting(option.value); if (option.value === 'NONE') setFish(false) }}><div><strong>{option.title}</strong></div><span className="radio-dot" /></button>)}</div>
      {needsFish && <div className="conditional-card"><strong>{ctx.text.fishFast}</strong><YesNo value={fish} onChange={setFish} text={ctx.text} /></div>}
      <button className="primary-button tall" disabled={ctx.saving || !fasting || (needsFish && fish === null)} onClick={() => ctx.commit({ orthodox_fasting: fasting, fish_during_fast: needsFish ? fish : false }, 'LIKES')}>{ctx.text.continue} →</button>
    </>
  )
}

function FoodSelectStep(ctx: RenderContext & { mode: 'likes' | 'dislikes' }) {
  const isLikes = ctx.mode === 'likes'
  const field = isLikes ? 'liked_foods' : 'disliked_foods'
  const otherField = isLikes ? 'liked_foods_other' : 'disliked_foods_other'
  const [selected, setSelected] = useState<string[]>(list(ctx.answers[field]))
  const [other, setOther] = useState(str(ctx.answers[otherField]))
  const title = isLikes ? ctx.text.likesTitle : ctx.text.dislikesTitle
  const body = isLikes ? ctx.text.likesBody : ctx.text.dislikesBody
  function toggle(value: string) { setSelected((items) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]) }
  return (
    <>
      <QuestionHeader title={title} body={body} />
      <div className="chip-grid food-chips">{foodOptions[ctx.language].map((option) => <button key={option.value} className={selected.includes(option.value) ? 'selected' : ''} onClick={() => toggle(option.value)}>{option.title}</button>)}</div>
      <label className="text-card"><span>{ctx.text.optional}</span><input value={other} onChange={(event: { target: { value: string } }) => setOther(event.target.value)} placeholder={ctx.text.other} maxLength={300} /></label>
      <button className="primary-button tall" disabled={ctx.saving} onClick={() => ctx.commit({ [field]: selected, [otherField]: other }, isLikes ? 'DISLIKES' : 'ALLERGIES')}>{ctx.text.continue} →</button>
    </>
  )
}

function AllergyStep(ctx: RenderContext) {
  const [selected, setSelected] = useState<string[]>(list(ctx.answers.food_allergies))
  const [other, setOther] = useState(str(ctx.answers.allergy_other))
  const initialSevere = typeof ctx.answers.health_anaphylactic_food_allergy === 'boolean' ? ctx.answers.health_anaphylactic_food_allergy : null
  const [severe, setSevere] = useState<boolean | null>(initialSevere)
  const hasAllergy = selected.length > 0 || other.trim().length > 0
  function toggle(value: string) { setSelected((items) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]) }
  return (
    <>
      <QuestionHeader title={ctx.text.allergiesTitle} body={ctx.text.allergiesBody} />
      <div className="chip-grid food-chips">{allergyOptions[ctx.language].map((option) => <button key={option.value} className={selected.includes(option.value) ? 'selected' : ''} onClick={() => toggle(option.value)}>{option.title}</button>)}</div>
      <label className="text-card"><span>{ctx.text.optional}</span><input value={other} onChange={(event: { target: { value: string } }) => setOther(event.target.value)} placeholder={ctx.text.other} maxLength={300} /></label>
      {hasAllergy && <div className="conditional-card safety"><strong>{ctx.text.severeAllergy}</strong><YesNo value={severe} onChange={setSevere} text={ctx.text} /></div>}
      <button className="primary-button tall" disabled={ctx.saving || (hasAllergy && severe === null)} onClick={() => ctx.commit({ food_allergies: selected, allergy_other: other, health_anaphylactic_food_allergy: hasAllergy ? severe : false }, 'INTOLERANCES')}>{ctx.text.continue} →</button>
    </>
  )
}

function IntoleranceStep(ctx: RenderContext) {
  const [selected, setSelected] = useState<string[]>(list(ctx.answers.food_intolerances))
  const [other, setOther] = useState(str(ctx.answers.intolerance_other))
  function toggle(value: string) { setSelected((items) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]) }
  const next: Step = ctx.answers.calculation_sex === 'FEMALE' ? 'HEALTH_PREGNANCY' : 'HEALTH_EATING'
  return (
    <>
      <QuestionHeader title={ctx.text.intoleranceTitle} body={ctx.text.intoleranceBody} />
      <div className="chip-grid food-chips">{allergyOptions[ctx.language].map((option) => <button key={option.value} className={selected.includes(option.value) ? 'selected' : ''} onClick={() => toggle(option.value)}>{option.title}</button>)}</div>
      <label className="text-card"><span>{ctx.text.optional}</span><input value={other} onChange={(event: { target: { value: string } }) => setOther(event.target.value)} placeholder={ctx.text.other} maxLength={300} /></label>
      <button className="primary-button tall" disabled={ctx.saving} onClick={() => ctx.commit({ food_intolerances: selected, intolerance_other: other }, next)}>{ctx.text.continue} →</button>
    </>
  )
}

function HealthYesNo(ctx: RenderContext & { field: string; question: string; next: Step }) {
  const existing = typeof ctx.answers[ctx.field] === 'boolean' ? Boolean(ctx.answers[ctx.field]) : null
  return (
    <div className="health-question-stage">
      <div className="health-shield">+</div>
      <p className="eyebrow">{ctx.text.healthIntro}</p>
      <h2>{ctx.question}</h2>
      <p className="health-explainer">{ctx.text.healthBody}</p>
      <YesNo value={existing} onChange={(value) => void ctx.commit({ [ctx.field]: value }, ctx.next)} text={ctx.text} disabled={ctx.saving} large />
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
      <YesNo value={choice} onChange={setChoice} text={ctx.text} large />
      {choice === true && <label className="text-card health-details"><span>{ctx.text.otherHealthDetails}</span><textarea value={details} onChange={(event: { target: { value: string } }) => setDetails(event.target.value)} maxLength={300} rows={4} /></label>}
      {choice !== null && <button className="primary-button tall" disabled={ctx.saving || (choice && details.trim().length < 3)} onClick={() => void ctx.finish({ health_other_important_change: choice, health_other_details: choice ? details : '' })}>{ctx.saving ? ctx.text.saving : `${ctx.text.continue} →`}</button>}
    </div>
  )
}

function YesNo({ value, onChange, text, disabled = false, large = false }: { value: boolean | null; onChange: (value: boolean) => void; text: RenderContext['text']; disabled?: boolean; large?: boolean }) {
  return <div className={`yes-no ${large ? 'large' : ''}`}><button disabled={disabled} className={value === false ? 'selected' : ''} onClick={() => onChange(false)}>{text.no}</button><button disabled={disabled} className={value === true ? 'selected yes' : ''} onClick={() => onChange(true)}>{text.yes}</button></div>
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
    const current = parseNumberDraft(input.draft)
    const base = Number.isFinite(current) ? current : min
    input.setNumeric(Math.min(max, Math.max(min, base + delta)))
  }
  return <div className="number-card"><button type="button" onClick={() => update(-step)}>−</button><label><input type="text" inputMode={step < 1 ? 'decimal' : 'numeric'} pattern={step < 1 ? '[0-9]*[.,]?[0-9]*' : '[0-9]*'} value={input.draft} onFocus={(event) => event.currentTarget.select()} onChange={(event) => input.type(event.target.value)} /><span>{suffix}</span></label><button type="button" onClick={() => update(step)}>+</button></div>
}

function CompactNumber({ label, value, onChange, min, max, suffix, step }: { label: string; value: number; onChange: (value: number) => void; min: number; max: number; suffix: string; step: number }) {
  const input = useNumberDraft(value, onChange)
  return <label className="compact-number"><span>{label}</span><div><input type="text" inputMode={step < 1 ? 'decimal' : 'numeric'} pattern={step < 1 ? '[0-9]*[.,]?[0-9]*' : '[0-9]*'} value={input.draft} onFocus={(event) => event.currentTarget.select()} onChange={(event) => input.type(event.target.value)} /><small>{suffix}</small></div></label>
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
