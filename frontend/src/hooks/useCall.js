import { useState, useEffect, useCallback } from 'react'
import { getCall } from '../services/calls'

export function useCall(callId) {
  const [call, setCall] = useState(null)
  const [loading, setLoading] = useState(!!callId)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!callId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getCall(callId)
      setCall(data)
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [callId])

  useEffect(() => { fetch() }, [fetch])

  return { call, loading, error, refetch: fetch }
}
