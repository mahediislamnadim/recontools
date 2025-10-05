#!/usr/bin/env python3
"""
ctf_scanner_selenium.py

Selenium-based scanner for JS-rendered pages (optional).
Saves rendered HTML and extracts custom tags/attributes & shadow DOM custom tags.
Outputs results to khoba_output/results.json and khoba_output/results.csv and saves HTML files into khoba_output/html/

This script prefers Selenium for rendering but falls back to requests+BeautifulSoup when Selenium
or Chrome is not available. The fallback won't execute JS but provides useful static analysis.
"""

import re
import json
import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
import concurrent.futures
import logging

import requests
try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

# Selenium is optional; prefer it for JS-rendered pages but provide a requests-based fallback
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False
else:
    # import common exceptions for finer-grained handling
    try:
        from selenium.common.exceptions import SessionNotCreatedException, WebDriverException
    except Exception:
        # fallback names if import fails
        SessionNotCreatedException = Exception
        WebDriverException = Exception

# ------------- Config defaults -------------
OUTPUT_DIR = Path("khoba_output")
HTML_DIR = OUTPUT_DIR / "html"
CSV_PATH = OUTPUT_DIR / "results.csv"
JSON_PATH = OUTPUT_DIR / "results.json"
LOG_FILE = OUTPUT_DIR / "scanner.log"

CONCURRENCY = 4
WAIT_AFTER_LOAD = 1.0  # seconds to wait after page load for JS
NAV_TIMEOUT = 30  # seconds (webdriver page_load_timeout)
# Feature flags (updated from CLI in main())
EXTERNAL_JS_FETCH = False
SCREENSHOT_ENABLED = False
FORCE_SELENIUM = False
CHROMEDRIVER_PATH = None
BROWSER_BINARY = None
# -------------------------------------------


def reconfigure_paths_and_logging(output_dir: str = None):
    """Reconfigure output paths and logging after CLI args are parsed."""
    global OUTPUT_DIR, HTML_DIR, CSV_PATH, JSON_PATH, LOG_FILE
    # update paths if user passed an output dir
    if output_dir:
        OUTPUT_DIR = Path(output_dir)
    HTML_DIR = OUTPUT_DIR / "html"
    CSV_PATH = OUTPUT_DIR / "results.csv"
    JSON_PATH = OUTPUT_DIR / "results.json"
    LOG_FILE = OUTPUT_DIR / "scanner.log"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    # reconfigure logging to write to the selected log file
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")]
    )


def safe_filename(url: str) -> str:
    invalid = r'[:\\/<>|?"*\s]'
    name = re.sub(invalid, "_", url)
    if len(name) > 200:
        name = name[:200]
    return name


