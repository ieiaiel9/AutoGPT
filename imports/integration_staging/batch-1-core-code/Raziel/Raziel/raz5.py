from AutoGPT import autogpt


import datetime
import os
import subprocess
import time
import json
import requests
import wit
import openai
import sys
sys.path.insert(0, 'C:\\Users\\Wylde7\\Desktop\\Raziel\\AutoGPT')
  # add autogpt directory to system path

import autogpt

# use autogpt functions here


# Wit.ai configuration
access_token = 'UP42MSAY7HB2OBAD6ZQ3QTST6LAU2XSO'
client = wit.Wit(access_token=access_token)

# OpenAI configuration
openai.api_key = "REDACTED_OPENAI_KEY"
model_engine = "text-davinci-002"

# AutoGPT configuration


def takeInput():
    statement = input("Please enter your statement: ")
    return statement.lower()
### how it responds
def generate_response(statement):
    try:
        # Send statement to Wit.ai for intent classification
        wit_response = client.message(statement)
        if wit_response['intents']:
            intent = wit_response['intents'][0]['name']

            # Generate response based on intent
            if intent == 'greeting':
                return 'RAZ: Hello! How can I help you?'
            elif intent == 'goodbye':
                return 'RAZ: Goodbye!'
            elif intent == 'search':
                # Use OpenAI to perform web search
                search_query = wit_response['entities']['wit$search_query'][0]['body']
                openai_response = openai.Completion.create(
                    engine=model_engine,
                    prompt=f"I want to search for {search_query}.",
                    max_tokens=60,
                    n=1,
                    stop=None,
                    temperature=0.5
                )
                return f"RAZopen: {openai_response.choices[0].text}"
            else:
                # Use AutoGPT to generate response
                gpt = AutoGPT()
                auto_gpt_response = gpt.generate_text(prompt=statement, length=60)

                return f"RAZAUTOGPT: {auto_gpt_response}"
        else:
            raise Exception("No intent found")
    except Exception as e:
        print(e)
        # Use OpenAI to generate response
        openai_response = openai.Completion.create(
            engine=model_engine,
            prompt=statement,
            max_tokens=60,
            n=1,
            stop=None,
            temperature=0.5
        )
        return f"RAZopenAI: {openai_response.choices[0].text}"



# Define a function to get the weather
def getWeather(city):
    api_key = "5641d84ecfe1ef7ba30e39e2bc0016c3"
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"
    response = requests.get(url)
    weather_data = response.json()
    if weather_data["cod"] != "404":
        temperature = round(weather_data["main"]["temp"] - 273.15)
        description = weather_data["weather"][0]["description"]
        speak(f"The temperature in {city} is {temperature} degrees Celsius with {description}")
    else:
        speak("City not found")

# Define a function to perform a Google search
def googleSearch(query):
    url = "https://www.google.com/search?q=" + query
    webbrowser.open(url)
    speak("Here are the search results for " + query)

# Define a function to capture a photo
def capturePhoto():
    ec.capture(0, "robo camera", "img.jpg")
    # Define a function to get the current time
def getTime():
    now = datetime.datetime.now()
    speak("The current time is " + now.strftime("%I:%M %p"))

# Define a function to open a website
def openWebsite(url):
    webbrowser.open(url)
    speak("Opening " + url)

#################################

#################################
if __name__ == '__main__':
    continue_conversation = True
    print("How can I help you? Please type your request.")
    while continue_conversation:
        statement = takeInput().lower()
        if "goodbye" in statement or "bye" in statement or "stop" in statement or "peace" in statement:
            print('Your personal assistant RAZ is shutting down. Goodbye!')
            continue_conversation = False
        else:
            response = generate_response(statement)
            print(response)

#################################

#################################
