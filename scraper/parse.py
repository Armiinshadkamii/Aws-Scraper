'''
In this file, we parse the target page to get
a list of products.
'''
import re
from bs4 import Tag, BeautifulSoup
from typing import Dict, Optional, Union, List
from urllib.parse import urlparse, parse_qs
import time, random

import scraper.fetch_page as fp


def extract_query_keywords(url):
    parsed = urlparse(url)
    query_dict = parse_qs(parsed.query)
    # "k" is Amazon's search parameter
    keywords = query_dict.get("k", [""])[0]
    
    return keywords.lower().split()


def find_price(tag : Tag) -> Optional[str]:
    '''
    Gets a tag object and Extracts patterns
    like $10, $3.50, or $1,000.
    Args:
    tag : bs4 Tag object
    Returns:
    string or none
    '''
    text = tag.get_text(strip=True)
    match = re.search(r"\$(\d+[,.]?\d*)", text)
    
    return match.group(0) if match else None

def _full_image_url(img: Tag) -> Optional[str]:
    '''
    Constructs a full image URL from an img tag.
    Args:
    img : bs4 Tag object representing an image
    Returns:
    Full URL as a string or None if the URL is invalid.
    '''
    img_src = img.get('src') or img.get('data-src')

    if img_src and isinstance(img_src, str):

        if not img_src:
            return None
        if img_src.startswith(('http:', 'https:')):
            return img_src
        if img_src.startswith('//'):
            return f'https:{img_src}'
        if img_src.startswith('/'):
            return f'https://m.media-amazon.com{img_src}'
        return None  # Unrecognized format
    else:
        return None

def _get_product_image(soup) -> Optional[str]:
    '''
    uses common selectors to find the product image
    Args:
    soup : BeautifulSoup object of the product page
    Returns:
    Full image URL as a string or None if not found.
    '''
    # Try the most common selectors one by one
    for selector in ['#landingImage', '#imgBlkFront', '#main-image']:
        img = soup.select_one(selector)
        if img and img.get('src'):
            img_url = _full_image_url(img)
            if img_url:
                return img_url
    
    # If all fail, return None
    return None


def _standard_product_page(link: str) -> str:
    """
    Converts any Amazon link to a working product page URL
    Args:
        link (str): The Amazon link to standardize.
    Returns:
        str: A standardized product page URL.
    If the link does not contain a valid ASIN, it returns the original link.
    If the link is already a valid product page, it returns it unchanged.
    """
    # Extract ASIN first
    asin = None
    patterns = [
        r'/dp/([A-Z0-9]{10})',          # /dp/ASIN
        r'/gp/product/([A-Z0-9]{10})',  # /gp/product/ASIN
        r'/product/([A-Z0-9]{10})',     # /product/ASIN
        r'ASIN=([A-Z0-9]{10})',         # ?ASIN=...
        r'([A-Z0-9]{10})'               # Just ASIN
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            asin = match.group(1)
            break
    
    if not asin:
        return link  # Fallback to original if no ASIN found
    
    # Return working product page URL
    return f"https://www.amazon.com/dp/{asin}/?tag=generic&language=en_US"


def _get_asin(std_link: str) -> Optional[str]:
    """
    Extracts the ASIN from a standard Amazon link
    Args:
    link : standardized Amazon link using _standard_product_page
    Returns:
    str: The ASIN if found, otherwise None.
    """
    asin = std_link.split('/dp/')[-1].split('/')[0]

    return asin if len(asin) == 10 else None

def extract_data_fallback(
        data: Dict[str, Union[Optional[str], bool, List[Dict[str, Optional[str]]]]],
        product_page: bool | str | None):
    '''
    This is the fallback mechanism that triggers when
    the extract data function does not find all the
    required data for scraped products.
    It is used to parse the product page not the search
    results page and it looks for only the missing fields.
    Args:
    data : product dict
    product page : the product page that will be parsed
    Returns :
    product dict with all the required data
    '''
    time.sleep(random.uniform(3, 8))

    if not product_page:
        return data
    
    if isinstance(product_page, str):
        html = fp.get_playwright_html(product_page)
    else:
        return data
    
    try:
        soup = BeautifulSoup(html, features="html.parser")
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return data
    
    missing_fields = [k for k, v in data.items() if v is None and k != '_needs_fallback']

    if 'title' in missing_fields:
        title_tag = soup.select_one('#productTitle') or soup.select_one('#title') or soup.select_one('h1.a-size-large')
        title_text = title_tag.get_text().strip() if title_tag else None
        
        data['title'] = title_text if title_text and len(title_text) >=5 else None
    
    if 'price' in missing_fields:
        price_container = soup.find_all(lambda tag : (
            tag.name in ['span', 'div', 'td'] and
            '$' in tag.get_text()
        ))

        for container in price_container:
            if isinstance(container, Tag):
                price = find_price(container)
                if price:
                    data['price'] = price
                    break
    
    if 'image' in missing_fields:
        img_src = _get_product_image(soup)
        data['image'] = img_src if img_src else None
    
    CRITICAL_KEYS = ['title', 'price', 'link', 'image']
    # If one of the items is None, we need a fallback
    data['_needs_fallback'] = any(data.get(key) is None for key in CRITICAL_KEYS)

    return data


def extract_data(
        tag : Tag
        ) -> Dict[str, Union[bool, Optional[str], List[Dict[str, Optional[str]]]]]:
    '''
    this function is used to parse the products of any search resluts page.
    It also flags the products that need fallback mechanism.
    Args:
    tag : bs4 Tag object that we assume has the data
    Returns:
    product dict
    '''
    data = {
        'asin': None,
        'title': None,
        'price': None,
        'link': None,
        'image': None,
        '_needs_fallback': False
    }
    # Title - look for heading elements or spans with title-like classes
    title = tag.find('h2') or tag.find('span')
    if title:
        data['title'] = title.get_text(strip=True)

    # Link - find product links
    link = tag.find('a', href=True)
    if link and isinstance(link, Tag) and '/dp/' in link['href']:  # Amazon product links contain /dp/
        link_url = link['href']

        if isinstance(link_url, str):
            if not link_url.startswith(('http', 'https')):
                # If the link is relative, construct the full URL
                link_url = f"https://www.amazon.com{link_url}"

            data['link'] = _standard_product_page(link_url)

            if data['link']:
                # Extract ASIN from the link
                asin = _get_asin(link_url)
                if asin:
                    data['asin'] = asin

    # Image - find product images
    img_element = tag.find('img', src=True)
    if img_element and isinstance(img_element, Tag):
        img_url = _full_image_url(img_element)

        if img_url:
            data['image'] = img_url
    
    price : Optional[str] = find_price(tag)
    if price:
        data['price'] = price

    # Does the data need a fallback mechanism ?
    required_fields = ['asin', 'title', 'price', 'link', 'image']
    data['_needs_fallback'] = any(data.get(key) is None for key in required_fields)
    
    return data if data['asin'] and data['link'] else {}