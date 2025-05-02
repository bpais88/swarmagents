import os
import logging
import json
from flask import Flask, request, jsonify

# Basic Logging Setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/webhook/email', methods=['POST'])
def handle_email_webhook():
    """Receives email payloads from SendGrid Inbound Parse."""
    logging.info("Received request on /webhook/email")
    
    try:
        # SendGrid sends data primarily as form data
        # 'email' contains the raw MIME message if 'Send Raw' is checked
        # Otherwise, other form fields like 'from', 'to', 'subject', 'text', 'html' are available
        
        # Log all form data received
        logging.info(f"Request Form Data: {request.form.to_dict()}")
        
        # You might also want to log headers or the raw request data
        # logging.info(f"Request Headers: {request.headers}")
        # logging.info(f"Request Raw Data: {request.data}")
        
        # --- Placeholder for Parsing Logic ---
        # Here you would parse request.form (or request.data if using raw)
        # to extract original sender, subject, body from the forwarded email.
        # Example (will need adjustment based on SendGrid format):
        # original_sender = request.form.get('from') 
        # original_subject = request.form.get('subject')
        # original_body = request.form.get('text') or request.form.get('html')
        # logging.info(f"Extracted - Sender: {original_sender}, Subject: {original_subject}")
        
        # --- Placeholder for Triggering Agent Workflow ---
        # Pass extracted data to the orchestrator
        # result = run_agent_graph(original_sender, original_subject, original_body)
        # logging.info(f"Agent processing result: {result}")
        
        # Respond to SendGrid
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logging.error(f"Error processing webhook request: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Default port is 5000, can be overridden by environment variable
    port = int(os.environ.get('PORT', 5000))
    logging.info(f"Starting webhook server on port {port}")
    # Set debug=True for development to auto-reload; set to False in production
    # Use host='0.0.0.0' to make it accessible externally (e.g., for ngrok)
    app.run(host='0.0.0.0', port=port, debug=True) 

