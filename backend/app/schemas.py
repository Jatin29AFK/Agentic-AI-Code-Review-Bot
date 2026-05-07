from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

Severity = Literal["critical", "high", "medium", "low", "suggestion"]
Category = Literal["bug", "security", "quality", "testing", "performance"]
RiskLevel = Literal["low", "medium", "high"]
AutoFixPatchFormat = Literal["unified_diff"]
AutoFixSafetyLevel = Literal["safe", "needs_review", "risky"]
AutoFixStatus = Literal["generated", "failed", "disabled"]


class ManualReviewRequest(BaseModel):
    repo_url: HttpUrl | str
    pr_number: int = Field(gt=0)
    github_token: str | None = Field(default=None, min_length=1)
    path_filters: list[str] = Field(default_factory=list)


class PostCommentsRequest(BaseModel):
    github_token: str | None = Field(default=None, min_length=1)
    post_inline_comments: bool = True
    skip_lgtm_comment: bool = True


class IssueFinding(BaseModel):
    id: str | None = None
    file: str
    line: int | None = Field(default=None, ge=1)
    severity: Severity
    category: Category
    title: str
    description: str
    suggested_fix: str
    confidence: float = Field(ge=0.0, le=1.0)


class DiffSummaryOutput(BaseModel):
    summary: str
    changed_modules: list[str] = Field(default_factory=list)
    risk_level: RiskLevel


class ReviewPlanItem(BaseModel):
    agent: Literal["bug", "security", "quality", "testing"]
    reason: str


class ReviewPlanOutput(BaseModel):
    review_plan: list[ReviewPlanItem] = Field(default_factory=list)


class FindingsOutput(BaseModel):
    issues: list[IssueFinding] = Field(default_factory=list)
    positive_notes: list[str] = Field(default_factory=list)


class TestSuggestionOutput(BaseModel):
    test_suggestions: list[str] = Field(default_factory=list)
    positive_notes: list[str] = Field(default_factory=list)


class FinalAggregationOutput(BaseModel):
    summary: str
    positive_notes: list[str] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    review_id: str
    repo: str
    pr_number: int
    pr_title: str
    summary: str
    release_notes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    score: int = Field(ge=0, le=100)
    total_files_reviewed: int = Field(ge=0)
    total_issues: int = Field(ge=0)
    issues: list[IssueFinding] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)
    positive_notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ReviewHistoryItem(BaseModel):
    review_id: str
    repo: str
    repo_url: str
    pr_number: int
    pr_title: str
    score: int
    risk_level: RiskLevel
    total_issues: int
    autofix_count: int = 0
    has_autofix: bool = False
    created_at: datetime


class CommentPostingResult(BaseModel):
    review_id: str
    summary_comment_posted: bool
    inline_comments_posted: int
    skipped_duplicates: int
    message: str


class ReviewedFileInfo(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    numbered_patch: str | None = None


class SkippedFileInfo(BaseModel):
    filename: str
    reason: str | None = None


class ReviewDetailsResponse(BaseModel):
    review_id: str
    repo_url: str
    pr_url: str
    head_sha: str
    base_sha: str
    path_filters: list[str] = Field(default_factory=list)
    changed_modules: list[str] = Field(default_factory=list)
    release_notes: list[str] = Field(default_factory=list)
    review_plan: list[ReviewPlanItem] = Field(default_factory=list)
    workflow_notes: list[str] = Field(default_factory=list)
    reviewed_files: list[ReviewedFileInfo] = Field(default_factory=list)
    skipped_files: list[SkippedFileInfo] = Field(default_factory=list)


class InlineCommentPreview(BaseModel):
    file: str
    line: int | None = None
    severity: Severity
    category: Category
    body: str


class CommentPreviewResponse(BaseModel):
    review_id: str
    summary_comment: str
    inline_comments: list[InlineCommentPreview] = Field(default_factory=list)
    skip_commenting: bool = False
    skip_reason: str | None = None


class AutoFixDraft(BaseModel):
    id: str
    issue_id: str
    file: str
    line: int | None = None
    fix_title: str
    rationale: str
    patch_format: AutoFixPatchFormat
    patch_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    safety_level: AutoFixSafetyLevel
    status: AutoFixStatus
    error_message: str | None = None


class AutoFixDraftBatchOutput(BaseModel):
    drafts: list[AutoFixDraft] = Field(default_factory=list)


class AutoFixDraftGenerationOutput(BaseModel):
    fix_title: str
    rationale: str
    patch_format: AutoFixPatchFormat
    patch_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    safety_level: AutoFixSafetyLevel


class AutoFixResponse(BaseModel):
    review_id: str
    enabled: bool
    message: str
    drafts: list[AutoFixDraft] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    app: str
    timestamp: datetime
