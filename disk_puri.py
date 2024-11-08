import os
import sys
import subprocess
import signal

# Global list to track temporary files for cleanup
temp_files = []

def cleanup(signum, frame):
    """Remove temporary files and exit gracefully."""
    for temp_file in temp_files:
        if os.path.isfile(temp_file):
            os.remove(temp_file)
    print("\nProcess interrupted. Exiting.")
    sys.exit(0)

# Register the cleanup function with SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, cleanup)

def stream_source(pass_type, device, block_size, count=None):
    """Handle live data sources like random and zero."""
    if pass_type == "random":
        command = f"dd if=/dev/urandom of={device} bs={block_size} status=progress"
    elif pass_type == "zeros":
        command = f"dd if=/dev/zero of={device} bs={block_size} status=progress"
    
    if count:
        command += f" count={count}"
    
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"Reached the end of {device}. Disk is full.")

def path_source(pass_type, device, block_size, count=None, content=None):
    """Handle file-based data sources like ones, string, and file."""
    temp_file = None
    
    if pass_type == "ones":
        temp_file = "ones_source.tmp"
        if not os.path.isfile(temp_file):
            with open(temp_file, "wb") as f:
                f.write(b"\xFF" * (1024 * 1024 * 256))  # 256MB of 0xFF bytes
        temp_files.append(temp_file)
    
    elif pass_type == "string":
        temp_file = "string_source.tmp"
        if not os.path.isfile(temp_file):
            with open(temp_file, "wb") as f:
                for _ in range(256):  # Fill 256MB with repeated string
                    f.write(content.encode() * (1024 * 1024 // len(content)))
        temp_files.append(temp_file)
    
    elif pass_type == "file":
        temp_file = content
        if not os.path.isfile(temp_file):
            print(f"Error: File not found at {temp_file}. Skipping this pass.")
            return
    
    # Construct the command
    if count:
        command = f"dd if={temp_file} of={device} bs={block_size} count={count} status=progress"
    else:
        command = f"while :; do cat {temp_file}; done | dd of={device} bs={block_size} status=progress"
    
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"Reached the end of {device}. Disk is full.")

    # Clean up only generated temp files
    if pass_type in ["ones", "string"]:
        os.remove(temp_file)
    
    # Construct the command
    if count:
        command = f"dd if={temp_file} of={device} bs={block_size} count={count} status=progress"
    else:
        command = f"while :; do cat {temp_file}; done | dd of={device} bs={block_size} status=progress"
    
    subprocess.run(command, shell=True, check=True)

    # Clean up only generated temp files
    if pass_type in ["ones", "string"]:
        os.remove(temp_file)

import subprocess

def perform_pass(pass_info, device):
    """Perform a single pass based on type and block size until the specified count or full disk."""
    pass_type = pass_info["type"]
    block_size = pass_info["block_size"]
    count = pass_info.get("count")
    
    # Prepare command based on pass type
    if pass_type == "random":
        command = f"dd if=/dev/urandom of={device} bs={block_size} status=progress"
    elif pass_type == "zeros":
        command = f"dd if=/dev/zero of={device} bs={block_size} status=progress"
    elif pass_type == "file":
        file_path = pass_info["content"]
        command = f"while :; do cat {file_path}; done | dd of={device} bs={block_size} status=progress"
    elif pass_type == "ones":
        temp_file = "ones_source.tmp"
        if not os.path.isfile(temp_file):
            with open(temp_file, "wb") as f:
                f.write(b"\xFF" * (1024 * 1024 * 256))  # Create a 256MB file of 0xFF bytes
        command = f"while :; do cat {temp_file}; done | dd of={device} bs={block_size} status=progress"
    elif pass_type == "string":
        temp_file = "string_source.tmp"
        text = pass_info["content"].encode()
        if not os.path.isfile(temp_file):
            with open(temp_file, "wb") as f:
                for _ in range(256):  # Fill 256MB with the repeated string
                    f.write(text * (1024 * 1024 // len(text)))
        command = f"while :; do cat {temp_file}; done | dd of={device} bs={block_size} status=progress"

    # Append count if specified
    if count:
        command += f" count={count}"

    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        if "end of device" in str(e):
            print("Disk is full; moving to the next pass.")
        else:
            print(f"Unexpected error: {e}")
            raise  # Re-raise unexpected errors
    finally:
        # Clean up temporary files after execution
        if pass_type in ["ones", "string"]:
            os.remove(temp_file)

def configure_passes():
    """Allow users to create their own pass schema with real-time schema display."""
    passes = []
    print("Create your custom pass schema.\n")
    
    while True:
        # Enhanced pass type prompt with descriptions
        print("Available pass types:")
        print("  (r)andom - Writes random data to the disk")
        print("  (z)eros  - Writes zeros to the disk")
        print("  (o)nes   - Writes binary ones (0xFF) to the disk")
        print("  (s)tring - Repeats a specified text string across the disk")
        print("  (f)ile   - Repeats the contents of a file across the disk")
        pass_type = input("Choose a pass type to add (r, z, o, s, f), or 'done' to finish: ").strip().lower()
        
        # Match user input to pass types
        if pass_type == "done":
            break
        elif pass_type == "r":
            pass_type = "random"
        elif pass_type == "z":
            pass_type = "zeros"
        elif pass_type == "o":
            pass_type = "ones"
        elif pass_type == "s":
            pass_type = "string"
        elif pass_type == "f":
            pass_type = "file"
        else:
            print("Invalid choice. Please enter one of the letters (r, z, o, s, f) or 'done' to finish.")
            continue
        
        # Prompt for content if necessary
        if pass_type == "string":
            content = input("Enter the string to fill the disk with: ").strip()
        elif pass_type == "file":
            content = input("Enter the path to the source file: ").strip()
            if not os.path.isfile(content):
                print("Invalid file path. Please enter a valid file.")
                continue
        else:
            content = None  # No content required for random, zeros, and ones

        # Prompt for block size, defaulting to 4M
        block_size = input("Enter block size (default 4M): ").strip() or "4M"

        # Prompt for count, optional
        count = input("Enter count (leave blank to fill the disk): ").strip() or None
        
        # Add the pass with type, content, block size, and count
        passes.append({"type": pass_type, "content": content, "block_size": block_size, "count": count})
        
        # Print the updated schema after each addition
        print("\nCurrent Pass Schema:")
        for i, p in enumerate(passes, start=1):
            content_display = ""
            if p["type"] == "string":
                content_display = f" (String: {p['content'][:24]}...)"  # Show first 24 characters
            elif p["type"] == "file":
                content_display = f" (File: {p['content']})"
            count_display = f", Count: {p['count']}" if p["count"] else ""
            print(f"{i}. Type: {p['type'].capitalize()}, Block Size: {p['block_size']}{count_display}{content_display}")
    
    return passes

def main():
    print("Multi-Pass Disk Preparation Script")

    if os.geteuid() != 0:
        print("This script requires elevated privileges. Please run with sudo.")
        sys.exit(1)

    device = input("\nEnter the destination device (e.g., /dev/diskX): ")

    # Configure passes
    passes = configure_passes()

    # Confirm before proceeding
    proceed = input("\nProceed with the above schema? (y/n): ").strip().lower()
    if proceed != 'y':
        print("Exiting without changes.")
        sys.exit(1)

    # Run each pass
    for i, pass_info in enumerate(passes, start=1):
        print(f"Running Pass {i}: Type: {pass_info['type'].capitalize()}, Block Size: {pass_info['block_size']}, Count: {pass_info['count'] or 'until full'}")
        perform_pass(pass_info, device)

    print("Disk preparation completed.")

if __name__ == "__main__":
    main()
