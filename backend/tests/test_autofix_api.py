from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base
from app.routes.reviews import get_autofix_drafts, regenerate_autofix_drafts
from app.schemas import IssueFinding, ReviewResult
from app.services.review_repository import ReviewRepository


class AutofixApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.repository = ReviewRepository()
        self._seed_review()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _seed_review(self):
        review = ReviewResult(
            review_id="review-api-1",
            repo="owner/repo",
            pr_number=7,
            pr_title="Patch endpoint",
            summary="Summary",
            risk_level="low",
            score=91,
            total_files_reviewed=1,
            total_issues=1,
            issues=[
                IssueFinding(
                    id="issue-api-1",
                    file="app/api.py",
                    line=24,
                    severity="low",
                    category="quality",
                    title="Extract helper",
                    description="The branch can be simplified.",
                    suggested_fix="Extract a helper.",
                    confidence=0.9,
                )
            ],
            test_suggestions=[],
            positive_notes=[],
            created_at=datetime.now(timezone.utc),
        )
        raw_result = {
            **review.model_dump(mode="json"),
            "repo_url": "https://github.com/owner/repo",
            "pr_url": "https://github.com/owner/repo/pull/7",
            "head_sha": "abc",
            "base_sha": "def",
            "changed_modules": ["app"],
            "review_plan": [],
            "workflow_notes": [],
            "reviewed_files": [
                {
                    "filename": "app/api.py",
                    "status": "modified",
                    "additions": 4,
                    "deletions": 1,
                    "changes": 5,
                    "numbered_patch": "1 @@ -20,2 +20,4 @@\n2 -return payload\n3 +if not payload:\n4 +    return None\n5 +return payload",
                }
            ],
            "skipped_files": [],
            "autofix_drafts": [
                {
                    "id": "draft-api-1",
                    "issue_id": "issue-api-1",
                    "file": "app/api.py",
                    "line": 24,
                    "fix_title": "Extract helper",
                    "rationale": "Keep the branch focused.",
                    "patch_format": "unified_diff",
                    "patch_text": "--- a/app/api.py\n+++ b/app/api.py\n@@ -20,2 +20,4 @@\n-return payload\n+if not payload:\n+    return None\n+return payload",
                    "confidence": 0.86,
                    "safety_level": "needs_review",
                    "status": "generated",
                    "error_message": None,
                }
            ],
        }
        with self.SessionLocal() as db:
            self.repository.save_review(db, review, raw_result)

    def test_get_autofix_returns_stored_drafts(self):
        orchestrator = SimpleNamespace(settings=SimpleNamespace(autofix_enabled=True))
        with self.SessionLocal() as db:
            response = get_autofix_drafts(
                review_id="review-api-1",
                db=db,
                repository=self.repository,
                orchestrator=orchestrator,
            )

        self.assertTrue(response.enabled)
        self.assertEqual(len(response.drafts), 1)
        self.assertEqual(response.drafts[0].id, "draft-api-1")

    def test_regenerate_autofix_returns_disabled_state_when_feature_is_off(self):
        orchestrator = SimpleNamespace(settings=SimpleNamespace(autofix_enabled=False))
        with self.SessionLocal() as db:
            response = regenerate_autofix_drafts(
                review_id="review-api-1",
                db=db,
                repository=self.repository,
                orchestrator=orchestrator,
            )

        self.assertFalse(response.enabled)
        self.assertEqual(response.drafts, [])
