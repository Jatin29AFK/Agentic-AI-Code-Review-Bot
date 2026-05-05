from app.schemas import TestSuggestionOutput
from app.services.llm_service import LLMService


class TestSuggestionAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str, summary: str) -> TestSuggestionOutput:
        system_prompt = (
            "You suggest high-value tests that should accompany a pull request. "
            "Recommend concrete scenarios, not vague reminders."
        )
        user_prompt = (
            f"PR summary:\n{summary}\n\n"
            "Suggest unit, integration, API, edge-case, or security tests that are missing based on the diff below.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="test_suggestions",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=TestSuggestionOutput,
        )

