import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getJudge } from '../api'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import Spinner from '../components/Spinner'
import Disclaimer from '../components/Disclaimer'

const OUTCOME_COLORS = {
  Allowed:   '#34d399',
  Dismissed: '#f87171',
  Partial:   '#fbbf24',
}

export default function JudgeProfilePage() {
  const { name } = useParams()
  const { data, isLoading, error } = useQuery({
    queryKey: ['judge', name],
    queryFn: () => getJudge(name),
  })

  if (isLoading) return <Spinner label="Loading judge profile…" />

  if (error) {
    return (
      <div>
        <Link to="/judges" className="text-sm text-indigo-400 hover:underline mb-4 block">
          ← Back to Judges
        </Link>
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg p-4 text-sm">
          {error.response?.data?.detail || error.message}
        </div>
      </div>
    )
  }

  if (!data) return null

  const allowRate  = Math.round((data.overall_allow_rate  || 0) * 100)
  const dismissRate = Math.round((data.overall_dismiss_rate || 0) * 100)
  const partialRate = Math.max(0, 100 - allowRate - dismissRate)

  const pieData = [
    { name: 'Allowed',   value: allowRate   },
    { name: 'Dismissed', value: dismissRate },
    { name: 'Partial',   value: partialRate },
  ].filter(d => d.value > 0)

  return (
    <div>
      <Link to="/judges" className="text-sm text-indigo-400 hover:underline mb-4 block">
        ← Back to Judges
      </Link>

      <h1 className="text-2xl font-bold text-white mb-1">{data.display_name}</h1>
      <p className="text-slate-400 text-sm mb-6">
        {data.total_cases} cases with known outcomes · avg {data.avg_hearings_before_judgment.toFixed(1)} hearings
      </p>

      <div className="grid md:grid-cols-2 gap-6 mb-8">
        {/* Pie chart */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Outcome Distribution</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={OUTCOME_COLORS[entry.name]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(v) => `${v}%`}
                  contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}
                  itemStyle={{ color: '#cbd5e1' }}
                />
                <Legend
                  formatter={(v) => <span className="text-xs text-slate-400">{v}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-slate-500 text-sm text-center py-12">No outcome data</p>
          )}
        </div>

        {/* Stats */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Overall Stats</h2>
            <div className="space-y-2">
              {[
                { label: 'Allow rate',        value: `${allowRate}%`,   color: 'text-emerald-400' },
                { label: 'Dismiss rate',      value: `${dismissRate}%`, color: 'text-red-400'     },
                { label: 'Avg hearings',      value: data.avg_hearings_before_judgment.toFixed(1) },
                { label: 'Total cases (known)', value: data.total_cases },
              ].map(({ label, value, color }) => (
                <div key={label} className="flex justify-between text-sm">
                  <span className="text-slate-500">{label}</span>
                  <span className={color || 'text-slate-200'}>{value}</span>
                </div>
              ))}
            </div>
          </div>

          {Object.keys(data.by_case_type || {}).length > 0 && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-3">By Case Type</h2>
              <div className="space-y-2">
                {Object.entries(data.by_case_type).map(([ct, stats]) => (
                  <div key={ct} className="flex justify-between text-sm">
                    <span className="text-slate-400">{ct}</span>
                    <span className="text-slate-300">
                      {Math.round((stats.allow_rate || 0) * 100)}% allow · {stats.total} cases
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {data.recent_judgments?.length > 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Recent Judgments</h2>
          <div className="space-y-3">
            {data.recent_judgments.map((j) => {
              const outcomeColor =
                j.outcome === 'allowed'   ? 'text-emerald-400' :
                j.outcome === 'dismissed' ? 'text-red-400' :
                'text-amber-400'
              return (
                <div key={j.case_id} className="flex items-start gap-3">
                  <span className={`text-xs font-semibold w-20 shrink-0 mt-0.5 ${outcomeColor}`}>
                    {j.outcome.toUpperCase()}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-300 truncate">{j.title || j.case_id}</p>
                    <p className="text-xs text-slate-600">{j.date?.slice(0, 10)}</p>
                  </div>
                  {j.url && (
                    <a
                      href={j.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-indigo-400 hover:underline shrink-0"
                    >
                      View →
                    </a>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <Disclaimer text={data.disclaimer} />
    </div>
  )
}
