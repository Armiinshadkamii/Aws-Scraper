from typing import List, Dict
from playwright.sync_api import Page, Locator
from playwright.sync_api import sync_playwright
import random
from typing import Optional, List
from itertools import product
from bs4 import BeautifulSoup, Tag

import scraper.fetch_page as fp
import scraper.parse as parse

def locator_to_tag(locator):
    """Convert a Playwright locator to a BeautifulSoup Tag object."""
    # Get the HTML content of the element
    html = locator.inner_html()
    
    # Parse with BeautifulSoup and get the first element
    soup = BeautifulSoup(html, 'html.parser')
    tag = soup.find()  # the first tag in the HTML

    if not isinstance(tag, Tag):
        raise ValueError("No valid Tag element found in the locator's HTML")
    
    return tag

def _get_price(option : Locator) -> Optional[str]:
    """
    Extracts the price from a variant option element.
    Args:
        option: Playwright Locator of the variant option (li).
    Returns:
        Optional[str]: Price if found, otherwise None.
    This function uses the locator_to_tag function to convert the Playwright Locator
    to a BeautifulSoup Tag, and then uses the parse module to find the price.
    """
    option_tag = locator_to_tag(option)
    price = parse.find_price(option_tag)
    if price:
        return price
    
    return None

def _get_sibling_options(
        page : Page,
        variant_type : str
    ) -> Optional[Locator]:
    """
    Fetches a list of visible clickable variant option elements for a given variant type.
    
    Args:
        page: Playwright page object.
        variant_type: The type of variant to look for ("Color", "Size", "Style").
    
    Returns:
        Locator object representing the variant options, or None.
    """
    try:
        label_container = page.locator(f'//*[contains(text(), "{variant_type}:")]')
        if not label_container.count():
            return None
        
        for level in [3, 4, 5]:
            sibling = label_container.locator(f'xpath=./ancestor::div[{level}]/following-sibling::*[1]')
            if not sibling.count():
                continue
            sibling_options = sibling.locator('li[data-asin]:visible')

            options_count = sibling_options.count()
            if options_count > 0:
                return sibling_options

        print('could not find any valid varaint options for ', variant_type)
        
        return None
    
    except Exception as e:
        print(f'Error fetching variant options: {e}')
        return None

# Value getters
def _get_color_value(section: Locator) -> Optional[str]:
    """
    Extracts color value from the Color section of an amazon
    product page by checking for an image with alt or title attributes.
    Args:
        section: Playwright Locator of the color option (li).
    Returns:
        Optional[str]: Color value if found, otherwise None.
    """
    img = section.locator('img')
    if img.count() > 0:
        return img.first.get_attribute('alt') or img.first.get_attribute('title')
    return None

def _get_option_value(section: Locator) -> Optional[str]:
    """
    Except for the Color options values which require parsing
    img tags, all the other options values can be extracted
    using this function.
    Args:
        section: Playwright Locator of the option (li).
    Returns:
        Optional[str]: Option value if found, otherwise None.
    """
    try:
        return section.inner_text().strip()
    except:
        return None

def _get_variant_types(page: Page) -> List[str]:
    """
    Extracts variant types like 'Size', 'Style', etc., by looking for label spans
    and checking if nearby li[data-asin] elements exist.
    """
    try:
        labels = page.locator('div[class]:has-text("feature") span:has-text(":")')
        variant_types = set()

        for label_el in labels.all():
            #label_el = labels.nth(i)
            label_text = label_el.inner_text().strip()

            if ":" not in label_text:
                continue

            variant = label_text.split(":")[0].strip()
            if not variant or variant.count(' ') >= 2:
                continue
            
            # Check if there's a nearby UL/LI with data-asin
            li_locator = _get_sibling_options(page=page, variant_type=variant)
            if li_locator and li_locator.count() > 0:
                variant_types.add(variant)


        return list(dict.fromkeys(variant_types))
    except Exception as e:
        print(f"Error extracting filtered variant types: {e}")
        return []


def _get_all_combinitions(page : Page) -> Dict[str, List[str | None]]:
    '''
    Gets all variant possibilities for the product.
    e.g:
    {
        "Color" : ['red', 'black', 'white'],
        "Style" : ['wired', 'wireless],
        "Pattern" : ['headset', 'headset + keyboard']
    }
    Returns:
        Dict[str, List[str | None]]: Dictionary with variant types as keys and lists of options as values.
    '''
    try:
        keys = _get_variant_types(page=page)
        if not keys:
            return {}
        
        combinitions : Dict[str, List[str | None]] = {k : [] for k in keys}
        
        for key in keys:
            options = _get_sibling_options(page=page, variant_type=key)
            if not options:
                continue
            
            opt_count = options.count()
            if opt_count == 0:
                continue
            
            for i in range(opt_count):
                option = options.nth(i)
                if key == 'Color':
                    combinitions['Color'].append(_get_color_value(option))
                else:
                    combinitions[key].append(_get_option_value(option))
        return combinitions
    except Exception as e:
        print(f'failed getting possibilities:\n{e}')
        return {}

