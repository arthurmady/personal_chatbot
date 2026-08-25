import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

HEADER_REGEX = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

def split_by_header(text: str) -> list[dict]:
    matches = list(HEADER_REGEX.finditer(text))
    sections = []

    for i, match in enumerate(matches):
        title = match.group(1).strip()
       
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append({"title": title, "content": content})

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
    sections = split_by_header(text)
    chunks: list[Document] = []

    for section in sections:
        pieces = split_oversized_section(section["content"], max_chars)

        for part_index, piece in enumerate(pieces):
            metadata = {
                "source": source,
                "title": section["title"]
            }
            if len(pieces) > 1:
                metadata["part"] = f"{part_index + 1}/{len(pieces)}"

            full_content = f"{section['title']}\n{piece}"

            chunks.append(Document(page_content=full_content, metadata=metadata))

    return chunks