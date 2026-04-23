import os
import streamlit as st
from dotenv import load_dotenv
import anthropic
from tavily import TavilyClient
from PyPDF2 import PdfReader



load_dotenv()

client = anthropic.Anthropic()
tavily = TavilyClient(api_key=os.getenv("TAVkey"))


   



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

def extract_from_pdf(uploaded_file):
   reader = PdfReader(uploaded_file) 
   text = ""
   
   for page in reader.pages:
       content = page.extract_text()
       if content:
           text+=content + "\n"
           
   return text

st.title("Researcher 🔍")
st.caption("AI research assistant powered by Claude")
st.sidebar.title("File Upload")
uploaded_file  = st.sidebar.file_uploader("Upload your file")
if uploaded_file:
    with st.spinner("Processing"):
        if uploaded_file.type == "application/pdf":
            raw_text = extract_from_pdf(uploaded_file)
            
        else:
            raw_text  = uploaded_file.read().decode("utf-8")
        
        st.sidebar.success("File Uploaded")
        st.sidebar.text_area("Preview", raw_text[:500] , height= 150)
        

def search_web(query):
    results = tavily.search(query=query, max_results=3)
    output = ""
    for r in results["results"]:
        output += f"Source: {r['url']}\n{r['content']}\n\n"
    return output

def run_agent(user_message, status_container):
    messages = [{"role": "user", "content": user_message}]
    counter = 0

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="You are a research assistant called Researcher. Use the search tool to find current information before answering. Be clear and structured.",
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return response.content[0].text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    status_container.write(f"🔍 Searching: *{block.input['query']}*")
                    result = search_web(block.input["query"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

            counter += 1
            if counter >= 10:
                return "Max searches reached."

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User input
if prompt := st.chat_input("Ask me anything..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Run agent and show response
    with st.chat_message("assistant"):
        status = st.empty()
        answer = run_agent(prompt, status)
        status.empty()
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})