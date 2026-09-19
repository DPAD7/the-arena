"""Open the page at phone width, tap a price, open the slip, open a card
   detail, and photograph each. Looking at the picture is the only way to
   know a sheet is not clipped by the card it lives in."""
import asyncio
import sys

from playwright.async_api import async_playwright

D = "/Users/joe/Desktop/odds"


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 390, "height": 844},
                              has_touch=True, is_mobile=True,
                              device_scale_factor=2)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text)
              if m.type == "error" else None)
        await pg.goto("file://" + D + "/site/index.html")
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=D + "/shot-board.png")

        # a price, so the slip has something in it
        btns = pg.locator(".board:not([hidden]) button.price:not([disabled])")
        n = await btns.count()
        print("tappable prices on the open day:", n)
        for i in range(min(3, n)):
            await btns.nth(i).click()
        await pg.wait_for_timeout(300)

        bar = pg.locator("#slipbar")
        print("slip bar showing:", await bar.is_visible())
        await pg.locator("#slipopen").click()
        await pg.wait_for_timeout(600)
        sheet = pg.locator("#slipsheet")
        print("slip sheet open:", await sheet.evaluate("d => d.open"))
        box = await sheet.bounding_box()
        print("slip sheet box:", box)
        print("slip rows:", await pg.locator(".sliprow").count())
        for t in await pg.locator(".sliprow > span:first-child").all_text_contents():
            print("   ", t)
        print("body locked:", await pg.evaluate(
            "getComputedStyle(document.body).position"))
        await pg.screenshot(path=D + "/shot-slip.png")
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(400)
        print("after Escape — body position:", await pg.evaluate(
            "getComputedStyle(document.body).position"))

        # a card detail
        more = pg.locator(".board:not([hidden]) .gmorebtn").first
        await more.click()
        await pg.wait_for_timeout(700)
        gs = pg.locator(".board:not([hidden]) dialog.gsheet[open]")
        print("card sheet open:", await gs.count())
        gbox = await gs.first.bounding_box()
        print("card sheet box:", gbox)
        print("card sheet title:", await gs.first.locator(".sheet__title").inner_text())
        print("chart in sheet:", await gs.first.locator(".wpx svg").count())
        await pg.screenshot(path=D + "/shot-detail.png")

        # the updater still finds the chart through the card
        print("card.querySelector reach:", await pg.evaluate(
            """() => {
              const c = document.querySelector('.board:not([hidden]) .gcard[data-espn]');
              return c ? [!!c.querySelector('.wpx svg'), c.querySelectorAll('.wpbig').length] : null;
            }"""))

        # desktop shape
        pg2 = await b.new_page(viewport={"width": 1100, "height": 800})
        await pg2.goto("file://" + D + "/site/index.html")
        await pg2.wait_for_timeout(900)
        await pg2.locator(".board:not([hidden]) button.price:not([disabled])").first.click()
        await pg2.locator("#slipopen").click()
        await pg2.wait_for_timeout(500)
        await pg2.screenshot(path=D + "/shot-slip-wide.png")

        if errs:
            print("\n!! page errors:")
            for e in errs[:15]:
                print("  ", e)
        else:
            print("\nno page errors")
        await b.close()


asyncio.run(main())
