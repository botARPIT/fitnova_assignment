import { useState, useCallback } from 'react'
import { uploadCall } from '../services/calls'

export function useUpload() {
  const [stage, setStage] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const upload = useCallback(async (file, advisorId) => {
    setError(null)
    setResult(null)
    setStage('uploading')

    try {
      // The backend handles the full pipeline inside one blocking request and
      // does not stream internal milestones, so keep a single honest in-flight
      // state instead of simulating stage completion with timers.
      setStage('processing')
      const data = await uploadCall(file, advisorId)
      setStage('completed')
      setResult(data)
    } catch (e) {
      setError(e.detail || e.message)
      setStage(null)
    }
  }, [])

  const reset = useCallback(() => {
    setStage(null)
    setResult(null)
    setError(null)
  }, [])

  return { stage, result, error, upload, reset }
}
