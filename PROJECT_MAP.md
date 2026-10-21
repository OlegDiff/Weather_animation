# PROJECT_MAP.md — карта файлов Weather_animation

Актуально по архиву `Weather_animation-main.zip` от 18.10.2026. Описывает **существующий** код, а не планируемую архитектуру.

## Как пользоваться (для Codex)

1. Начинай с таблицы «Задача → файлы», не обходи репозиторий целиком.
2. Читай **только названные файлы и при необходимости непосредственно связанные функции**. Полный `README.md`, все тесты и весь проект без необходимости не открывай.
3. Меняй минимальный набор файлов. Если необходим выход за указанные границы, кратко объясни причину.
4. Прежде чем править сгенерированные файлы, найди исходник и команду генерации.
5. После изменения выполняй **только релевантные проверки**. Полный прогон — при изменении общих контрактов, сборке к релизу или по просьбе пользователя.

## Задача → куда идти

| Требуемая правка | Основной файл / конкретное место | Дополнительно только при необходимости |
|---|---|---|
| Изменить дождь (капли, брызги, синие буквы, волны) | `frontend/app.js`: `particle`, `setEffect`, `update`, `draw` (ветка `rain`) | `tests/test_frontend.py` |
| Изменить снег (хлопья, накопление, цвет) | `frontend/app.js`: `particle`, `setEffect`, `update`, `draw` (ветка `snow`) | `tests/test_frontend.py` |
| Изменить ветер (изгиб, колебания, интенсивность) | `frontend/app.js`: `draw` (ветка `wind`), `applyVisualMetrics` | `tests/test_frontend.py` |
| Изменить солнце (цвет, мерцание, подсветка, облака) | `frontend/app.js`: `draw` (заключительная ветка `sun`), `puff`, `update` | `tests/test_frontend.py` |
| Изменить пасмурность (серые буквы, облака) | `frontend/app.js`: `draw` (ветка `cloudy`), `puff`, `applyVisualMetrics` | `tests/test_frontend.py` |
| Изменить форму букв, шрифт **внутри карты** или формирование маски | `frontend/app.js`: `specs`, `cities=specs.map(...)`, `mask` | `backend/map-layout.json`, если меняются размеры подписей |
| Изменить последовательность демосцен / распределение эффектов по городам | `frontend/app.js`: `STAGE_SECONDS`, `FADE_SECONDS`, `SPREAD_SECONDS`, `stageNames`, `demoEffect`, `sequences`, `reset`, `advanceDemo` | `tests/test_frontend.py` |
| Изменить плавность переходов между эффектами | `frontend/app.js`: `reset`, `updateCity`, `drawCity`, `FADE_SECONDS` | `tests/test_frontend.py` |
| Изменить скорость или производительность анимации | `frontend/app.js`: `render`, `update`, `draw`, создание `mask` / `atlas` / `tiles` | Браузерные тесты, только при значимых изменениях |
| Изменить позицию, подпись или размер города на европейской карте | `backend/map-layout.json` → запуск `python tools/build_city_map.py` | `frontend/app.js` только если меняется сам способ размещения |
| Изменить широту/долготу или идентичность города | `backend/map-geocoding.json` → запуск `python tools/build_city_map.py` | `backend/map-layout.json` для нового города; `tests/test_europe_map.py` |
| Добавить или убрать город | `backend/map-layout.json` + `backend/map-geocoding.json` → генерация | `backend/config.py` подхватывает каталог автоматически; обновить тесты с фиксированным количеством городов |
| Изменить размер Canvas / пропорции карты | `frontend/index.html`, `frontend/style.css`, `frontend/app.js` (коэффициенты масштаба в `specs`) | `tools/build_city_map.py`, `backend/map-layout.json`, `tests/test_europe_map.py` |
| Изменить элементы интерфейса, подписи кнопок, ссылки | `frontend/index.html` | `frontend/app.js`, если меняется поведение |
| Изменить внешние отступы, ширину страницы, кнопки, раскрывающиеся панели | `frontend/style.css` | `frontend/index.html` |
| Изменить кнопки Пауза/Следующая сцена, переключатель демо/live | `frontend/app.js`: обработчики `onclick`, `modeSelect.addEventListener` | `frontend/index.html`, `tests/test_frontend.py` |
| Изменить подсказки города при наведении | `frontend/app.js`: `canvas.addEventListener('pointermove', ...)` | — |
| Изменить отображение погодных показателей, статус, объяснения | `frontend/app.js`: `showWeather`, `showExplanations`, `formatTime`, `metric` | `frontend/index.html` для HTML-контейнеров |
| Изменить запрос браузера к погодному API или частоту опроса | `frontend/app.js`: `applyWeather`, `refreshWeather` | `backend/main.py` при изменении маршрута/параметра; `backend/weather_api.py` для серверного кеша |
| Изменить **правила**, по которым погода превращается в эффект | `backend/weather_logic.py`: `select_effect_with_reason`, `select_effect` | `backend/config.py` для порогов, `tests/test_weather.py` |
| Изменить порог ветра, порог облачности, кеш, повторы, таймауты | `backend/config.py` | `tests/test_weather.py`; `backend/weather_api.py` только если меняется механизм |
| Изменить набор погодных параметров, валидацию или преобразование Open-Meteo | `backend/weather_logic.py`: `FIELDS`, `normalize` | `backend/weather_api.py` (параметры запроса), `frontend/app.js` (если меняется JSON-контракт), `tests/test_weather.py` |
| Изменить поставщика погоды, сетевые запросы, обработку ответов | `backend/weather_api.py`: `fetch_current`, `fetch_many` | `backend/weather_logic.py`, `tests/test_europe_map.py` |
| Изменить группировку 175 городов в API-запросах, параллелизм | `backend/weather_api.py`: `fetch_many` | `tests/test_europe_map.py` |
| Изменить серверное кеширование, stale / unavailable / повторные запросы | `backend/weather_api.py`: `WeatherService` | `backend/config.py`, `tests/test_weather.py` |
| Изменить `/api/weather`, обслуживание страниц / статики | `backend/main.py` | `backend/weather_api.py` только если изменяется служба получения погоды |
| Изменить старую карту из четырёх городов | `frontend/legacy/app.js`, `frontend/legacy/index.html`, `frontend/legacy/style.css` | `backend/config.py`, если меняются четыре города; API `?map=legacy` |
| Добавить Python-зависимость | `requirements.txt` | `requirements-dev.txt` только для тестовых инструментов |
| Изменить игнорируемые Git-файлы | `.gitignore` | — |
| Обновить инструкции запуска и архитектуры | `README.md` | `docs/europe-map.md` для решений по европейской карте |
| Изменить инструкции Codex | `AGENTS.md`, `PROJECT_MAP.md` | — |

