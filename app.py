"""Web UI. Run with: streamlit run app.py"""
from collections import Counter
from html import escape
from pathlib import Path

import streamlit as st

from ask import CHAT_MODEL, ask, read_log
from evaluate import K, load_questions, score_question
from search import EMBED_MODEL, get_collection

st.set_page_config(page_title="Datasheet Answer Finder", page_icon="📄", layout="wide")
st.markdown(f"<style>{Path('style.css').read_text()}</style>", unsafe_allow_html=True)

EXAMPLES = [
    "How much current does the ESP32 draw when transmitting 802.11b at full power?",
    "What is the PoE budget of the S24-PoE switch?",
    "How much does the Route10 weigh?",
]


@st.cache_data
def chunks_per_datasheet():
    metadatas = get_collection().get(include=["metadatas"])["metadatas"]
    return Counter(m["source"] for m in metadatas)


def page_header(title, subtitle):
    st.markdown(f'<p class="page-title">{title}</p><p class="page-sub">{subtitle}</p>', unsafe_allow_html=True)


def show_answer(result):
    """Answer card: answer, verified badge, quote, then the retrieved chunks."""
    if result["source"]:
        badge = f'<span class="badge ok">✓ Verified · {escape(result["source"]["source"])} · page {result["source"]["page"]}</span>'
    else:
        badge = '<span class="badge bad">✕ Not verified: quote not found in the retrieved text</span>'
    # escape() so text from the LLM or the PDF is shown as text, never run as HTML
    quote = f'<div class="quote">{escape(result["quote"])}</div>' if result["quote"] else ""
    st.markdown(
        f'<div class="answer-card"><div class="answer-text">{escape(result["answer"])}</div>{badge}{quote}</div>',
        unsafe_allow_html=True,
    )
    with st.expander(f"Sources: top {len(result['hits'])} retrieved chunks"):
        for hit in result["hits"]:
            st.markdown(
                f'<p class="source-head">{escape(hit["source"])}, page {hit["page"]} '
                f'<span>· distance {hit["distance"]:.3f}</span></p>',
                unsafe_allow_html=True,
            )
            st.text(hit["text"])


# ---------- Sidebar: brand, navigation, indexed datasheets ----------
with st.sidebar:
    st.markdown('<div class="brand"><div class="brand-icon">📄</div>Datasheet Finder</div>', unsafe_allow_html=True)
    st.write("")
    page = st.radio(
        "Navigation",
        [":material/chat: Ask", ":material/analytics: Evaluation", ":material/receipt_long: Logs"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown('<p class="side-label">Indexed datasheets</p>', unsafe_allow_html=True)
    for source, count in chunks_per_datasheet().items():
        st.markdown(f'<div class="doc"><span>{escape(source)}</span><span>{count} chunks</span></div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<p class="side-label">Models (local, Ollama)</p>', unsafe_allow_html=True)
    st.caption(f"Embeddings: {EMBED_MODEL}  \nAnswers: {CHAT_MODEL}")

# ---------- Ask: chat-style question and answer ----------
if page.endswith("Ask"):
    page_header("Ask a datasheet", "Every answer comes with the exact quote and page it came from, and the quote is checked.")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.write(message["content"])
            else:
                show_answer(message["content"])

    question = st.chat_input("Ask about a pin, a voltage, a power figure…")
    if not st.session_state.messages:
        st.caption("Try one of these:")
        for column, example in zip(st.columns(len(EXAMPLES)), EXAMPLES):
            if column.button(example, use_container_width=True):
                question = example

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.spinner("Searching the datasheets…"):
            result = ask(question, K)
        st.session_state.messages.append({"role": "assistant", "content": result})
        st.rerun()

# ---------- Evaluation: score the 15 test questions ----------
elif page.endswith("Evaluation"):
    questions = load_questions()
    page_header("Evaluation", f"{len(questions)} test questions, each with the page(s) where the answer is printed.")
    check_answers = st.toggle("Also check the LLM answers (slower)", value=True)
    if st.button("Run evaluation", type="primary", icon=":material/play_arrow:"):
        progress = st.progress(0.0, text="Scoring questions…")
        rows = []
        for i, q in enumerate(questions, start=1):
            rows.append(score_question(q, check_answers))
            progress.progress(i / len(questions), text=f"Scoring questions… {i}/{len(questions)}")
        progress.empty()
        st.session_state.eval_rows = rows  # keep results when switching pages

    rows = st.session_state.get("eval_rows")
    if rows:
        metrics = ["hit@1", f"hit@{K}"] + (["good answer"] if "good answer" in rows[0] else [])
        for column, key in zip(st.columns(len(metrics)), metrics):
            total = sum(r[key] for r in rows)
            column.metric(key, f"{total}/{len(rows)}  ({total / len(rows):.0%})")
        st.write("")
        # Show every row (about 35 px each) and put the answer before the long "retrieved" column.
        columns = [c for c in rows[0] if c != "retrieved"] + ["retrieved"]
        st.dataframe(rows, column_order=columns, height=35 * (len(rows) + 1) + 3, hide_index=True)

# ---------- Logs: every question asked, for review ----------
else:
    log = read_log()  # one record per question asked on the Ask page or with ask.py
    page_header("Query log", "Every question asked, with its result and timing, so problems can be found later.")
    if not log:
        st.info("No questions logged yet. Ask one on the Ask page.")
    else:
        n = len(log)
        verified = sum(r["verified"] for r in log)
        not_found = sum(r["not_found"] for r in log)
        cols = st.columns(4)
        cols[0].metric("Questions", n)
        cols[1].metric(f"Verified ({verified}/{n})", f"{verified / n:.0%}")
        cols[2].metric(f"Not found ({not_found}/{n})", f"{not_found / n:.0%}")
        cols[3].metric("Avg response", f"{sum(r['retrieval_ms'] + r['llm_ms'] for r in log) / n / 1000:.1f} s")
        st.caption(
            f"Average retrieval {sum(r['retrieval_ms'] for r in log) / n:.0f} ms · "
            f"average LLM {sum(r['llm_ms'] for r in log) / n:.0f} ms"
        )
        rows = [
            {
                "time": r["time"][:16].replace("T", " "),  # e.g. 2026-11-07 22:31 (UTC)
                # entries logged before the model field was added all came from llama3.2
                "model": r.get("model", "llama3.2"),
                "question": r["question"],
                "answer": r["answer"],
                "verified": r["verified"],
                "best distance": r["retrieved"][0]["distance"],
                "top source": f"{r['retrieved'][0]['source']} p.{r['retrieved'][0]['page']}",
                "total ms": r["retrieval_ms"] + r["llm_ms"],
            }
            for r in reversed(log)
        ]
        st.dataframe(rows, hide_index=True, height=min(35 * (len(rows) + 1) + 3, 600))
