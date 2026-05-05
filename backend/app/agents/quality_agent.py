from app.schemas import FindingsOutput
from app.services.llm_service import LLMService


class CodeQualityAgent:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    def run(self, review_payload: str, summary: str) -> FindingsOutput:
        system_prompt = (
            "You review pull request diffs for maintainability and code quality. "
            "Prefer high-signal feedback over style nitpicks."
        )
        user_prompt = (
            f"PR summary:\n{summary}\n\n"
            "Find duplicated logic, complex control flow, weak naming, missing typing, poor separation of concerns, "
            "and performance risks when visible in the diff. "
            "Use category='quality' for maintainability issues and category='performance' for clear performance problems.\n\n"
            f"{review_payload}"
        )
        return self.llm_service.generate_structured(
            task_name="code_quality",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=FindingsOutput,
        )

