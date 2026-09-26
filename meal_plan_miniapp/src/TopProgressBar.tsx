import { useEffect, useState } from 'react'

type Props = {
  active: boolean
}

export default function TopProgressBar({ active }: Props) {
  const [progress, setProgress] = useState(0)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    let timer: number | undefined
    let interval: number | undefined

    if (active) {
      setVisible(true)
      setProgress(20)

      // Trickle progress up to 85% while active
      interval = window.setInterval(() => {
        setProgress((prev) => {
          if (prev >= 85) return prev
          const step = Math.max(1, Math.round((85 - prev) * 0.15))
          return Math.min(85, prev + step)
        })
      }, 200)
    } else {
      // Completed: rush to 100% and fade out
      setProgress((prev) => (prev > 0 ? 100 : 0))
      timer = window.setTimeout(() => {
        setVisible(false)
        setProgress(0)
      }, 300)
    }

    return () => {
      if (timer) window.clearTimeout(timer)
      if (interval) window.clearInterval(interval)
    }
  }, [active])

  if (!visible && progress === 0) return null

  return (
    <div className="top-progress-container" aria-hidden="true">
      <div
        className="top-progress-bar"
        style={{
          width: `${progress}%`,
          opacity: active || progress < 100 ? 1 : 0,
        }}
      />
    </div>
  )
}
