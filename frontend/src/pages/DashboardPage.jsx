import { useNavigate } from 'react-router-dom'
import { useAnalytics } from '../hooks/useAnalytics'
import { useCalls } from '../hooks/useCalls'
import ScoreGauge from '../components/common/ScoreGauge'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { formatTime } from '../utils/format'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const { overview, loading: overviewLoading, error: overviewError, refetch } = useAnalytics()
  const { calls, loading: callsLoading } = useCalls({ limit: 5 })
  const navigate = useNavigate()

  if (overviewError) {
    return <ErrorState message={overviewError} onRetry={refetch} />
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Dashboard</h1>

      {overviewLoading ? (
        <LoadingSkeleton count={4} />
      ) : overview ? (
        <>
          <div className={styles.cards}>
            <div className={styles.card}>
              <div className={styles.cardLabel}>Total Calls</div>
              <div className={styles.cardValue}>{overview.total_calls ?? 0}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardLabel}>Completed</div>
              <div className={styles.cardValue}>{overview.completed_calls ?? 0}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardLabel}>Failed</div>
              <div className={styles.cardValue}>{overview.failed_calls ?? 0}</div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardLabel}>Active Advisors</div>
              <div className={styles.cardValue}>{overview.active_advisors ?? 0}</div>
            </div>
          </div>

          <div className={styles.grid}>
            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Average Score</h2>
              <ScoreGauge value={overview.avg_score} size="lg" />
            </div>

            <div className={styles.section}>
              <h2 className={styles.sectionTitle}>Top Flags</h2>
              {overview.top_flags && overview.top_flags.length > 0 ? (
                <div className={styles.flagList}>
                  {overview.top_flags.map((f, i) => (
                    <div key={i} className={styles.flagRow}>
                      <span className={styles.flagTag}>{f.tag?.replace(/_/g, ' ')}</span>
                      <span className={styles.flagCount}>{f.count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState message="No flags recorded yet" />
              )}
            </div>
          </div>

          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>Recent Calls</h2>
            {callsLoading ? (
              <LoadingSkeleton type="table" count={3} />
            ) : calls.length > 0 ? (
              <div className={styles.callTable}>
                <div className={styles.callHeader}>
                  <span>Advisor</span>
                  <span>Team</span>
                  <span>Status</span>
                  <span>Duration</span>
                  <span>Score</span>
                </div>
                {calls.map(call => (
                  <div
                    key={call.id}
                    className={styles.callRow}
                    onClick={() => navigate(`/calls/${call.id}`)}
                  >
                    <span>{call.advisor_name || '—'}</span>
                    <span>{call.team_name || '—'}</span>
                    <span className={`${styles.status} ${styles[call.status] || ''}`}>{call.status}</span>
                    <span>{call.duration_sec ? formatTime(call.duration_sec) : '—'}</span>
                    <span className={styles.scoreCell}>{call.overall_score != null ? call.overall_score.toFixed(1) : '—'}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState message="No calls uploaded yet" />
            )}
          </div>
        </>
      ) : null}
    </div>
  )
}
