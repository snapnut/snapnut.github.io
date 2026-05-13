import os
import time
import re
import asyncio
import textwrap
import traceback
import mimetypes
from fastapi import FastAPI, Response, Request, HTTPException
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
        runtime_context = globals().copy()
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
            lines.append(f'    output.append({script_match.group(1)!r})')
            lines.append(f'    output.append({script_match.group(2)!r})')
            lines.append(f'    output.append({script_match.group(3)!r})')
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
                lines.append(f'    output.append({raw_text!r})')

            expr_block = match.group(1)
            code_block = match.group(2)

            if expr_block is not None:
                expression = expr_block.strip()
                lines.append(f'    output.append(str({expression}))')
            elif code_block is not None:
                block_text = textwrap.dedent(code_block.strip('\n'))
                for code_line in block_text.splitlines():
                    lines.append(f'    {code_line}')

            last_pos = match.end()

        remaining = segment[last_pos:]
        if remaining:
            lines.append(f'    output.append({remaining!r})')

engine = PyHPEngine()

async def getLocal(file_name: str, request: Request) -> Response:
    full_path = os.path.abspath(os.path.normpath(os.path.join(rooty, file_name)))
    if not full_path.startswith(os.path.abspath(rooty)):
        return Response(content="<h1>403 Forbidden</h1>", status_code=403, media_type="text/html")

    if not os.path.isfile(full_path):
        return Response(content="<h1>404 Not Found</h1>", status_code=404, media_type="text/html")

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
        rendered_html = await engine.render_file(full_path, request, {})
        return Response(content=rendered_html, media_type="text/html")
    except Exception as e:
        print("\n--- PYHP RENDER ERROR ---")
        print(f"File: {full_path}")
        print(f"Query: {request.query_params}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print("--------------------------\n")
        return Response(
            content="<h1>500 Internal Server Error</h1><p>Something went wrong processing the page :(</p>",
            status_code=500,
            media_type="text/html"
        )

# --- ROUTES ---

@app.get("/api/stats")
async def get_stats():
    uptime_seconds = int(time.time() - start_time)
    return {
        "status": f"System: {mySysname} | Uptime: {uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m | Temp: {get_cpu_temp()}",
    }

get_inc = 0
@app.get("/api/inc")
async def WS_get_inc():
    global get_inc
    get_inc += 1
    return {"inc": get_inc}

@app.get("/")
async def WS_root(request: Request):
    return await getLocal("index.html", request)

# NOTE: App mounting should remain at the bottom so it doesn't hijack API routes, 
# but our catch-all above will now handle all routing requests.
app.mount("/", StaticFiles(directory=rooty), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
