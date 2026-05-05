const severityMap = {
  critical: "bg-rose-100 text-rose-800 border-rose-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  low: "bg-sky-100 text-sky-800 border-sky-200",
  suggestion: "bg-slate-100 text-slate-700 border-slate-200",
};

export default function SeverityBadge({ severity }) {
  const label = severity?.charAt(0).toUpperCase() + severity?.slice(1);
  return (
    <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-semibold ${severityMap[severity] || severityMap.suggestion}`}>
      {label}
    </span>
  );
}
