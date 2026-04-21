# import necessary modules
import random
import datetime
import requests
import json
import pyttsx3
import webbrowser
import asyncio
import aiohttp
from wit import Wit

# Set up Wit API client
wit_token = "W5VGDHMGTC3DU2VZU4LYDFSWYOBU4WSQ"
wit_client = Wit(wit_token)

# Define your prompt
def create_prompt():
    prompt = (f"Train a language model to complete the sentence 'I love coding because' with creative and meaningful endings. \n"
              f"1. I love coding because it allows me to create something new every day.\n"
              f"2. I love coding because it challenges me to constantly learn and improve.\n"
              f"3. I love coding because it gives me the power to automate and simplify tasks.\n"
              f"4. I love coding because it's a way to express my creativity and solve problems.\n"
              f"5. I love coding because it opens up endless opportunities for innovation and discovery.\n"
              f"6. I love coding because it's like solving puzzles, and I enjoy the satisfaction of finding the solution.\n"
              f"7. I love coding because it empowers me to make a positive impact on the world.\n"
              f"8. I love coding because it's a field that is constantly evolving, and there is always something new to learn.\n"
              f"9. I love coding because it allows me to collaborate with like-minded people from all over the world.\n"
              f"10. I love coding because it's a fun and rewarding way to spend my time.\n"
              )
    return prompt

# Define the parameters for the API call
temperature = 0.5
max_tokens = 60
top_p = 1
frequency_penalty = 0
presence_penalty = 0

# Define a function to get user input
def get_user_input():
    return input("You: ")

# Define a function to speak a message
def speak(message):
    print("RAZ: " + message)
    engine = pyttsx3.init()
    engine.say(message)
    engine.runAndWait()



# Define a function to handle user input
def handle_user_input(user_input):
    try:
        # Send the user input to Wit.ai for natural language understanding
        resp = wit.message(WIT_ACCESS_TOKEN, user_input)
        # Get the intent and entities from the response
        intent = resp["intents"][0]["name"]
        entities = resp["entities"]
        # Generate a response based on the intent and entities
        if intent == "greeting":
            return "Hello!"
        elif intent == "bye":
            return "Goodbye!"
        elif intent == "weather":
            location = entities["location"][0]["value"]
            return f"The weather in {location} is sunny today."
        else:
            return "I'm sorry, I don't understand."
    except:
        return "There was an error processing your request."


# Define the function to generate random numbers
def generate_random_number():
    return random.randint(1, 100)

def main():
    # Greet the user
    speak("Hello!")

    # Get the number of random numbers to generate
    num_numbers = get_num_numbers()

    # Get the range of random numbers
    range_min, range_max = get_range()

    # Generate the random numbers
    numbers = generate_random_numbers(num_numbers, range_min, range_max)

    # Print the random numbers
    print("Here are your random numbers:")
    for number in numbers:
        print(number)

# Define the speak function
def say_text(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

# Keep the conversation going until the user says goodbye
while True:
    # Get user input
    user_input = get_user_input()

    # Check if the user wants to end the conversation
    if "goodbye" in user_input.lower():
        speak("Goodbye!")
        break


# Define a list of possible greeting responses
greeting_responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']


# Define a function to handle the user's message
def handle_message(user_input):
    # Call the Wit API to generate a response
     print("Calling RAZ...")
   wit_response = wit_client.message(user_input)
    # Check if message refers to AI name
    if 'RAZ' in user_input.upper():
        response = "Yes, how may I assist you?"


    # Check if message refers to greeting
    elif any(intent['name'] == 'greetings' for intent in wit_response['intents']):
        responses = ['Hello!', 'Hi there!', 'How can I assist you?', 'Hi! How can I help?']
        response = random.choice(responses)

    # Check if message refers to thanks
    elif 'thanks' in wit_response['intents']:
        response = "You're welcome! Anything else I can assist you with?"

    # Check if message refers to goodbye
    elif 'goodbye' in wit_response['intents'] or 'bye' in wit_response['intents'] or 'quit' in wit_response['intents']:
        response = "Goodbye! Have a great day."
        continue_conversation = False
# Check if message asks for the time
    elif 'TIME' in wit_response['intents']:
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        response = f"The current time is {current_time}"
    # If none of the above conditions are met, generate a generic response
    else:
        response = "I'm sorry, I didn't understand what you said."

    # Output the response
    print("RAZ: " + response)

    # Return whether the conversation should continue
    return continue_conversation

# Start the conversation
continue_conversation = True
while continue_conversation:
    # Get user input
    user_input = input("You: ")

    # Handle the user's message
    if user_input:
        handle_message(user_input)
    else:
        continue_conversation = False


    # Check if user said goodbye
    if 'goodbye' in user_input.lower() or 'bye' in user_input.lower() or 'quit' in user_input.lower():
        continue_conversation = False



# Check if message refers to current time
def handle_time_intent(intent):
    if intent == 'get_time':
        time = get_current_time()
        speak(f"The current time is {time}.")

def get_current_time():
    now = datetime.datetime.now()
    return now.strftime("%H:%M:%S")
# Check if message refers to opening a website
if intent == 'open_website':
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



        # Extract and speak the AI's completed text
        speak(response.choices[0].text)

# Message does not match any recognized intent
else:
    speak("I'm sorry, I don't understand. Could you please rephrase?")

# XXXXXXXXXXXXXXXXXXXXXXXXMessage processing completed
