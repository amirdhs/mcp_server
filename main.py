#!/usr/bin/env python3
"""
Telegram AI Agent with Gmail and Google Calendar Integration
Compatible with Python 3.8+
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import base64
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelegramAIAgent:
    def __init__(self):
        self.telegram_app = None
        self.google_creds = None
        self.gmail_service = None
        self.calendar_service = None
        self.tasks_service = None

        # Configuration
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.ionos_api_key = os.getenv("IONOS_API_KEY")
        self.ionos_base_url = "https://openai.inference.de-txl.ionos.com/v1"
        self.ionos_model = "meta-llama/Llama-3.3-70B-Instruct"

        # Google OAuth2 configuration
        self.google_scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/tasks'
        ]

        # Active conversations context
        self.user_contexts = {}

    async def authenticate_google(self):
        """Authenticate with Google services"""
        creds = None

        # Load existing credentials
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    logger.error("credentials.json not found. Please download from Google Cloud Console.")
                    return False

                flow = Flow.from_client_secrets_file(
                    'credentials.json', self.google_scopes)
                flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'

                auth_url, _ = flow.authorization_url(prompt='consent')
                print(f'Please go to this URL: {auth_url}')
                code = input('Enter the authorization code: ')
                flow.fetch_token(code=code)
                creds = flow.credentials

            # Save credentials for future use
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.google_creds = creds
        self.gmail_service = build('gmail', 'v1', credentials=creds)
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        self.tasks_service = build('tasks', 'v1', credentials=creds)
        return True

    async def setup_telegram_bot(self):
        """Setup Telegram bot"""
        if not self.telegram_token:
            logger.error("TELEGRAM_BOT_TOKEN not set")
            return False

        self.telegram_app = Application.builder().token(self.telegram_token).build()

        # Add handlers
        self.telegram_app.add_handler(CommandHandler("start", self.telegram_start))
        self.telegram_app.add_handler(CommandHandler("help", self.telegram_help))
        self.telegram_app.add_handler(CommandHandler("gmail", self.telegram_gmail))
        self.telegram_app.add_handler(CommandHandler("calendar", self.telegram_calendar))
        self.telegram_app.add_handler(CommandHandler("tasks", self.telegram_tasks))
        self.telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.telegram_message))

        return True

    async def telegram_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 **AI Assistant Ready!**

I can help you with:
• 💬 **Chat** - Ask me anything
• 📧 **Gmail** - Search and read emails
• 📅 **Calendar** - Create and view events
• ✅ **Tasks** - Manage your to-do list

**Commands:**
/help - Show this help
/gmail [query] - Search Gmail
/calendar - View upcoming events
/tasks - View your tasks

Just send me a message to start chatting!
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')

    async def telegram_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🔧 **Available Commands:**

📧 **Gmail Commands:**
• `/gmail search term` - Search emails
• `/gmail unread` - Show unread emails
• `/gmail from:sender@email.com` - Emails from specific sender

📅 **Calendar Commands:**
• `/calendar` - Show upcoming events
• `Create meeting tomorrow 2pm` - Create event (via chat)

✅ **Task Commands:**
• `/tasks` - Show all tasks
• `Add task: Review documents` - Create task (via chat)

💬 **Chat Examples:**
• "What emails did I get today?"
• "Schedule a meeting for Friday"
• "Add a reminder to call John"
• "Search for emails about project Alpha"

Just type naturally and I'll understand what you want to do!
        """
        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def telegram_gmail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /gmail command"""
        query = ' '.join(context.args) if context.args else 'is:unread'

        try:
            results = await self.search_gmail(query, 5)
            if 'error' in results:
                await update.message.reply_text(f"❌ Error: {results['error']}")
                return

            if not results.get('results'):
                await update.message.reply_text("📭 No emails found for your query.")
                return

            response = f"📧 **Gmail Results for '{query}':**\n\n"
            for i, email in enumerate(results['results'][:5], 1):
                response += f"**{i}.** {email['subject']}\n"
                response += f"📨 From: {email['from']}\n"
                response += f"📅 {email['date']}\n"
                response += f"💬 {email['snippet'][:100]}...\n\n"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error searching Gmail: {str(e)}")

    async def telegram_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /calendar command"""
        try:
            events_json = await self.get_calendar_events(10)
            events = json.loads(events_json)

            if 'error' in events:
                await update.message.reply_text(f"❌ Error: {events['error']}")
                return

            if not events:
                await update.message.reply_text("📅 No upcoming events found.")
                return

            response = "📅 **Upcoming Events:**\n\n"
            for i, event in enumerate(events[:5], 1):
                title = event.get('summary', 'No Title')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No time'))

                response += f"**{i}.** {title}\n"
                response += f"🕐 {start_time}\n"
                if event.get('description'):
                    response += f"📝 {event['description'][:50]}...\n"
                response += "\n"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting calendar events: {str(e)}")

    async def telegram_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tasks command"""
        try:
            tasks_json = await self.get_task_lists()
            task_data = json.loads(tasks_json)

            if 'error' in task_data:
                await update.message.reply_text(f"❌ Error: {task_data['error']}")
                return

            response = "✅ **Your Tasks:**\n\n"
            task_count = 0

            for task_list in task_data:
                if task_list.get('tasks'):
                    response += f"📋 **{task_list['list_name']}:**\n"
                    for task in task_list['tasks'][:5]:
                        task_count += 1
                        title = task.get('title', 'No Title')
                        status = "✅" if task.get('status') == 'completed' else "⏳"
                        response += f"{status} {title}\n"
                        if task.get('due'):
                            response += f"   📅 Due: {task['due']}\n"
                    response += "\n"

            if task_count == 0:
                response = "✅ No tasks found. You're all caught up!"

            await update.message.reply_text(response, parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error getting tasks: {str(e)}")

    async def telegram_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages"""
        user_message = update.message.text
        chat_id = str(update.message.chat_id)
        user_id = update.message.from_user.id

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')

        try:
            # Analyze message intent
            intent = await self.analyze_intent(user_message)

            # Execute based on intent
            if intent['action'] == 'search_gmail':
                response = await self.handle_gmail_search(intent['query'])
            elif intent['action'] == 'create_calendar_event':
                response = await self.handle_calendar_creation(intent)
            elif intent['action'] == 'create_task':
                response = await self.handle_task_creation(intent)
            elif intent['action'] == 'get_calendar':
                response = await self.handle_calendar_view()
            elif intent['action'] == 'get_tasks':
                response = await self.handle_tasks_view()
            else:
                # Regular AI chat
                context_info = f"User ID: {user_id}, Chat ID: {chat_id}"
                ai_response = await self.ai_chat(user_message, context_info)
                response = ai_response.get('response', 'Sorry, I could not process your request.')

            await update.message.reply_text(response, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await update.message.reply_text("❌ Sorry, I encountered an error processing your message.")

    async def analyze_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user message intent using AI"""
        analysis_prompt = f"""
Analyze this user message and determine the intent. Return JSON with 'action' and relevant parameters.

Possible actions:
- search_gmail: Search Gmail (extract query)
- create_calendar_event: Create calendar event (extract title, date, time)
- create_task: Create task (extract title, description, due_date)
- get_calendar: View calendar events
- get_tasks: View tasks
- chat: Regular conversation

User message: "{message}"

Return only JSON format like: {{"action": "search_gmail", "query": "from:john@example.com"}}
"""

        try:
            ai_response = await self.ai_chat(analysis_prompt, "Intent analysis")
            response_text = ai_response.get('response', '{}')

            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                intent = json.loads(json_match.group())
                return intent
        except:
            pass

        # Fallback to simple keyword matching
        message_lower = message.lower()

        if any(word in message_lower for word in ['email', 'gmail', 'mail', 'inbox']):
            return {'action': 'search_gmail', 'query': message}
        elif any(word in message_lower for word in ['meeting', 'appointment', 'schedule', 'calendar event']):
            return {'action': 'create_calendar_event', 'title': message}
        elif any(word in message_lower for word in ['task', 'todo', 'reminder', 'add']):
            return {'action': 'create_task', 'title': message}
        elif 'calendar' in message_lower:
            return {'action': 'get_calendar'}
        elif 'task' in message_lower:
            return {'action': 'get_tasks'}
        else:
            return {'action': 'chat'}

    async def handle_gmail_search(self, query: str) -> str:
        """Handle Gmail search requests"""
        try:
            results = await self.search_gmail(query, 3)
            if 'error' in results:
                return f"❌ Gmail Error: {results['error']}"

            if not results.get('results'):
                return "📭 No emails found matching your search."

            response = f"📧 **Found {len(results['results'])} emails:**\n\n"
            for i, email in enumerate(results['results'], 1):
                response += f"**{i}.** {email['subject']}\n"
                response += f"📨 {email['from']}\n"
                response += f"💬 {email['snippet'][:100]}...\n\n"

            return response
        except Exception as e:
            return f"❌ Error searching Gmail: {str(e)}"

    async def handle_calendar_creation(self, intent: Dict[str, Any]) -> str:
        """Handle calendar event creation"""
        try:
            # Use AI to extract event details
            ai_prompt = f"""
Extract event details from: "{intent.get('title', '')}"
Return JSON with: title, start_time (ISO format), end_time (ISO format), description
If no specific time mentioned, use next available business hour.
Current date/time for reference: {datetime.now().isoformat()}
"""

            ai_response = await self.ai_chat(ai_prompt, "Event extraction")
            # For now, create a simple event

            return "📅 Calendar event creation is being processed. Please use more specific details like 'Schedule meeting tomorrow at 2 PM for 1 hour about project review'."
        except Exception as e:
            return f"❌ Error creating calendar event: {str(e)}"

    async def handle_task_creation(self, intent: Dict[str, Any]) -> str:
        """Handle task creation"""
        try:
            task_title = intent.get('title', '').replace('add task', '').replace('task:', '').strip()
            if not task_title:
                return "❌ Please specify a task title."

            result = await self.create_task({'title': task_title})
            if result.get('success'):
                return f"✅ Task created: {task_title}"
            else:
                return f"❌ Error creating task: {result.get('error', 'Unknown error')}"
        except Exception as e:
            return f"❌ Error creating task: {str(e)}"

    async def handle_calendar_view(self) -> str:
        """Handle calendar view requests"""
        try:
            events_json = await self.get_calendar_events(5)
            events = json.loads(events_json)

            if 'error' in events:
                return f"❌ Calendar Error: {events['error']}"

            if not events:
                return "📅 No upcoming events found."

            response = "📅 **Upcoming Events:**\n\n"
            for i, event in enumerate(events, 1):
                title = event.get('summary', 'No Title')
                start = event.get('start', {})
                start_time = start.get('dateTime', start.get('date', 'No time'))
                response += f"**{i}.** {title}\n🕐 {start_time}\n\n"

            return response
        except Exception as e:
            return f"❌ Error getting calendar: {str(e)}"

    async def handle_tasks_view(self) -> str:
        """Handle tasks view requests"""
        try:
            tasks_json = await self.get_task_lists()
            task_data = json.loads(tasks_json)

            if 'error' in task_data:
                return f"❌ Tasks Error: {task_data['error']}"

            response = "✅ **Your Tasks:**\n\n"
            for task_list in task_data:
                if task_list.get('tasks'):
                    for task in task_list['tasks'][:5]:
                        title = task.get('title', 'No Title')
                        status = "✅" if task.get('status') == 'completed' else "⏳"
                        response += f"{status} {title}\n"

            return response if "⏳" in response or "✅" in response else "✅ No tasks found."
        except Exception as e:
            return f"❌ Error getting tasks: {str(e)}"

    # Google Services Methods (unchanged from previous version)
    async def search_gmail(self, query: str, max_results: int = 10):
        """Search Gmail messages"""
        try:
            results = self.gmail_service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            if not messages:
                return {"results": [], "message": "No messages found"}

            detailed_messages = []
            for msg in messages:
                msg_detail = self.gmail_service.users().messages().get(
                    userId='me', id=msg['id']
                ).execute()

                payload = msg_detail['payload']
                headers = payload.get('headers', [])

                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')

                detailed_messages.append({
                    'id': msg['id'],
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'snippet': msg_detail.get('snippet', '')
                })

            return {"results": detailed_messages, "count": len(detailed_messages)}
        except Exception as e:
            return {"error": str(e)}

    async def get_calendar_events(self, max_results: int = 10):
        """Get upcoming calendar events"""
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            events_result = self.calendar_service.events().list(
                calendarId='primary', timeMin=now, maxResults=max_results,
                singleEvents=True, orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return json.dumps(events, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def create_calendar_event(self, event_data: Dict[str, Any]):
        """Create a calendar event"""
        try:
            event = {
                'summary': event_data['title'],
                'description': event_data.get('description', ''),
                'start': {
                    'dateTime': event_data['start_time'],
                    'timeZone': event_data.get('timezone', 'UTC'),
                },
                'end': {
                    'dateTime': event_data['end_time'],
                    'timeZone': event_data.get('timezone', 'UTC'),
                },
            }

            created_event = self.calendar_service.events().insert(
                calendarId='primary', body=event
            ).execute()

            return {
                "success": True,
                "event_id": created_event['id'],
                "html_link": created_event.get('htmlLink'),
                "message": "Event created successfully"
            }
        except Exception as e:
            return {"error": str(e)}

    async def get_task_lists(self):
        """Get task lists"""
        try:
            results = self.tasks_service.tasklists().list().execute()
            task_lists = results.get('items', [])

            all_tasks = []
            for task_list in task_lists:
                tasks = self.tasks_service.tasks().list(
                    tasklist=task_list['id']
                ).execute()

                all_tasks.append({
                    'list_name': task_list['title'],
                    'list_id': task_list['id'],
                    'tasks': tasks.get('items', [])
                })

            return json.dumps(all_tasks, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def create_task(self, task_data: Dict[str, Any]):
        """Create a task"""
        try:
            # Get the default task list
            task_lists = self.tasks_service.tasklists().list().execute()
            default_list_id = task_lists['items'][0]['id']

            task = {
                'title': task_data['title'],
                'notes': task_data.get('notes', ''),
            }

            if 'due_date' in task_data:
                task['due'] = task_data['due_date']

            created_task = self.tasks_service.tasks().insert(
                tasklist=default_list_id, body=task
            ).execute()

            return {
                "success": True,
                "task_id": created_task['id'],
                "message": "Task created successfully"
            }
        except Exception as e:
            return {"error": str(e)}

    async def ai_chat(self, message: str, context: str = ""):
        """Chat with Ionos AI model"""
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.ionos_api_key}",
                    "Content-Type": "application/json"
                }

                system_prompt = """You are a helpful AI assistant integrated with Gmail, Google Calendar, and Tasks. 
You can help users manage their emails, schedule events, and organize tasks. Be concise and helpful."""

                messages = [
                    {"role": "system", "content": system_prompt}
                ]

                if context:
                    messages.append({"role": "system", "content": f"Context: {context}"})

                messages.append({"role": "user", "content": message})

                data = {
                    "model": self.ionos_model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7
                }

                response = await client.post(
                    f"{self.ionos_base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30.0
                )

                if response.status_code == 200:
                    result = response.json()
                    ai_response = result['choices'][0]['message']['content']
                    return {
                        "response": ai_response,
                        "model": self.ionos_model,
                        "success": True
                    }
                else:
                    return {
                        "error": f"AI API error: {response.status_code}",
                        "response": "Sorry, I couldn't process your request."
                    }
        except Exception as e:
            logger.error(f"AI chat error: {e}")
            return {
                "error": str(e),
                "response": "Sorry, there was an error processing your request."
            }

    async def run(self):
        """Run the Telegram bot"""
        logger.info("Starting Telegram AI Agent...")

        # Initialize Google services
        if not await self.authenticate_google():
            logger.error("Failed to authenticate with Google services")
            return

        # Setup Telegram bot
        if not await self.setup_telegram_bot():
            logger.error("Failed to setup Telegram bot")
            return

        logger.info("Bot is running... Press Ctrl+C to stop")

        # Start the bot
        await self.telegram_app.initialize()
        await self.telegram_app.start()
        await self.telegram_app.updater.start_polling()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            await self.telegram_app.updater.stop()
            await self.telegram_app.stop()
            await self.telegram_app.shutdown()


async def main():
    """Main entry point"""
    agent = TelegramAIAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())