import { useState, useEffect, useCallback } from 'react'
import { getOverview, getTeamStats, getAdvisorStats } from '../services/analytics'

export function useAnalytics() {
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getOverview()
      setOverview(data)
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { overview, loading, error, refetch: fetch }
}

export function useTeamAnalytics(teamId) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(!!teamId)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!teamId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getTeamStats(teamId)
      setStats(data)
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [teamId])

  useEffect(() => { fetch() }, [fetch])

  return { stats, loading, error, refetch: fetch }
}

export function useAdvisorAnalytics(advisorId) {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(!!advisorId)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!advisorId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getAdvisorStats(advisorId)
      setStats(data)
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [advisorId])

  useEffect(() => { fetch() }, [fetch])

  return { stats, loading, error, refetch: fetch }
}
