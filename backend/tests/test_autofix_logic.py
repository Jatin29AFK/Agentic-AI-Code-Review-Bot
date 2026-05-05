from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.autofix_agent import AutofixAgent
from app.schemas import AutoFixDraft, IssueFinding
from app.services.review_orchestrator import ReviewOrchestrator


class StubLLMService:
    def __init__(self, payload):
        self.payload = payload

    def generate_structured(self, **kwargs):
        response_model = kwargs["response_model"]
        return response_model.model_validate(self.payload)


class AutofixLogicTests(unittest.TestCase):
    def test_autofix_schema_accepts_valid_draft(self):
        draft = AutoFixDraft.model_validate(
            {
                "id": "draft-1",
                "issue_id": "issue-1",
                "file": "app/service.py",
                "line": 12,
                "fix_title": "Guard missing input",
                "rationale": "The branch should return early when the payload is missing.",
                "patch_format": "unified_diff",
                "patch_text": "--- a/app/service.py\n+++ b/app/service.py\n@@ -1,2 +1,3 @@\n-print('x')\n+if not payload:\n+    return None\n print('x')",
                "confidence": 0.91,
                "safety_level": "needs_review",
                "status": "generated",
            }
        )
        self.assertEqual(draft.patch_format, "unified_diff")

    def test_issue_eligibility_requires_confidence_category_and_patch(self):
        orchestrator = ReviewOrchestrator.__new__(ReviewOrchestrator)
        orchestrator.settings = SimpleNamespace(
            autofix_min_confidence=0.85,
        )
        patch_map = {"app/service.py": "@@ -1,1 +1,2 @@"}

        eligible_issue = IssueFinding(
            id="issue-1",
            file="app/service.py",
            line=14,
            severity="high",
            category="bug",
            title="Missing null guard",
            description="The diff dereferences the payload before validating it.",
            suggested_fix="Return early when payload is empty.",
            confidence=0.92,
        )
        low_confidence_issue = eligible_issue.model_copy(update={"id": "issue-2", "confidence": 0.62})
        vague_issue = eligible_issue.model_copy(
            update={
                "id": "issue-3",
                "category": "quality",
                "description": "This suggests a broad refactor across the module.",
                "suggested_fix": "Apply a broad refactor.",
            }
        )

        self.assertTrue(orchestrator._is_autofix_eligible(eligible_issue, patch_map))
        self.assertFalse(orchestrator._is_autofix_eligible(low_confidence_issue, patch_map))
        self.assertFalse(orchestrator._is_autofix_eligible(vague_issue, patch_map))

    def test_autofix_agent_returns_failed_draft_when_patch_is_invalid(self):
        llm = StubLLMService(
            {
                "fix_title": "Patch draft",
                "rationale": "Try to fix the issue.",
                "patch_format": "unified_diff",
                "patch_text": "not a real unified diff",
                "confidence": 0.9,
                "safety_level": "safe",
            }
        )
        agent = AutofixAgent(llm, max_patch_chars=8000)
        issue = IssueFinding(
            id="issue-9",
            file="app/service.py",
            line=3,
            severity="medium",
            category="bug",
            title="Broken conditional",
            description="The conditional is inverted in the new code path.",
            suggested_fix="Restore the guard condition.",
            confidence=0.9,
        )

        draft = agent.generate_draft(
            review_id="review-1",
            repo="owner/repo",
            pr_title="Fix condition",
            issue=issue,
            numbered_patch="1 @@ -1,2 +1,2 @@\n2 -if ready:\n3 +if not ready:",
        )

        self.assertEqual(draft.status, "failed")
        self.assertIsNone(draft.patch_text)
        self.assertIn("unified diff", draft.error_message.lower())

    def test_autofix_agent_returns_generated_draft_for_valid_patch(self):
        llm = StubLLMService(
            {
                "fix_title": "Patch draft",
                "rationale": "Add the missing guard.",
                "patch_format": "unified_diff",
                "patch_text": "--- a/app/service.py\n+++ b/app/service.py\n@@ -10,2 +10,4 @@\n-    do_work(payload)\n+    if payload is None:\n+        return None\n+    do_work(payload)",
                "confidence": 0.97,
                "safety_level": "needs_review",
            }
        )
        agent = AutofixAgent(llm, max_patch_chars=8000)
        issue = IssueFinding(
            id="issue-10",
            file="app/service.py",
            line=10,
            severity="high",
            category="bug",
            title="Missing payload guard",
            description="The code path now assumes payload is present.",
            suggested_fix="Return early when payload is missing.",
            confidence=0.97,
        )

        draft = agent.generate_draft(
            review_id="review-2",
            repo="owner/repo",
            pr_title="Fix payload handling",
            issue=issue,
            numbered_patch="1 @@ -10,2 +10,2 @@\n2 -    do_work(payload)\n3 +    do_work(payload)",
        )

        self.assertEqual(draft.status, "generated")
        self.assertTrue(draft.patch_text.startswith("--- a/app/service.py"))
        self.assertEqual(draft.safety_level, "needs_review")
