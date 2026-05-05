import { Clock3, ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function ReviewHistory() {
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getReviews().then(setReviews).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="space-y-8">
      <section className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Review history</h1>
        <p className="mt-3 text-sm leading-7 text-slate-700">
          Every completed review is persisted locally, so you can revisit earlier PR analyses and reuse the comment-posting flow later.
        </p>
      </section>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      {reviews.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-8 text-sm text-slate-600">
          No stored reviews yet.
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((review) => (
            <article key={review.review_id} className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <p className="text-sm text-slate-500">{review.repo}</p>
                  <h2 className="text-lg font-semibold text-slate-900">
                    PR #{review.pr_number}: {review.pr_title}
                  </h2>
                  <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600">
                    <span>Score {review.score}</span>
                    <span className="capitalize">{review.risk_level} risk</span>
                    <span>{review.total_issues} issues</span>
                    <span>{review.autofix_count || 0} autofix draft{review.autofix_count === 1 ? "" : "s"}</span>
                    <span className="inline-flex items-center gap-2">
                      <Clock3 className="h-4 w-4" />
                      {new Date(review.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                        review.has_autofix ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-100 text-slate-500"
                      }`}
                    >
                      {review.has_autofix ? "Autofix available" : "No autofix drafts"}
                    </span>
                  </div>
                </div>

                <Link
                  to={`/reviews/${review.review_id}`}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-slate-100 px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-200"
                >
                  Open details
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
