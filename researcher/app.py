import os
import streamlit as st
from dotenv import load_dotenv
import anthropic
from tavily import TavilyClient
from PyPDF2 import PdfReader
import base64
from sentence_transformers import SentenceTransformer , util
from langchain_text_splitters import RecursiveCharacterTextSplitter
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
def chunk_text(raw_text):
    if not raw_text or not raw_text.strip():
      return []
    text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
     chunk_size=450, chunk_overlap=50)
    chunks  = text_splitter.split_text(raw_text)
    return chunks
    
def search_pdf(query, chunks: list , chunk_embeddings):
    
    if not chunks:
     return""
    
    query_embedding = embedder.encode(query  , convert_to_tensor = True)
    scores = util.cos_sim(query_embedding, chunk_embeddings)[0]
    top_indices = torch.topk(scores, min(4, len(chunks))).indices.tolist() #grab the position of list and conver to list from tensor
    top_indices = sorted(top_indices)
    
    relevant = []
    for i in top_indices:
     relevant.append(chunks[i]) #get the actual text
    
    return "\n---\n".join(relevant)
    


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
def run_agent(query, image_bytes= None,
    image_media_type= None
):
    # 1. Build history (Memory)
    messages = []
    for msg in st.session_state.messages[:-1]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # 2. Enrich the current prompt
    text_to_send = query
    if "pdf_chunks" in st.session_state and "chunk_embeddings" in st.session_state:
        search_relevance = search_pdf(query ,  st.session_state.pdf_chunks ,st.session_state.chunk_embeddings)
        if search_relevance:
         text_to_send += f"\n\n[DOCUMENT CONTEXT]:\n{search_relevance}"
    
    content_list = [{"type": "text", "text": text_to_send}]
        
    if image_bytes:
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        content_list.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_media_type,
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
              st.session_state.chunk_embeddings = embedder.encode(
              st.session_state.pdf_chunks,
              convert_to_tensor=True,
              show_progress_bar=False
                )
              st.sidebar.success(f"Indexed {len(st.session_state.pdf_chunks)} chunks")

            elif uploaded_file.type in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
                st.session_state.image_bytes = uploaded_file.read()
                st.session_state.image_type = uploaded_file.type
                st.sidebar.success("Image ready")

            else:
                st.sidebar.error(f"Unsupported file type: {uploaded_file.type}")

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
         st.session_state.image_bytes = uploaded_file.read()
         st.session_state.image_type = uploaded_file.type
        
        answer = run_agent(
            prompt,
            image_bytes=st.session_state.get("image_bytes"),
           image_media_type=st.session_state.get("image_type")

            )
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        