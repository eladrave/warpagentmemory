import os
import json
import uuid
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# If running in Cloud Run with mounted GCS, this might be e.g. /mnt/gcs/users.json
USERS_FILE_PATH = os.getenv("USERS_FILE_PATH", "users.json")

class UserManager:
    def __init__(self):
        self.file_path = USERS_FILE_PATH
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w") as f:
                json.dump({}, f)
            logger.info(f"Created new users file at {self.file_path}")

    def _load_users(self) -> Dict:
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users.json: {e}")
            return {}

    def _save_users(self, data: Dict):
        try:
            # Atomic write approach to prevent corruption
            tmp_path = self.file_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, self.file_path)
        except Exception as e:
            logger.error(f"Error saving users.json: {e}")

    def add_user(self, email: str, folder_id: str) -> str:
        """Adds a user and returns their new API token."""
        data = self._load_users()
        
        # Check if user already exists
        for token, info in data.items():
            if info.get("email") == email:
                logger.info(f"User {email} already exists, updating folder_id.")
                data[token]["folder_id"] = folder_id
                self._save_users(data)
                return token
                
        # Create new user
        token = "am_" + str(uuid.uuid4()).replace("-", "")
        data[token] = {
            "email": email,
            "folder_id": folder_id
        }
        self._save_users(data)
        logger.info(f"Created new token for {email}")
        return token

    def get_user_by_token(self, token: str) -> Optional[Dict]:
        data = self._load_users()
        return data.get(token)

    def list_users(self):
        return self._load_users()
