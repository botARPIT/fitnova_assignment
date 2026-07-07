import { useState, useEffect, useCallback } from 'react'
import { listTeams, listAdvisors } from '../services/org'

export function useTeams() {
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listTeams()
      setTeams(data.teams || [])
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetch() }, [fetch])

  return { teams, loading, error, refetch: fetch }
}

export function useAdvisors(teamId) {
  const [advisors, setAdvisors] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listAdvisors(teamId)
      setAdvisors(data.advisors || [])
    } catch (e) {
      setError(e.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [teamId])

  useEffect(() => { fetch() }, [fetch])

  return { advisors, loading, error, refetch: fetch }
}
