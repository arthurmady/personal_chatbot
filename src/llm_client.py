from openai import OpenAI
from config import OMNIROUTE_BASE_URL, OMNIROUTE_MODEL, OMNIROUTE_API_KEY

client = OpenAI(
    base_url=OMNIROUTE_BASE_URL,
    api_key=OMNIROUTE_API_KEY,
)

def ask_llm(messages: list[dict], model: str = OMNIROUTE_MODEL) -> str:
    """
    messages: liste au format [{"role": "user", "content": "..."}]
    Retourne le texte de la réponse.
    """
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content

##########################
from pathlib import Path

prompt = Path("CONTENT.txt").read_text(
    encoding="utf-8"
)

if __name__ == "__main__":
    response = ask_llm([
        {
            "role": "user",
            "content": prompt,
        }
    ])

    print(response)
