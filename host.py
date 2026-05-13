import os
import time
import re
import io
import asyncio
import traceback
from contextlib import redirect_stdout
from fastapi import FastAPI, Response, Request
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
    def __init__(self):
        # Regex for <? blocks ?> and <?= expressions =?>
        self.regex = re.compile(r'<\?(.*?)\?>|<?= (.*?) =?>', re.DOTALL)

    async def render_file(self, file_path: str, request: Request, context: Dict[str, Any]) -> str:
        with open(file_path, 'r') as f:
            template = f.read()
        
        context['query_params'] = dict(request.query_params)
        context['path'] = request.url.path
        
        chunks = []
        last_pos = 0
        tasks = []

        for match in self.regex.finditer(template):
            chunks.append(template[last_pos:match.start()])
            
            code_block = match.group(1)
            expr_block = match.group(2)

            if code_block:
                tasks.append(self._run_block(code_block.strip(), context))
            else:
                tasks.append(self._run_eval(expr_block.strip(), context))
            
            chunks.append(None) 
            last_pos = match.end()

        chunks.append(template[last_pos:])
        
		# parallelism is my forte
        results = await asyncio.gather(*tasks)

        result_idx = 0
        final_output = []
        for chunk in chunks:
            if chunk is None:
                final_output.append(str(results[result_idx]))
                result_idx += 1
            else:
                final_output.append(chunk)

        return "".join(final_output)

    async def _run_block(self, code: str, context: Dict[str, Any]) -> str:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                exec(code, context)
            return buffer.getvalue()
        except Exception:
            raise

    async def _run_eval(self, expr: str, context: Dict[str, Any]) -> str:
        try:
            return eval(expr, context)
        except Exception:
            raise

engine = PyHPEngine()

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
    try:
        context = globals().copy()
        
        file_path = os.path.join(rooty, "index.html")
        rendered_html = await engine.render_file(file_path, request, context)
        return Response(content=rendered_html, media_type="text/html")

    except Exception as e:
        print("\n--- PYHP RENDER ERROR ---")
        print(f"File: {os.path.join(rooty, 'index.html')}")
        print(f"Query: {request.query_params}")
        print(f"Traceback:\n{traceback.format_exc()}")
        print("--------------------------\n")
        
        return Response(
            content="<h1>500 Internal Server Error</h1><p>Something went wrong processing the page :(</p>",
            status_code=500,
            media_type="text/html"
        )

app.mount("/", StaticFiles(directory=rooty), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
