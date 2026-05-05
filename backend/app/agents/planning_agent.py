from app.schemas import ReviewPlanOutput
from app.services.llm_service import LLMService


class PlanningAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str, summary: str) -> ReviewPlanOutput:
        system_prompt = (
            "You are a review planner. Decide which specialized reviewers should run on a pull request. "
            "Allowed agent values are: bug, security, quality, testing."
        )
        user_prompt = (
            f"PR summary:\n{summary}\n\n"
            "Choose the most relevant specialist checks based on the diff below. "
            "Do not include unnecessary agents.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="planning",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=ReviewPlanOutput,
        )

