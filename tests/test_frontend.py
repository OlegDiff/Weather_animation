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
    page.goto(url + "/legacy/")
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
    page.route("**/api/weather?map=legacy", respond)
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
    page.route("**/api/weather?map=legacy", lambda route: route.fulfill(json=weather(("neutral",)*4)))
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
    page.unroute("**/api/weather?map=legacy")
    page.route("**/api/weather?map=legacy", lambda route: route.fulfill(json={"mode": "live", "cities": [{"id":"paris","effect":"unknown","status":"fresh"}]}))
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
    page.route("**/api/weather?map=legacy", respond)
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
        page.goto((ROOT / "frontend" / "legacy" / "index.html").as_uri())
        expect(page.locator("[data-status]")).to_contain_text("1 / 3")
        assert page.locator('[value="live"]').evaluate('(option) => option.disabled')
        expect(page.locator("[data-local-hint]")).to_be_visible()
    finally:
        page.close()


def test_europe_five_stage_cycle_and_transitions(browser_site):
    from playwright.sync_api import expect
    browser, url = browser_site
    page = browser.new_page()
    requests, errors = [], []
    page.on("request", lambda request: requests.append(request.url))
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.clock.install()
        page.goto(url + "/?mode=demo")
        canvas = page.locator("canvas")
        catalog = page.evaluate("window.WEATHER_MAP.cities")

        def effects():
            return dict(item.rsplit(": ", 1) for item in canvas.get_attribute("aria-label").split("; "))

        first = effects()
        assert all(first[c["name"]] == "снег" for c in catalog if c["latitude"] >= 51)
        assert all(first[c["name"]] in ("солнце", "пасмурно") for c in catalog if c["latitude"] < 45)
        page.evaluate("""()=>{
            window.sawBlend=false;
            const draw=CanvasRenderingContext2D.prototype.drawImage;
            CanvasRenderingContext2D.prototype.drawImage=function(...args){
                if(this.canvas===document.querySelector('canvas')&&this.globalAlpha>0&&this.globalAlpha<1)
                    window.sawBlend=true;
                return draw.apply(this,args);
            };
        }""")
        # The automatic timer enters stage two, then cities change gradually.
        page.clock.run_for(18500)
        expect(page.locator("[data-status]")).to_contain_text("2 / 5")
        page.clock.run_for(3000)
        assert page.evaluate("window.sawBlend")
        page.locator("[data-pause]").click()
        page.clock.run_for(50)
        frozen = canvas.evaluate("c=>c.toDataURL()")
        frozen_label = effects()
        page.clock.run_for(2000)
        assert canvas.evaluate("c=>c.toDataURL()") == frozen
        assert effects() == frozen_label
        page.locator("[data-pause]").click()
        page.clock.run_for(5500)
        second = effects()
        assert all((second[c["name"]] == "снег") == (c["latitude"] >= 57) for c in catalog)
        assert list(second.values()).count("снег") < list(first.values()).count("снег")
        stages = {}
        for stage in (3, 4, 5, 1):
            page.locator("[data-next]").click()
            expect(page.locator("[data-status]")).to_contain_text(f"{stage} / 5")
            page.clock.run_for(8500)
            stages[stage] = effects()
        assert list(stages[3].values()).count("солнце") > len(catalog) * .6
        assert "снег" not in stages[3].values()
        assert list(stages[4].values()).count("солнце") < list(stages[3].values()).count("солнце")
        assert all((stages[5][c["name"]] == "снег") == (c["latitude"] >= 58) for c in catalog)
        assert stages[1] == first
        assert not any("/api/weather" in url for url in requests)
        assert not errors
    finally:
        page.close()

