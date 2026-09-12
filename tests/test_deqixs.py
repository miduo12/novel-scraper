from novel_scraper.adapters.deqixs import DeqixsAdapter

BOOK_HTML = """
<!doctype html>
<html>
<head>
  <meta property="og:novel:book_name" content="测试小说" />
  <meta property="og:novel:author" content="测试作者" />
</head>
<body>
  <h1 class="booktitle">测试小说</h1>
  <div id="list-chapterAll">
    <dd><a href="/books/99/62182.html">第1章 开始</a></dd>
    <dd><a href="/books/99/62183.html">第2章 继续</a></dd>
  </div>
</body>
</html>
"""

CHAPTER_HTML = """
<!doctype html>
<html>
<head><meta property="og:title" content="测试小说_第1章 开始_得奇小说网" /></head>
<body>
  <h1 class="pt10"> 第1章 开始(第/页)</h1>
  <div class="readcontent" id="rtext">
    <div id="chapter-content"></div>
  </div>
  <script src="/scripts/chapter.js.php?aid=99&amp;cid=62182&amp;referrer=x"></script>
</body>
</html>
"""

SCRIPT_JS = (
    "var chapterToken = 'token123';\nvar timestamp = 1789225625000;\nvar nonce = 'abc123';\n"
)

API_PAYLOAD = {
    "status": 1,
    "message": "获取成功",
    "data": {
        "content": "第1章 开始<br /><br />第一段<br /><br />第二段",
    },
}


class FakeHttp:
    def __init__(self) -> None:
        self.text_calls: list[str] = []
        self.json_calls: list[str] = []

    def get_text(self, url: str, **_kwargs: object) -> str:
        self.text_calls.append(url)
        if "chapter.js.php" in url:
            return SCRIPT_JS
        return CHAPTER_HTML

    def get_json(self, url: str, **_kwargs: object) -> dict[str, object]:
        self.json_calls.append(url)
        return API_PAYLOAD


def test_parse_book_and_chapters() -> None:
    adapter = DeqixsAdapter(FakeHttp())
    book = adapter.parse_book(BOOK_HTML, "https://www.deqixs.cc/books/99/")

    assert book.title == "测试小说"
    assert book.author == "测试作者"
    assert len(book.chapters) == 2
    assert book.chapters[0].url == "https://www.deqixs.cc/books/99/62182.html"


def test_parse_chapter_title() -> None:
    adapter = DeqixsAdapter(FakeHttp())
    assert adapter.parse_chapter_title(CHAPTER_HTML) == "第1章 开始"


def test_fetch_chapter_pages_uses_single_complete_api_request() -> None:
    http = FakeHttp()
    adapter = DeqixsAdapter(http)
    book = adapter.parse_book(BOOK_HTML, "https://www.deqixs.cc/books/99/")
    pages = adapter.fetch_chapter_pages(book.chapters[0], max_pages=10)

    assert len(pages) == 1
    assert pages[0].content == "第一段\n\n第二段"
    assert len(http.json_calls) == 1
