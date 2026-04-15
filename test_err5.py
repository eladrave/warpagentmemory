from memory_manager import MemoryManager
import logging
import os
logging.basicConfig(level=logging.DEBUG)

manager = MemoryManager()
token = "am_ef6f67db00b24c64857b1ba79bfe2c26"
user_info = manager.users.get_user_by_token(token)
user_email = user_info["email"]

user_dir = manager._get_user_dir(user_email)
for f in os.listdir(user_dir):
    print("File:", f)
    with open(os.path.join(user_dir, f), "r") as fd:
        print(fd.read())
        
store_display_name = f"AgentMemory_{user_email}"
for s in manager.gemini.client.file_search_stores.list():
    if s.display_name == store_display_name:
        print("Found store:", s.name)
        for doc in manager.gemini.client.file_search_stores.documents.list(parent=s.name):
            print("Doc in store:", doc.name, doc.display_name)
