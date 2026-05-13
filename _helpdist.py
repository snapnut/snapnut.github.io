import sys
import os
import re
from datetime import datetime

state = {'count': 0}

def get_count():
    state['count'] += 1
    return str(state['count'])

now = datetime.now()
syms = {
    'DATE':    lambda: now.strftime('%Y-%m-%d'),
    'TIME':    lambda: now.strftime('%H:%M:%S UTC'),
    'COUNTER': get_count,
}

TAG_RE = re.compile(r'\{\{(.*?)\}\}')

def replace_tag(match):
    tag_name = match.group(1) # between the open symbols
    if tag_name in syms:
        return syms[tag_name]()
    
    return match.group(0) # do nothin if not found

def process_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content = TAG_RE.sub(replace_tag, content)

        if new_content != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Processed: {path}")
    except Exception as e:
        print(f"Error {path}: {e}")

if len(sys.argv) != 2:
    print("Usage: pass a DIST directory as an argument.")
    sys.exit(-1)

distfs = sys.argv[1]

if not os.path.isdir(distfs):
    print(f"{distfs} is not a directory.")
    sys.exit(-1)

for root, _, files in os.walk(distfs):
    for file in files:
        if file.endswith('.html'):
            process_file(os.path.join(root, file))