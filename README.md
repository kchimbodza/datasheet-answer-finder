# Datasheet Answer Finder

Ask a plain question about a hardware datasheet and get an answer **with the exact quote and page it came from**. Every quote is checked, every question is logged, and the system is scored on a 15-question test set.

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-local%20LLMs-000000)
![Chroma](https://img.shields.io/badge/Chroma-vector%20DB-4F46E5)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)

![Demo: asking questions, running the evaluation and viewing the query log](docs/demo.gif)

<sub>28-second demo · [full-quality MP4](docs/demo.mp4)</sub>

## At a glance

| | |
|---|---|
| **What it does** | Answers questions about long hardware datasheets (ESP32, a router, network switches) and shows the exact quote and page number for each answer |
| **Skills shown** | RAG (retrieval-augmented generation), vector search, embeddings, LLM evaluation, LLM observability |
| **Tech** | Python, Ollama (local LLMs), Chroma (vector database), Streamlit (web UI) |
| **Runs** | Fully on a laptop. No cloud services or API keys |

## Key results

- **Better retrieval through measurement:** splitting pages into smaller chunks raised how often the right page is found (top 3 results) from **40% to 73%**.
- **Compared 4 local LLMs on the same test set:** the best, `qwen2.5:7b`, gave correct, verified answers **60%** of the time, compared with 47% for the starting model.
- **Logging exposed a blind spot:** "quote verified" does not mean "answer correct". The query log showed real quotes attached to wrong answers, so I added a "verified but wrong" score.

## Results

**Retrieval: does it find the right page?** (15 test questions)

| Chunking | Right page ranked 1st | Right page in top 3 |
|---|---|---|
| One chunk per page | 3/15 (20%) | 6/15 (40%) |
| ~800-character chunks (current) | **7/15 (47%)** | **11/15 (73%)** |

**Answer models: are the answers correct?** (same retrieval for every model; each model run twice with identical scores)

| Model | Size | Correct + verified | Verified but wrong | Time per question |
|---|---|---|---|---|
| llama3.2 (default) | 3B | 7/15 (47%) | 3 | ~0.8 s |
| **qwen2.5:7b** | 7B | **9/15 (60%)** | **1** | ~1.5 s |
| gemma3:4b | 4B | 8/15 (53%) | 3 | ~1.9 s |
| phi4-mini | 3.8B | 8/15 (53%) | 2 | ~1.5 s |

<sub>Measured on an RTX 4050 laptop GPU (6 GB). "Verified but wrong" = the quote really is in the datasheet, but the answer is wrong.</sub>

## Screenshots

| Ask | Evaluation | Query log |
|---|---|---|
| ![Ask page](docs/app-ask.png) | ![Evaluation page](docs/app-evaluation.png) | ![Logs page](docs/app-logs.png) |

## What I learned

- **Measure before tuning.** Whole-page chunks let short overview pages beat the dense spec tables that hold the numbers. The test set showed this, and smaller chunks fixed much of it.
- **A real quote is not a correct answer.** Asked for the 8-port switch's idle power, the model quoted a real line, but it belonged to the 24-port switch.
- **One run is not enough.** With llama3.2, one question flipped between "240 mA" and "not found" across sessions, with the same code and data.
- **Logs find what tests miss.** On 10 real questions, 8 answers were "verified", but at least 3 of those were wrong or not real answers (for example "Disruptively priced" for a price question).
- **A bigger model helps, but retrieval sets the limit.** The right page was in the top 3 for only 11 of 15 questions, so no answer model can reach 15/15 without better retrieval.

<details>
<summary><b>How it works (technical details)</b></summary>

The tool has two halves. First it builds a searchable index of the datasheets once. Then, for every question, it finds the most relevant text and asks a local LLM to answer from that text only, with a quote that can be checked.

**1. Building the index (`ingest.py`)**
Every PDF page is read with pypdf and cut into chunks of about 800 characters, always breaking between lines. Each chunk remembers its file and page. The `nomic-embed-text` model (in Ollama) turns each chunk into an **embedding**, a list of numbers that represents its meaning. The file name is added in front of each chunk first, so spec tables that never name the product are still linked to it. Everything is stored in Chroma, in the `chroma_db/` folder.

**2. Finding the right text (`search.py`)**
The question is embedded the same way, and Chroma returns the 3 closest chunks by cosine distance (0 = very similar). The embedding model expects a label in front of the text, `search_document:` for chunks and `search_query:` for questions.

**3. Answering with a checkable quote (`ask.py`)**
The 3 chunks and the question go to a local LLM (default `llama3.2`). The prompt requires JSON with an answer and a word-for-word quote, or "not found". The **excerpt check** then looks for that quote in the retrieved chunks, ignoring case, spaces and line breaks (PDFs often break a word like "pull-up" across lines). If it's there, the answer is **verified** with its file and page. Otherwise it's marked **not verified**.

**4. Measuring it (`evaluate.py`, `questions.json`)**
15 test questions, each with the page(s) that hold the answer and a short text the correct answer must contain. The script reports:
- **hit@1 / hit@3**: a chunk from a right page came 1st / was in the top 3
- **good answer**: the answer contains the expected text *and* the quote is verified
- **verified but wrong**: the quote is real but the answer is wrong

`--model` runs the same test with a different answer model.

**5. Logging every question (`ask.py`)**
Each question appends one JSON line to `logs/queries.jsonl` with the model, question, answer, quote, verified / not-found flags, the retrieved chunks and their distances, and the retrieval and LLM times. Test runs are excluded, and the log stays local (it's in `.gitignore`).

**6. The UI (`app.py`)**
A Streamlit app with three pages: **Ask** (chat with verified/not-verified badges and sources), **Evaluation** (runs the test set) and **Logs** (verified rate, not-found rate, timings, recent questions). Colours are in `.streamlit/config.toml` and styles in `style.css`. LLM and PDF text is HTML-escaped before it's shown.

**Known limits**
- One ESP32 page (69, a large pin table) is longer than the embedding model's 2048-token limit, so its end is cut off.
- pypdf reads the ESP32 PDF's minus sign as "⚶"; `ingest.py` replaces it with "-".

</details>

<details>
<summary><b>Run it yourself</b></summary>

```bash
git clone https://github.com/kchimbodza/datasheet-answer-finder.git
cd datasheet-answer-finder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Needs Ollama running locally:
ollama pull nomic-embed-text   # embeddings
ollama pull llama3.2           # answers (default model)

# Put the datasheet PDFs in data/ (see below), then:
python ingest.py                                   # build the index
streamlit run app.py                               # web UI
python ask.py "How much does the Route10 weigh?"   # one question from the terminal
python evaluate.py --answers                       # score the 15 test questions
python evaluate.py --answers --model qwen2.5:7b    # same test, different model
python -m pytest                                   # tests
```

Example output:

```
Answer: 0.46 kg
Quote:  "Weight 0.46 kg (1.01 lbs)"
Verified: quote found on Route10_Datasheet.pdf page 4
```

**Datasheets used** (not in the repo because they belong to their manufacturers; download into `data/`):
- `esp32_datasheet_en.pdf`: ESP32 Series Datasheet v5.3 (78 pages), from https://www.espressif.com/documentation/esp32_datasheet_en.pdf
- `Route10_Datasheet.pdf` (5 pages) and `Alta_Labs_Switches_Datasheet.pdf` (8 pages), from https://www.alta.inc

</details>

## Built with

Python, Ollama, Chroma, Streamlit. Built with help from an AI coding assistant (Claude Code). I planned, reviewed and tested every part.

## Author

**Kudzayi Chimbodza** · [GitHub @kchimbodza](https://github.com/kchimbodza)
