import { useState, useCallback, useRef, useEffect } from 'react'
import { uploadCall, getCallStatus, getCall } from '../services/calls'

const POLL_INTERVAL_MS = 2000
const MAX_POLL_TIME_MS = 600_000

export function useUpload() {
  const [stage, setStage] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const pollingRef = useRef(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    return () => {
      cancelledRef.current = true
      if (pollingRef.current) clearTimeout(pollingRef.current)
    }
  }, [])

  const startPolling = useCallback(async (callId) => {
    const startedAt = Date.now()

    const poll = async () => {
      if (cancelledRef.current) return

      try {
        const status = await getCallStatus(callId)
        if (cancelledRef.current) return

        if (status.status === 'completed') {
          const detail = await getCall(callId)
          if (!cancelledRef.current) {
            setStage('completed')
            setResult(detail)
          }
          return
        }

        if (status.status === 'failed') {
          if (!cancelledRef.current) {
            const msg = status.error_message || `Pipeline failed at stage: ${status.failed_stage || 'unknown'}`
            setError(msg)
            setStage(null)
          }
          return
        }

        if (Date.now() - startedAt >= MAX_POLL_TIME_MS) {
          if (!cancelledRef.current) {
            setError('Upload timed out after 10 minutes.')
            setStage(null)
          }
          return
        }

        pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS)
      } catch (e) {
        if (!cancelledRef.current) {
          setError(e.detail || e.message)
          setStage(null)
        }
      }
    }

    await poll()
  }, [])

  const upload = useCallback(async (file, advisorId) => {
    cancelledRef.current = false
    setError(null)
    setResult(null)
    setStage('uploading')

    try {
      setStage('processing')
      const data = await uploadCall(file, advisorId)

      if (data.status === 'completed') {
        setStage('completed')
        setResult(data)
        return
      }

      if (data.status === 'processing') {
        await startPolling(data.call_id)
        return
      }

      setStage('completed')
      setResult(data)
    } catch (e) {
      const detail = e.detail
      if (detail && detail.status === 'processing' && detail.call_id) {
        setStage('processing')
        await startPolling(detail.call_id)
        return
      }
      setError(typeof detail === 'string' ? detail : detail?.detail || e.message)
      setStage(null)
    }
  }, [startPolling])

  const reset = useCallback(() => {
    cancelledRef.current = true
    if (pollingRef.current) {
      clearTimeout(pollingRef.current)
      pollingRef.current = null
    }
    setStage(null)
    setResult(null)
    setError(null)
  }, [])

  return { stage, result, error, upload, reset }
}
