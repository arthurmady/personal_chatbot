from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from personal_chatbot.backend.src.generation.generate import generate_answer
from personal_chatbot.backend.src.ingestion.ingest import ingest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QuestionRequest(BaseModel):
    question: str

@app.post("/chat")
def chat(request: QuestionRequest):
    all_docs = []

    for file in Path("data").glob("*"):
        if file.is_file():
            file_path = str(file.resolve())
            docs_file = ingest(file_path)
            all_docs.extend(docs_file)
    reponse = generate_answer(request.question, all_docs)
    return {"reponse": reponse}