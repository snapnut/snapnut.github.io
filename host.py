from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import time

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
	get_inc+=1
	return {"inc": get_inc}

@app.get("/")
async def WS_root():
	return FileResponse(rooty+"/index.html")

app.mount("/", StaticFiles(directory=rooty), name="static")

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="127.0.0.1", port=8000)
