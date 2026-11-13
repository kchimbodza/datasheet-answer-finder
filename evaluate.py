"""Score the system on questions.json.

Retrieval: how often a right page (some facts appear on more than one page) is the top match (hit@1) or in the top 3 (hit@3).
With --answers it also asks the LLM and counts answers that contain the expected text
AND pass the excerpt check (the quote really is on a retrieved page).
"""
import json
import sys
import time

from search import retrieve

K = 3


def is_right_page(hit, q):
    return hit["source"] == q["source"] and hit["page"] in q["pages"]


def score_question(q, check_answers=False, model=None):
    hits = retrieve(q["question"], K)
    row = {
        "question": q["question"],
        "hit@1": is_right_page(hits[0], q),
        f"hit@{K}": any(is_right_page(h, q) for h in hits),
        "retrieved": ", ".join(f"{h['source']} p.{h['page']}" for h in hits),
    }
    if check_answers:
        from ask import CHAT_MODEL, ask

        # log=False keeps test runs out of the usage log
        result = ask(q["question"], K, log=False, model=model or CHAT_MODEL)
        correct = q["answer_contains"].lower() in result["answer"].lower()
        row["answer"] = result["answer"]
        row["good answer"] = correct and result["source"] is not None
        row["verified but wrong"] = result["source"] is not None and not correct
    return row


def load_questions():
    return json.load(open("questions.json"))


if __name__ == "__main__":
    check_answers = "--answers" in sys.argv
    # e.g. python evaluate.py --answers --model qwen2.5:7b --save
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
    start = time.perf_counter()
    rows = []
    for q in load_questions():
        row = score_question(q, check_answers, model)
        rows.append(row)
        status = "OK  " if row["hit@1"] else ("top3" if row[f"hit@{K}"] else "MISS")
        print(f"{status} {row['question']}")
        if check_answers:
            print(f"      answer: {row['answer']!r} ({'good' if row['good answer'] else 'BAD'})")

    n = len(rows)
    for key in ["hit@1", f"hit@{K}"] + (["good answer", "verified but wrong"] if check_answers else []):
        total = sum(r[key] for r in rows)
        print(f"{key}: {total}/{n} ({total / n:.0%})")
    print(f"average time per question: {(time.perf_counter() - start) / n:.1f} s")

    if "--save" in sys.argv:  # per-question results, e.g. results/qwen2.5:7b.json
        from pathlib import Path

        name = (model or "retrieval") if check_answers else "retrieval"
        if check_answers and not model:
            from ask import CHAT_MODEL
            name = CHAT_MODEL
        out = Path("results") / f"{name.replace(':', '-')}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
        print(f"saved {out}")
