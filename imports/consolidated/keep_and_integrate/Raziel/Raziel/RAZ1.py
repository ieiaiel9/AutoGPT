import random
from datetime import datetime
import requests
import json
from wit import Wit
import pyttsx3
import webbrowser
import asyncio
import random
import webbrowser
from datetime import datetime
import pyttsx3
import aiohttp
from wit import Wit
import sys
import openai_secret_manager
import openai
import datetime
import pytz
from wit import Wit
import webbrowser
import random
import pyttsx3


import wit
import datetime
import pytz

openai.api_key = "REDACTED_OPENAI_KEY"
# Set up OpenAI API credentials
# Use the API as normal
response = openai.Completion.create(...)

openai.api_key = openai_secret_manager.get_secret("openai")["api_key"]
model_engine = "text-davinci-002"

# Set up Wit API client
wit_token = openai_secret_manager.get_secret("wit_ai_token")["api_key"]
wit_client = Wit(wit_token)
 Load your OpenAI API key from your local key store
assert "openai" in openai_secret_manager.get_services()
secrets = openai_secret_manager.get_secret("openai")



# Define your prompt
prompt = (f"Train a language model to complete the sentence 'I love coding because' with creative and meaningful endings. \n"
          f"Example 1: I love coding because it makes me feel like a magician. \n"
          f"Example 2: I love coding because it allows me to bring my ideas to life. \n")

# Define the parameters for the API call
model_engine = "text-davinci-002"
temperature = 0.5
max_tokens = 50
top_p = 1.0
frequency_penalty = 0.5
presence_penalty = 0.5

# Call the OpenAI API to generate completions
response = openai.Completion.create(
    engine=model_engine,
    prompt=prompt,
    temperature=temperature,
    max_tokens=max_tokens,
    top_p=top_p,
    frequency_penalty=frequency_penalty,
    presence_penalty=presence_penalty
)

# Print the generated completions
for choice in response.choices:
    print(choice.text)
    ###
    ###
# Set up pyttsx3 text-to-speech engine
engine = pyttsx3.init()

# Define the speak function
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Define the get_current_time function
def get_current_time():
    now = datetime.datetime.now()
    time = now.strftime("%I:%M %p")
    return time

# Define the handle_message function
def handle_message(message):
    # Use Wit to extract intent and entities from message
    resp = wit_client.message(message)
    intent = None
    entities = None
    try:
        intent = resp['intents'][0]['name']
        entities = resp['entities']
    except:
        pass

    # Check if message refers to AI name
    if 'your_bot_name' in message.lower():
        speak("Yes, how may I assist you?")

    # Check if message refers to greeting
    elif intent == 'greetings':
        responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
        speak(random.choice(responses))

    # Check if message refers to thanks
    elif intent == 'thanks':
        speak("You're welcome! Anything else I can assist you with?")

    # Check if message refers to goodbye
    elif intent == 'goodbye':
        speak("Goodbye! Have a great day.")
        return True

    # Check if message refers to current time
    elif intent == 'get_time':
        time = get_current_time()
        speak(f"The current time is {time}.")

    # Check if message refers to opening a website
    elif intent == 'open_website':
        website = entities['website:website'][0]['value']
        webbrowser.open(website)
        speak(f"Opening {website}.")

    # Check if message refers to music artists search
    elif intent == 'search':
        search_query = None
        try:
            search_query = entities['search_query'][0]['value']
        except:
            pass

        if search_query is not None:
            # Call OpenAI search API
            response = openai.Completion.create(
                engine=model_engine,
                prompt=f"Search for today's new music billboard artists for {search_query}.",
                max_tokens=60
            )

            # Extract and speak the AI's completed text
            speak(response.choices[0].text)

    # Message does not match any recognized intent
    else:
        speak("I'm sorry, I don't understand. Could you please rephrase?")

    # Message processing completed
    return False


# Main program loop
if __name__ == '__main__':
    speak("How may I assist you?")
    while True:
        message = input()
        should_exit = handle_message(message)
        if should_exit:
            break

sys.setrecursionlimit(10**6)

# Initialize the Wit API client and pyttsx3 text-to-speech engine
client = Wit("YOUR_ACCESS_TOKEN")
engine = pyttsx3.init()

# Define the speak function
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Define the get_current_time function
def get_current_time():
    now = datetime.now()
    time = now.strftime("%I:%M %p")
    return time

# Define the handle_message function
async def handle_message(resp):
    intent = resp['intents'][0]['name']
    entities = resp['entities']
    if intent == 'greetings':
        responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
        return random.choice(responses)
    elif intent == 'get_time':
        time = get_current_time()
        return f"The current time is {time}."
    elif intent == 'open_website':
        website = entities['website:website'][0]['value']
        webbrowser.open(website)
        return f"Opening {website}."
    else:
        return "I'm sorry, I don't understand. Could you please rephrase?"






# Load your Wit.ai API key
wit_token = openai_secret_manager.get_secret("wit_ai_token")["api_key"]
client = wit.Wit(wit_token)

# Load your OpenAI API key
openai.api_key = openai_secret_manager.get_secret("openai")["api_key"]


def handle_message(message):
    resp = client.message(message)

    intent = None
    if 'intents' in resp:
        intent = resp['intents'][0]['name']

    if intent == 'greeting':
        return "Hello! How can I help you today?"

    elif intent == 'thanks':
        return "You're welcome! Anything else I can assist you with?"

    elif intent == 'goodbye':
        return "Goodbye! Have a great day."

    elif intent == 'datetime':
        tz_NY = pytz.timezone('America/New_York')
        datetime_NY = datetime.datetime.now(tz_NY)
        return f"The current date and time is {datetime_NY.strftime('%m/%d/%Y %I:%M %p')}."

    else:
        return "I'm sorry, I don't understand. Could you please rephrase?"


