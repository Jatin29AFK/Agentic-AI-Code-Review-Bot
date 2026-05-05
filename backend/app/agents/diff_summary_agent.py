from app.schemas import DiffSummaryOutput
from app.services.llm_service import LLMService


class DiffSummaryAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str) -> DiffSummaryOutput:
        system_prompt = (
            "You are a senior engineer summarizing a pull request for downstream review agents. "
            "Focus on what changed, the modules touched, and delivery risk."
        )
        user_prompt = (
            "Summarize the pull request diff below. "
            "The changed_modules list should use concise, human-readable module names or folders.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="diff_summary",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=DiffSummaryOutput,
        )

