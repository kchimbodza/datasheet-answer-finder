"""Answer a question from the datasheets, quoting the exact excerpt, and check the quote is real."""
import json
import sys

import ollama

from search import retrieve

CHAT_MODEL = "llama3.2"

PROMPT = """Answer the question using ONLY the datasheet pages below.
Reply in JSON with three keys:
  "answer": a short answer,
  "quote": one sentence copied word for word from the pages that supports the answer,
  "page_id": the id of the page the quote came from (for example "demo-mcu32.pdf p.4").
If the pages do not contain the answer, set "answer" to "not found" and "quote" to "".

{pages}

Question: {question}"""


def normalise(text):
    return " ".join(text.lower().split()).strip(" .\"'")


def find_quote(quote, hits):
    """Excerpt check: return the page the quote appears on word for word, or None if it is made up."""
    if not normalise(quote):
        return None
    for hit in hits:
        if normalise(quote) in normalise(hit["text"]):
            return hit
    return None


def ask(question, k=3):
    hits = retrieve(question, k)
    pages = "\n\n".join(f"[{h['source']} p.{h['page']}]\n{h['text']}" for h in hits)
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": PROMPT.format(pages=pages, question=question)}],
        format="json",
        options={"temperature": 0},
    )
    reply = json.loads(response["message"]["content"])
    answer, quote = str(reply.get("answer", "")), str(reply.get("quote", ""))
    return {"answer": answer, "quote": quote, "source": find_quote(quote, hits), "hits": hits}


if __name__ == "__main__":
    result = ask(" ".join(sys.argv[1:]) or "What is the deep-sleep current of the DEMO-MCU32?")
    print("Answer:", result["answer"])
    print(f'Quote:  "{result["quote"]}"')
    if result["source"]:
        print(f"Verified: quote found on {result['source']['source']} page {result['source']['page']}")
    else:
        print("NOT VERIFIED: quote is not in the retrieved pages, so do not trust this answer")
