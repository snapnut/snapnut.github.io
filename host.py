import os
import time
import re
import json
import asyncio
import textwrap
import traceback
import mimetypes
import minify_html
import html as _html
import uuid
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Any, Dict

app = FastAPI()
rooty = "./dist"

start_time = time.time()
mySysname = os.uname().sysname

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = f.read()
            return f"{int(temp) / 1000}°C"
    except:
        return "N/A"

class PyHPEngine:
    TEMPLATE_TAG_RE = re.compile(r'<!--pyinl\s*(.*?)\s*-->|<!--py(?!inl)\s*(.*?)\s*-->', re.DOTALL)
    SCRIPT_BLOCK_RE = re.compile(r'(?is)(<script\b[^>]*>)(.*?)(</script>)', re.DOTALL)

    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def _smart_dedent(self, text: str) -> str:
        """
        Remove common leading whitespace from text, handling cases where the first
        line may have no indentation (e.g., when code starts on the same line as the tag).
        For the first line, use it as-is. For subsequent lines, find the common indentation
        and remove it.
        """
        lines = text.split('\n')
        if not lines:
            return text
        
        # Find minimum indentation across lines 2+ (non-empty lines)
        min_indent = float('inf')
        for line in lines[1:]:  # Skip first line
            if line.strip():  # Non-empty line
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)
        
        if min_indent == float('inf') or min_indent == 0:
            # No indentation to remove from lines 2+, return as-is
            return text
        
        # Remove the minimum indentation from all lines except the first
        dedented_lines = [lines[0]]  # Keep first line as-is
        for line in lines[1:]:
            if line.strip():  # Non-empty
                dedented_lines.append(line[min_indent:] if len(line) > min_indent else line.lstrip())
            else:  # Empty or whitespace-only
                dedented_lines.append('')
        
        return '\n'.join(dedented_lines)

    @staticmethod
    def _python_literal(value: str) -> str:
        # JSON string quoting is safe for arbitrary text and avoids edge-case quote injection.
        return json.dumps(value, ensure_ascii=False)

    async def render_file(self, file_path: str, request: Request, context: Dict[str, Any]) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            template = f.read()

        file_path = os.path.abspath(file_path)
        mtime = os.path.getmtime(file_path)
        cache_entry = self._cache.get(file_path)

        if cache_entry and cache_entry['mtime'] == mtime:
            code_obj = cache_entry['code_obj']
        else:
            code_obj = self._compile_template(template, file_path)
            self._cache[file_path] = {
                'mtime': mtime,
                'code_obj': code_obj,
            }

        render_context = self._build_context(request, context)
        exec(code_obj, render_context)
        return await render_context['__render']()

    def _build_context(self, request: Request, context: Dict[str, Any]) -> Dict[str, Any]:
        # Preserve module globals so helpers defined at the top of host.py
        # and imported utilities remain available inside templates.
        runtime_context = globals().copy()
        runtime_context['request'] = request
        runtime_context.update(context)
        return runtime_context

    def _compile_template(self, template: str, file_path: str):
        lines = [
            'async def __render():',
            '    output = []',
            '    def write(*values, sep=" ", end="\\n"):',
            '        output.append(sep.join(str(v) for v in values) + end)',
            '    print = write',
        ]

        pos = 0
        for script_match in self.SCRIPT_BLOCK_RE.finditer(template):
            # 1. Process template tags in the HTML BEFORE the script block
            self._append_segment(lines, template[pos:script_match.start()])
            
            # 2. Append the literal opening <script> tag
            lines.append(f'    output.append({self._python_literal(script_match.group(1))})')
            
            # 3. FIX: Process template tags INSIDE the script block content
            self._append_segment(lines, script_match.group(2))
            
            # 4. Append the literal closing </script> tag
            lines.append(f'    output.append({self._python_literal(script_match.group(3))})')
            pos = script_match.end()

        self._append_segment(lines, template[pos:])
        lines.append('    return "".join(output)')

        source = '\n'.join(lines)
        return compile(source, file_path, 'exec')

    def _append_segment(self, lines: list, segment: str) -> None:
        last_pos = 0
        for match in self.TEMPLATE_TAG_RE.finditer(segment):
            raw_text = segment[last_pos:match.start()]
            if raw_text:
                # Preserve original line counts so Python tracebacks map to
                # the template file lines. Split with keepends to retain
                # newline characters and emit one source line per template line.
                for raw_line in raw_text.splitlines(keepends=True):
                    lines.append(f'    output.append({self._python_literal(raw_line)})')

            expr_block = match.group(1)
            code_block = match.group(2)

            if expr_block is not None:
                expression = expr_block.strip()
                lines.append(f'    output.append(str({expression}))')
            elif code_block is not None:
                # Strip leading/trailing whitespace from the block, then dedent
                block_text = code_block.strip()
                block_text = self._smart_dedent(block_text)
                for code_line in block_text.splitlines():
                    lines.append(f'    {code_line}')

            last_pos = match.end()

        remaining = segment[last_pos:]
        if remaining:
            for raw_line in remaining.splitlines(keepends=True):
                lines.append(f'    output.append({self._python_literal(raw_line)})')

engine = PyHPEngine()

