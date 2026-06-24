import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { searchSimilar } from '../api'
import CaseCard from '../components/CaseCard'
import Spinner from '../components/Spinner'
import Disclaimer from '../components/Disclaimer'

const CASE_TYPES = ['IPR', 'civil', 'criminal', 'labour', 'tax', 'constitutional']
const OUTCOMES   = ['', 'allowed', 'dismissed', 'partially_allowed']

export default function SearchPage() {
  const [query, setQuery]       = useState('')
  const [caseType, setCaseType] = useState('IPR')
  const [outcome, setOutcome]   = useState('')
  const [topK, setTopK]         = useState(10)

  const { mutate, data, isPending, error } = useMutation({
    mutationFn: searchSimilar,
  })

  const handleSearch = (e) => {
    e.preventDefault()
    if (!query.trim()) return
    mutate({ query, top_k: topK, case_type: caseType || undefined, outcome: outcome || undefined })
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Similar Case Finder</h1>
      <p className="text-slate-400 text-sm mb-6">
        Paste your case facts or argument summary to find the most relevant precedents.
      </p>

      <form onSubmit={handleSearch} className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Describe the case facts, legal issues, or argument summary…"
          rows={5}
          className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 resize-none mb-4"
        />

        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Case Type</label>
            <select
              value={caseType}
              onChange={e => setCaseType(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All types</option>
              {CASE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Outcome filter</label>
            <select
              value={outcome}
              onChange={e => setOutcome(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">Any outcome</option>
              {OUTCOMES.slice(1).map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-500 mb-1">Results</label>
            <select
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {[5, 10, 20].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <button
            type="submit"
            disabled={isPending || !query.trim()}
            className="ml-auto px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isPending ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {isPending && <Spinner label="Finding similar cases…" />}

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg p-4 text-sm mb-4">
          {error.response?.data?.detail || error.message}
        </div>
      )}

      {data && (
        <>
          <p className="text-sm text-slate-500 mb-4">
            Found <span className="text-slate-200 font-medium">{data.total}</span> similar cases
          </p>
          <div className="grid gap-3">
            {data.results.map((r, i) => (
              <CaseCard key={r.case_id} result={r} rank={i + 1} />
            ))}
          </div>
          <Disclaimer text={data.disclaimer} />
        </>
      )}
    </div>
  )
}
