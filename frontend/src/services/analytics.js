import { get } from './apiClient'

export function getOverview() {
  return get('/api/analytics/overview')
}

export function getTeamStats(teamId) {
  return get(`/api/analytics/teams/${teamId}`)
}

export function getAdvisorStats(advisorId) {
  return get(`/api/analytics/advisors/${advisorId}`)
}
