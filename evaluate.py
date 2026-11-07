"""Score the system on questions.json.

Retrieval: how often a right page (some facts appear on more than one page) is the top match (hit@1) or in the top 3 (hit@3).
With --answers it also asks the LLM and counts answers that contain the expected text
AND pass the excerpt check (the quote really is on a retrieved page).
"""
import json
import sys

from search import retrieve

K = 3


def is_right_page(hit, q):
    return hit["source"] == q["source"] and hit["page"] in q["pages"]


def score_question(q, check_answers=False):
    hits = retrieve(q["question"], K)
    row = {
        "question": q["question"],
        "hit@1": is_right_page(hits[0], q),
        f"hit@{K}": any(is_right_page(h, q) for h in hits),
        "retrieved": ", ".join(f"{h['source']} p.{h['page']}" for h in hits),
    }
    if check_answers:
        from ask import ask

        result = ask(q["question"], K, log=False)  # keep test runs out of the usage log
        correct = q["answer_contains"].lower() in result["answer"].lower()
        row["answer"] = result["answer"]
        row["good answer"] = correct and result["source"] is not None
    return row


def load_questions():
    return json.load(open("questions.json"))


if __name__ == "__main__":
    check_answers = "--answers" in sys.argv
    rows = []
    for q in load_questions():
        row = score_question(q, check_answers)
        rows.append(row)
        status = "OK  " if row["hit@1"] else ("top3" if row[f"hit@{K}"] else "MISS")
        print(f"{status} {row['question']}")
        if check_answers:
            print(f"      answer: {row['answer']!r} ({'good' if row['good answer'] else 'BAD'})")

    n = len(rows)
    for key in ["hit@1", f"hit@{K}"] + (["good answer"] if check_answers else []):
        total = sum(r[key] for r in rows)
        print(f"{key}: {total}/{n} ({total / n:.0%})")
