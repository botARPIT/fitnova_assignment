import { useMemo } from 'react'
import { formatTime } from '../../utils/format'
import styles from './TranscriptViewer.module.css'

export default function TranscriptViewer({ turns, highlightQuote }) {
  const speakerColors = ['speaker0', 'speaker1', 'speaker2']

  const highlightedRanges = useMemo(() => {
    if (!highlightQuote) return []
    const ranges = []
    turns.forEach((turn, turnIdx) => {
      const text = turn.text.toLowerCase()
      for (let i = 0; i <= text.length - highlightQuote.length; i++) {
        const slice = text.slice(i, i + highlightQuote.length)
        if (slice === highlightQuote.toLowerCase()) {
          ranges.push({ turnIdx, start: i, end: i + highlightQuote.length })
        }
      }
    })
    return ranges
  }, [turns, highlightQuote])

  if (!turns || turns.length === 0) {
    return <div className={styles.empty}>No transcript available.</div>
  }

  return (
    <div className={styles.container}>
      {turns.map((turn, i) => {
        const spkNum = turn.speaker?.replace('speaker_', '').replace('SPEAKER_', '') || '0'
        return (
          <div key={i} className={`${styles.turn} ${highlightedRanges.some(r => r.turnIdx === i) ? styles.hasHighlight : ''}`}>
            <div className={styles.turnHeader}>
              <span className={`${styles.speaker} ${styles[speakerColors[parseInt(spkNum) % 3]]}`}>
                {turn.speaker}
              </span>
              <span className={styles.time}>
                {formatTime(turn.start)} – {formatTime(turn.end)}
              </span>
            </div>
            <div className={styles.text}>
              {highlightQuote && highlightedRanges.some(r => r.turnIdx === i)
                ? highlightText(turn.text, highlightedRanges.filter(r => r.turnIdx === i), styles)
                : turn.text}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function highlightText(text, ranges, styles) {
  const parts = []
  let lastIdx = 0

  const sorted = [...ranges].sort((a, b) => a.start - b.start)

  sorted.forEach((r, i) => {
    if (r.start > lastIdx) {
      parts.push(<span key={`t-${i}`}>{text.slice(lastIdx, r.start)}</span>)
    }
    parts.push(
      <mark key={`h-${i}`} className={styles.highlight}>
        {text.slice(r.start, r.end)}
      </mark>
    )
    lastIdx = r.end
  })

  if (lastIdx < text.length) {
    parts.push(<span key="end">{text.slice(lastIdx)}</span>)
  }

  return parts
}