## Публикация на GitHub Pages

- `tools/build_pages.py` — автономная сборка `_site/` стандартной библиотекой Python;
  получение 175 городов карты плюс Helsinki для legacy через `WeatherService`/`fetch_many`, отказ при неполных
  или устаревших данных, явный список разрешённых frontend-файлов.
- `.github/workflows/pages.yml` — почасовая публикация Pages артефакта, ручной
  запуск и push в main; без коммитов данных, с сериализацией запусков.
- `tests/test_pages.py` — контракт статического JSON, состав артефакта,
  сохранность предыдущей сборки при полном/частичном отказе и старых данных.
- Сборщик добавляет `data-weather-url` в HTML обеих карт. Без него JS использует
  локальный API; с ним — общий `data/weather.json` и проверяет возраст данных
  в браузере. Пути относительные, включая размещение в подпапке.
- Проверка: `python -m pytest -q`, затем `python tools/build_pages.py`.
  Настройка Pages и диагностика описаны в README.

## Что в каждом файле

### `frontend/` — браузер и визуальная часть

- **`frontend/app.js`** — основной большой JS-модуль (самовызываемая функция). `demoEffect` распределяет синтетическую погоду по сценам; `specs` и `cities` создают надписи из `window.WEATHER_MAP`; `particle` / `setEffect` / `applyVisualMetrics` настраивают эффекты; `update` изменяет состояние частиц и снега; `puff` рисует облако; `draw` отрисовывает все погодные эффекты на Canvas; `render` запускает цикл `requestAnimationFrame`; `showWeather` / `showExplanations` показывают информацию; `applyWeather` / `refreshWeather` обрабатывают API; обработчики внизу файла управляют режимами, кнопками и наведением. **Примечание:** отдельного `weather-effects.js` сейчас нет.
- **`frontend/map-cities.js`** — **сгенерированный** JS-каталог (`window.WEATHER_MAP`), 175 городов, размеры исходной композиции и географические координаты. Не редактировать вручную: исходники — два JSON-файла в `backend/`.
- **`frontend/index.html`** — главная HTML-страница, Canvas 1600×900, навигация, панель режимов, погодные данные. Подключает `map-cities.js`, затем `app.js`.
- **`frontend/style.css`** — оформление внешнего интерфейса, максимальная ширина 1600px, соотношение Canvas 16:9. **Цвета погодных букв и эффекты задаёт JS, не CSS.**

