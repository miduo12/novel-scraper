from novel_scraper.adapters import adapter_for_url, is_supported_url
from novel_scraper.adapters.sudugu import SuduguAdapter

BOOK_HTML = """
<!doctype html>
<html>
<head><title>阵问长生-速读谷-观虚小说-最新章节无错字免费阅读</title></head>
<body>
<h1>万字 阵问长生</h1>
<a href="/modules/article/authorarticle.php?author=x">作者：观虚</a>
<div class="des">修真证道，悟阵飞仙。</div>
<div id="list"><ul>
<li><a href="https://www.sudugu.cc/674/555753.html">第1章 墨画</a></li>
<li><a href="https://www.sudugu.cc/674/555754.html">第2章 道碑</a></li>
</ul></div>
</body>
</html>
"""

PAGE_1 = """
<html><head><title>阵问长生 第1章 墨画（1 / 2）-速读谷</title></head>
<body><h1>阵问长生 > 第1章 墨画（1 / 2）</h1>
<div class="con">第1章 墨画<br><br>第一页正文。<br></div>
<div class="prenext"><a href="/674/555753_2.html">下一页</a></div>
</body></html>
"""

PAGE_2 = """
<html><head><title>阵问长生 第1章 墨画（2 / 2）-速读谷</title></head>
<body><h1>阵问长生 > 第1章 墨画（2 / 2）</h1>
<div class="con">第二页正文。<br></div>
<div class="prenext"><a href="/674/555754.html">下一章</a></div>
</body></html>
"""


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_text(self, url: str, **_kwargs: object) -> str:
        self.calls.append(url)
        if url.endswith("_2.html"):
            return PAGE_2
        return PAGE_1


def test_sudugu_is_registered() -> None:
    assert is_supported_url("https://www.sudugu.cc/674/")
    assert adapter_for_url("https://www.sudugu.cc/674/", FakeHttp()).name == "sudugu"


def test_parse_sudugu_book_and_chapters() -> None:
    adapter = SuduguAdapter(FakeHttp())
    book = adapter.parse_book(BOOK_HTML, "https://www.sudugu.cc/674/")

    assert book.title == "阵问长生"
    assert book.author == "观虚"
    assert len(book.chapters) == 2
    assert book.chapters[0].number == 1
    assert book.chapters[1].url == "https://www.sudugu.cc/674/555754.html"


def test_normalize_sudugu_page_url() -> None:
    adapter = SuduguAdapter(FakeHttp())
    assert (
        adapter.normalize_book_url("https://www.sudugu.cc/674/555753_2.html")
        == "https://www.sudugu.cc/674/"
    )
    assert adapter.parse_chapter_title(PAGE_2) == "第1章 墨画"


def test_fetch_all_sudugu_pages() -> None:
    http = FakeHttp()
    adapter = SuduguAdapter(http)
    book = adapter.parse_book(BOOK_HTML, "https://www.sudugu.cc/674/")
    pages = adapter.fetch_chapter_pages(book.chapters[0], max_pages=10)

    assert len(pages) == 2
    assert pages[0].content == "第一页正文。"
    assert pages[1].content == "第二页正文。"
    assert http.calls == [
        "https://www.sudugu.cc/674/555753.html",
        "https://www.sudugu.cc/674/555753_2.html",
    ]
