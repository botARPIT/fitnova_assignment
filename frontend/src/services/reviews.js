import { get, post, patch } from './apiClient'

export function contestFlag(callId, { flag_index, reason, reviewer_id }) {
  return post(`/api/calls/${callId}/contest-flag`, { flag_index, reason, reviewer_id })
}

export function resolveReview(callId, reviewId, decision) {
  return patch(`/api/calls/${callId}/reviews/${reviewId}`, { decision })
}

export function listReviews(callId) {
  return get(`/api/calls/${callId}/reviews`)
}
