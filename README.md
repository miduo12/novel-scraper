# 小说下载器

一个面向普通用户的 Windows 桌面小说下载工具。粘贴得奇小说网目录链接，选择保存位置，点击一次即可自动抓取全部章节并生成 TXT。

## 直接下载使用

Windows 10/11 64 位用户可以直接下载单文件版本：

**下载地址：** [NovelScraper.exe](https://github.com/miduo12/novel-scraper/releases/latest/download/NovelScraper.exe)

使用方法：

1. 下载 `NovelScraper.exe`。
2. 双击运行，不需要安装 Python。
3. 粘贴小说目录链接，例如 `https://www.deqixs.cc/books/99/` 或 `https://www.sudugu.cc/674/`。
4. 选择保存位置，默认是系统“下载/小说下载”。
5. 如果只下载部分章节，勾选“仅下载指定范围”并填写起始、结束章节；不勾选则下载全部章节。
6. 点击“开始下载”，完成后会同时保留 `chapters/` 分章 TXT 和书籍根目录下的合并 TXT。

> 当前 EXE 没有购买商业代码签名证书，Windows SmartScreen 首次运行时可能提示“未知发布者”。可以点击“更多信息”后选择“仍要运行”。如果希望发布给大量用户，后续应补充代码签名。

## 桌面版功能

- 粘贴网址即可使用，不需要命令行。
- 自动显示书名、作者、当前章节和完成进度。
- 支持停止任务，已完成的章节会保留。
- 支持按章节标题中的真实章号自定义“从第 N 章到第 M 章”的下载范围。
- 内置“稳定 / 快速 / 极速”三档下载速度，默认使用快速模式。
- 再次打开并下载同一本小说时，会自动跳过已完成章节，实现断点续爬。
- 网络失败自动重试，失败章节会写入 `failed_chapters.txt`。
- 每章保存为独立 TXT，同时自动合并生成书籍根目录下的完整 TXT。
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

当前版本已适配：

- 得奇小说网 `deqixs.cc`
- 速读谷 `sudugu.cc`

不是“理论上支持所有网站”的通用爬虫。站点结构变化后，需要更新对应适配器：

- `src/novel_scraper/adapters/deqixs.py`
- `src/novel_scraper/adapters/sudugu.py`

速读谷章节采用 `章节ID_页码.html` 分页，适配器会读取页面中的“当前页 / 总页数”并合并完整章节。目录如果分成多页，程序会自动跟随“下一页”继续解析，并支持恢复 `data-enc` 中保存的隐藏末章地址。

当前已确认的站点结构：

- 完整章节目录：`#list-chapterAll dd a[href]`。
- 章节标题：`h1.pt10`。
- 正文签名：页面中的 `chapter.js.php`。
- 正文接口：`modules/article/ajax2.php`。
- 当前 `ajax2.php` 一次返回整章正文，程序每章只需“签名脚本 + 正文接口”两次请求，不再重复抓取 `?page=2`。
- 如果站点未来恢复服务器端分页，适配器仍保留 HTML 正文和分页回退逻辑。

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

## 内容检测与保守清洗

桌面端主窗口新增“内容检测/清洗”按钮，用于处理已经下载完成的小说。原始 `chapters/` 永远不会被覆盖。

使用步骤：

1. 选择一个包含 `chapters/` 的小说文件夹。
2. 选择“仅检测”或“保守自动修复”。
3. 点击开始，程序会逐章检测广告、标点、乱码和异常繁简体字符。
4. 自动修复完成后，程序会询问“保存清洗版 / 暂不保存 / 先人工审核”。
5. 只有选择保存，或在人工审核窗口点击“应用审核结果”后，才会写入 `cleaned/`。

两种模式：

- `仅检测`：不修改正文，只生成报告。
- `保守自动修复`：只修改高置信度问题；中低置信度问题只记录，始终保留原文。

输出结构：

```text
小说下载/
└── 玄鉴仙族/
    ├── chapters/                 # 原始章节，始终保留
    ├── cleaned/                  # 用户确认保存后才生成
    │   ├── chapters/
    │   └── 玄鉴仙族_清洗版.txt
    └── reports/
        ├── clean_report.json
        ├── clean_report.csv
        ├── clean_report.txt
        ├── clean_log.json       # 所有自动修改的完整记录
        └── review_decisions.json # 人工审核接受/取消记录
```

命令行用法：

```powershell
.\.venv\Scripts\python.exe -m novel_scraper clean "下载目录\玄鉴仙族" --mode detect
.\.venv\Scripts\python.exe -m novel_scraper clean "下载目录\玄鉴仙族" --mode auto
.\.venv\Scripts\python.exe -m novel_scraper clean "下载目录\玄鉴仙族" --mode auto --save
```

命令行默认只生成报告，必须显式添加 `--save` 才会保存清洗版。

清洗规则默认位于 `src/novel_scraper/resources/config/`：

- `ad_rules.json`：网站推广、URL 和广告关键词规则。
- `whitelist.json`：如果正常正文被误报，把相关短语加入白名单。
- `traditional_map.json`：用于报告繁简体异常的保守映射。

可以通过 `--config-dir 自定义目录` 覆盖默认规则：

```powershell
.\.venv\Scripts\python.exe -m novel_scraper clean "下载目录\玄鉴仙族" --mode auto --save --config-dir .\config
```

保守原则：

- 广告按段落判断，不因为出现“微信”“网站”等单个词就删除整段。
- 标点只在中文上下文中修复，不修改英文句子、URL 和数字。
- `！！`、`？？？` 等可能是作者表达的内容不会被自动删除。
- 繁体字只有在全文风格和上下文证据明确时才自动修正，专有名词默认保留。
- 程序不会做通用错别字猜测，无法确定的问题只写报告。

人工审核窗口：

- 左侧列表按章节显示自动修改总数及标点、广告和其他问题数量。
- 鼠标悬停章节或修改行会显示原文、修改后和原因。
- 右侧逐条列出原文与修改后内容，可取消任意修改。
- 点击“应用审核结果”后重新生成 `cleaned/`，原始 `chapters/` 不变。
- 审核决定保存在 `reports/review_decisions.json`。

## 并发下载

默认使用 5 个工作线程并发抓取不同章节。分页仍在线程内部按顺序处理，不对单个章节的多个页面并发请求，避免增加网站压力。

- GUI 可以在“并发线程”中选择 1、3、5、8、10。
- 默认线程数：5。
- 所有线程共享随机请求间隔，默认约 0.2～0.4 秒，避免多个线程同时突发请求。
- 主线程按章节索引顺序接收和保存结果，合并 TXT 不会乱序。
- 单章失败只记录该章节，其他线程继续抓取。
- 已完成章节仍按断点状态跳过。

真实站点基准（得奇小说网前 100 章，0.03 秒基础间隔、0.03 秒抖动、关闭重试）：单线程 108.66 秒，5 线程 18.26 秒，约 5.95 倍加速。CLI 参数：

- `--workers 5`：并发章节线程数，限制为 1～10。
- `--jitter 0.2`：每个请求随机额外等待的上限。
- `--delay 0.2`：请求间隔基础值。

## 重复章节检测与倒序下载

下载默认开启跨章节正文去重。程序会计算每个章节正文的 SHA-256；正文完全相同的章节只保存第一次出现的内容，并在 `duplicate_chapters.txt` 中记录后续重复 URL、首次出现章节和正文哈希。

如果小说目录在后期出现大量重复章节，可以勾选“从最新章节向前下载”。程序会先抓最新章节，再向前抓取；合并 TXT 仍按小说目录顺序输出，不会倒序排列。

命令行参数：

- 默认：启用正文哈希去重
- `--no-deduplicate`：关闭正文去重
- `--reverse`：从选中范围的最后一章向前下载

```powershell
python -m novel_scraper crawl "https://www.deqixs.cc/books/51/" --reverse
```

## 广告黑名单

如果检测后仍然看到未清理的广告，可以把它加入用户广告黑名单。黑名单会持久化保存，不会写入 Git 仓库。

桌面端有两种加入方式：

1. 在“内容检测/清洗”窗口点击“广告黑名单”，从剪贴板粘贴完整广告文本。
2. 在“人工审核自动修改”窗口下方的差异预览中选中广告文本，点击“选中文本加入黑名单”。

检测时不会简单做关键词匹配，而是会：

- 去除空格、标点和 HTML 后做标准化
- 使用序列相似度和字符片段重合度比较
- 高度重合时自动删除
- 中等重合时只报告，不修改

默认黑名单文件：

```text
%APPDATA%\NovelScraper\ad_blacklist.json
```

黑名单删除操作也会记录在清洗日志中，规则名称为 `user_ad_blacklist`。

## 命令行版本

桌面版和命令行版共用同一个爬虫核心，也可以继续使用 CLI：

```powershell
python -m novel_scraper chapters "https://www.deqixs.cc/books/99/"
python -m novel_scraper chapter "https://www.deqixs.cc/books/99/63332.html"
python -m novel_scraper crawl "https://www.deqixs.cc/books/99/" --from-chapter 100 --to-chapter 200 --delay 0.2
```

常用参数：

- `--delay 1.0`：请求之间的最短间隔秒数。
- `--retries 3`：网络失败后的额外重试次数。
- `--max-pages 100`：单章最大分页数，防止异常页面导致无限循环。
- `--from-chapter 100`：从标题中的第 100 章开始（包含）。
- `--to-chapter 200`：抓到标题中的第 200 章结束（包含）。
- `--limit 3`：从选定范围中最多处理前 N 章，适合联调。
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
├── storage.py      TXT、状态和失败记录
└── text_cleaner/   内容检测、保守清洗和报告
```

## 合规说明

请合理设置请求频率，仅用于个人学习、备份和已获授权的内容。不要使用本工具绕过付费、权限或访问控制，并遵守目标网站的服务条款和适用法律。

## 安全与隐私

- `.env`、`.env.*`、Token、私钥、证书、`secrets.json` 和 `credentials.json` 已加入 `.gitignore`。
- 下载内容、虚拟环境、构建目录和日志不会提交到 Git。
- 程序不会在项目代码中保存 GitHub 登录 Token；本机 GitHub 凭据由 Git Credential Manager 管理。
