import { formatScore, getScoreVal, scoreColorHex } from '../../utils/format'
import styles from './ScoreGauge.module.css'

export default function ScoreGauge({ value, max = 5, label, size = 'md' }) {
  const scoreValue = getScoreVal(value)
  const pct = scoreValue == null ? 0 : Math.min((scoreValue / max) * 100, 100)
  const color = scoreColorHex(value, max)

  return (
    <div className={`${styles.container} ${styles[size]}`}>
      {label && <div className={styles.label}>{label}</div>}
      <div className={styles.value} style={{ color }}>{formatScore(value)}</div>
      <div className={styles.barTrack}>
        <div
          className={styles.barFill}
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <div className={styles.range}>
        <span>0</span>
        <span>{max}</span>
      </div>
    </div>
  )
}
