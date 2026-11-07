"""Answer a question from the datasheets, quoting the exact excerpt, and check the quote is real."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ollama

from search import retrieve

CHAT_MODEL = "llama3.2"
LOG_PATH = Path("logs/queries.jsonl")

PROMPT = """Answer the question using ONLY the datasheet pages below.
Reply in JSON with three keys:
  "answer": a short answer,
  "quote": one sentence copied word for word from the pages that supports the answer,
  "page_id": the id of the page the quote came from (for example "demo-mcu32.pdf p.4").
If the pages do not contain the answer, set "answer" to "not found" and "quote" to "".

{pages}

Question: {question}"""


def normalise(text):
    # Drop ALL whitespace: PDFs break lines mid-word ("pull-\nup"), and the model rejoins them ("pull-up").
    return "".join(text.lower().split()).strip(".\"'")


def find_quote(quote, hits):
    """Excerpt check: return the page the quote appears on word for word, or None if it is made up."""
    if not normalise(quote):
        return None
    for hit in hits:
        if normalise(quote) in normalise(hit["text"]):
            return hit
    return None


def ask(question, k=3, log=True, model=CHAT_MODEL):
    start = time.perf_counter()
    hits = retrieve(question, k)
    retrieval_ms = (time.perf_counter() - start) * 1000

    pages = "\n\n".join(f"[{h['source']} p.{h['page']}]\n{h['text']}" for h in hits)
    start = time.perf_counter()
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(pages=pages, question=question)}],
        format="json",
        options={"temperature": 0},
    )
    llm_ms = (time.perf_counter() - start) * 1000

    reply = json.loads(response["message"]["content"])
    answer, quote = str(reply.get("answer", "")), str(reply.get("quote", ""))
    result = {"answer": answer, "quote": quote, "source": find_quote(quote, hits), "hits": hits}
    if log:
        log_query(question, result, retrieval_ms, llm_ms, model)
    return result


def log_query(question, result, retrieval_ms, llm_ms, model=CHAT_MODEL):
    """Observability: append one JSON line per question so usage can be reviewed later."""
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": model,
        "question": question,
        "answer": result["answer"],
        "quote": result["quote"],
        "verified": result["source"] is not None,
        "not_found": result["answer"].strip().lower() == "not found",
        "retrieved": [
            {"source": h["source"], "page": h["page"], "distance": round(h["distance"], 3)}
            for h in result["hits"]
        ],
        "retrieval_ms": round(retrieval_ms),
        "llm_ms": round(llm_ms),
    }
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(record) + "\n")


def read_log():
    if not LOG_PATH.exists():
        return []
    return [json.loads(line) for line in LOG_PATH.read_text().splitlines() if line.strip()]


if __name__ == "__main__":
    result = ask(" ".join(sys.argv[1:]) or "What is the deep-sleep current of the DEMO-MCU32?")
    print("Answer:", result["answer"])
    print(f'Quote:  "{result["quote"]}"')
    if result["source"]:
        print(f"Verified: quote found on {result['source']['source']} page {result['source']['page']}")
    else:
        print("NOT VERIFIED: quote is not in the retrieved pages, so do not trust this answer")
