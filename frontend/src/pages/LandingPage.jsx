import { Link } from 'react-router-dom'
import styles from './LandingPage.module.css'

const WORKFLOW_STEPS = [
  {
    title: 'Upload Deepgram-Ready Audio',
    detail: 'Assign the recording to the right advisor, send it through transcription, and keep the workflow tied to the real call owner.',
  },
  {
    title: 'Validate Evidence, Not Hype',
    detail: 'Speaker repair, scoring, and flags stay grounded in quote-backed findings and company-policy checks before anyone acts on them.',
  },
  {
    title: 'Resolve With Role-Based Review',
    detail: 'Advisors can contest their own calls. Team leaders and directors decide whether flags should stand or be overturned.',
  },
]

const VALUE_POINTS = [
  'Deepgram transcription with LLM speaker repair',
  'Evidence-backed scoring across five sales dimensions',
  'Contest and review workflow with advisor/team-leader separation',
  'Org, team, advisor, and call-level visibility in one place',
]

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <span className={styles.eyebrow}>FitNova Sales Intelligence</span>
          <h1 className={styles.title}>
            Review fitness sales calls with evidence-backed scoring, contestation, and decision flow.
          </h1>
          <p className={styles.subtitle}>
            A call recording moves from upload to transcription, speaker repair, structured analysis,
            and review resolution without losing accountability for who said what and who can act on it.
          </p>
          <div className={styles.actions}>
            <Link className={styles.primaryCta} to="/upload">
              Start With Upload
            </Link>
            <Link className={styles.secondaryCta} to="/dashboard">
              Open Dashboard
            </Link>
          </div>
          <div className={styles.valueStrip}>
            {VALUE_POINTS.map((point) => (
              <span key={point} className={styles.valuePill}>{point}</span>
            ))}
          </div>
        </div>

        <div className={styles.heroPanel}>
          <div className={styles.panelCard}>
            <span className={styles.panelBadge}>Active Review Loop</span>
            <div className={styles.metricGrid}>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Transcript</span>
                <strong className={styles.metricValue}>Deepgram + LLM</strong>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Flags</span>
                <strong className={styles.metricValue}>Quote-Verified</strong>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Permissions</span>
                <strong className={styles.metricValue}>Role-Based</strong>
              </div>
              <div className={styles.metricCard}>
                <span className={styles.metricLabel}>Outcome</span>
                <strong className={styles.metricValue}>Contest or Keep</strong>
              </div>
            </div>
            <div className={styles.pipelineRail}>
              <div className={styles.railStep}>
                <span className={styles.stepDot} />
                <div>
                  <strong>Transcribe</strong>
                  <p>Audio becomes structured turns with timestamps.</p>
                </div>
              </div>
              <div className={styles.railStep}>
                <span className={styles.stepDot} />
                <div>
                  <strong>Flag</strong>
                  <p>Scores and findings are validated against policy and evidence.</p>
                </div>
              </div>
              <div className={styles.railStep}>
                <span className={styles.stepDot} />
                <div>
                  <strong>Resolve</strong>
                  <p>Only the right people can contest or adjudicate.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.workflowSection}>
        <div className={styles.sectionHeading}>
          <span className={styles.sectionEyebrow}>Workflow</span>
          <h2>Built to explain how review decisions are made, not just display a score.</h2>
        </div>
        <div className={styles.workflowGrid}>
          {WORKFLOW_STEPS.map((step, index) => (
            <article key={step.title} className={styles.workflowCard}>
              <span className={styles.workflowIndex}>0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