if __name__ == '__main__':
    print("How can I assist you?")
    while True:
        message = input()
        response = handle_message(message)
        print(response)



import openai_secret_manager
import openai
import json
import re
import datetime
import openai
import os

# Set up OpenAI API credentials
openai.api_key = os.environ["OPENAI_SECRET_KEY"]
model_engine = "text-davinci-002"

# Example text completion task
prompt = "The quick brown fox jumps over the"

# Fine-tune GPT-3 on the task
response = openai.Completion.create(
    engine=model_engine,
    prompt=prompt,
    max_tokens=5,
    n=1,
    stop=None,
    temperature=0.5,
)

# Print the AI's completed text
print(response.choices[0].text)

# Fetching API keys
secrets = openai_secret_manager.get_secret("wit")
wit_access_token = secrets["access_token"]

# Authenticate with OpenAI
secrets = openai_secret_manager.get_secret("openai")
openai.api_key = secrets["api_key"]

# Set up Wit client
from wit import Wit
wit_client = Wit(wit_access_token)


def handle_message(message):
    # Use Wit to extract intent and entities from message
    resp = wit_client.message(message)
    intent = None
    entities = None
    try:
        intent = resp['intents'][0]['name']
        entities = resp['entities']
    except:
        pass

    # Check if message refers to AI name
    if 'raz' in message.lower():
        print("My name is Raz!")
        return

    # Check if message refers to AI full name
    if 'raziel w.' in message.lower():
        print("My full name is Raziel W.!")
        return

    # Check intent and call corresponding function
    if intent == 'get_time':
        get_time()
    elif intent == 'search':
        search(entities)
    else:
        print("I'm sorry, I don't understand. Could you please rephrase?")


def get_time():
    current_time = datetime.datetime.now().strftime("%I:%M %p")
    print(f"The current time is {current_time}.")


def search(entities):
    # Extract search query from entities
    search_query = None
    try:
        search_query = entities['search_query'][0]['value']
    except:
        pass

    if search_query is not None:
        # Call OpenAI search API
        response = openai.Completion.create(
            engine="davinci",
            prompt=f"Search for today's new music billboard artists for {search_query}.",
            max_tokens=60
        )

        # Extract and print results
        result = response.choices[0].text
        result = re.sub('[^0-9a-zA-Z\n\.\?]+', ' ', result)
        print(result)
    else:
        print("What would you like me to search for?")


while True:
    message = input("How can I assist you?\n")
    handle_message(message)



# Define the Wit.ai message handler
async def handle_wit_message(message):
    async with aiohttp.ClientSession() as session:
        resp = await client.message(message)
        response = await handle_message(resp)
        speak(response)
        print(response)

# Run the main program loop
async def main():
    while True:
        message = input("How can I assist you?\n")
        await handle_wit_message(message)

# Start the event loop
asyncio.run(main())
# Initialize the Wit API client and pyttsx3 text-to-speech engine
client = Wit("W5VGDHMGTC3DU2VZU4LYDFSWYOBU4WSQ")
engine = pyttsx3.init()

# Define the speak function
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Define the get_current_time function
def get_current_time():
    now = datetime.now()
    time = now.strftime("%I:%M %p")
    return time

# Define the get_weather function
def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid=5641d84ecfe1ef7ba30e39e2bc0016c3"
    response = requests.get(url)
    data = json.loads(response.text)
    weather = data['weather'][0]['description']
    temp = int(data['main']['temp'] - 273.15)
    return f"It's currently {weather} and {temp} degrees Celsius in {city}."

# Define the handle_message function
###
def handle_message(message):
    resp = client.message(message)
    intent = None
    if resp['intents']:
        intent = resp['intents'][0]['name']
    entities = resp['entities']
    if intent == 'greetings':
        responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
        return random.choice(responses)
    elif intent == 'get_time':
        time = get_current_time()
        return f"The current time is {time}."
    elif intent == 'get_weather':
        city = entities['wit$location:location'][0]['body']
        weather = get_weather(city)
        return weather
    elif intent == 'open_website':
        website = entities['website'][0]['value']
        webbrowser.open(website)
        return f"Opening {website}."
    else:
        return "I'm sorry, I don't understand. Could you please rephrase?"
## My name is Raz
def handle_message(message):
    resp = client.message(message)
    intent = resp['intents'][0]['name']
    entities = resp['entities']
    if 'raz' in message.lower():
        return "Yes, my name is Raz. How can I assist you?"
    elif intent == 'greetings':
        responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
        return random.choice(responses)
    elif intent == 'get_time':
        time = get_current_time()
        return f"The current time is {time}."
    elif intent == 'get_weather':
        city = entities['wit$location:location'][0]['body']
        weather = get_weather(city)
        return weather
    elif intent == 'open_website':
        website = entities['website'][0]['value']
        webbrowser.open(website)
        return f"Opening {website}."
    elif "raziel w." in message.lower():
        return "Yes, that's my full name!"
    else:
        return "I'm sorry, I don't understand. Could you please rephrase?"

###
# Run the main program loop
while True:
    message = input("How can I assist you?\n")
    response = handle_message(message)
    speak(response)
    print(response)
