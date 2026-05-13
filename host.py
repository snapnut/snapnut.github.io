from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()
rooty = "./dist"

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
