import os
import openai
from flask import Flask, request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# Load API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Google Auth
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/tasks']

def get_google_services():
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    calendar_service = build('calendar', 'v3', credentials=creds)
    tasks_service = build('tasks', 'v1', credentials=creds)
    return calendar_service, tasks_service

calendar_service, tasks_service = get_google_services()

# NLP with OpenAI
import requests
import os


def analyze_message(text):
    prompt = f"""
    You are a smart assistant. Analyze the following message and return a JSON object:
    - intent: "task" or "event"
    - title: short title
    - date: in format YYYY-MM-DD
    - time: in format HH:MM (24-hour)

    Message: "{text}"
    """

    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }

    response = requests.post(
        "https://openai.inference.de-txl.ionos.com/v1/chat/completions",
        headers=headers,
        json=payload
    )

    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]

    # Return the parsed JSON object
    return eval(content)  # Or better: use `json.loads(content)` if response is valid JSON


# Flask app
app = Flask(__name__)

@app.route("/message", methods=["POST"])
def handle_message():
    data = request.json
    user_message = data.get("text")

    try:
        parsed = analyze_message(user_message)
        intent = parsed["intent"]
        title = parsed["title"]
        date = parsed["date"]
        time = parsed["time"]

        if intent == "task":
            task = {
                "title": title,
                "due": f"{date}T{time}:00.000Z"
            }
            tasks_service.tasks().insert(tasklist='@default', body=task).execute()
            return f"✅ Task created: {title}"

        elif intent == "event":
            event = {
                "summary": title,
                "start": {"dateTime": f"{date}T{time}:00", "timeZone": "Europe/Berlin"},
                "end": {"dateTime": f"{date}T{time}:00", "timeZone": "Europe/Berlin"}
            }
            calendar_service.events().insert(calendarId='primary', body=event).execute()
            return f"📅 Event added: {title}"

        else:
            return "❓ Could not determine intent"

    except Exception as e:
        print(e)
        return "❌ Error processing your message"

@app.route("/")
def index():
    return "Rocket.Chat MCP is running"



if __name__ == "__main__":
    app.run(port=5000)
