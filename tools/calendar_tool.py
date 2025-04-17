from utils.llm import llm_think
from datetime import datetime
import logging

class CalendarTool:
    def schedule(self, lead_message: str):
        today = datetime.today().strftime("%A, %B %d, %Y")

        prompt = f"""
Today is {today}.

A customer sent the following message:

\"\"\"{lead_message}\"\"\"

Please do the following:
1. Extract a realistic future date and time for a 30-minute meeting based on their availability.
2. Specify whether the meeting is "online" or "in-person".
3. Suggest a meeting subject line.
4. Respond with *only* the following JSON block wrapped in triple backticks.

```json
{{
  "datetime": "Wednesday, April 24, 2025 at 10:00 AM",
  "mode": "online",
  "subject": "AI project discussion"
}}
"""
        response, _ = llm_think(prompt)

        # Debug the raw LLM output
        print("\n🔍 LLM Response from CalendarTool:\n", response, "\n")

        try:
            json_part = response.strip().split("```json")[-1].split("```")[0].strip()
            print("✅ Extracted JSON block:\n", json_part)
            return json_part
        except Exception as e:
            logging.error(f"[CalendarTool] Failed to extract JSON: {e}")
            return ""
