import { useState, useRef, useCallback } from 'react'
import './App.css'

const API = 'http://localhost:8000'

function formatTime(sec) {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function scoreColor(val, max = 5) {
  const pct = val / max
  if (pct >= 0.7) return 'score-high'
  if (pct >= 0.4) return 'score-mid'
  return 'score-low'
}

/* ── Icons (inline SVG) ────────────────────────────────────── */
const UploadIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
  </svg>
)

const AudioIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
  </svg>
)

const ENGINE_OPTIONS = [
  { value: 'deepgram', label: 'Deepgram Nova-2', desc: 'Cloud API • Fast • Phone-optimized', icon: '☁️' },
  { value: 'whisperx', label: 'WhisperX + Pyannote', desc: 'Local GPU • Better diarization', icon: '🖥️' },
]


export default function App() {
  /* ── state ───────────────────────────────────────────────── */
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [transcript, setTranscript] = useState(null)
  const [flagging, setFlagging] = useState(false)
  const [flagResult, setFlagResult] = useState(null)
  const [error, setError] = useState(null)
  const [engine, setEngine] = useState('deepgram')
  const inputRef = useRef(null)

  /* ── file handlers ───────────────────────────────────────── */
  const handleFile = useCallback((f) => {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!['wav', 'mp3', 'm4a'].includes(ext)) {
      setError(`Unsupported format ".${ext}". Use wav, mp3, or m4a.`)
      return
    }
    setFile(f)
    setError(null)
    setTranscript(null)
    setFlagResult(null)
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  /* ── transcribe ──────────────────────────────────────────── */
  const doTranscribe = async () => {
    if (!file) return
    setTranscribing(true)
    setError(null)
    setTranscript(null)
    setFlagResult(null)

    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/transcribe?engine=${engine}`, { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setTranscript(data)
    } catch (e) {
      setError(`Transcription failed: ${e.message}`)
    } finally {
      setTranscribing(false)
    }
  }

  /* ── flag ─────────────────────────────────────────────────── */
  const doFlag = async () => {
    if (!transcript) return
    setFlagging(true)
    setError(null)
    setFlagResult(null)

    try {
      const res = await fetch(`${API}/flag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_id: transcript.call_id }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setFlagResult(data)
    } catch (e) {
      setError(`Flagging failed: ${e.message}`)
    } finally {
      setFlagging(false)
    }
  }

  /* ── render ──────────────────────────────────────────────── */
  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <h1>🏋️ <span>FitNova</span> Call Intelligence</h1>
        <p>Upload a sales call → Transcribe → Analyze quality & compliance</p>
      </header>

      <main className="app-main">
        <div className="pipeline">

          {/* ── Step 1: Upload & Transcribe ─────────────────── */}
          <section className="step-card">
            <div className="step-header">
              <div className="step-number">1</div>
              <h2>Upload & Transcribe <small>POST /transcribe</small></h2>
            </div>
            <div className="step-body">

              {/* Engine selector */}
              <div className="engine-selector">
                <label className="engine-label">STT Engine</label>
                <div className="engine-options">
                  {ENGINE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      className={`engine-btn ${engine === opt.value ? 'active' : ''}`}
                      onClick={() => setEngine(opt.value)}
                      disabled={transcribing}
                    >
                      <span className="engine-icon">{opt.icon}</span>
                      <div className="engine-text">
                        <strong>{opt.label}</strong>
                        <small>{opt.desc}</small>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Drop zone */}
              <div
                className={`upload-zone ${dragOver ? 'drag-over' : ''}`}
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
              >
                <UploadIcon />
                <p><strong>Click to upload</strong> or drag and drop</p>
                <p className="formats">WAV, MP3, M4A — minimum 10 seconds</p>
                <input
                  ref={inputRef}
                  type="file"
                  accept=".wav,.mp3,.m4a"
                  hidden
                  onChange={(e) => handleFile(e.target.files[0])}
                />
              </div>

              {/* Selected file */}
              {file && (
                <div className="file-selected">
                  <div className="file-icon"><AudioIcon /></div>
                  <div className="file-info">
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{formatBytes(file.size)}</div>
                  </div>
                  <button className="remove-btn" onClick={() => { setFile(null); setTranscript(null); setFlagResult(null) }}>✕</button>
                </div>
              )}

              {/* Actions */}
              <div className="btn-row">
                <button
                  className="btn btn-primary"
                  disabled={!file || transcribing}
                  onClick={doTranscribe}
                >
                  {transcribing ? <><span className="spinner" /> Transcribing…</> : '▶ Transcribe'}
                </button>
              </div>

              {/* Loading */}
              {transcribing && (
                <>
                  <div className="loading-bar"><div className="progress" style={{ width: '100%' }} /></div>
                  <div className="loading-text">
                    <span className="spinner" />
                    {engine === 'whisperx'
                      ? 'Running WhisperX + Pyannote locally on GPU… (first run downloads models)'
                      : 'Sending to Deepgram nova-2-phonecall with diarization…'
                    }
                  </div>
                </>
              )}

              {/* Transcript result */}
              {transcript && (
                <div className="transcript-viewer">
                  <div className="transcript-meta">
                    <span className="meta-pill">📋 Call ID: <strong>{transcript.call_id.slice(0, 8)}…</strong></span>
                    <span className="meta-pill">⏱ Duration: <strong>{formatTime(transcript.duration_sec)}</strong></span>
                    <span className="meta-pill">💬 Turns: <strong>{transcript.turns.length}</strong></span>
                    <span className={`meta-pill engine-pill ${transcript.engine === 'whisperx' ? 'engine-local' : 'engine-cloud'}`}>
                      {transcript.engine === 'whisperx' ? '🖥️' : '☁️'} {transcript.engine}
                    </span>
                  </div>
                  <div className="transcript-turns">
                    {transcript.turns.map((t, i) => {
                      const spkClean = t.speaker.replace('speaker_', '').replace('SPEAKER_', '')
                      return (
                        <div className="turn" key={i}>
                          <div className="turn-header">
                            <span className={`turn-speaker speaker-${spkClean}`}>{t.speaker}</span>
                            <span className="turn-time">{formatTime(t.start)} – {formatTime(t.end)}</span>
                          </div>
                          <div className="turn-text">{t.text}</div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* ── Step 2: Flag & Analyze ──────────────────────── */}
          <section className="step-card" style={{ opacity: transcript ? 1 : 0.4, pointerEvents: transcript ? 'auto' : 'none' }}>
            <div className="step-header">
              <div className="step-number">2</div>
              <h2>Flag & Analyze <small>POST /flag</small></h2>
            </div>
            <div className="step-body">
              {!transcript && (
                <div className="empty-state">
                  <p>Transcribe a call first to enable analysis</p>
                </div>
              )}

              {transcript && !flagResult && (
                <>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Run the Gemini-powered quality analysis on <strong>{transcript.call_id.slice(0, 8)}…</strong>
                  </p>
                  <div className="btn-row">
                    <button
                      className="btn btn-primary"
                      disabled={flagging}
                      onClick={doFlag}
                    >
                      {flagging ? <><span className="spinner" /> Analyzing…</> : '🔍 Run Analysis'}
                    </button>
                  </div>

                  {flagging && (
                    <>
                      <div className="loading-bar"><div className="progress" style={{ width: '100%' }} /></div>
                      <div className="loading-text"><span className="spinner" /> Gemini 3.5 Flash is scoring the call & extracting flags…</div>
                    </>
                  )}
                </>
              )}

              {/* Flag results */}
              {flagResult && (
                <div className="flag-results">
                  {/* Overall */}
                  <div className="overall-score">
                    <span className={`big-score ${scoreColor(flagResult.overall_score)}`}>
                      {flagResult.overall_score.toFixed(1)}
                    </span>
                    <div className="score-info">
                      <h3>Overall Score</h3>
                      <p>Average across 5 rubric dimensions (0–5 scale)</p>
                    </div>
                  </div>

                  {/* Per-dimension scores */}
                  <div className="scores-grid">
                    {Object.entries(flagResult.scores).map(([dim, val]) => (
                      <div className="score-card" key={dim}>
                        <div className="score-label">{dim.replace(/_/g, ' ')}</div>
                        <div className={`score-value ${scoreColor(val)}`}>{val}/5</div>
                      </div>
                    ))}
                  </div>

                  {/* Verified flags */}
                  <div className="flags-section">
                    <h3>
                      Verified Flags
                      <span className={`count-badge ${flagResult.flags.length > 0 ? 'danger' : 'muted'}`}>
                        {flagResult.flags.length}
                      </span>
                    </h3>
                    {flagResult.flags.length === 0 ? (
                      <div className="empty-state"><p>No issues found — clean call ✅</p></div>
                    ) : (
                      <div className="flag-list">
                        {flagResult.flags.map((f, i) => (
                          <div className="flag-item" key={i}>
                            <div className="flag-item-header">
                              <span className="flag-tag">{f.tag}</span>
                              <span className={`severity-badge ${f.severity}`}>{f.severity}</span>
                              {f.match_score != null && (
                                <span className="match-score">match: {f.match_score}%</span>
                              )}
                            </div>
                            <div className="flag-quote">"{f.quoted_line}"</div>
                            <div className="flag-reason">{f.reason}</div>
                            <div className="flag-timestamp">⏱ {formatTime(f.timestamp)}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Discarded flags */}
                  {flagResult.discarded_flags.length > 0 && (
                    <div className="flags-section discarded-section">
                      <h3>
                        Discarded (low match)
                        <span className="count-badge muted">{flagResult.discarded_flags.length}</span>
                      </h3>
                      <div className="flag-list">
                        {flagResult.discarded_flags.map((f, i) => (
                          <div className="flag-item" key={i}>
                            <div className="flag-item-header">
                              <span className="flag-tag">{f.tag}</span>
                              <span className={`severity-badge ${f.severity}`}>{f.severity}</span>
                              {f.match_score != null && (
                                <span className="match-score" style={{ color: 'var(--danger)' }}>match: {f.match_score}%</span>
                              )}
                            </div>
                            <div className="flag-quote">"{f.quoted_line}"</div>
                            <div className="flag-reason">{f.reason}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Re-run */}
                  <div className="btn-row">
                    <button className="btn btn-secondary" onClick={() => setFlagResult(null)}>
                      ↻ Re-analyze
                    </button>
                  </div>
                </div>
              )}
            </div>
          </section>
        </div>

        {/* Global error */}
        {error && <div className="error-banner">⚠ {error}</div>}
      </main>
    </div>
  )
}
