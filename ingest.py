"""Read every PDF in data/, split each page into small chunks, embed them and store them in Chroma."""
from pathlib import Path

import chromadb
from pypdf import PdfReader

from search import COLLECTION, DB_PATH, embed, get_collection

CHUNK_CHARS = 800  # small enough that one chunk is about one topic


def load_pages(folder="data"):
    pages = []
    for pdf_path in sorted(Path(folder).glob("*.pdf")):
        for number, page in enumerate(PdfReader(pdf_path).pages, start=1):
            # The ESP32 PDF's minus sign comes out as "⚶"; fix it so quotes like "-40 °C" still match.
            text = page.extract_text().replace("⚶", "-").strip()
            if text:
                pages.append({"source": pdf_path.name, "page": number, "text": text})
    return pages


def split_page(text):
    """Group whole lines into chunks of at most about CHUNK_CHARS characters."""
    chunks, current = [], ""
    for line in text.splitlines():
        if current and len(current) + len(line) > CHUNK_CHARS:
            chunks.append(current)
            current = ""
        current += line + "\n"
    return chunks + [current]


if __name__ == "__main__":
    chunks = []
    for p in load_pages():
        for i, text in enumerate(split_page(p["text"])):
            chunks.append({"id": f"{p['source']}-p{p['page']}-c{i}", **p, "text": text})

    # Start fresh each run so re-ingesting never leaves duplicate chunks behind.
    client = chromadb.PersistentClient(path=DB_PATH)
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    get_collection().add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        # Put the file name in front so a spec table that never names the product is still linked to it.
        embeddings=embed([f"{c['source']}\n{c['text']}" for c in chunks], "search_document: "),
        metadatas=[{"source": c["source"], "page": c["page"]} for c in chunks],
    )
    print(f"Stored {len(chunks)} chunks in {DB_PATH}/")
