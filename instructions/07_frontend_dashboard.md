# Task 07: Frontend — Multi-Page Dashboard

## Objective
Evolve the existing single-page React frontend into a multi-page dashboard with navigation, call history, call detail view, analytics overview, and the existing upload/analysis flow.

## Parallelization
**Group C** — Depends on Tasks 04, 05, 06 (backend endpoints must exist). Can start UI shell in parallel.

## Context
The current frontend (`App.jsx`) is a single-page file that:
- Uploads audio
- Selects STT engine
- Displays transcript and flags

We need to evolve this into a multi-page dashboard while **preserving all existing functionality**.

## Technology
- React (existing Vite setup)
- React Router v6 for navigation
- Vanilla CSS (existing `App.css` + new pages)
- No additional UI library

## Pages to Create

### 1. Dashboard Layout (`src/components/Layout.jsx`)

Persistent sidebar navigation + main content area:

```
┌──────────────┬───────────────────────────────────────────┐
│              │                                           │
│  🎯 FitNova  │   Main Content Area                      │
│              │                                           │
│  📊 Dashboard│                                           │
│  📞 Calls    │   (routed content)                       │
│  📤 Upload   │                                           │
│  👥 Team     │                                           │
│              │                                           │
│              │                                           │
│              │                                           │
└──────────────┴───────────────────────────────────────────┘
```

- Sidebar: dark background, accent-colored active state
- Responsive: collapsible on mobile
- Logo/branding at top

### 2. Dashboard Page (`src/pages/DashboardPage.jsx`)

Route: `/`

Shows org-wide metrics cards:
- Total Calls (with completed/failed breakdown)
- Average Score (with gauge/progress ring)
- Active Advisors count
- Top Flags (bar chart or list)

Data source: `GET /api/analytics/overview`

### 3. Call List Page (`src/pages/CallListPage.jsx`)

Route: `/calls`

- Sortable, filterable table of all calls
- Columns: Date, Advisor, Team, Duration, Score, Status, Actions
- Filter bar: by advisor, team, status
- Click row → navigate to call detail
- Pagination

Data source: `GET /api/calls`

### 4. Call Detail Page (`src/pages/CallDetailPage.jsx`)

Route: `/calls/:callId`

Shows everything about a single call:
- **Header**: Advisor name, date, duration, overall score badge
- **Transcript Panel**: Diarized turns with speaker labels (Advisor/Customer), color-coded
- **Scores Panel**: Dimension-by-dimension scores (radar chart or bar chart)
- **Flags Panel**: List of flags with tag, quote, severity
  - **Contest Button** on each flag: opens modal to submit contest reason
- **Reviews Panel**: Shows any existing flag contests and their status

Data sources:
- `GET /api/calls/{callId}`
- `POST /api/calls/{callId}/contest-flag` (for contesting)
- `GET /api/calls/{callId}/reviews`

### 5. Upload Page (`src/pages/UploadPage.jsx`)

Route: `/upload`

Refactor the existing upload flow from `App.jsx`:
- File upload zone (drag & drop)
- Advisor selector dropdown (populated from `GET /api/org/advisors`)
- Engine selector (Deepgram/WhisperX/LLM)
- Progress indicator during processing
- On completion: navigate to call detail page

Data sources:
- `GET /api/org/advisors` (for selector)
- `POST /api/calls/upload` (new pipeline endpoint)

### 6. Team Page (`src/pages/TeamPage.jsx`)

Route: `/team`

- Team selector tabs
- Advisor leaderboard table (sorted by avg score)
- Per-advisor: call count, avg score, recent trend

Data sources:
- `GET /api/org/teams`
- `GET /api/analytics/teams/{teamId}`

## Files to Create

```
src/
├── components/
│   ├── Layout.jsx          # Sidebar + content area
│   ├── Layout.css
│   ├── ScoreGauge.jsx      # Circular score indicator
│   ├── FlagCard.jsx        # Single flag with contest button
│   ├── TranscriptViewer.jsx # Color-coded transcript display
│   └── ContestModal.jsx    # Modal for flag contestation
├── pages/
│   ├── DashboardPage.jsx
│   ├── DashboardPage.css
│   ├── CallListPage.jsx
│   ├── CallListPage.css
│   ├── CallDetailPage.jsx
│   ├── CallDetailPage.css
│   ├── UploadPage.jsx
│   ├── UploadPage.css
│   ├── TeamPage.jsx
│   └── TeamPage.css
└── App.jsx                 # Updated with React Router
```

## Files to Modify

### `src/App.jsx`

Replace the single-page layout with React Router:

```jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import CallListPage from './pages/CallListPage';
import CallDetailPage from './pages/CallDetailPage';
import UploadPage from './pages/UploadPage';
import TeamPage from './pages/TeamPage';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/calls" element={<CallListPage />} />
          <Route path="/calls/:callId" element={<CallDetailPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/team" element={<TeamPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
```

### `package.json`
Add dependency:
```
"react-router-dom": "^6.23.0"
```

## Design Guidelines

### Color Palette
Use the existing dark theme from `App.css` and extend it:
- Background: `#0a0a0f` (deep dark)
- Surface: `#12121a` (cards/panels)
- Accent: `#6366f1` (indigo/purple — for active states)
- Success: `#22c55e`
- Warning: `#f59e0b`
- Error: `#ef4444`
- Text: `#e2e8f0` (primary), `#94a3b8` (secondary)

### Score Visualization
- 0-2: Red badge (poor)
- 2-3: Orange badge (needs improvement)
- 3-4: Yellow badge (acceptable)
- 4-5: Green badge (excellent)

### Transcript Colors
- Advisor turns: indigo/blue left-aligned
- Customer turns: teal/green right-aligned (chat-bubble style)

### Typography
- Use Inter or Outfit (Google Fonts)
- Headers: 600-700 weight
- Body: 400 weight

## Acceptance Criteria
1. All 5 pages render correctly with proper routing
2. Sidebar navigation highlights active page
3. Dashboard shows live metrics from analytics API
4. Call list supports filtering by advisor, team, status
5. Call detail shows full transcript + scores + flags
6. Contest modal submits to the API and refreshes state
7. Upload page uses the new `/api/calls/upload` pipeline
8. Responsive layout (sidebar collapses on mobile)
9. Consistent dark theme across all pages
10. Smooth page transitions