def extract_data(
        page : Page
        ) -> List[Dict[str, Optional[str]]]:
    """Extract product data from an Amazon product page.
    
    Args:
        page: Playwright page object (already loaded on the product page).
    
    Returns:
        Dict[str, str]: Extracted product data including title, price, and image URL.
            Example: {"title": "Product Title", "price": "$26.49", "image_url": "http://example.com/image.jpg"}
    """

    '''
    1. get all possibilities
    {
        "Color" : ['red', 'black', 'white'],
        "Style" : ['wired', 'wireless],
        "Pattern" : ['headset', 'headset + keyboard']
    }
    2. get nth possibility
    3. select nth possibility
    4. extract price
    5. end
    '''

    combinitions = _get_all_combinitions(page)
    if not combinitions:
        return []
    
    combinitions_list = list(combinitions.values())
    keys_list = list(combinitions.keys())
    
    possibilities = product(*combinitions_list)
    
    # Generate a list of lists for possibilities.
    # we do this because we want to have access to
    # each possibility at a time so we can extract
    # prices after we have clicked on the options
    # of each of the variant types in the possibility.
    variant_types_list : List[List[Dict[str, str]]] = []
    
    for possib in possibilities:
        possib_list : List[Dict[str, str]] = []
        for i, type in enumerate(list(possib)):
            temp_dict = {}
            temp_dict[keys_list[i]] = type
            possib_list.append(temp_dict)
        
        variant_types_list.append(possib_list)

    variant_types_count = len(variant_types_list)
    
    # Now we go through the options inside
    # the each sublist and selelct the each
    # option. at the end of each sublist ,
    # we get the price.
    all_variants_list = []
    no_price = 0

    for variant_sublist in variant_types_list:
        this_variant_options = {}
        get_price_from = {}
        for variant_option in variant_sublist:
            (key, val), = variant_option.items()
            this_variant_options[key] = val
            options : Locator | None = _get_sibling_options(page=page, variant_type=key)
            if options:
                for option in options.all():
                    if key.lower() == 'color':
                        color_value = _get_color_value(option)
                        if color_value:
                            if color_value.lower() == val.lower():
                                try:
                                    option.scroll_into_view_if_needed()
                                    option.click(force=True)
                                    page.wait_for_timeout(500)

                                    if key not in get_price_from.keys():
                                        get_price_from[key] = option
                                    
                                    break
                                except Exception as e:
                                    print(f'click failed for {key} : {val}\n {e}')
                                    break
                    else:
                        option_value = _get_option_value(option)
                        if option_value:
                            if option_value.lower() == val.lower():
                                try:
                                    option.scroll_into_view_if_needed()
                                    option.click(force=True)
                                    page.wait_for_timeout(500)

                                    if key not in get_price_from.keys():
                                        get_price_from[key] = option
                                    
                                    break
                                except Exception as e:
                                    print(f'click failed for {key} : {val}\n {e}')
                                    break
            else:
                print('no options found for ', key)
            

        # Not all of product pages keep the price of
        # variant inside the color options, therefore,
        # we need to check he option for all typs. e.g:
        # Size, Color, Style, etc ...
        price = None
        for key, option in get_price_from.items():
            price = _get_price(option)
            if price:
                break
        
        if not price:
            no_price += 1

        if no_price >= variant_types_count:
            print(f'{no_price} variants had no price, returning...')
            print()
            return []
        
        this_variant_options['price'] = price
        all_variants_list.append(this_variant_options)

    return all_variants_list


    
def get_variants(
        product_page : str,
        callback,
        headless: bool = True
        ) -> List[Dict[str, Optional[str]]]:
    """
    Get product variants using Playwright and process with callback.
    
    Args:
        product_page: URL of the product page
        callback: Function that takes a Playwright Page and returns parsed variants
        headless: Run browser in headless mode
    
    Returns:
        Parsed variants from callback or None if failed
    """
    
    with sync_playwright() as p:
        browser = None
        page = None
        context = None
        try:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--ignore-certificate-errors',
                    '--no-sandbox',
                    f'--user-agent={random.choice(fp.USER_AGENTS)}'
                ],
                slow_mo=random.randint(0, 100)  # Humanize the speed
            )
            context = browser.new_context(
                user_agent=random.choice(fp.USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                bypass_csp=True  
            )
            page = context.new_page()

            # Randomize initial interactions
            if random.random() > 0.5:
                page.mouse.move(
                    random.randint(0, 500),
                    random.randint(0, 500)
                )

            # Clear Playwright's automation flags
            page.add_init_script("""
                delete navigator.__proto__.webdriver;
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            print(f"Getting variants for: {product_page}\n")
            page.goto(product_page, timeout=60000, wait_until='domcontentloaded')  # 60s timeout

            return callback(page)

        except Exception as e:
            print(f'Error getting variants. exception:\n{e}')
            return []

        finally:
        # Close resources in reverse creation order
        # Prevents "already closed" errors
            try:
                if page:
                    page.close()
            except Exception as e:
                print(f"Error closing page: {e}")

            try:
                if context:
                    context.close()
            except Exception as e:
                print(f"Error closing context: {e}")

            try:
                if browser:
                    browser.close()
            except Exception as e:
                print(f"Error closing browser: {e}")