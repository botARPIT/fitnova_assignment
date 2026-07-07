import { useState } from 'react'
import styles from './ContestModal.module.css'

export default function ContestModal({ flag, onClose, onSubmit }) {
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!reason.trim()) return
    setSubmitting(true)
    try {
      await onSubmit(reason.trim())
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <h3 className={styles.title}>Contest Flag</h3>
        {flag && (
          <div className={styles.flagPreview}>
            <span className={styles.tag}>{flag.tag?.replace(/_/g, ' ')}</span>
            <p className={styles.quote}>&ldquo;{flag.quoted_line}&rdquo;</p>
          </div>
        )}
        <textarea
          className={styles.textarea}
          placeholder="Explain why you believe this flag is incorrect..."
          value={reason}
          onChange={e => setReason(e.target.value)}
          rows={4}
        />
        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button
            className={styles.submitBtn}
            onClick={handleSubmit}
            disabled={!reason.trim() || submitting}
          >
            {submitting ? 'Submitting...' : 'Submit Contest'}
          </button>
        </div>
      </div>
    </div>
  )
}
