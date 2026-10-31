#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Architecture Service
Data persistence, ArchDaily integration, translation, sticky notes, and favorites management.
"""

import json
import os
import random
import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "architecture.db"
IMAGE_CACHE_DIR = DATA_DIR / "images_cache"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def translate_to_zh(text: str) -> str:
    """自动将英文简介翻译为优美中文"""
    if not text or not text.strip():
        return ""
    # 如果已经主要是中文，直接返回
    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    if zh_chars > len(text) * 0.3:
        return text.strip()

    try:
        clean = text[:1500].strip()
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=zh-CN&dt=t&q=" + urllib.parse.quote(clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join([item[0] for item in data[0] if item and item[0]])
            return translated.strip() if translated else text
    except Exception as exc:
        print("[Architecture] Translation to zh fallback:", exc)
        return text


def translate_to_en(text: str) -> str:
    """自动将中文搜索词翻译为精准英文"""
    if not text or not text.strip():
        return ""
    # 如果没有中文字符，直接返回
    if not re.search(r'[\u4e00-\u9fff]', text):
        return text.strip()

    try:
        clean = text[:300].strip()
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=" + urllib.parse.quote(clean)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join([item[0] for item in data[0] if item and item[0]])
            return translated.strip() if translated else text
    except Exception as exc:
        print("[Architecture] Translation to en fallback:", exc)
        return text



def download_cover_image(project_id: str, image_url: str) -> Optional[str]:
    """下载建筑封面大图到本地缓存，供多模态视觉模型（如 Claude Opus）直接读取。"""
    if not image_url or not image_url.strip():
        return None
    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', project_id)
        local_path = IMAGE_CACHE_DIR / f"{safe_id}.jpg"
        if local_path.exists() and local_path.stat().st_size > 1024:
            return str(local_path)

        parts = urllib.parse.urlsplit(image_url.strip())
        clean_url = urllib.parse.urlunsplit((
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path),
            urllib.parse.quote(parts.query, safe='=&?+:/-_'),
            parts.fragment
        ))

        req = urllib.request.Request(clean_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
            if len(content) > 500:
                with open(local_path, "wb") as f:
                    f.write(content)
                return str(local_path)
    except Exception as exc:
        print(f"[Architecture] Image cache download failed for {project_id}:", exc)
    return None


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            structured_title TEXT NOT NULL,
            architect TEXT,
            country TEXT,
            city TEXT,
            location TEXT,
            year TEXT,
            cover_image TEXT,
            images_json TEXT,
            description TEXT,
            description_zh TEXT,
            description_en TEXT,
            tags_json TEXT,
            source_url TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            color TEXT DEFAULT '#faf9f5',
            rotation REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            favorited_by TEXT NOT NULL,
            structured_title TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, favorited_by)
        );

        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            viewed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            user_note TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS daemon_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            is_read INTEGER DEFAULT 0
        );
        """)

        # Add description_zh / description_en / translation columns if missing
        cols = [c[1] for c in conn.execute("PRAGMA table_info(projects)").fetchall()]
        for col_name in [
            "description_zh", "description_en",
            "structured_title_zh", "structured_title_en",
            "title_zh", "title_en",
            "location_zh", "location_en"
        ]:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE projects ADD COLUMN {col_name} TEXT")

        fav_cols = [c[1] for c in conn.execute("PRAGMA table_info(favorites)").fetchall()]
        if "tags_json" not in fav_cols:
            conn.execute("ALTER TABLE favorites ADD COLUMN tags_json TEXT DEFAULT '[]'")

        conn.commit()

    # Pre-seed default project if empty
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if count == 0:
            _seed_default_project(conn)


