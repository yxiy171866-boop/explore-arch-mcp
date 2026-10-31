#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone Web Application for Architecture Companion
Runs a FastAPI server hosting the REST API and the interactive HTML canvas.
"""

from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import service

app = FastAPI(title="Architecture Companion Web UI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class SwitchDisplayRequest(BaseModel):
    project_id: str


class AddNoteRequest(BaseModel):
    project_id: str
    author: str
    content: str
    color: Optional[str] = None


class ToggleFavoriteRequest(BaseModel):
    project_id: str
    favorited_by: Optional[str] = "User"
    structured_title: Optional[str] = None
    note: Optional[str] = None
    tags: Optional[List[str]] = None


class RecommendRequest(BaseModel):
    project_id: str
    user_note: Optional[str] = None


@app.on_event("startup")
def on_startup():
    service.init_db()


@app.get("/", response_class=HTMLResponse)
def get_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return "<h1>Architecture Companion Frontend Not Found</h1><p>Please place index.html in the static directory.</p>"


@app.get("/api/architecture/current")
def read_current():
    try:
        p = service.get_current_project()
        if not p:
            raise HTTPException(status_code=404, detail="No project found")
        notes = service.get_notes(p["id"])
        is_fav = service.is_favorite(p["id"])
        return {
            "status": "success",
            "project": p,
            "notes": notes,
            "is_favorite": is_fav,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/architecture/current")
def update_current(req: SwitchDisplayRequest):
    try:
        service.set_current_project(req.project_id)
        p = service.get_current_project()
        if not p:
            raise HTTPException(status_code=404, detail="No project found")
        notes = service.get_notes(p["id"])
        is_fav = service.is_favorite(p["id"])
        return {
            "status": "success",
            "project": p,
            "notes": notes,
            "is_favorite": is_fav,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/random")
def read_random():
    try:
        p = service.get_random_archdaily_project()
        if not p:
            raise HTTPException(status_code=404, detail="No projects found")
        is_fav = service.is_favorite(p["id"])
        return {
            "status": "success",
            "project": p,
            "is_favorite": is_fav,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/search")
def search_projects(q: str = Query(...)):
    try:
        results = service.search_archdaily(q)
        return {"status": "success", "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/notes")
def read_notes(project_id: str = Query(...)):
    try:
        notes = service.get_notes(project_id)
        return {"status": "success", "notes": notes}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/architecture/notes")
def create_note(req: AddNoteRequest):
    try:
        note = service.add_note(
            project_id=req.project_id,
            author=req.author,
            content=req.content,
            color=req.color,
        )
        return {"status": "success", "note": note}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/api/architecture/notes/{note_id}")
def remove_note(note_id: int):
    try:
        ok = service.delete_note(note_id)
        if not ok:
            raise HTTPException(status_code=404, detail="便签不存在或已被删除")
        return {"status": "success", "message": "Note deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/architecture/favorite")
def change_favorite(req: ToggleFavoriteRequest):
    try:
        res = service.toggle_favorite(
            project_id=req.project_id,
            favorited_by=req.favorited_by or "User",
            structured_title=req.structured_title,
            note=req.note,
            tags=req.tags,
        )
        return {"status": "success", **res}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/favorites")
def read_favorites(tag: Optional[str] = Query(None), q: Optional[str] = Query(None)):
    try:
        favs = service.list_favorites(tag=tag, query=q)
        return {"status": "success", "favorites": favs}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/favorite-tags")
def read_favorite_tags():
    try:
        tags = service.get_favorite_tags()
        return {"status": "success", "tags": tags}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/history")
def read_history(limit: int = Query(50)):
    try:
        items = service.list_history(limit=limit)
        return {"status": "success", "history": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/carousel")
def read_carousel():
    try:
        items = service.list_carousel_projects()
        return {"status": "success", "items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/architecture/recommend")
def send_recommendation(req: RecommendRequest):
    try:
        rec = service.recommend_to_ai(req.project_id, req.user_note)
        return {"status": "success", "recommendation": rec}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/architecture/ai-shares")
@app.get("/api/architecture/daemon-shares")
def read_ai_shares(unread_only: bool = Query(True)):
    try:
        shares = service.get_ai_shares(unread_only=unread_only)
        return {"status": "success", "shares": shares}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/architecture/ai-shares/mark-all-read")
@app.post("/api/architecture/daemon-shares/mark-all-read")
def mark_all_shares_read():
    try:
        service.mark_all_ai_shares_read()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    print("Architecture Companion Web App starting at http://127.0.0.1:8000")
    uvicorn.run("app:app", host="127.0.0.1", port=8000)

