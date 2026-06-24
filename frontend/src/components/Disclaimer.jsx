export default function Disclaimer({ text }) {
  if (!text) return null
  return (
    <p className="text-xs text-slate-600 border border-slate-800 rounded-lg px-4 py-2 mt-6">
      ⚠ {text}
    </p>
  )
}
