import { useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUpload } from '../hooks/useUpload'
import { useTeams, useAdvisors } from '../hooks/useTeams'
import ProgressIndicator from '../components/common/ProgressIndicator'
import ErrorState from '../components/common/ErrorState'
import { formatBytes } from '../utils/format'
import styles from './UploadPage.module.css'

export default function UploadPage() {
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedTeamId, setSelectedTeamId] = useState('')
  const [selectedAdvisorId, setSelectedAdvisorId] = useState('')
  const inputRef = useRef(null)
  const navigate = useNavigate()
  const { stage, result, error, upload, reset } = useUpload()
  const { teams, loading: teamsLoading, error: teamsError } = useTeams()
  const { advisors, loading: advisorsLoading, error: advisorsError } = useAdvisors(selectedTeamId)

  const handleFile = useCallback((f) => {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!['wav', 'mp3', 'm4a'].includes(ext)) return
    setFile(f)
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  const handleUpload = async () => {
    if (!file || !selectedTeamId || !selectedAdvisorId) return
    await upload(file, selectedAdvisorId)
  }

  const handleViewCall = () => {
    if (result?.call_id) {
      navigate(`/calls/${result.call_id}`)
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Upload Call</h1>

      {error && (
        <div className={styles.errorBanner}>
          <ErrorState message={error} onRetry={reset} />
        </div>
      )}

      {stage ? (
        <div className={styles.progressSection}>
          <ProgressIndicator currentStage={stage} />

          <p className={styles.progressText}>
            {stage === 'uploading' && 'Uploading audio file...'}
            {stage === 'processing' && 'Backend is processing the call. This currently includes transcribing, speaker repair, and flagging.'}
            {stage === 'completed' && 'Analysis complete!'}
          </p>
          {stage && stage !== 'completed' && (
            <div className={styles.stageHint}>
              Current backend state: <strong>{stage.replace(/_/g, ' ')}</strong>
            </div>
          )}
          {stage === 'completed' && result && (
            <div className={styles.resultSection}>
              <div className={styles.resultInfo}>
                <span>Overall Score: <strong>{result.overall_score?.toFixed(1)}</strong></span>
                <span>Flags: <strong>{result.flags?.length || 0}</strong></span>
                {result.idempotent_reuse && (
                  <span>Result: <strong>Reused previous analysis</strong></span>
                )}
              </div>
              <div className={styles.resultActions}>
                <button className={styles.primaryBtn} onClick={handleViewCall}>
                  View Call Detail
                </button>
                <button className={styles.secondaryBtn} onClick={reset}>
                  Upload Another
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <>
          <div className={styles.runtimeNote}>
            <span className={styles.runtimeBadge}>Active Pipeline</span>
            <p>
              Uploads run through the current production path:
              <strong> STT transcription</strong>, <strong>LLM speaker repair</strong>,
              and <strong>LLM quality analysis + flagging</strong>.
            </p>
          </div>

          <div
            className={`${styles.dropZone} ${dragOver ? styles.dragOver : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" width="48" height="48">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p><strong>Click to upload</strong> or drag and drop</p>
            <p className={styles.formats}>WAV, MP3, M4A — minimum 10 seconds</p>
            <input
              ref={inputRef}
              type="file"
              accept=".wav,.mp3,.m4a"
              hidden
              onChange={(e) => handleFile(e.target.files[0])}
            />
          </div>

          {file && (
            <div className={styles.fileInfo}>
              <div className={styles.fileIcon}>
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" width="18" height="18">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
                </svg>
              </div>
              <div className={styles.fileDetails}>
                <div className={styles.fileName}>{file.name}</div>
                <div className={styles.fileSize}>{formatBytes(file.size)}</div>
              </div>
              <button className={styles.removeBtn} onClick={() => { setFile(null); reset() }}>✕</button>
            </div>
          )}

          <div className={styles.assignmentSection}>
            <div className={styles.assignmentHeader}>
              <h2 className={styles.assignmentTitle}>Assign Recording</h2>
              <p className={styles.assignmentHint}>
                Choose the team first, then the advisor. Upload stays disabled until both are selected.
              </p>
            </div>

            {(teamsError || advisorsError) && (
              <div className={styles.selectorError}>
                {teamsError || advisorsError}
              </div>
            )}

            <div className={styles.selectorGrid}>
              <div className={styles.selectorField}>
                <label htmlFor="team-select">Team</label>
                <select
                  id="team-select"
                  className={styles.selectInput}
                  value={selectedTeamId}
                  onChange={(e) => {
                    setSelectedTeamId(e.target.value)
                    setSelectedAdvisorId('')
                  }}
                  disabled={teamsLoading}
                >
                  <option value="">
                    {teamsLoading ? 'Loading teams...' : 'Select team'}
                  </option>
                  {teams.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className={styles.selectorField}>
                <label htmlFor="advisor-select">Advisor</label>
                <select
                  id="advisor-select"
                  className={styles.selectInput}
                  value={selectedAdvisorId}
                  onChange={(e) => setSelectedAdvisorId(e.target.value)}
                  disabled={!selectedTeamId || advisorsLoading}
                >
                  <option value="">
                    {!selectedTeamId
                      ? 'Select team first'
                      : advisorsLoading
                        ? 'Loading advisors...'
                        : 'Select advisor'}
                  </option>
                  {advisors.map((advisor) => (
                    <option key={advisor.id} value={advisor.id}>
                      {advisor.name}{advisor.role ? ` (${advisor.role})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className={styles.actions}>
            <button
              className={styles.primaryBtn}
              disabled={!file || !selectedTeamId || !selectedAdvisorId}
              onClick={handleUpload}
            >
              Upload & Analyze
            </button>
          </div>
        </>
      )}
    </div>
  )
}
