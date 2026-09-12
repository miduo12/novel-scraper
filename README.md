# 小说下载器

一个面向普通用户的 Windows 桌面小说下载工具。粘贴得奇小说网目录链接，选择保存位置，点击一次即可自动抓取全部章节并生成 TXT。

## 直接下载使用

Windows 10/11 64 位用户可以直接下载单文件版本：

**下载地址：** [NovelScraper.exe](https://github.com/miduo12/novel-scraper/releases/latest/download/NovelScraper.exe)

使用方法：

1. 下载 `NovelScraper.exe`。
2. 双击运行，不需要安装 Python。
3. 粘贴小说目录链接，例如 `https://www.deqixs.cc/books/99/`。
4. 选择保存位置，默认是系统“下载/小说下载”。
5. 点击“开始下载”，程序会自动读取目录、抓取章节并生成整本 TXT。

> 当前 EXE 没有购买商业代码签名证书，Windows SmartScreen 首次运行时可能提示“未知发布者”。可以点击“更多信息”后选择“仍要运行”。如果希望发布给大量用户，后续应补充代码签名。

## 桌面版功能

- 粘贴网址即可使用，不需要命令行。
- 自动显示书名、作者、当前章节和完成进度。
- 支持停止任务，已完成的章节会保留。
- 再次打开并下载同一本小说时，会自动跳过已完成章节，实现断点续爬。
- 网络失败自动重试，失败章节会写入 `failed_chapters.txt`。
- 每章保存为独立 TXT，同时合并生成整本 TXT。
- 运行记录直接显示在窗口中。

输出目录示例：

```text
小说下载/
└── 玄鉴仙族/
    ├── chapters/
    │   ├── 0001_第1章 初入.txt
    │   └── ...
    ├── state.json
    ├── failed_chapters.txt
    └── 玄鉴仙族.txt
```

## 当前适配范围

当前版本优先完整适配得奇小说网 `deqixs.cc`，不是“理论上支持所有网站”的通用爬虫。站点结构变化后，需要更新 `src/novel_scraper/adapters/deqixs.py`。

当前已确认的站点结构：

- 完整章节目录：`#list-chapterAll dd a[href]`。
- 章节标题：`h1.pt10`。
- 正文签名：页面中的 `chapter.js.php`。
- 正文接口：`modules/article/ajax2.php`。
- 分页请求使用 `?page=N`，越界时可能重复返回最后一页。程序会对提取后的正文计算 SHA-256，发现重复立即停止。

## 从源码运行桌面版

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[gui]"
python -m novel_scraper.gui
```

如果 PyPI 下载速度较慢，可以使用镜像：

```powershell
python -m pip install -e ".[gui]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 命令行版本

桌面版和命令行版共用同一个爬虫核心，也可以继续使用 CLI：

```powershell
python -m novel_scraper chapters "https://www.deqixs.cc/books/99/"
python -m novel_scraper chapter "https://www.deqixs.cc/books/99/63332.html"
python -m novel_scraper crawl "https://www.deqixs.cc/books/99/" --limit 3 --delay 1.0
```

常用参数：

- `--delay 1.0`：请求之间的最短间隔秒数。
- `--retries 3`：网络失败后的额外重试次数。
- `--max-pages 100`：单章最大分页数，防止异常页面导致无限循环。
- `--limit 3`：只处理前 N 章，适合联调。
- `--force`：忽略已有断点，重新抓取本次范围内的章节。

## 构建 Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

构建产物位于 `dist/NovelScraper.exe`。该文件是 PyInstaller 单文件程序，可以复制到其他 Windows 10/11 64 位电脑直接运行。

## 测试

```powershell
python -m pip install -e ".[gui,dev]"
python -m pytest
```

真实站点测试需要显式开启：

```powershell
$env:RUN_LIVE_TESTS="1"
python -m pytest tests/test_live_deqixs.py -m integration
```

## 项目结构

```text
src/novel_scraper/
├── adapters/       网站适配器
├── cli.py          命令行入口
├── crawler.py      断点、重试和事件流
├── gui.py          PySide6 桌面界面
├── gui_worker.py   GUI 后台线程
├── http.py         HTTP 客户端
├── parsers.py      HTML 正文解析
└── storage.py      TXT、状态和失败记录
```

## 合规说明

请合理设置请求频率，仅用于个人学习、备份和已获授权的内容。不要使用本工具绕过付费、权限或访问控制，并遵守目标网站的服务条款和适用法律。
