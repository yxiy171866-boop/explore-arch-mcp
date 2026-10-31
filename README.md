# Explore Architecture MCP (建筑漫游与双向画板系统)

一套让 AI 自主探索世界建筑的完整工具集，包含基于 FastMCP 的标准 MCP 服务器、高性能 REST API 后端以及纯原生前端互动画布。

AI 可通过标准工具调用自主浏览、检索、收藏 ArchDaily 超过 6.5 万座全球经典与现代建筑作品，并配合多模态视觉通道直接读取现场高清建筑摄影进行鉴赏，支持与用户进行双向安利、便签留言讨论与分类标签管理。接入即用，无需申请任何付费第三方 API 密钥。

---

## 核心功能

- 全球真实建筑数据库：直连 ArchDaily 开放接口，收录全球现代建筑、公共设施、住宅与历史改造作品。
- AI 多模态视觉赋能：支持自动下载现场高清实景原图到本地缓存目录，多模态模型（如 Claude Opus、GPT-4o、Gemini 等）可直接读取图像鉴赏光影关系、混凝土与砖石肌理、开窗比例与空间进深。
- 拟真便签墙：建筑展品下方支持便签纸流留言讨论，支持自定义署名与单条确认安全删除。
- 结构化收藏与标签筛选：收藏项自动生成规范索引标题（格式如 `[国家·城市] 建筑名 · 建筑师`），支持挂载多个分类标签，并提供标签过滤气泡与实时关键词模糊检索框。
- 展品腰部轮播切换：主卡片腰部设有翻阅控制按钮，与个人收藏夹联动循环翻阅。
- 双向分享推送：支持 AI 向前端大图主动分享建筑，前端顶部弹出实时横幅；用户亦可在前端将漫游到的灵感作品一键转给 AI。
- 多语言模式切换：提供纯中文、中英双语对照、原生英文三种语言展示，包括标题、简介与结构化地理索引的实时意译。
- 零外部付费依赖：开箱即用，无需申请任何付费 API 密钥，内建 SQLite 高速持久化存储与本地并发缓存。

---

## 项目目录结构

```text
explore-arch-mcp/
├── server.py             # 标准 FastMCP 协议服务器实现 (stdio 传输)
├── service.py            # ArchDaily 爬虫、SQLite 本地缓存、双语翻译与业务逻辑
├── app.py                # 独立 FastAPI 服务端 (提供 REST 接口与静态前端托管)
├── requirements.txt      # 依赖文件
├── LICENSE               # MIT 开源协议
├── .gitignore            # Git 忽略配置
├── README.md             # 项目说明文档
└── static/
    └── index.html        # 单页面互动画布 UI (便签流、漫游卡片、收藏管理与搜索)
```

---

## 快速上手

### 1. 安装环境与依赖

本项目推荐使用 Python 3.10 或更高版本。

```bash
git clone https://github.com/yxiy171866-boop/explore-arch-mcp.git
cd explore-arch-mcp

python3 -m venv venv
source venv/bin/activate  # Windows 用户运行: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 启动独立 Web 服务

```bash
python app.py
```

服务默认运行在 `http://localhost:8000`。打开浏览器访问即可进入互动画布。
初次访问时会弹出设置向导，可在本地配置你与 AI 的称谓（保存在浏览器本地 localStorage 中，不涉及任何云端隐私上传）。

---

## MCP 客户端配置

本系统完全符合标准 Model Context Protocol 规范，可无缝接入各类支持 MCP 的 AI 桌面端与开发工具。

### Claude Desktop 配置

编辑 Claude Desktop 配置文件：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

在 `mcpServers` 字段中加入：

```json
{
  "mcpServers": {
    "architecture": {
      "command": "python",
      "args": [
        "/绝对路径/explore-arch-mcp/server.py"
      ]
    }
  }
}
```

配置完成后重启 Claude Desktop，即可在对话中直接唤醒建筑工具。

### Cursor / Windsurf / 通用客户端配置

在工具的 MCP 设置面板中添加：
- Type: `stdio`
- Command: `python`
- Args: `/绝对路径/explore-arch-mcp/server.py`

---

## MCP 工具列表与参数说明

本服务为 AI 助手提供以下 8 个标准工具：

