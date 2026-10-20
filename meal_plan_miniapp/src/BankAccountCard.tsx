import { useState } from 'react'
import { Language, PaymentAccount } from './api'
import { hapticSuccess } from './telegram'

type Props = {
  bank: PaymentAccount
  language: Language
}

function formatAccountDisplay(account: string): string {
  // Group digits into readable chunks of 4 for easy visual verification
  const clean = account.replace(/\s+/g, '')
  if (/^\d+$/.test(clean)) {
    return clean.replace(/(\d{4})(?=\d)/g, '$1 ')
  }
  return account
}

export default function BankAccountCard({ bank, language }: Props) {
  const [copied, setCopied] = useState(false)

  async function handleCopy(e?: React.MouseEvent) {
    if (e) e.stopPropagation()
    try {
      await navigator.clipboard.writeText(bank.account)
    } catch {
      const el = document.createElement('textarea')
      el.value = bank.account
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
    }
    hapticSuccess()
    setCopied(true)
    window.setTimeout(() => setCopied(false), 2400)
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
          <div className="bank-name-wrap">
            <strong className="bank-name">{bank.name}</strong>
            <span className="bank-verified-tag">{language === 'AM' ? 'ቀጥታ ማስተላለፊያ' : 'Direct Transfer'}</span>
          </div>
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
              <span>{language === 'AM' ? 'ቁጥር ቅዳ' : 'Copy'}</span>
            </>
          )}
        </button>
      </div>

      <div className="bank-card-body">
        <div className="account-number-box">
          <span className="account-label">{language === 'AM' ? 'የአካውንት ቁጥር' : 'ACCOUNT NUMBER'}</span>
          <div className="account-number-row">
            <span className="account-digits">{formatAccountDisplay(bank.account)}</span>
            <span className="copy-action-pill">{copied ? (language === 'AM' ? 'ተቀድቷል' : 'COPIED') : (language === 'AM' ? 'ለመቅዳት ይንኩ' : 'TAP TO COPY')}</span>
          </div>
        </div>
      </div>

      <div className="bank-card-footer">
        <div className="account-holder-info">
          <span className="holder-label">{language === 'AM' ? 'የአካውንት ባለቤት ስም' : 'ACCOUNT HOLDER NAME'}</span>
          <strong className="holder-name">{bank.holder}</strong>
        </div>
        <div className="status-indicator">
          <span className="live-indicator-dot" />
          <small>{language === 'AM' ? 'ንቁ አካውንት' : 'Active Account'}</small>
        </div>
      </div>
    </div>
  )
}
