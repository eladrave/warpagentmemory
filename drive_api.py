import os
import io
import time
import logging
import json
from typing import Optional, Dict
from google.oauth2.service_account import Credentials
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']

class RateLimitException(Exception):
    pass

class DriveClient:
    def __init__(self, service_account_path: str = "service_account.json"):
        self.sa_email = "unknown"
        if os.path.exists(service_account_path):
            with open(service_account_path, "r") as f:
                self.sa_email = json.load(f).get("client_email", "unknown")
            creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
            self.service = build('drive', 'v3', credentials=creds)
            logger.info("Initialized Google Drive with Service Account.")
        else:
            credentials, _ = google.auth.default(scopes=SCOPES)
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Initialized Google Drive with Default Credentials.")
            
        self.folder_id_cache: Optional[str] = None
        self.file_id_cache: Dict[str, str] = {}
        self.folder_name = "AgentMemory"

    @retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5), retry=retry_if_exception_type(HttpError))
    def _execute_with_retry(self, request):
        return request.execute()

    def get_or_create_folder(self) -> str:
        if self.folder_id_cache:
            return self.folder_id_cache

        # For SAs, we can only write to folders shared with them by normal users.
        query = f"name='{self.folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        request = self.service.files().list(q=query, spaces='drive', fields='files(id, name, capabilities)')
        results = self._execute_with_retry(request)
        files = results.get('files', [])

        if not files:
            raise Exception(f"AgentMemory folder not found! Please create a folder named 'AgentMemory' in your personal Google Drive and share it with Editor permissions to: {self.sa_email}")

        self.folder_id_cache = files[0].get('id')
        logger.info(f"Found AgentMemory folder with ID: {self.folder_id_cache}")

        return self.folder_id_cache

    def get_or_create_file(self, filename: str) -> str:
        if filename in self.file_id_cache:
            return self.file_id_cache[filename]

        folder_id = self.get_or_create_folder()
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        request = self.service.files().list(q=query, spaces='drive', fields='files(id, name)')
        results = self._execute_with_retry(request)
        files = results.get('files', [])

        if not files:
            file_metadata = {
                'name': filename,
                'parents': [folder_id],
                'mimeType': 'text/markdown'
            }
            media = MediaIoBaseUpload(io.BytesIO(b""), mimetype='text/markdown', resumable=True)
            request = self.service.files().create(body=file_metadata, media_body=media, fields='id')
            file = self._execute_with_retry(request)
            file_id = file.get('id')
            logger.info(f"Created file {filename} with ID: {file_id}")
        else:
            file_id = files[0].get('id')
            logger.info(f"Found file {filename} with ID: {file_id}")

        self.file_id_cache[filename] = file_id
        return file_id

    def read_file(self, filename: str) -> str:
        try:
            file_id = self.get_or_create_file(filename)
            request = self.service.files().get_media(fileId=file_id)
            content = self._execute_with_retry(request)
            return content.decode('utf-8')
        except HttpError as e:
            if "File not found" in str(e) or e.resp.status == 404:
                return ""
            raise e
        except Exception as e:
            logger.error(f"Failed to read file {filename}: {e}")
            return ""

    def append_to_file(self, filename: str, text: str):
        file_id = self.get_or_create_file(filename)
        current_content = self.read_file(filename)
        
        new_content = current_content + "\n" + text + "\n"
        
        media = MediaIoBaseUpload(io.BytesIO(new_content.encode('utf-8')), mimetype='text/markdown', resumable=True)
        request = self.service.files().update(fileId=file_id, media_body=media)
        self._execute_with_retry(request)
        logger.info(f"Appended text to {filename}")

    def update_file_exact(self, filename: str, content: str):
        file_id = self.get_or_create_file(filename)
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/markdown', resumable=True)
        request = self.service.files().update(fileId=file_id, media_body=media)
        self._execute_with_retry(request)
        logger.info(f"Updated full content of {filename}")

