# src/chunking/chunk.py

import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Matche une ligne "## Titre [tag1, tag2]" — les tags entre crochets sont optionnels
HEADER_REGEX = re.compile(r"^## (.+?)(?:\s*\[([^\]]*)\])?\s*$", re.MULTILINE)


def split_by_header(text: str) -> list[dict]:
    """
    Découpe le texte markdown en sections, une par header de niveau ##.
    Retourne une liste de dicts {"title", "tags", "content"}.

    Logique : on trouve toutes les positions des headers, puis le contenu
    d'une section va de la fin d'un header jusqu'au début du header suivant
    (ou la fin du texte pour la dernière section).
    """
    matches = list(HEADER_REGEX.finditer(text))
    sections = []

    for i, match in enumerate(matches):
        title = match.group(1).strip()
        tags_raw = match.group(2)  # None si pas de crochets sur cette ligne
        tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append({"title": title, "tags": tags, "content": content})

    return sections


def split_oversized_section(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=int(max_chars * 0.1),
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(content)


def chunk_markdown_by_header(text: str, source: str, max_chars: int = 500) -> list[Document]:
    """
    Orchestrateur : un chunk par header ##, sous-découpé seulement si
    nécessaire. Chaque chunk garde le titre et les tags en metadata,
    exploitables ensuite pour filtrer le retrieval (étape 4).
    """
    sections = split_by_header(text)
    chunks: list[Document] = []

    for section in sections:
        pieces = split_oversized_section(section["content"], max_chars)

        for part_index, piece in enumerate(pieces):
            metadata = {
                "source": source,
                "title": section["title"],
                "tags": section["tags"],
            }
            if len(pieces) > 1:
                metadata["part"] = f"{part_index + 1}/{len(pieces)}"

            # Important : on remet le titre en tête du contenu de CHAQUE
            # chunk (même les sous-morceaux). Sans ça, si le retrieval
            # renvoie un sous-chunk isolé, on perd le contexte du titre
            # ("Sodebo - Montaigu" sans savoir que c'est un stage).
            full_content = f"## {section['title']}\n{piece}"

            chunks.append(Document(page_content=full_content, metadata=metadata))

    return chunks