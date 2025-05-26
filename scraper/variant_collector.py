from typing import List, Dict
from playwright.sync_api import Page, ElementHandle, Locator
from playwright.sync_api import sync_playwright
import random
from typing import Optional, List
import scraper.fetch_page as fp


def _find_variant_section(page, variant_type):
    """Finds the container for a variant type using text relationships"""
    # XPath that finds elements containing the label and their parent containers
    xpaths = [
        f'//*[contains(translate(text(), "COLOR", "color"), "{variant_type}")]/ancestor::div[1]',
        f'//label[contains(translate(., "COLOR", "color"), "{variant_type}")]/following-sibling::div',
        f'//*[contains(text(), "{variant_type}:")]/../..'
    ]
    
    for xpath in xpaths:
        section = page.locator(xpath)
        if section.count() > 0:
            return section
    return None


def _get_variant_value(page, variant_type):
    """Gets selected value by analyzing the active/selected state"""
    section = _find_variant_section(page, variant_type)
    if not section:
        return None

    # Look for common selected state patterns
    selected_patterns = [
        '[class*="selected"]',  # CSS class
        '[aria-selected="true"]',  # ARIA attribute
        '[data-selected]',  # Data attribute
        '.active',  # Common active class
        '.is-selected'  # Common selected class
    ]
    
    for pattern in selected_patterns:
        selected = section.locator(pattern)
        if selected.count() > 0:
            return selected.first.inner_text().strip()
    
    # Fallback: First visible option if no selection indicators found
    return section.locator('li,button,div').first.inner_text().strip()


def _get_variant_options(page: Page, variant_type: str) -> Optional[Locator]:
    """
    Fetches a list of visible clickable variant option elements for a given variant type.
    
    Args:
        page: Playwright page object.
        variant_type: The type of variant to look for ("Color", "Size", "Style").
    
    Returns:
        List of ElementHandle objects representing the variant options, or None.
    """
    try:
        # Screenshot for debugging
        # page.screenshot(path='screenshot.png', full_page=True)
        section = page.locator(f'//*[contains(text(), "{variant_type}:")]/ancestor::div[1]')
        if not section.count():
            print(f'No section found for variant type: {variant_type}')
            return None
        
        # Filter only visible, clickable list items
        options = section.locator('li, button, div[role="button"]')

        if not options.count():
            print(f"No visible options found for {variant_type}")
            return None

        return options
        
    except Exception as e:
        print(f'Error fetching variant options: {e}')
        return None

# Value getters
def get_color_value(page: Page) -> Optional[str]:
    return _get_variant_value(page, "Color")

def get_size_value(page: Page) -> Optional[str]:
    return _get_variant_value(page, "Size")

def get_style_value(page: Page) -> Optional[str]:
    return _get_variant_value(page, "Style")


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

    results = []
    for variant_type in ["Color", "Size", "Style"]:
        options = _get_variant_options(page, variant_type)
        if not options:
            continue
        
        options_count = options.count()
        if options_count == 0:
            print(f"No options found for {variant_type}")
            continue
        for i in range(options_count):
            option = options.nth(i)
            print(option.inner_text())
            
            option.scroll_into_view_if_needed()
            page.wait_for_timeout(random.randint(100, 500))  # Random delay to simulate human interaction
            
            page.screenshot(path='pre-hover-screenshot.png', full_page=True)
            option.hover()
            page.screenshot(path='post-hover-screenshot.png', full_page=True)
            page.wait_for_timeout(random.randint(200, 500))

            results.append(
                {
                    "color": get_color_value(page),
                    "size": get_size_value(page),
                    "style": get_style_value(page)
                }
            )


    return results

    
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

            print(f"Getting variants for: {product_page}")
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

    