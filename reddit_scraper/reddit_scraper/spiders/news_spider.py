import scrapy

class NewsSpider(scrapy.Spider):
    name = "news_spider"
    allowed_domains = ["theguardian.com"]
    start_urls = ["https://www.theguardian.com/international"]

    def __init__(self, keyword=None, *args, **kwargs):
        super(NewsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword  # Pass keyword from the main program

    def parse(self, response):
        for article in response.css("a[data-link-name='article']"):
            title = article.css("::text").get()
            url = response.urljoin(article.attrib.get("href"))

            # Check if the keyword exists in the title
            if self.keyword and self.keyword.lower() in (title or "").lower():
                yield {
                    "title": title,
                    "url": url,
                }
