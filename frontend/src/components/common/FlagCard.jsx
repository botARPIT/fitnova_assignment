import { formatTime } from '../../utils/format'
import styles from './FlagCard.module.css'

export default function FlagCard({ flag, onContest, onQuoteClick, showContest = true }) {
  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.tag}>{flag.tag?.replace(/_/g, ' ')}</span>
        <span className={`${styles.severity} ${styles[flag.severity] || ''}`}>{flag.severity}</span>
        {flag.match_score != null && (
          <span className={styles.match}>match: {flag.match_score}%</span>
        )}
      </div>
      <div
        className={styles.quote}
        onClick={() => onQuoteClick?.(flag)}
        role={onQuoteClick ? 'button' : undefined}
        tabIndex={onQuoteClick ? 0 : undefined}
      >
        &ldquo;{flag.quoted_line}&rdquo;
      </div>
      <div className={styles.reason}>{flag.reason}</div>
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
