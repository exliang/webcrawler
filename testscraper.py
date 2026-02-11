# File to get and print statistics from stats.json after crawling

import json
import scraper

# Load stats from your saved JSON
with open("stats.json", "r", encoding="utf-8") as f:
    loaded_stats = json.load(f)
    
scraper.stats.update(loaded_stats)
print(len(scraper.stats["unique_pgs"]))
print(scraper.stats["longest_page"][0])
print(scraper.stats["longest_page"][1])
print(scraper.find_50_most_common_words())
print(scraper.find_total_subdomains()) #only call once or counts will accumulate
print(len(scraper.find_total_subdomains())) #num subdomains

for word, count in scraper.find_50_most_common_words():
    print(word, count)

for word, count in scraper.find_total_subdomains():
    print(word + ",", count)