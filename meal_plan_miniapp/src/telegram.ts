export type TelegramWebApp = {
  initData: string
  ready: () => void
  expand: () => void
  close?: () => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  requestFullscreen?: () => void
  HapticFeedback?: {
    impactOccurred?: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
    selectionChanged?: () => void
  }
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp
    }
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null
}

export function initializeTelegramShell(): TelegramWebApp | null {
  const app = getTelegramWebApp()
  if (!app) return null

  app.ready()
  app.expand()
  app.setHeaderColor?.('#f7f4ed')
  app.setBackgroundColor?.('#f7f4ed')
  try {
    app.requestFullscreen?.()
  } catch {
    // Fullscreen availability varies by Telegram client/version. It is optional.
  }
  return app
}

export function hapticSelect() {
  getTelegramWebApp()?.HapticFeedback?.selectionChanged?.()
}
