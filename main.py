'''
This programm is designed to parse amazon pages
to get a list of products and then save them and
their variants to a json file.
'''

from scraper.fetch_page import get_playwright_html
from scraper.detect import ProductCardDetector
from scraper.parse import extract_query_keywords
from scraper.variant_collector import get_variants, extract_data

from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Union
import json
import glob
from collections import Counter


# url = "https://www.amazon.com/s?k=python+programming&language=en_US"
# url = "https://www.amazon.com/Notebooks-Laptop-Computers/b?ie=UTF8&node=565108"
# url = "https://www.amazon.com/Headphones-Headsets/s?k=Headphones+and+Headsets"


def run_scraper(
        pass_num: int,
        url: str):
    html: str = get_playwright_html(url=url)
    soup = BeautifulSoup(html, features="html.parser")

    detector = ProductCardDetector(extract_query_keywords(url=url), soup)
    products: List[
        Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]]]] = detector.get_all_product_cards()

    # Get variants
    for product in products:
        try:
            if (link := product.get('link')):
                variants: List[Dict[str, Optional[str]]] = get_variants(
                    str(link), extract_data)
            else:
                variants = []
        except Exception as e:
            print(f"Error getting variants for {product['link']}: {e}")
            variants = []

        product['variants'] = variants

    # Save products and their variants
    with open(f"outputs/run{pass_num}.json", "w") as f:
        json.dump(products, f, indent=4)

    print(f"Found {len(products)} products.")


def generate_stats(
        all_runs_asins: List[List[str]],
        num_passes: int):
    try:

        # flat list of all asins
        all_asins_flat = [asin for run in all_runs_asins for asin in run]

        # count the asins
        asins_counts = Counter(all_asins_flat)

        # unique asins
        unique_asins = len(asins_counts)

        # avg asins
        avg_asins = sum(len(run) for run in all_runs_asins) / num_passes

        # max asins
        max_asins = max(len(run) for run in all_runs_asins)

        # min asins
        min_asins = min(len(run) for run in all_runs_asins)

        # count of asins seen once
        asins_seen_once = sum(1 for count in asins_counts.values() if count == 1)

        # count of asins seen everytime
        asins_seen_everytime = sum(1 for count in asins_counts.values() if count == num_passes)

        # list of asins seen once
        seen_once_asins_list = [asin for asin, count in asins_counts.items() if count == 1]

        # list of asins seen everytime
        seen_everytime_asins_list = [asin for asin, count in asins_counts.items() if count == num_passes]

        # Generate file
        stats_dict = {
            "unique_asins": unique_asins if unique_asins else 0,
            "avg_asins": avg_asins,
            "max_asins": max_asins,
            "min_asins": min_asins,
            "asins_seen_once": asins_seen_once,
            "asins_seen_everytime": asins_seen_everytime,
            "seen_once_asins_list": seen_once_asins_list if seen_once_asins_list else [],
            "seen_everytime_asins_list": seen_everytime_asins_list if seen_everytime_asins_list else []
        }

    except Exception as e:
        print(f"Error generating stats: {e}")
        stats_dict = {
            "unique_asins": 0,
            "avg_asins": 0,
            "max_asins": 0,
            "min_asins": 0,
            "asins_seen_once": 0,
            "asins_seen_everytime": 0,
            "seen_once_asins_list": [],
            "seen_everytime_asins_list": []
        }
    # Save the stats to a json file
    with open("outputs/stats.json", "w") as f:
        json.dump(stats_dict, f, indent=4)
    print(f"Stats generated and saved to outputs/stats.json")


def main():
    url = "https://www.amazon.com/Headphones-Headsets/s?k=Headphones+and+Headsets"
    num_passes = 3

    for i in range(1, num_passes + 1):
        print(f"Running pass {i} of {num_passes}...")
        print()
        run_scraper(i, url)

    all_runs_asins: List[List[str]] = []
    seen_asins = set()
    all_products: List[Dict[str, Union[Optional[str], bool]]] = []
    # all_products: list[dict[str, (str | None) | bool]]

    for file_path in glob.glob("outputs/run*.json"):
        with open(file_path, 'r') as f:
            products = json.load(f)

            for p in products:
                if p.get('asin') and p['asin'] not in seen_asins:
                    seen_asins.add(p['asin'])
                    all_products.append(p)

            asins = [p['asin'] for p in products if p.get('asin')]
            all_runs_asins.append(asins)

    generate_stats(all_runs_asins, num_passes)


if __name__ == "__main__":
    main()
