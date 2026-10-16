# Researcher

A Streamlit research assistant using Claude and Tavily, with PDF retrieval through Pinecone and local Hugging Face embeddings.

## Features

- Ask follow-up questions using conversation history.
- Inspect the sources consulted for each answer.
- Choose 1–5 results per search. Repeated searches within a question reuse results.
- Upload PDFs for retrieval or images for visual questions.
- Download a text transcript, including source links.

Sources consulted are pages returned by search, not a guarantee that every claim is supported. Review the links before relying on an answer.

## Setup

Use Python 3.10 or newer. From the project root:

```sh
python -m venv venv
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `researcher/.env` with your own credentials:

```dotenv
ANTHROPIC_API_KEY=your_key
TAVkey=your_key
PINECONE_API_KEY=your_key
```

Create a Pinecone index named `research`, configured for the 384-dimensional `all-MiniLM-L6-v2` embeddings. The first embedding use downloads the model. Claude, Tavily, and Pinecone require accounts and may incur charges.

Run the maintained entry point:

```sh
cd researcher
python -m streamlit run Research.py
```

## Structure

```text
researcher/
  Research.py             Streamlit UI, document ingestion and agent loop
  research_tools.py       Source, WebSearch and ChatExport classes
  test_research_tools.py  Offline helper tests
requirements.txt         Application dependencies
```

`app.py`, `task1.py`, and `task2.py` and `task3.py` are earlier development files; use `Research.py` for this version.

`WebSearch` owns source collection and a per-question cache. `ChatExport` formats transcripts independently of Streamlit. These classes can be tested without API credentials.

## Checks

From the project root:

```sh
python -m unittest discover -s researcher -p "test_*.py" -v
```

The offline tests cover search reuse, source deduplication, link filtering, retry after failure, blank queries and transcript formatting. They do not exercise live APIs or the Streamlit interface.

## Current limitations

- PDF indexing uses a shared Pinecone index without session namespaces. This version is for a personal demo, not a multi-user deployment. The database-clear button deletes all vectors in that index.
- Conversation history stays in the current Streamlit session.
- Prior image attachments are not resent on later questions.
- API credentials are required at startup for all services.
