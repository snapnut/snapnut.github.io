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
from typing import Any, Dict, Optional

# ============================================================================
# CONFIG & CONSTANTS
# ============================================================================
app = FastAPI()
rooty = "./dist"
start_time = time.time()

# Guestbook rate limiting
GUESTBOOK_RATE_WINDOW = 24 * 3600  # 24 hours
GUESTBOOK_MAX_PER_WINDOW = 50      # max submissions per IP per window
GUESTBOOK_MIN_INTERVAL = 15        # seconds between submissions
GUESTBOOK_MAX_MESSAGE_CHARS = 100

# Initialize numeric guestbook ID counter from existing entries
def _init_guestbook_counter():
    max_id = 0
    try:
        with open("guestbook.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    entry_id = obj.get("id")
                    if isinstance(entry_id, int) and entry_id > max_id:
                        max_id = entry_id
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return max_id

_guestbook_counter = _init_guestbook_counter()
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
        """Remove common leading whitespace, handling first-line edge cases."""
        lines = text.split('\n')
        if not lines:
            return text
        
        min_indent = float('inf')
        for line in lines[1:]:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)
        
        if min_indent == float('inf') or min_indent == 0:
            return text
        
        dedented_lines = [lines[0]]
        for line in lines[1:]:
            if line.strip():
                dedented_lines.append(line[min_indent:] if len(line) > min_indent else line.lstrip())
            else:
                dedented_lines.append('')
        
        return '\n'.join(dedented_lines)

    @staticmethod
    def _python_literal(value: str) -> str:
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
                'source': template,  # Store for error reporting
            }

        render_context = self._build_context(request, context)
        try:
            exec(code_obj, render_context)
        except Exception as e:
            render_context['__error_context'] = {
                'template_source': self._cache[file_path]['source'],
            }
            raise
        
        return await render_context['__render']()

    def _build_context(self, request: Request, context: Dict[str, Any]) -> Dict[str, Any]:
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
            self._append_segment(lines, template[pos:script_match.start()])
            lines.append(f'    output.append({self._python_literal(script_match.group(1))})')
            self._append_segment(lines, script_match.group(2))
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
                for raw_line in raw_text.splitlines(keepends=True):
                    lines.append(f'    output.append({self._python_literal(raw_line)})')

            expr_block = match.group(1)
            code_block = match.group(2)

            if expr_block is not None:
                expression = expr_block.strip()
                lines.append(f'    output.append(str({expression}))')
            elif code_block is not None:
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

# ============================================================================
# ERROR HANDLING & FORMATTING
# ============================================================================
def format_template_error(file_path: str, template_source: Optional[str], exc_info: str) -> str:
    """Format template rendering errors with helpful context."""
    lines = [
        "\n" + "="*80,
        "PYHP TEMPLATE RENDERING ERROR",
        "="*80,
        f"File: {file_path}\n",
        "Error traceback:",
        exc_info,
    ]
    
    # Try to extract the problematic code block from traceback
    if template_source:
        # Look for line numbers in the traceback
        line_matches = re.findall(r'line (\d+)', exc_info)
        if line_matches:
            lines.append("\nContext from template:")
            template_lines = template_source.split('\n')
            for line_num_str in set(line_matches):
                try:
                    line_num = int(line_num_str)
                    start = max(0, line_num - 3)
                    end = min(len(template_lines), line_num + 2)
                    lines.append(f"\n  Lines {start+1}-{end}:")
                    for i in range(start, end):
                        marker = ">>> " if i == line_num - 1 else "    "
                        lines.append(f"  {marker}{i+1}: {template_lines[i][:100]}")
                except (ValueError, IndexError):
                    pass
    
    lines.append("\n" + "="*80 + "\n")
    return '\n'.join(lines)

def json_response(ok: bool, **kwargs) -> Response:
    """Helper to create consistent JSON API responses."""
    data = {"ok": ok, **kwargs}
    status = 200 if ok else kwargs.get("status_code", 400)
    return Response(
        content=json.dumps(data),
        media_type="application/json",
        status_code=status
    )

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
        # Render template and minify output
        rendered_html = await engine.render_file(full_path, request, {})
        return Response(content=minify_html.minify(
            rendered_html,
            minify_js=True,
            minify_css=True,
            remove_processing_instructions=True
        ), media_type="text/html")
    except Exception as e:
        template_source = None
        if full_path in engine._cache:
            template_source = engine._cache[full_path].get('source')
        
        exc_info = traceback.format_exc()
        error_msg = format_template_error(full_path, template_source, exc_info)
        print(error_msg)
        
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



# ============================================================================
# GUESTBOOK STORAGE & RATE LIMITING
# ============================================================================
ip_submissions = {}

@app.post("/api/submit-guestbook")
async def submit_guestbook(request: Request):
    """Submit a message to the guestbook with rate limiting."""
    ip = getattr(request.client, "host", "unknown") or "unknown"
    now = int(time.time())

    # Cleanup and validate submission frequency
    times = ip_submissions.get(ip, [])
    times = [t for t in times if now - t < GUESTBOOK_RATE_WINDOW]
    ip_submissions[ip] = times

    if times and (now - times[-1]) < GUESTBOOK_MIN_INTERVAL:
        return json_response(False, error="too_many_requests", status_code=429, retry_after=GUESTBOOK_MIN_INTERVAL)

    if len(times) >= GUESTBOOK_MAX_PER_WINDOW:
        return json_response(False, error="rate_limit_exceeded", status_code=429)

    # Extract and validate message
    try:
        data = await request.json()
        msg = data.get("message", "").strip()
    except Exception:
        form = await request.form()
        msg = form.get("message", "").strip()

    if not msg:
        return json_response(False, error="empty", status_code=400)

    if len(msg) > GUESTBOOK_MAX_MESSAGE_CHARS:
        msg = msg[:GUESTBOOK_MAX_MESSAGE_CHARS]

    # Reject obvious spam
    if len(re.findall(r'https?://', msg)) > 2:
        return json_response(False, error="spam_detected", status_code=400)

    # Sanitize and save
    safe_msg = _html.escape(msg)
    global _guestbook_counter
    _guestbook_counter += 1
    entry = {"id": _guestbook_counter, "ts": now, "msg": safe_msg}

    try:
        with open("guestbook.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Guestbook write error: {e}")
        return json_response(False, error="write_failed", status_code=500)

    times.append(now)
    return json_response(True, ts=now, saved=msg, id=_guestbook_counter)

app.mount("/", StaticFiles(directory=rooty), name="static")
app.add_middleware(GZipMiddleware, minimum_size=500)

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(client_addr)s - '%(request_line)s' %(status_code)s"
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=LOGGING_CONFIG)
