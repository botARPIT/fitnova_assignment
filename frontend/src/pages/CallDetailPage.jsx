import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useCall } from '../hooks/useCall'
import ScoreGauge from '../components/common/ScoreGauge'
import FlagCard from '../components/common/FlagCard'
import TranscriptViewer from '../components/common/TranscriptViewer'
import ContestModal from '../components/common/ContestModal'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { buildApiUrl } from '../services/apiClient'
import { formatScore, formatTime, getScoreEvidence, getScoreVal, scoreColor } from '../utils/format'
import { contestFlag as contestFlagApi, listReviews, resolveReview } from '../services/reviews'
import styles from './CallDetailPage.module.css'

const TAG_META = {
  no_needs_discovery: {
    title: 'Needs Discovery Missing',
    summary: 'The advisor moved forward without understanding the customer context deeply enough.',
    dimension: 'needs_discovery',
    policies: [
      'Understand goals before pitching.',
      'Ask about routine, schedule, budget, and limitations.',
    ],
  },
  overpromising: {
    title: 'Overpromising / Guarantees',
    summary: 'The advisor made result-oriented claims that create compliance risk.',
    dimension: 'compliance',
    policies: [
      'Advisors must not guarantee exact weight loss, muscle gain, or timelines.',
      'Results vary by consistency, nutrition, sleep, and adherence.',
    ],
  },
  pressure_or_urgency_tactics: {
    title: 'Pressure / Urgency Tactics',
    summary: 'The advisor used urgency or pressure instead of guiding the customer toward a considered next step.',
    dimension: 'compliance',
    policies: [
      'Advisors must not use fake urgency such as "today only" or "last slot" unless true and approved.',
      'The goal is to book a free trial session, not force immediate payment.',
    ],
  },
  price_before_value: {
    title: 'Price Before Value',
    summary: 'Pricing came before enough value building or discovery, which weakens trust and lowers conversion quality.',
    dimension: 'needs_discovery',
    policies: [
      'Explain value before deep pricing discussion.',
      'Recommend a plan that matches the customer goals and constraints.',
    ],
  },
  undisclosed_costs: {
    title: 'Cost Transparency Issue',
    summary: 'The advisor created ambiguity around price or cost disclosure.',
    dimension: 'compliance',
    policies: [
      'Advisors must disclose costs honestly.',
      'Advisors must not invent hidden fees, discounts, or offers unless explicitly approved.',
    ],
  },
  weak_or_missing_trial_booking: {
    title: 'Weak Trial Booking',
    summary: 'The advisor did not confidently guide the call toward the expected free-trial next step.',
    dimension: 'next_step_booking',
    policies: [
      'Attempt to book a free trial session before ending the call.',
      'All plans include a 7-day free trial.',
    ],
  },
  talking_over_customer: {
    title: 'Talking Over Customer',
    summary: 'The call flow suggests the advisor did not create enough space for the customer to respond comfortably.',
    dimension: 'objection_handling',
    policies: [
      'Do needs discovery before pitching a plan.',
      'Handle objections by exploring the customer concern rather than overrunning it.',
    ],
  },
}

const DIMENSION_META = {
  needs_discovery: {
    title: 'Needs Discovery',
    emptyState: 'No discovery-related findings on this call.',
  },
  product_knowledge: {
    title: 'Product Knowledge',
    emptyState: 'No product-accuracy findings were surfaced for this call.',
  },
  objection_handling: {
    title: 'Objection Handling',
    emptyState: 'No objection-handling findings were surfaced for this call.',
  },
  compliance: {
    title: 'Compliance',
    emptyState: 'No compliance findings were surfaced for this call.',
  },
  next_step_booking: {
    title: 'Next Step Booking',
    emptyState: 'No booking-related findings were surfaced for this call.',
  },
}

const SEVERITY_ORDER = {
  critical: 3,
  major: 2,
  minor: 1,
}

