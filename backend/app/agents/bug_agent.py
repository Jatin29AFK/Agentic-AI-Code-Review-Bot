from app.schemas import FindingsOutput
from app.services.llm_service import LLMService


class BugDetectionAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str, summary: str) -> FindingsOutput:
        system_prompt = (
            "You review pull request diffs for likely implementation bugs. "
            "Return only practical findings grounded in the changed code. "
            "Do not invent issues when the diff does not support them."
        )
        user_prompt = (
            f"PR summary:\n{summary}\n\n"
            "Look for null handling problems, incorrect conditions, async mistakes, missing error handling, "
            "broken API usage, and edge-case regressions. "
            "Every issue must use category='bug' unless it is clearly a performance issue.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="bug_detection",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FindingsOutput,
        )

