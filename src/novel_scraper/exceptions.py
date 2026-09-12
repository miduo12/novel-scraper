class ScraperError(Exception):
    """项目内所有可预期错误的基类。"""


class FetchError(ScraperError):
    """网络请求失败。"""


class ParseError(ScraperError):
    """网页结构无法解析。"""


class UnsupportedSiteError(ScraperError):
    """当前没有适配该网站。"""


class ChapterContentError(ScraperError):
    """章节正文为空或无法获取。"""


class CrawlCancelled(ScraperError):
    """用户主动停止抓取。"""
