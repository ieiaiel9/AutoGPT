# def speak(text):
#    engine.say(text)
#    engine.runAndWait()
    # import necessary modules
import random
import datetime
import requests
import json
import webbrowser
from wit import Wit


# Define a function to handle the user's message
def handle_message(user_input):
    # Greet the user
    greetings = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
    greeting = random.choice(greetings)
    print("RAZ: " + greeting)

    # Initialize conversation variable
    continue_conversation = True

    # Start a loop to handle the conversation
    while continue_conversation:
        # Call the Wit API to generate a response
        wit_response = get_wit_response(user_input)

        # Check if message refers to AI name
        if 'RAZ' in user_input.upper():
            response = "Yes, how may I assist you?"

        # Check if message refers to greeting
        elif is_intent(wit_response, 'greetings'):
            responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
            response = random.choice(responses)

        # Check if message refers to thanks
        elif is_intent(wit_response, 'thanks'):
            responses = ["You're welcome!", "No problem!", "Anytime!"]
            response = random.choice(responses)

 # Check if message refers to goodbye
elif is_intent(wit_response, 'goodbye') or user_input.lower() == "bye" or user_input.lower() == "quit":
            response = "Goodbye! Have a great day."
            continue_conversation = False
            break
        # Check if message asks for the time
        elif is_intent(wit_response, 'get_time'):
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            response = f"The current time is {current_time}."

        # Check if message contains a web search query
        elif is_intent(wit_response, 'search_query'):
            search_query = wit_response['entities']['search_query'][0]['value']
            search_url = f"https://www.google.com/search?q={search_query}"
            webbrowser.open(search_url)
            response = f"Here are the search results for '{search_query}'."

        # If none of the above conditions are met, generate a generic response
        else:
            response = "I'm sorry, I didn't understand what you said."

        # Output the response
        print("RAZ: " + response)

        # Get user input
        if continue_conversation:
            user_input = input("You: ")

    # Return whether the conversation should continue
    return continue_conversation


# Define a function to check if a Wit.ai response has a certain intent
def is_intent(wit_response, intent_name):
    intents = wit_response.get('intents')
    if intents:
        for intent in intents:
            if intent.get('name') == intent_name and intent.get('confidence') > 0.5:
                return True
    return False


# Define a function to call the Wit API and return the response JSON
def get_wit_response(user_input):
    wit_token = "<YOUR_WIT_TOKEN_HERE>"
    headers = {
        "Authorization": f"Bearer {wit_token}",
        "Content-Type": "application/json"
    }
    params = {
        "q": user_input
    }
    response = requests.get("https://api.wit.ai/message", headers=headers, params=params)
    response.raise_for_status()
    response_json = response.json()
    return response_json


# Start the conversation
continue_conversation = True
while continue_conversation:
    # Get user input
    user_input = input("You: ")
