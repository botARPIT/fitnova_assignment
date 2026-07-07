import { useLocation, useNavigate } from 'react-router-dom'
import styles from './TopBar.module.css'

const BREADCRUMB_LABELS = {
  '': 'Dashboard',
  'calls': 'Calls',
  'upload': 'Upload',
  'team': 'Team',
}

export default function TopBar({ onRefresh }) {
  const location = useLocation()
  const navigate = useNavigate()
  const segments = location.pathname.split('/').filter(Boolean)

  return (
    <header className={styles.topbar}>
      <div className={styles.breadcrumbs}>
        <button className={styles.homeLink} onClick={() => navigate('/')}>
          FitNova
        </button>
        {segments.map((seg, i) => (
          <span key={seg} className={styles.segment}>
            <span className={styles.separator}>/</span>
            <span className={i === segments.length - 1 ? styles.current : styles.link}>
              {BREADCRUMB_LABELS[seg] || seg}
            </span>
          </span>
        ))}
      </div>

      <div className={styles.actions}>
        {onRefresh && (
          <button className={styles.refreshBtn} onClick={onRefresh} title="Refresh">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" width="18" height="18">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
            </svg>
          </button>
        )}
      </div>
    </header>
  )
}
