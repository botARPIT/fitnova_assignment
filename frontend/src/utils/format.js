export function formatTime(sec) {
  if (sec == null) return '--:--'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatBytes(bytes) {
  if (bytes == null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function getScoreVal(val) {
  if (val == null) return null
  if (typeof val === 'object' && val !== null && 'score' in val) {
    const num = Number(val.score)
    return isNaN(num) ? null : num
  }
  const num = Number(val)
  return isNaN(num) ? null : num
}

export function getScoreEvidence(val) {
  if (!val || typeof val !== 'object') return ''
  return typeof val.evidence === 'string' ? val.evidence : ''
}

export function formatScore(val) {
  const scoreVal = getScoreVal(val)
  if (scoreVal == null) return '—'
  return scoreVal.toFixed(1)
}

export function scoreColor(val, max = 5) {
  const scoreVal = getScoreVal(val)
  if (scoreVal == null) return 'low'
  const pct = scoreVal / max
  if (pct >= 0.7) return 'high'
  if (pct >= 0.4) return 'mid'
  return 'low'
}

export function scoreColorHex(val, max = 5) {
  const scoreVal = getScoreVal(val)
  if (scoreVal == null) return 'var(--text-secondary)'
  const pct = scoreVal / max
  if (pct >= 0.7) return 'var(--success)'
  if (pct >= 0.4) return 'var(--warning)'
  return 'var(--error)'
}

export function truncateId(id) {
  if (!id) return ''
  return `${id.slice(0, 8)}…`
}
