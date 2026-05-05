import {
  AlertCircle,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileSearch,
  Filter,
  FolderTree,
  GitPullRequest,
  Link2,
  MessageSquareShare,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api } from "../api/client";
import IssueCard from "../components/IssueCard";
import SeverityBadge from "../components/SeverityBadge";

const categories = ["all", "bug", "security", "quality", "testing", "performance"];
const severityOrder = ["critical", "high", "medium", "low", "suggestion"];
const autofixSafetyClasses = {
  safe: "border-emerald-200 bg-emerald-50 text-emerald-700",
  needs_review: "border-amber-200 bg-amber-50 text-amber-700",
  risky: "border-rose-200 bg-rose-50 text-rose-700",
};
const autofixStatusClasses = {
  generated: "border-sky-200 bg-sky-50 text-sky-700",
  failed: "border-rose-200 bg-rose-50 text-rose-700",
  disabled: "border-slate-200 bg-slate-100 text-slate-600",
};

const permissionTips = [
  "Fine-grained PATs should have repository access plus Pull requests: Read and write.",
  "If the summary comment fails, add Issues: Read and write or Pull requests: Read and write as well.",
  "Classic PATs usually need public_repo for public repos and repo for private repos.",
];

function isPermissionError(message) {
  return message?.toLowerCase().includes("resource not accessible by personal access token");
}

