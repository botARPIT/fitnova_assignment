import { get } from './apiClient'

export function listTeams() {
  return get('/api/org/teams')
}

export function listAdvisors(teamId) {
  const params = teamId ? `?team_id=${teamId}` : ''
  return get(`/api/org/advisors${params}`)
}
