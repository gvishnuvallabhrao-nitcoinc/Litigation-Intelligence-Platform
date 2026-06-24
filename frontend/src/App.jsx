import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import PrecedentsPage from './pages/PrecedentsPage'
import AnalyzePage from './pages/AnalyzePage'
import JudgesPage from './pages/JudgesPage'
import JudgeProfilePage from './pages/JudgeProfilePage'

const NAV = [
  { to: '/search',     label: 'Similar Cases' },
  { to: '/precedents', label: 'Precedents' },
  { to: '/analyze',    label: 'Analyze Argument' },
  { to: '/judges',     label: 'Judges' },
]

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-8">
          <div className="flex items-center gap-2">
            <span className="text-indigo-400 text-xl">⚖</span>
            <span className="font-semibold text-white">LegalIntel</span>
            <span className="text-xs text-slate-500 ml-1">India</span>
          </div>
          <nav className="flex gap-1">
            {NAV.map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm transition-colors ${
                    isActive
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800'
                  }`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        <Routes>
          <Route path="/" element={<Navigate to="/search" replace />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/precedents" element={<PrecedentsPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/judges" element={<JudgesPage />} />
          <Route path="/judges/:name" element={<JudgeProfilePage />} />
        </Routes>
      </main>

      <footer className="border-t border-slate-800 text-center text-xs text-slate-600 py-4">
        Research aid only — not legal advice. Consult a qualified advocate.
      </footer>
    </div>
  )
}