def _seed_default_project(conn):
    now = datetime.now().isoformat()
    pid = "ad-church-of-the-light"
    title = "Church of the Light"
    structured_title = "[日本·大阪] 光之教堂 · Tadao Ando"
    architect = "Tadao Ando Architect & Associates"
    location = "Ibaraki, Osaka, Japan"
    country = "日本"
    city = "大阪"
    year = "1999"
    cover_image = "https://images.adsttc.com/media/images/5037/f3cd/28ba/0d59/9b00/064c/large_jpg/stringio.jpg?1414206110"
    images = [
        "https://images.adsttc.com/media/images/5037/f3cd/28ba/0d59/9b00/064c/large_jpg/stringio.jpg?1414206110",
        "https://images.adsttc.com/media/images/5037/f3e0/28ba/0d59/9b00/064f/large_jpg/stringio.jpg?1414206113",
        "https://images.adsttc.com/media/images/5037/f3bb/28ba/0d59/9b00/0649/large_jpg/stringio.jpg?1414206116",
        "https://images.adsttc.com/media/images/5037/f3d3/28ba/0d59/9b00/064d/large_jpg/stringio.jpg?1414206119",
    ]
    description_zh = (
        "安藤忠雄的代表作之一，位于大阪府茨木市。建筑由极具质感的清水混凝土墙体与一道在背墙上切开的十字形光隙组成。"
        "光与暗的张力、空间的静默与永恒，让这里成为现代建筑史上的神圣经典。"
    )
    description_en = (
        "The Church of the Light is the main chapel of the Ibaraki Kasugaoka Church. "
        "It was built in 1989, in the city of Ibaraki, Osaka Prefecture. Designed by Tadao Ando, "
        "the structure embraces Ando's philosophical framework about the contrast between light and solid concrete."
    )
    tags = ["宗教建筑", "清水混凝土", "光影艺术", "极简主义", "文化遗产"]
    url = "https://www.archdaily.com/101260/ad-classics-church-of-the-light-tadao-ando"

    conn.execute("""
    INSERT OR REPLACE INTO projects (
        id, title, structured_title, architect, country, city, location, year, cover_image, images_json,
        description, description_zh, description_en, tags_json, source_url, created_at,
        structured_title_zh, structured_title_en, title_zh, title_en, location_zh, location_en
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        pid, title, structured_title, architect, country, city, location, year, cover_image, json.dumps(images),
        description_zh, description_zh, description_en, json.dumps(tags), url, now,
        structured_title, structured_title, title, title, location, location
    ))
    conn.commit()


def _format_structured_title(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "未命名建筑").strip()
    if " / " in title:
        short_title = title.split(" / ")[0].strip()
    else:
        short_title = title

    offices = item.get("offices") or []
    if offices and isinstance(offices, list) and isinstance(offices[0], dict):
        architect = offices[0].get("name", "").strip()
    else:
        architect = str(item.get("architect") or "").strip()

    loc = str(item.get("location") or "").strip()
    country = str(item.get("country") or "").strip()
    city = str(item.get("city") or "").strip()

    if loc and (not country or not city):
        parts = [p.strip() for p in loc.split(",") if p.strip()]
        if len(parts) >= 2:
            city = city or parts[0]
            country = country or parts[-1]
        elif len(parts) == 1:
            country = country or parts[0]

    place = ""
    if country and city:
        place = f"{country}·{city}"
    elif country:
        place = country
    elif city:
        place = city
    else:
        place = "建筑漫游"

    arch_str = f" · {architect}" if architect else ""
    return f"[{place}] {short_title}{arch_str}"


def parse_archdaily_project(raw: Dict[str, Any]) -> Dict[str, Any]:
    doc_id = str(raw.get("document_id") or raw.get("id") or "")
    if not doc_id:
        url_part = str(raw.get("url") or "")
        match = re.search(r"/(\d+)/", url_part)
        doc_id = match.group(1) if match else f"ad-{random.randint(100000, 999999)}"

    title = str(raw.get("title") or "Untitled Architecture").strip()
    clean_title = title.split(" / ")[0].strip() if " / " in title else title

    offices = raw.get("offices") or []
    architect = offices[0].get("name", "").strip() if offices and isinstance(offices[0], dict) else ""

    loc = str(raw.get("location") or "").strip()
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    city = parts[0] if len(parts) >= 2 else ""
    country = parts[-1] if len(parts) >= 1 else ""

    year = str(raw.get("year") or "").strip()

    feat = raw.get("featured_images") or {}
    cover_image = feat.get("url_large") or feat.get("url_medium") or ""

    images = []
    if cover_image:
        images.append(cover_image)
    for m in (raw.get("miniatures") or []):
        if isinstance(m, dict):
            u = m.get("url_large") or m.get("url_medium")
            if u and u not in images:
                images.append(u)

    desc_raw = str(raw.get("meta_description") or raw.get("description") or "").strip()
    desc_zh = translate_to_zh(desc_raw)

    tags = [t.get("name") for t in (raw.get("tags") or []) if isinstance(t, dict) and t.get("name")]

    structured_title = _format_structured_title({
        "title": title,
        "architect": architect,
        "location": loc,
        "country": country,
        "city": city
    })

    # Chinese translations for full Chinese mode
    title_zh = translate_to_zh(clean_title)
    structured_title_zh = translate_to_zh(structured_title)
    location_zh = translate_to_zh(loc) if loc else ""

    return {
        "id": f"ad-{doc_id}",
        "title": clean_title,
        "title_zh": title_zh or clean_title,
        "title_en": clean_title,
        "full_title": title,
        "structured_title": structured_title,
        "structured_title_zh": structured_title_zh or structured_title,
        "structured_title_en": structured_title,
        "architect": architect,
        "country": country,
        "city": city,
        "location": loc,
        "location_zh": location_zh or loc,
        "location_en": loc,
        "year": year,
        "cover_image": cover_image,
        "images": images,
        "description": desc_zh or desc_raw,
        "description_zh": desc_zh or desc_raw,
        "description_en": desc_raw,
        "tags": tags,
        "source_url": raw.get("url", ""),
    }


def save_project_to_db(p: Dict[str, Any]):
    now = datetime.now().isoformat()
    # Cache cover image locally for AI multimodal vision support
    cover_url = p.get("cover_image", "")
    if cover_url:
        try:
            download_cover_image(p["id"], cover_url)
        except Exception:
            pass

    with get_db() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO projects (
            id, title, structured_title, architect, country, city, location, year, cover_image, images_json,
            description, description_zh, description_en, tags_json, source_url, created_at,
            structured_title_zh, structured_title_en, title_zh, title_en, location_zh, location_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"],
            p["title"],
            p["structured_title"],
            p.get("architect", ""),
            p.get("country", ""),
            p.get("city", ""),
            p.get("location", ""),
            p.get("year", ""),
            p.get("cover_image", ""),
            json.dumps(p.get("images", [])),
            p.get("description_zh") or p.get("description", ""),
            p.get("description_zh", ""),
            p.get("description_en", ""),
            json.dumps(p.get("tags", [])),
            p.get("source_url", ""),
            now,
            p.get("structured_title_zh") or p["structured_title"],
            p.get("structured_title_en") or p["structured_title"],
            p.get("title_zh") or p["title"],
            p.get("title_en") or p["title"],
            p.get("location_zh") or p.get("location", ""),
            p.get("location_en") or p.get("location", ""),
        ))
        conn.commit()


def search_archdaily(query: str, page: int = 1) -> List[Dict[str, Any]]:
    raw_q = (query or "").strip()
    if not raw_q:
        return []

    # 1. 先检索本地项目库中匹配的建筑（支持中文全称、建筑师、分类标签模糊匹配）
    local_results = []
    try:
        with get_db() as conn:
            like_q = f"%{raw_q}%"
            db_rows = conn.execute("""
                SELECT * FROM projects 
                WHERE title LIKE ? OR structured_title LIKE ? OR architect LIKE ? 
                   OR description_zh LIKE ? OR title_zh LIKE ? OR structured_title_zh LIKE ?
                   OR tags_json LIKE ?
                ORDER BY created_at DESC LIMIT 10
            """, (like_q, like_q, like_q, like_q, like_q, like_q, like_q)).fetchall()
            for r in db_rows:
                local_results.append(_row_to_project(r))
    except Exception as db_err:
        print("[Architecture] Local DB search warning:", db_err)

    # 2. ArchDaily 原生检索仅支持英文。若包含中文字符，先智能翻译为英文关键词（如 '安藤忠雄 光之教堂' -> 'Tadao Ando Church of Light'）
    target_q = raw_q
    if re.search(r'[\u4e00-\u9fff]', raw_q):
        translated_q = translate_to_en(raw_q)
        if translated_q:
            target_q = translated_q

    q = urllib.parse.quote(target_q)
    url = f"https://www.archdaily.com/search/api/v1/us/projects?q={q}&page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    api_results = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])[:4]
            for r in results:
                parsed = parse_archdaily_project(r)
                if parsed.get("cover_image"):
                    save_project_to_db(parsed)
                    api_results.append(parsed)
    except Exception as exc:
        print("[Architecture] ArchDaily search failed:", exc)

    # 3. 合并本地项目与在线搜索，去重
    seen = set()
    combined = []
    for item in local_results + api_results:
        pid = item.get("id")
        if pid and pid not in seen:
            seen.add(pid)
            combined.append(item)
    return combined


def get_random_archdaily_project() -> Optional[Dict[str, Any]]:
    random_page = random.randint(1, 150)
    url = f"https://www.archdaily.com/search/api/v1/us/projects?page={random_page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            valid_results = [r for r in results if r.get("featured_images") or r.get("miniatures")]
            if valid_results:
                pick = random.choice(valid_results)
                parsed = parse_archdaily_project(pick)
                save_project_to_db(parsed)
                return parsed
    except Exception as exc:
        print("[Architecture] ArchDaily random browse failed:", exc)

    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects ORDER BY RANDOM() LIMIT 1").fetchone()
        if row:
            return _row_to_project(row)
    return None


def _row_to_project(row: sqlite3.Row) -> Dict[str, Any]:
    keys = row.keys()
    safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', row["id"])
    cache_file = IMAGE_CACHE_DIR / f"{safe_id}.jpg"
    local_image_path = str(cache_file) if cache_file.exists() and cache_file.stat().st_size > 1024 else None

    return {
        "id": row["id"],
        "title": row["title"],
        "title_zh": row["title_zh"] if "title_zh" in keys and row["title_zh"] else row["title"],
        "title_en": row["title_en"] if "title_en" in keys and row["title_en"] else row["title"],
        "structured_title": row["structured_title"],
        "structured_title_zh": row["structured_title_zh"] if "structured_title_zh" in keys and row["structured_title_zh"] else row["structured_title"],
        "structured_title_en": row["structured_title_en"] if "structured_title_en" in keys and row["structured_title_en"] else row["structured_title"],
        "architect": row["architect"],
        "country": row["country"],
        "city": row["city"],
        "location": row["location"],
        "location_zh": row["location_zh"] if "location_zh" in keys and row["location_zh"] else (row["location"] or ""),
        "location_en": row["location_en"] if "location_en" in keys and row["location_en"] else (row["location"] or ""),
        "year": row["year"],
        "cover_image": row["cover_image"],
        "image_path": local_image_path or row["cover_image"],
        "local_image_path": local_image_path,
        "images": json.loads(row["images_json"] or "[]"),
        "description": row["description_zh"] or row["description"] or "",
        "description_zh": row["description_zh"] or row["description"] or "",
        "description_en": row["description_en"] or "",
        "tags": json.loads(row["tags_json"] or "[]"),
        "source_url": row["source_url"],
    }


def get_current_project() -> Optional[Dict[str, Any]]:
    init_db()
    with get_db() as conn:
        state = conn.execute("SELECT value FROM app_state WHERE key = 'current_project_id'").fetchone()
        pid = state["value"] if state else None
        if pid:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
            if row:
                return _row_to_project(row)

        # 优先展示最新收藏的建筑
        fav = conn.execute("SELECT project_id FROM favorites ORDER BY id DESC LIMIT 1").fetchone()
        if fav:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (fav["project_id"],)).fetchone()
            if row:
                return _row_to_project(row)

    # 初始状态或无收藏时，随机从 ArchDaily 漫游探索一座精选建筑大图
    rand_p = get_random_archdaily_project()
    if rand_p:
        set_current_project(rand_p["id"])
        return rand_p

    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects ORDER BY RANDOM() LIMIT 1").fetchone()
        if row:
            return _row_to_project(row)
    return None


def set_current_project(project_id: str):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES ('current_project_id', ?)", (project_id,))
        conn.execute("INSERT INTO history (project_id, viewed_at) VALUES (?, ?)", (project_id, now))
        conn.commit()


def get_notes(project_id: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM notes WHERE project_id = ? ORDER BY id ASC",
            (project_id,)
        ).fetchall()
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "author": r["author"],
                "content": r["content"],
                "color": r["color"],
                "rotation": 0.0,
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def add_note(project_id: str, author: str, content: str, color: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    chosen_color = color or "#faf9f5"

    with get_db() as conn:
        cursor = conn.execute("""
        INSERT INTO notes (project_id, author, content, color, rotation, created_at)
        VALUES (?, ?, ?, ?, 0.0, ?)
        """, (project_id, author.strip(), content.strip(), chosen_color, now))
        conn.commit()
        note_id = cursor.lastrowid

    return {
        "id": note_id,
        "project_id": project_id,
        "author": author,
        "content": content,
        "color": chosen_color,
        "rotation": 0.0,
        "created_at": now,
    }


def delete_note(note_id: int) -> bool:
    """删除指定便签"""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cursor.rowcount > 0


def toggle_favorite(
    project_id: str,
    favorited_by: str = "User",
    structured_title: Optional[str] = None,
    note: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, note, tags_json FROM favorites WHERE project_id = ? AND favorited_by = ?",
            (project_id, favorited_by)
        ).fetchone()

        if existing:
            # 如果显式传入了 tags 或 note，视为更新收藏备注与标签
            if tags is not None or note is not None:
                updated_note = note if note is not None else (existing["note"] or "")
                updated_tags = json.dumps(tags) if tags is not None else (existing["tags_json"] or "[]")
                conn.execute(
                    "UPDATE favorites SET note = ?, tags_json = ? WHERE id = ?",
                    (updated_note, updated_tags, existing["id"])
                )
                conn.commit()
                return {
                    "is_favorite": True,
                    "project_id": project_id,
                    "structured_title": structured_title,
                    "note": updated_note,
                    "tags": json.loads(updated_tags),
                    "updated": True,
                }
            else:
                conn.execute("DELETE FROM favorites WHERE id = ?", (existing["id"],))
                conn.commit()
                return {"is_favorite": False, "project_id": project_id}
        else:
            if not structured_title:
                p_row = conn.execute("SELECT structured_title FROM projects WHERE id = ?", (project_id,)).fetchone()
                structured_title = p_row["structured_title"] if p_row else f"建筑收藏 · {project_id}"

            tags_json = json.dumps(tags or [])
            conn.execute("""
            INSERT INTO favorites (project_id, favorited_by, structured_title, note, tags_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (project_id, favorited_by, structured_title, note or "", tags_json, now))
            conn.commit()
            return {
                "is_favorite": True,
                "project_id": project_id,
                "structured_title": structured_title,
                "note": note or "",
                "tags": tags or [],
            }


def is_favorite(project_id: str, favorited_by: str = "User") -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM favorites WHERE project_id = ? AND favorited_by = ?",
            (project_id, favorited_by)
        ).fetchone()
        return bool(row)


