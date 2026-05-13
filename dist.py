import os
import re
import shutil
import sys
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

def process_file(path, minify=False):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 1. Replace Tags
        new_content = TAG_RE.sub(replace_tag, content)

        # 2. Minify (Optional - see implementation below)
        if minify:
            new_content = minify_html_logic(new_content)

        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Processed: {path}")
    except Exception as e:
        print(f"Error processing {path}: {e}")

def minify_html_logic(html):
    # Remove comments
    html = re.sub(r'', '', html, flags=re.DOTALL)
    # Collapse whitespace/newlines between tags
    html = re.sub(r'>\s+<', '><', html)
    # Remove leading/trailing whitespace
    return html.strip()

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
            if file.endswith('.html'):
                process_file(os.path.join(root, file), minify=True)

    print("Ready for distribution!")

if __name__ == "__main__":
    main()
