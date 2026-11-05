from app.llm.provider import get_llm_provider
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt


def generate_answer(question: str, context: str) -> str:
    provider = get_llm_provider()
    return provider.generate(SYSTEM_PROMPT, build_user_prompt(question, context))
