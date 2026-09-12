from pathlib import Path

from novel_scraper.models import Book, Chapter
from novel_scraper.storage import BookStorage


def test_storage_checkpoint_and_combined_txt(tmp_path: Path) -> None:
    chapter = Chapter(index=1, title="第1章 开始", url="https://example.com/1.html")
    book = Book(
        title="测试小说",
        author="作者",
        description="",
        source_url="https://example.com/book/",
        chapters=(chapter,),
    )
    storage = BookStorage(tmp_path, book)
    state = storage.load_state()

    storage.save_chapter(chapter, "正文")
    storage.mark_completed(state, chapter)
    output = storage.build_combined_txt()

    assert chapter.url in storage.load_state().completed
    assert output.read_text(encoding="utf-8").startswith("测试小说")
    assert "第1章 开始\n\n正文" in output.read_text(encoding="utf-8")
