import os
import sys
import subprocess
import signal
import stat
import time

# Global variables
temp_files = []
schema_sources = []
DEFAULT_DD_FLAGS = "bs=4M iflag=fullblock oflag=direct conv=fdatasync status=progress"

# Metadata dictionary defining sources
source_types_metadata = {
    "random": {
        "description": "random data",
        "if_device": "/dev/urandom",
        "content": None,
        "continuous_write": False,
    },
    "zeros": {
        "description": "zeros",
        "if_device": "/dev/zero",
        "content": None,
        "continuous_write": False,
    },
    "path": {
        "description": "content from system path",
        "requires_input_path": True,
        "content": None,
        "continuous_write": None,  # Will be set by user choice
    },
}


# Check if the given path is a block device
def is_block_device(path):
    return os.path.exists(path) and stat.S_ISBLK(os.stat(path).st_mode)


# Construct the dd command, with or without while loop
def build_dd_command(if_device, of_device, flags, continuous_write):
    if continuous_write:
        return f"while :; do cat {if_device}; done | dd of={of_device} {flags}"
    return f"dd if={if_device} of={of_device} {flags}"


def create_data_file():
    print("\n\033[1mCreate Custom Data File:\033[0m")

    # Get content
    user_input = input("Enter file content (default: All binary ones): ").strip()
    content = (
        b"\xFF" if not user_input or user_input.upper() == "FF" else user_input.encode()
    )

    # Get file size
    size_mb = input("Enter file size in MB (default: 128MB): ").strip()
    try:
        size_mb = int(size_mb) if size_mb else 128
    except ValueError:
        print("Invalid size input. Using default 128MB.")
        size_mb = 128

    # Get filename (with default)
    default_name = f"gen_{int(time.time())}.tmp"
    filename = (
        input(f"Enter filename (default: {default_name}): ").strip() or default_name
    )

    # Get cleanup preference
    cleanup = (
        input("Remove file after script completion? [Y/n]: ").strip().lower() != "n"
    )

    # Create the file
    repeat_count = (size_mb * 1024 * 1024) // len(content)
    with open(filename, "wb") as f:
        f.write(content * repeat_count)

    if cleanup:
        temp_files.append(filename)

    print(f"\nCreated file: {filename}")
    print(f"Size: {size_mb}MB")
    print(f"Cleanup on exit: {'Yes' if cleanup else 'No'}")

    # Offer to add to schema with automatic path selection
    if input("\nAdd this file to schema? [Y/n]: ").strip().lower() != "n":
        device = get_device()
        if device:
            write_mode = (
                input("Write source: (o)nce or (c)ontinuously? ").strip().lower()
            )
            continuous_write = write_mode.startswith("c")

            flags = (
                input(
                    f"Enter dd flags or press Enter for default [{DEFAULT_DD_FLAGS}]: "
                ).strip()
                or DEFAULT_DD_FLAGS
            )

            command = build_dd_command(filename, device, flags, continuous_write)

            schema_sources.append(
                {"device": device, "type": "path", "flags": flags, "command": command}
            )
            print("Source added successfully.")


def execute_command(command):
    try:
        process = subprocess.run(command, shell=True, text=True, stderr=subprocess.PIPE)
        if process.returncode == 0:
            return True
        elif "No space left on device" in process.stderr:
            return True  # Drive full is success case
        return False
    except Exception as e:
        return False


# Check of_device
def get_device():
    device = input("Enter target drive (e.g., /dev/sdb): ").strip()
    if not is_block_device(device):
        print("Invalid device path. Ensure it is a valid block device in /dev/.")
        return None
    return device


def add_source_to_schema():
    device = get_device()
    if not device:
        return

    # Prompt for source type
    print("\n\033[1mChoose source type:\033[0m")
    for key, meta in source_types_metadata.items():
        print(f"({key[0]}){key[1:]: <6} - {meta['description']}")

    source_type_key = input("Choose source type: ").strip().lower()

    # Retrieve metadata for the selected source type
    source_type = next(
        (key for key in source_types_metadata if source_type_key == key[0]), None
    )
    if not source_type:
        print("Invalid source type.")
        return
    metadata = source_types_metadata[source_type]

    # Configure if_device based on source type
    if_device = metadata.get("if_device")

    # Handle path input source types
    if metadata.get("requires_input_path"):
        if_device = input("Enter the full path to the source: ").strip()
        if not os.path.exists(if_device):
            print("Invalid path.")
            return

        write_mode = input("Write source: (o)nce or (c)ontinuously? ").strip().lower()
        metadata["continuous_write"] = write_mode.startswith("c")

    # Get dd flags
    flags = (
        input(
            f"Enter dd flags or press Enter for default [{DEFAULT_DD_FLAGS}]: "
        ).strip()
        or DEFAULT_DD_FLAGS
    )

    # Build the command using the simplified build_dd_command
    command = build_dd_command(
        if_device, device, flags, metadata.get("continuous_write", False)
    )

    # Add the source to schema
    schema_sources.append(
        {"device": device, "type": source_type, "flags": flags, "command": command}
    )
    print("Source added successfully.")


