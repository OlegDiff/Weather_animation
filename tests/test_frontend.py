"""Optional browser checks: WEATHER_BROWSER_TESTS=1 python -m pytest tests/test_frontend.py."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest

pytestmark = pytest.mark.skipif(os.getenv("WEATHER_BROWSER_TESTS") != "1", reason="Opt-in browser checks")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def browser_site():
    from playwright.sync_api import sync_playwright
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                urlopen(url, timeout=1).close()
                break
            except OSError:
                if server.poll() is not None:
                    raise RuntimeError("Test server exited")
                time.sleep(0.1)
        else:
            raise RuntimeError("Test server startup timed out")
        with sync_playwright() as playwright:
            channel = os.getenv("WEATHER_BROWSER_CHANNEL", "msedge" if sys.platform == "win32" else "chromium")
            browser = playwright.chromium.launch(channel=channel, headless=True)
            yield browser, url
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture
def page(browser_site):
    browser, url = browser_site
    context = browser.new_context()
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.clock.install()
    page.goto(url)
    yield page
    context.close()
    assert not errors


def weather(effects=("neutral", "rain", "wind", "sun"), status="fresh"):
    return {"mode": "live", "cities": [
        {"id": name, "effect": effect, "status": status, "data_time": "2026-10-12T07:45:00Z",
         "temperature_c": 12, "missing_fields": []}
        for name, effect in zip(("dublin", "helsinki", "paris", "madrid"), effects)
    ]}


def test_demo_cycle_pause_and_controls(page):
    from playwright.sync_api import expect
    expect(page.locator("[data-mode]")).to_have_value("demo")
    initial = page.locator("canvas").get_attribute("aria-label")
    expect(page.locator("[data-status]")).to_contain_text("1 / 3")
    page.locator("[data-pause]").click()
    before = page.locator("canvas").evaluate("(c)=>c.toDataURL()")
    page.clock.run_for(1000)
    assert page.locator("canvas").evaluate("(c)=>c.toDataURL()") == before
    page.locator("[data-pause]").click()
    page.clock.run_for(12500)
    expect(page.locator("[data-status]")).to_contain_text("2 / 3")
    page.locator("[data-next]").click()
    expect(page.locator("[data-status]")).to_contain_text("3 / 3")
    page.locator("[data-next]").click()
    assert page.locator("canvas").get_attribute("aria-label") == initial


def test_live_mapping_cache_failure_and_return(page):
    from playwright.sync_api import expect
    requests = []
    failed = [False]
    def respond(route):
        requests.append(1)
        if failed[0]:
            route.abort()
        else:
            data = weather()
            data["cities"].reverse()  # Mapping must use IDs, not list order.
            route.fulfill(json=data)
    page.route("**/api/weather", respond)
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("обновление раз")
    expect(page.locator("[data-next]")).to_be_disabled()
    expect(page.locator(".weather-track")).to_be_hidden()
    expect(page.locator("canvas")).to_have_attribute("aria-label", "Dublin: без эффекта; Helsinki: дождь; Raris: ветер; Madrid: солнце")
    page.clock.run_for(13000)
    assert len(requests) == 1
    assert "Raris" in page.locator("[data-weather-rows]").inner_text()
    failed[0] = True
    page.clock.fast_forward(600000)
    expect(page.locator("[data-status]")).to_contain_text("Не удалось")
    expect(page.locator("[data-weather-rows]")).to_contain_text("связь потеряна")
    assert "Helsinki: дождь" in page.locator("canvas").get_attribute("aria-label")
    page.locator("[data-mode]").select_option("demo")
    expect(page.locator("[data-status]")).to_contain_text("1 / 3")
    expect(page.locator("[data-next]")).to_be_enabled()
    expect(page.locator("[data-weather-info]")).to_be_hidden()
    count = len(requests)
    page.clock.fast_forward(60000)
    assert len(requests) == count


def test_missing_data_and_neutral_render(page):
    from playwright.sync_api import expect
    page.route("**/api/weather", lambda route: route.fulfill(json=weather(("neutral",)*4)))
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("обновление раз")
    page.clock.run_for(100)
    # Neutral is drawn in original city colours, not the yellow sun branch.
    counts = page.locator("canvas").evaluate("""c => {
        const data=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
        return [[7,84,43],[6,41,109],[189,69,5],[166,9,18]].map(rgb=>{
            let count=0;
            for(let i=0;i<data.length;i+=4)if(rgb.every((v,j)=>data[i+j]===v))count++;
            return count;
        });
    }""")
    assert all(count > 1000 for count in counts)
    page.screenshot(path=str(ROOT / ".pytest_cache" / "frontend-live.png"), full_page=True)
    page.locator("[data-mode]").select_option("demo")
    page.unroute("**/api/weather")
    page.route("**/api/weather", lambda route: route.fulfill(json={"mode": "live", "cities": [{"id":"paris","effect":"unknown","status":"fresh"}]}))
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("недоступна")
    assert page.locator("canvas").get_attribute("aria-label").count("без эффекта") == 4


def test_initial_failure_recovery_and_stale(page):
    from playwright.sync_api import expect
    failing = [True]
    def respond(route):
        if failing[0]:
            route.fulfill(status=503, body="Unavailable")
        else:
            route.fulfill(json=weather(("snow", "rain", "neutral", "sun"), "stale"))
    page.route("**/api/weather", respond)
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("Не удалось")
    assert page.locator("canvas").get_attribute("aria-label").count("без эффекта") == 4
    failing[0] = False
    page.clock.fast_forward(60000)
    expect(page.locator("[data-weather-rows]")).to_contain_text("устаревшие")
    expect(page.locator("canvas")).to_have_attribute("aria-label", "Dublin: снег; Helsinki: дождь; Raris: без эффекта; Madrid: солнце")


def test_file_demo(browser_site):
    from playwright.sync_api import expect
    browser, _ = browser_site
    page = browser.new_page()
    try:
        page.goto((ROOT / "frontend" / "index.html").as_uri())
        expect(page.locator("[data-status]")).to_contain_text("1 / 3")
        assert page.locator('[value="live"]').evaluate('(option) => option.disabled')
        expect(page.locator("[data-local-hint]")).to_be_visible()
    finally:
        page.close()
