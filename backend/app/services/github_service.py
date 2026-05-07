from __future__ import annotations

import logging
import re
from fnmatch import fnmatch
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GitHubServiceError(RuntimeError):
    """Raised when GitHub API operations fail."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class PullRequestFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None
    blob_url: str | None
    is_reviewable: bool
    skip_reason: str | None = None
    numbered_patch: str = ""


@dataclass
class PullRequestContext:
    owner: str
    repo_name: str
    repo_url: str
    pr_number: int
    pr_title: str
    pr_body: str
    pr_url: str
    head_sha: str
    base_sha: str
    files: list[PullRequestFile] = field(default_factory=list)

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repo_name}"

    @property
    def reviewable_files(self) -> list[PullRequestFile]:
        return [file for file in self.files if file.is_reviewable]


class GitHubService:
    IGNORED_DIRECTORIES = {
        "node_modules/",
        "dist/",
        "build/",
        "coverage/",
        ".next/",
        "vendor/",
    }
    IGNORED_FILENAMES = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
    }
    IGNORED_EXTENSIONS = {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mov",
        ".mp3",
    }
    REVIEWABLE_EXTENSIONS = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".java",
        ".go",
        ".rb",
        ".rs",
        ".php",
        ".cs",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".kt",
        ".swift",
        ".scala",
        ".sql",
        ".html",
        ".css",
        ".scss",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".sh",
        ".tf",
    }

    def __init__(self) -> None:
        self.settings = get_settings()

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        parsed = urlparse(repo_url.strip())
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        parts = [part for part in path.split("/") if part]
        if parsed.netloc not in {"github.com", "www.github.com"} or len(parts) < 2:
            raise GitHubServiceError(
                "Invalid GitHub repository URL. Expected format like https://github.com/owner/repo",
                status_code=400,
            )
        return parts[0], parts[1]

    def get_pull_request_context(
        self,
        repo_url: str,
        pr_number: int,
        github_token: str | None = None,
        path_filters: list[str] | None = None,
    ) -> PullRequestContext:
        owner, repo_name = self.parse_repo_url(repo_url)
        pr_data = self._request_json("GET", f"/repos/{owner}/{repo_name}/pulls/{pr_number}", github_token)
        files_data = self._paginate(f"/repos/{owner}/{repo_name}/pulls/{pr_number}/files", github_token)
        files = self._build_files(files_data, path_filters or [])

        return PullRequestContext(
            owner=owner,
            repo_name=repo_name,
            repo_url=repo_url,
            pr_number=pr_number,
            pr_title=pr_data.get("title", f"PR #{pr_number}"),
            pr_body=pr_data.get("body") or "",
            pr_url=pr_data.get("html_url", repo_url),
            head_sha=pr_data.get("head", {}).get("sha", ""),
            base_sha=pr_data.get("base", {}).get("sha", ""),
            files=files,
        )

    def list_issue_comments(self, owner: str, repo_name: str, pr_number: int, github_token: str | None = None) -> list[dict]:
        return self._paginate(f"/repos/{owner}/{repo_name}/issues/{pr_number}/comments", github_token)

    def list_review_comments(self, owner: str, repo_name: str, pr_number: int, github_token: str | None = None) -> list[dict]:
        return self._paginate(f"/repos/{owner}/{repo_name}/pulls/{pr_number}/comments", github_token)

    def post_issue_comment(self, owner: str, repo_name: str, pr_number: int, body: str, github_token: str | None = None) -> dict:
        return self._request_json(
            "POST",
            f"/repos/{owner}/{repo_name}/issues/{pr_number}/comments",
            github_token,
            json={"body": body},
        )

    def post_inline_comment(
        self,
        owner: str,
        repo_name: str,
        pr_number: int,
        *,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        github_token: str | None = None,
    ) -> dict:
        return self._request_json(
            "POST",
            f"/repos/{owner}/{repo_name}/pulls/{pr_number}/comments",
            github_token,
            json={
                "body": body,
                "commit_id": commit_id,
                "path": path,
                "line": line,
                "side": "RIGHT",
            },
        )

    def _paginate(self, path: str, github_token: str | None) -> list[dict]:
        page = 1
        items: list[dict] = []
        while True:
            chunk = self._request_json("GET", path, github_token, params={"per_page": 100, "page": page})
            if not isinstance(chunk, list):
                raise GitHubServiceError("Unexpected GitHub API response while paginating.")
            items.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return items

    def _request_json(
        self,
        method: str,
        path: str,
        github_token: str | None,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict | list[dict]:
        token = github_token or self.settings.github_token
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "agentic-ai-code-review-bot",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com{path}"
        try:
            with httpx.Client(timeout=self.settings.github_timeout_seconds) as client:
                response = client.request(method, url, headers=headers, json=json, params=params)
        except httpx.HTTPError as exc:
            raise GitHubServiceError(f"Unable to reach GitHub API: {exc}", status_code=502) from exc

        if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
            reset = response.headers.get("x-ratelimit-reset", "unknown")
            raise GitHubServiceError(f"GitHub API rate limit exceeded. Reset timestamp: {reset}", status_code=429)

        if response.status_code >= 400:
            detail = self._extract_error_message(response)
            guidance = self._build_permission_guidance(response.status_code, detail, path, method)
            message = f"GitHub API request failed ({response.status_code}): {detail}"
            if guidance:
                message = f"{message}. {guidance}"
            raise GitHubServiceError(message, status_code=response.status_code)

        return response.json()

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return response.text[:300]
        if isinstance(data, dict):
            return data.get("message") or response.text[:300]
        return response.text[:300]

    def _build_permission_guidance(self, status_code: int, detail: str, path: str, method: str) -> str | None:
        normalized = detail.lower()
        if status_code == 401:
            return "The GitHub token was rejected. Double-check that the token is valid and has not expired."

        if status_code == 403 and "resource not accessible by personal access token" in normalized:
            if method == "POST" and "/issues/" in path and "/comments" in path:
                return (
                    "Your token can read the PR but cannot create the summary comment. "
                    "For a fine-grained PAT, grant Repository access plus Pull requests: Read and write, "
                    "and either Issues: Read and write or Pull requests: Read and write on that repository. "
                    "For a classic PAT, use public_repo for public repositories or repo for private repositories."
                )
            if method == "POST" and "/pulls/" in path and "/comments" in path:
                return (
                    "Your token cannot create inline PR review comments. "
                    "For a fine-grained PAT, grant Repository access with Pull requests: Read and write "
                    "and Contents: Read on that repository. "
                    "For a classic PAT, use public_repo for public repositories or repo for private repositories."
                )
            return (
                "The token is missing repository permissions for this action. "
                "Use a classic PAT with public_repo or repo scope, or a fine-grained PAT that includes "
                "repository access plus Pull requests: Read and write."
            )

        return None

    def _build_files(self, files_data: list[dict], path_filters: list[str]) -> list[PullRequestFile]:
        files: list[PullRequestFile] = []
        max_files = self.settings.max_files_reviewed
        reviewable_count = 0

        for item in files_data:
            filename = item.get("filename", "")
            patch = item.get("patch")
            is_reviewable, skip_reason = self._is_reviewable(filename, item, path_filters)

            if is_reviewable and reviewable_count >= max_files:
                is_reviewable = False
                skip_reason = f"Skipped because the PR exceeded the max reviewable file limit ({max_files})."

            numbered_patch = self._annotate_patch(patch) if patch and is_reviewable else ""

            if is_reviewable:
                reviewable_count += 1

            files.append(
                PullRequestFile(
                    filename=filename,
                    status=item.get("status", "modified"),
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    changes=item.get("changes", 0),
                    patch=patch,
                    blob_url=item.get("blob_url"),
                    is_reviewable=is_reviewable,
                    skip_reason=skip_reason,
                    numbered_patch=numbered_patch,
                )
            )
        return files

    def _is_reviewable(self, filename: str, item: dict, path_filters: list[str]) -> tuple[bool, str | None]:
        normalized = filename.lower()
        if item.get("status") == "removed":
            return False, "Removed files are skipped."
        if any(normalized.startswith(prefix) for prefix in self.IGNORED_DIRECTORIES):
            return False, "Generated or dependency directory skipped."
        if normalized.split("/")[-1] in self.IGNORED_FILENAMES:
            return False, "Lock file skipped."
        if any(normalized.endswith(ext) for ext in self.IGNORED_EXTENSIONS):
            return False, "Binary or non-code asset skipped."
        if "generated" in normalized or normalized.endswith(".min.js"):
            return False, "Generated asset skipped."
        if not item.get("patch"):
            return False, "GitHub did not provide a textual patch for this file."

        extension_match = re.search(r"(\.[A-Za-z0-9]+)$", normalized)
        extension = extension_match.group(1) if extension_match else ""
        if extension and extension not in self.REVIEWABLE_EXTENSIONS:
            return False, f"Unsupported file extension {extension}."

        if item.get("changes", 0) > 1200:
            return False, "Huge file skipped to keep the review focused."
        if not self._matches_path_filters(filename, path_filters):
            return False, "Skipped by custom path filters."

        return True, None

    def _matches_path_filters(self, filename: str, path_filters: list[str]) -> bool:
        normalized_patterns = [pattern.strip() for pattern in path_filters if pattern.strip()]
        if not normalized_patterns:
            return True

        include_patterns = [pattern for pattern in normalized_patterns if not pattern.startswith("!")]
        exclude_patterns = [pattern[1:] for pattern in normalized_patterns if pattern.startswith("!") and len(pattern) > 1]
        normalized_filename = filename.lower()

        def matches(pattern: str) -> bool:
            lowered = pattern.lower()
            return fnmatch(normalized_filename, lowered) or fnmatch(normalized_filename, f"**/{lowered}")

        if include_patterns and not any(matches(pattern) for pattern in include_patterns):
            return False
        if any(matches(pattern) for pattern in exclude_patterns):
            return False
        return True

    def _annotate_patch(self, patch: str) -> str:
        if len(patch) > self.settings.max_patch_chars_per_file:
            patch = patch[: self.settings.max_patch_chars_per_file] + "\n... [truncated]"

        annotated: list[str] = []
        old_line = 0
        new_line = 0
        hunk_pattern = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")

        for raw_line in patch.splitlines():
            hunk_match = hunk_pattern.match(raw_line)
            if hunk_match:
                old_line = int(hunk_match.group("old"))
                new_line = int(hunk_match.group("new"))
                annotated.append(raw_line)
                continue

            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                annotated.append(f"{new_line}: {raw_line}")
                new_line += 1
            elif raw_line.startswith("-") and not raw_line.startswith("---"):
                annotated.append(f"old:{old_line}: {raw_line}")
                old_line += 1
            else:
                annotated.append(f"{new_line}: {raw_line}")
                old_line += 1
                new_line += 1

        return "\n".join(annotated)
