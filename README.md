# Amazon Pattern-Based Scraper

This project is a modular scraper for Amazon product listings and variants. It uses Playwright for stealthy page interaction and BeautifulSoup for robust HTML parsing. Instead of relying on brittle CSS selectors, it detects recurring structural patterns inside product containers.

## Features

- Layout-agnostic product card detection using HTML structure signatures
- Stealthy scraping with randomized user agents and interaction simulation
- Fallback parsing for incomplete product data
- Variant extraction with combinatorial logic and price retrieval
- Multi-pass scraping with stability analysis across runs
- Final product filtering based on ASIN consistency
- JSON output for both raw and final product data

## How It Works

### Product Card Detection (`detect.py`)

- **Core Idea:** Amazon pages vary widely in layout. Instead of relying on fixed CSS selectors, this module detects repetitive HTML structures within likely grid containers. These containers typically have class names like `"grid"`, `"results"`, `"items"`, `"products"`, or `"card"`.

- **Signatures:**
  - **Structure Signature:** A tuple of direct child tag names (e.g., `('div', 'span', 'img')`) used to identify recurring layout patterns.
  - **Class Signature:** A sorted tuple of class names from each tag, used to detect visual consistency.

- **Heuristics:** A tag is considered a product card if:
  - It is visible (not hidden via CSS or ARIA attributes).
  - Its structure or class signature matches one of the most common patterns.
  - It contains at least two of the following: a price-like string, an image tag, or a title-like element.

- **Output:** A list of product dictionaries, each containing:
  - `asin`, `title`, `price`, `link`, `image`, and a flag `_needs_fallback` indicating missing fields.

---

### HTML Fetching (`fetch_page.py`)

- **Playwright Context:** Uses Chromium with randomized settings to mimic real user behavior:
  - Random user agents (Windows, macOS, Linux, mobile)
  - Viewport size, locale, timezone, and geolocation
  - Scroll simulation to trigger lazy loading
  - Removal of automation flags to reduce bot detection

- **Output:** Returns the full HTML content of the page for parsing.

---

### Parsing and Fallback (`parse.py`)

- **Card Parsing:**
  - Extracts title from heading or span elements
  - Extracts price using regex patterns like `"$12.99"`
  - Normalizes product links to `/dp/{ASIN}` format
  - Extracts image URLs from `img` tags or known selectors

- **Fallback Logic:**
  - If any critical field is missing (`title`, `price`, `image`, `link`), the scraper loads the product page directly
  - Uses safer selectors like `#productTitle`, `#landingImage`, and price containers to fill in missing data

- **Output:** A complete product dictionary with fallback-corrected fields

---

### Variant Exploration (`variant_extractor.py`)

- **Discovery:**
  - Scans the product page for variant labels like `"Color:"`, `"Style:"`, `"Size:"`
  - Locates sibling `<li>` elements with `data-asin` attributes to identify selectable options

- **Combinations:**
  - Builds the Cartesian product of all variant options
  - Iteratively selects each combination on the page using Playwright interactions

- **Pricing:**
  - After selecting each variant combination, reads the updated price from the DOM
  - Handles cases where price is embedded in the selected option or nearby elements

- **Output:** A list of dictionaries, each representing a variant combination with its associated price

---

### Multi-Pass Engine and Stability (`main.py`)

- **Run Passes:**
  - Scrapes the same search URL multiple times (e.g., 2–3 passes)
  - Saves each run to `outputs/run{n}.json`

- **Compute Stats:**
  - Aggregates ASINs across all runs
  - Calculates:
    - Unique ASIN count
    - Average, max, and min ASINs per run
    - ASINs seen only once
    - ASINs seen in every run

- **Final List:**
  - Filters products to those seen in all passes (stable ASINs)
  - Attaches variant data only to these stable products
  - Saves final output to:
    - `outputs/final.json` (products + variants)
    - `outputs/stats.json` (run statistics)

---

## Outputs

### Per-Run Files

- `outputs/run1.json`, `outputs/run2.json`, ...

### Final Files

- `outputs/final.json` — stable products with attached variants
- `outputs/stats.json` — ASIN stability metrics across runs

---

## Notes

- This scraper is designed for educational and research purposes.
- Amazon’s layout and anti-bot systems change frequently; this scraper adapts by detecting patterns, not relying on fixed selectors.
- Be mindful of Amazon’s [robots.txt](https://www.amazon.com/robots.txt) and scraping policies.