### `frontend/legacy/` — сохранённая старая версия

- **`frontend/legacy/app.js`** — самостоятельная четырёхгородская анимация, обработка demo/live, погодные эффекты (по смыслу похожа на основной `app.js`, но не является общим модулем).
- **`frontend/legacy/index.html`** — разметка старой страницы с Canvas 1100×578, подключает только локальный `app.js`.
- **`frontend/legacy/style.css`** — отдельные стили старой страницы.
- **Правило:** при правках европейской карты **не изменять legacy по умолчанию**; при исправлении общей ошибки сравнивать реализации и менять обе лишь при обоснованной необходимости.

### `backend/` — сервер и данные

- **`backend/config.py`** — список четырёх старых городов `CITIES`; параметры `CACHE_SECONDS=600`, `RETRY_SECONDS=60`, `REQUEST_TIMEOUT_SECONDS=5`, `MAX_DATA_AGE_SECONDS=3600`; пороги `WIND_THRESHOLD_KMH=18` и `SUN_MAX_CLOUD_PCT=60`; загрузка `EUROPE_CITIES` из файлов каталога.
- **`backend/main.py`** — FastAPI-приложение; `GET /api/weather` отдаёт погоду 175 городов по умолчанию либо старых четырёх при `?map=legacy`; монтирует статические файлы `frontend/`.
- **`backend/weather_api.py`** — клиент Open-Meteo. `fetch_current` — один город; `fetch_many` — пакетные запросы (до 40 городов в партии, до 5 параллельных работников); `WeatherService` — кеш, блокировка параллельных обновлений, восстановление после сбоев, статусы `fresh` / `stale` / `unavailable` и выдача JSON для фронтенда.
- **`backend/weather_logic.py`** — словарь `FIELDS` (поля и единицы Open-Meteo), проверка допустимых значений в `normalize`, выбор `effect` и русскоязычного `effect_reason` в `select_effect_with_reason`. Приоритет: снег → дождь → ветер → облачно → солнце → neutral. Пороги берутся из `config.py`.
- **`backend/map-layout.json`** — **первичный источник для расположения надписей**: `id`, `name`, `query`, `country`, `x`, `y`, `w`, `h` в координатах референса 1672×941.
- **`backend/map-geocoding.json`** — **первичный источник географических координат** по id: GeoNames id, latitude, longitude, код страны, население.

### `tools/`

- **`tools/build_city_map.py`** — объединяет `map-layout.json` и `map-geocoding.json`, проверяет совпадение страны и записывает `frontend/map-cities.js`. После изменения любого из двух JSON выполнить: `python tools/build_city_map.py`.

### `tests/`

- **`tests/test_weather.py`** — Python-тесты выбора эффектов, порогов, нормализации, старого API, кеша, восстановления после сбоев и конкурентных запросов.
- **`tests/test_europe_map.py`** — каталог 175 городов, совпадение с браузерным каталогом, неоднозначные географические названия, пакетная загрузка, частичный отказ и API европейской карты.
- **`tests/test_frontend.py`** — браузерные сценарии (Playwright): демо/пауза/режимы, анимации, объяснения, интенсивность, облачность, 5 стадий, европейская и старая версии. Некоторые тесты имеют предварительные условия по окружению; не считать их автоматически выполненными.

