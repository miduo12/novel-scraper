# 得奇小说网爬虫

一个可断点续爬的 Python 小说爬虫核心项目。当前优先适配得奇小说网，完成核心抓取后再接入 PySide6 GUI。

## 已确认的站点结构

- 小说目录：`https://www.deqixs.cc/books/99/`
- 完整章节容器：`#list-chapterAll dd a[href]`，当前目录一次性返回全书章节。
- 章节标题：`h1.pt10`，需要清理 `(第/页)` 一类页标记。
- 当前章节正文使用两层加载：页面中的 `chapter.js.php` 提供签名，随后请求 `modules/article/ajax2.php` 获取正文。
- 章节分页仍按 `?page=N` 请求。当前测试站对越界分页会返回同一页内容，所以程序对正文做规范化后计算 SHA-256；遇到重复正文立即停止，不重复保存。

## 当前功能

- 从小说 URL 或章节 URL 推导目录地址。
- 解析完整章节目录并打印章节 URL。
- 抓取单个章节的全部分页并合并为完整章节。
- 抓取整本小说，按章节分别保存并生成整本 TXT。
- JSON 断点状态、已存在章节跳过、失败原因记录。
- 网络失败自动重试、指数退避、请求间隔。
- 按 URL 去重，限制最大分页数，防止异常循环。
- 适配器分层，后续可以继续添加其他小说网站。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

当前开发环境也可以直接运行，因为已经安装 `requests` 和 `beautifulsoup4`。

## 命令行用法

### 1. 查看完整目录

```powershell
python -m novel_scraper chapters "https://www.deqixs.cc/books/99/"
```

### 2. 抓取一个章节的所有分页

```powershell
python -m novel_scraper chapter "https://www.deqixs.cc/books/99/63332.html"
```

### 3. 抓取整本小说

```powershell
python -m novel_scraper crawl "https://www.deqixs.cc/books/99/"
```

首次联调建议只抓前三章并用较小间隔：

```powershell
python -m novel_scraper crawl "https://www.deqixs.cc/books/99/" --limit 3 --delay 0.5
```

常用参数：

- `--delay 1.0`：请求之间的最短间隔秒数。
- `--retries 3`：网络失败后的额外重试次数。
- `--max-pages 100`：单章最大分页数，防止异常页面导致无限循环。
- `--limit 3`：只处理前 N 章，适合联调。
- `--force`：忽略已有断点，重新抓取本次范围内的章节。

## 输出目录

默认输出到 `downloads/书名/`：

```text
downloads/
└── 玄鉴仙族/
    ├── chapters/
    │   ├── 0001_第1章 初入.txt
    │   └── ...
    ├── state.json
    ├── failed_chapters.txt
    └── 玄鉴仙族.txt
```

每章抓取成功后会立即写入独立文件并更新 `state.json`。中途停止或断网后，再次执行同一命令会跳过已完成章节。整本 TXT 会在每次运行结束时重新合并当前已经存在的章节。

## 测试

```powershell
python -m pytest
```

真实站点测试需要显式开启：

```powershell
$env:RUN_LIVE_TESTS="1"
python -m pytest tests/test_live_deqixs.py -m integration
```

`downloads/` 已加入 `.gitignore`，抓取到的正文不会推送到 GitHub。

## 后续开发

1. 用当前 CLI 跑通小范围章节，确认正文和断点行为。
2. 增加更多异常结构测试和站点变化检测。
3. 接入 PySide6 GUI，复用 `NovelCrawler`、`CrawlOptions` 和进度事件。
4. 再抽象通用适配器接口，扩展到其他小说网站。
