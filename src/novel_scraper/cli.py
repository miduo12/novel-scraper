from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .crawler import CrawlOptions, NovelCrawler
from .exceptions import ScraperError

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novel-scraper",
        description="得奇小说网桌面爬虫的核心命令行程序",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别，默认 INFO",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", type=Path, default=Path("downloads"), help="输出目录")
    common.add_argument("--delay", type=float, default=1.0, help="请求之间的最短间隔秒数")
    common.add_argument("--timeout", type=float, default=20.0, help="单次请求超时秒数")
    common.add_argument("--retries", type=int, default=3, help="失败后的额外重试次数")
    common.add_argument("--max-pages", type=int, default=100, help="单个章节的最大分页数")

    chapters = subparsers.add_parser("chapters", parents=[common], help="解析并打印完整章节目录")
    chapters.add_argument("url", help="小说目录 URL 或章节 URL")

    chapter = subparsers.add_parser("chapter", parents=[common], help="抓取一个章节的全部分页")
    chapter.add_argument("url", help="章节 URL")

    crawl = subparsers.add_parser("crawl", parents=[common], help="抓取整本小说并生成 TXT")
    crawl.add_argument("url", help="小说目录 URL 或章节 URL")
    crawl.add_argument("--limit", type=int, default=None, help="最多处理前 N 章，便于测试")
    crawl.add_argument("--force", action="store_true", help="忽略断点，重新抓取指定章节")

    return parser


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def setup_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper()),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.log_level)

    try:
        if args.command == "chapters":
            with NovelCrawler.from_url(args.url, _options(args)) as crawler:
                book = crawler.list_chapters(args.url)
                print(f"《{book.title}》 作者：{book.author or '未知'}，共 {len(book.chapters)} 章")
                for chapter in book.chapters:
                    print(f"{chapter.index:04d}\t{chapter.title}\t{chapter.url}")
            return 0

        if args.command == "chapter":
            with NovelCrawler.from_url(args.url, _options(args)) as crawler:
                crawler.crawl_single_chapter(args.url)
            return 0

        if args.command == "crawl":
            with NovelCrawler.from_url(args.url, _options(args)) as crawler:
                crawler.crawl_book(args.url)
            return 0
    except KeyboardInterrupt:
        logger.warning("用户中断，已保存现有断点")
        return 130
    except (ScraperError, OSError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error("未知命令")
    return 2


def _options(args: argparse.Namespace) -> CrawlOptions:
    return CrawlOptions(
        output_dir=args.output,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        max_pages=args.max_pages,
        limit=getattr(args, "limit", None),
        force=getattr(args, "force", False),
    )


if __name__ == "__main__":
    sys.exit(main())
