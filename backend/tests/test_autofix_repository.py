from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base
from app.schemas import AutoFixDraft, IssueFinding, ReviewResult
from app.services.review_repository import ReviewRepository


class AutofixRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.repository = ReviewRepository()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _build_review(self):
        return ReviewResult(
            review_id="review-1",
            repo="owner/repo",
            pr_number=4,
            pr_title="Improve handler",
            summary="Summary",
            risk_level="medium",
            score=82,
            total_files_reviewed=1,
            total_issues=1,
            issues=[
                IssueFinding(
                    id="issue-1",
                    file="app/service.py",
                    line=11,
                    severity="medium",
                    category="bug",
                    title="Missing guard",
                    description="Description",
                    suggested_fix="Suggested fix",
                    confidence=0.91,
                )
            ],
            test_suggestions=[],
            positive_notes=[],
            created_at=datetime.now(timezone.utc),
        )

    def test_save_and_replace_autofix_drafts_round_trip(self):
        review = self._build_review()
        raw_result = {
            **review.model_dump(mode="json"),
            "repo_url": "https://github.com/owner/repo",
            "pr_url": "https://github.com/owner/repo/pull/4",
            "head_sha": "abc",
            "base_sha": "def",
            "changed_modules": ["app"],
            "review_plan": [],
            "workflow_notes": [],
            "reviewed_files": [],
            "skipped_files": [],
            "autofix_drafts": [
                {
                    "id": "draft-1",
                    "issue_id": "issue-1",
                    "file": "app/service.py",
                    "line": 11,
                    "fix_title": "Add guard",
                    "rationale": "Prevent None usage.",
                    "patch_format": "unified_diff",
                    "patch_text": "--- a/app/service.py\n+++ b/app/service.py\n@@ -1,1 +1,3 @@\n-pass\n+if payload is None:\n+    return None\n+pass",
                    "confidence": 0.9,
                    "safety_level": "needs_review",
                    "status": "generated",
                    "error_message": None,
                }
            ],
        }

        with self.SessionLocal() as db:
            self.repository.save_review(db, review, raw_result)
            stored = self.repository.get_autofix_drafts(db, "review-1")
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].fix_title, "Add guard")

            replacement = [
                AutoFixDraft(
                    id="draft-2",
                    issue_id="issue-1",
                    file="app/service.py",
                    line=11,
                    fix_title="Refine guard",
                    rationale="Handle None earlier.",
                    patch_format="unified_diff",
                    patch_text="--- a/app/service.py\n+++ b/app/service.py\n@@ -1,1 +1,2 @@\n-pass\n+return None",
                    confidence=0.88,
                    safety_level="safe",
                    status="generated",
                    error_message=None,
                )
            ]
            self.repository.replace_autofix_drafts(db, "review-1", replacement)

            updated = self.repository.get_autofix_drafts(db, "review-1")
            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].id, "draft-2")

            raw = self.repository.get_review_raw(db, "review-1")
            self.assertEqual(raw["autofix_drafts"][0]["fix_title"], "Refine guard")
