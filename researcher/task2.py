import os 
from dotenv import load_dotenv
import anthropic 


load_dotenv()

api = os.getenv("ANTHROPIC_API_KEY")
if not api:
     raise("API kry not dound buddy do something")
 
client = anthropic.Anthropic()

message = []
print("Agent ready for anwsering your questions")
while True:
    user_input = input("You:")
    
    if  user_input.lower() == "quit":
     break

    message.append({"role" : "user" , "content" : user_input })  
 
    response = client.messages.create (
        model = "claude-haiku-4-5-20251001",
        max_tokens= 500,
        system = """You are a research assistant called Researchr.
                    Your job is to help users research any topic by providing clear, 
                    factual, well-structured summaries.
                    Always cite where users should verify information.
                    Never make things up.If you don't know something, say so.""",
        messages = message
    )

    reply = response.content[0].text
    message.append({"role": "assistant" , "content" : reply})
    print(reply)
