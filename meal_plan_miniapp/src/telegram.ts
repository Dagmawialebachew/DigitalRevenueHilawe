export type TelegramWebApp = {
  initData: string
  ready: () => void
  expand: () => void
  close?: () => void
  setHeaderColor?: (color: string) => void
  setBackgroundColor?: (color: string) => void
  HapticFeedback?: {
    impactOccurred?: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
    selectionChanged?: () => void
    notificationOccurred?: (type: 'error' | 'success' | 'warning') => void
  }
  BackButton?: {
    isVisible: boolean
    show: () => void
    hide: () => void
    onClick: (callback: () => void) => void
    offClick: (callback: () => void) => void
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
  return app
}

export function hapticSelect() {
  getTelegramWebApp()?.HapticFeedback?.selectionChanged?.()
}

export function hapticLight() {
  getTelegramWebApp()?.HapticFeedback?.impactOccurred?.('light')
}

export function hapticMedium() {
  getTelegramWebApp()?.HapticFeedback?.impactOccurred?.('medium')
}

export function hapticHeavy() {
  getTelegramWebApp()?.HapticFeedback?.impactOccurred?.('heavy')
}

export function hapticSuccess() {
  getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.('success')
}

export function hapticError() {
  getTelegramWebApp()?.HapticFeedback?.notificationOccurred?.('error')
}

/**
 * Synchronizes the native Telegram WebApp top-left BackButton.
 * Returns a cleanup function to unregister the listener and hide the button.
 */
export function syncTelegramBackButton(visible: boolean, onBack?: () => void): () => void {
  const app = getTelegramWebApp()
  const btn = app?.BackButton
  if (!btn) return () => {}

  if (visible && onBack) {
    btn.show()
    btn.onClick(onBack)
    return () => {
      btn.offClick(onBack)
      btn.hide()
    }
  } else {
    btn.hide()
    return () => {}
  }
}
