# Setup Guide

## 1. Safety First 🔒

This project has been set up to prevent accidental leakage of sensitive credentials.
The `config.json` file is ignored by git, so your secrets will stay local.

## 2. Configuration Steps

1.  Locate the file `config.example.json`.
2.  Copy it and rename the copy to `config.json`.
3.  Open `config.json` and fill in your actual credentials:
    ```json
    "mt5_account_id": "YOUR_MT5_ID",
    "mt5_password": "YOUR_MT5_PASSWORD",
    "telegram_bot_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID"
    ```

## 3. Running the App

Once configured, run the following command to start the intelligent trading system:

```bash
# Windows (using Python Launcher)
py -m service.server -c config.json

# Linux/Mac
python3 -m service.server -c config.json
```

## 4. Updates

If you pull updates from the repository, your local `config.json` will be safe and untouched.
