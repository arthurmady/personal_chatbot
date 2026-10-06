from langchain_openai import ChatOpenAI
from config import OPENROUTER_BASE_URL, OPENROUTER_MODEL, OPENROUTER_API_KEY

llm = ChatOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
    model=OPENROUTER_MODEL,
    timeout=60,
    max_retries=2,
    extra_body={"provider": {"only": ["groq"], "allow_fallbacks": True}},
)