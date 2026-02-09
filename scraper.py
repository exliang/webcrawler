import re, string, json, os
from urllib.parse import urlparse, urldefrag, urljoin
from bs4 import BeautifulSoup
from utils.response import Response

# dict to keep track of stat values
stats = {
    "unique_pgs": set(),
    "longest_page": ("", 0), #(url, wordcount)
    "word_counts": {}, #{word: count}
    "subdomains": {}, #{subdomain: unqiuepages}
}

# load stopwords once
def load_stopwords(path: str):
    with open(path, "r", encoding="utf-8") as file:
        return {word.strip() for word in file}
STOP_WORDS = load_stopwords("stopwords.txt")

def scraper(url: str, resp: Response) -> list:
    """
    url: the URL that was added to the frontier, and downloaded from the cache
        (type str and was an url that was previously added to the frontier)
    resp: response given by the caching server for the requested URL 
        (an object of type Response)
    """
    print(f"Status: {resp.status}, Has content: {resp.raw_response is not None}")

    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        # extract pg's text
        html = BeautifulSoup(resp.raw_response.content, "html.parser", from_encoding='utf-8') # encoding to handle char encoding errors
        pg_text = html.get_text(separator=" ")

        # detect & avoid sets of similar pgs w no info (pgs w barely any content)
        if len(pg_text.split()) < 50: # defined threashold < 50 words
            return []

        # detect & avoid crawling very large files esp if they hv low info value
        MAX_FILE_SIZE = 1_000_000 # 1 MB
        if len(resp.raw_response.content) > MAX_FILE_SIZE: # comparing size in bytes
            return []

        if is_valid(url): # only valid URLs for report
            # for finding num of unique pgs (remove fragment & add url to set)
            find_unique_pages(resp)

            # for finding longest pg word-wise (extract only text from html)
            find_longest_page(resp)

            # for finding 50 most common words 
            update_word_counts(pg_text)

        links = extract_next_links(url, resp)
        return [link for link in links if is_valid(link)]
    
    # handle cases where status code isn't 200, no content/responswe
    return []

def extract_next_links(url: str, resp: Response) -> list:
    """ Extracts all hyperlinks from a page's HTML content and returns them as a list of strings.
        Args:
            url - the URL that was used to get the page
            resp - response from server
        Returns: a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    """
    hyperlinks = [] # list to store all hyperlinks gathered 

    # check if response status isn't 200, raw_response doesn't exists, or content is empty
    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content: 
        return []

    # parse HTML
    html = BeautifulSoup(resp.raw_response.content, 'html.parser')

    # extract hyperlinks: <a href>
    for hyperlink in html.find_all('a'):
        link = hyperlink.get('href')
        if link: # prevents empty links
            link = link.strip() # get rid of uncessary white space

            # skip malformed/broken URLs
            if not link or "YOUR_IP" in link: #avoid valuerror
                continue

            try:
                # Normalize URLs (so that every href str is following same url format)
                absolute_url = urljoin(resp.url, link) # join relative URLs to base URL
                absolute_url = urldefrag(absolute_url)[0] # remove fragment from link
                absolute_url = absolute_url.lower() # make all lowercase for effective matching
                hyperlinks.append(absolute_url) # add normalized url to list
            except Exception: # catch & skip malformed URLs
                continue 
    
    print(f"Extracted {len(hyperlinks)} links, valid: ")
    for link in [link for link in hyperlinks if is_valid(link)]:
        print(link)
        
    return hyperlinks

