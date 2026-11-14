"""Offline localhost FastAPI application for the BYU AI Day game."""
from __future__ import annotations
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from engine import GameEngine, read_catalog, MAX_STATIC_OBJECTS, MAX_PEDESTRIANS

BASE = Path(__file__).resolve().parent
app = FastAPI(title='BEAT THE HUMANOID: Human vs AI', docs_url=None, redoc_url=None)
engine = GameEngine()
app.mount('/static', StaticFiles(directory=BASE/'static'), name='static')

class ValidationRequest(BaseModel):
    maze_id: str
    objects: list[list[int]] = Field(default_factory=list)
    pedestrians: list[list[int]] = Field(default_factory=list)

class ChallengeRequest(ValidationRequest):
    strategy: str

@app.get('/')
def home():
    return FileResponse(BASE/'static'/'index.html')

@app.get('/api/catalog')
def catalog():
    return {'mazes': [{k:m[k] for k in ('id','mechanism','candidate_index','width','height','start','goal','wall_rows')}
                      for m in engine.catalog['mazes']],
            'max_static_objects': MAX_STATIC_OBJECTS, 'max_pedestrians': MAX_PEDESTRIANS,
            'strategies': ['periodic','age','uncertainty'],
            'catalog_sha256': 'fe3c41bf93c6694ddbfe9629e4bb333113ecf57fc9b4f615a9570d1aaafbc2d2'}

@app.post('/api/validate')
def validate(request: ValidationRequest):
    return engine.validate(request.maze_id, request.objects, request.pedestrians)

@app.post('/api/challenge')
def challenge(request: ChallengeRequest):
    return engine.start(request.model_dump())

@app.get('/api/state')
def state():
    return engine.snapshot()

@app.post('/api/reset')
def reset():
    result=engine.reset()
    return JSONResponse(result, status_code=200 if result['ok'] else 409)

@app.websocket('/ws')
async def websocket_updates(websocket: WebSocket):
    await websocket.accept()
    try:
        last = None
        last_status = None
        while True:
            snapshot = engine.snapshot()
            seq = snapshot.get('frame_seq')
            status = snapshot.get('status')
            if seq != last or status != last_status:
                await websocket.send_json(snapshot)
                last = seq
                last_status = status
            await asyncio.sleep(0.06)
    except WebSocketDisconnect:
        return

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='127.0.0.1', port=8765, access_log=False)
