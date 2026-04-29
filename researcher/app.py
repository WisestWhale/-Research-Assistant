import os
import streamlit as st
from dotenv import load_dotenv
import anthropic
from tavily import TavilyClient
from PyPDF2 import PdfReader
import base64
from sentence_transformers import SentenceTransformer , util
import torch

load_dotenv()

client = anthropic.Anthropic()
tavily = TavilyClient(api_key=os.getenv("TAVkey"))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

tools = [
    {
        "name": "search_web",
        "description": "Search the web for current information on any topic",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
]
def chunk_text(raw_text, chunk_size = 500 , overlaps = 100 ):
    chunks= []
    for i in range (0 , len(raw_text) ,chunk_size - overlaps ):
       chunk = raw_text[i : i + chunk_size]
       chunks.append(chunk)
       return chunks 
    



def encode_image(imagefile):
    return base64.b64encode(imagefile.read()).decode('utf-8')

def extract_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file) 
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    return text

def search_web(query):
    results = tavily.search(query=query, max_results=3)
    output = ""
    for r in results["results"]:
        output += f"Source: {r['url']}\n{r['content']}\n\n"
    return output

# --- CORE AGENT LOGIC ---
def run_agent(user_message, image_file=None):
    # 1. Build history (Memory)
    messages = []
    for msg in st.session_state.messages[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 2. Enrich the current prompt
    text_to_send = user_message
    if "pdf_chunks" in st.session_state:
        search_relevance = search_pdf(user_message , st.session_state.pdf_chunks)
        text_to_send += f"\n\n[DOCUMENT CONTEXT]:\n{st.session_state.medical_context}"
    
    content_list = [{"type": "text", "text": text_to_send}]
        
    if image_file:
        image_base64 = encode_image(image_file)
        content_list.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_file.type,
                "data": image_base64,
            },
        })
        
    # 3. Add the enriched message to the thread
    messages.append({"role": "user", "content": content_list})
    
    counter = 0

    # 4. Agent Execution Loop
    with st.status("Agent is researching...", expanded=True) as status:
        while True:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system="You are a research assistant called Researcher. Use the search tool to find current information. You can also read from the provided PDF context.",
                tools=tools,
                messages=messages
            )

            if response.stop_reason == "end_turn":
                status.update(label="Research complete!", state="complete", expanded=False)
                return response.content[0].text
            
            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "search_web":
                            st.write(f"🔍 Searching: *{block.input['query']}*")
                            result = search_web(block.input["query"])
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            })

                messages.append({"role": "user", "content": tool_results})

                counter += 1
                if counter >= 10:
                    status.update(label="Max searches reached.", state="error")
                    return "Max searches reached."

# --- UI LAYOUT ---
st.title("Researcher 🔍")
st.caption("AI research assistant powered by Claude")

st.sidebar.title("File Upload")
uploaded_file = st.sidebar.file_uploader("Upload your file or image")

if uploaded_file:
    if "last_uploaded" not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
        with st.spinner("Indexing Document..."):
            if uploaded_file.type == "application/pdf":
                raw_text = extract_from_pdf(uploaded_file)
                st.session_state.pdf_chunks = chunk_text(raw_text)
                st.sidebar.success(f"Split into {len(st.session_state.pdf_chunks)} chunks")
            st.session_state.last_uploaded = uploaded_file.name

# Chat logic
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        img_to_pass = None
        if uploaded_file and uploaded_file.type != "application/pdf":
            img_to_pass = uploaded_file
        
        answer = run_agent(prompt, img_to_pass)
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        