def test_weather_explanation_panel(page):
    from playwright.sync_api import expect
    data = weather()
    data["cities"][2].update(
        effect="sun", wind_speed_kmh=8.4, wind_direction_deg=137,
        cloud_cover_pct=8, precipitation_mm=0, rain_mm=0, showers_mm=0,
        snowfall_cm=0, precipitation_interval_seconds=900, weather_code=2, is_day=1,
        effect_reason="День, код погоды 2, облачность 8% не выше 60%, осадки отсутствуют.")
    page.route("**/api/weather?map=legacy", lambda route: route.fulfill(json=data))
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("обновление раз")
    panel = page.locator("[data-weather-details]")
    assert not panel.evaluate("(node)=>node.open")
    panel.locator("summary").click()
    city = panel.locator("section").nth(2)
    expect(city).to_contain_text("Raris")
    expect(city).to_contain_text("8,4 км/ч")
    expect(city).to_contain_text("15 мин")
    expect(city).to_contain_text("облачность 8% не выше 60%")
    expect(panel.locator("section").first).to_contain_text("нет данных")
    data["cities"][2]["status"] = "stale"
    page.clock.fast_forward(600000)
    expect(city).to_contain_text("Последние доступные данные")
    assert panel.evaluate("(node)=>node.open")
    page.locator("[data-mode]").select_option("demo")
    expect(panel).to_be_hidden()

def test_live_intensity_updates_without_effect_change(page):
    from playwright.sync_api import expect
    data = weather(("neutral","neutral","wind","sun"))
    data["cities"][2]["wind_speed_kmh"] = 18
    data["cities"][3]["cloud_cover_pct"] = 0
    page.route("**/api/weather?map=legacy", lambda route: route.fulfill(json=data))
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("[data-status]")).to_contain_text("обновление раз")
    page.locator("[data-pause]").click()
    # Observe actual Canvas calls, without exposing application internals.
    page.evaluate("""()=>{
      window.visualProbe={wind:[],clouds:0};
      const proto=CanvasRenderingContext2D.prototype;
      const draw=proto.drawImage, gradient=proto.createRadialGradient;
      const fill=proto.fillRect;
      proto.fillRect=function(...args){
        if(this.canvas===document.querySelector('canvas')&&args[2]===1100)
          window.visualProbe={wind:[],clouds:0};
        return fill.apply(this,args);
      };
      proto.drawImage=function(...args){
        if(this.canvas===document.querySelector('canvas')&&args.length===9&&args[4]===1)
          window.visualProbe.wind.push(args[5]);
        return draw.apply(this,args);
      };
      proto.createRadialGradient=function(...args){
        window.visualProbe.clouds++;
        return gradient.apply(this,args);
      };
    }""")
    page.clock.run_for(50)
    weak=page.evaluate("Math.max(...visualProbe.wind)")
    assert weak>0
    assert page.evaluate("visualProbe.clouds")==0
    data["cities"][2]["wind_speed_kmh"]=36
    data["cities"][3]["cloud_cover_pct"]=36
    with page.expect_response("**/api/weather?map=legacy"):
        page.clock.fast_forward(600000)
    expect(page.locator("[data-weather-explanations]")).to_contain_text("36 %")
    page.clock.run_for(50)
    strong=page.evaluate("Math.max(...visualProbe.wind)")
    assert strong==pytest.approx(weak*2)
    assert page.evaluate("visualProbe.clouds")==7*3
    data["cities"][2]["wind_speed_kmh"]=200
    data["cities"][3]["cloud_cover_pct"]=60
    with page.expect_response("**/api/weather?map=legacy"):
        page.clock.fast_forward(600000)
    expect(page.locator("[data-weather-explanations]")).to_contain_text("60 %")
    page.clock.run_for(50)
    assert page.evaluate("Math.max(...visualProbe.wind)")==pytest.approx(weak*4)
    assert page.evaluate("visualProbe.clouds")==12*3
    page.locator("[data-mode]").select_option("demo")
    page.clock.run_for(50)
    assert page.evaluate("visualProbe.clouds")==10*3