def make_driver(show_browser: bool = False, chromedriver_path: str = None, browser_binary: str = None):
    opts = Options()
    if not show_browser:
        try:
            opts.add_argument("--headless=new")
        except Exception:
            opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,1000")

    # allow user to specify browser binary (useful for non-standard installs)
    if browser_binary:
        try:
            opts.binary_location = browser_binary
        except Exception:
            # some selenium versions use different attribute name
            try:
                opts._binary_location = browser_binary
            except Exception:
                pass

    # allow a user-provided chromedriver binary path
    try:
        if chromedriver_path:
            service = Service(chromedriver_path)
        else:
            service = Service(ChromeDriverManager().install())
    except Exception:
        # webdriver-manager may fail or not be desired; try to rely on default Service
        service = Service(chromedriver_path) if chromedriver_path else None

    if service is not None:
        driver = webdriver.Chrome(service=service, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(NAV_TIMEOUT)
    return driver


def check_selenium_driver():
    """Attempt to create and quit a driver once to validate chromedriver/browser compatibility.
    Returns True if a driver can be created and started, False otherwise.
    """
    try:
        # make_driver will consult CHROMEDRIVER_PATH / BROWSER_BINARY if provided
        drv = make_driver(show_browser=False, chromedriver_path=CHROMEDRIVER_PATH, browser_binary=BROWSER_BINARY)
        try:
            drv.quit()
        except Exception:
            pass
        return True
    except Exception as e:
        logging.warning("Selenium driver check failed: %s", e)
        return False


def extract_from_html(html: str) -> Dict[str, List[str]]:
    """Parse raw HTML with BeautifulSoup to find custom element tags and custom attributes.
    Returns dict with keys: tags, attrs
    """
    if BeautifulSoup is None:
        # Minimal fallback: crude regex for tags and attributes (best-effort)
        tags = sorted(set(re.findall(r"<([a-zA-Z0-9\-]+)", html)))
        tags = [t for t in tags if '-' in t]
        attrs = sorted(set(re.findall(r"\b([a-zA-Z0-9\-]+)=\"", html)))
        attrs = [a for a in attrs if '-' in a and not a.startswith('aria-') and not a.startswith('data-')]
        return {"tags": tags, "attrs": attrs}

    soup = BeautifulSoup(html, "html.parser")
    tags_set = set()
    attrs_set = set()

    for el in soup.find_all(True):
        name = el.name or ''
        if '-' in name:
            tags_set.add(name.lower())
        for attr in el.attrs.keys():
            if attr and '-' in attr and not attr.startswith('aria-') and not attr.startswith('data-'):
                attrs_set.add(attr)

    return {
        "tags": sorted(tags_set),
        "attrs": sorted(attrs_set),
    }


def extract_from_js(html: str, base_url: str = None, fetch_external: bool = False) -> Dict[str, List[str]]:
    """Extract custom element names from inline JS and (optionally) external JS files.
    Returns dict with key 'js_tags'.
    """
    js_tags = set()
    script_sources = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        for s in soup.find_all('script'):
            src = s.get('src')
            if src:
                script_sources.append(src)
            else:
                if s.string:
                    script_sources.append(s.string)
    else:
        # crude fallback: find <script ...> blocks
        for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE):
            script_sources.append(m.group(1))

    # helper to scan a JS text blob
    def scan_js_text(js_text: str):
        if not js_text:
            return
        # customElements.define('my-tag' ...)
        for m in re.finditer(r"customElements\.define\(['\"]([a-zA-Z0-9\-]+)['\"]", js_text):
            js_tags.add(m.group(1).lower())
        # document.createElement('my-tag')
        for m in re.finditer(r"createElement\(['\"]([a-zA-Z0-9\-]+)['\"]\)", js_text):
            js_tags.add(m.group(1).lower())

    # scan inline scripts first
    for blob in [s for s in script_sources if not (s and (s.strip().startswith('http') or s.strip().startswith('/')) )]:
        scan_js_text(blob)

    # optionally fetch external scripts
    if fetch_external:
        for src in [s for s in script_sources if s and not s.strip().startswith('<')]:
            try:
                # resolve relative URL if base_url provided
                if base_url and not src.startswith('http'):
                    from urllib.parse import urljoin
                    src_url = urljoin(base_url, src)
                else:
                    src_url = src
                r = requests.get(src_url, timeout=10)
                if r.status_code == 200:
                    scan_js_text(r.text)
            except Exception:
                continue

    return {"js_tags": sorted(js_tags)}


