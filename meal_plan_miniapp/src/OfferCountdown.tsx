import React, { useEffect, useState } from 'react'
import { Language } from './api'

const STORAGE_KEY = 'hilawe_offer_timer_end_v1'
const DURATION_MS = 59 * 60 * 1000 // 59 minutes

export function OfferCountdown({ language }: { language: Language }) {
  const [timeLeftMs, setTimeLeftMs] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      const now = Date.now()
      if (stored) {
        const target = parseInt(stored, 10)
        if (target > now && target <= now + DURATION_MS) {
          return target - now
        }
      }
      const newTarget = now + DURATION_MS
      localStorage.setItem(STORAGE_KEY, String(newTarget))
      return DURATION_MS
    } catch {
      return DURATION_MS
    }
  })

  useEffect(() => {
    const timer = setInterval(() => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY)
        const now = Date.now()
        let target = stored ? parseInt(stored, 10) : 0
        if (!target || target <= now) {
          // Reset a fresh 59 min window if fully expired to maintain urgency
          target = now + DURATION_MS
          localStorage.setItem(STORAGE_KEY, String(target))
        }
        setTimeLeftMs(Math.max(0, target - now))
      } catch {
        setTimeLeftMs((prev) => Math.max(0, prev - 1000))
      }
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  const totalSeconds = Math.floor(timeLeftMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const formattedTime = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`

  const label = language === 'AM' ? 'ቅናሹ የሚያበቃበት ሰአት' : 'Special offer ends in'

  return (
    <div className="offer-countdown-pill" aria-label="Urgency Countdown">
      <span className="countdown-flame">⚡</span>
      <span className="countdown-label">{label}፦</span>
      <span className="countdown-time">{formattedTime}</span>
      <span className="countdown-pulse" />
    </div>
  )
}
