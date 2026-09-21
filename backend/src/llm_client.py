from langchain_openai import ChatOpenAI
from config import OPENROUTER_BASE_URL, OPENROUTER_MODEL, OPENROUTER_API_KEY

llm = ChatOpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
    model=OPENROUTER_MODEL,
    extra_body={"provider": {"only": ["groq"], "allow_fallbacks": True}},
)