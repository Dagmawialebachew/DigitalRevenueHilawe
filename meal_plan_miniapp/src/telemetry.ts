import { getTelegramWebApp } from './telegram'

const API_BASE = (
  import.meta.env.VITE_MEAL_API_BASE_URL ||
  (import.meta.env.DEV ? 'http://127.0.0.1:8081' : 'https://digitalrevenuehilawe.onrender.com')
).replace(/\/$/, '')

export type TelemetryStage = 'LAUNCH' | 'INTAKE' | 'PROFILE' | 'CHECKOUT' | 'PAYMENT' | 'DELIVERY'

export interface TelemetryUser {
  telegram_id: number
  first_name: string
  username?: string | null
}

let cachedUser: TelemetryUser | null = null

export function setTelemetryUser(user: TelemetryUser) {
  cachedUser = user
}

function getOrGenerateVisitorId(): number {
  if (typeof window === 'undefined') return 999999
  const key = 'hilawe_visitor_id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = String(Math.floor(100000000 + Math.random() * 900000000))
    localStorage.setItem(key, id)
  }
  return parseInt(id, 10)
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let pendingPayload: Record<string, unknown> | null = null

/**
 * Fire-and-forget telemetry dispatcher.
 * Guaranteed 0 main-thread lag, uses navigator.sendBeacon where available.
 */
export function trackMovement(
  stage: TelemetryStage,
  step: string,
  metadata?: Record<string, unknown>,
  immediate = false
) {
  const initData = getTelegramWebApp()?.initData || ''
  const effectiveUser = cachedUser || {
    telegram_id: getOrGenerateVisitorId(),
    first_name: 'Visitor',
    username: null,
  }

  pendingPayload = {
    init_data: initData,
    stage,
    step,
    metadata: metadata || {},
    user: effectiveUser,
    visitor_id: effectiveUser.telegram_id,
    client_ts: new Date().toISOString(),
  }

  const dispatch = () => {
    if (!pendingPayload) return
    const payload = pendingPayload
    pendingPayload = null

    const body = JSON.stringify(payload)
    const url = `${API_BASE}/api/meal/track`

    // Attempt navigator.sendBeacon first (runs off main thread, zero CPU freeze)
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      try {
        const blob = new Blob([body], { type: 'application/json' })
        const sent = navigator.sendBeacon(url, blob)
        if (sent) return
      } catch {
        // Fallback to async fetch
      }
    }

    // Fire-and-forget fetch with keepalive
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {
      // Intentionally silent
    })
  }

  if (immediate) {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    dispatch()
  } else {
    if (debounceTimer) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(dispatch, 300)
  }
}
