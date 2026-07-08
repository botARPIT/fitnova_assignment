import { get, post } from './apiClient'

export function contestFlag(callId, flagId, contestReason, advisorId) {
  return post(
    `/api/calls/${callId}/flags/${flagId}/contest`,
    { contest_reason: contestReason },
    { headers: { 'X-Advisor-ID': advisorId } }
  )
}

export function resolveReview(reviewId, decision, decisionReason, advisorId) {
  return post(
    `/api/reviews/${reviewId}/decision`,
    { decision, decision_reason: decisionReason },
    { headers: { 'X-Advisor-ID': advisorId } }
  )
}

export function listReviews(callId) {
  return get(`/api/calls/${callId}/reviews`)
}

export function listPendingReviews() {
  return get('/api/reviews/pending')
}
