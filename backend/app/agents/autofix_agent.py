from __future__ import annotations

import logging
import re
from uuid import uuid4

from app.schemas import AutoFixDraft, AutoFixDraftGenerationOutput, IssueFinding
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class AutofixAgent:
    def __init__(self, llm_service: LLMService, *, max_patch_chars: int) -> None:
        self.llm_service = llm_service
        self.max_patch_chars = max_patch_chars

    def generate_draft(
        self,
        *,
        review_id: str,
        repo: str,
        pr_title: str,
        issue: IssueFinding,
        numbered_patch: str,
    ) -> AutoFixDraft:
        system_prompt = (
            "You are a senior software engineer generating a candidate patch draft for a single pull request finding. "
            "Return one unified diff only. Keep the patch minimal, realistic, and limited to the referenced file. "
            "Do not invent files not already in the diff."
        )
        user_prompt = (
            f"Repository: {repo}\n"
            f"Pull request: {pr_title}\n"
            f"Issue reference: {issue.id}\n"
            f"File: {issue.file}\n"
            f"Line: {issue.line}\n"
            f"Severity: {issue.severity}\n"
            f"Category: {issue.category}\n"
            f"Title: {issue.title}\n"
            f"Description: {issue.description}\n"
            f"Suggested fix: {issue.suggested_fix}\n\n"
            "Produce a candidate unified diff patch that fixes the issue in that file. "
            "The patch must start with ---/+++ headers and include at least one @@ hunk.\n\n"
            f"Relevant file patch with current line numbers:\n{numbered_patch[:20000]}"
        )

        try:
            output = self.llm_service.generate_structured(
                task_name="autofix_patch",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=AutoFixDraftGenerationOutput,
            )
            normalized_patch = self._validate_patch(output.patch_text, issue.file)
            confidence = min(output.confidence, 0.99)
            return AutoFixDraft(
                id=str(uuid4()),
                issue_id=issue.id or str(uuid4()),
                file=issue.file,
                line=issue.line,
                fix_title=output.fix_title,
                rationale=output.rationale,
                patch_format=output.patch_format,
                patch_text=normalized_patch[: self.max_patch_chars],
                confidence=confidence,
                safety_level=output.safety_level,
                status="generated",
                error_message=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Autofix generation failed for %s:%s: %s", issue.file, issue.line, exc)
            return AutoFixDraft(
                id=str(uuid4()),
                issue_id=issue.id or str(uuid4()),
                file=issue.file,
                line=issue.line,
                fix_title=f"Autofix unavailable for {issue.title}",
                rationale="The autofix agent could not produce a trustworthy patch draft for this issue.",
                patch_format="unified_diff",
                patch_text=None,
                confidence=0.0,
                safety_level="risky",
                status="failed",
                error_message=str(exc),
            )

    def _validate_patch(self, patch_text: str, expected_file: str) -> str:
        normalized = patch_text.strip()
        if not normalized:
            raise ValueError("Autofix patch was empty.")
        if not normalized.startswith("--- "):
            raise ValueError("Autofix patch did not start with a unified diff header.")
        if "\n+++ " not in normalized or "\n@@ " not in normalized:
            raise ValueError("Autofix patch did not contain required unified diff sections.")
        if expected_file not in normalized:
            raise ValueError("Autofix patch did not reference the expected file.")

        hunk_headers = re.findall(r"^@@ .+ @@$", normalized, flags=re.MULTILINE)
        if not hunk_headers:
            raise ValueError("Autofix patch did not include a valid hunk header.")
        return normalized
