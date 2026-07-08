import { useEffect, useMemo, useRef } from 'react'
import { formatTime } from '../../utils/format'
import styles from './TranscriptViewer.module.css'

export default function TranscriptViewer({ turns, highlightQuote, focusTurnIndex = null }) {
  const turnRefs = useRef(new Map())

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

  useEffect(() => {
    if (focusTurnIndex == null) return
    const node = turnRefs.current.get(focusTurnIndex)
    if (node) {
      node.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [focusTurnIndex])

  if (!turns || turns.length === 0) {
    return <div className={styles.empty}>No transcript available.</div>
  }

  return (
    <div className={styles.container}>
      {turns.map((turn, i) => {
        const speakerRole = getSpeakerRole(turn.speaker)
        return (
          <div
            key={i}
            ref={(node) => {
              if (node) turnRefs.current.set(i, node)
              else turnRefs.current.delete(i)
            }}
            className={`
              ${styles.turn}
              ${styles[speakerRole]}
              ${highlightedRanges.some(r => r.turnIdx === i) ? styles.hasHighlight : ''}
              ${focusTurnIndex === i ? styles.focusedTurn : ''}
            `}
          >
            <div className={styles.turnHeader}>
              <div className={styles.speakerBlock}>
                <span className={`${styles.speaker} ${styles[`${speakerRole}Badge`]}`}>
                  {formatSpeaker(turn.speaker)}
                </span>
                <span className={styles.time}>
                  {formatTime(turn.start)} – {formatTime(turn.end)}
                </span>
              </div>
              <span className={styles.turnIndex}>
                Turn {i + 1}
              </span>
            </div>
            <div className={`${styles.text} ${styles[`${speakerRole}Text`]}`}>
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

function getSpeakerRole(speaker = '') {
  const normalized = String(speaker).trim().toLowerCase()
  if (normalized === 'advisor') return 'advisor'
  if (normalized === 'customer') return 'customer'
  if (normalized.includes('speaker_1') || normalized.includes('speaker_01')) return 'customer'
  return 'advisor'
}

function formatSpeaker(speaker = '') {
  const role = getSpeakerRole(speaker)
  return role === 'advisor' ? 'Advisor' : 'Customer'
}
