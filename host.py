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
    TEMPLATE_TAG_RE = re.compile(r'<\?=\s*(.*?)\s*\?>|<\?(?!\=)(.*?)\?>', re.DOTALL)
    SCRIPT_BLOCK_RE = re.compile(r'(?is)(<script\b[^>]*>)(.*?)(</script>)')

    def __init__(self):
        self._cache: Dict[str, Any] = {}

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
                # Keep the original code block line structure so line numbers
                # align with the template. Dedent to normalize indentation
                # but do not strip leading/trailing newlines which affect
                # line numbering.
                block_text = textwrap.dedent(code_block)
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

    # limit length
    if len(msg) > 2000:
        msg = msg[:2000]

    # heuristic: reject excessive links
    if len(re.findall(r'https?://', msg)) > 2:
        return Response(content=json.dumps({"ok": False, "error": "spam_detected"}), media_type="application/json", status_code=400)

    # sanitize to prevent XSS
    safe_msg = _html.escape(msg)
    ts = now
    entry = {"ts": ts, "msg": safe_msg}

    try:
        with open("guestbook.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed writing guestbook: {e}")
        return Response(content=json.dumps({"ok": False, "error": "write_failed"}), media_type="application/json", status_code=500)

    # Persist the submission timestamp for rate limiting
    times.append(now)
    ip_submissions[ip] = times

    return Response(content=json.dumps({"ok": True, "ts": ts}), media_type="application/json")

app.mount("/", StaticFiles(directory=rooty), name="static")
app.add_middleware(GZipMiddleware, minimum_size=500)

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=LOGGING_CONFIG)
