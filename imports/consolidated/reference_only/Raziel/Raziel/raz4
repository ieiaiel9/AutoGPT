import speech_recognition as sr
import pyttsx3
import datetime
import webbrowser
import os
import time
import subprocess
from ecapture import ecapture as ec
import wolframalpha
import json
import requests
import wit

access_token = 'UP42MSAY7HB2OBAD6ZQ3QTST6LAU2XSO'
client = wit.Wit(access_token=access_token)

response = client.message('Hello')

print(response)

engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice', 'voices[0].id')


def wishMe():
    hour = datetime.datetime.now().hour
    if hour >= 0 and hour < 12:
        print("Hello,Good Morning")
    elif hour >= 12 and hour < 18:
        print("Hello,Good Afternoon")
    else:
        print("Hello,Good Evening")


def takeCommand():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        audio = r.listen(source)
        try:
            statement = r.recognize_google(audio, language='en-in')
            print(f"user said:{statement}\n")
        except Exception as e:
            print("Pardon me, please say that again")
            return "None"
        return statement.lower()


def takeInput():
    print("Listening...")
    statement = input().lower()

    if "goodbye" in statement or "bye" in statement or "stop" in statement:
        print('Your personal assistant RAZ is shutting down. Goodbye!')
        return None
    else:
        print("You said: " + statement)
        print("Sorry, I didn't understand your choice. Please try again.")
    return statement


if __name__ == '__main__':
    while True:
        use_voice = input("Do you want to use voice input? (y/n): ").lower()
        if use_voice == 'n':
            continue_conversation = True
            print("How can I help you? Please type your request.")
            while continue_conversation:
                statement = takeInput().lower()
                if statement is None:
                    continue_conversation = False
                elif statement != "None":
                    print("You said: " + statement)
                    continue_conversation = True
                else:
                    continue_conversation = False
        elif use_voice == 'y':
            print("Tell me, how can I help you?")
            statement = takeCommand().lower()
            if statement is None:
                print('Your personal assistant RAZ is shutting down. Goodbye!')
                break
            elif "goodbye" in statement or "bye" in statement or "stop" in statement:
                print('Your personal assistant RAZ is shutting down. Goodbye!')
                break
            else:
                print("You said: " + statement)
                print("Sorry, I didn't understand your choice. Please try again.")
        else:
            print("Sorry, I didn't understand your choice. Please try again.")