def scan_single_url_selenium(url: str, show_browser: bool = False, wait_after: float = WAIT_AFTER_LOAD) -> Dict[str, Any]:
    """Use Selenium to render and extract dynamic content."""
    result = {
        "url": url,
        "ok": False,
        "status": None,
        "custom_tags": [],
        "registered_custom_elements": [],
        "custom_attributes": [],
        "saved_html": None,
        "error": None,
        "fetched_at": datetime.now(timezone.utc).isoformat()
    }

    driver = None
    try:
        logging.info(f"[selenium] Scanning: {url}")
        driver = make_driver(show_browser=show_browser, chromedriver_path=CHROMEDRIVER_PATH, browser_binary=BROWSER_BINARY)
        driver.get(url)
        time.sleep(wait_after)

        html = driver.page_source

        # Best-effort status retrieval
        try:
            res = driver.execute_script("return (performance.getEntriesByType('navigation')[0] || {}).responseStart || null;")
            result["status"] = None if res is None else 200
        except Exception:
            result["status"] = None

        # Extract via JS to capture shadow DOM and runtime-created custom elements
        js_extract = """
        (() => {
            const out = { tags: [], attrs: [], shadow_tags: [], registered: [] };
            try {
                const els = [...document.querySelectorAll('*')];
                const customEls = els.filter(e => e.tagName && e.tagName.includes('-'));
                out.tags = [...new Set(customEls.map(e => e.tagName.toLowerCase()))];

                const customAttrs = new Set();
                els.forEach(e => {
                    [...e.attributes].forEach(attr => {
                        if (attr && attr.name && attr.name.includes('-') && !attr.name.startsWith('aria-') && !attr.name.startsWith('data-')) {
                            customAttrs.add(attr.name);
                        }
                    });
                });
                out.attrs = Array.from(customAttrs);

                const found = new Set();
                function walk(node) {
                    if (!node) return;
                    if (node.shadowRoot) {
                        try {
                            const inner = [...node.shadowRoot.querySelectorAll('*')];
                            inner.forEach(e => { if (e.tagName && e.tagName.includes('-')) found.add(e.tagName.toLowerCase()); });
                        } catch(e){}
                    }
                    if (node.children) {
                        [...node.children].forEach(c => walk(c));
                    }
                }
                walk(document.documentElement);
                out.shadow_tags = Array.from(found);

                try { out.registered = out.tags.filter(t => !!customElements.get(t)); } catch(e){}
            } catch(e) {}
            return out;
        })();
        """
        dom_info = {}
        try:
            dom_info = driver.execute_script(js_extract) or {}
        except Exception as e:
            logging.debug(f"JS extraction failed for {url}: {e}")
            dom_info = {}

        tags = dom_info.get("tags") or []
        shadow_tags = dom_info.get("shadow_tags") or []
        attrs = dom_info.get("attrs") or []
        registered = dom_info.get("registered") or []

        merged_tags = list(dict.fromkeys(tags + shadow_tags))
        result["custom_tags"] = merged_tags
        result["custom_attributes"] = attrs
        result["registered_custom_elements"] = registered

        # JS extraction: scan inline and (optionally) external scripts
        try:
            js_info = extract_from_js(html, base_url=url, fetch_external=EXTERNAL_JS_FETCH)
            result["js_tags"] = js_info.get("js_tags", [])
            # merge js tags with DOM tags
            merged_tags = list(dict.fromkeys(merged_tags + result["js_tags"]))
            result["custom_tags"] = merged_tags
        except Exception:
            result["js_tags"] = []

        # optional screenshot
        if SCREENSHOT_ENABLED:
            try:
                shot_name = safe_filename(url) + ".png"
                shot_path = HTML_DIR / shot_name
                driver.save_screenshot(str(shot_path))
                result["screenshot"] = str(shot_path)
            except Exception:
                result["screenshot"] = None

        # save HTML
        filename = safe_filename(url) + ".html"
        path = HTML_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        result["saved_html"] = str(path)
        result["ok"] = True
        logging.info(f"[selenium] Done: {url} -> tags: {len(merged_tags)}, attrs: {len(attrs)}")

    except Exception as e:
        logging.exception(f"[selenium] Error scanning {url}: {e}")
        result["error"] = str(e)
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass

    return result


def scan_single_url_requests(url: str, wait_after: float = WAIT_AFTER_LOAD) -> Dict[str, Any]:
    """Fallback scanner using requests (no JS execution)."""
    result = {
        "url": url,
        "ok": False,
        "status": None,
        "custom_tags": [],
        "registered_custom_elements": [],
        "custom_attributes": [],
        "saved_html": None,
        "error": None,
    "fetched_at": datetime.now(timezone.utc).isoformat()
    }
    headers = {"User-Agent": "ctf-scanner/1.0 (+https://github.com)"}
    try:
        logging.info(f"[requests] Fetching: {url}")
        r = requests.get(url, headers=headers, timeout=NAV_TIMEOUT, allow_redirects=True)
        result["status"] = r.status_code
        html = r.text

        info = extract_from_html(html)
        result["custom_tags"] = info.get("tags", [])
        result["custom_attributes"] = info.get("attrs", [])
        try:
            js_info = extract_from_js(html, base_url=url, fetch_external=EXTERNAL_JS_FETCH)
            result["js_tags"] = js_info.get("js_tags", [])
            # merge js tags into custom tags
            result["custom_tags"] = list(dict.fromkeys(result["custom_tags"] + result["js_tags"]))
        except Exception:
            result["js_tags"] = []

        # save HTML
        filename = safe_filename(url) + ".html"
        path = HTML_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        result["saved_html"] = str(path)
        result["ok"] = True
        logging.info(f"[requests] Done: {url} -> tags: {len(result['custom_tags'])}, attrs: {len(result['custom_attributes'])}")
    except Exception as e:
        logging.exception(f"[requests] Error scanning {url}: {e}")
        result["error"] = str(e)
    return result