const ADVISORS = [
  { id: '00000000-0000-0000-0000-000000000100', name: 'Saad Khan (Advisor)', role: 'advisor' },
  { id: '00000000-0000-0000-0000-000000000101', name: 'Rohan Mehta (Advisor)', role: 'advisor' },
  { id: '00000000-0000-0000-0000-000000000102', name: 'Priya Sharma (Team Leader)', role: 'team_leader' },
  { id: '00000000-0000-0000-0000-000000000103', name: 'Arjun Patel (Advisor)', role: 'advisor' },
  { id: '00000000-0000-0000-0000-000000000104', name: 'Neha Gupta (Team Leader)', role: 'team_leader' },
  { id: '00000000-0000-0000-0000-000000000105', name: 'Vikram Singh (Director)', role: 'director' },
]

function prettifyTag(tag = '') {
  return tag.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function getTagMeta(tag = '') {
  return TAG_META[tag] || {
    title: prettifyTag(tag),
    summary: 'Evidence-backed issue detected in the call review.',
    dimension: 'compliance',
    policies: [],
  }
}

function getHighestSeverity(items = []) {
  const selected = items.reduce((best, current) => {
    const currentRank = SEVERITY_ORDER[current?.severity] || 0
    const bestRank = SEVERITY_ORDER[best?.severity] || 0
    return currentRank > bestRank ? current : best
  }, items[0] || null)
  return selected?.severity || 'minor'
}

function buildGroupedFindings(flags = []) {
  const groups = new Map()

  flags.forEach((flag, index) => {
    const key = flag.tag || `unknown-${index}`
    const meta = getTagMeta(flag.tag)
    const existing = groups.get(key)

    if (existing) {
      existing.items.push(flag)
      existing.occurrences += 1
      existing.severity = getHighestSeverity(existing.items)
      existing.primaryFlag = [...existing.items].sort(
        (a, b) => (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0)
          || (a.timestamp ?? 0) - (b.timestamp ?? 0)
      )[0]
      return
    }

    groups.set(key, {
      key,
      tag: flag.tag,
      title: meta.title,
      summary: meta.summary,
      dimension: meta.dimension,
      policies: meta.policies,
      severity: flag.severity || 'minor',
      occurrences: 1,
      primaryFlag: flag,
      items: [flag],
    })
  })

  return [...groups.values()].sort(
    (a, b) => (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0)
      || (a.primaryFlag?.timestamp ?? 0) - (b.primaryFlag?.timestamp ?? 0)
  )
}

function buildTimelineItems(groups = []) {
  return groups
    .flatMap((group) =>
      group.items.map((item, occurrenceIndex) => ({
        ...item,
        timelineKey: `${group.key}-${occurrenceIndex}`,
        groupKey: group.key,
        groupTitle: group.title,
        groupSeverity: group.severity,
        groupSummary: group.summary,
      }))
    )
    .sort((a, b) => (a.timestamp ?? 0) - (b.timestamp ?? 0))
}

function getDimensionSummary(dim, score, relatedGroups) {
  const scoreValue = getScoreVal(score)
  const count = relatedGroups.length

  if (dim === 'needs_discovery') {
    return count > 0
      ? `${count} discovery-stage issue${count === 1 ? '' : 's'} affected the conversation flow.`
      : 'Discovery flow appears comparatively stable in this call.'
  }

  if (dim === 'compliance') {
    return count > 0
      ? `${count} compliance finding${count === 1 ? '' : 's'} require review.`
      : 'No active compliance findings surfaced.'
  }

  if (dim === 'next_step_booking') {
    return count > 0
      ? `${count} booking-related finding${count === 1 ? '' : 's'} blocked a strong close.`
      : 'No booking issues were surfaced.'
  }

  if (dim === 'objection_handling') {
    return count > 0
      ? `${count} objection-handling finding${count === 1 ? '' : 's'} impacted customer engagement.`
      : 'No objection-handling issues were surfaced.'
  }

  if (dim === 'product_knowledge') {
    if (count > 0) {
      return `${count} product or policy accuracy finding${count === 1 ? '' : 's'} were surfaced.`
    }
    if (scoreValue != null && scoreValue >= 3) {
      return 'No active product-accuracy issues were surfaced.'
    }
    return 'Score is low, but current findings do not break product accuracy into structured subtypes.'
  }

  return count > 0 ? `${count} linked finding${count === 1 ? '' : 's'}.` : 'No linked findings.'
}

function ReviewCard({ review, actingAdvisorId, onResolve }) {
  const [decision, setDecision] = useState('accepted')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!actingAdvisorId) {
      setError('Please select an acting advisor in the header first.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await onResolve(review.id, decision, reason)
      setReason('')
    } catch (e) {
      setError(e.detail || e.message || 'Failed to resolve review')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.reviewCard}>
      <div className={styles.reviewHeader}>
        <div className={styles.reviewMeta}>
          <span className={styles.reviewTitle}>Flag Review</span>
          <span className={styles.reviewSubtitle}>Flag ID: {review.flag_id}</span>
        </div>
        <span className={`${styles.reviewBadge} ${
          review.status === 'PENDING'
            ? styles.pendingBadge
            : review.status === 'ACCEPTED'
              ? styles.acceptedBadge
              : styles.overturnedBadge
        }`}>
          {review.status}
        </span>
      </div>

      <div className={styles.reviewContent}>
        <div className={styles.reviewField}>
          <span className={styles.fieldLabel}>Contested By (Advisor):</span>
          <span className={styles.fieldValue}>{review.advisor_id}</span>
        </div>
        <div className={styles.reviewField}>
          <span className={styles.fieldLabel}>Contest Reason:</span>
          <span className={styles.fieldValue}>{review.contest_reason}</span>
        </div>
        {review.status !== 'PENDING' && (
          <>
            <div className={styles.reviewField}>
              <span className={styles.fieldLabel}>Resolved By (Team Leader):</span>
              <span className={styles.fieldValue}>{review.team_leader_id}</span>
            </div>
            <div className={styles.reviewField}>
              <span className={styles.fieldLabel}>Decision Reason:</span>
              <span className={styles.fieldValue}>{review.decision_reason || 'No reason provided'}</span>
            </div>
          </>
        )}
      </div>

      {review.status === 'PENDING' && (
        <form className={styles.resolveForm} onSubmit={handleSubmit}>
          <h4 className={styles.resolveTitle}>Resolve Contest</h4>
          <div className={styles.formGrid}>
            <div className={styles.formField}>
              <label>Decision</label>
              <select value={decision} onChange={e => setDecision(e.target.value)}>
                <option value="accepted">Accept (Keep Flag)</option>
                <option value="overturned">Overturn (Remove Flag)</option>
              </select>
            </div>
            <div className={styles.formField}>
              <label>Reason (Optional)</label>
              <textarea
                placeholder="Provide details about your decision..."
                value={reason}
                onChange={e => setReason(e.target.value)}
              />
            </div>
          </div>
          <div className={styles.resolveActions}>
            {error && <span className={styles.resolveError}>{error}</span>}
            <button
              type="submit"
              className={styles.resolveBtn}
              disabled={submitting}
            >
              {submitting ? 'Resolving...' : 'Submit Decision'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

export default function CallDetailPage() {
  const { callId } = useParams()
  const { call, loading, error, refetch } = useCall(callId)
  const [activeTab, setActiveTab] = useState('overview')
  const [highlightQuote, setHighlightQuote] = useState(null)
  const [contestFlag, setContestFlag] = useState(null)
  const [contestMsg, setContestMsg] = useState(null)
  const [focusTurnIndex, setFocusTurnIndex] = useState(null)

  const [reviews, setReviews] = useState([])
  const [reviewsLoading, setReviewsLoading] = useState(false)
  const [reviewsError, setReviewsError] = useState(null)
  const [actingAdvisorId, setActingAdvisorId] = useState('')

  const fetchReviews = useCallback(async () => {
    setReviewsLoading(true)
    setReviewsError(null)
    try {
      const data = await listReviews(callId)
      setReviews(data.reviews || [])
    } catch (e) {
      setReviewsError(e.detail || e.message || 'Failed to load reviews')
    } finally {
      setReviewsLoading(false)
    }
  }, [callId])

  useEffect(() => {
    if (callId) {
      fetchReviews()
    }
  }, [callId, fetchReviews])

  // Pre-load sensible default actor from call's advisor_id
  useEffect(() => {
    if (call && call.advisor_id && !actingAdvisorId) {
      setActingAdvisorId(call.advisor_id)
    }
  }, [call, actingAdvisorId])

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
  const flags = call.effective_flags || call.flags || []
  const discardedFlags = call.discarded_flags || []
  const turns = call.turns || []
  const audioUrl = buildApiUrl(`/api/calls/${callId}/audio`)
  const transcriptSourceLabel = call.transcript_source === 'gemini_corrected'
    ? 'Speaker labels: LLM-corrected'
    : 'Speaker labels: STT raw fallback'
  const groupedFindings = buildGroupedFindings(flags)
  const timelineItems = buildTimelineItems(groupedFindings)
  const groupedByDimension = Object.keys(DIMENSION_META).reduce((acc, key) => {
    acc[key] = groupedFindings.filter((group) => group.dimension === key)
    return acc
  }, {})

  const handleContest = async (flag) => {
    setContestFlag(flag)
    setContestMsg(null)
  }

  const handleContestSubmit = async (reason) => {
    if (!actingAdvisorId) {
      setContestMsg('Error: Please select an acting advisor first.')
      setContestFlag(null)
      return
    }
    try {
      await contestFlagApi(callId, contestFlag.flag_id, reason, actingAdvisorId)
      setContestMsg('Flag contested successfully.')
      setContestFlag(null)
      await refetch()
      await fetchReviews()
    } catch (e) {
      setContestMsg(`Error: ${e.detail || e.message}`)
      setContestFlag(null)
    }
  }

  const handleResolveReview = async (reviewId, decision, decisionReason) => {
    if (!actingAdvisorId) {
      throw new Error('Please select an acting advisor first.')
    }
    await resolveReview(reviewId, decision, decisionReason, actingAdvisorId)
    setContestMsg('Review resolved successfully.')
    await refetch()
    await fetchReviews()
  }

  const handleQuoteClick = (flag) => {
    setHighlightQuote(flag.quoted_line || flag.quote || null)
    setFocusTurnIndex(typeof flag.matched_turn_index === 'number' ? flag.matched_turn_index : null)
    setActiveTab('transcript')
  }

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'transcript', label: 'Transcript' },
    { key: 'timeline', label: 'Timeline' },
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
        <div className={styles.headerControls}>
          <div className={styles.actorSelector}>
            <label htmlFor="acting-advisor">Acting As:</label>
            <select
              id="acting-advisor"
              value={actingAdvisorId}
              onChange={(e) => setActingAdvisorId(e.target.value)}
            >
              <option value="">Select Actor...</option>
              {ADVISORS.map((advisor) => (
                <option key={advisor.id} value={advisor.id}>
                  {advisor.name}
                </option>
              ))}
            </select>
          </div>
          <div className={styles.meta}>
            {call.duration_sec && (
              <span className={styles.metaItem}>⏱ {formatTime(call.duration_sec)}</span>
            )}
            <span className={`${styles.metaItem} ${styles[call.status]}`}>{call.status}</span>
          </div>
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

      <div className={styles.audioSection}>
        <div className={styles.audioCard}>
          <div className={styles.audioHeader}>
            <div>
              <h2 className={styles.audioTitle}>Call Recording</h2>
              <p className={styles.audioSubtitle}>Listen alongside the transcript and flags.</p>
            </div>
          </div>
          <audio className={styles.audioPlayer} controls preload="none" src={audioUrl}>
            Your browser does not support audio playback.
          </audio>
        </div>
      </div>

      {contestMsg && (
        <div className={styles.contestMsg}>{contestMsg}</div>
      )}

      {activeTab === 'overview' && (
        <div className={styles.overview}>
          <div className={styles.scoreOverviewGrid}>
            <div className={styles.scoreSummaryCard}>
              <ScoreGauge value={call.overall_score} size="lg" label="Overall Score" />
              <p className={styles.scoreSummaryText}>
                {groupedFindings.length > 0
                  ? `${groupedFindings.length} grouped finding${groupedFindings.length === 1 ? '' : 's'} across ${flags.length} occurrence${flags.length === 1 ? '' : 's'}.`
                  : 'No active findings surfaced for this call.'}
              </p>
            </div>
            {Object.entries(scores).map(([dim, val]) => (
              <div key={dim} className={styles.scoreSummaryCard}>
                <ScoreGauge value={val} label={DIMENSION_META[dim]?.title || dim.replace(/_/g, ' ')} />
                <p className={styles.scoreSummaryText}>
                  {getDimensionSummary(dim, val, groupedByDimension[dim] || [])}
                </p>
              </div>
            ))}
          </div>

          <div className={styles.flagsSection}>
            <h2 className={styles.sectionTitle}>Grouped Findings ({groupedFindings.length})</h2>
            {groupedFindings.length > 0 ? (
              <div className={styles.groupedFindings}>
                {groupedFindings.map((group) => (
                  <article key={group.key} className={styles.groupCard}>
                    <div className={styles.groupHeader}>
                      <div>
                        <h3 className={styles.groupTitle}>{group.title}</h3>
                        <p className={styles.groupSummary}>{group.summary}</p>
                      </div>
                      <div className={styles.groupBadges}>
                        <span className={`${styles.groupSeverity} ${styles[group.severity]}`}>{group.severity}</span>
                        <span className={styles.groupOccurrence}>
                          {group.occurrences} occurrence{group.occurrences === 1 ? '' : 's'}
                        </span>
                      </div>
                    </div>

                    {group.policies.length > 0 && (
                      <div className={styles.policyBlock}>
                        <span className={styles.policyTitle}>Policy context</span>
                        <ul className={styles.policyList}>
                          {group.policies.map((policy) => (
                            <li key={policy}>{policy}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div className={styles.evidenceList}>
                      {group.items.map((flag, index) => (
                        <button
                          key={`${group.key}-${index}`}
                          className={styles.evidenceItem}
                          onClick={() => handleQuoteClick(flag)}
                        >
                          <div className={styles.evidenceHeader}>
                            <span className={styles.evidenceIndex}>Evidence {index + 1}</span>
                            <span className={styles.evidenceTime}>{formatTime(flag.timestamp)}</span>
                          </div>
                          <div className={styles.evidenceQuote}>&ldquo;{flag.quoted_line || flag.quote}&rdquo;</div>
                          <div className={styles.evidenceReason}>{flag.reason || flag.explanation}</div>
                        </button>
                      ))}
                    </div>

                    <div className={styles.groupFooter}>
                      <span className={styles.groupFooterText}>
                        Linked to {DIMENSION_META[group.dimension]?.title || group.dimension.replace(/_/g, ' ')}
                      </span>
                      {group.primaryFlag && (!group.primaryFlag.status || group.primaryFlag.status === 'ACTIVE') && (
                        <button className={styles.groupContestBtn} onClick={() => handleContest(group.primaryFlag)}>
                          Contest Issue
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState message="No active findings on this call." />
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
        <div className={styles.transcriptSection}>
          <div className={styles.transcriptMeta}>
            <span className={styles.transcriptBadge}>{transcriptSourceLabel}</span>
          </div>
          <TranscriptViewer
            turns={turns}
            highlightQuote={highlightQuote}
            focusTurnIndex={focusTurnIndex}
          />
        </div>
      )}

      {activeTab === 'timeline' && (
        <div className={styles.timeline}>
          {timelineItems.length > 0 ? (
            timelineItems.map((item) => (
              <button
                key={item.timelineKey}
                className={styles.timelineItem}
                onClick={() => handleQuoteClick(item)}
              >
                <div className={styles.timelineRail}>
                  <span className={styles.timelineDot} />
                </div>
                <div className={styles.timelineContent}>
                  <div className={styles.timelineHeader}>
                    <span className={styles.timelineTime}>{formatTime(item.timestamp)}</span>
                    <span className={`${styles.timelineSeverity} ${styles[item.severity]}`}>{item.severity}</span>
                  </div>
                  <h3 className={styles.timelineTitle}>{item.groupTitle}</h3>
                  <p className={styles.timelineReason}>{item.reason || item.explanation}</p>
                  <p className={styles.timelineQuote}>&ldquo;{item.quoted_line || item.quote}&rdquo;</p>
                </div>
              </button>
            ))
          ) : (
            <EmptyState message="No issues to place on the call timeline." />
          )}
        </div>
      )}

      {activeTab === 'analysis' && (
        <div className={styles.analysis}>
          {Object.entries(scores).length > 0 ? (
            <div className={styles.dimensionCards}>
              {Object.entries(scores).map(([dim, val]) => {
                const relatedGroups = groupedByDimension[dim] || []
                return (
                  <div key={dim} className={styles.dimensionCard}>
                    <div className={styles.dimRow}>
                      <span className={styles.dimLabel}>{DIMENSION_META[dim]?.title || dim.replace(/_/g, ' ')}</span>
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
                      <span className={`${styles.dimVal} ${styles[scoreColor(val)]}`}>{formatScore(val)} / 5</span>
                    </div>
                    <p className={styles.dimensionSummary}>{getDimensionSummary(dim, val, relatedGroups)}</p>
                    {getScoreEvidence(val) && (
                      <p className={styles.dimEvidence}>{getScoreEvidence(val)}</p>
                    )}

                    {relatedGroups.length > 0 ? (
                      <div className={styles.relatedIssues}>
                        <span className={styles.relatedTitle}>Related findings</span>
                        <div className={styles.relatedIssueList}>
                          {relatedGroups.map((group) => (
                            <button
                              key={`${dim}-${group.key}`}
                              className={styles.relatedIssue}
                              onClick={() => handleQuoteClick(group.primaryFlag)}
                            >
                              <span>{group.title}</span>
                              <span className={styles.relatedMeta}>{group.occurrences} item{group.occurrences === 1 ? '' : 's'}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className={styles.analysisEmpty}>{DIMENSION_META[dim]?.emptyState}</p>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <EmptyState message="No analysis data available." />
          )}
        </div>
      )}

      {activeTab === 'reviews' && (
        <div className={styles.reviewsList}>
          {reviewsLoading ? (
            <LoadingSkeleton count={2} />
          ) : reviewsError ? (
            <ErrorState message={reviewsError} onRetry={fetchReviews} />
          ) : reviews.length > 0 ? (
            reviews.map((review) => (
              <ReviewCard
                key={review.id}
                review={review}
                actingAdvisorId={actingAdvisorId}
                onResolve={handleResolveReview}
              />
            ))
          ) : (
            <EmptyState
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" width="40" height="40">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 0 1-1.043 3.296 3.745 3.745 0 0 1-3.296 1.043A3.745 3.745 0 0 1 12 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 0 1-3.296-1.043 3.745 3.745 0 0 1-1.043-3.296A3.745 3.745 0 0 1 3 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 0 1 1.043-3.296 3.746 3.746 0 0 1 3.296-1.043A3.746 3.746 0 0 1 12 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 0 1 3.296 1.043 3.746 3.746 0 0 1 1.043 3.296A3.745 3.745 0 0 1 21 12Z" />
                </svg>
              }
              title="No Review History"
              message="Select a flag under the overview tab to contest it. Team leaders can accept or overturn contests here."
            />
          )}
        </div>
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
