export default function ScoreCard({ icon: Icon, label, value, hint, tone = "slate" }) {
  const toneClasses = {
    slate: "border-slate-200 bg-white/80 text-slate-900",
    emerald: "border-sky-200 bg-sky-50 text-sky-900",
    amber: "border-amber-200 bg-amber-50 text-amber-900",
    rose: "border-rose-200 bg-rose-50 text-rose-900",
  };

  return (
    <article className={`rounded-lg border p-5 shadow-panel ${toneClasses[tone]}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-current">{value}</p>
          {hint ? <p className="mt-2 text-sm text-slate-500">{hint}</p> : null}
        </div>
        <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-slate-200 bg-white/70">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </article>
  );
}
