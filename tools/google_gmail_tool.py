import os
import logging
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow # Might need this for initial auth helper later
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# TODO: Define precise scopes needed
SCOPES = ['https://www.googleapis.com/auth/gmail.compose', 'https://www.googleapis.com/auth/gmail.readonly']

class GoogleGmailTool:
    """Tool for interacting with the Gmail API, focusing on creating drafts."""

    def __init__(self, user_id='me'):
        """
        Initializes the tool, potentially loading credentials.
        user_id: The user's email address or 'me' to indicate the authenticated user.
        """
        self.user_id = user_id
        self.service = self._get_service()

    def _get_service(self):
        """Authenticates and returns the Gmail API service client."""
        creds = None
        # TODO: Implement robust credential loading/refreshing
        # This initial version expects refresh token and client secrets in env vars
        
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

        if not all([client_id, client_secret, refresh_token]):
            logging.error("Missing Google OAuth environment variables (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)")
            raise ValueError("Missing Google OAuth environment variables")

        try:
            # Create credentials object from refresh token
            creds = Credentials.from_authorized_user_info(
                info={
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scopes": SCOPES # Ensure scopes match what the refresh token was granted for
                },
                scopes=SCOPES
            )

            # If credentials exist and are expired, refresh them
            if creds and creds.expired and creds.refresh_token:
                logging.info("Refreshing Google OAuth token.")
                creds.refresh(Request())
                # TODO: Persist the potentially updated credentials (if needed)
            
            if not creds or not creds.valid:
                 # This path ideally shouldn't be hit if refresh token is valid
                 # We might need an initial auth flow here if no refresh token exists
                 logging.error("Failed to obtain valid Google OAuth credentials.")
                 raise ValueError("Failed to obtain valid Google OAuth credentials.")

            service = build('gmail', 'v1', credentials=creds)
            logging.info("Gmail API service created successfully.")
            return service
        except Exception as e:
            logging.error(f"Error creating Gmail service: {e}", exc_info=True)
            raise

    def create_draft(self, subject: str, to_address: str, body_text: str, thread_id: str = None):
        """
        Creates a draft email in the user's Gmail account.

        Args:
            subject: The subject line of the email.
            to_address: The recipient's email address.
            body_text: The plain text body of the email.
            thread_id: Optional; the thread ID to reply to. If provided, sets References/In-Reply-To.

        Returns:
            The created draft object or None if an error occurred.
        """
        if not self.service:
            logging.error("Gmail service not available.")
            return None
        
        try:
            message = MIMEText(body_text)
            message['to'] = to_address
            message['subject'] = subject
            # TODO: Add 'from' if needed (usually defaults to authenticated user)
            # message['from'] = self.user_id 
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {'raw': encoded_message}
            draft_body = {'message': create_message}

            if thread_id:
                # To make it a reply, include threadId and potentially fetch 
                # References/In-Reply-To headers from the original message using thread_id
                # This requires 'gmail.readonly' scope and fetching the original message
                # For simplicity now, just associating with the thread.
                # Proper threading requires setting 'References' and 'In-Reply-To' headers in MIMEText
                draft_body['message']['threadId'] = thread_id
                logging.info(f"Creating draft as part of thread: {thread_id}")
                # Placeholder: Add logic here to get original headers and set them in MIMEText
                # Example: message['In-Reply-To'] = original_message_id
                #          message['References'] = original_references

            draft = self.service.users().drafts().create(
                userId=self.user_id,
                body=draft_body
            ).execute()

            logging.info(f"Draft created successfully. Draft ID: {draft['id']}")
            return draft

        except HttpError as error:
            logging.error(f'An HTTP error occurred creating draft: {error}')
            return None
        except Exception as e:
            logging.error(f'An unexpected error occurred creating draft: {e}', exc_info=True)
            return None

# Example usage (for testing):
if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    # Make sure GOOGLE_* env vars are set in your .env file
    if not os.getenv('GOOGLE_REFRESH_TOKEN'):
        print("Please set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN in your .env file.")
    else:
        try:
            gmail_tool = GoogleGmailTool(user_id='me') # Use 'me' for the authenticated user
            # Test draft creation
            draft = gmail_tool.create_draft(
                subject="Test Draft from Agent",
                to_address="example-recipient@example.com", # CHANGE THIS to a valid recipient
                body_text="This is a test draft created by the GoogleGmailTool."
                # thread_id="YOUR_TEST_THREAD_ID" # Optional: Add a real thread ID from your Gmail
            )
            if draft:
                print(f"Draft created: {draft}")
            else:
                print("Failed to create draft.")
        except Exception as e:
            print(f"Error during testing: {e}")