### Документация и проектная конфигурация

- **`README.md`** — общая документация, запуск, модель погоды, развитие проекта. Значительный файл; для локальных изменений **не перечитывать целиком**.
- **`docs/europe-map.md`** — происхождение композиции, 175 городов, уточнения геокодирования, поведение API и зафиксированные проверки.
- **`docs/reference/Europe Typographic City Map.png`** — изображение-референс, не исполняемый код.
- **`AGENTS.md`** — указания для Codex, безопасность Git, архитектурные ограничения и правила экономной работы.
- **`requirements.txt`** — зависимости Python-приложения.
- **`requirements-dev.txt`** — `requirements.txt` плюс pytest, httpx, Playwright.
- **`.gitignore`** — исключения для окружений, кешей, секретов и логов.

## Карта основных зависимостей

```text
backend/map-layout.json  ──┐
                            ├─> tools/build_city_map.py ─> frontend/map-cities.js
backend/map-geocoding.json ┘                                  │
            │                                                  v
            └─> backend/config.py ─> EUROPE_CITIES         frontend/app.js
                          │                                   ^
                          v                                   │
Open-Meteo <─> backend/weather_api.py <─> backend/weather_logic.py
                          │                                   │
                          └──── backend/main.py ── /api/weather ┘

frontend/index.html ──> frontend/style.css + map-cities.js + app.js
frontend/legacy/index.html ──> legacy/style.css + legacy/app.js
backend/main.py ──> обслуживает всю папку frontend/ как статические файлы
```

Обратите внимание: `backend/config.py` считывает исходные JSON при запуске Python, а браузер читает **отдельно сгенерированный** `frontend/map-cities.js`; при изменении каталога надо сохранять синхронность.

## Минимальные проверки по затронутой области

- Правки только CSS/HTML: браузерная проверка изменённой страницы, при необходимости конкретный сценарий в `tests/test_frontend.py`.
- Правки только отрисовки в `frontend/app.js`: проверить затронутый эффект в демо; запускать при необходимости **один** подходящий браузерный тест, не все.
- `backend/weather_logic.py` / пороги: `python -m pytest tests/test_weather.py -q`.
- `backend/weather_api.py` (пакетные запросы): `python -m pytest tests/test_europe_map.py -q`; при изменении кеша также `tests/test_weather.py`.
- JSON-каталог / генератор: `python tools/build_city_map.py` и `python -m pytest tests/test_europe_map.py -q`.
- Изменение общего JSON-контракта, запуска сервера или выпуска релиза: согласованная более широкая проверка.

Не устанавливай зависимости, не запускай все тесты, не делай повторный запуск тестов после каждой микроправки и не выполняй Git commit / push без отдельной просьбы пользователя. При обнаружении проблемы в смежном файле сначала сообщи о ней, не расширяй задачу молча.

## Известные ловушки

1. `frontend/app.js` реализует **и эффекты, и API-запросы браузера**: правка визуального алгоритма не требует чтения всего серверного кода.
2. В `AGENTS.md` ранее описывался `frontend/weather-effects.js` как **планируемый**: такого файла в архиве нет; не создавай его автоматически.
3. Цветные буквы и облака задаются функцией `draw` в JS, а не CSS.
4. Редактирование `frontend/map-cities.js` напрямую будет потеряно при следующей генерации.
5. `frontend/legacy/` — отдельный снимок старой версии, обычно не изменяется вместе с основной картой.
6. `frontend/index.html` содержит статический текст о длительности первой демосцены, но фактическая длительность в `frontend/app.js` задаётся `STAGE_SECONDS=6`; при изменениях синхронизируй интерфейс и поведение.
7. Проект не содержит конфигурации Cloudflare Pages Functions или другого хостинга в этой версии архива. Инфраструктурные файлы нельзя предполагать существующими.

## Поддержание карты

Обновляй этот документ только если добавлены/переименованы/удалены файлы, изменены их роли или значимые связи. Для косметических правок карту не переписывай.