# Menu item: delete a pass from the schema
def delete_source():
    if not schema_sources:
        print("No sources to delete.")
        return
    try:
        source_number = int(input("Enter source number to delete: ").strip()) - 1
        if 0 <= source_number < len(schema_sources):
            del schema_sources[source_number]
            print("Source deleted.")
        else:
            print("Invalid source number.")
    except ValueError:
        print("Please enter a valid number.")


# Menu item: duplicate an existing pass
def copy_source():
    if not schema_sources:
        print("No sources to copy.")
        return
    try:
        source_number = int(input("Enter source number to copy: ").strip()) - 1
        if 0 <= source_number < len(schema_sources):
            schema_sources.append(schema_sources[source_number].copy())
            print("Source copied.")
        else:
            print("Invalid source number.")
    except ValueError:
        print("Please enter a valid number.")


# Print the current schema with commands
def print_schema():
    print(f"\n\033[1mCurrent Schema:\033[0m")
    print(
        f"Repeat count: {schema_repeat_count if schema_repeat_count > 0 else 'infinite'}"
    )
    print()
    if not schema_sources:
        print("  (No sources added yet)")
    else:
        for i, s in enumerate(schema_sources, start=1):
            print(f"\033[1m{i}.\033[0m {s['command']}")
            print()  # Blank line between passes


# Menu item: set the run count
def set_repeat_count():
    try:
        repeat_count = int(
            input(
                "Enter the number of times to repeat the schema (0 for infinitely): "
            ).strip()
        )
        if repeat_count < 0:
            print("Invalid input. Setting repeat count to 1 by default.")
            repeat_count = 1
        global schema_repeat_count
        schema_repeat_count = repeat_count
    except ValueError:
        print("Invalid input. Setting repeat count to 1 by default.")
        schema_repeat_count = 1


def run_schema():
    run_count = 0

    while schema_repeat_count == 0 or run_count < schema_repeat_count:
        run_count += 1
        print(f"\n\033[1m --- Starting Schema Run {run_count} ---\033[0m")

        for i, source_info in enumerate(schema_sources, start=1):
            print(f"\n\033[1m{i}.\033[0m {source_info['command']}\n")

            if execute_command(source_info["command"]):
                print("Pass completed successfully.")
            else:
                print("Error during execution.")
                return

        if schema_repeat_count > 0:
            print(f"--- Completed run {run_count} of {schema_repeat_count} ---")

    print("Disk preparation completed.")


# Remove temporary files and exit gracefully
def cleanup(signum, frame):
    for temp_file in temp_files:
        if os.path.isfile(temp_file):
            os.remove(temp_file)
    print("\nProcess interrupted. Exiting.")
    sys.exit(0)


# Register cleanup handler
signal.signal(signal.SIGINT, cleanup)


# Main menu for schema setup and execution
def main_menu():
    while True:
        print("\n\033[1mMain Menu:\033[0m")
        print("(a)dd      - Add source to schema")
        print("(d)elete   - Delete source from schema")
        print("(c)opy     - Duplicate existing source")
        print("(g)enerate - Generate a custom data file")
        print("(r)epeat   - Set whether to repeat the schema")
        print("Type 'done' to execute your schema.")

        choice = input("Choose an option: ").strip().lower()

        if choice == "a":
            add_source_to_schema()
        elif choice == "d":
            delete_source()
        elif choice == "c":
            copy_source()
        elif choice == "r":
            set_repeat_count()
        elif choice == "g":
            create_data_file()
        elif choice == "done":
            run_schema()
            break
        else:
            print("Invalid choice. Please choose again.")

        print_schema()


if __name__ == "__main__":
    schema_repeat_count = 1
    print("\033[1mMulti-Pass Disk Preparation Script\033[0m")
    main_menu()
