import random
from datetime import datetime
import requests
import json
from wit import Wit
import pyttsx3
import webbrowser

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
def handle_message(message):
    resp = client.message(message)
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

# Run the main program loop
while True:
    message = input("How can I assist you?\n")
    response = handle_message(message)
    speak(response)
    print(response)
