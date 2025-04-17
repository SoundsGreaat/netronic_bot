# Netronic Bot / Telegram Bot

[![Static Badge](https://img.shields.io/badge/MIT-Lisence?style=for-the-badge&logo=github&label=License&color=yellow)](https://github.com/SoundsGreaat/netronic_bot?tab=MIT-1-ov-file)

## Description
The project aims to simplify the process of obtaining employee contacts. Users can quickly find the necessary information using a bot in the messenger, which allows them to effectively organize communication in the organization. It is possible to ask AI for help and get answers to work-related questions.
In addition, the project allows administrators to easily edit contact information to always have up-to-date employee data.
The project was implemented strictly to [**Netronic's**](https://netronic.com.ua/lp) order.

Telegram Bot name: [**@netronic_bot**](https://t.me/netronic_bot)

## Features
### User functionality
- 🔒 **Restricted access**: Only users added to the database can access the bot.
- 🔍 **Employee search**: Search for employees by name, position, or Telegram nickname.
- 📝 **Google Forms integration**: Fill out Google Forms directly from the bot menu.
- 🏆 **View commendations**: Users can view commendation cards created by administrators.
- 🔔 **Credentials reminders**: Provide credentials for work accounts upon user request.
- 🎉 **Birthday reminders**: Notifies users about upcoming employee birthdays.
- 🤖 **AI assistance**: Ask AI for help with work-related questions and document analysis.

### Admin functionality
- 💼 **Add employees**: Add new employees to the database with their details.
- 🖋️ **Edit employee data**: Update existing employee information.
- 🗑️ **Delete employees**: Remove employees from the database when necessary.
- 🕒 **Grant temporary access**: Temporarily allow bot access without adding users to the database.
- 🔗 **Link editing mode**: Modify or delete links in the bot's menu.
- ✅ **Validation checks**: Notify administrators of incorrect phone numbers, Telegram nicknames, or links.
- 🖼️ **Create commendation cards**: Generate commendation cards using the `make_card.py` script.
- 🔄 **CRM integration**: Automatically add or remove employees in the CRM system based on database updates.
- 📊 **Google Sheets export**: Automatically export employee data to Google Sheets for convenience.
- 🎂 **Birthday notifications**: Automatically send birthday reminders to administrators or employees.
- 📝 **Programmatic Google Forms filling**: Use the `google_forms_filler.py` script to fill forms programmatically.
- 📤 **Send messages and photos**: Use the `telethon_functions.py` script to send messages and photos to users.

## Technologies
- **Python 3.12**: Main programming language.
- **Telethon**: Library for interacting with the Telegram Bot API.
- **Telegram Bot API**: Used for user interaction.
- **PostgreSQL**: Database for storing employee data.
- **SQLAlchemy**: Library for database ORM and SQL operations.
- **GForms**: Library for Google Forms integration.
- **OpenAI**: Library for AI-powered assistance.
- **Pillow**: Library for image processing.
- **Cryptography**: Library for encrypting and decrypting session files.
- **RapidFuzz**: Library for fuzzy string matching and similarity calculations.
- **APScheduler**: Library for scheduling tasks.

## How To Use It
1. **Clone the repository**: `git clone https://github.com/SoundsGreaat/netronic_bot.git`
2. **Install the required packages**: `pip install -r requirements.txt`
3. **Generate secret keys**: Create a `.env` file in the root of the project and fill it with the following data:
    ```env
    TELETHON_API_ID=your_api_id
    TELETHON_API_HASH=your_api_hash
    NETRONIC_BOT_TOKEN=your_bot_token
    DATABASE_URL=your_database_url
    OPENAI_API_KEY=your_openai_api_key
    OPENAI_ASSISTANT_ID=your_openai_assistant_id
    FERNET_KEY=your_fernet_key
    FORM_URL=your_form_url
    CRM_KEY=your_crm_key
    CRM_URL=your_crm_url
    GOOGLE_API_CREDENTIALS=your_google_api_credentials
    TELETHON_API_ID_USERBOT=your_api_id_userbot
    TELETHON_API_HASH_USERBOT=your_api_hash_userbot
    ```
4. **Run the bot**: `python src/main.py`