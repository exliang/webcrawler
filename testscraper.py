import scraper

class DummyResponse:
    def __init__(self, url):
        self.url = url

# Clear the stats set first for testing
scraper.stats["unique_pgs"] = set()

# Test URLs
urls = [
    "http://www.ics.uci.edu/page1.html#section1",
    "http://www.ics.uci.edu/page1.html#section2",  # same page, different fragment
    "http://www.ics.uci.edu/page2.html",
    "http://www.cs.uci.edu/page1.html",
    "http://www.cs.uci.edu/page1.html",
    "http://www.cs.uci.edu/page1.html/",
    "",        # empty string
    None       # None value
]

# Call the function on each URL
for url in urls:
    resp = DummyResponse(url)
    # Only check non-empty, non-None URLs
    if scraper.is_valid(url):
        print("Valid URL:", url)
        scraper.find_unique_pages(resp)

# Check results
print("\nUnique pages found:", len(scraper.stats["unique_pgs"]))
print(scraper.stats["unique_pgs"])
