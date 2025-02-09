from pathlib import Path
from firebase_admin import initialize_app, credentials, firestore
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Initialize Firebase
service_account_key = Path(__file__).parent.parent / "firebase-credentials.json"
try:
    client_credentials = credentials.Certificate(str(service_account_key))
    initialize_app(client_credentials)
    db = firestore.client()
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {str(e)}")
    raise

def get_threads_from_db(conversation_id: str) -> dict:
    """
    Retrieve threads for a specific conversation from Firestore.
    
    Args:
        conversation_id: Unique identifier for the conversation (channel_id:thread_ts)
        
    Returns:
        Dict containing thread data or empty dict if not found
    """
    try:
        doc = db.collection('slack-chats').document(conversation_id).get()
        
        if doc.exists:
            return doc.to_dict()['threads']
        return {}
        
    except Exception as e:
        logger.error(f"Error retrieving threads from Firestore: {str(e)}")
        return {}

def save_threads_to_db(conversation_id: str, threads: dict) -> None:
    """
    Save threads for a specific conversation to Firestore.
    
    Args:
        conversation_id: Unique identifier for the conversation (channel_id:thread_ts)
        threads: Dictionary containing thread data
    """
    try:
        db.collection('slack-chats').document(conversation_id).set({
            'threads': threads,
            'updated_at': datetime.utcnow()
        }, merge=True)
        
        logger.info(f"Saved threads for conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Error saving threads to Firestore: {str(e)}")
        raise

class SlackThreadStorage:
    """Legacy class maintained for backward compatibility."""
    
    def __init__(self):
        self.db = db
        self.collection = self.db.collection('slack-chats')

    def save_thread(self, 
                   channel_id: str, 
                   thread_ts: str, 
                   user_id: str, 
                   initial_message: str,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Save a new Slack thread to Firestore."""
        try:
            conversation_id = f"{channel_id}:{thread_ts}"
            
            thread_data = {
                'channel_id': channel_id,
                'thread_ts': thread_ts,
                'user_id': user_id,
                'initial_message': initial_message,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_active': True,
                'message_count': 1,
                'metadata': metadata or {}
            }
            
            # Get existing threads
            existing_threads = get_threads_from_db(conversation_id)
            
            # Add new thread
            existing_threads[thread_ts] = thread_data
            
            # Save updated threads
            save_threads_to_db(conversation_id, existing_threads)
            
            return thread_ts
            
        except Exception as e:
            logger.error(f"Failed to save thread to Firestore: {str(e)}")
            raise

    def update_thread(self, 
                     thread_ts: str, 
                     updates: Dict[str, Any],
                     channel_id: str = None) -> None:
        """Update an existing thread record."""
        try:
            if not channel_id:
                raise ValueError("channel_id is required for update_thread")
                
            conversation_id = f"{channel_id}:{thread_ts}"
            
            # Get existing threads
            existing_threads = get_threads_from_db(conversation_id)
            
            if thread_ts not in existing_threads:
                raise ValueError(f"Thread {thread_ts} not found")
                
            # Update thread data
            existing_threads[thread_ts].update(updates)
            existing_threads[thread_ts]['updated_at'] = datetime.utcnow()
            
            # Save updated threads
            save_threads_to_db(conversation_id, existing_threads)
            
        except Exception as e:
            logger.error(f"Failed to update thread in Firestore: {str(e)}")
            raise

    def get_thread(self, thread_ts: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a thread record by its timestamp."""
        try:
            conversation_id = f"{channel_id}:{thread_ts}"
            threads = get_threads_from_db(conversation_id)
            return threads.get(thread_ts)
            
        except Exception as e:
            logger.error(f"Failed to retrieve thread from Firestore: {str(e)}")
            raise

    def add_message_to_thread(self,
                            thread_ts: str,
                            message: str,
                            user_id: str,
                            message_ts: str,
                            channel_id: str) -> None:
        """Add a new message to an existing thread."""
        try:
            conversation_id = f"{channel_id}:{thread_ts}"
            
            # Get existing threads
            threads = get_threads_from_db(conversation_id)
            
            if thread_ts not in threads:
                raise ValueError(f"Thread {thread_ts} not found")
                
            # Add message to thread
            if 'messages' not in threads[thread_ts]:
                threads[thread_ts]['messages'] = {}
                
            threads[thread_ts]['messages'][message_ts] = {
                'content': message,
                'user_id': user_id,
                'timestamp': message_ts,
                'created_at': datetime.utcnow()
            }
            
            # Update thread metadata
            threads[thread_ts]['updated_at'] = datetime.utcnow()
            threads[thread_ts]['message_count'] = len(threads[thread_ts]['messages'])
            
            # Save updated threads
            save_threads_to_db(conversation_id, threads)
            
        except Exception as e:
            logger.error(f"Failed to add message to thread: {str(e)}")
            raise

    def get_thread_messages(self, 
                          thread_ts: str,
                          channel_id: str,
                          limit: int = 100) -> list:
        """Retrieve messages from a thread."""
        try:
            conversation_id = f"{channel_id}:{thread_ts}"
            threads = get_threads_from_db(conversation_id)
            
            if thread_ts not in threads or 'messages' not in threads[thread_ts]:
                return []
                
            messages = list(threads[thread_ts]['messages'].values())
            messages.sort(key=lambda x: x['timestamp'])
            
            return messages[:limit]
            
        except Exception as e:
            logger.error(f"Failed to retrieve thread messages: {str(e)}")
            raise

    def close_thread(self, thread_ts: str, channel_id: str) -> None:
        """Mark a thread as inactive/closed."""
        try:
            self.update_thread(
                thread_ts=thread_ts,
                channel_id=channel_id,
                updates={'is_active': False}
            )
            logger.info(f"Closed thread {thread_ts}")
            
        except Exception as e:
            logger.error(f"Failed to close thread: {str(e)}")
            raise 