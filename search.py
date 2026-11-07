"""Embeddings (via Ollama) and retrieval (via Chroma)."""
import chromadb
import ollama

EMBED_MODEL = "nomic-embed-text"
DB_PATH = "chroma_db"
COLLECTION = "datasheets"


def embed(texts, prefix):
    # nomic-embed-text expects "search_document: " for stored text and "search_query: " for questions.
    response = ollama.embed(model=EMBED_MODEL, input=[prefix + t for t in texts])
    return response["embeddings"]


def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    # cosine distance: 0 = same direction (very similar), larger = less similar
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def retrieve(question, k=3):
    """Return the k pages most similar to the question, best first."""
    results = get_collection().query(
        query_embeddings=embed([question], "search_query: "), n_results=k
    )
    return [
        {"source": meta["source"], "page": meta["page"], "text": text, "distance": dist}
        for text, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


if __name__ == "__main__":
    import sys

    for hit in retrieve(" ".join(sys.argv[1:]) or "deep sleep current"):
        print(f"{hit['source']} p.{hit['page']}  distance={hit['distance']:.3f}")
