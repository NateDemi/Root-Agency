from pathlib import Path
from agency_swarm import Agency
from firebase_admin import initialize_app, credentials, firestore
from reporting_manager.reporting_manager import ReportingManager
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

# Authenticate on firebase
service_account_key = str(Path(__file__).parent /"firebase-credentials.json")

client_credentials = credentials.Certificate(service_account_key)
initialize_app(client_credentials)
db = firestore.client()


reporting_manager = ReportingManager()


def get_threads_from_db(conversation_id):
    doc = db.collection(u'slack-chats').document(conversation_id).get()

    if doc.exists:
        return doc.to_dict()['threads']
    else:
        return {}


def save_threads_to_db(conversation_id, threads):
    db.collection(u'slack-chats').document(conversation_id).set({
        u'threads': threads
    })


def generate_response(message, conversation_id):
    agency = Agency(
        [reporting_manager],
        shared_instructions=str(Path(__file__).parent /"agency_manifesto.md"),
        threads_callbacks={
            "load": lambda: get_threads_from_db(conversation_id),
            "save": lambda threads: save_threads_to_db(conversation_id, threads),
        },
        settings_path=str(Path(__file__).parent / "settings.json")
    )

    completion = agency.get_completion(message, yield_messages=False)
    return completion

if __name__ == "__main__":
    print(generate_response("Hello", "test_channel_id:test_thread_id"))