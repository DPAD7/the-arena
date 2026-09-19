"""Pull the slip down with real touch events and see what moves.

   Three things have to be true: a long pull shuts the sheet, a short pull
   springs it back, and neither of them scrolls the page behind."""
import asyncio

from playwright.async_api import async_playwright

D = "/Users/joe/Desktop/odds"
URL = "file://" + D + "/site/index.html"


async def swipe(pg, cdp, x, y, dy, steps=12):
    await cdp.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, steps + 1):
        await cdp.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y + dy * i / steps}]})
        await pg.wait_for_timeout(16)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


async def open_slip(pg):
    await pg.evaluate("""() => {
      document.querySelectorAll('dialog.sheet[open]').forEach(d => d.close());
    }""")
    await pg.wait_for_timeout(200)
    if await pg.locator("#slipbar").is_hidden():
        await pg.locator(".board:not([hidden]) button.price:not([disabled])").first.click()
    await pg.locator("#slipopen").click()
    await pg.wait_for_timeout(600)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  has_touch=True, is_mobile=True,
                                  device_scale_factor=2)
        pg = await ctx.new_page()
        cdp = await ctx.new_cdp_session(pg)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(URL)
        await pg.wait_for_timeout(1000)

        # scroll down first, so "the page moved" would be visible
        await pg.evaluate("window.scrollTo(0, 500)")
        await pg.wait_for_timeout(200)
        before = await pg.evaluate("window.pageYOffset")
        print("page scrolled to:", before)

        for label, dy, want_open in (("a long pull", 320, False),
                                     ("a short pull", 40, True)):
            await open_slip(pg)
            box = await pg.locator("#slipsheet").bounding_box()
            # start on the head, which is not a button
            x, y = 195, box["y"] + 34
            await swipe(pg, cdp, x, y, dy)
            await pg.wait_for_timeout(500)
            still = await pg.locator("#slipsheet").evaluate("d => d.open")
            print("%-13s dy=%3d -> sheet %s  (wanted %s)"
                  % (label, dy, "open" if still else "shut",
                     "open" if want_open else "shut"))
            assert still == want_open, label + " did the wrong thing"

        await pg.evaluate("document.querySelectorAll('dialog[open]').forEach(d=>d.close())")
        await pg.wait_for_timeout(400)
        after = await pg.evaluate("window.pageYOffset")
        print("page back at:", after, "->", "held" if abs(after - before) < 4 else "MOVED")

        # the middle still scrolls when there is something to scroll
        await open_slip(pg)
        moved = await pg.evaluate("""() => {
          const s = document.querySelector('#slipsheet .sheet__scroll');
          s.scrollTop = 40; return s.scrollTop;
        }""")
        print("the middle still scrolls:", moved >= 0)
        print("page errors:", errs[:3] or "none")
        await b.close()


asyncio.run(main())
