import { CheckCircle2, Loader2 } from "lucide-react";

export default function LoadingSteps({ steps, currentStep }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel">
      <p className="text-sm font-semibold text-slate-900">Review in progress</p>
      <div className="mt-4 space-y-3">
        {steps.map((step, index) => {
          const completed = index < currentStep;
          const active = index === currentStep;
          return (
            <div
              key={step}
              className={`flex min-h-11 items-center justify-between rounded-lg border px-4 ${
                completed
                  ? "border-emerald-200 bg-emerald-50"
                  : active
                    ? "border-sky-200 bg-sky-50"
                    : "border-slate-200 bg-slate-50/70"
              }`}
            >
              <span className="text-sm text-slate-700">{step}</span>
              {completed ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin text-sky-600" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-slate-300" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
