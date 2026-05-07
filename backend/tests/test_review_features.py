from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas import ReviewResult
from app.services.comment_service import CommentService
from app.services.github_service import GitHubService


class ReviewFeatureTests(unittest.TestCase):
    def test_path_filters_support_include_and_exclude_patterns(self):
        service = GitHubService()

        self.assertTrue(service._matches_path_filters("src/app/main.py", ["src/**"]))
        self.assertFalse(service._matches_path_filters("docs/readme.md", ["src/**"]))
        self.assertFalse(service._matches_path_filters("src/generated/file.py", ["src/**", "!src/generated/**"]))

    def test_comment_preview_marks_lgtm_reviews_as_skippable(self):
        review = ReviewResult(
            review_id="review-lgtm-1",
            repo="owner/repo",
            pr_number=12,
            pr_title="Improve copy",
            summary="The automated review did not find major issues in the supported diff.",
            release_notes=["Updates 1 reviewed file across src."],
            risk_level="low",
            score=100,
            total_files_reviewed=1,
            total_issues=0,
            issues=[],
            test_suggestions=[],
            positive_notes=["The changes are small and coherent."],
            created_at=datetime.now(timezone.utc),
        )

        preview = CommentService().build_comment_preview(review)

        self.assertTrue(preview.skip_commenting)
        self.assertIsNotNone(preview.skip_reason)
        self.assertIn("Release Notes", preview.summary_comment)


if __name__ == "__main__":
    unittest.main()
