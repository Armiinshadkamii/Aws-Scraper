
from playwright.sync_api import sync_playwright

from playwright.sync_api import Page
import time
import random
from typing import Tuple, Optional

# To avoid getting blocked or detected as a bot, we need to
# send GET requests using different user_agents to mimic real
# human behavior.
USER_AGENTS = [
      # Windows (Chrome, Edge, Firefox)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    
    # macOS (Safari, Chrome, Firefox)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:109.0) Gecko/20100101 Firefox/115.0",
    
    # Linux (Chrome, Firefox)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
    
    # Legacy (for older device simulation)
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.79 Safari/537.36",
        # Android (Chrome, Samsung)
    "Mozilla/5.0 (Linux; Android 14; SM-S901U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.210 Mobile Safari/537.36",
    
    # iOS (Safari, Chrome)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    
    # Windows Phone (Edge)
    "Mozilla/5.0 (Windows Phone 10.0; Android 6.0.1; Microsoft; Lumia 950) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 Edge/40.15254.603"
]


def get_playwright_html(url: str, scroll_steps: int = 15, headless: bool = True) -> str:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-default-apps'
                ]
            )
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
                bypass_csp=True,
                device_scale_factor=random.uniform(1, 1.5),
                geolocation={"longitude": -74.0060, "latitude": 40.7128}   
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
                window.navigator.chrome = {runtime: {}, etc: 'etc'};
            """)

            print(f"Navigating to {url}")
            page.goto(url, timeout=60000)  # 60s timeout

            # Simulate slow scroll to load lazy-loaded products
            for i in range(scroll_steps):
                #page.mouse.wheel(0, 1000)
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(random.uniform(0.8, 1.5))

            # Optional: wait for more products (e.g., 30+ cards)
            page.wait_for_timeout(3000)  # let JS finish

            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f'Failed to get page. exception:\n{e}')
        return ""