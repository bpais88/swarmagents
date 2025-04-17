# Google Calendar Integration

## Setup Instructions

1. Visit the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Library"
4. Search for and enable the "Google Calendar API"
5. Go to "APIs & Services" > "Credentials"
6. Click "Create Credentials" > "OAuth client ID"
7. Set the application type to "Desktop app"
8. Name your OAuth client
9. Download the JSON file
10. Rename it to `credentials.json` and place it in this directory

## Security Notes

- Both `credentials.json` and `token.json` contain sensitive information
- These files are listed in `.gitignore` to prevent them from being committed
- Never share these files or commit them to version control
- Each developer should create their own credentials

## Usage

The first time you run the application, it will use the credentials.json file to open a browser window and prompt you to authorize the application. After authorization, it will create a token.json file that stores the access and refresh tokens. 