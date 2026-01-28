from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import asyncio
import re
import os

app = FastAPI(title="Ozon Price Parser", docs_url="/")

async def get_ozon_price(url: str) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--remote-debugging-port=9222"
            ],
            ignore_default_args=["--enable-automation"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            java_script_enabled=True,
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru'] });
        """)
        page = await context.new_page()
        page.set_default_timeout(25000)
        page.set_default_navigation_timeout(30000)

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Попытка 1: найти цену в HTML как текст (зелёная цена)
            selectors = [
                "[data-widget='webPrice'] span",
                ".price",
                "[class*='price']",
                ".c3118",
                ".yo3",
                "span:has-text('₽')",
                "div[data-test-id='product-price']"
            ]
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        text = await el.text_content()
                        # Извлекаем число перед ₽
                        match = re.search(r'(\d[\d\s]*)\s*₽', text.replace(',', ''))
                        if match:
                            return int(match.group(1).replace(' ', ''))
                except:
                    continue

            # Попытка 2: регулярка по HTML
            html = await page.content()
            match = re.search(r'"price":\{"main":\{"value":(\d+)', html)
            if match:
                return int(match.group(1))

            raise Exception("Цена не найдена")
        finally:
            await browser.close()

@app.post("/price")
async def parse_price(url: str):
    if not url or "ozon.ru" not in url:
        raise HTTPException(status_code=400, detail="Требуется ссылка на ozon.ru")
    try:
        price = await get_ozon_price(url)
        return {"price": price}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Ozon Price Parser API",
        "usage": "POST /price {\"url\": \"https://www.ozon.ru/product/...\"}"
    }
