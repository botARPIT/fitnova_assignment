import { get } from './apiClient'

function normalizeOverview(data) {
  const summary = data?.summary || {}
  return {
    ...data,
    summary,
    total_calls: summary.total_calls ?? 0,
    completed_calls: summary.completed_calls ?? 0,
    failed_calls: summary.failed_calls ?? 0,
    avg_score: summary.avg_score ?? 0,
    active_advisors: summary.active_advisors ?? 0,
    top_flags: data?.top_flags || [],
    objective_metrics: data?.objective_metrics || {},
    score_trend: data?.score_trend || [],
  }
}

function normalizeTeamAnalytics(data) {
  return {
    ...data,
    advisors: data?.advisor_leaderboard || [],
    flags: data?.coaching_opportunities || [],
    advisor_leaderboard: data?.advisor_leaderboard || [],
    coaching_opportunities: data?.coaching_opportunities || [],
    score_trend: data?.score_trend || [],
  }
}

function normalizeAdvisorAnalytics(data) {
  return {
    ...data,
    summary: data?.summary || {},
    recent_calls: data?.recent_calls || [],
    flag_frequency: data?.flag_frequency || [],
    flags: data?.flag_frequency || [],
    coaching_opportunities: data?.coaching_opportunities || [],
    score_trend: data?.score_trend || [],
  }
}

export function getOverview() {
  return get('/api/analytics/overview').then(normalizeOverview)
}

export function getTeamStats(teamId) {
  return get(`/api/analytics/teams/${teamId}`).then(normalizeTeamAnalytics)
}

export function getAdvisorStats(advisorId) {
  return get(`/api/analytics/advisors/${advisorId}`).then(normalizeAdvisorAnalytics)
}
