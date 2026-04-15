from memory_manager import MemoryManager
import logging
logging.basicConfig(level=logging.DEBUG)

manager = MemoryManager()
token = "am_ef6f67db00b24c64857b1ba79bfe2c26"
print(manager.search_memory(token, "What does the user like?"))
