import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services.comment_service import CommentService
from app.services.github_service import GitHubServiceError
from app.services.llm_service import LLMConfigurationError, LLMResponseError
from app.services.review_orchestrator import ReviewOrchestrator
from app.services.review_repository import ReviewRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event", "")
    body = await request.body()

    if settings.github_webhook_secret:
        expected = "sha256=" + hmac.new(
            settings.github_webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    if event == "ping":
        return {"status": "ok", "message": "GitHub webhook ping received."}

    if event != "pull_request":
        return {"status": "ignored", "message": f"Unsupported event {event}."}

    action = payload.get("action")
    if action not in {"opened", "synchronize", "reopened"}:
        return {"status": "ignored", "message": f"Action {action} is not configured for review."}

    repo_url = payload.get("repository", {}).get("html_url")
    pr_number = payload.get("pull_request", {}).get("number")
    if not repo_url or not pr_number:
        raise HTTPException(status_code=400, detail="Webhook payload is missing repository or PR metadata.")

    orchestrator = ReviewOrchestrator()
    repository = ReviewRepository()
    comment_service = CommentService()

    try:
        review_result, raw_result = orchestrator.run_review(repo_url=repo_url, pr_number=pr_number)
        repository.save_review(db, review_result, raw_result)
    except GitHubServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    comment_result = None
    if settings.post_webhook_comments and settings.github_token:
        try:
            comment_result = comment_service.post_review_comments(
                review=review_result,
                raw_review=raw_result,
                github_token=None,
                post_inline_comments=True,
                skip_lgtm_comment=True,
            ).model_dump()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Webhook review succeeded but comment posting failed: %s", exc)

    return {
        "status": "processed",
        "review_id": review_result.review_id,
        "risk_level": review_result.risk_level,
        "score": review_result.score,
        "comment_result": comment_result,
    }
