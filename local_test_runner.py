import os
import json
import logging
import sys

# Add project root to Python path to allow imports from orchestrator, agents etc.
# Assuming the script is in the root directory
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now import after potentially modifying the path
from orchestrator.graph import run_graph 

# Configure basic logging for the test
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

if __name__ == "__main__":
    print("Starting local test run...")

    # Mock input data
    mock_lead_message = "Hello, I am interested in learning more about your product. Can we schedule a demo next week?"
    mock_lead_rule = "Consider it a lead if the sender asks for a meeting, demo, or pricing."
    mock_access_token = None  # Testing without a real Google token

    print(f"Lead Message: {mock_lead_message}")
    print(f"Lead Rule: {mock_lead_rule}")
    print(f"Access Token: {mock_access_token}")

    # Set environment variables if needed (e.g., for Supabase memory or specific timezone)
    # os.environ['USER_TIMEZONE'] = 'America/New_York'
    # os.environ['SUPABASE_URL'] = 'your_supabase_url'
    # os.environ['SUPABASE_ANON_KEY'] = 'your_supabase_anon_key'
    # os.environ['OPENAI_API_KEY'] = 'your_openai_key' # Ensure LLM util can find key

    try:
        report = run_graph(
            lead_message=mock_lead_message,
            lead_rule=mock_lead_rule,
            access_token=mock_access_token
        )

        print("\n--- Workflow Report ---")
        print(json.dumps(report, indent=4, default=str))

    except Exception as e:
        logging.error(f"Error during local_test_runner execution: {e}", exc_info=True)
        print(f"\n--- Test Run Failed ---")
        print(f"Error: {e}")

    print("\nLocal test run finished.")
