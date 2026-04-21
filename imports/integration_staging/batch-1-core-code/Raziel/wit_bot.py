import requests

WIT_TOKEN = "W5VGDHMGTC3DU2VZU4LYDFSWYOBU4WSQ"

def wit_response(message):
    resp = requests.get('https://api.wit.ai/message?v=20220416&q=' + message, headers={'Authorization': 'Bearer ' + WIT_TOKEN})
    if resp.status_code == 200:
        response_text = resp.json()['_text']
        return response_text
    else:
        return "Sorry, I didn't understand that"

print(wit_response("Hello, how are you?"))
