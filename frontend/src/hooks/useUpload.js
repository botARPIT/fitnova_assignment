import { useState, useCallback } from 'react'
import { uploadCall } from '../services/calls'

export function useUpload() {
  const [stage, setStage] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(0)

  const upload = useCallback(async (file, advisorId) => {
    setError(null)
    setResult(null)
    setStage('uploading')
    setProgress(20)

    try {
      setStage('processing')
      setProgress(50)

      const data = await uploadCall(file, advisorId)

      setStage('analyzing')
      setProgress(75)

      setTimeout(() => {
        setStage('completed')
        setProgress(100)
        setResult(data)
      }, 500)
    } catch (e) {
      setError(e.detail || e.message)
      setStage(null)
      setProgress(0)
    }
  }, [])

  const reset = useCallback(() => {
    setStage(null)
    setResult(null)
    setError(null)
    setProgress(0)
  }, [])

  return { stage, result, error, progress, upload, reset }
}
