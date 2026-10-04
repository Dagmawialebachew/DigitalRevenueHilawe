import { useState } from 'react'
import { Language, PaymentAccount } from './api'
import { hapticSuccess } from './telegram'

type Props = {
  bank: PaymentAccount
  language: Language
}

export default function BankAccountCard({ bank, language }: Props) {
  const [copied, setCopied] = useState(false)

  async function handleCopy(e?: React.MouseEvent) {
    if (e) e.stopPropagation()
    try {
      await navigator.clipboard.writeText(bank.account)
    } catch {
      // Fallback for environments where clipboard API is restricted
      const el = document.createElement('textarea')
      el.value = bank.account
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    hapticSuccess()
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2200)
  }

  const isCbe = bank.code.toUpperCase().includes('CBE')
  const bankThemeClass = isCbe ? 'bank-theme-cbe' : 'bank-theme-abyssinia'

  return (
    <div
      className={`bank-card interactive-bank-card ${bankThemeClass} ${copied ? 'is-copied' : ''}`}
      onClick={() => void handleCopy()}
      role="button"
      tabIndex={0}
      aria-label={`${bank.name} ${bank.account}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          void handleCopy()
        }
      }}
    >
      <div className="bank-card-header">
        <div className="bank-card-title-group">
          <span className="bank-code-badge">{bank.code}</span>
          <strong className="bank-name">{bank.name}</strong>
        </div>
        <button
          type="button"
          className={`copy-button ${copied ? 'copied' : ''}`}
          onClick={(e) => void handleCopy(e)}
          title={language === 'AM' ? 'የአካውንት ቁጥር ቅዳ' : 'Copy account number'}
        >
          {copied ? (
            <>
              <span className="copy-check">✓</span>
              <span>{language === 'AM' ? 'ተቀድቷል!' : 'Copied!'}</span>
            </>
          ) : (
            <>
              <svg className="copy-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
              </svg>
              <span>{language === 'AM' ? 'ቅዳ' : 'Copy'}</span>
            </>
          )}
        </button>
      </div>

      <div className="bank-card-body">
        <div className="account-number-wrap">
          <code className="account-number">{bank.account}</code>
        </div>
      </div>

      <div className="bank-card-footer">
        <div className="account-holder-info">
          <small className="holder-label">{language === 'AM' ? 'የአካውንት ስም' : 'ACCOUNT NAME'}</small>
          <strong className="holder-name">{bank.holder}</strong>
        </div>
        <small className="tap-hint">
          {copied
            ? (language === 'AM' ? '✓ ቁጥሩ ተቀድቷል' : '✓ Number in clipboard')
            : (language === 'AM' ? 'ለመቅዳት ይጫኑ' : 'Tap to copy')}
        </small>
      </div>
    </div>
  )
}
