import styles from './ProgressIndicator.module.css'

const STAGES = [
  { key: 'uploading', label: 'Upload' },
  { key: 'transcribing', label: 'Transcribing' },
  { key: 'flagging', label: 'Flagging' },
  { key: 'completed', label: 'Completed' },
]

export default function ProgressIndicator({ currentStage }) {
  const normalizedStage = currentStage === 'processing' ? 'transcribing' : currentStage
  const currentIdx = STAGES.findIndex(s => s.key === normalizedStage)
  const isFullyCompleted = normalizedStage === 'completed'

  return (
    <div className={styles.container}>
      {STAGES.map((stage, i) => {
        const done = i < currentIdx || (isFullyCompleted && i === currentIdx)
        const active = i === currentIdx && !isFullyCompleted
        return (
          <div key={stage.key} className={`${styles.step} ${done ? styles.done : ''} ${active ? styles.active : ''}`}>
            <div className={styles.markerRow}>
              <div className={styles.dot}>
                {done ? (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" width="14" height="14">
                    <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                ) : active ? (
                  <span className={styles.activePulse}>
                    <span />
                    <span />
                    <span />
                  </span>
                ) : (
                  <span>{i + 1}</span>
                )}
              </div>
              {i < STAGES.length - 1 && <div className={`${styles.line} ${done ? styles.lineDone : ''}`} />}
            </div>
            <span className={styles.label}>{stage.label}</span>
          </div>
        )
      })}
    </div>
  )
}
