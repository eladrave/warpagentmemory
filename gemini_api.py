import os
import time
import logging
from typing import Optional, List
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=self.api_key)
        self.store_name_cache: Optional[str] = None
        
    @retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
    def get_or_create_store(self, display_name: str = "AgentMemoryStore") -> str:
        if self.store_name_cache:
            return self.store_name_cache
            
        # Try to find existing
        for store in self.client.file_search_stores.list():
            if store.display_name == display_name:
                self.store_name_cache = store.name
                logger.info(f"Found existing Gemini Store: {self.store_name_cache}")
                return self.store_name_cache
                
        # Create new
        store = self.client.file_search_stores.create(config={'display_name': display_name})
        self.store_name_cache = store.name
        logger.info(f"Created new Gemini Store: {self.store_name_cache}")
        return self.store_name_cache

    @retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
    def upload_and_index_file(self, file_path: str, display_name: str):
        store_name = self.get_or_create_store()
        
        # Check if document with this display_name exists and delete it
        docs = list(self.client.file_search_stores.documents.list(parent=store_name))
        for doc in docs:
            if getattr(doc, 'display_name', '') == display_name:
                logger.info(f"Deleting existing Gemini doc: {doc.name}")
                self.client.file_search_stores.documents.delete(name=doc.name, config={'force': True})
            
        # Upload
        logger.info(f"Uploading {file_path} to Gemini store as {display_name}...")
        op = self.client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store_name,
            file=file_path,
            config={'display_name': display_name}
        )
        
        # We won't block forever, just assume it works eventually (or block for max 30s)
        retries = 0
        while not op.done and retries < 10:
            try:
                op = self.client.operations.get(op)
            except Exception as e:
                pass
            time.sleep(3)
            retries += 1
            
        logger.info(f"Uploaded {display_name} to Gemini store.")

    @retry(wait=wait_exponential(multiplier=1, min=4, max=60), stop=stop_after_attempt(5))
    def search(self, query: str, context: str = "") -> str:
        store_name = self.get_or_create_store()
        
        sys_inst = (
            "You are an AI memory retrieval system. You will be asked questions about the user's past actions, preferences, and details. "
            "Use the provided RAG files to answer. Be concise and accurate. "
            f"Here is today's raw memory data not yet indexed (use it if relevant!): \n{context}\n"
        )
        
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=query,
            config=types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=0.2,
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))]
            )
        )
        
        return response.text
        