def read_urls(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    return lines


def save_outputs(results: List[Dict[str, Any]]):
    # JSON
    with open(JSON_PATH, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)

    # CSV
    keys = ["url", "ok", "status", "custom_tags", "registered_custom_elements", "custom_attributes", "saved_html", "error", "fetched_at"]
    with open(CSV_PATH, "w", encoding="utf-8", newline='') as cf:
        writer = csv.DictWriter(cf, fieldnames=keys)
        writer.writeheader()
        for r in results:
            row = {k: (json.dumps(r.get(k), ensure_ascii=False) if isinstance(r.get(k), (list, dict)) else r.get(k)) for k in keys}
            writer.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="CTF scanner (Selenium-based) - extract custom tags/attributes")
    ap.add_argument("-i", "--input", required=True, help="input file with one URL per line")
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY, help="number of concurrent workers")
    ap.add_argument("--wait", type=float, default=WAIT_AFTER_LOAD, help="seconds to wait after page load")
    ap.add_argument("--show-browser", action="store_true", help="show browser for debugging")
    ap.add_argument("--chromedriver-path", help="path to a chromedriver binary to use (optional)")
    ap.add_argument("--browser-binary", help="path to a Chrome/Chromium binary to use (optional)")
    ap.add_argument("--output", help="output directory (default: khoba_output)")
    ap.add_argument("--fetch-external-js", action="store_true", help="fetch external JS files to detect custom elements")
    ap.add_argument("--screenshot", action="store_true", help="save screenshots (selenium mode only)")
    ap.add_argument("--force-selenium", action="store_true", help="try to force selenium even if driver check fails")
    args = ap.parse_args()

    # wire CLI flags into globals and reconfigure paths/logging
    global EXTERNAL_JS_FETCH, SCREENSHOT_ENABLED, FORCE_SELENIUM, CHROMEDRIVER_PATH, BROWSER_BINARY
    CHROMEDRIVER_PATH = args.chromedriver_path
    BROWSER_BINARY = args.browser_binary
    EXTERNAL_JS_FETCH = bool(args.fetch_external_js)
    SCREENSHOT_ENABLED = bool(args.screenshot)
    FORCE_SELENIUM = bool(args.force_selenium)

    reconfigure_paths_and_logging(output_dir=args.output)

    urls = read_urls(args.input)
    logging.info(f"Loaded {len(urls)} urls from {args.input}")

    results = []
    # Choose method based on availability and driver/browser compatibility
    use_selenium = SELENIUM_AVAILABLE
    if use_selenium:
        ok = check_selenium_driver()
        if ok:
            logging.info("Selenium is available and driver is compatible: using Selenium-based rendering")
            use_selenium = True
        else:
            if FORCE_SELENIUM:
                logging.warning("Selenium detected but driver/browser incompatible; --force-selenium specified, attempting Selenium anyway")
                use_selenium = True
            else:
                logging.warning("Selenium detected but driver/browser incompatible; falling back to requests (no JS)")
                use_selenium = False
    else:
        logging.info("Selenium not available: using static requests fallback (no JS)")

    # ThreadPoolExecutor to parallelize
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        if use_selenium:
            futures = [ex.submit(scan_single_url_selenium, u, args.show_browser, args.wait) for u in urls]
        else:
            futures = [ex.submit(scan_single_url_requests, u, args.wait) for u in urls]

        for fut in concurrent.futures.as_completed(futures):
            try:
                res = fut.result()
            except Exception as e:
                logging.exception(f"Worker exception: {e}")
                res = {"url": "unknown", "error": str(e), "ok": False}
            results.append(res)

    save_outputs(results)
    logging.info(f"Saved JSON -> {JSON_PATH} CSV -> {CSV_PATH} HTMLs -> {HTML_DIR.resolve()}")
    print(f"Done. Results: {CSV_PATH} and {JSON_PATH}")


if __name__ == "__main__":
    main()

