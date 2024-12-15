import scrapy
import logging
import spacy

class MultiSourceSpider(scrapy.Spider):
    name = "multi_source_spider"

    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [403, 429, 500, 502, 503, 504],
    }

    allowed_domains = [
        "bbc.com",
        "theguardian.com",
        "reuters.com",
        "forbes.com",
        "businessinsider.com",
        "cnbc.com",
        "techcrunch.com",
        "wired.com",
        "venturebeat.com",
        "practicalecommerce.com",
        "ecommercetimes.com",
        "digitalcommerce360.com",
        "supplychaindive.com",
    ]

    start_urls = [
        "https://www.theguardian.com/business",
        "https://www.bbc.com/news/business",
        "https://www.reuters.com/business",
        "https://www.forbes.com/ecommerce/",
        "https://www.businessinsider.com",
        "https://www.cnbc.com/retail/",
        "https://techcrunch.com/startups/",
        "https://www.wired.com/category/business/",
        "https://venturebeat.com/category/ecommerce/",
        "https://www.practicalecommerce.com/",
        "https://www.ecommercetimes.com/",
        "https://www.digitalcommerce360.com/",
        "https://www.supplychaindive.com/",
    ]

    def __init__(self, keyword=None, *args, **kwargs):
        super(MultiSourceSpider, self).__init__(*args, **kwargs)
        self.keyword = keyword.lower() if keyword else "default"
        self.nlp = spacy.load("en_core_web_sm")
        self.log(f"Spider initialized with keyword: {self.keyword}", level=logging.INFO)

    def parse(self, response):
        """
        General parsing logic for articles.
        """
        if response.status in [403, 401]:
            self.log(f"Access denied for {response.url}", level=logging.WARNING)
            return

        articles_checked = 0
        matches_found = 0
        self.log(f"Scraping {response.url} for keyword: {self.keyword}", level=logging.INFO)

        keyword_doc = self.nlp(self.keyword)  # Convert the keyword to a spaCy Doc object
        similarity_threshold = 0.7  # Set a similarity threshold for fuzzy matching

        for article in response.css("a"):
            articles_checked += 1

            # Combine all text within the <a> tag to form a meaningful title
            title = " ".join(article.css("*::text").getall()).strip()

            if not title:  # Skip if no meaningful text is found
                continue

            url = response.urljoin(article.attrib.get("href", ""))

            # Compute similarity using spaCy
            title_doc = self.nlp(title)
            similarity_score = keyword_doc.similarity(title_doc)

            # Include articles that meet the threshold
            if similarity_score >= similarity_threshold:
                matches_found += 1
                self.log(
                    f"Including article - Title: {title}, URL: {url}, Similarity Score: {similarity_score:.2f}",
                    level=logging.INFO,
                )
                yield {
                    "title": title,
                    "url": url,
                    "similarity_score": similarity_score,
                    "reason": f"Similarity score ({similarity_score:.2f}) >= threshold ({similarity_threshold:.2f})",
                }

        # Log summary for the page
        if matches_found == 0:
            self.log(f"No matches found for keyword '{self.keyword}' in {articles_checked} articles on {response.url}.", level=logging.WARNING)
        else:
            self.log(f"Found {matches_found} matches out of {articles_checked} articles on {response.url}.", level=logging.INFO)

            """
            General parsing logic for articles.
            """
            if response.status in [403, 401]:
                self.log(f"Access denied for {response.url}", level=logging.WARNING)
                return

            articles_checked = 0
            matches_found = 0
            self.log(f"Scraping {response.url} for keyword: {self.keyword}", level=logging.INFO)

            keyword_doc = self.nlp(self.keyword)  # Convert the keyword to a spaCy Doc object
            similarity_threshold = 0.7  # Set a similarity threshold for fuzzy matching

            for article in response.css("a"):
                articles_checked += 1
                title = " ".join(article.css("::text").getall()).strip()
                url = response.urljoin(article.attrib.get("href", ""))

                # Log every article being checked
                self.log(f"Checking article - Title: {title}, URL: {url}", level=logging.DEBUG)

                # Use spaCy to compute similarity
                title_doc = self.nlp(title)
                similarity_score = keyword_doc.similarity(title_doc)

                if similarity_score >= similarity_threshold:
                    matches_found += 1
                    yield {
                        "title": title.strip(),
                        "url": url.strip(),
                        "similarity_score": similarity_score,
                    }

            if matches_found == 0:
                self.log(f"No matches found for keyword '{self.keyword}' in {articles_checked} articles on {response.url}.", level=logging.WARNING)
