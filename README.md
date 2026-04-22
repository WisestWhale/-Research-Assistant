# Researchr 🔍
An AI-powered research assistant that searches the web in real time to answer your questions.

Built with Claude (Anthropic) + Tavily Search + Streamlit.

## What it does
Researchr takes any research question, autonomously decides what to search for, searches the web, and synthesizes the results into a clear structured answer. It maintains conversation history so you can ask follow up questions.

## How it works
The agent uses a ReAct loop (Reason → Act → Observe):

1. User asks a question
2. Claude reasons about what to search for
3. Tavily searches the web and returns results
4. Claude reads the results and decides if it needs more information
5. When satisfied Claude returns a final structured answer

## Tech stack
Claude Haiku for LLM reasoning, Tavily for real time web search, Streamlit for the web UI, Python for the backend.

## Setup
Clone the repo, create a virtual environment, install dependencies with `pip install anthropic tavily-python streamlit python-dotenv`, add your API keys to a `.env` file, then run with `streamlit run app.py`.

## Project structure
```
researchr/
├── app.py                    
├── .gitignore      
└── README.md       
```