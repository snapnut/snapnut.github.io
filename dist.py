import os
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

# --- CONFIGURATION ---
SOURCE_DIR = "./public"
BUILD_DIR = "dist"

# --- TAG REPLACEMENT LOGIC ---
state = {'count': 0}

def get_count():
    state['count'] += 1
    return str(state['count'])

# Static time for the entire run
now = datetime.now(timezone.utc)
syms = {
    'DATE':    lambda: now.strftime('%Y-%m-%d'),
    'TIME':    lambda: now.strftime('%H:%M:%S UTC'),
    'COUNTER': get_count,
}

TAG_RE = re.compile(r'\{\{(.*?)\}\}')

def replace_tag(match):
    tag_name = match.group(1)
    if tag_name in syms:
        return syms[tag_name]()
    return match.group(0)

def process_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Replace Tags
        new_content = TAG_RE.sub(replace_tag, content)

        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Processed: {path}")
    except Exception as e:
        print(f"Error processing {path}: {e}")

# --- SIZE CHECKING LOGIC ---
def is_binary(file_path):
    # does it have a null byte
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except Exception:
        return True

def check_distribution_size():
    total_bytes = 0
    print("Site size")
    print()
    print(f"{'Bytes':<12} | {'File Path'}")
    print()

    # Walk through the generated build directory
    for path in Path(BUILD_DIR).rglob('*'):
        if path.is_file() and not is_binary(path):
            try:
                file_size = path.stat().st_size
                total_bytes += file_size
                print(f"{file_size:<12,} | {path}")
            except Exception as e:
                print(f"Error reading size for {path}: {e}")

    print()
    print(f"Site bytes: {total_bytes:,} bytes\n")

# --- MAIN EXECUTION ---
def main():
    # 1. Clean and Setup Dist
    print(f"Cleaning")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    
    print(f"Syncing")
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory '{SOURCE_DIR}' not found.")
        sys.exit(-1)
    
    shutil.copytree(SOURCE_DIR, BUILD_DIR)

    # 2. Process HTML Files
    print("Processing")
    for root, _, files in os.walk(BUILD_DIR):
        for file in files:
            if file.endswith('.html') or file.endswith('.js') or file.endswith('.css'):
                process_file(os.path.join(root, file))

    check_distribution_size()
    print("Ready for distribution!")

if __name__ == "__main__":
    main()
