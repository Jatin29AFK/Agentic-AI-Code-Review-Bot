import { AlertCircle, Loader2, Play, WandSparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import LoadingSteps from "../components/LoadingSteps";

const loadingSteps = [
  "Fetching pull request details",
  "Reading changed files",
  "Running agent reviewers",
  "Generating final review",
  "Saving result",
];

function parsePullRequestUrl(value) {
  const match = value.match(/^https?:\/\/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)(?:\/.*)?$/i);
  if (!match) {
    return null;
  }
  return {
    repoUrl: `https://github.com/${match[1]}`,
    prNumber: match[2],
  };
}

export default function NewReview() {
  const navigate = useNavigate();
  const [prUrl, setPrUrl] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [prNumber, setPrNumber] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading) {
      setCurrentStep(0);
      return undefined;
    }

    const interval = window.setInterval(() => {
      setCurrentStep((step) => (step < loadingSteps.length - 1 ? step + 1 : step));
    }, 1400);

    return () => window.clearInterval(interval);
  }, [loading]);

  const canSubmit = useMemo(() => repoUrl.trim() && Number(prNumber) > 0 && !loading, [loading, prNumber, repoUrl]);

  function autofillFromPrUrl() {
    const parsed = parsePullRequestUrl(prUrl.trim());
    if (!parsed) {
      setError("Paste a GitHub pull request URL like https://github.com/owner/repo/pull/123.");
      return;
    }
    setRepoUrl(parsed.repoUrl);
    setPrNumber(parsed.prNumber);
    setError("");
  }

  function loadExample() {
    setPrUrl("https://github.com/psf/requests/pull/7213");
    setRepoUrl("https://github.com/psf/requests");
    setPrNumber("7213");
    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    const submittedToken = githubToken.trim();

    try {
      const review = await api.createManualReview({
        repo_url: repoUrl.trim(),
        pr_number: Number(prNumber),
        github_token: submittedToken || undefined,
      });
      setGithubToken("");
      navigate(`/reviews/${review.review_id}`, {
        state: {
          review,
          githubToken: submittedToken,
        },
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-8 xl:grid-cols-[minmax(0,1.2fr)_360px]">
      <section className="space-y-6">
        <div className="border-b border-slate-200 pb-6">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Run a manual PR review</h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-700">
            Paste a GitHub repository URL and pull request number to fetch the live diff, route it through the review agents, and store the structured result locally.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 rounded-lg border border-slate-200 bg-white/80 p-6 shadow-panel">
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-3">
              <label className="text-sm font-medium text-slate-700" htmlFor="pr-url">
                GitHub pull request URL
              </label>
              <button
                type="button"
                onClick={loadExample}
                className="inline-flex h-8 items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 text-xs font-semibold text-sky-700 transition hover:bg-sky-100"
              >
                <WandSparkles className="h-3.5 w-3.5" />
                Use public example
              </button>
            </div>
            <div className="flex flex-col gap-3 md:flex-row">
              <input
                id="pr-url"
                type="url"
                value={prUrl}
                onChange={(event) => setPrUrl(event.target.value)}
                placeholder="https://github.com/owner/repo/pull/123"
                className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
              />
              <button
                type="button"
                onClick={autofillFromPrUrl}
                className="inline-flex h-11 items-center justify-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                Autofill
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="repo-url">
              GitHub repository URL
            </label>
            <input
              id="repo-url"
              type="url"
              value={repoUrl}
              onChange={(event) => setRepoUrl(event.target.value)}
              placeholder="https://github.com/owner/repository"
              className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="pr-number">
              Pull request number
            </label>
            <input
              id="pr-number"
              type="number"
              min="1"
              value={prNumber}
              onChange={(event) => setPrNumber(event.target.value)}
              placeholder="42"
              className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
              required
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="github-token">
              GitHub token <span className="text-slate-500">(optional for public repos)</span>
            </label>
            <input
              id="github-token"
              type="password"
              autoComplete="off"
              value={githubToken}
              onChange={(event) => setGithubToken(event.target.value)}
              placeholder="ghp_..."
              className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
            />
            <p className="text-xs leading-6 text-slate-500">
              For posting comments back to GitHub later, a fine-grained PAT usually needs repository access with Pull requests: Read and write, plus Issues: Read and write or Pull requests: Read and write.
            </p>
          </div>

          {error ? (
            <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>{error}</p>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={!canSubmit}
            className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 text-sm font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Start review
          </button>
        </form>
      </section>

      <aside className="space-y-5">
        <LoadingSteps steps={loadingSteps} currentStep={loading ? currentStep : -1} />

        <div className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel">
          <p className="text-sm font-semibold text-slate-900">What gets reviewed</p>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
            <li>Relevant code diffs only</li>
            <li>Secrets redacted before LLM analysis</li>
            <li>Bug, security, quality, and testing signals</li>
            <li>SQLite-backed review history for demos and replay</li>
          </ul>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white/80 p-5 shadow-panel">
          <p className="text-sm font-semibold text-slate-900">Comment posting tips</p>
          <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
            <li>Public repos can be reviewed without a token, but comment posting still needs write permissions.</li>
            <li>Fine-grained PATs should include repository access and PR comment permissions.</li>
            <li>Classic PATs usually need <code>public_repo</code> for public repos and <code>repo</code> for private repos.</li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
