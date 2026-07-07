import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCalls } from '../hooks/useCalls'
import { useTeams, useAdvisors } from '../hooks/useTeams'
import LoadingSkeleton from '../components/common/LoadingSkeleton'
import ErrorState from '../components/common/ErrorState'
import EmptyState from '../components/common/EmptyState'
import { formatTime } from '../utils/format'
import styles from './CallListPage.module.css'

const PAGE_SIZE = 20

export default function CallListPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [advisorFilter, setAdvisorFilter] = useState('')
  const [teamFilter, setTeamFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const [sortField, setSortField] = useState('created_at')
  const [sortDir, setSortDir] = useState('desc')

  const { teams } = useTeams()
  const { advisors } = useAdvisors(teamFilter)
  const { calls, count, loading, error, refetch } = useCalls({
    advisor_id: advisorFilter,
    team_id: teamFilter,
    status: statusFilter,
    limit: PAGE_SIZE,
    offset,
  })

  useEffect(() => {
    setAdvisorFilter('')
  }, [teamFilter])

  const filteredCalls = useMemo(() => {
    if (!search.trim()) return calls
    const q = search.toLowerCase()
    return calls.filter(c =>
      (c.advisor_name || '').toLowerCase().includes(q) ||
      (c.team_name || '').toLowerCase().includes(q) ||
      (c.id || '').toLowerCase().includes(q)
    )
  }, [calls, search])

  const sortedCalls = useMemo(() => {
    const sorted = [...filteredCalls]
    sorted.sort((a, b) => {
      let aVal = a[sortField]
      let bVal = b[sortField]
      if (aVal == null) return 1
      if (bVal == null) return -1
      if (typeof aVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal)
      }
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
    return sorted
  }, [filteredCalls, sortField, sortDir])

  const totalPages = Math.ceil(count / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir('desc')
    }
  }

  const sortIcon = (field) => {
    if (sortField !== field) return '↕'
    return sortDir === 'asc' ? '↑' : '↓'
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>Calls</h1>
      </div>

      <div className={styles.filters}>
        <input
          className={styles.searchInput}
          type="text"
          placeholder="Search by advisor, team, or ID..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select className={styles.select} value={teamFilter} onChange={e => setTeamFilter(e.target.value)}>
          <option value="">All Teams</option>
          {teams.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
        <select className={styles.select} value={advisorFilter} onChange={e => setAdvisorFilter(e.target.value)}>
          <option value="">All Advisors</option>
          {advisors.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <select className={styles.select} value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Statuses</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : loading ? (
        <LoadingSkeleton type="table" count={8} />
      ) : sortedCalls.length > 0 ? (
        <>
          <div className={styles.table}>
            <div className={styles.tableHeader}>
              <span className={styles.sortable} onClick={() => handleSort('advisor_name')}>
                Advisor {sortIcon('advisor_name')}
              </span>
              <span className={styles.sortable} onClick={() => handleSort('team_name')}>
                Team {sortIcon('team_name')}
              </span>
              <span className={styles.sortable} onClick={() => handleSort('status')}>
                Status {sortIcon('status')}
              </span>
              <span className={styles.sortable} onClick={() => handleSort('duration_sec')}>
                Duration {sortIcon('duration_sec')}
              </span>
              <span className={styles.sortable} onClick={() => handleSort('overall_score')}>
                Score {sortIcon('overall_score')}
              </span>
              <span className={styles.sortable} onClick={() => handleSort('created_at')}>
                Date {sortIcon('created_at')}
              </span>
            </div>
            {sortedCalls.map(call => (
              <div
                key={call.id}
                className={styles.tableRow}
                onClick={() => navigate(`/calls/${call.id}`)}
              >
                <span>{call.advisor_name || '—'}</span>
                <span>{call.team_name || '—'}</span>
                <span className={`${styles.status} ${styles[call.status] || ''}`}>{call.status}</span>
                <span>{call.duration_sec ? formatTime(call.duration_sec) : '—'}</span>
                <span className={styles.score}>{call.overall_score != null ? call.overall_score.toFixed(1) : '—'}</span>
                <span className={styles.date}>
                  {call.created_at ? new Date(call.created_at).toLocaleDateString() : '—'}
                </span>
              </div>
            ))}
          </div>

          <div className={styles.pagination}>
            <button
              className={styles.pageBtn}
              disabled={currentPage <= 1}
              onClick={() => setOffset(0)}
            >
              First
            </button>
            <button
              className={styles.pageBtn}
              disabled={currentPage <= 1}
              onClick={() => setOffset(o => Math.max(0, o - PAGE_SIZE))}
            >
              Previous
            </button>
            <span className={styles.pageInfo}>
              Page {currentPage} of {totalPages || 1}
            </span>
            <button
              className={styles.pageBtn}
              disabled={currentPage >= totalPages}
              onClick={() => setOffset(o => o + PAGE_SIZE)}
            >
              Next
            </button>
            <button
              className={styles.pageBtn}
              disabled={currentPage >= totalPages}
              onClick={() => setOffset((totalPages - 1) * PAGE_SIZE)}
            >
              Last
            </button>
          </div>
        </>
      ) : (
        <EmptyState
          title="No calls found"
          message={search || advisorFilter || teamFilter || statusFilter ? 'Try adjusting your filters.' : 'Upload a call to get started.'}
        />
      )}
    </div>
  )
}