export default function ReviewResult() {
  const { reviewId } = useParams();
  const location = useLocation();
  const [review, setReview] = useState(location.state?.review || null);
  const [details, setDetails] = useState(null);
  const [commentPreview, setCommentPreview] = useState(null);
  const [autofixState, setAutofixState] = useState({
    loading: true,
    regenerating: false,
    error: "",
    enabled: true,
    message: "",
    drafts: [],
  });
  const [githubToken] = useState(location.state?.githubToken || "");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [postInlineComments, setPostInlineComments] = useState(true);
  const [postingState, setPostingState] = useState({ loading: false, message: "", error: "" });
  const [copyState, setCopyState] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!review) {
      api
        .getReview(reviewId)
        .then(setReview)
        .catch((err) => setError(err.message));
    }

    api.getReviewDetails(reviewId).then(setDetails).catch(() => {});
    api.getCommentPreview(reviewId).then(setCommentPreview).catch(() => {});
    api
      .getAutofixDrafts(reviewId)
      .then((response) =>
        setAutofixState({
          loading: false,
          regenerating: false,
          error: "",
          enabled: response.enabled,
          message: response.message,
          drafts: response.drafts || [],
        })
      )
      .catch((err) =>
        setAutofixState((current) => ({
          ...current,
          loading: false,
          regenerating: false,
          error: err.message,
        }))
      );
  }, [review, reviewId]);

  const filteredIssues = useMemo(() => {
    if (!review) {
      return [];
    }

    const normalizedQuery = searchQuery.trim().toLowerCase();
    return review.issues.filter((issue) => {
      const matchesCategory = categoryFilter === "all" || issue.category === categoryFilter;
      if (!matchesCategory) {
        return false;
      }
      if (!normalizedQuery) {
        return true;
      }
      const haystack = [issue.file, issue.title, issue.description, issue.suggested_fix, issue.category, issue.severity]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [categoryFilter, review, searchQuery]);

  const groupedIssues = useMemo(
    () =>
      severityOrder.reduce((groups, severity) => {
        groups[severity] = filteredIssues.filter((issue) => issue.severity === severity);
        return groups;
      }, {}),
    [filteredIssues]
  );

  const issueTotals = useMemo(
    () =>
      severityOrder.reduce((totals, severity) => {
        totals[severity] = review?.issues.filter((issue) => issue.severity === severity).length || 0;
        return totals;
      }, {}),
    [review]
  );

  const issueById = useMemo(() => {
    const map = new Map();
    (review?.issues || []).forEach((issue) => {
      if (issue.id) {
        map.set(issue.id, issue);
      }
    });
    return map;
  }, [review]);

  async function handlePostComments() {
    if (!review) {
      return;
    }
    setPostingState({ loading: true, message: "", error: "" });
    try {
      const result = await api.postComments(review.review_id, {
        github_token: githubToken || undefined,
        post_inline_comments: postInlineComments,
      });
      setPostingState({
        loading: false,
        message: `${result.message} Summary posted: ${result.summary_comment_posted ? "yes" : "already existed"}, inline comments: ${result.inline_comments_posted}, duplicates skipped: ${result.skipped_duplicates}.`,
        error: "",
      });
    } catch (err) {
      setPostingState({ loading: false, message: "", error: err.message });
    }
  }

  function copyText(text, label) {
    navigator.clipboard.writeText(text).then(() => {
      setCopyState(`${label} copied`);
      window.setTimeout(() => setCopyState(""), 1800);
    });
  }

  function downloadReviewBundle() {
    if (!review) {
      return;
    }
    const payload = {
      review,
      details,
      comment_preview: commentPreview,
      autofix: {
        enabled: autofixState.enabled,
        message: autofixState.message,
        drafts: autofixState.drafts,
      },
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${review.repo.replace("/", "_")}_pr_${review.pr_number}_review.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function handleRegenerateAutofix() {
    setAutofixState((current) => ({
      ...current,
      regenerating: true,
      error: "",
    }));
    try {
      const response = await api.regenerateAutofixDrafts(reviewId);
      setAutofixState({
        loading: false,
        regenerating: false,
        error: "",
        enabled: response.enabled,
        message: response.message,
        drafts: response.drafts || [],
      });
    } catch (err) {
      setAutofixState((current) => ({
        ...current,
        regenerating: false,
        error: err.message,
      }));
    }
  }

  function downloadPatch(draft) {
    if (!draft.patch_text) {
      return;
    }
    const blob = new Blob([draft.patch_text], { type: "text/x-diff" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${draft.file.replaceAll("/", "_")}-${draft.issue_id}.patch`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  if (error) {
    return <p className="text-sm text-rose-700">{error}</p>;
  }

  if (!review) {
    return <p className="text-sm text-slate-600">Loading review...</p>;
  }

  const riskBadgeSeverity =
    review.risk_level === "high" ? "critical" : review.risk_level === "medium" ? "medium" : "low";

  return (
    <div className="space-y-10">
      <section className="border-b border-slate-200 pb-8">
        <div className="flex flex-col gap-8 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-4xl space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <SeverityBadge severity={riskBadgeSeverity} />
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                Score {review.score}/100
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                {review.total_files_reviewed} files reviewed
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-700">
                {review.total_issues} issues
              </span>
            </div>

            <div className="space-y-3">
              <p className="text-sm text-slate-500">{review.repo}</p>
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
                PR #{review.pr_number}: {review.pr_title}
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-slate-700">{review.summary}</p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {details?.pr_url ? (
                <a
                  href={details.pr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open PR
                </a>
              ) : null}
              <button
                onClick={() => copyText(review.summary, "Summary")}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                <Copy className="h-4 w-4" />
                Copy summary
              </button>
              <button
                onClick={downloadReviewBundle}
                className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                <Download className="h-4 w-4" />
                Export JSON
              </button>
              {copyState ? <span className="text-xs text-sky-700">{copyState}</span> : null}
            </div>
          </div>

          <div className="w-full max-w-md space-y-3">
            <button
              onClick={handlePostComments}
              disabled={postingState.loading}
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-sky-500 px-5 text-sm font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
            >
              <MessageSquareShare className="h-4 w-4" />
              {postingState.loading ? "Posting..." : "Post comments to GitHub"}
            </button>
            <label className="inline-flex h-11 items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={postInlineComments}
                onChange={(event) => setPostInlineComments(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 bg-white text-sky-500 focus:ring-sky-400"
              />
              Post inline comments
            </label>
          </div>
        </div>
      </section>

      {postingState.message ? (
        <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{postingState.message}</p>
        </div>
      ) : null}

      {postingState.error ? (
        <div className="space-y-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{postingState.error}</p>
          </div>
          {isPermissionError(postingState.error) ? (
            <div className="rounded-lg border border-slate-200 bg-white/80 p-4">
              <p className="text-sm font-semibold text-slate-900">GitHub token fix</p>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                {permissionTips.map((tip) => (
                  <li key={tip}>{tip}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-4">
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <GitPullRequest className="h-5 w-5 text-sky-700" />
            <p className="text-sm font-semibold text-slate-900">Risk snapshot</p>
          </div>
          <p className="mt-4 text-3xl font-semibold capitalize text-slate-900">{review.risk_level}</p>
          <p className="mt-2 text-sm text-slate-500">Created {new Date(review.created_at).toLocaleString()}</p>
        </article>
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-amber-600" />
            <p className="text-sm font-semibold text-slate-900">Severity mix</p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {severityOrder.map((severity) => (
              <span key={severity} className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-700">
                {severity}: {issueTotals[severity]}
              </span>
            ))}
          </div>
        </article>
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <FolderTree className="h-5 w-5 text-rose-600" />
            <p className="text-sm font-semibold text-slate-900">Changed modules</p>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {(details?.changed_modules || []).length ? (
              details.changed_modules.map((module) => (
                <span key={module} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-700">
                  {module}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-500">No module summary stored.</span>
            )}
          </div>
        </article>
        <article className="panel p-5">
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-violet-600" />
            <p className="text-sm font-semibold text-slate-900">Preview ready</p>
          </div>
          <p className="mt-4 text-3xl font-semibold text-slate-900">{commentPreview?.inline_comments?.length || 0}</p>
          <p className="mt-2 text-sm text-slate-500">Inline comments available to inspect below before posting.</p>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(360px,1fr)]">
        <div className="panel p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Filter className="h-4 w-4" />
            Filter findings
          </div>
          <div className="mt-4 flex flex-col gap-4">
            <div className="relative">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search by file, title, description, or fix"
                className="h-11 w-full rounded-lg border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-sky-300"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {categories.map((category) => (
                <button
                  key={category}
                  onClick={() => setCategoryFilter(category)}
                  className={`inline-flex h-9 items-center rounded-lg px-3 text-sm font-medium capitalize transition ${
                    categoryFilter === category
                      ? "bg-sky-500 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="panel p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Link2 className="h-4 w-4" />
            Review workflow
          </div>
          <div className="mt-4 space-y-3">
            {(details?.review_plan || []).length ? (
              details.review_plan.map((item) => (
                <div key={`${item.agent}-${item.reason}`} className="rounded-lg border border-slate-200 bg-slate-50/85 p-4">
                  <p className="text-sm font-semibold capitalize text-slate-900">{item.agent} agent</p>
                  <p className="mt-1 text-sm leading-6 text-slate-700">{item.reason}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No explicit planning metadata stored for this review.</p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="panel p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <FileSearch className="h-4 w-4" />
            Reviewed files
          </div>
          <div className="mt-4 space-y-3">
            {(details?.reviewed_files || []).length ? (
              details.reviewed_files.map((file) => (
                <div key={file.filename} className="rounded-lg border border-slate-200 bg-slate-50/85 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">{file.filename}</p>
                    <span className="rounded-full border border-slate-200 px-3 py-1 text-xs uppercase tracking-wide text-slate-600">
                      {file.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-500">
                    +{file.additions} / -{file.deletions} / {file.changes} total changed lines
                  </p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No reviewed file metadata available.</p>
            )}
          </div>
        </div>

        <div className="panel p-6">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <AlertCircle className="h-4 w-4" />
            Skipped files and workflow notes
          </div>
          <div className="mt-4 space-y-4">
            <div className="space-y-3">
              {(details?.skipped_files || []).length ? (
                details.skipped_files.slice(0, 12).map((file) => (
                  <div key={`${file.filename}-${file.reason}`} className="rounded-lg border border-slate-200 bg-slate-50/85 p-4">
                    <p className="text-sm font-semibold text-slate-900">{file.filename}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{file.reason || "Skipped by filter."}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">No skipped files were recorded.</p>
              )}
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/85 p-4">
              <p className="text-sm font-semibold text-slate-900">Workflow notes</p>
              <div className="mt-3 space-y-2">
                {(details?.workflow_notes || []).length ? (
                  details.workflow_notes.map((note) => (
                    <p key={note} className="text-sm leading-6 text-slate-700">
                      {note}
                    </p>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No workflow notes available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="space-y-8">
        {severityOrder.map((severity) => (
          <div key={severity} className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <SeverityBadge severity={severity} />
                <h2 className="text-xl font-semibold capitalize text-slate-900">{severity}</h2>
              </div>
              <span className="text-sm text-slate-500">{groupedIssues[severity]?.length || 0} items</span>
            </div>

            {groupedIssues[severity]?.length ? (
              <div className="grid gap-4">
                {groupedIssues[severity].map((issue, index) => (
                  <div key={`${issue.file}-${issue.line}-${index}`} id={issue.id ? `issue-${issue.id}` : undefined}>
                    <IssueCard issue={issue} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-5 text-sm text-slate-500">
                No {severity} issues in the current filter.
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="panel p-6">
          <h2 className="text-xl font-semibold text-slate-900">Test suggestions</h2>
          <div className="mt-4 space-y-3">
            {review.test_suggestions.length ? (
              review.test_suggestions.map((item) => (
                <div key={item} className="rounded-lg border border-slate-200 bg-slate-50/85 p-4 text-sm leading-6 text-slate-700">
                  {item}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No extra test suggestions were generated for this diff.</p>
            )}
          </div>
        </div>

        <div className="panel p-6">
          <h2 className="text-xl font-semibold text-slate-900">Positive notes</h2>
          <div className="mt-4 space-y-3">
            {review.positive_notes.length ? (
              review.positive_notes.map((item) => (
                <div key={item} className="rounded-lg border border-slate-200 bg-slate-50/85 p-4 text-sm leading-6 text-slate-700">
                  {item}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">No positive notes were recorded for this review.</p>
            )}
          </div>
        </div>

      </section>

      <section className="panel p-6">
        <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Autofix drafts</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              High-confidence findings can be turned into reviewable patch drafts. These are suggestions only and always require human review before use.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                autofixState.enabled ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-100 text-slate-600"
              }`}
            >
              {autofixState.enabled ? "Autofix enabled" : "Autofix disabled"}
            </span>
            <button
              onClick={handleRegenerateAutofix}
              disabled={autofixState.regenerating || !autofixState.enabled}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
            >
              <RefreshCw className={`h-4 w-4 ${autofixState.regenerating ? "animate-spin" : ""}`} />
              {autofixState.regenerating ? "Regenerating..." : "Regenerate drafts"}
            </button>
          </div>
        </div>

        <div className="mt-6 space-y-5">
          {autofixState.loading ? (
            <p className="text-sm text-slate-500">Loading autofix drafts...</p>
          ) : null}

          {!autofixState.loading && autofixState.message ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50/85 p-4 text-sm text-slate-700">
              {autofixState.message}
            </div>
          ) : null}

          {autofixState.error ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {autofixState.error}
            </div>
          ) : null}

          {!autofixState.loading && !autofixState.drafts.length ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-5 text-sm text-slate-500">
              No autofix drafts are available for this review yet.
            </div>
          ) : null}

          {autofixState.drafts.length ? (
            <div className="grid gap-4">
              {autofixState.drafts.map((draft) => {
                const linkedIssue = issueById.get(draft.issue_id);
                return (
                  <article key={draft.id} className="rounded-xl border border-slate-200 bg-white/90 p-5 shadow-panel">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${
                              autofixSafetyClasses[draft.safety_level] || autofixSafetyClasses.needs_review
                            }`}
                          >
                            {draft.safety_level.replaceAll("_", " ")}
                          </span>
                          <span
                            className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${
                              autofixStatusClasses[draft.status] || autofixStatusClasses.generated
                            }`}
                          >
                            {draft.status.replaceAll("_", " ")}
                          </span>
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                            {draft.file}
                            {draft.line ? `:${draft.line}` : ""}
                          </span>
                          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                            {Math.round(draft.confidence * 100)}% confidence
                          </span>
                        </div>

                        <div>
                          <h3 className="text-lg font-semibold text-slate-900">{draft.fix_title}</h3>
                          <p className="mt-2 text-sm leading-6 text-slate-700">{draft.rationale}</p>
                        </div>

                        <div className="rounded-lg border border-slate-200 bg-slate-50/85 p-4">
                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Linked finding</p>
                          {linkedIssue ? (
                            <div className="mt-2 flex flex-wrap items-center gap-3">
                              <a
                                href={`#issue-${linkedIssue.id}`}
                                className="text-sm font-semibold text-sky-700 hover:text-sky-800"
                              >
                                {linkedIssue.title}
                              </a>
                              <span className="text-xs text-slate-500">
                                {linkedIssue.file}
                                {linkedIssue.line ? `:${linkedIssue.line}` : ""}
                              </span>
                            </div>
                          ) : (
                            <p className="mt-2 text-sm text-slate-600">The source issue is not available in the current view, but this draft is still tied to the stored review finding.</p>
                          )}
                        </div>

                        {draft.status === "failed" && draft.error_message ? (
                          <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                            {draft.error_message}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex shrink-0 flex-wrap items-center gap-2">
                        <button
                          onClick={() => copyText(draft.patch_text || "", `${draft.fix_title} patch`)}
                          disabled={!draft.patch_text}
                          className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          <Copy className="h-4 w-4" />
                          Copy patch
                        </button>
                        <button
                          onClick={() => downloadPatch(draft)}
                          disabled={!draft.patch_text}
                          className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                        >
                          <Download className="h-4 w-4" />
                          Export patch
                        </button>
                      </div>
                    </div>

                    <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50/85 p-4">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-slate-900">Unified diff draft</p>
                        <span className="text-xs text-slate-500">{draft.patch_format}</span>
                      </div>
                      {draft.patch_text ? (
                        <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                          {draft.patch_text}
                        </pre>
                      ) : (
                        <div className="rounded-lg border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
                          No patch text is available for this draft.
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel p-6">
        <div className="flex flex-col gap-3 border-b border-slate-200 pb-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-slate-900">Comment preview</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Review the exact GitHub summary and inline comments here before posting anything back to the pull request.
            </p>
          </div>
          {commentPreview ? (
            <button
              onClick={() => copyText(commentPreview.summary_comment, "Summary comment")}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              <Copy className="h-4 w-4" />
              Copy summary comment
            </button>
          ) : null}
        </div>

        <div className="mt-6 space-y-6">
          {commentPreview ? (
            <>
              <div className="rounded-lg border border-slate-200 bg-slate-50/85 p-5">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Summary comment</p>
                    <p className="mt-1 text-xs text-slate-500">This is the top-level PR comment the bot will try to publish.</p>
                  </div>
                  <span className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600">
                    {commentPreview.inline_comments.length} inline preview item(s)
                  </span>
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-700">
                  {commentPreview.summary_comment}
                </pre>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">Inline comment previews</p>
                    <p className="mt-1 text-xs text-slate-500">These are the targeted comments that require line-level GitHub permissions.</p>
                  </div>
                </div>

                {commentPreview.inline_comments.length ? (
                  <div className="grid gap-4">
                    {commentPreview.inline_comments.map((item, index) => (
                      <div key={`${item.file}-${item.line}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50/85 p-5">
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                          <div className="flex flex-wrap items-center gap-2">
                            <SeverityBadge severity={item.severity} />
                            <span className="rounded-full border border-slate-200 px-3 py-1 text-xs capitalize text-slate-600">{item.category}</span>
                            <span className="text-xs text-slate-500">
                              {item.file}
                              {item.line ? `:${item.line}` : ""}
                            </span>
                          </div>
                          <button
                            onClick={() => copyText(item.body, `${item.file}${item.line ? `:${item.line}` : ""} comment`)}
                            className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                          >
                            <Copy className="h-3.5 w-3.5" />
                            Copy inline comment
                          </button>
                        </div>
                        <pre className="mt-4 overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-700">
                          {item.body}
                        </pre>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-slate-200 bg-white/70 p-5 text-sm text-slate-500">
                    No inline comment previews are available for this review.
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Comment preview not available yet.</p>
          )}
        </div>
      </section>

      <div className="flex items-center justify-between border-t border-slate-200 pt-6">
        <Link to="/history" className="text-sm font-medium text-sky-700 hover:text-sky-800">
          Back to review history
        </Link>
        <Link to="/reviews/new" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900">
          Start another review
          <ExternalLink className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
