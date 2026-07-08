import { formatTime } from '../../utils/format'
import styles from './FlagCard.module.css'

export default function FlagCard({ flag, onContest, onQuoteClick, showContest = true }) {
  const quote = flag.quoted_line ?? flag.quote ?? ''
  const reason = flag.reason ?? flag.explanation ?? ''
  const matchScore = typeof flag.match_score === 'number'
    ? `${Math.round((flag.match_score <= 1 ? flag.match_score * 100 : flag.match_score))}%`
    : null

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.tag}>{flag.tag?.replace(/_/g, ' ')}</span>
        <span className={`${styles.severity} ${styles[flag.severity] || ''}`}>{flag.severity}</span>
        {matchScore && (
          <span className={styles.match}>match: {matchScore}</span>
        )}
      </div>
      <div
        className={styles.quote}
        onClick={() => onQuoteClick?.(flag)}
        role={onQuoteClick ? 'button' : undefined}
        tabIndex={onQuoteClick ? 0 : undefined}
      >
        &ldquo;{quote}&rdquo;
      </div>
      <div className={styles.reason}>{reason}</div>
      <div className={styles.footer}>
        {flag.timestamp != null && (
          <span className={styles.timestamp}>{formatTime(flag.timestamp)}</span>
        )}
        {onContest && showContest && (
          <button className={styles.contestBtn} onClick={() => onContest(flag)}>
            Contest
          </button>
        )}
      </div>
    </div>
  )
}
