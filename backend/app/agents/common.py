from app.services.github_service import PullRequestContext
from app.services.secret_redactor import redact_secrets


def build_review_payload(context: PullRequestContext, max_total_chars: int) -> str:
    sections = [
        f"Repository: {context.repo_slug}",
        f"Pull Request: #{context.pr_number} - {context.pr_title}",
        f"PR Body:\n{context.pr_body or '(no description provided)'}",
        "",
        "Changed files:",
    ]

    for file in context.files:
        file_summary = (
            f"- {file.filename} [{file.status}] "
            f"(+{file.additions}/-{file.deletions}, changes={file.changes}, reviewable={file.is_reviewable})"
        )
        if file.skip_reason:
            file_summary += f" - {file.skip_reason}"
        sections.append(file_summary)

    sections.append("")
    sections.append("Reviewable diffs:")

    remaining = max_total_chars
    for file in context.reviewable_files:
        section = (
            f"\nFILE: {file.filename}\n"
            f"STATUS: {file.status}\n"
            "PATCH WITH NEW-FILE LINE NUMBERS:\n"
            f"{file.numbered_patch}\n"
        )
        if len(section) > remaining:
            section = section[:remaining] + "\n... [review payload truncated]"
        sections.append(section)
        remaining -= len(section)
        if remaining <= 0:
            break

    return redact_secrets("\n".join(sections))

