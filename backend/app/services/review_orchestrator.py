from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.aggregator_agent import FinalReviewAggregatorAgent
from app.agents.autofix_agent import AutofixAgent
from app.agents.bug_agent import BugDetectionAgent
from app.agents.common import build_review_payload
from app.agents.diff_summary_agent import DiffSummaryAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.quality_agent import CodeQualityAgent
from app.agents.security_agent import SecurityReviewAgent
from app.agents.test_agent import TestSuggestionAgent
from app.config import get_settings
from app.schemas import AutoFixDraft, DiffSummaryOutput, FindingsOutput, IssueFinding, ReviewPlanOutput, ReviewResult, TestSuggestionOutput
from app.services.github_service import GitHubService, PullRequestContext
from app.services.llm_service import LLMResponseError, LLMService

logger = logging.getLogger(__name__)


SEVERITY_PENALTIES = {
    "critical": 20,
    "high": 12,
    "medium": 7,
    "low": 3,
    "suggestion": 1,
}


class ReviewOrchestrator:
    def __init__(self, github_service: GitHubService | None = None, llm_service: LLMService | None = None) -> None:
        self.settings = get_settings()
        self.github_service = github_service or GitHubService()
        self.llm_service = llm_service or LLMService()
        self.diff_summary_agent = DiffSummaryAgent(self.llm_service)
        self.planning_agent = PlanningAgent(self.llm_service)
        self.bug_agent = BugDetectionAgent(self.llm_service)
        self.security_agent = SecurityReviewAgent(self.llm_service)
        self.quality_agent = CodeQualityAgent(self.llm_service)
        self.test_agent = TestSuggestionAgent(self.llm_service)
        self.aggregator_agent = FinalReviewAggregatorAgent(self.llm_service)
        self.autofix_agent = AutofixAgent(self.llm_service, max_patch_chars=self.settings.autofix_max_patch_chars)

    def run_review(self, *, repo_url: str, pr_number: int, github_token: str | None = None) -> tuple[ReviewResult, dict]:
        context = self.github_service.get_pull_request_context(repo_url, pr_number, github_token)
        review_id = str(uuid4())
        created_at = datetime.now(timezone.utc)

        if not context.reviewable_files:
            result = ReviewResult(
                review_id=review_id,
                repo=context.repo_slug,
                pr_number=context.pr_number,
                pr_title=context.pr_title,
                summary="No supported code files were available in this PR diff, so the bot skipped AI analysis.",
                risk_level="low",
                score=100,
                total_files_reviewed=0,
                total_issues=0,
                issues=[],
                test_suggestions=[],
                positive_notes=["The PR only changed ignored, generated, binary, or otherwise unsupported files."],
                created_at=created_at,
            )
            raw = self._build_raw_result(
                context,
                result,
                changed_modules=[],
                plan=[],
                workflow_notes=["No reviewable files found."],
                autofix_drafts=[],
            )
            return result, raw

        review_payload = build_review_payload(context, self.settings.max_total_patch_chars)
        diff_summary = self._run_diff_summary(review_payload, context)
        review_plan = self._run_planning(review_payload, diff_summary, context)
        issues, positive_notes, test_suggestions, workflow_notes = self._run_specialists(
            review_payload=review_payload,
            diff_summary=diff_summary,
            review_plan=review_plan,
        )

        issues = self._dedupe_issues(issues)
        issues = self._assign_issue_ids(issues)
        score = self._calculate_score(issues)
        risk_level = self._calculate_risk_level(score, issues)

        final_summary, final_positive_notes, final_test_suggestions = self._finalize_narrative(
            diff_summary=diff_summary,
            issues=issues,
            test_suggestions=test_suggestions,
            positive_notes=positive_notes,
        )

        result = ReviewResult(
            review_id=review_id,
            repo=context.repo_slug,
            pr_number=context.pr_number,
            pr_title=context.pr_title,
            summary=final_summary,
            risk_level=risk_level,
            score=score,
            total_files_reviewed=len(context.reviewable_files),
            total_issues=len(issues),
            issues=issues,
            test_suggestions=final_test_suggestions,
            positive_notes=final_positive_notes,
            created_at=created_at,
        )
        autofix_drafts = self._generate_autofix_drafts(
            review_id=review_id,
            repo=context.repo_slug,
            pr_title=context.pr_title,
            issues=issues,
            patch_map=self._build_patch_map_from_context(context),
        )
        workflow_notes.append(
            f"autofix agent produced {sum(1 for draft in autofix_drafts if draft.status == 'generated')} generated draft(s)."
        )
        raw = self._build_raw_result(
            context,
            result,
            changed_modules=diff_summary.changed_modules,
            plan=[item.model_dump() for item in review_plan.review_plan],
            workflow_notes=workflow_notes,
            autofix_drafts=autofix_drafts,
        )
        return result, raw

    def regenerate_autofix_for_review(self, review: ReviewResult, raw_review: dict) -> list[AutoFixDraft]:
        if not self.settings.autofix_enabled:
            return []

        stored_files = raw_review.get("reviewed_files", [])
        patch_map = {
            item["filename"]: item.get("numbered_patch", "")
            for item in stored_files
            if item.get("numbered_patch")
        }
        if not patch_map:
            raise LLMResponseError("This review does not contain stored diff context required for autofix regeneration.")

        return self._generate_autofix_drafts(
            review_id=review.review_id,
            repo=review.repo,
            pr_title=review.pr_title,
            issues=review.issues,
            patch_map=patch_map,
        )

    def _run_diff_summary(self, review_payload: str, context: PullRequestContext) -> DiffSummaryOutput:
        try:
            return self.diff_summary_agent.run(review_payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Diff summary agent fell back to heuristics: %s", exc)
            modules = sorted({file.filename.split("/")[0] for file in context.reviewable_files})
            heuristic_risk = "high" if len(context.reviewable_files) > 10 else "medium" if len(context.reviewable_files) > 4 else "low"
            return DiffSummaryOutput(
                summary=f"This PR updates {len(context.reviewable_files)} reviewable files across {', '.join(modules[:5]) or 'the repository'}.",
                changed_modules=modules[:10],
                risk_level=heuristic_risk,
            )

    def _run_planning(
        self,
        review_payload: str,
        diff_summary: DiffSummaryOutput,
        context: PullRequestContext,
    ) -> ReviewPlanOutput:
        try:
            plan = self.planning_agent.run(review_payload, diff_summary.summary)
            if plan.review_plan:
                return plan
        except Exception as exc:  # noqa: BLE001
            logger.warning("Planning agent fell back to heuristics: %s", exc)

        plan = [{"agent": "bug", "reason": "Every code diff should receive a bug pass."}, {"agent": "quality", "reason": "Maintainability checks are always useful."}]
        joined_filenames = " ".join(file.filename.lower() for file in context.reviewable_files)
        if any(keyword in joined_filenames for keyword in ["auth", "login", "security", "api", "config", "middleware"]):
            plan.append({"agent": "security", "reason": "The diff touches auth, API, or configuration surfaces."})
        if any(file.filename.endswith(testable_ext) for file in context.reviewable_files for testable_ext in (".py", ".js", ".ts", ".tsx", ".jsx")):
            plan.append({"agent": "testing", "reason": "Executable application code changed, so test coverage should be reviewed."})
        return ReviewPlanOutput.model_validate({"review_plan": plan})

    def _run_specialists(
        self,
        *,
        review_payload: str,
        diff_summary: DiffSummaryOutput,
        review_plan: ReviewPlanOutput,
    ) -> tuple[list[IssueFinding], list[str], list[str], list[str]]:
        issues: list[IssueFinding] = []
        positive_notes: list[str] = []
        test_suggestions: list[str] = []
        workflow_notes: list[str] = []
        successful_specialists = 0

        agents = {item.agent for item in review_plan.review_plan}
        if not agents:
            agents = {"bug", "quality", "testing"}

        def capture_findings(output: FindingsOutput, agent_name: str) -> None:
            nonlocal successful_specialists
            successful_specialists += 1
            issues.extend(output.issues)
            positive_notes.extend(output.positive_notes)
            workflow_notes.append(f"{agent_name} agent completed with {len(output.issues)} issues.")

        for agent_name in sorted(agents):
            try:
                if agent_name == "bug":
                    capture_findings(self.bug_agent.run(review_payload, diff_summary.summary), "bug")
                elif agent_name == "security":
                    capture_findings(self.security_agent.run(review_payload, diff_summary.summary), "security")
                elif agent_name == "quality":
                    capture_findings(self.quality_agent.run(review_payload, diff_summary.summary), "quality")
                elif agent_name == "testing":
                    output = self.test_agent.run(review_payload, diff_summary.summary)
                    successful_specialists += 1
                    test_suggestions.extend(output.test_suggestions)
                    positive_notes.extend(output.positive_notes)
                    workflow_notes.append(f"testing agent completed with {len(output.test_suggestions)} suggestions.")
            except Exception as exc:  # noqa: BLE001
                workflow_notes.append(f"{agent_name} agent failed: {exc}")
                logger.warning("%s agent failed: %s", agent_name, exc)

        if successful_specialists == 0:
            raise LLMResponseError("All specialist review agents failed. No trustworthy review could be produced.")

        return issues, positive_notes, test_suggestions, workflow_notes

    def _dedupe_issues(self, issues: list[IssueFinding]) -> list[IssueFinding]:
        deduped: dict[tuple, IssueFinding] = {}
        for issue in issues:
            key = (
                issue.file,
                issue.line,
                issue.severity,
                issue.category,
                issue.title.strip().lower(),
            )
            existing = deduped.get(key)
            if not existing or issue.confidence > existing.confidence:
                deduped[key] = issue

        ordered = sorted(
            deduped.values(),
            key=lambda item: (
                ["critical", "high", "medium", "low", "suggestion"].index(item.severity),
                item.file,
                item.line or 0,
            ),
        )
        return ordered

    def _assign_issue_ids(self, issues: list[IssueFinding]) -> list[IssueFinding]:
        assigned: list[IssueFinding] = []
        for issue in issues:
            issue_key = f"{issue.file}|{issue.line}|{issue.category}|{issue.title.strip().lower()}"
            issue_id = issue.id or f"issue_{hashlib.sha1(issue_key.encode('utf-8')).hexdigest()[:12]}"
            assigned.append(issue.model_copy(update={"id": issue_id}))
        return assigned

    def _calculate_score(self, issues: list[IssueFinding]) -> int:
        score = 100
        for issue in issues:
            score -= SEVERITY_PENALTIES.get(issue.severity, 0)
        return max(score, 0)

    def _calculate_risk_level(self, score: int, issues: list[IssueFinding]) -> str:
        if any(issue.severity == "critical" for issue in issues) or score < 60:
            return "high"
        if 60 <= score <= 80:
            return "medium"
        return "low"

    def _finalize_narrative(
        self,
        *,
        diff_summary: DiffSummaryOutput,
        issues: list[IssueFinding],
        test_suggestions: list[str],
        positive_notes: list[str],
    ) -> tuple[str, list[str], list[str]]:
        deduped_positive_notes = self._dedupe_strings(positive_notes)
        deduped_test_suggestions = self._dedupe_strings(test_suggestions)

        try:
            aggregated = self.aggregator_agent.run(
                summary=diff_summary.summary,
                issues=issues,
                test_suggestions=deduped_test_suggestions,
                specialist_positive_notes=deduped_positive_notes,
            )
            summary = aggregated.summary
            positive = self._dedupe_strings(aggregated.positive_notes or deduped_positive_notes)
            tests = self._dedupe_strings(aggregated.test_suggestions or deduped_test_suggestions)
            return summary, positive, tests
        except Exception as exc:  # noqa: BLE001
            logger.warning("Aggregator agent fell back to local summary: %s", exc)

        if issues:
            summary = f"{diff_summary.summary} The automated review found {len(issues)} actionable issue(s)."
        else:
            summary = f"{diff_summary.summary} The automated review did not find major issues in the supported diff."

        if not deduped_positive_notes and not issues:
            deduped_positive_notes = ["The changed code looks coherent in the reviewed diff and did not raise major concerns."]

        return summary, deduped_positive_notes, deduped_test_suggestions

    def _build_raw_result(
        self,
        context: PullRequestContext,
        result: ReviewResult,
        *,
        changed_modules: list[str],
        plan: list[dict],
        workflow_notes: list[str],
        autofix_drafts: list[AutoFixDraft],
    ) -> dict:
        return {
            **result.model_dump(mode="json"),
            "repo_url": context.repo_url,
            "pr_url": context.pr_url,
            "head_sha": context.head_sha,
            "base_sha": context.base_sha,
            "changed_modules": changed_modules,
            "review_plan": plan,
            "workflow_notes": workflow_notes,
            "reviewed_files": [
                {
                    "filename": file.filename,
                    "status": file.status,
                    "additions": file.additions,
                    "deletions": file.deletions,
                    "changes": file.changes,
                    "numbered_patch": file.numbered_patch,
                }
                for file in context.reviewable_files
            ],
            "skipped_files": [
                {"filename": file.filename, "reason": file.skip_reason}
                for file in context.files
                if not file.is_reviewable
            ],
            "autofix_drafts": [draft.model_dump(mode="json") for draft in autofix_drafts],
        }

    def _dedupe_strings(self, items: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = item.strip()
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                ordered.append(normalized)
        return ordered[:10]

    def _build_patch_map_from_context(self, context: PullRequestContext) -> dict[str, str]:
        return {file.filename: file.numbered_patch for file in context.reviewable_files if file.numbered_patch}

    def _generate_autofix_drafts(
        self,
        *,
        review_id: str,
        repo: str,
        pr_title: str,
        issues: list[IssueFinding],
        patch_map: dict[str, str],
    ) -> list[AutoFixDraft]:
        if not self.settings.autofix_enabled:
            return []

        eligible_issues = [
            issue
            for issue in issues
            if self._is_autofix_eligible(issue, patch_map)
        ][: self.settings.autofix_max_issues_per_review]

        drafts: list[AutoFixDraft] = []
        for issue in eligible_issues:
            drafts.append(
                self.autofix_agent.generate_draft(
                    review_id=review_id,
                    repo=repo,
                    pr_title=pr_title,
                    issue=issue,
                    numbered_patch=patch_map[issue.file],
                )
            )
        return drafts

    def _is_autofix_eligible(self, issue: IssueFinding, patch_map: dict[str, str]) -> bool:
        if issue.confidence < self.settings.autofix_min_confidence:
            return False
        if issue.category not in {"bug", "quality", "security"}:
            return False
        if issue.file not in patch_map:
            return False

        combined_text = " ".join([issue.title, issue.description, issue.suggested_fix]).lower()
        vague_markers = ["architecture", "broad refactor", "policy", "organization-wide", "monitoring", "deployment"]
        if any(marker in combined_text for marker in vague_markers):
            return False

        if issue.category == "security":
            local_fix_markers = ["sanitize", "escape", "validate", "auth", "token", "secret", "sql", "query", "cors", "header"]
            if not any(marker in combined_text for marker in local_fix_markers):
                return False

        return True
