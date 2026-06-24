const OUTCOME_STYLE = {
  allowed:           'bg-emerald-900/50 text-emerald-300 border-emerald-700',
  dismissed:         'bg-red-900/50 text-red-300 border-red-700',
  partially_allowed: 'bg-amber-900/50 text-amber-300 border-amber-700',
  unknown:           'bg-slate-800 text-slate-400 border-slate-700',
}

const OUTCOME_LABEL = {
  allowed:           'ALLOWED',
  dismissed:         'DISMISSED',
  partially_allowed: 'PARTIAL',
  unknown:           'UNKNOWN',
}

export default function CaseCard({ result, rank }) {
  const outcome = result.outcome || 'unknown'
  const style = OUTCOME_STYLE[outcome] || OUTCOME_STYLE.unknown
  const label = OUTCOME_LABEL[outcome] || outcome.toUpperCase()
  const score = Math.round((result.similarity_score || 0) * 100)

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 hover:border-indigo-700 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${style}`}>
            {label}
          </span>
          <span className="text-xs text-slate-500">{result.court}</span>
          <span className="text-xs text-slate-600">•</span>
          <span className="text-xs text-slate-500">{result.date?.slice(0, 10)}</span>
        </div>
        <span className="text-xs font-mono text-indigo-400 shrink-0">
          {score}% match
        </span>
      </div>

      <p className="text-sm font-medium text-slate-100 mb-1 line-clamp-2">
        {rank && <span className="text-slate-600 mr-1">[{rank}]</span>}
        {result.title}
      </p>

      <p className="text-xs text-slate-500 mb-3">
        Judge: {result.judge || '—'}
      </p>

      {result.summary && (
        <p className="text-xs text-slate-400 line-clamp-3 mb-3">
          {result.summary}
        </p>
      )}

      <div className="flex items-center justify-between">
        {result.acts_cited?.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {result.acts_cited.slice(0, 3).map((act) => (
              <span
                key={act}
                className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded"
              >
                {act}
              </span>
            ))}
            {result.acts_cited.length > 3 && (
              <span className="text-xs text-slate-600">
                +{result.acts_cited.length - 3}
              </span>
            )}
          </div>
        )}
        {result.url && (
          <a
            href={result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-indigo-400 hover:text-indigo-300 hover:underline shrink-0 ml-auto"
          >
            View case →
          </a>
        )}
      </div>
    </div>
  )
}
