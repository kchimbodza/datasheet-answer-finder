# Datasheet Answer Finder

Ask a plain question about a hardware datasheet (ESP32, a router and network switches) and get an answer with the exact page excerpt it came from, plus a score showing how often it finds the right page on a small question set.

![Asking a question: the answer, the verified quote and the retrieved chunks](docs/ask-verified.png)

| When the answer is not in the retrieved text | Evaluation on 15 test questions |
|---|---|
| ![Not verified](docs/ask-not-verified.png) | ![Evaluation tab](docs/evaluation.png) |

## Why I built this

I wanted hands-on practice with **Python**, so I built a small, complete tool with it in about an hour.

## How to run it

```bash
git clone https://github.com/kchimbodza/datasheet-answer-finder.git
cd datasheet-answer-finder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Needs Ollama running locally with these two models:
ollama pull nomic-embed-text   # makes the embeddings
ollama pull llama3.2           # writes the answers

# Put the datasheet PDFs in data/ (they are not in this repo, see below)
python ingest.py               # splits pages into chunks, embeds them, stores them in chroma_db/
streamlit run app.py           # web UI: ask questions and run the evaluation
python ask.py "How much current does the ESP32 draw when transmitting 802.11b at full power?"
python evaluate.py             # retrieval score on the 15 test questions
python evaluate.py --answers   # also scores the LLM answers (slower)
python -m pytest               # tests for the excerpt check
```

Example output:

```
Answer: 240 mA
Quote:  "T able 5-4. Current Consumption Depending on RF Modes
Work Mode Min T yp Max Unit
T ransmit 802.11b, DSSS 1 Mbps, POUT = +19.5 dBm — 240 — mA"
Verified: quote found on esp32_datasheet_en.pdf page 52
```

### Datasheets used

The PDFs are not committed because they belong to their manufacturers. Download them into `data/`:

- `esp32_datasheet_en.pdf`: ESP32 Series Datasheet v5.3 (78 pages), from
  https://www.espressif.com/documentation/esp32_datasheet_en.pdf
- `Route10_Datasheet.pdf` (5 pages) and `Alta_Labs_Switches_Datasheet.pdf` (8 pages), from
  https://www.alta.inc

## How it works

The tool has two halves. First it builds a searchable index of the datasheets once. Then, for
every question, it finds the most relevant text and asks a local LLM to answer from that text
only, with a quote I can check.

**1. Building the index (`ingest.py`)**

I read every PDF in `data/` page by page with pypdf. A whole datasheet page often covers several
topics (a power table, some notes, part of the next section), so I cut each page into smaller
chunks of about 800 characters, always breaking between lines. Each chunk remembers which file
and page it came from, because the page number is what the user sees as the source and what the
evaluation checks.

Next I turn each chunk into an **embedding**: a list of numbers that represents what the text is
about, so texts with similar meaning end up with similar numbers. I use the free
`nomic-embed-text` model running locally in Ollama. Before embedding, I add the file name to the
front of the chunk. Spec tables often never mention the product name, so this links them to the
right product. Everything is stored in Chroma, a vector database that saves to the `chroma_db/`
folder.

**2. Finding the right text (`search.py`)**

When a question comes in, I embed it with the same model and ask Chroma for the 3 chunks whose
embeddings are closest to it. "Closest" is measured with cosine distance: 0 means pointing in the
same direction (very similar), and bigger numbers mean less similar. The embedding model expects
a small label in front of the text, `search_document:` for stored chunks and `search_query:` for
questions, so I add those.

**3. Answering with a quote I can check (`ask.py`)**

I send those 3 chunks and the question to `llama3.2`, also running locally in Ollama. The prompt
says to answer only from those chunks and to reply in JSON with an answer, a sentence copied word
for word as the quote, and where it came from. If the answer isn't there, it should say
"not found".

LLMs can make things up, so I don't trust the quote just because the model gave one. My
**excerpt check** looks for the quote inside the chunks that were actually retrieved (ignoring
upper/lower case and extra spaces). If it's there, the answer is shown as verified with its file
and page. If not, it's marked **NOT VERIFIED**. This catches invented or reworded quotes. It
can't tell whether a real quote actually answers the question; the failures below show this.

**4. Measuring it (`evaluate.py` and `questions.json`)**

I wrote 15 test questions. For each one I looked up which page(s) of the datasheet print the
answer, plus a short piece of text the right answer must contain (for example "240" for 240 mA).
The script asks every question and counts:

- **hit@1**: the top chunk came from a right page.
- **hit@3**: a chunk from a right page was anywhere in the top 3.
- **good answer** (with `--answers`): the LLM's answer contains the expected text **and** its
  quote passed the excerpt check.

This turns "does it work?" into numbers I can compare. That's how I found that smaller chunks
roughly doubled retrieval accuracy.

**5. The UI (`app.py`)**

A small Streamlit page that uses the same functions. One tab asks a question and shows the answer,
the verification result, the quote and the 3 retrieved chunks. The other tab runs the evaluation
and shows the scores and a row for every question.

### Results (15 questions, measured on my machine)

| Measure | One chunk per page | ~800-character chunks (current) |
|---|---|---|
| Right page ranked 1st (hit@1) | 3/15 (20%) | 7/15 (47%) |
| Right page in top 3 (hit@3) | 6/15 (40%) | 11/15 (73%) |
| Answer correct **and** quote verified | 5/15 (33%) | 8/15 (53%) |

With whole pages, short prose pages (overview, feature lists) kept beating the dense spec
tables that hold the actual numbers. Smaller chunks fixed much of that.

### What I learned from the failures

- **The quote check proves a quote exists, not that it answers the question.** Asked for the
  idle power of the 8-port switch, the model answered "15 Watts" with a real, verified quote,
  but it came from the 24-port switch's spec page. Splitting the page had cut the table rows away
  from the header that says which switch they belong to.
- **A page-level hit is not always enough.** For the ESP32 deep-sleep question, a chunk from the
  right page (30) came first, but it was the prose part of the page, not the table row with
  "10 µA", so the model correctly said "not found".
- A verified quote can still be a non-answer. Asked for the Route10's retail price (not in the
  datasheet), the model answered "Disruptively priced" with a real quote from page 2
  ([screenshot](docs/ask-quote-but-no-answer.png)).
- One ESP32 page (69, a large pin table) is longer than the embedding model's 2048-token limit,
  so the end of it is cut off before embedding.
- pypdf reads the ESP32 PDF's minus sign as "⚶", so `ingest.py` replaces it with "-".

## Built with

Python, Ollama, Chroma

Built with help from an AI coding assistant (Claude Code). I planned, reviewed and tested every part.

## Author

**Kudzayi Chimbodza** · [GitHub @kchimbodza](https://github.com/kchimbodza)
