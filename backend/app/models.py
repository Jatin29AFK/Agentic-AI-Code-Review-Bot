from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    repo_url: Mapped[str] = mapped_column(String(500))
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    pr_title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(32), index=True)
    score: Mapped[int] = mapped_column(Integer)
    total_files_reviewed: Mapped[int] = mapped_column(Integer)
    total_issues: Mapped[int] = mapped_column(Integer)
    raw_result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    issues: Mapped[list["IssueRecord"]] = relationship(
        "IssueRecord",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    autofix_drafts: Mapped[list["AutoFixRecord"]] = relationship(
        "AutoFixRecord",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class IssueRecord(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(64), ForeignKey("reviews.id"), index=True)
    file: Mapped[str] = mapped_column(String(500))
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    suggested_fix: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)

    review: Mapped[ReviewRecord] = relationship("ReviewRecord", back_populates="issues")


class AutoFixRecord(Base):
    __tablename__ = "autofix_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(64), ForeignKey("reviews.id"), index=True)
    issue_id: Mapped[str] = mapped_column(String(64), index=True)
    file: Mapped[str] = mapped_column(String(500))
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fix_title: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str] = mapped_column(Text)
    patch_format: Mapped[str] = mapped_column(String(32))
    patch_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    safety_level: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    review: Mapped[ReviewRecord] = relationship("ReviewRecord", back_populates="autofix_drafts")
