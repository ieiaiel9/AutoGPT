# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client
# Set environment variables for your credentials
# Read more at http://twil.io/secure
account_sid = "REDACTED_TWILIO_SID"
auth_token = "REDACTED_TWILIO_TOKEN"
client = Client(account_sid, auth_token)
message = client.messages.create(
  body="Hello from Twilio",
  from_="+18882947088",
  to="+16198274924"
)
print(message.sid)
