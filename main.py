#!/usr/bin/env python3
"""
EchoDesk v2.0 - Main Entry Point

Provides an interactive console interface to EchoDesk with support for:
- Text commands
- Voice processing
- Screen capture and reading
- Memory management
- Application launching
- Task execution

To use the GUI instead, run: python -m ui.main_window
"""

import sys
import traceback
from echodesk import EchoDesk


def print_welcome():
    """Print the EchoDesk welcome message."""
    print("\n" + "=" * 60)
    print("  EchoDesk v2.0 Starting...")
    print("=" * 60)
    print()


def print_status(app: EchoDesk):
    """Print the system status."""
    status = app.status()
    
    print("\nSystem Status:")
    print(f"  Running: {status['running']}")
    print(f"  Initialized: {status['initialized']}")
    print(f"  Active Subsystems: {status['subsystems_active']}/{status['subsystems_total']}")
    print()
    
    print("  Subsystem Status:")
    for name, available in status['subsystems'].items():
        status_str = "✓" if available else "✗"
        print(f"    {status_str} {name.capitalize()}")
    print()


def print_help():
    """Print available commands."""
    help_text = """
Available Commands:

  Memory Management:
    remember <text>          - Store information in memory
    what do you remember     - Retrieve memory contents
    recall <query>           - Search memory for a specific query

  Screen Operations:
    read screen              - Read text from the screen
    capture screen           - Take a screenshot
    screenshot               - Alias for capture screen

  Application Control:
    open <app_name>          - Launch an application
    launch <app_name>        - Alias for open

  Searching & Knowledge:
    search <query>           - Search the internet
    <general question>       - Ask EchoDesk a question

  Task Execution:
    execute <task>           - Execute a complex task
    plan <task>              - Create an execution plan

  System Commands:
    status                   - Show system status
    help                     - Show this help message
    exit                     - Gracefully shut down EchoDesk
    quit                     - Alias for exit

Examples:
  > remember Buy milk
  > what do you remember
  > open chrome
  > search Python tutorials
  > read screen
  > exit
"""
    print(help_text)


def handle_command(app: EchoDesk, command: str) -> bool:
    """
    Handle a user command.
    
    Args:
        app: The EchoDesk instance.
        command: The user's input command.
    
    Returns:
        True to continue, False to exit.
    """
    command = command.strip()
    if not command:
        return True
    
    # Normalize command
    cmd_lower = command.lower()
    
    # Exit commands
    if cmd_lower in ("exit", "quit"):
        print("\nGracefully shutting down EchoDesk...")
        app.shutdown()
        return False
    
    # Help command
    if cmd_lower == "help":
        print_help()
        return True
    
    # Status command
    if cmd_lower == "status":
        print_status(app)
        return True
    
    # Memory commands
    if cmd_lower.startswith("remember "):
        text = command[9:].strip()
        result = app.remember(text)
        if result.get("success"):
            print(f"✓ {result.get('message', 'Remembered.')}")
        else:
            print(f"✗ {result.get('message', 'Failed to remember.')}")
        return True
    
    if cmd_lower in ("what do you remember", "recall all"):
        result = app.recall("*")
        if result.get("success"):
            memory = result.get("result", {})
            if memory:
                print("\nMemory Contents:")
                for key, value in memory.items():
                    print(f"  {key}: {value}")
            else:
                print("No memories found.")
        else:
            print(f"✗ {result.get('message', 'Failed to recall.')}")
        return True
    
    if cmd_lower.startswith("recall "):
        query = command[7:].strip()
        result = app.recall(query)
        if result.get("success"):
            print(f"✓ Found: {result.get('result', 'No matches.')}")
        else:
            print(f"✗ {result.get('message', 'Recall failed.')}")
        return True
    
    # Screen commands
    if cmd_lower in ("read screen", "read the screen"):
        print("Reading screen...")
        result = app.read_screen()
        if result.get("success"):
            text = result.get("result", "No text found.")
            print(f"\nScreen Text:\n{text}\n")
        else:
            print(f"✗ {result.get('message', 'Failed to read screen.')}")
        return True
    
    if cmd_lower in ("capture screen", "screenshot", "take screenshot"):
        print("Capturing screen...")
        result = app.capture_screen()
        if result.get("success"):
            path = result.get("result", "")
            print(f"✓ Screenshot saved to: {path}")
        else:
            print(f"✗ {result.get('message', 'Failed to capture screen.')}")
        return True
    
    # Application launching
    if cmd_lower.startswith("open "):
        app_name = command[5:].strip()
        print(f"Launching {app_name}...")
        result = app.launch(app_name)
        if result.get("success"):
            print(f"✓ {result.get('message', 'Application launched.')}")
        else:
            print(f"✗ {result.get('message', 'Failed to launch.')}")
        return True
    
    if cmd_lower.startswith("launch "):
        app_name = command[7:].strip()
        print(f"Launching {app_name}...")
        result = app.launch(app_name)
        if result.get("success"):
            print(f"✓ {result.get('message', 'Application launched.')}")
        else:
            print(f"✗ {result.get('message', 'Failed to launch.')}")
        return True
    
    # Search command
    if cmd_lower.startswith("search "):
        query = command[7:].strip()
        print(f"Searching for '{query}'...")
        result = app.process(f"search {query}")
        if result.get("success"):
            print(f"✓ {result.get('message', 'Search completed.')}")
        else:
            print(f"✗ {result.get('message', 'Search failed.')}")
        return True
    
    # Generic command processing
    print(f"Processing: {command}")
    result = app.process(command)
    if result.get("success"):
        message = result.get("message", "Command processed.")
        print(f"✓ {message}")
    else:
        message = result.get("message", "Command failed.")
        print(f"✗ {message}")
    
    return True


def main():
    """Main entry point for EchoDesk."""
    try:
        # Initialize EchoDesk
        print_welcome()
        print("Initializing EchoDesk components...")
        
        app = EchoDesk()
        
        # Validate dependencies
        dependencies = app.validate_dependencies()
        active = sum(1 for v in dependencies.values() if v)
        total = len(dependencies)
        print(f"Loaded {active}/{total} subsystems successfully.\n")
        
        # Start the application
        app.start()
        
        # Interactive console loop
        print("EchoDesk is ready. Type 'help' for available commands.\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if not handle_command(app, user_input):
                    break
                    
            except KeyboardInterrupt:
                print("\n\nInterrupt received. Shutting down...")
                app.shutdown()
                break
            except EOFError:
                print("\n\nEnd of input. Shutting down...")
                app.shutdown()
                break
        
        print("\nEchoDesk v2.0 shutdown complete.")
        return 0
        
    except Exception as e:
        print(f"\nFatal Error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())