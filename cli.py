import argparse
import sys
import os
from memory_manager import MemoryManager
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="AgentMemory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Add memory
    add_parser = subparsers.add_parser("add", help="Add a new memory")
    add_parser.add_argument("text", type=str, help="The memory text to add")
    
    # Search memory
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("query", type=str, help="Search query")
    
    # Force Sync
    sync_parser = subparsers.add_parser("sync", help="Force sync all memories from Drive to Gemini")
    sync_parser.add_argument("--force", action="store_true", help="Force re-sync")
    
    # Dream
    subparsers.add_parser("dream", help="Manually trigger the dreaming process")

    args = parser.parse_args()
    
    # We initialize it here. Note: BackgroundScheduler starts automatically.
    # In CLI mode we might want to shut it down gracefully so the script ends.
    manager = MemoryManager()
    
    try:
        if args.command == "add":
            manager.add_memory(args.text)
            print("Memory added successfully to local buffer.")
            print("Flushing buffer to Drive/Gemini...")
            manager._flush_buffer()
            print("Done.")
            
        elif args.command == "search":
            print(f"Searching for: {args.query}")
            result = manager.search_memory(args.query)
            print("\n--- Results ---")
            print(result)
            
        elif args.command == "sync":
            if args.force:
                manager.sync_force()
            else:
                print("Use --force to confirm full sync.")
                
        elif args.command == "dream":
            manager.dream()
            
    finally:
        manager.scheduler.shutdown()

if __name__ == "__main__":
    main()
