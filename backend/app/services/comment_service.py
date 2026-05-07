from __future__ import annotations

import logging

from app.schemas import CommentPostingResult, CommentPreviewResponse, InlineCommentPreview, IssueFinding, ReviewResult
from app.services.github_service import GitHubService, GitHubServiceError

logger = logging.getLogger(__name__)

COMMENT_PREFIX = "[Agentic AI Code Review Bot]"
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "suggestion": 4}


class CommentService:
    def __init__(self, github_service: GitHubService | None = None) -> None:
        self.github_service = github_service or GitHubService()

    def post_review_comments(
        self,
        *,
        review: ReviewResult,
        raw_review: dict,
        github_token: str | None,
        post_inline_comments: bool,
        skip_lgtm_comment: bool,
    ) -> CommentPostingResult:
        if skip_lgtm_comment and self._should_skip_commenting(review):
            return CommentPostingResult(
                review_id=review.review_id,
                summary_comment_posted=False,
                inline_comments_posted=0,
                skipped_duplicates=0,
                message="Skipped comment posting because the review is effectively LGTM and skip_lgtm_comment is enabled.",
            )

        repo_slug = review.repo.split("/", 1)
        if len(repo_slug) != 2:
            raise GitHubServiceError("Stored review metadata is missing a valid GitHub repository slug.")
        owner, repo_name = repo_slug

        existing_issue_comments = self.github_service.list_issue_comments(owner, repo_name, review.pr_number, github_token)
        existing_review_comments = self.github_service.list_review_comments(owner, repo_name, review.pr_number, github_token)

        summary_marker = f"{COMMENT_PREFIX}\nReview ID: {review.review_id}"
        summary_exists = any(summary_marker in (comment.get("body") or "") for comment in existing_issue_comments)

        summary_posted = False
        skipped_duplicates = 1 if summary_exists else 0
        if not summary_exists:
            body = self._build_summary_comment(review)
            self.github_service.post_issue_comment(owner, repo_name, review.pr_number, body, github_token)
            summary_posted = True

        inline_comments_posted = 0
        if post_inline_comments:
            existing_review_bodies = {comment.get("body") or "" for comment in existing_review_comments}
            for issue in self._select_inline_issues(review.issues):
                if not issue.line:
                    continue
                body = self._build_inline_comment(review.review_id, issue)
                if body in existing_review_bodies:
                    skipped_duplicates += 1
                    continue
                try:
                    self.github_service.post_inline_comment(
                        owner,
                        repo_name,
                        review.pr_number,
                        body=body,
                        commit_id=raw_review.get("head_sha", ""),
                        path=issue.file,
                        line=issue.line,
                        github_token=github_token,
                    )
                    inline_comments_posted += 1
                except GitHubServiceError as exc:
                    logger.warning("Skipping inline comment for %s:%s because GitHub rejected it: %s", issue.file, issue.line, exc)

        return CommentPostingResult(
            review_id=review.review_id,
            summary_comment_posted=summary_posted,
            inline_comments_posted=inline_comments_posted,
            skipped_duplicates=skipped_duplicates,
            message="Comments processed successfully.",
        )

    def build_comment_preview(self, review: ReviewResult) -> CommentPreviewResponse:
        skip_commenting = self._should_skip_commenting(review)
        return CommentPreviewResponse(
            review_id=review.review_id,
            summary_comment=self._build_summary_comment(review),
            inline_comments=[
                InlineCommentPreview(
                    file=issue.file,
                    line=issue.line,
                    severity=issue.severity,
                    category=issue.category,
                    body=self._build_inline_comment(review.review_id, issue),
                )
                for issue in self._select_inline_issues(review.issues)
            ],
            skip_commenting=skip_commenting,
            skip_reason="This review has no actionable issues and can skip a top-level LGTM-style comment by default."
            if skip_commenting
            else None,
        )

    def _build_summary_comment(self, review: ReviewResult) -> str:
        top_issues = review.issues[:3]
        issue_lines = "\n".join(
            f"- `{issue.severity.upper()}` {issue.title} ({issue.file}{':' + str(issue.line) if issue.line else ''})"
            for issue in top_issues
        ) or "- No major issues found."
        test_suggestions = "\n".join(f"- {item}" for item in review.test_suggestions[:5]) or "- No additional test suggestions."
        positive_notes = "\n".join(f"- {item}" for item in review.positive_notes[:5]) or "- No additional positive notes."

        return (
            f"{COMMENT_PREFIX}\n"
            f"Review ID: {review.review_id}\n\n"
            f"**Score:** {review.score}/100\n"
            f"**Risk level:** {review.risk_level}\n"
            f"**Issues found:** {review.total_issues}\n\n"
            f"**Summary**\n{review.summary}\n\n"
            f"**Release Notes**\n{self._format_release_notes(review.release_notes)}\n\n"
            f"**Top Issues**\n{issue_lines}\n\n"
            f"**Suggested Tests**\n{test_suggestions}\n\n"
            f"**Positive Notes**\n{positive_notes}"
        )

    def _build_inline_comment(self, review_id: str, issue: IssueFinding) -> str:
        return (
            f"{COMMENT_PREFIX}\n"
            f"Review ID: {review_id}\n"
            f"Severity: {issue.severity}\n"
            f"Category: {issue.category}\n\n"
            f"**{issue.title}**\n"
            f"{issue.description}\n\n"
            f"Suggested fix: {issue.suggested_fix}\n"
            f"Confidence: {issue.confidence:.2f}"
        )

    def _select_inline_issues(self, issues: list[IssueFinding]) -> list[IssueFinding]:
        ranked = sorted(issues, key=lambda issue: (SEVERITY_ORDER[issue.severity], -issue.confidence))
        return [issue for issue in ranked if issue.line][:5]

    def _should_skip_commenting(self, review: ReviewResult) -> bool:
        return review.total_issues == 0 and review.risk_level == "low"

    def _format_release_notes(self, release_notes: list[str]) -> str:
        return "\n".join(f"- {note}" for note in release_notes[:5]) or "- No release notes generated."
