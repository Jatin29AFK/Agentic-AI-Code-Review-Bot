import { AlertTriangle, CheckCircle2, GitPullRequestArrow, ShieldAlert, Sparkles, Workflow } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import ScoreCard from "../components/ScoreCard";

export default function Dashboard() {
  const [reviews, setReviews] = useState([]);
  const [error, setError] = useState("");
  const [health, setHealth] = useState({ loading: true, ok: false, message: "" });

  useEffect(() => {
    api.getReviews().then(setReviews).catch((err) => setError(err.message));
    api
      .getHealth()
      .then(() => setHealth({ loading: false, ok: true, message: "Backend connected" }))
      .catch((err) => setHealth({ loading: false, ok: false, message: err.message }));
  }, []);

  const stats = useMemo(() => {
    const totalReviews = reviews.length;
    const totalIssues = reviews.reduce((sum, review) => sum + review.total_issues, 0);
    const avgScore = totalReviews
      ? Math.round((reviews.reduce((sum, review) => sum + review.score, 0) / totalReviews) * 10) / 10
      : 0;
    const highRisk = reviews.filter((review) => review.risk_level === "high").length;
    return { totalReviews, totalIssues, avgScore, highRisk };
  }, [reviews]);

  return (
    <div className="space-y-10">
      <section className="border-b border-slate-200 pb-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-4">
            <span className="inline-flex h-8 items-center rounded-full border border-sky-200 bg-sky-100 px-3 text-xs font-semibold text-sky-800">
              Fast GitHub PR reviews with optional token-based access
            </span>
            <div className="space-y-3">
              <h1 className="text-4xl font-semibold tracking-tight text-slate-900">Agentic AI Code Review Bot</h1>
              <p className="max-w-2xl text-base leading-7 text-slate-700">
                Review public or authorized private pull requests with a multi-agent workflow that focuses on bugs, security, quality, and missing tests before human reviewers step in.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 font-semibold ${
                  health.ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-800"
                }`}
              >
                {health.loading ? "Checking backend..." : health.message}
              </span>
              <span className="text-slate-500">Public repos work without a token. Private repos and GitHub comment posting need one.</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/reviews/new"
              className="inline-flex h-11 items-center justify-center rounded-lg bg-sky-500 px-5 text-sm font-semibold text-white transition hover:bg-sky-600"
            >
              Start a review
            </Link>
            <Link
              to="/history"
              className="inline-flex h-11 items-center justify-center rounded-lg border border-slate-200 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              View history
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <ScoreCard icon={GitPullRequestArrow} label="Total reviews" value={stats.totalReviews} hint="Saved in local SQLite history" />
        <ScoreCard icon={Sparkles} label="Average score" value={stats.avgScore} hint="Across all completed reviews" tone="emerald" />
        <ScoreCard icon={AlertTriangle} label="Issues found" value={stats.totalIssues} hint="Actionable findings surfaced by the bot" tone="amber" />
        <ScoreCard icon={ShieldAlert} label="High-risk PRs" value={stats.highRisk} hint="PRs needing closer human attention" tone="rose" />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <h2 className="text-lg font-semibold text-slate-900">Public repo, review only</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Paste the repo URL and PR number. You can usually leave the GitHub token empty unless you hit rate limits.
          </p>
        </article>
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <Workflow className="h-5 w-5 text-sky-600" />
            <h2 className="text-lg font-semibold text-slate-900">Public repo, reliable usage</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Add a fine-grained PAT when you want higher GitHub API limits, more reliable fetches, or to review many PRs in one sitting.
          </p>
        </article>
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-5 w-5 text-amber-600" />
            <h2 className="text-lg font-semibold text-slate-900">Private repo or post comments</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Use a token with repository access. For comment posting, grant Pull requests: Read and write plus Issues: Read and write.
          </p>
        </article>
      </section>

      <section className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Recent reviews</h2>
            <p className="mt-1 text-sm text-slate-600">Most recent review runs and their overall health signal.</p>
          </div>
          <Link to="/history" className="text-sm font-medium text-sky-700 hover:text-sky-800">
            View full history
          </Link>
        </div>

        {error ? <p className="text-sm text-rose-700">{error}</p> : null}

        {reviews.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-8 text-sm text-slate-600">
            No reviews yet. Run a manual review to populate the dashboard.
          </div>
        ) : (
          <div className="grid gap-4">
            {reviews.slice(0, 6).map((review) => (
              <Link
                key={review.review_id}
                to={`/reviews/${review.review_id}`}
                className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel transition hover:border-sky-200 hover:bg-white"
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <p className="text-sm text-slate-500">{review.repo}</p>
                    <h3 className="text-lg font-semibold text-slate-900">
                      PR #{review.pr_number}: {review.pr_title}
                    </h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <span className="rounded-full border border-slate-200 px-3 py-1 text-slate-700">Score {review.score}</span>
                    <span className="rounded-full border border-slate-200 px-3 py-1 capitalize text-slate-700">{review.risk_level} risk</span>
                    <span className="rounded-full border border-slate-200 px-3 py-1 text-slate-700">{review.total_issues} issues</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