### 1. search_architecture
- 功能：按关键词检索世界建筑项目，支持按建筑名、建筑师、风格、城市或年份搜索。
- 参数：
  - `query` (string, 必需)：综合搜索词（如 `安藤忠雄 光之教堂`、`解构主义`、`落水山庄`）。
  - `style` (string, 可选)：建筑风格（如 `粗野主义`、`极简主义`）。
  - `architect` (string, 可选)：建筑师或事务所名称。
  - `city` (string, 可选)：城市或国家名称。
  - `year` (string, 可选)：建造年份。
- 返回：匹配建筑的结构化索引、建筑师、年份、地点、简短理念、本地图片路径与项目 ID。

### 2. random_architecture
- 功能：在 ArchDaily 6.5万+ 项目库中随机漫游探索一座精选建筑灵感作品。
- 参数：无。
- 返回：随机建筑的结构化索引、基本信息、设计理念与本地大图路径。

### 3. get_current_display
- 功能：获取当前前端大图正在展示的建筑作品详情及下方的全部便签留言。
- 参数：无。
- 返回：展品详细信息、本地大图文件路径以及历史便签列表。

### 4. write_note
- 功能：在当前大图展示的建筑下方留下一张专属便签。
- 参数：
  - `content` (string, 必需)：便签留言正文。
  - `author` (string, 可选)：便签署名，默认 `AI`。
- 返回：操作状态与贴好的便签内容。

### 5. share_to_big_display
- 功能：搜索或指定一座建筑并推送到前端大图展示，触发前端实时分享通知，同时可附带推荐便签。
- 参数：
  - `keyword_or_title` (string, 可选)：建筑名称、关键词或建筑师。
  - `project_id` (string, 可选)：项目 ID（如已知）。
  - `note` (string, 可选)：推荐理由或留言。
- 返回：展示状态、结构化索引与图片路径。

### 6. check_recommendations
- 功能：查看用户在前端通过“转给他”按钮安利给 AI 的建筑推荐列表。
- 参数：无。
- 返回：待处理的推荐作品列表与用户留言。

### 7. favorite_architecture
- 功能：将指定建筑收入收藏夹，或更新分类标签与收藏理由。
- 参数：
  - `project_id` (string, 必需)：项目 ID。
  - `structured_title` (string, 可选)：规范化索引标题。
  - `reason` (string, 可选)：收藏理由。
  - `tags` (array of string, 可选)：分类标签列表（如 `["清水混凝土", "安藤忠雄", "教堂"]`）。
- 返回：收藏或取消收藏的状态结果。

### 8. list_favorite_architectures
- 功能：查阅收藏夹列表，支持按标签过滤或按关键词模糊搜索。
- 参数：
  - `tag` (string, 可选)：分类标签。
  - `keyword` (string, 可选)：搜索关键词（支持匹配建筑名、建筑师、地点或笔记）。
- 返回：符合条件的收藏列表与详细信息。

---

## 数据流、网络交互与隐私说明

- 本地数据存储：
  - 所有便签留言、个人收藏、自定义分类标签以及足迹历史均保存在本地 SQLite 数据库（`data/architecture.db`）。
  - 建筑实景大图下载后缓存于本地 `data/images_cache/` 目录，供多模态视觉模型读取，避免重复请求。
  - 前端用户与 AI 称呼保存在浏览器本地 localStorage，服务默认绑定 `127.0.0.1` 仅限本地访问，不设任何云端遥测与外部数据上报。
- 外部网络交互：
  - 建筑检索与作品元数据：AI 或用户检索时，系统直接向 ArchDaily 公共查询接口发送搜索请求并解析公开项目数据。
  - 文本意译（中英互译）：系统默认通过 Google 翻译公共端点进行异步意译，配合本地 LRU 缓存与多线程并发执行，减少请求频次并防止延迟。翻译内容仅涉及公开的建筑名称、设计理念及地理位置文本，不涉及任何私人便签与个人生活数据。

---

## 开源许可与声明

- 本项目采用 MIT 协议开源，详见 LICENSE 文件。
- 建筑摄影与建筑作品描述的数据版权均归 ArchDaily 及对应建筑师事务所、摄影师所有。本项目仅用于个人学习、建筑艺术交流与研究用途，严禁用于任何未经授权的商业用途。
