import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { searchPrecedents, searchCitations } from '../api'
import CaseCard from '../components/CaseCard'
import Spinner from '../components/Spinner'
import Disclaimer from '../components/Disclaimer'

export default function PrecedentsPage() {
  const [tab, setTab]           = useState('precedents') // 'precedents' | 'citations'
  const [query, setQuery]       = useState('')
  const [acts, setActs]         = useState('')
  const [caseType, setCaseType] = useState('IPR')
  const [topK, setTopK]         = useState(5)

  const precMutation = useMutation({ mutationFn: searchPrecedents })
  const citeMutation = useMutation({ mutationFn: searchCitations })
  const active = tab === 'precedents' ? precMutation : citeMutation

  const handleSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    if (tab === 'precedents') {
      precMutation.mutate({ query, case_type: caseType, top_k: topK })
    } else {
      const actsArr = acts.split(',').map(a => a.trim()).filter(Boolean)
      citeMutation.mutate({ query, acts_cited: actsArr, case_type: caseType, top_k: topK })
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Winning Precedents & Citations</h1>
      <p className="text-slate-400 text-sm mb-6">
        Find cases that won on similar facts, or get citation recommendations that share your Acts.
      </p>

      <div className="flex gap-2 mb-5">
        {['precedents', 'citations'].map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm rounded-lg transition-colors ${
              tab === t
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-100'
            }`}
          >
            {t === 'precedents' ? 'Winning Precedents' : 'Citation Recommendations'}
          </button>
        ))}
      </div>

      <form onSubmit={handleSearch} className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Describe the case facts or legal issues…"
          rows={4}
          className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 resize-none mb-3"
        />

        {tab === 'citations' && (
          <input
            value={acts}
            onChange={e => setActs(e.target.value)}
            placeholder="Acts cited, comma-separated (e.g. Trade Marks Act, Patents Act)"
            className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 mb-3"
          />
        )}

        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Case Type</label>
            <select
              value={caseType}
              onChange={e => setCaseType(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {['IPR', 'civil', 'criminal', 'labour', 'tax'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Results</label>
            <select
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {[5, 10, 15].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={active.isPending || !query.trim()}
            className="ml-auto px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {active.isPending ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {active.isPending && <Spinner label={tab === 'precedents' ? 'Finding winning precedents…' : 'Finding citations…'} />}

      {active.error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg p-4 text-sm mb-4">
          {active.error.response?.data?.detail || active.error.message}
        </div>
      )}

      {active.data && (
        <>
          <p className="text-sm text-slate-500 mb-4">
            <span className="text-slate-200 font-medium">{active.data.total}</span> results
            {tab === 'precedents' && ' — all allowed (won)'}
          </p>
          <div className="grid gap-3">
            {active.data.results.map((r, i) => (
              <CaseCard key={r.case_id} result={r} rank={i + 1} />
            ))}
          </div>
          <Disclaimer text={active.data.disclaimer} />
        </>
      )}
    </div>
  )
}
