import argparse
import sys
import os
from users import UserManager
from memory_manager import MemoryManager
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="AgentMemory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Register user
    reg_parser = subparsers.add_parser("register", help="Register a user and get a token")
    reg_parser.add_argument("email", type=str, help="User's email address")
    
    # Add memory
    add_parser = subparsers.add_parser("add", help="Add a new memory")
    add_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    add_parser.add_argument("text", type=str, help="The memory text to add")
    
    # Search memory
    search_parser = subparsers.add_parser("search", help="Search memories")
    search_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    search_parser.add_argument("query", type=str, help="Search query")
    
    # Get all memories
    get_all_parser = subparsers.add_parser("get_all", help="Get all memories")
    get_all_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    
    # Delete memory
    delete_parser = subparsers.add_parser("delete", help="Delete a memory by its 8-character ID")
    delete_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    delete_parser.add_argument("memory_id", type=str, help="The 8-character memory ID (e.g. abc12345)")
    
    # Force Sync
    sync_parser = subparsers.add_parser("sync", help="Force sync all memories from Storage to Gemini")
    sync_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    sync_parser.add_argument("--force", action="store_true", help="Force re-sync")
    
    # Dream
    subparsers.add_parser("dream", help="Manually trigger the dreaming process")

    args = parser.parse_args()

    if args.command == "register":
        users = UserManager()
        token = users.add_user(args.email)
        print(f"Successfully registered user {args.email}.")
        print(f"API Token: {token}")
        print("Please save this token and provide it to the MCP client.")
        return

    # Local CLI Mode (runs local scheduler)
    manager = MemoryManager()
    try:
        if args.command == "add":
            mem_id = manager.add_memory(args.token, args.text)
            print(f"Memory [ID:{mem_id}] added successfully to local buffer.")
            print("Flushing buffer to Storage/Gemini...")
            manager._flush_buffer()
            print("Done.")
            
        elif args.command == "search":
            print(f"Searching for: {args.query}")
            result = manager.search_memory(args.token, args.query)
            print("\n--- Results ---")
            print(result)
            
        elif args.command == "get_all":
            result = manager.get_all_memories(args.token)
            print("\n--- All Memories ---")
            print(result)
            
        elif args.command == "delete":
            result = manager.delete_memory(args.token, args.memory_id)
            print(result)
            
        elif args.command == "sync":
            if args.force:
                manager.sync_force(args.token)
            else:
                print("Use --force to confirm full sync.")
                
        elif args.command == "dream":
            manager.dream_all_users()
            
    finally:
        manager.scheduler.shutdown()

if __name__ == "__main__":
    main()
