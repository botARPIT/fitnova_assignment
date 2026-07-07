import { useState, useEffect, useCallback } from 'react'
import { listCalls as listCallsApi } from '../services/calls'

export function useCalls({ advisor_id, team_id, status, limit = 50, offset = 0 } = {}) {
  const [calls, setCalls] = useState([])
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listCallsApi({ advisor_id, team_id, status, limit, offset })
      setCalls(data.calls || [])
      setCount(data.count || 0)
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [advisor_id, team_id, status, limit, offset])

  useEffect(() => { fetch() }, [fetch])

  return { calls, count, loading, error, refetch: fetch }
}
