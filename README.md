# Researcher

A Streamlit research assistant using Claude and Tavily, with PDF retrieval through Pinecone and local Hugging Face embeddings.

## Features

- Ask follow-up questions using conversation history.
- Use **Clear chat** to remove the current conversation and its source list while keeping uploaded files available. Download the chat first if you want to keep it.
- Inspect the sources consulted for each answer.
- See how many Claude calls and tokens each answer used, with an estimated cost at Claude Haiku 4.5 list prices.
- Long answers cut off at the length limit are shown with a note instead of being discarded.
- Choose 1–5 results per search. Repeated searches within a question reuse results.
- Upload PDFs for retrieval or images for visual questions. PDF search combines vector search with a cross-encoder reranker (`ms-marco-MiniLM-L6-v2`) that picks the four chunks sent to Claude; **Inspect reranking** shows every candidate's score and which ones were sent.
- **Test keyword search** runs BM25 keyword scoring over the indexed PDF's chunks.
- **Client requirements**: upload a brief or transcript PDF and extract a checklist. Each requirement must come with a quote that is found word for word on its page, or nothing is saved. Mark items reviewed and done, and download the checklist as JSON.
- Download a plain-text transcript, including source links.

Sources consulted are pages returned by search, not a guarantee that every claim is supported. Review the links before relying on an answer.

## Setup

Use Python 3.10 or newer. From the project root:

```sh
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks `Activate.ps1`, skip activation and call the venv's Python directly, for example `.\venv\Scripts\python.exe -m pip install -r requirements.txt`. The install includes PyTorch through `sentence-transformers`, so it takes a few minutes.

Create `researcher/.env` with your own credentials:

```dotenv
ANTHROPIC_API_KEY=your_key
TAVkey=your_key
PINECONE_API_KEY=your_key
```

Create a Pinecone index named `research`, configured for the 384-dimensional `all-MiniLM-L6-v2` embeddings. The first embedding use downloads the embedding model, and the first PDF question downloads the reranker model. Claude, Tavily, and Pinecone require accounts and may incur charges.

Run the maintained entry point:

```sh
cd researcher
python -m streamlit run Research.py
```

## Structure

```text
researcher/
  Research.py              Streamlit UI, PDF ingestion, reranking and agent loop
  research_tools.py        Source, WebSearch, Usage and ChatExport classes
  client_requirements.py   Requirement extraction and quote validation
  requirements_ui.py       Client requirements checklist panel
  test_research_tools.py   Offline helper tests
requirements.txt         Application dependencies
```

`app.py`, `task1.py`, and `task2.py` and `task3.py` are earlier development files; use `Research.py` for this version.

`WebSearch` owns source collection and a per-question cache. `ChatExport` formats transcripts independently of Streamlit. These classes can be tested without API credentials.

## Checks

From the project root:

```sh
python -m unittest discover -s researcher -p "test_*.py" -v
```

The offline tests cover search reuse, source deduplication, link filtering, retry after failure, blank queries, token usage totals and text transcripts. They do not exercise live APIs or the Streamlit interface.

## Current limitations

- PDF indexing uses a shared Pinecone index without session namespaces. This version is for a personal demo, not a multi-user deployment. The database-clear button deletes all vectors in that index.
- Conversation history stays in the current Streamlit session.
- Prior image attachments are not resent on later questions.
- API credentials are required at startup for all services.

## License

Apache-2.0. See [LICENSE](LICENSE). Models and services used at runtime have their own terms; see [docs/PLAN.md](docs/PLAN.md) section 6.
