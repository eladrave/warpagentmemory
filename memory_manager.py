import os
import time
import logging
import datetime
import threading
from typing import Dict, List
from apscheduler.schedulers.background import BackgroundScheduler
from drive_api import DriveClient
from gemini_api import GeminiClient
from users import UserManager

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.drive = DriveClient()
        self.gemini = GeminiClient()
        self.users = UserManager()
        
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
            content_to_flush = "\n".join(memories)
            
            try:
                # 1. Append to Google Drive (folder discovery handled by Drive API)
                self.drive.append_to_file(user_email, today_file, content_to_flush)
                
                # 2. Trigger Gemini Update
                full_content = self.drive.read_file(user_email, today_file)
                tmp_path = f"/tmp/{today_file}_{user_email}"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(full_content)
                    
                store_display_name = f"AgentMemory_{user_email}"
                self.gemini.store_name_cache = None # Clear cache to ensure we get the right user's store
                
                # Override the store name explicitly for this user
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
                    
                logger.info(f"Uploading {tmp_path} to Gemini store {store_name} as {today_file}...")
                op = self.gemini.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store_name,
                    file=tmp_path,
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
                    self.local_buffer[token] = content_to_flush.split("\n") + self.local_buffer[token]

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
            generic_mem = self.drive.read_file(user_email, "generic_memory.md")
            today = datetime.datetime.now()
            yesterday = today - datetime.timedelta(days=1)
            
            today_mem = self.drive.read_file(user_email, f"memory_{today.strftime('%Y-%m-%d')}.md")
            yesterday_mem = self.drive.read_file(user_email, f"memory_{yesterday.strftime('%Y-%m-%d')}.md")
            
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
                
            self.drive.update_file_exact(user_email, "generic_memory.md", new_generic_mem.strip())
            
            tmp_path = f"/tmp/generic_memory_{user_email}.md"
            with open(tmp_path, "w", encoding="utf-8") as f:
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
                file=tmp_path,
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
        
        try:
            folder_id = self.drive.get_user_folder_id(user_email)
        except Exception as e:
            logger.error(f"Failed to find folder for {user_email}: {e}")
            return
            
        query = f"'{folder_id}' in parents and trashed=false"
        request = self.drive.service.files().list(q=query, spaces='drive', fields='files(id, name)')
        results = self.drive._execute_with_retry(request)
        files = results.get('files', [])
        
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
        
        for f in files:
            name = f.get('name')
            if name.endswith('.md'):
                content = self.drive.read_file(user_email, name)
                tmp_path = f"/tmp/{name}_{user_email}"
                with open(tmp_path, "w", encoding="utf-8") as tmp_f:
                    tmp_f.write(content)
                logger.info(f"Uploading {name} to {store_name}...")
                self.gemini.client.file_search_stores.upload_to_file_search_store(
                    file_search_store_name=store_name,
                    file=tmp_path,
                    config={'display_name': name}
                )
                
        logger.info(f"Full sync completed for {user_email}.")
