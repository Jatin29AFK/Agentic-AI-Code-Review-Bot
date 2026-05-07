import { Clock3, ExternalLink, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function ReviewHistory() {
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("newest");
  const [riskFilter, setRiskFilter] = useState("all");

  useEffect(() => {
    api.getReviews().then(setReviews).catch((err) => setError(err.message));
  }, []);

  const filteredReviews = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const next = reviews.filter((review) => {
      const matchesRisk = riskFilter === "all" || review.risk_level === riskFilter;
      if (!matchesRisk) {
        return false;
      }
      if (!query) {
        return true;
      }
      return [review.repo, review.pr_title, String(review.pr_number)].join(" ").toLowerCase().includes(query);
    });

    return next.sort((left, right) => {
      if (sortBy === "score") {
        return left.score - right.score;
      }
      if (sortBy === "issues") {
        return right.total_issues - left.total_issues;
      }
      if (sortBy === "risk") {
        const order = { high: 0, medium: 1, low: 2 };
        return order[left.risk_level] - order[right.risk_level];
      }
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  }, [reviews, riskFilter, searchQuery, sortBy]);

  return (
    <div className="space-y-8">
      <section className="border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Review history</h1>
        <p className="mt-3 text-sm leading-7 text-slate-700">
          Every completed review is persisted locally, so you can revisit earlier PR analyses and reuse the comment-posting flow later.
        </p>
      </section>

      <section className="panel p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_180px]">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search by repo, PR title, or number"
              className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
            />
          </label>

          <select
            value={riskFilter}
            onChange={(event) => setRiskFilter(event.target.value)}
            className="h-11 rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition focus:border-sky-300"
          >
            <option value="all">All risk levels</option>
            <option value="high">High risk</option>
            <option value="medium">Medium risk</option>
            <option value="low">Low risk</option>
          </select>

          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value)}
            className="h-11 rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition focus:border-sky-300"
          >
            <option value="newest">Newest first</option>
            <option value="risk">Highest risk first</option>
            <option value="issues">Most issues first</option>
            <option value="score">Lowest score first</option>
          </select>
        </div>
      </section>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      {filteredReviews.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-8 text-sm text-slate-600">
          {reviews.length === 0 ? "No stored reviews yet." : "No reviews match the current search or filter."}
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReviews.map((review) => (
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
