import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useCall } from '../hooks/useCall'
import ScoreGauge from '../components/common/ScoreGauge'
import FlagCard from '../components/common/FlagCard'
import TranscriptViewer from '../components/common/TranscriptViewer'
import ContestModal from '../components/common/ContestModal'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { formatScore, formatTime, getScoreEvidence, getScoreVal, scoreColor } from '../utils/format'
import { contestFlag as contestFlagApi } from '../services/reviews'
import styles from './CallDetailPage.module.css'

export default function CallDetailPage() {
  const { callId } = useParams()
  const { call, loading, error, refetch } = useCall(callId)
  const [activeTab, setActiveTab] = useState('overview')
  const [highlightQuote, setHighlightQuote] = useState(null)
  const [contestFlag, setContestFlag] = useState(null)
  const [contestMsg, setContestMsg] = useState(null)

  if (loading) {
    return (
      <div className={styles.page}>
        <LoadingSkeleton type="table" count={1} />
        <div style={{ height: 20 }} />
        <LoadingSkeleton count={3} />
      </div>
    )
  }

  if (error) {
    return <ErrorState message={error} onRetry={refetch} />
  }

  if (!call) {
    return <EmptyState title="Call not found" message="This call does not exist or may have been deleted." />
  }

  const scores = call.scores || {}
  const flags = call.flags || []
  const discardedFlags = call.discarded_flags || []
  const turns = call.turns || []

  const handleContest = async (flag) => {
    setContestFlag(flag)
    setContestMsg(null)
  }

  const handleContestSubmit = async (reason) => {
    const flagIdx = flags.indexOf(contestFlag)
    try {
      await contestFlagApi(callId, { flag_index: flagIdx, reason })
      setContestMsg('Flag contested successfully.')
      setContestFlag(null)
    } catch (e) {
      setContestMsg(`Error: ${e.detail || e.message}`)
    }
  }

  const handleQuoteClick = (flag) => {
    setHighlightQuote(flag.quoted_line || flag.quote || null)
    setActiveTab('transcript')
  }

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'transcript', label: 'Transcript' },
    { key: 'analysis', label: 'Analysis' },
    { key: 'reviews', label: 'Reviews' },
  ]

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Call Detail</h1>
          <p className={styles.subtitle}>
            ID: {call.id?.slice(0, 8)}… &middot;{' '}
            {call.advisor_name || 'Unknown advisor'} &middot;{' '}
            {call.team_name || 'No team'}
          </p>
        </div>
        <div className={styles.meta}>
          {call.duration_sec && (
            <span className={styles.metaItem}>⏱ {formatTime(call.duration_sec)}</span>
          )}
          <span className={`${styles.metaItem} ${styles[call.status]}`}>{call.status}</span>
        </div>
      </div>

      <div className={styles.tabs}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={`${styles.tab} ${activeTab === tab.key ? styles.activeTab : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {contestMsg && (
        <div className={styles.contestMsg}>{contestMsg}</div>
      )}

      {activeTab === 'overview' && (
        <div className={styles.overview}>
          <div className={styles.scoreGrid}>
            <ScoreGauge value={call.overall_score} size="lg" label="Overall Score" />
            {Object.entries(scores).map(([dim, val]) => (
              <ScoreGauge key={dim} value={val} label={dim.replace(/_/g, ' ')} />
            ))}
          </div>

          <div className={styles.flagsSection}>
            <h2 className={styles.sectionTitle}>Flags ({flags.length})</h2>
            {flags.length > 0 ? (
              <div className={styles.flagGrid}>
                {flags.map((flag, i) => (
                  <FlagCard
                    key={i}
                    flag={flag}
                    onContest={handleContest}
                    onQuoteClick={handleQuoteClick}
                  />
                ))}
              </div>
            ) : (
              <EmptyState message="No flags on this call" />
            )}
          </div>

          {discardedFlags.length > 0 && (
            <div className={styles.flagsSection}>
              <h2 className={styles.sectionTitle}>Discarded Flags ({discardedFlags.length})</h2>
              <div className={styles.flagGrid}>
                {discardedFlags.map((flag, i) => (
                  <FlagCard key={i} flag={flag} showContest={false} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'transcript' && (
        <TranscriptViewer
          turns={turns}
          highlightQuote={highlightQuote}
        />
      )}

      {activeTab === 'analysis' && (
        <div className={styles.analysis}>
          {Object.entries(scores).length > 0 ? (
            <div className={styles.dimScores}>
              {Object.entries(scores).map(([dim, val]) => (
                <div key={dim} className={styles.dimBlock}>
                  <div className={styles.dimRow}>
                    <span className={styles.dimLabel}>{dim.replace(/_/g, ' ')}</span>
                    <div className={styles.dimBar}>
                      <div
                        className={styles.dimFill}
                        style={{
                          width: `${((getScoreVal(val) ?? 0) / 5) * 100}%`,
                          background:
                            (getScoreVal(val) ?? 0) >= 3.5
                              ? 'var(--success)'
                              : (getScoreVal(val) ?? 0) >= 2
                                ? 'var(--warning)'
                                : 'var(--error)',
                        }}
                      />
                    </div>
                    <span className={`${styles.dimVal} ${styles[scoreColor(val)]}`}>{formatScore(val)}</span>
                  </div>
                  {getScoreEvidence(val) && (
                    <p className={styles.dimEvidence}>{getScoreEvidence(val)}</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No analysis data available." />
          )}
        </div>
      )}

      {activeTab === 'reviews' && (
        <EmptyState
          icon={
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" width="40" height="40">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
            </svg>
          }
          title="Review History"
          message="Select a flag to contest it. Team leaders can accept or overturn contests."
        />
      )}

      {contestFlag && (
        <ContestModal
          flag={contestFlag}
          onClose={() => setContestFlag(null)}
          onSubmit={handleContestSubmit}
        />
      )}
    </div>
  )
}
