import os 
from dotenv import load_dotenv
import anthropic 


load_dotenv()

api = os.getenv("ANTHROPIC_API_KEY")
if not api:
     raise("API kry not dound buddy do something")
 
client = anthropic.Anthropic()

messages = []
print("Agent ready for anwsering your questions")
while True:
    user_input = input("You:")
    
    if  user_input.lower() == "quit":
     break

    messages.append({"role" : "user" , "content" : user_input })  
 
    response = client.messages.create (
        model = "claude-haiku-4-5-20251001",
        max_tokens= 100,
        system = "You are a research assistant. Help the user find, summarize and understand information clearly and concisely.",
        messages= messages
    )

    reply = response.content[0].text
    messages.append({"role": "assistant" , "content" : reply})
    print(reply)
