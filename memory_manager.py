import os
import time
import logging
import datetime
import threading
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from gemini_api import GeminiClient
from users import UserManager

logger = logging.getLogger(__name__)

# Default to a local directory if not running in Cloud Run
STORAGE_DIR = os.getenv("STORAGE_DIR", os.path.join(os.getcwd(), "gcs_mount"))

class MemoryManager:
    def __init__(self):
        self.gemini = GeminiClient()
        self.users = UserManager()
        
        # Ensure base storage directory exists
        os.makedirs(STORAGE_DIR, exist_ok=True)
        
        # token -> list of memories
        self.local_buffer: Dict[str, List[str]] = {}
        self.buffer_lock = threading.Lock()
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._flush_buffer, 'interval', seconds=15)
        # Run dreaming every day at 3am or configurable hours
        dream_interval = int(os.getenv("DREAM_INTERVAL_HOURS", "24"))
        self.scheduler.add_job(self.dream_all_users, 'interval', hours=dream_interval)
        self.scheduler.start()
        
    def _get_today_filename(self) -> str:
        return f"memory_{datetime.datetime.now().strftime('%Y-%m-%d')}.md"
        
    def _get_user_dir(self, user_email: str) -> str:
        # Create user-specific directory in GCS mount
        user_dir = os.path.join(STORAGE_DIR, user_email)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def add_memory(self, token: str, memory_text: str):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        entry = f"- {timestamp} {memory_text}"
        
        with self.buffer_lock:
            if token not in self.local_buffer:
                self.local_buffer[token] = []
            self.local_buffer[token].append(entry)
            
        logger.info(f"Memory added to local buffer for token {token[:10]}...")

    def _flush_buffer(self):
        with self.buffer_lock:
            if not self.local_buffer:
                return
            snapshot = self.local_buffer
            self.local_buffer = {}
            
        today_file = self._get_today_filename()
        
        for token, memories in snapshot.items():
            if not memories:
                continue
                
            user_info = self.users.get_user_by_token(token)
            if not user_info:
                logger.error(f"Invalid token {token} during flush.")
                continue
                
            user_email = user_info["email"]
            content_to_flush = "\n".join(memories) + "\n"
            
            try:
                # 1. Append to local file (GCS bucket mount)
                user_dir = self._get_user_dir(user_email)
                file_path = os.path.join(user_dir, today_file)
                
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(content_to_flush)
                
                # 2. Trigger Gemini Update
                store_display_name = f"AgentMemory_{user_email}"
                self.gemini.store_name_cache = None # Clear cache
                
                def _get_store():
                    for s in self.gemini.client.file_search_stores.list():
                        if s.display_name == store_display_name:
                            return s.name
                    s = self.gemini.client.file_search_stores.create(config={'display_name': store_display_name})
                    return s.name
                    
                store_name = _get_store()
                
                # Check if document exists and delete it
                docs = list(self.gemini.client.file_search_stores.documents.list(parent=store_name))
                for doc in docs:
                    if getattr(doc, 'display_name', '') == today_file:
                        self.gemini.client.file_search_stores.documents.delete(name=doc.name, config={'force': True})
                    
                logger.info(f"Uploading {file_path} to Gemini store {store_name} as {today_file}...")
                op = self.gemini.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store_name,
                    file=file_path,
                    config={'display_name': today_file}
                )
                
                retries = 0
                while not op.done and retries < 10:
                    try:
                        op = self.gemini.client.operations.get(op)
                    except:
                        pass
                    time.sleep(3)
                    retries += 1
                
                logger.info(f"Successfully flushed for {user_email}")
                
            except Exception as e:
                logger.error(f"Failed to flush buffer for {user_email}: {e}")
                # Put back in buffer
                with self.buffer_lock:
                    if token not in self.local_buffer:
                        self.local_buffer[token] = []
                    self.local_buffer[token] = memories + self.local_buffer[token]

    def search_memory(self, token: str, query: str) -> str:
        user_info = self.users.get_user_by_token(token)
        if not user_info:
            raise ValueError("Invalid API token.")
            
        user_email = user_info["email"]
        store_display_name = f"AgentMemory_{user_email}"
        
        with self.buffer_lock:
            context = "\n".join(self.local_buffer.get(token, []))
            
        store_name = None
        for s in self.gemini.client.file_search_stores.list():
            if s.display_name == store_display_name:
                store_name = s.name
                break
                
        if not store_name:
            return "No memory store found for this user."
            
        sys_inst = (
            "You are an AI memory retrieval system. You will be asked questions about the user's past actions, preferences, and details. "
            "Use the provided RAG files to answer. Be concise and accurate. "
            f"Here is today's raw memory data not yet indexed (use it if relevant!): \n{context}\n"
        )
        
        from google.genai import types
        response = self.gemini.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=query,
            config=types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=0.2,
                tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[store_name]))]
            )
        )
        
        return response.text

    def dream_all_users(self):
        logger.info("Initiating global dreaming process...")
        for token, user_info in self.users.list_users().items():
            self._dream_user(user_info)
            
    def _dream_user(self, user_info: Dict):
        user_email = user_info["email"]
        logger.info(f"Dreaming for {user_email}...")
        
        try:
            user_dir = self._get_user_dir(user_email)
            generic_mem_path = os.path.join(user_dir, "generic_memory.md")
            
            generic_mem = ""
            if os.path.exists(generic_mem_path):
                with open(generic_mem_path, "r", encoding="utf-8") as f:
                    generic_mem = f.read()
                    
            today = datetime.datetime.now()
            yesterday = today - datetime.timedelta(days=1)
            
            today_mem_path = os.path.join(user_dir, f"memory_{today.strftime('%Y-%m-%d')}.md")
            yesterday_mem_path = os.path.join(user_dir, f"memory_{yesterday.strftime('%Y-%m-%d')}.md")
            
            today_mem = ""
            if os.path.exists(today_mem_path):
                with open(today_mem_path, "r", encoding="utf-8") as f:
                    today_mem = f.read()
                    
            yesterday_mem = ""
            if os.path.exists(yesterday_mem_path):
                with open(yesterday_mem_path, "r", encoding="utf-8") as f:
                    yesterday_mem = f.read()
            
            if not today_mem and not yesterday_mem:
                logger.info(f"No recent memories to dream about for {user_email}.")
                return
                
            prompt = (
                "You are tasked with summarizing recent AI agent memories into a master generic_memory.md file.\n"
                "Extract any permanent user preferences, facts, or important instructions from the recent memories and merge them into the master file.\n"
                "Keep the master file concise, organized by category, and drop irrelevant daily details.\n"
                f"CURRENT MASTER GENERIC MEMORY:\n{generic_mem}\n\n"
                f"RECENT MEMORIES:\n{yesterday_mem}\n{today_mem}\n\n"
                "Output ONLY the new raw markdown for the generic_memory.md file."
            )
            
            model = os.getenv("DREAMING_MODEL", "gemini-2.5-flash")
            response = self.gemini.client.models.generate_content(
                model=model,
                contents=prompt
            )
            
            new_generic_mem = response.text
            if new_generic_mem.startswith("```markdown"):
                new_generic_mem = new_generic_mem[11:]
            if new_generic_mem.startswith("```"):
                new_generic_mem = new_generic_mem[3:]
            if new_generic_mem.endswith("```"):
                new_generic_mem = new_generic_mem[:-3]
                
            with open(generic_mem_path, "w", encoding="utf-8") as f:
                f.write(new_generic_mem.strip())
                
            store_display_name = f"AgentMemory_{user_email}"
            store_name = None
            for s in self.gemini.client.file_search_stores.list():
                if s.display_name == store_display_name:
                    store_name = s.name
                    break
            if not store_name:
                s = self.gemini.client.file_search_stores.create(config={'display_name': store_display_name})
                store_name = s.name
                
            docs = list(self.gemini.client.file_search_stores.documents.list(parent=store_name))
            for doc in docs:
                if getattr(doc, 'display_name', '') == "generic_memory.md":
                    self.gemini.client.file_search_stores.documents.delete(name=doc.name, config={'force': True})
                    
            op = self.gemini.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=generic_mem_path,
                config={'display_name': "generic_memory.md"}
            )
            
            logger.info(f"Dreaming process completed successfully for {user_email}.")
            
        except Exception as e:
            logger.error(f"Dreaming process failed for {user_email}: {e}")

    def sync_force(self, token: str):
        user_info = self.users.get_user_by_token(token)
        if not user_info:
            raise ValueError("Invalid API token.")
        
        user_email = user_info["email"]
        logger.info(f"Forcing full sync of all memories for {user_email}...")
        
        user_dir = self._get_user_dir(user_email)
        files = [f for f in os.listdir(user_dir) if f.endswith('.md')]
        
        store_display_name = f"AgentMemory_{user_email}"
        
        # Delete old store
        for s in list(self.gemini.client.file_search_stores.list()):
            if s.display_name == store_display_name:
                self.gemini.client.file_search_stores.delete(name=s.name)
                logger.info(f"Deleted old Gemini Store for {user_email}")
                break
                
        # Create new store
        store = self.gemini.client.file_search_stores.create(config={'display_name': store_display_name})
        store_name = store.name
        
        for name in files:
            file_path = os.path.join(user_dir, name)
            logger.info(f"Uploading {name} to {store_name}...")
            self.gemini.client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store_name,
                file=file_path,
                config={'display_name': name}
            )
                
        logger.info(f"Full sync completed for {user_email}.")
