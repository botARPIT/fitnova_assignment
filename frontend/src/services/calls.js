import { get, post } from './apiClient'

function normalizeTurns(transcript) {
  if (Array.isArray(transcript)) return transcript
  if (transcript && Array.isArray(transcript.turns)) return transcript.turns
  return []
}

function normalizeFlag(flag = {}) {
  const quotedLine = flag.quoted_line ?? flag.quote ?? ''
  const reason = flag.reason ?? flag.explanation ?? ''

  return {
    ...flag,
    quoted_line: quotedLine,
    quote: flag.quote ?? quotedLine,
    reason,
    explanation: flag.explanation ?? reason,
  }
}

export function normalizeCallDetail(call) {
  if (!call || typeof call !== 'object') return call

  const diarizedTurns = normalizeTurns(call.diarized_transcript)
  const rawTurns = normalizeTurns(call.raw_transcript)

  return {
    ...call,
    raw_transcript: rawTurns,
    diarized_transcript: diarizedTurns,
    turns: diarizedTurns.length > 0 ? diarizedTurns : rawTurns,
    transcript_source: diarizedTurns.length > 0 ? 'gemini_corrected' : 'deepgram_raw',
    flags: Array.isArray(call.flags) ? call.flags.map(normalizeFlag) : [],
    discarded_flags: Array.isArray(call.discarded_flags)
      ? call.discarded_flags.map(normalizeFlag)
      : [],
    effective_flags: Array.isArray(call.effective_flags)
      ? call.effective_flags.map(normalizeFlag)
      : [],
  }
}

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
  return get(`/api/calls/${callId}`).then(normalizeCallDetail)
}

export function getCallStatus(callId) {
  return get(`/api/calls/${callId}/status`)
}

export function uploadCall(file, advisorId) {
  const form = new FormData()
  form.append('file', file)
  const params = advisorId ? `?advisor_id=${advisorId}` : ''
  return post(`/api/calls/upload${params}`, form)
}
