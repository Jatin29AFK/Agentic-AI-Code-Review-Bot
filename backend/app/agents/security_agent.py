from app.schemas import FindingsOutput
from app.services.llm_service import LLMService


class SecurityReviewAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str, summary: str) -> FindingsOutput:
        system_prompt = (
            "You review pull request diffs for application security risks. "
            "Only flag security issues supported by the patch."
        )
        user_prompt = (
            f"PR summary:\n{summary}\n\n"
            "Look for secret exposure, injection risk, missing auth checks, insecure CORS, unsafe file handling, "
            "sensitive logging, and misuse of eval or shell execution. "
            "Use category='security' for all findings.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="security_review",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FindingsOutput,
        )