def test_cloudy_grey_letters_and_moving_dark_clouds(page):
    from playwright.sync_api import expect
    data = weather(("cloudy",)*4)
    for city in data["cities"]:
        city["cloud_cover_pct"]=80
    page.route("**/api/weather?map=legacy", lambda route: route.fulfill(json=data))
    page.locator("[data-mode]").select_option("live")
    expect(page.locator("canvas")).to_have_attribute("aria-label", "Dublin: пасмурно; Helsinki: пасмурно; Raris: пасмурно; Madrid: пасмурно")
    page.clock.run_for(100)
    pixels=page.locator("canvas").evaluate("""c=>{
      const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let grey=0,dark=0,coloured=0;
      for(let i=0;i<d.length;i+=4){
        if(d[i]===153&&d[i+1]===153&&d[i+2]===153)grey++;
        if(d[i]<130&&d[i]===d[i+1]&&d[i]===d[i+2])dark++;
        if(Math.max(d[i],d[i+1],d[i+2])-Math.min(d[i],d[i+1],d[i+2])>5)coloured++;
      }
      return {grey,dark,coloured};
    }""")
    assert pixels["grey"]>1000
    assert pixels["dark"]>1000
    assert pixels["coloured"]==0
    before=page.locator("canvas").evaluate("(c)=>c.toDataURL()")
    page.clock.run_for(1000)
    assert before!=page.locator("canvas").evaluate("(c)=>c.toDataURL()")
    page.locator("[data-pause]").click()
    page.clock.run_for(50)
    paused=page.locator("canvas").evaluate("(c)=>c.toDataURL()")
    page.clock.run_for(500)
    assert paused==page.locator("canvas").evaluate("(c)=>c.toDataURL()")

def test_europe_demo_and_live_versions(browser_site):
    from playwright.sync_api import expect
    import json
    browser,url=browser_site
    page=browser.new_page(viewport={"width":1700,"height":1100})
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    catalog=json.loads((ROOT/"backend/map-layout.json").read_text(encoding="utf-8"))
    try:
        page.clock.install()
        page.goto(url+"/?mode=demo")
        expect(page.locator("[data-status]")).to_contain_text("1 / 5")
        canvas=page.locator("canvas")
        assert canvas.get_attribute("width")=="1600"
        assert canvas.get_attribute("height")=="900"
        assert canvas.get_attribute("aria-label").count(":")==175
        assert canvas.get_attribute("aria-label").count("снег")==page.evaluate("window.WEATHER_MAP.cities.filter(c=>c.latitude>=51).length")
        page.clock.run_for(2000)
        page.screenshot(path=str(ROOT/".pytest_cache/europe-demo.png"),full_page=True)
        page.locator("[data-next]").click()
        expect(page.locator("[data-status]")).to_contain_text("2 / 5")
        assert "дождь" in canvas.get_attribute("aria-label")
        page.route("**/api/weather?map=europe",lambda route:route.fulfill(json={
            "mode":"live","cities":[dict(id=c["id"],effect=["sun","cloudy","wind","rain","snow"][i%5],
                status="fresh",data_time="2026-10-18T10:00:00Z",temperature_c=12,
                wind_speed_kmh=20,cloud_cover_pct=40) for i,c in enumerate(reversed(catalog))]
        }))
        page.goto(url+"/?mode=live")
        expect(page.locator("[data-status]")).to_contain_text("обновление раз")
        expect(page.locator("[data-mode]")).to_have_value("live")
        assert page.locator("[data-weather-rows] li").count()==175
        expected={c["id"]:["солнце","пасмурно","ветер","дождь","снег"][i%5] for i,c in enumerate(reversed(catalog))}
        label=canvas.get_attribute("aria-label")
        for city in catalog:
            assert city["name"]+": "+expected[city["id"]] in label
        page.clock.run_for(250)
        page.screenshot(path=str(ROOT/".pytest_cache/europe-live.png"),full_page=True)
        page.set_viewport_size({"width":600,"height":900})
        box=canvas.bounding_box()
        assert box["width"]/box["height"]==pytest.approx(16/9,rel=.002)
        page.locator("[data-mode]").select_option("demo")
        assert canvas.get_attribute("aria-label").count("снег")==page.evaluate("window.WEATHER_MAP.cities.filter(c=>c.latitude>=51).length")
        assert not errors
    finally:
        page.close()
