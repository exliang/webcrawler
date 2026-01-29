import re, utils
from urllib.parse import urlparse, urldefrag, urljoin
from bs4 import BeautifulSoup

# dict to keep track of stat values
stats = {
    "unique_pgs": set(),
    "longest_page": ("", 0), #(url, wordcount)
}

def scraper(url: str, resp: utils.response.Response) -> list:
    """
    url: the URL that was added to the frontier, and downloaded from the cache
        (type str and was an url that was previously added to the frontier)
    resp: response given by the caching server for the requested URL 
        (an object of type Response)
    """
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        # for finding num of unique pgs (remove fragment & add url to set)
        unfragmented_url = urldefrag(resp.url)[0]
        stats["unique_pgs"].add(unfragmented_url)

        # for finding longest pg word-wise (extract only text from html) NOTE: might need to edit tokenizer func instead since some words include punc
        html = BeautifulSoup(resp.raw_response.content, 'html.parser')
        text = html.get_text(separator=" ") # split words by space for effective counting
        num_words = len(text.split())
        if num_words > stats["longest_page"][1]: 
            stats["longest_page"] = (url, num_words)

        # TODO: for finding 50 most common words 
        # edit tokenizer method?

        # TODO: for finding num of subdomains


    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url: str, resp: utils.response.Response) -> list: #emily
    """ Extracts all hyperlinks from a page's HTML content and returns them as a list of strings.
        Args:
            url - the URL that was used to get the page
            resp - response from server
        Returns: a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    """
    # resp.url: the actual url of the page (final url that got fetched)
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    
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


def is_valid(url: str) -> bool: #kay
    """Decides whether a URL should be crawled. Returns True if the URL is valid, False otherwise."""
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    # NOTE: returns only URLs that are within the domains and paths mentioned in assignment
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise



# Sources:
# - https://beautiful-soup-4.readthedocs.io/en/latest/#quick-start
# - https://docs.python.org/3/library/urllib.parse.html