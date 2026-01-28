from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright
import asyncio
import re

app = FastAPI(title="Ozon Price Parser", docs_url="/")

async def get_price(url: str) -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
            ignore_default_args=["--enable-automation"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0",
            java_script_enabled=True,
        )
        page = await context.new_page()
        page.set_default_timeout(20000)

        try:
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            # Ищем цену как текст с ₽
            text = await page.text_content("body")
            match = re.search(r'(\d{1,5})\s*₽', text)
            if match:
                return int(match.group(1))

            # Или в JSON
            try:
                data = await page.evaluate("window.__NUXT__")
                if data and 'state' in data:
                    price = data['state'].get('product', {}).get('price', {}).get('main', {}).get('value')
                    if isinstance(price, (int, float)):
                        return int(price)
            except:
                pass

            raise Exception("Цена не найдена")
        finally:
            await browser.close()

@app.post("/price")
async def price(url: str):
    if "ozon.ru" not in url:
        raise HTTPException(400, "Только ozon.ru")
    try:
        p = await get_price(url)
        return {"price": p}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/")
async def root():
    return {"ok": true}