def is_valid(url: str) -> bool: #kay
    """ Decides whether a URL should be crawled. Returns True if the URL is valid, False otherwise.
        Args:
            url - the URL to validate
        Returns: bool - True whether if URL should be crawled, False if otherwise
    """
    try:
        parsed = urlparse(url)

        # Valid for only http/https
        if parsed.scheme not in set(["http", "https"]):
            return False
        
        # if http or https appears twice --> malformed URL
        if parsed.path.count("http") > 0 or parsed.path.count("https") > 0:
            return False

        # Use hostname for domain
        if not parsed.hostname:
            return False

        # Valid for allowed domains
        allowed_domains = [
            "ics.uci.edu",
            "cs.uci.edu",
            "informatics.uci.edu",
            "stat.uci.edu"
        ]

        # Check if the domain matches the allowed domains
        if not any (parsed.hostname == domain or parsed.hostname.endswith("." + domain) for domain in allowed_domains):
            return False

        # Check for bad files (may be more)
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|img|tiff?|mid|mp2|mp3|mp4|mpg" # added mpg, img
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf|txt" # added txt
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names|ppsx|pps" # added ppsx, pps
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        
        # Check for infinite traps & low value/repetitive pages
        parsed_query = parsed.query.lower()
        calendar_pattern = re.compile(r"/(fall|spring|winter|summer)-\d{4}-week-\d+") # ex: fall-2025-week-3
        quarter_pattern = re.compile(r"/(fall|spring|winter|summer)-quarter-week-\d+") # ex: fall-quarter-week-3
        date_pattern = re.compile(r"/\d{4}([/-]\d{2}){2}$") # ex: 2025-2-06
        numerical_pattern = re.compile(r"/[a-z]+\d+\.html$") # ex: r25.html

        if "/events/" in parsed.path.lower() or "/event/" in parsed.path.lower() or calendar_pattern.search(parsed.path.lower()) \
            or date_pattern.search(parsed.path.lower()) or quarter_pattern.search(parsed.path.lower()) \
            or parsed.path.lower().endswith("week"): # calendar/event/date pattern 
            return False
        if "grape" in parsed.hostname: # grape.ics.uci.edu ton of low-value repetitive content
            return False
        if numerical_pattern.search(parsed.path.lower()): # numerical trap 
            return False
        if any(param in parsed_query for param in ['do=', 'idx=', 'id=', 'version=', 'from=', 'precision=', 'rev=']): # low info value & near-dupe pgs
            return False
        if 'requesttracker' in parsed_query or "/page/" in parsed.path.lower() or "junkyard" in parsed.path.lower(): # repeated query params, giving barely any new info
            return False
        if '/ml/datasets' in parsed_query or 'datasets' in parsed_query: # filter out large ML datasets
            return False
        if "/pub/" in parsed.path.lower() or "publications" in parsed.path.lower(): # low textual content
            return False
        if "~dechter/" in parsed.path.lower(): # pg not found and/or low value
            return False
        if len(url) > 200: # very long URLs (defined threashold > 200 chars)
            return False
        if url.count('?') > 1 or url.count('&') > 4: # lots of ? or &
            return False

        return True

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def find_unique_pages(resp: Response):
    """ Finds and tracks unique valid pages. Duplicate URLs are ignored.
        Args:
            resp - response from server
    """
    # for finding num of unique pgs (remove fragment & add url to set)
    unfragmented_url = urldefrag(resp.url)[0].lower().rstrip("/") # lowercase & remove trailing slash
    stats["unique_pgs"].add(unfragmented_url)

def find_longest_page(resp: Response):
    """ Finds the longest page based on word count.
        Compares the current page count to the current longest page count.
        Arg:
            url - the URL of the page
            resp - the response from server
    """
    # for finding longest pg word-wise (extract only text from html)
    html = BeautifulSoup(resp.raw_response.content, 'html.parser')
    text = html.get_text(separator=" ") # split words by space for effective counting
    num_words = len(text.split())
    if num_words > stats["longest_page"][1]: 
        stats["longest_page"] = (resp.url, num_words)

def tokenize(text: str):
    """Helper func for update_word_counts()
    Turns the raw text into a list of lowercase words and removes punctuation.
        Arg:
            text - the raw text taken from the HTML page
        Returns: a list of lowercase words
    """
    # end --> end
    # (.word) --> word
    # don't --> don't (keep punc in the middle of the word)
    # convert to lowercase & remove punctuation at front and end of word (word alr slit by space)
    return [word.lower().strip(string.punctuation) for word in text.split() if word.strip(string.punctuation)] # filter out empty strs

def update_word_counts(text: str):
    """ Updates the word count for each word on the page.
        Arg:
            text - the raw text taken from the HTML page
    """
    tokens = tokenize(text)
    for token in tokens: 
        token = token.strip()
        if token and len(token) > 1 and any(c.isalpha() for c in token) and token not in STOP_WORDS and not token.isnumeric(): # exclude numbers, char != word, no spaces, no special chars
            stats["word_counts"][token] = stats["word_counts"].get(token, 0) + 1


# NOTE: run these at the end once the crawler is done for the report
def find_50_most_common_words():
    """ Finds 50 most common words from all the pages crawled.
        Returns: list of tuples sorted by count
    """
    # returns
    return sorted(stats["word_counts"].items(), key=lambda x: x[1], reverse=True)[:50]

def find_total_subdomains() -> list:
    """ Finds all subdomains and counts how many unique pages are found.
        Groups unique pages by their subdomain.
        Returns: a list of tuples sorted alphabetically
    """
    # for finding num of subdomains
    unique_pgs = stats["unique_pgs"]
    for url in unique_pgs:
        parsed_url = urlparse(url)
        domain = parsed_url.hostname #doesn't include the port
        if domain and domain.endswith("uci.edu"):
            stats["subdomains"][domain] = stats["subdomains"].get(domain, 0) + 1
    return sorted(stats["subdomains"].items())

def save_stats_to_file(path="stats.json"):
    stats_to_save = {
        "unique_pgs": list(stats["unique_pgs"]),
        "longest_page": stats["longest_page"],
        "word_counts": stats["word_counts"],
        "subdomains": stats["subdomains"]
    }

    with open(path, "w", encoding="utf-8") as file:
        json.dump(stats_to_save, file, ensure_ascii=False, indent=4)

# print(len(stats["unique_pgs"]))
# print(stats["longest_page"][0])
# print(find_50_most_common_words())
# print(find_total_subdomains()) #only call once or counts will accumulate


# Documentation:
# - https://beautiful-soup-4.readthedocs.io/en/latest/#quick-start
# - https://docs.python.org/3/library/urllib.parse.html
# - https://docs.python.org/3/library/hashlib.html