# MCP Server Setup Instructions

This MCP server provides a Telegram AI agent that can interact with Gmail, Google Calendar, and Google Tasks using the Ionos AI model.

## Prerequisites

1. Python 3.8 or higher
2. Google Cloud Project with APIs enabled
3. Telegram Bot Token
4. Ionos AI API Key

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the following APIs:
   - Gmail API
   - Google Calendar API
   - Google Tasks API
4. Create OAuth2 credentials:
   - Go to "Credentials" → "Create Credentials" → "OAuth client ID"
   - Choose "Desktop application"
   - Download the JSON file and rename it to `credentials.json`
   - Place it in the same directory as your script

## Step 3: Telegram Bot Setup

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Use `/newbot` command to create a new bot
3. Follow the instructions and get your bot token
4. Copy the token to your `.env` file

## Step 4: Ionos AI Setup

1. Get your API key from Ionos AI service
2. Add it to your `.env` file

## Step 5: Environment Configuration

1. Copy `.env.example` to `.env`
2. Fill in all the required values:

```bash
cp .env.example .env
# Edit .env with your actual values
```

## Step 6: First Run and Authentication

1. Run the server for the first time:

```bash
python mcp_server.py
```

2. The script will prompt you to authenticate with Google:
   - A URL will be displayed
   - Open it in your browser
   - Grant permissions
   - Copy the authorization code back to the terminal

3. Your credentials will be saved in `token.pickle` for future use

## Usage

### Available Tools

1. **send_telegram_message**: Send messages via Telegram
2. **search_gmail**: Search Gmail messages
3. **create_calendar_event**: Create Google Calendar events
4. **create_task**: Create Google Tasks
5. **ai_chat**: Chat with Ionos AI model

### Telegram Commands

- `/start` - Initialize the bot
- Send any message to chat with the AI

### Example Interactions

**Search Gmail:**
```
"Search for emails from john@example.com"
```

**Create Calendar Event:**
```
"Create a meeting for tomorrow at 2 PM for 1 hour about project review"
```

**Create Task:**
```
"Add a task to review the quarterly report by Friday"
```

## File Structure

```
├── mcp_server.py          # Main MCP server
├── requirements.txt       # Python dependencies
├── .env                  # Environment variables
├── credentials.json      # Google OAuth2 credentials
├── token.pickle         # Saved Google authentication token
└── README.md            # This file
```

## Security Notes

1. Keep your `.env` file secure and never commit it to version control
2. The `token.pickle` file contains sensitive authentication data
3. Use HTTPS in production environments
4. Regularly rotate your API keys

## Troubleshooting

### Common Issues

1. **"ModuleNotFoundError"**: Make sure all dependencies are installed
2. **"Authentication failed"**: Check your Google credentials and re-run authentication
3. **"Telegram bot not responding"**: Verify your bot token and network connection
4. **"Ionos AI errors"**: Check your API key and rate limits

### Logs

The server logs important events. Check the console output for error messages and debugging information.

## Development

To extend functionality:

1. Add new tools in the `setup_handlers()` method
2. Implement corresponding methods for each tool
3. Update the resource list if needed
4. Test thoroughly before deploying

## Production Deployment

For production use:

1. Use a process manager like systemd or supervisord
2. Set up proper logging
3. Configure firewall rules
4. Use environment-specific configuration
5. Set up monitoring and alerting

## API Rate Limits

Be aware of API rate limits:
- Gmail API: 1 billion quota units per day
- Calendar API: 1 million requests per day
- Tasks API: 50,000 requests per day
- Ionos AI: Check your plan limits

## Support

For issues or questions:
1. Check the logs for error messages
2. Verify all credentials are correct
3. Test individual components separately
4. Check API status pages for service outages