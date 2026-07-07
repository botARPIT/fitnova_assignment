import { useState, useEffect } from 'react'
import { useTeams } from '../hooks/useTeams'
import { useTeamAnalytics, useAdvisorAnalytics } from '../hooks/useAnalytics'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { formatTime } from '../utils/format'
import styles from './TeamPage.module.css'

export default function TeamPage() {
  const { teams, loading: teamsLoading, error: teamsError } = useTeams()
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const { stats: teamStats, loading: teamLoading } = useTeamAnalytics(selectedTeamId)
  const [selectedAdvisorId, setSelectedAdvisorId] = useState('')
  const { stats: advisorStats, loading: advisorLoading, error: advisorError } = useAdvisorAnalytics(selectedAdvisorId)

  useEffect(() => {
    setSelectedAdvisorId('')
  }, [selectedTeamId])

  useEffect(() => {
    if (teams.length > 0 && !selectedTeamId) {
      setSelectedTeamId(teams[0].id)
    }
  }, [teams, selectedTeamId])

  if (teamsError) {
    return <ErrorState message={teamsError} />
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Team</h1>

      {teamsLoading ? (
        <LoadingSkeleton count={2} />
      ) : teams.length > 0 ? (
        <>
          <div className={styles.teamTabs}>
            {teams.map(t => (
              <button
                key={t.id}
                className={`${styles.teamTab} ${selectedTeamId === t.id ? styles.activeTeam : ''}`}
                onClick={() => setSelectedTeamId(t.id)}
              >
                {t.name}
                <span className={styles.memberCount}>{t.advisor_count} members</span>
              </button>
            ))}
          </div>

          {teamLoading ? (
            <LoadingSkeleton type="table" count={3} />
          ) : teamStats && teamStats.advisors && teamStats.advisors.length > 0 ? (
            <>
              <div className={styles.leaderboard}>
                <h2 className={styles.sectionTitle}>Advisor Leaderboard</h2>
                <div className={styles.table}>
                  <div className={styles.tableHeader}>
                    <span>#</span>
                    <span>Name</span>
                    <span>Role</span>
                    <span>Calls</span>
                    <span>Avg Score</span>
                  </div>
                  {teamStats.advisors.map((a, i) => (
                    <div
                      key={a.id}
                      className={`${styles.tableRow} ${selectedAdvisorId === a.id ? styles.selectedRow : ''}`}
                      onClick={() => setSelectedAdvisorId(a.id)}
                    >
                      <span className={styles.rank}>{i + 1}</span>
                      <span>{a.name}</span>
                      <span className={styles.role}>{a.role}</span>
                      <span>{a.call_count ?? 0}</span>
                      <span className={styles.score}>{a.avg_score != null ? a.avg_score.toFixed(1) : '—'}</span>
                    </div>
                  ))}
                </div>
              </div>

              {selectedAdvisorId && (
                <div className={styles.advisorDetail}>
                  <h2 className={styles.sectionTitle}>Advisor Detail</h2>
                  {advisorLoading ? (
                    <LoadingSkeleton count={2} />
                  ) : advisorError ? (
                    <ErrorState message={advisorError} />
                  ) : advisorStats ? (
                    <div className={styles.advisorGrid}>
                      <div className={styles.advisorCard}>
                        <div className={styles.advisorStatLabel}>Total Calls</div>
                        <div className={styles.advisorStatValue}>{advisorStats.summary?.total_calls ?? 0}</div>
                      </div>
                      <div className={styles.advisorCard}>
                        <div className={styles.advisorStatLabel}>Avg Score</div>
                        <div className={styles.advisorStatValue}>{advisorStats.summary?.avg_score?.toFixed(1) ?? '—'}</div>
                      </div>
                      <div className={styles.advisorCard}>
                        <div className={styles.advisorStatLabel}>Best Score</div>
                        <div className={styles.advisorStatValue}>{advisorStats.summary?.max_score?.toFixed(1) ?? '—'}</div>
                      </div>
                      <div className={styles.advisorCard}>
                        <div className={styles.advisorStatLabel}>Lowest Score</div>
                        <div className={styles.advisorStatValue}>{advisorStats.summary?.min_score?.toFixed(1) ?? '—'}</div>
                      </div>

                      {advisorStats.recent_calls?.length > 0 && (
                        <div className={`${styles.advisorCard} ${styles.fullWidth}`}>
                          <h3 className={styles.cardTitle}>Recent Calls</h3>
                          <div className={styles.recentList}>
                            {advisorStats.recent_calls.map(c => (
                              <div key={c.id} className={styles.recentRow}>
                                <span>{formatTime(c.duration_sec)}</span>
                                <span className={styles.recentDate}>
                                  {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                                </span>
                                <span className={styles.recentScore}>{c.overall_score?.toFixed(1)}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {advisorStats.flag_frequency?.length > 0 && (
                        <div className={`${styles.advisorCard} ${styles.fullWidth}`}>
                          <h3 className={styles.cardTitle}>Common Flags</h3>
                          <div className={styles.flagFreq}>
                            {advisorStats.flag_frequency.map((f, i) => (
                              <div key={i} className={styles.flagRow}>
                                <span>{f.tag?.replace(/_/g, ' ')}</span>
                                <span className={styles.flagCount}>{f.count}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              )}
            </>
          ) : (
            <EmptyState title="No data yet" message="This team has no completed calls." />
          )}
        </>
      ) : (
        <EmptyState title="No teams" message="No teams have been set up yet." />
      )}
    </div>
  )
}
