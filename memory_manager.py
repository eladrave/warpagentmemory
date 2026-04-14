import os
import time
import logging
import datetime
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from drive_api import DriveClient
from gemini_api import GeminiClient

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.drive = DriveClient()
        self.gemini = GeminiClient()
        
        self.local_buffer = []
        self.buffer_lock = threading.Lock()
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self._flush_buffer, 'interval', seconds=15)
        # Run dreaming every day at 3am or configurable hours
        dream_interval = int(os.getenv("DREAM_INTERVAL_HOURS", "24"))
        self.scheduler.add_job(self.dream, 'interval', hours=dream_interval)
        self.scheduler.start()
        
        self.today_date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        
    def _get_today_filename(self) -> str:
        return f"memory_{datetime.datetime.now().strftime('%Y-%m-%d')}.md"

    def add_memory(self, memory_text: str):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        entry = f"- {timestamp} {memory_text}"
        
        with self.buffer_lock:
            self.local_buffer.append(entry)
            
        logger.info("Memory added to local buffer.")

    def _flush_buffer(self):
        with self.buffer_lock:
            if not self.local_buffer:
                return
            content_to_flush = "\n".join(self.local_buffer)
            self.local_buffer = []
            
        today_file = self._get_today_filename()
        try:
            # 1. Append to Google Drive
            self.drive.append_to_file(today_file, content_to_flush)
            
            # 2. Trigger Gemini Update
            # Download full file content to local tmp to upload to Gemini
            full_content = self.drive.read_file(today_file)
            tmp_path = f"/tmp/{today_file}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(full_content)
                
            self.gemini.upload_and_index_file(tmp_path, display_name=today_file)
            
        except Exception as e:
            logger.error(f"Failed to flush buffer to Drive/Gemini: {e}")
            # Put back in buffer
            with self.buffer_lock:
                self.local_buffer = content_to_flush.split("\n") + self.local_buffer

    def search_memory(self, query: str) -> str:
        # Context includes the unindexed local buffer
        with self.buffer_lock:
            context = "\n".join(self.local_buffer)
            
        try:
            return self.gemini.search(query, context=context)
        except Exception as e:
            logger.error(f"Failed to search Gemini: {e}")
            return "Error searching memory."

    def dream(self):
        logger.info("Initiating dreaming process...")
        try:
            # Fetch generic_memory.md
            generic_mem = self.drive.read_file("generic_memory.md")
            
            # Fetch last few days of memory (for simplicity, let's just get today and yesterday)
            today = datetime.datetime.now()
            yesterday = today - datetime.timedelta(days=1)
            
            today_mem = self.drive.read_file(f"memory_{today.strftime('%Y-%m-%d')}.md")
            yesterday_mem = self.drive.read_file(f"memory_{yesterday.strftime('%Y-%m-%d')}.md")
            
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
            # Remove markdown code block if added
            if new_generic_mem.startswith("```markdown"):
                new_generic_mem = new_generic_mem[11:]
            if new_generic_mem.startswith("```"):
                new_generic_mem = new_generic_mem[3:]
            if new_generic_mem.endswith("```"):
                new_generic_mem = new_generic_mem[:-3]
                
            self.drive.update_file_exact("generic_memory.md", new_generic_mem.strip())
            
            tmp_path = "/tmp/generic_memory.md"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(new_generic_mem.strip())
            self.gemini.upload_and_index_file(tmp_path, display_name="generic_memory.md")
            
            logger.info("Dreaming process completed successfully.")
            
        except Exception as e:
            logger.error(f"Dreaming process failed: {e}")

    def sync_force(self):
        logger.info("Forcing full sync of all memories from Drive to Gemini...")
        folder_id = self.drive.get_or_create_folder()
        query = f"'{folder_id}' in parents and trashed=false"
        request = self.drive.service.files().list(q=query, spaces='drive', fields='files(id, name)')
        results = self.drive._execute_with_retry(request)
        files = results.get('files', [])
        
        self.gemini.delete_store()
        self.gemini.get_or_create_store()
        
        for f in files:
            name = f.get('name')
            if name.endswith('.md'):
                content = self.drive.read_file(name)
                tmp_path = f"/tmp/{name}"
                with open(tmp_path, "w", encoding="utf-8") as tmp_f:
                    tmp_f.write(content)
                self.gemini.upload_and_index_file(tmp_path, display_name=name)
                
        logger.info("Full sync completed.")
