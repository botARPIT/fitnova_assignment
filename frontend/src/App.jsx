import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import ErrorBoundary from './components/common/ErrorBoundary'
import DashboardPage from './pages/DashboardPage'
import CallListPage from './pages/CallListPage'
import CallDetailPage from './pages/CallDetailPage'
import UploadPage from './pages/UploadPage'
import TeamPage from './pages/TeamPage'

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/calls" element={<CallListPage />} />
            <Route path="/calls/:callId" element={<CallDetailPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/team" element={<TeamPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
