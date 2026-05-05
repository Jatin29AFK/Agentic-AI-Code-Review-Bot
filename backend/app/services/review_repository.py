import json
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models import AutoFixRecord, IssueRecord, ReviewRecord
from app.schemas import AutoFixDraft, IssueFinding, ReviewHistoryItem, ReviewResult


class ReviewRepository:
    def save_review(self, db: Session, result: ReviewResult, raw_result: dict) -> ReviewResult:
        record = ReviewRecord(
            id=result.review_id,
            repo=result.repo,
            repo_url=str(raw_result.get("repo_url", "")),
            pr_number=result.pr_number,
            pr_title=result.pr_title,
            summary=result.summary,
            risk_level=result.risk_level,
            score=result.score,
            total_files_reviewed=result.total_files_reviewed,
            total_issues=result.total_issues,
            raw_result_json=json.dumps(raw_result, default=str),
            created_at=result.created_at,
        )
        record.issues = [
            IssueRecord(
                id=issue.id or str(uuid4()),
                file=issue.file,
                line=issue.line,
                severity=issue.severity,
                category=issue.category,
                title=issue.title,
                description=issue.description,
                suggested_fix=issue.suggested_fix,
                confidence=issue.confidence,
            )
            for issue in result.issues
        ]
        record.autofix_drafts = [
            AutoFixRecord(
                id=draft["id"],
                issue_id=draft["issue_id"],
                file=draft["file"],
                line=draft.get("line"),
                fix_title=draft["fix_title"],
                rationale=draft["rationale"],
                patch_format=draft["patch_format"],
                patch_text=draft.get("patch_text"),
                confidence=draft["confidence"],
                safety_level=draft["safety_level"],
                status=draft["status"],
                error_message=draft.get("error_message"),
            )
            for draft in raw_result.get("autofix_drafts", [])
        ]
        db.add(record)
        db.commit()
        db.refresh(record)
        return result

    def list_reviews(self, db: Session) -> list[ReviewHistoryItem]:
        records = db.execute(select(ReviewRecord).order_by(desc(ReviewRecord.created_at))).scalars().all()
        return [
            ReviewHistoryItem(
                review_id=record.id,
                repo=record.repo,
                repo_url=record.repo_url,
                pr_number=record.pr_number,
                pr_title=record.pr_title,
                score=record.score,
                risk_level=record.risk_level,
                total_issues=record.total_issues,
                autofix_count=sum(1 for draft in record.autofix_drafts if draft.status == "generated"),
                has_autofix=any(draft.status == "generated" for draft in record.autofix_drafts),
                created_at=record.created_at,
            )
            for record in records
        ]

    def get_review(self, db: Session, review_id: str) -> ReviewResult | None:
        record = db.get(ReviewRecord, review_id)
        if not record:
            return None

        try:
            raw_result = json.loads(record.raw_result_json)
            return ReviewResult.model_validate(raw_result)
        except (json.JSONDecodeError, ValueError):
            return ReviewResult(
                review_id=record.id,
                repo=record.repo,
                pr_number=record.pr_number,
                pr_title=record.pr_title,
                summary=record.summary,
                risk_level=record.risk_level,
                score=record.score,
                total_files_reviewed=record.total_files_reviewed,
                total_issues=record.total_issues,
                issues=[
                    IssueFinding(
                        id=issue.id,
                        file=issue.file,
                        line=issue.line,
                        severity=issue.severity,
                        category=issue.category,
                        title=issue.title,
                        description=issue.description,
                        suggested_fix=issue.suggested_fix,
                        confidence=issue.confidence,
                    )
                    for issue in record.issues
                ],
                test_suggestions=[],
                positive_notes=[],
                created_at=record.created_at,
            )

    def get_review_raw(self, db: Session, review_id: str) -> dict | None:
        record = db.get(ReviewRecord, review_id)
        if not record:
            return None
        return json.loads(record.raw_result_json)

    def get_autofix_drafts(self, db: Session, review_id: str) -> list[AutoFixDraft]:
        record = db.get(ReviewRecord, review_id)
        if not record:
            return []
        return [
            AutoFixDraft(
                id=draft.id,
                issue_id=draft.issue_id,
                file=draft.file,
                line=draft.line,
                fix_title=draft.fix_title,
                rationale=draft.rationale,
                patch_format=draft.patch_format,
                patch_text=draft.patch_text,
                confidence=draft.confidence,
                safety_level=draft.safety_level,
                status=draft.status,
                error_message=draft.error_message,
            )
            for draft in record.autofix_drafts
        ]

    def replace_autofix_drafts(self, db: Session, review_id: str, drafts: list[AutoFixDraft]) -> list[AutoFixDraft]:
        record = db.get(ReviewRecord, review_id)
        if not record:
            return []
        record.autofix_drafts = [
            AutoFixRecord(
                id=draft.id,
                issue_id=draft.issue_id,
                file=draft.file,
                line=draft.line,
                fix_title=draft.fix_title,
                rationale=draft.rationale,
                patch_format=draft.patch_format,
                patch_text=draft.patch_text,
                confidence=draft.confidence,
                safety_level=draft.safety_level,
                status=draft.status,
                error_message=draft.error_message,
            )
            for draft in drafts
        ]

        raw_result = json.loads(record.raw_result_json)
        raw_result["autofix_drafts"] = [draft.model_dump(mode="json") for draft in drafts]
        record.raw_result_json = json.dumps(raw_result, default=str)
        db.add(record)
        db.commit()
        db.refresh(record)
        return drafts

    def get_stats(self, db: Session) -> dict:
        total_reviews = db.scalar(select(func.count(ReviewRecord.id))) or 0
        avg_score = db.scalar(select(func.avg(ReviewRecord.score))) or 0
        total_issues = db.scalar(select(func.count(IssueRecord.id))) or 0
        high_risk_prs = db.scalar(select(func.count(ReviewRecord.id)).where(ReviewRecord.risk_level == "high")) or 0
        return {
            "total_reviews": int(total_reviews),
            "avg_score": round(float(avg_score), 1) if total_reviews else 0.0,
            "total_issues": int(total_issues),
            "high_risk_prs": int(high_risk_prs),
        }
