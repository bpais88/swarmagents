import os
import requests
from dotenv import load_dotenv

load_dotenv()

class HubSpotCRMTool:
    def __init__(self):
        self.api_key = os.getenv("HUBSPOT_API_KEY")
        self.base_url = "https://api.hubapi.com"

    def log(self, lead):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Step 1: Create a contact
        contact_payload = {
            "properties": {
                "email": lead["from"],
                "firstname": "Lead",
                "lastname": "AI Generated",
            }
        }

        contact_resp = requests.post(
            f"{self.base_url}/crm/v3/objects/contacts",
            json=contact_payload,
            headers=headers
        )

        if contact_resp.status_code not in (200, 201):
            return f"[HubSpot] Failed to create contact: {contact_resp.text}"

        contact_id = contact_resp.json()["id"]

        # Step 2: Log a note
        note_payload = {
            "properties": {
                "hs_note_body": f"Lead message: {lead['subject']}"
            }
        }

        note_resp = requests.post(
            f"{self.base_url}/crm/v3/objects/notes",
            json=note_payload,
            headers=headers
        )

        if note_resp.status_code not in (200, 201):
            return f"[HubSpot] Failed to create note: {note_resp.text}"

        note_id = note_resp.json()["id"]

        # Step 3: Associate the note with the contact
        requests.put(
            f"{self.base_url}/crm/v3/objects/notes/{note_id}/associations/contact/{contact_id}/note_to_contact",
            headers=headers
        )

        return f"[HubSpot] Contact created and note logged for {lead['from']}"
