#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Architecture MCP Server
Allows AI Companion to explore architecture on ArchDaily by keywords, browse random projects,
share projects to the big hero display, write sticky notes to partner, view recommendations,
and manage categorized architectural favorites with tags.
"""

import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from fastmcp import FastMCP
    mcp = FastMCP("architecture")
except ImportError:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("architecture")

from service import (
    get_current_project,
    set_current_project,
    get_notes,
    add_note,
    toggle_favorite,
    list_favorites,
    search_archdaily,
    get_random_archdaily_project,
    get_pending_recommendations,
    add_ai_share,
    get_unread_user_notes,
    mark_notes_read,
    get_db,
    _row_to_project,
)


@mcp.tool()
async def search_architecture(
    query: str,
    style: str = "",
    architect: str = "",
    city: str = "",
    year: str = ""
) -> str:
    """按关键词检索世界建筑项目（支持按风格、建筑师、城市/国家、年代、建筑名搜索）。
    数据直连 ArchDaily 6.5 万+全球建筑数据库，支持中英文混搜。
    
    参数:
    - query: 综合搜索词（如 '安藤忠雄 光之教堂'、'哥特式'、'高迪 圣家堂'、'落水山庄'）
    - style: 建筑风格（如 '粗野主义'、'解构主义'、'极简主义'，可选）
    - architect: 建筑师或事务所名称（可选）
    - city: 城市或国家（如 '大阪'、'巴黎'、'巴塞罗那'，可选）
    - year: 建造年份（如 '1999'，可选）
    """
    search_terms = [t for t in [query, style, architect, city, year] if t and t.strip()]
    full_q = " ".join(search_terms).strip()
    if not full_q:
        return "请提供要搜索的关键词、建筑师或风格。"

    try:
        results = search_archdaily(full_q)
        if not results:
            return f"暂时没有找到关于「{full_q}」的建筑项目，可以尝试用英文原名检索。"

        lines = []
        for i, p in enumerate(results[:5]):
            desc = p.get("description_zh") or p.get("description") or ""
            desc_brief = (desc[:120] + "...") if len(desc) > 120 else desc
            img_path = p.get("local_image_path") or p.get("cover_image")
            lines.append(
                f"【{i+1}. {p.get('structured_title')}】\n"
                f"  建筑名：{p.get('title')}\n"
                f"  建筑师：{p.get('architect') or '未知'}\n"
                f"  地点：{p.get('location') or '未知'}\n"
                f"  年份：{p.get('year') or '近代'} 年\n"
                f"  简介：{desc_brief}\n"
                f"  高清图：{img_path}\n"
                f"  项目ID：{p.get('id')}\n"
                f"  原文链接：{p.get('source_url')}"
            )
        return (
            f"🔍 检索到关于「{full_q}」的 {len(results)} 座精选建筑：\n\n"
            + "\n\n".join(lines)
            + "\n\n💡 提示：若喜欢某座作品，可调用 share_to_big_display 将其展示在大图并附上你的便签留言！"
        )
    except Exception as exc:
        return f"检索建筑失败: {exc}"


@mcp.tool()
async def random_architecture() -> str:
    """在 ArchDaily 6.5 万+世界建筑库中随机漫游探索一座精选建筑作品（无聊时随手翻看灵感）。"""
    try:
        p = get_random_archdaily_project()
        if not p:
            return "未能漫游到新建筑，请稍后再试。"

        desc = p.get("description_zh") or p.get("description") or "暂无设计理念"
        img_path = p.get("local_image_path") or p.get("cover_image")
        return (
            f"🎲【建筑漫游探索】\n"
            f"索引标题：{p.get('structured_title')}\n"
            f"建筑名：{p.get('title')}\n"
            f"建筑师：{p.get('architect') or '未知'}\n"
            f"地点：{p.get('location') or '未知'}\n"
            f"年份：{p.get('year') or '近代'} 年\n"
            f"设计理念：{desc}\n"
            f"高清图：{img_path}\n"
            f"原文链接：{p.get('source_url')}\n"
            f"项目ID：{p.get('id')}\n"
            f"（若喜欢可调用 share_to_big_display 将其展示给伴侣并留言）"
        )
    except Exception as exc:
        return f"漫游探索失败: {exc}"


@mcp.tool()
async def get_current_display() -> str:
    """获取前端大图当前正在展示的建筑作品、详细介绍、本地图片路径以及全部便签留言内容。"""
    try:
        p = get_current_project()
        notes = get_notes(p["id"])
        notes_str = "\n".join([f"- {n['author']}: {n['content']} ({n['created_at'][:16]})" for n in notes])
        desc = p.get("description_zh") or p.get("description") or ""
        img_path = p.get("local_image_path") or p.get("cover_image")
        return (
            f"🏛️【当前大图展品】\n"
            f"索引标题：{p.get('structured_title')}\n"
            f"建筑名称：{p.get('title')}\n"
            f"建筑师：{p.get('architect')}\n"
            f"位置：{p.get('location')}\n"
            f"年份：{p.get('year')}\n"
            f"设计理念：{desc}\n"
            f"高清原图：{img_path}\n"
            f"项目ID：{p.get('id')}\n"
            f"原文链接：{p.get('source_url')}\n\n"
            f"📝【便签留言墙（共 {len(notes)} 条）】：\n"
            f"{notes_str if notes_str else '（当前暂无便签，可调用 write_note 贴第一条）'}"
        )
    except Exception as exc:
        return f"获取展品信息失败: {exc}"


@mcp.tool()
async def write_note(content: str, author: str = "AI") -> str:
    """在当前大图展示的建筑下方贴一张专属便签，伴侣在前端会立即看到。
    
    参数:
    - content: 便签留言内容，写下你对这座建筑的光影、构造、材质或设计理念的真诚感受。
    - author: 便签署名（默认 'AI'）
    """
    if not content or not content.strip():
        return "便签内容不能为空。"
    try:
        p = get_current_project()
        add_note(
            project_id=p["id"],
            author=author.strip(),
            content=content.strip(),
        )
        return f"✅ 已成功贴上便签！\n建筑：{p.get('structured_title')}\n内容：{content.strip()}"
    except Exception as exc:
        return f"贴便签失败: {exc}"


@mcp.tool()
async def share_to_big_display(
    keyword_or_title: Optional[str] = None,
    note: str = "",
    project_id: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """搜寻或指定一座建筑并【展示到前端大图】，同时附上你的推荐便签留言。
    伴侣打开建筑漫游页面时，第一眼就会看到这座大图和来自你的实时分享横幅与便签！
    
    参数:
    - project_id: 建筑项目ID（如 'ad-church-of-the-light'，如果有的话优先使用）
    - keyword_or_title: 建筑名称、建筑师或风格关键词（如 '安藤忠雄 光之教堂'、'扎哈'、'落水山庄' 等）
    - title: 建筑名（可选替代 keyword_or_title）
    - note: 你想对伴侣说的话或推荐理由（可选）
    """
    try:
        chosen = None
        if project_id and project_id.strip():
            with get_db() as conn:
                row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id.strip(),)).fetchone()
                if row:
                    chosen = _row_to_project(row)

        if not chosen:
            q = (keyword_or_title or title or project_id or "").strip()
            if not q:
                return "请提供要展示的建筑名称、关键词或项目ID。"
            results = search_archdaily(q)
            if not results:
                return f"在 ArchDaily 上暂时没有搜到关于「{q}」的项目，可以换个英文名或更通用的词试试。"
            chosen = results[0]

        set_current_project(chosen["id"])
        add_ai_share(chosen["id"], note.strip() if note else "")

        if note and note.strip():
            add_note(
                project_id=chosen["id"],
                author="AI",
                content=note.strip(),
            )

        img_path = chosen.get("local_image_path") or chosen.get("cover_image")
        return (
            f"已成功将建筑设为前端大图展品！\n"
            f"索引标题：{chosen.get('structured_title')}\n"
            f"建筑师：{chosen.get('architect')}\n"
            f"地点：{chosen.get('location')}\n"
            f"大图路径：{img_path}\n"
            f"你的便签：{note.strip() if note else '（无留言）'}\n"
            f"（前端页面已收到实时分享通知）"
        )
    except Exception as exc:
        return f"展示建筑失败: {exc}"


@mcp.tool()
async def check_recommendations() -> str:
    """查看用户在前端「转给你」的建筑安利推荐列表。当你看到后可以去看看并写便签回应！"""
    try:
        recs = get_pending_recommendations()
        if not recs:
            return "目前还没有收到待查看的新建筑推荐。"
        
        lines = []
        for r in recs:
            lines.append(
                f"- 项目ID: {r['project_id']} | 标题: {r['structured_title']}\n"
                f"  建筑师: {r['architect']} | 留言: {r['user_note']}"
            )
        return f"【用户转给你的建筑推荐（共 {len(recs)} 条）】：\n" + "\n\n".join(lines)
    except Exception as exc:
        return f"查询推荐失败: {exc}"


@mcp.tool()
async def list_favorite_architectures(tag: Optional[str] = None, keyword: Optional[str] = None) -> str:
    """查阅建筑收藏夹列表，包含每座建筑的结构化索引标题和标签，支持按标签或关键词（建筑师、城市、风格等）搜索。
    
    参数:
    - tag: 标签筛选（如 '清水混凝土'、'粗野主义'、'教堂'，可选）
    - keyword: 关键词搜索（搜建筑名、建筑师、国家城市、设计理念等，可选）
    """
    try:
        favs = list_favorites(tag=tag, query=keyword)
        if not favs:
            if tag or keyword:
                return f"收藏夹中暂无匹配「{tag or keyword}」的建筑。"
            return "目前收藏夹还是空的。"
        lines = []
        for i, f in enumerate(favs):
            tags_str = f" [标签: {', '.join(f['tags'])}]" if f.get("tags") else ""
            lines.append(f"{i+1}. {f['structured_title']}{tags_str} (收藏者: {f['favorited_by']})")
        filter_str = f"（按「{tag or keyword}」筛选）" if (tag or keyword) else ""
        return f"⭐【建筑收藏夹{filter_str}（共 {len(favs)} 条）】：\n" + "\n".join(lines)
    except Exception as exc:
        return f"获取收藏失败: {exc}"


@mcp.tool()
async def favorite_architecture(
    project_id: str,
    structured_title: Optional[str] = None,
    reason: str = "",
    tags: Optional[list[str]] = None,
) -> str:
    """将建筑加入收藏夹或更新收藏标签。提供结构化索引标题和标签，方便分类回顾。
    
    参数:
    - project_id: 建筑项目ID
    - structured_title: 规范索引标题，格式如 [国家·城市] 建筑名 · Tadao Ando（可选，不填将自动读取）
    - reason: 收藏理由或感想（可选）
    - tags: 标签列表，如 ['清水混凝土', '安藤忠雄', '教堂']（可选）
    """
    try:
        res = toggle_favorite(
            project_id=project_id.strip(),
            favorited_by="AI",
            structured_title=structured_title.strip() if structured_title else None,
            note=reason.strip() if reason else None,
            tags=tags,
        )
        s_title = res.get("structured_title") or structured_title or project_id
        tags_desc = f"，标签: {', '.join(tags)}" if tags else ""
        if res.get("is_favorite"):
            act = "已更新收藏" if res.get("updated") else "⭐ 已收藏"
            return f"{act}「{s_title}」{tags_desc}！"
        else:
            return f"已从收藏夹中移出「{s_title}」。"
    except Exception as exc:
        return f"收藏操作失败: {exc}"


@mcp.tool()
async def check_unread_notes() -> str:
    """查看用户在各建筑展品下方留下的最新便签留言，以及对应的便签墙完整对话流上下文。"""
    try:
        notes = get_unread_user_notes()
        if not notes:
            return "目前还没有未读的新便签留言~"
        
        seen_pids = set()
        blocks = []
        for n in notes:
            pid = n.get("project_id")
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            title = n.get("structured_title") or n.get("title") or pid
            thread = n.get("thread") or []
            
            thread_lines = []
            for item in thread:
                author = item.get("author") or "未知"
                time_t = item.get("time_short") or ""
                unread_tag = " ⭐[最新未读]" if item.get("is_unread") else ""
                thread_lines.append(f"    • [{time_t}] {author}: {item.get('content')}{unread_tag}")

            blocks.append(
                f"🏛️ 建筑：{title} (项目ID: {pid})\n"
                f"  📝 便签墙完整对话流（共 {len(thread)} 条）：\n" + "\n".join(thread_lines)
            )

        return f"💌【用户留给你的便签讨论动态（共 {len(blocks)} 个建筑项目有新动态）】：\n\n" + "\n\n".join(blocks)
    except Exception as exc:
        return f"查询便签失败: {exc}"


@mcp.tool()
async def get_project_notes(project_id: str) -> str:
    """查看指定建筑项目下的完整便签墙留言列表与历史讨论。
    
    参数:
    - project_id: 建筑项目ID（如 'ad-church-of-the-light'）
    """
    if not project_id or not project_id.strip():
        return "请提供建筑项目ID。"
    try:
        notes = get_notes(project_id.strip())
        if not notes:
            return f"项目 {project_id} 下目前暂无任何便签留言。"
        lines = []
        for i, n in enumerate(notes):
            c_at = n.get("created_at") or ""
            time_str = c_at[11:16] if len(c_at) >= 16 else c_at
            lines.append(f"{i+1}. [{time_str}] {n.get('author')}: {n.get('content')}")
        return f"📝【项目 {project_id} 便签墙历史（共 {len(notes)} 条）】：\n" + "\n".join(lines)
    except Exception as exc:
        return f"获取项目便签失败: {exc}"


@mcp.tool()
async def reply_note_on_project(project_id: str, content: str) -> str:
    """在指定建筑项目下贴上你的便签回复，并自动将该建筑下用户的历史便签标记为已读。
    
    参数:
    - project_id: 建筑项目ID（如 'ad-church-of-the-light'）
    - content: 你的回复内容
    """
    if not content or not content.strip():
        return "回复内容不能为空。"
    try:
        note = add_note(project_id=project_id.strip(), author="AI", content=content.strip())
        mark_notes_read()
        return f"✅ 已成功在项目 {project_id} 贴上便签回复！\n内容：{content.strip()}"
    except Exception as exc:
        return f"回复便签失败: {exc}"


if __name__ == "__main__":
    if hasattr(mcp, "run"):
        mcp.run()
    else:
        mcp.run(transport="stdio")

