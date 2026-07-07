import styles from './LoadingSkeleton.module.css'

export default function LoadingSkeleton({ type = 'card', count = 1 }) {
  if (type === 'row') {
    return (
      <div className={styles.row}>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className={styles.rowItem}>
            <div className={styles.pulse} style={{ height: 14, width: '60%' }} />
            <div className={styles.pulse} style={{ height: 14, width: '40%', marginTop: 8 }} />
            <div className={styles.pulse} style={{ height: 14, width: '50%', marginTop: 8 }} />
          </div>
        ))}
      </div>
    )
  }

  if (type === 'table') {
    return (
      <div className={styles.table}>
        <div className={styles.tableHeader}>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className={styles.pulse} style={{ height: 14, width: `${60 + i * 10}%` }} />
          ))}
        </div>
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className={styles.tableRow}>
            <div className={styles.pulse} style={{ height: 14, width: '30%' }} />
            <div className={styles.pulse} style={{ height: 14, width: '45%' }} />
            <div className={styles.pulse} style={{ height: 14, width: '25%' }} />
            <div className={styles.pulse} style={{ height: 14, width: '35%' }} />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={styles.grid}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={styles.card}>
          <div className={styles.pulse} style={{ height: 16, width: '50%' }} />
          <div className={styles.pulse} style={{ height: 32, width: '30%', marginTop: 16 }} />
          <div className={styles.pulse} style={{ height: 14, width: '70%', marginTop: 16 }} />
        </div>
      ))}
    </div>
  )
}
