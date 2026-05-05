from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AutoFixResponse,
    CommentPostingResult,
    CommentPreviewResponse,
    ManualReviewRequest,
    PostCommentsRequest,
    ReviewDetailsResponse,
    ReviewHistoryItem,
    ReviewPlanItem,
    ReviewResult,
    ReviewedFileInfo,
    SkippedFileInfo,
)
from app.services.comment_service import CommentService
from app.services.github_service import GitHubServiceError
from app.services.llm_service import LLMConfigurationError, LLMResponseError
from app.services.review_orchestrator import ReviewOrchestrator
from app.services.review_repository import ReviewRepository

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


def get_repository() -> ReviewRepository:
    return ReviewRepository()


def get_orchestrator() -> ReviewOrchestrator:
    return ReviewOrchestrator()


def get_comment_service() -> CommentService:
    return CommentService()


@router.post("/manual", response_model=ReviewResult)
def create_manual_review(
    payload: ManualReviewRequest,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
    orchestrator: ReviewOrchestrator = Depends(get_orchestrator),
) -> ReviewResult:
    try:
        review_result, raw_result = orchestrator.run_review(
            repo_url=str(payload.repo_url),
            pr_number=payload.pr_number,
            github_token=payload.github_token,
        )
        repository.save_review(db, review_result, raw_result)
        return review_result
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected review failure: {exc}") from exc


@router.get("", response_model=list[ReviewHistoryItem])
def list_reviews(
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
) -> list[ReviewHistoryItem]:
    return repository.list_reviews(db)


@router.get("/{review_id}", response_model=ReviewResult)
def get_review(
    review_id: str,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
) -> ReviewResult:
    result = repository.get_review(db, review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Review not found.")
    return result


@router.get("/{review_id}/details", response_model=ReviewDetailsResponse)
def get_review_details(
    review_id: str,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
) -> ReviewDetailsResponse:
    raw_review = repository.get_review_raw(db, review_id)
    if not raw_review:
        raise HTTPException(status_code=404, detail="Review not found.")

    return ReviewDetailsResponse(
        review_id=review_id,
        repo_url=raw_review.get("repo_url", ""),
        pr_url=raw_review.get("pr_url", ""),
        head_sha=raw_review.get("head_sha", ""),
        base_sha=raw_review.get("base_sha", ""),
        changed_modules=raw_review.get("changed_modules", []),
        review_plan=[ReviewPlanItem.model_validate(item) for item in raw_review.get("review_plan", [])],
        workflow_notes=raw_review.get("workflow_notes", []),
        reviewed_files=[ReviewedFileInfo.model_validate(item) for item in raw_review.get("reviewed_files", [])],
        skipped_files=[SkippedFileInfo.model_validate(item) for item in raw_review.get("skipped_files", [])],
    )


@router.get("/{review_id}/comment-preview", response_model=CommentPreviewResponse)
def get_comment_preview(
    review_id: str,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentPreviewResponse:
    review = repository.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")
    return comment_service.build_comment_preview(review)


@router.get("/{review_id}/autofix", response_model=AutoFixResponse)
def get_autofix_drafts(
    review_id: str,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
    orchestrator: ReviewOrchestrator = Depends(get_orchestrator),
) -> AutoFixResponse:
    review = repository.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found.")

    if not orchestrator.settings.autofix_enabled:
        return AutoFixResponse(
            review_id=review_id,
            enabled=False,
            message="Autofix drafts are currently disabled by backend configuration.",
            drafts=[],
        )

    drafts = repository.get_autofix_drafts(db, review_id)
    return AutoFixResponse(
        review_id=review_id,
        enabled=True,
        message="Autofix drafts loaded successfully." if drafts else "No autofix drafts are available for this review.",
        drafts=drafts,
    )


@router.post("/{review_id}/autofix/regenerate", response_model=AutoFixResponse)
def regenerate_autofix_drafts(
    review_id: str,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
    orchestrator: ReviewOrchestrator = Depends(get_orchestrator),
) -> AutoFixResponse:
    review = repository.get_review(db, review_id)
    raw_review = repository.get_review_raw(db, review_id)
    if not review or not raw_review:
        raise HTTPException(status_code=404, detail="Review not found.")

    if not orchestrator.settings.autofix_enabled:
        return AutoFixResponse(
            review_id=review_id,
            enabled=False,
            message="Autofix drafts are currently disabled by backend configuration.",
            drafts=[],
        )

    try:
        drafts = orchestrator.regenerate_autofix_for_review(review, raw_review)
        repository.replace_autofix_drafts(db, review_id, drafts)
        return AutoFixResponse(
            review_id=review_id,
            enabled=True,
            message="Autofix drafts regenerated successfully." if drafts else "No eligible issues were available for autofix regeneration.",
            drafts=drafts,
        )
    except (GitHubServiceError, LLMResponseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Unexpected autofix failure: {exc}") from exc


@router.post("/{review_id}/post-comments", response_model=CommentPostingResult)
def post_comments(
    review_id: str,
    payload: PostCommentsRequest,
    db: Session = Depends(get_db),
    repository: ReviewRepository = Depends(get_repository),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentPostingResult:
    review = repository.get_review(db, review_id)
    raw_review = repository.get_review_raw(db, review_id)
    if not review or not raw_review:
        raise HTTPException(status_code=404, detail="Review not found.")

    try:
        return comment_service.post_review_comments(
            review=review,
            raw_review=raw_review,
            github_token=payload.github_token,
            post_inline_comments=payload.post_inline_comments,
        )
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
