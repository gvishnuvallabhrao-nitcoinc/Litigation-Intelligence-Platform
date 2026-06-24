import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getJudges } from '../api'
import Spinner from '../components/Spinner'

export default function JudgesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['judges'],
    queryFn: getJudges,
  })

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-1">Judge Analytics</h1>
      <p className="text-slate-400 text-sm mb-6">
        Historical allow rates and case statistics by judge.
      </p>

      {isLoading && <Spinner label="Loading judges…" />}

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg p-4 text-sm">
          {error.response?.data?.detail || error.message}
        </div>
      )}

      {data && (
        <>
          <p className="text-sm text-slate-500 mb-4">
            {data.total} judges in the database
          </p>
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-xs text-slate-500">
                  <th className="text-left px-4 py-3">Judge</th>
                  <th className="text-right px-4 py-3">Cases</th>
                  <th className="text-right px-4 py-3">Allow Rate</th>
                  <th className="text-right px-4 py-3">Avg Hearings</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {data.judges.map((j) => {
                  const rate = Math.round((j.allow_rate || 0) * 100)
                  const rateColor =
                    rate >= 60 ? 'text-emerald-400' :
                    rate >= 40 ? 'text-amber-400' :
                    'text-red-400'
                  return (
                    <tr
                      key={j.judge_name}
                      className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
                    >
                      <td className="px-4 py-3 text-slate-200">
                        {j.judge_name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-400">{j.total_cases}</td>
                      <td className={`px-4 py-3 text-right font-medium ${rateColor}`}>
                        {rate}%
                      </td>
                      <td className="px-4 py-3 text-right text-slate-400">
                        {(j.avg_hearing_count || 0).toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          to={`/judges/${j.judge_name}`}
                          className="text-xs text-indigo-400 hover:text-indigo-300"
                        >
                          Profile →
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
