import { get, post } from './apiClient'

export function listCalls({ advisor_id, team_id, status, limit, offset } = {}) {
  const params = new URLSearchParams()
  if (advisor_id) params.set('advisor_id', advisor_id)
  if (team_id) params.set('team_id', team_id)
  if (status) params.set('status', status)
  if (limit) params.set('limit', limit)
  if (offset) params.set('offset', offset)
  const qs = params.toString()
  return get(`/api/calls${qs ? `?${qs}` : ''}`)
}

export function getCall(callId) {
  return get(`/api/calls/${callId}`)
}

export function uploadCall(file, advisorId) {
  const form = new FormData()
  form.append('file', file)
  const params = advisorId ? `?advisor_id=${advisorId}` : ''
  return post(`/api/calls/upload${params}`, form)
}
