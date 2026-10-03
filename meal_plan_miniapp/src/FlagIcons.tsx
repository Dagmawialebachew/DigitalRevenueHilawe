import React from 'react'

export function EthiopiaFlag({ className = 'flag-icon' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 24" width="36" height="24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <clipPath id="et-clip">
          <rect width="36" height="24" rx="4" />
        </clipPath>
      </defs>
      <g clipPath="url(#et-clip)">
        {/* Tricolor stripes */}
        <rect width="36" height="8" y="0" fill="#078930" />
        <rect width="36" height="8" y="8" fill="#FCDD09" />
        <rect width="36" height="8" y="16" fill="#DA121A" />
        {/* Blue central disc */}
        <circle cx="18" cy="12" r="5" fill="#0F47AF" />
        {/* Yellow Star and rays */}
        <polygon
          points="18,8.2 19.2,11.2 22.4,11.2 19.8,12.9 20.8,15.8 18,14.1 15.2,15.8 16.2,12.9 13.6,11.2 16.8,11.2"
          fill="#FCDD09"
        />
        <circle cx="18" cy="12" r="1.1" fill="#0F47AF" />
      </g>
    </svg>
  )
}

export function UsaFlag({ className = 'flag-icon' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 24" width="36" height="24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <clipPath id="us-clip">
          <rect width="36" height="24" rx="4" />
        </clipPath>
      </defs>
      <g clipPath="url(#us-clip)">
        {/* 13 Stripes */}
        {Array.from({ length: 7 }).map((_, i) => (
          <rect key={i} y={i * (24 / 7)} width="36" height={24 / 13} fill="#B22234" />
        ))}
        {Array.from({ length: 6 }).map((_, i) => (
          <rect key={`w-${i}`} y={(i * 2 + 1) * (24 / 13)} width="36" height={24 / 13} fill="#FFFFFF" />
        ))}
        {/* Canton */}
        <rect width="16" height="13" fill="#3C3B6E" />
        {/* Simplified star constellation */}
        <circle cx="4" cy="3.5" r="0.9" fill="#FFFFFF" />
        <circle cx="8" cy="3.5" r="0.9" fill="#FFFFFF" />
        <circle cx="12" cy="3.5" r="0.9" fill="#FFFFFF" />
        <circle cx="6" cy="6.5" r="0.9" fill="#FFFFFF" />
        <circle cx="10" cy="6.5" r="0.9" fill="#FFFFFF" />
        <circle cx="4" cy="9.5" r="0.9" fill="#FFFFFF" />
        <circle cx="8" cy="9.5" r="0.9" fill="#FFFFFF" />
        <circle cx="12" cy="9.5" r="0.9" fill="#FFFFFF" />
      </g>
    </svg>
  )
}

export function EuropeFlag({ className = 'flag-icon' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 24" width="36" height="24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <clipPath id="eu-clip">
          <rect width="36" height="24" rx="4" />
        </clipPath>
      </defs>
      <g clipPath="url(#eu-clip)">
        <rect width="36" height="24" fill="#003399" />
        {/* 12 Stars Circle */}
        {Array.from({ length: 12 }).map((_, i) => {
          const angle = (i * 30 * Math.PI) / 180
          const cx = 18 + 6.2 * Math.cos(angle)
          const cy = 12 + 6.2 * Math.sin(angle)
          return <polygon key={i} points={`${cx},${cy - 1.2} ${cx + 0.4},${cy - 0.3} ${cx + 1.2},${cy - 0.3} ${cx + 0.6},${cy + 0.3} ${cx + 0.9},${cy + 1.1} ${cx},${cy + 0.6} ${cx - 0.9},${cy + 1.1} ${cx - 0.6},${cy + 0.3} ${cx - 1.2},${cy - 0.3} ${cx - 0.4},${cy - 0.3}`} fill="#FFCC00" />
        })}
      </g>
    </svg>
  )
}

export function UaeFlag({ className = 'flag-icon' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 24" width="36" height="24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <clipPath id="uae-clip">
          <rect width="36" height="24" rx="4" />
        </clipPath>
      </defs>
      <g clipPath="url(#uae-clip)">
        {/* Horizontal stripes */}
        <rect x="9" y="0" width="27" height="8" fill="#00732F" />
        <rect x="9" y="8" width="27" height="8" fill="#FFFFFF" />
        <rect x="9" y="16" width="27" height="8" fill="#000000" />
        {/* Left vertical red stripe */}
        <rect x="0" y="0" width="9" height="24" fill="#FF0000" />
      </g>
    </svg>
  )
}

export function GlobeFlag({ className = 'flag-icon' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 24" width="36" height="24" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <clipPath id="globe-clip">
          <rect width="36" height="24" rx="4" />
        </clipPath>
      </defs>
      <g clipPath="url(#globe-clip)">
        <rect width="36" height="24" fill="#1C2128" />
        <circle cx="18" cy="12" r="8" fill="#242B35" stroke="#E6A23C" strokeWidth="1.2" />
        <ellipse cx="18" cy="12" rx="4.2" ry="8" fill="none" stroke="#E6A23C" strokeWidth="1" strokeDasharray="1.5 1.5" />
        <line x1="10" y1="12" x2="26" y2="12" stroke="#E6A23C" strokeWidth="1" />
        <line x1="18" y1="4" x2="18" y2="20" stroke="#E6A23C" strokeWidth="1" />
      </g>
    </svg>
  )
}

export function RegionFlagIcon({ region, className = 'flag-icon' }: { region: string; className?: string }) {
  switch (region) {
    case 'ETHIOPIA':
      return <EthiopiaFlag className={className} />
    case 'UNITED_STATES':
      return <UsaFlag className={className} />
    case 'EUROPE':
      return <EuropeFlag className={className} />
    case 'UAE':
      return <UaeFlag className={className} />
    case 'OTHER':
    default:
      return <GlobeFlag className={className} />
  }
}