async def getLocal(file_name: str, request: Request) -> Response:
    full_path = os.path.abspath(os.path.normpath(os.path.join(rooty, file_name)))

    # Security via obscurity! 404s for both
    if not full_path.startswith(os.path.abspath(rooty)):
        raise HTTPException(status_code=404)

    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404)

    _, ext = os.path.splitext(full_path)
    if ext.lower() != ".html":
        try:
            with open(full_path, 'rb') as f:
                file_content = f.read()
            mime_type, _ = mimetypes.guess_type(full_path)
            return Response(content=file_content, media_type=mime_type or "application/octet-stream")
        except Exception as e:
            print(f"Error serving static file {full_path}: {e}")
            return Response(content="<h1>500 Internal Server Error</h1>", status_code=500, media_type="text/html")

    try:
        # When the file is rendered, it should be just only VALID HTML. That means no processing instructions!!!
        # Ideally the minifier should run in dist.py, but I catch all edge cases!!
        rendered_html = await engine.render_file(full_path, request, {})
        return Response(content=minify_html.minify(
            rendered_html,
            minify_js=True,
            minify_css=True,
            remove_processing_instructions=True
        ), media_type="text/html")
    except Exception as e:
        print("\n--- PYHP RENDER ERROR ---")
        print(f"File: {full_path}")
        print(f"Query: {request.query_params}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print("--------------------------\n")
        return Response(
            content="<h1>500 Internal Server Error</h1><p>Something went wrong processing the page :3</p><hr><small><i>PyHP</i></small>",
            status_code=500,
            media_type="text/html"
        )

# --- ROUTES ---

@app.exception_handler(404)
async def fourOhFour(request: Request, exception: HTTPException):
    return Response(
        content="<h1>404 Not Found</h1><p>The requested resource was not found.</p><hr><a href='/'>Go home!</a>",
        status_code=404,
        media_type="text/html"
    )

async def get_stats():
    uptime_seconds = int(time.time() - start_time)
    return {
        "status": f"System: {mySysname} | Uptime: {uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m | Temp: {get_cpu_temp()}",
    }

@app.get("/")
async def WS_root(request: Request):
    return await getLocal("index.html", request)


# Guestbook rate-limited API
# Basic in-memory rate limiting per IP
ip_submissions = {}
RATE_WINDOW = 24 * 3600  # 24 hours
MAX_PER_WINDOW = 50      # max submissions per IP per window
MIN_INTERVAL = 15        # seconds between submissions
# Message length limit (characters)
MAX_MESSAGE_CHARS = 100

@app.post("/api/submit-guestbook")
async def submit_guestbook(request: Request):
    ip = getattr(request.client, "host", "unknown") or "unknown"
    now = int(time.time())

    # Cleanup old timestamps for this IP
    times = ip_submissions.get(ip, [])
    times = [t for t in times if now - t < RATE_WINDOW]

    if times and (now - times[-1]) < MIN_INTERVAL:
        return Response(content=json.dumps({"ok": False, "error": "too_many_requests", "retry_after": MIN_INTERVAL}), media_type="application/json", status_code=429)

    if len(times) >= MAX_PER_WINDOW:
        return Response(content=json.dumps({"ok": False, "error": "rate_limit_exceeded"}), media_type="application/json", status_code=429)

    # Read message (JSON preferred, fallback to form)
    try:
        data = await request.json()
        msg = data.get("message", "").strip()
    except Exception:
        form = await request.form()
        msg = form.get("message", "").strip()

    if not msg:
        return Response(content=json.dumps({"ok": False, "error": "empty"}), media_type="application/json", status_code=400)

    # enforce length limit by truncating (characters, UTF-8 safe since Python strings are Unicode)
    if len(msg) > MAX_MESSAGE_CHARS:
        msg = msg[:MAX_MESSAGE_CHARS]

    # heuristic: reject excessive links
    if len(re.findall(r'https?://', msg)) > 2:
        return Response(content=json.dumps({"ok": False, "error": "spam_detected"}), media_type="application/json", status_code=400)

    # sanitize to prevent XSS
    safe_msg = _html.escape(msg)
    ts = now
    # Generate a server-side unique ID (UUID4 string, 36 chars)
    def _generate_unique_id():
        # Attempt a few times to avoid improbable collisions by scanning existing IDs
        for _ in range(5):
            cid = str(uuid.uuid4())
            exists = False
            try:
                with open("guestbook.jsonl", "r", encoding="utf-8") as rf:
                    for line in rf:
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if obj.get("id") == cid:
                            exists = True
                            break
            except FileNotFoundError:
                pass
            if not exists:
                return cid
        # Fallback (extremely unlikely to collide)
        return str(uuid.uuid4())

    cid = _generate_unique_id()
    entry = {"id": cid, "ts": ts, "msg": safe_msg}

    try:
        with open("guestbook.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed writing guestbook: {e}")
        return Response(content=json.dumps({"ok": False, "error": "write_failed"}), media_type="application/json", status_code=500)

    # Persist the submission timestamp for rate limiting
    times.append(now)
    ip_submissions[ip] = times

    # Return the saved (possibly truncated) message and server-generated id
    return Response(content=json.dumps({"ok": True, "ts": ts, "saved": msg, "id": cid}), media_type="application/json")

app.mount("/", StaticFiles(directory=rooty), name="static")
app.add_middleware(GZipMiddleware, minimum_size=500)

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=LOGGING_CONFIG)