def list_favorites(tag: Optional[str] = None, query: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
        SELECT f.*, p.title, p.title_zh, p.title_en, p.structured_title_zh, p.structured_title_en,
               p.cover_image, p.architect, p.year, p.country, p.city, p.location_zh, p.location_en,
               p.description, p.description_zh
        FROM favorites f
        LEFT JOIN projects p ON f.project_id = p.id
        ORDER BY f.id DESC
        """).fetchall()

        fav_cols = rows[0].keys() if rows else []
        has_tags = "tags_json" in fav_cols

        q = (query or "").strip().lower()
        if q.startswith("#"):
            q = q[1:].strip()

        output = []
        for r in rows:
            tags_list = json.loads(r["tags_json"] or "[]") if has_tags and r["tags_json"] else []
            if tag and tag.strip():
                if tag.strip().lower() not in [str(t).lower() for t in tags_list]:
                    continue
            if q:
                match_text = " ".join([
                    str(r["title"] or ""),
                    str(r["title_zh"] or ""),
                    str(r["structured_title"] or ""),
                    str(r["structured_title_zh"] or ""),
                    str(r["architect"] or ""),
                    str(r["country"] or ""),
                    str(r["city"] or ""),
                    str(r["location_zh"] or ""),
                    str(r["note"] or ""),
                    str(r["description_zh"] or ""),
                    " ".join(tags_list)
                ]).lower()
                if q not in match_text:
                    continue

            output.append({
                "id": r["id"],
                "project_id": r["project_id"],
                "favorited_by": r["favorited_by"],
                "structured_title": r["structured_title"],
                "structured_title_zh": r["structured_title_zh"] or r["structured_title"],
                "structured_title_en": r["structured_title_en"] or r["structured_title"],
                "title": r["title"],
                "title_zh": r["title_zh"] or r["title"],
                "title_en": r["title_en"] or r["title"],
                "note": r["note"],
                "tags": tags_list,
                "created_at": r["created_at"],
                "cover_image": r["cover_image"],
                "architect": r["architect"],
                "is_favorite": True,
            })
        return output


def get_favorite_tags() -> List[str]:
    """获取收藏夹中已被使用的所有标签列表（去重并排序）"""
    with get_db() as conn:
        fav_cols = [c[1] for c in conn.execute("PRAGMA table_info(favorites)").fetchall()]
        if "tags_json" not in fav_cols:
            return []
        rows = conn.execute("SELECT tags_json FROM favorites WHERE tags_json IS NOT NULL").fetchall()
        tags_set = set()
        for r in rows:
            try:
                for t in json.loads(r["tags_json"] or "[]"):
                    if t and str(t).strip():
                        tags_set.add(str(t).strip())
            except Exception:
                pass
        return sorted(list(tags_set))


def add_daemon_share(project_id: str, note: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    with get_db() as conn:
        # Mark previous unread shares as read so new share cleanly supersedes previous
        conn.execute("UPDATE daemon_shares SET is_read = 1 WHERE is_read = 0")
        cursor = conn.execute("""
        INSERT INTO daemon_shares (project_id, note, created_at, is_read)
        VALUES (?, ?, ?, 0)
        """, (project_id, note or "", now))
        conn.commit()
        share_id = cursor.lastrowid
    return {"id": share_id, "project_id": project_id, "note": note, "created_at": now}


def get_daemon_shares(unread_only: bool = True) -> List[Dict[str, Any]]:
    with get_db() as conn:
        sql = """
        SELECT s.*, p.title, p.structured_title, p.cover_image, p.architect, p.location
        FROM daemon_shares s
        JOIN projects p ON s.project_id = p.id
        """
        if unread_only:
            sql += " WHERE s.is_read = 0"
        sql += " ORDER BY s.id DESC"
        rows = conn.execute(sql).fetchall()
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "note": r["note"],
                "created_at": r["created_at"],
                "is_read": bool(r["is_read"]),
                "title": r["title"],
                "structured_title": r["structured_title"],
                "architect": r["architect"],
                "cover_image": r["cover_image"],
                "location": r["location"],
            }
            for r in rows
        ]


def mark_daemon_share_read(share_id: int) -> bool:
    with get_db() as conn:
        res = conn.execute("UPDATE daemon_shares SET is_read = 1 WHERE id = ?", (share_id,))
        conn.commit()
        return res.rowcount > 0


def mark_all_daemon_shares_read() -> bool:
    with get_db() as conn:
        conn.execute("UPDATE daemon_shares SET is_read = 1 WHERE is_read = 0")
        conn.commit()
        return True


def list_history(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(f"""
        SELECT h.id as history_id, h.viewed_at, p.*
        FROM history h
        JOIN projects p ON h.project_id = p.id
        ORDER BY h.id DESC
        LIMIT {limit}
        """).fetchall()

        seen = set()
        output = []
        for r in rows:
            pid = r["id"]
            if pid not in seen:
                seen.add(pid)
                fav = conn.execute("SELECT id FROM favorites WHERE project_id = ?", (pid,)).fetchone()
                output.append({
                    "project_id": pid,
                    "title": r["title"],
                    "title_zh": r["title_zh"] if "title_zh" in r.keys() and r["title_zh"] else r["title"],
                    "title_en": r["title_en"] if "title_en" in r.keys() and r["title_en"] else r["title"],
                    "structured_title": r["structured_title"],
                    "structured_title_zh": r["structured_title_zh"] if "structured_title_zh" in r.keys() and r["structured_title_zh"] else r["structured_title"],
                    "structured_title_en": r["structured_title_en"] if "structured_title_en" in r.keys() and r["structured_title_en"] else r["structured_title"],
                    "location_zh": r["location_zh"] if "location_zh" in r.keys() and r["location_zh"] else (r["location"] or ""),
                    "location_en": r["location_en"] if "location_en" in r.keys() and r["location_en"] else (r["location"] or ""),
                    "cover_image": r["cover_image"],
                    "architect": r["architect"],
                    "year": r["year"],
                    "country": r["country"],
                    "city": r["city"],
                    "viewed_at": r["viewed_at"],
                    "is_favorite": bool(fav),
                })
        return output


def list_carousel_projects() -> List[Dict[str, Any]]:
    """返回用于腰部左右箭头翻阅的建筑列表（严格以收藏夹为准，未收藏的分享不进入翻页轮播）"""
    favs = list_favorites()
    fav_ids = [f["project_id"] for f in favs]

    items = []
    seen = set()

    with get_db() as conn:
        for fid in fav_ids:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (fid,)).fetchone()
            if row and fid not in seen:
                seen.add(fid)
                items.append(_row_to_project(row))

    return items


def recommend_to_daemon(project_id: str, user_note: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute("""
        INSERT INTO recommendations (project_id, user_note, status, created_at)
        VALUES (?, ?, 'pending', ?)
        """, (project_id, user_note or "向你推荐了这座精选建筑，快来看看吧！", now))
        conn.commit()
    return {"status": "success", "message": "已成功转给伴侣，TA稍后会来查看！"}


def get_pending_recommendations() -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("""
        SELECT r.*, p.title, p.structured_title, p.cover_image, p.architect, p.location
        FROM recommendations r
        JOIN projects p ON r.project_id = p.id
        WHERE r.status = 'pending'
        ORDER BY r.id DESC
        """).fetchall()
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "user_note": r["user_note"],
                "created_at": r["created_at"],
                "title": r["title"],
                "structured_title": r["structured_title"],
                "architect": r["architect"],
                "cover_image": r["cover_image"],
            }
            for r in rows
        ]


init_db()
