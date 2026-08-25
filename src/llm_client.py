from langchain_openai import ChatOpenAI
from personal_chatbot.config import OMNIROUTE_BASE_URL, OMNIROUTE_MODEL, OMNIROUTE_API_KEY

llm = ChatOpenAI(
    base_url=OMNIROUTE_BASE_URL,
    api_key=OMNIROUTE_API_KEY, 
    model=OMNIROUTE_MODEL,
)