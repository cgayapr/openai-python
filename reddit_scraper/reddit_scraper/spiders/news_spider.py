import scrapy
import logging
from scrapy.crawler import CrawlerProcess
from difflib import SequenceMatcher

class NewsSpider(scrapy.Spider):
    name = "news_spider"
    allowed_domains = ["theguardian.com"]
    start_urls = ["https://www.theguardian.com"]

    def __init__(self, keyword=None, *args, **kwargs):
        super(NewsSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword  # Pass keyword from the main program
        if self.keyword:
            self.log(f"Initialized NewsSpider with keyword: {self.keyword}", level=logging.INFO)

    def is_match(self, keyword, text, threshold=0.7):
        """Check if keyword partially matches the text with a given threshold."""
        return SequenceMatcher(None, keyword.lower(), text.lower()).ratio() >= threshold

    def parse(self, response):
        # Debug: Log the URL being parsed
        self.log(f"Parsing URL: {response.url}", level=logging.INFO)

        articles_found = False  # Track if any articles are found
        articles_checked = 0  # Count the number of articles checked

        # Extract articles
        for article in response.css("a[data-link-name='article']"):
            articles_checked += 1
            title = article.css("::text").get() or "No Title Found"
            url = response.urljoin(article.attrib.get("href") or "#")

            # Debug: Log the extracted article details
            self.log(f"Checking article - Title: {title}, URL: {url}", level=logging.DEBUG)

            # Check for matches
            if self.keyword and self.is_match(self.keyword, title):
                articles_found = True
                result = {"title": title.strip(), "url": url.strip()}
                self.log(f"Yielding article matching keyword - {result}", level=logging.INFO)
                yield result

        # Debug: Log if no articles match the keyword
        if not articles_found and articles_checked > 0:
            self.log(
                f"Checked {articles_checked} articles but found no matches for keyword: {self.keyword}",
                level=logging.WARNING
            )
        elif articles_checked == 0:
            self.log(f"No articles found on the page to check.", level=logging.WARNING)


def run_spider():
    # Ask the user for a keyword
    keyword = input("Enter a keyword to search for articles: ").strip()
    if not keyword:
        print("Error: Keyword cannot be empty. Please try again.")
        return

    # Initialize the Scrapy crawler process
    process = CrawlerProcess(settings={
        "FEEDS": {"output.json": {"format": "json"}},  # Save results to output.json
        "LOG_LEVEL": "DEBUG",  # Display detailed logs for debugging
    })

    # Run the spider with the given keyword
    process.crawl(NewsSpider, keyword=keyword)
    process.start()
    print("Spider finished running. Results saved to 'output.json'.")


# Main execution block
if __name__ == "__main__":
    run_spider()
