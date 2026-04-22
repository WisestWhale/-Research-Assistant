import os
from dotenv import load_dotenv
import anthropic
from tavily import TavilyClient

load_dotenv()

client = anthropic.Anthropic()
tavily = TavilyClient(api_key=os.getenv("TAVkey"))

# Tell Claude what tools it has available
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

def search_web(query):
    results = tavily.search(query=query, max_results=3)
    # Format results into clean text
    output = ""
    for r in results["results"]:
        output += f"Source: {r['url']}\n{r['content']}\n\n"
    return output

def run_agent(user_message):
    messages = [{"role": "user", "content": user_message}]
    counter = 0
    
    while True: 
        
        
       # max 10 iterations
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="You are a research assistant. Use the search tool to find current information before answering.",
            tools=tools,
            messages=messages
        )
        
        # Claude is done — no more tool calls
        if response.stop_reason == "end_turn":
            print(f"\nResearchr: {response.content[0].text}")
            return
        
        # Claude wants to use a tool
        # Claude wants to use tools
        if response.stop_reason == "tool_use":
            # tool handling code
            counter += 1
            if counter >= 10:
                break
            print("Researchr ready. Type 'quit' to exit.")
            messages.append({"role": "assistant", "content": response.content})
            # Handle ALL tool calls in this response, not just the first
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n[Searching: {block.input['query']}]")
                    result = search_web(block.input["query"])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            
            # Append all tool results in one message
            messages.append({
                "role": "user",
                "content": tool_results
            })
            
while True:
    user_input = input("\nYou: ")
    if user_input.lower() == "quit":
        break
    run_agent(user_input)
  


# Test it
