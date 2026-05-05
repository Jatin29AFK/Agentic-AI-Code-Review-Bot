import json

from app.schemas import FinalAggregationOutput, IssueFinding
from app.services.llm_service import LLMService


class FinalReviewAggregatorAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(
        self,
        *,
        summary: str,
        issues: list[IssueFinding],
        test_suggestions: list[str],
        specialist_positive_notes: list[str],
    ) -> FinalAggregationOutput:
        system_prompt = (
            "You are the final review aggregator for an AI code review bot. "
            "Write a concise final summary, keep only distinct positive notes, and keep test suggestions crisp."
        )
        user_prompt = (
            f"Diff summary:\n{summary}\n\n"
            f"Issues:\n{json.dumps([issue.model_dump() for issue in issues], indent=2)}\n\n"
            f"Test suggestions:\n{json.dumps(test_suggestions, indent=2)}\n\n"
            f"Specialist positive notes:\n{json.dumps(specialist_positive_notes, indent=2)}"
        )
        return self.llm_service.generate_structured(
            task_name="final_aggregation",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FinalAggregationOutput,
        )
