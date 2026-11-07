"""Web UI. Run with: streamlit run app.py"""
import streamlit as st

from ask import ask
from evaluate import K, load_questions, score_question

st.set_page_config(page_title="Datasheet Answer Finder", page_icon="📄", layout="wide")
st.title("📄 Datasheet Answer Finder")
st.caption("Ask a question about the datasheets. Every answer comes with the exact quote and page it came from.")

ask_tab, eval_tab = st.tabs(["Ask a question", "Evaluation"])

with ask_tab:
    question = st.text_input("Question", placeholder="How much current does the ESP32 draw in deep sleep?")
    if question:
        with st.spinner("Searching the datasheets..."):
            result = ask(question, K)

        st.subheader(result["answer"])
        if result["source"]:
            st.success(f"Quote verified on **{result['source']['source']}**, page {result['source']['page']}")
        else:
            st.error("Not verified: the quote is not in the retrieved pages, so do not trust this answer.")
        if result["quote"]:
            st.markdown("> " + result["quote"].replace("\n", "\n> "))

        st.markdown(f"**Top {K} retrieved chunks** (lower distance = more similar)")
        for hit in result["hits"]:
            with st.expander(f"{hit['source']}, page {hit['page']} (distance {hit['distance']:.3f})"):
                st.text(hit["text"])

with eval_tab:
    questions = load_questions()
    st.write(f"{len(questions)} test questions, each with the page(s) where the answer is printed.")
    check_answers = st.checkbox("Also check the LLM answers (slower)")
    if st.button("Run evaluation", type="primary"):
        progress = st.progress(0.0)
        rows = []
        for i, q in enumerate(questions, start=1):
            rows.append(score_question(q, check_answers))
            progress.progress(i / len(questions))

        metrics = ["hit@1", f"hit@{K}"] + (["good answer"] if check_answers else [])
        for column, key in zip(st.columns(len(metrics)), metrics):
            total = sum(r[key] for r in rows)
            column.metric(key, f"{total}/{len(rows)} ({total / len(rows):.0%})")
        # Show every row (about 35 px each) and put the answer before the long "retrieved" column.
        columns = [c for c in rows[0] if c != "retrieved"] + ["retrieved"]
        st.dataframe(rows, column_order=columns, height=35 * (len(rows) + 1) + 3, hide_index=True)
