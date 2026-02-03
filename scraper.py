import re, utils, string, hashlib
from urllib.parse import urlparse, urldefrag, urljoin
from bs4 import BeautifulSoup

# dict to keep track of stat values
stats = {
    "unique_pgs": set(),
    "longest_page": ("", 0), #(url, wordcount)
    "word_counts": {}, #{word: count}
    "subdomains": {}, #{subdomain: unqiuepages}
    "seen_fingerprints": set()
}

# load stopwords once
def load_stopwords(path: str):
    with open(path, "r", encoding="utf-8") as file:
        return {word.strip() for word in file}
STOP_WORDS = load_stopwords("stopwords.txt")


def scraper(url: str, resp: utils.response.Response) -> list:
    """
    url: the URL that was added to the frontier, and downloaded from the cache
        (type str and was an url that was previously added to the frontier)
    resp: response given by the caching server for the requested URL 
        (an object of type Response)
    """
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        # extract pg's text
        html = BeautifulSoup(resp.raw_response.content, "html.parser")
        pg_text = html.get_text(separator=" ")

        # detect & avoid sets of similar pgs w no info (exact duplicates) #TODO: need to check near-dupes too?
        pg_fingerprint = hashlib.md5(pg_text.encode("utf-8")).hexdigest()
        sf = stats["seen_fingerprints"]
        if pg_fingerprint in sf: # detected similar pg
            return []
        sf.add(pg_fingerprint)

        # TODO: detect & avoid crawling very large files (esp if they hv low info value)

        # for finding num of unique pgs (remove fragment & add url to set)
        find_unique_pages(resp)

        # for finding longest pg word-wise (extract only text from html)
        find_longest_page(url, resp)

        # for finding 50 most common words 
        update_word_counts(pg_text)

    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url: str, resp: utils.response.Response) -> list:
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
            
            # Normalize URLs (so that every href str is following same url format)
            absolute_url = urljoin(resp.url, link) # join relative URLs to base URL
            absolute_url = urldefrag(absolute_url)[0] # remove fragment from link
            hyperlinks.append(absolute_url) # add normalized url to list
        
    return hyperlinks

def is_valid(url: str) -> bool:
    """Decides whether a URL should be crawled. Returns True if the URL is valid, False otherwise."""
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    # NOTE: returns only URLs that are within the domains and paths mentioned in assignment
    # (ex: https://www.ics.uci.edu/ & https://ics.uci.edu/ both valid)
    try:
        parsed = urlparse(url)

        # Valid for only http/https
        if parsed.scheme not in set(["http", "https"]):
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
        if not any (parsed.hostname.endswith(domain) for domain in allowed_domains):
            return False

        # Check for bad files (#TODO: may be more)
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf|txt" # added txt
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        
        # Check for traps
        #TODO

        return True

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def find_unique_pages(resp: utils.response.Response) -> None:
    # for finding num of unique pgs (remove fragment & add url to set)
    unfragmented_url = urldefrag(resp.url)[0]
    stats["unique_pgs"].add(unfragmented_url)

def find_longest_page(url: str, resp: utils.response.Response) -> None:
    # for finding longest pg word-wise (extract only text from html)
    html = BeautifulSoup(resp.raw_response.content, 'html.parser')
    text = html.get_text(separator=" ") # split words by space for effective counting
    num_words = len(text.split())
    if num_words > stats["longest_page"][1]: 
        stats["longest_page"] = (resp.url, num_words)

def tokenize(text: str) -> list:
    """Helper func for find_word_counts()"""
    # end --> end
    # (.word) --> word
    # don't --> don't (keep punc in the middle of the word)
    # convert to lowercase & remove punctuation at front and end of word (word alr slit by space)
    return [word.lower().strip(string.punctuation) for word in text.split() if word.strip(string.punctuation)]

def update_word_counts(text: str) -> None:
    tokens = tokenize(text)
    for token in tokens: 
        if token and token not in STOP_WORDS:
            stats["word_counts"][token] = stats["word_counts"].get(token, 0) + 1


# NOTE: run these at the end once the crawler is done for the report
def find_50_most_common_words() -> list:
    return sorted(stats["word_counts"].items(), key=lambda x: x[1], reverse=True)

def find_total_subdomains() -> list:
    # for finding num of subdomains 
    unique_pgs = stats["unique_pgs"]
    for url in unique_pgs:
        parsed_url = urlparse(url)
        domain = parsed_url.hostname #doesn't include the port
        if domain and domain.endswith("uci.edu"):
            stats["subdomains"][domain] = stats["subdomains"].get(domain, 0) + 1
    return sorted(stats["subdomains"].items())

# print(len(stats["unique_pgs"]))
# print(stats["longest_page"][0])
# print(find_50_most_common_words())
# print(find_total_subdomains())) #only call once or counts will accumulate


# Sources:
# - https://beautiful-soup-4.readthedocs.io/en/latest/#quick-start
# - https://docs.python.org/3/library/urllib.parse.html
# - https://docs.python.org/3/library/hashlib.html