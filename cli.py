import argparse
import sys
import os
import requests
from users import UserManager
from memory_manager import MemoryManager
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    # Check if we should use remote mode
    remote_url = os.getenv("REMOTE_SERVER_URL")
    
    parser = argparse.ArgumentParser(description="AgentMemory CLI")
    parser.add_argument("--local", action="store_true", help="Force local mode (bypass remote server)")
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
    
    # Force Sync
    sync_parser = subparsers.add_parser("sync", help="Force sync all memories from Storage to Gemini")
    sync_parser.add_argument("--token", type=str, required=True, help="API Token for the user")
    sync_parser.add_argument("--force", action="store_true", help="Force re-sync")
    
    # Dream
    subparsers.add_parser("dream", help="Manually trigger the dreaming process")

    args = parser.parse_args()
    
    is_remote = remote_url and not args.local

    if args.command == "register":
        if is_remote:
            res = requests.post(f"{remote_url}/register", json={"email": args.email})
            if res.status_code == 200:
                print(f"Successfully registered user {args.email} on remote server.")
                print(f"API Token: {res.json()['token']}")
            else:
                print(f"Error registering user: {res.text}")
        else:
            users = UserManager()
            token = users.add_user(args.email)
            print(f"Successfully registered user {args.email} locally.")
            print(f"API Token: {token}")
        print("Please save this token and provide it to the MCP client.")
        return

    if is_remote:
        # Remote CLI Mode
        headers = {"Authorization": f"Bearer {getattr(args, 'token', '')}"}
        
        if args.command == "add":
            res = requests.post(f"{remote_url}/add", json={"text": args.text}, headers=headers)
            print("Remote response:", res.json() if res.status_code == 200 else res.text)
            
        elif args.command == "search":
            res = requests.post(f"{remote_url}/search", json={"query": args.query}, headers=headers)
            if res.status_code == 200:
                print("\n--- Results ---")
                print(res.json().get("results"))
            else:
                print("Remote error:", res.text)
                
        elif args.command == "sync":
            if args.force:
                res = requests.post(f"{remote_url}/sync", headers=headers)
                print("Remote response:", res.json() if res.status_code == 200 else res.text)
            else:
                print("Use --force to confirm full sync.")
                
        elif args.command == "dream":
            res = requests.post(f"{remote_url}/dream")
            print("Remote response:", res.json() if res.status_code == 200 else res.text)
            
        return

    # Local CLI Mode (runs local scheduler)
    manager = MemoryManager()
    try:
        if args.command == "add":
            manager.add_memory(args.token, args.text)
            print("Memory added successfully to local buffer.")
            print("Flushing buffer to Storage/Gemini...")
            manager._flush_buffer()
            print("Done.")
            
        elif args.command == "search":
            print(f"Searching for: {args.query}")
            result = manager.search_memory(args.token, args.query)
            print("\n--- Results ---")
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
