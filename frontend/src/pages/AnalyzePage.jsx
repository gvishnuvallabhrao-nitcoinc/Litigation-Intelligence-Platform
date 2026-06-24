import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { analyzeArgument } from '../api'
import Spinner from '../components/Spinner'
import Disclaimer from '../components/Disclaimer'

const SCORE_STYLE = {
  Strong:   { bar: 'bg-emerald-500', text: 'text-emerald-400', width: 'w-full' },
  Moderate: { bar: 'bg-amber-500',   text: 'text-amber-400',   width: 'w-2/3'  },
  Weak:     { bar: 'bg-red-500',     text: 'text-red-400',     width: 'w-1/3'  },
  Unknown:  { bar: 'bg-slate-600',   text: 'text-slate-400',   width: 'w-0'    },
}

function BulletSection({ title, items, accent = 'indigo' }) {
  if (!items?.length) return null
  const colors = {
    emerald: 'text-emerald-400',
    red:     'text-red-400',
    amber:   'text-amber-400',
    indigo:  'text-indigo-400',
  }
  return (
    <div className="mb-5">
      <h3 className={`text-sm font-semibold mb-2 ${colors[accent]}`}>{title}</h3>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-slate-300 flex gap-2">
            <span className={`mt-0.5 shrink-0 ${colors[accent]}`}>•</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function AnalyzePage() {
  const [argument, setArgument] = useState('')
  const [caseType, setCaseType] = useState('IPR')
  const [court, setCourt]       = useState('Delhi High Court')
  const [topK, setTopK]         = useState(10)

  const { mutate, data, isPending, error } = useMutation({ mutationFn: analyzeArgument })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!argument.trim()) return
    mutate({ argument, case_type: caseType, court, top_k: topK })
  }

  const score = data?.overall_score || 'Unknown'
  const style = SCORE_STYLE[score] || SCORE_STYLE.Unknown

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Argument Strength Analysis</h1>
      <p className="text-slate-400 text-sm mb-6">
        Enter your argument and get AI-powered analysis based on winning and losing patterns from similar cases.
      </p>

      <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
        <textarea
          value={argument}
          onChange={e => setArgument(e.target.value)}
          placeholder="Describe your legal argument in detail…"
          rows={6}
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
              {['IPR', 'civil', 'criminal', 'labour', 'tax'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Court</label>
            <select
              value={court}
              onChange={e => setCourt(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option>Delhi High Court</option>
              <option>Bombay High Court</option>
              <option>Madras High Court</option>
              <option>Supreme Court of India</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Compare against</label>
            <select
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {[5, 10, 20].map(n => <option key={n} value={n}>{n} cases</option>)}
            </select>
          </div>
          <button
            type="submit"
            disabled={isPending || !argument.trim()}
            className="ml-auto px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {isPending ? 'Analysing…' : 'Analyse'}
          </button>
        </div>
      </form>

      {isPending && <Spinner label="Analysing argument against similar cases (Cohere)…" />}

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg p-4 text-sm mb-4">
          {error.response?.data?.detail || error.message}
        </div>
      )}

      {data && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          {/* Score header */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-slate-400">
                Overall Strength — based on {data.similar_cases_used} similar cases
              </span>
              <span className={`text-lg font-bold ${style.text}`}>{score.toUpperCase()}</span>
            </div>
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-700 ${style.bar} ${style.width}`} />
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-x-8">
            <BulletSection title="Strengths"         items={data.strengths}           accent="emerald" />
            <BulletSection title="Weaknesses"        items={data.weaknesses}          accent="red"     />
            <BulletSection title="Missing Elements"  items={data.missing_elements}    accent="amber"   />
            <BulletSection title="Suggested Citations" items={data.suggested_citations} accent="indigo"  />
          </div>

          {data.raw_analysis && (
            <details className="mt-4">
              <summary className="text-xs text-slate-600 cursor-pointer hover:text-slate-400">
                Raw analysis
              </summary>
              <pre className="mt-2 text-xs text-slate-500 whitespace-pre-wrap bg-slate-950 rounded-lg p-4">
                {data.raw_analysis}
              </pre>
            </details>
          )}

          <Disclaimer text={data.disclaimer} />
        </div>
      )}
    </div>
  )
}
