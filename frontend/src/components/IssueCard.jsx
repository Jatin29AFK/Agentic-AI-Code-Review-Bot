import SeverityBadge from "./SeverityBadge";

const categoryClasses = {
  bug: "bg-sky-100 text-sky-800 border-sky-200",
  security: "bg-rose-100 text-rose-800 border-rose-200",
  quality: "bg-violet-100 text-violet-800 border-violet-200",
  testing: "bg-emerald-100 text-emerald-800 border-emerald-200",
  performance: "bg-amber-100 text-amber-800 border-amber-200",
};

export default function IssueCard({ issue }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel">
      <div className="flex flex-wrap items-center gap-3">
        <SeverityBadge severity={issue.severity} />
        <span className={`inline-flex h-7 items-center rounded-full border px-3 text-xs font-semibold capitalize ${categoryClasses[issue.category] || categoryClasses.quality}`}>
          {issue.category}
        </span>
        <span className="text-sm text-slate-500">
          {issue.file}
          {issue.line ? `:${issue.line}` : ""}
        </span>
      </div>

      <div className="mt-4 space-y-3">
        <h3 className="text-lg font-semibold text-slate-900">{issue.title}</h3>
        <p className="text-sm leading-6 text-slate-700">{issue.description}</p>
        <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Suggested fix</p>
          <p className="mt-2 text-sm leading-6 text-slate-700">{issue.suggested_fix}</p>
        </div>
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-slate-500">Confidence</p>
          <div className="flex min-w-[180px] items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-sky-400" style={{ width: `${issue.confidence * 100}%` }} />
            </div>
            <span className="w-12 text-right text-sm text-slate-600">{Math.round(issue.confidence * 100)}%</span>
          </div>
        </div>
      </div>
    </article>
  );
}
