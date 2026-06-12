import os
from google.cloud import firestore
from datetime import datetime, timedelta

class StateManager:
    def __init__(self):
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("Missing GOOGLE_CLOUD_PROJECT environment variable.")
        
        # Connect to the default Firestore database
        self.db = firestore.Client(project=project_id)
        # Create a dedicated document just for tracking the ingestion timeline
        self.doc_ref = self.db.collection('adk_system').document('ingestion_state')

    def get_date_window(self, start_default="2025-01-01", days_to_fetch=7):
        """Retrieves the bookmark and calculates the next 7-day window."""
        doc = self.doc_ref.get()
        
        if doc.exists:
            current_start = doc.to_dict().get('last_processed_date', start_default)
        else:
            # If the database is empty, initialize it with the default start date
            current_start = start_default
            self.doc_ref.set({'last_processed_date': current_start})
        
        # Calculate the end date for the Gmail query
        start_dt = datetime.strptime(current_start, "%Y-%m-%d")
        end_dt = start_dt + timedelta(days=days_to_fetch)
        end_str = end_dt.strftime("%Y-%m-%d")
        
        return current_start, end_str

    def advance_cursor(self, new_date):
        """Moves the bookmark forward in Firestore after a successful batch."""
        self.doc_ref.set({'last_processed_date': new_date}, merge=True)
        print(f"[StateManager] Time-slicer advanced to {new_date}")