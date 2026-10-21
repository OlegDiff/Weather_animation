"""Static export contract, failure preservation and publication allowlist."""
from datetime import datetime, timedelta, timezone
import json
from urllib.error import URLError

import pytest

from backend.weather_api import WeatherService
from backend.weather_logic import FIELDS
from tools import build_pages


def weather_batch(cities):
    current = dict(temperature_2m=12, precipitation=0, rain=0, showers=0,
                   snowfall=0, wind_speed_10m=10, wind_direction_10m=230,
                   cloud_cover=10, weather_code=0, is_day=1, interval=900,
                   time=datetime.now(timezone.utc).isoformat())
    return {c['id']: {'utc_offset_seconds': 0, 'current': dict(current),
                     'current_units': {**{v[0]: v[1] for v in FIELDS.values()},
                                       'interval': 'seconds'}} for c in cities}


def test_static_export_matches_api_and_contains_only_public_assets(tmp_path, monkeypatch):
    service = WeatherService(cities=build_pages.PAGES_CITIES, batch_fetcher=weather_batch)
    expected = service.get_weather()
    monkeypatch.setattr(build_pages, 'WeatherService', lambda **kwargs: service)
    result = build_pages.build_site(tmp_path)
    stored = json.loads((tmp_path / 'data/weather.json').read_text(encoding='utf-8'))
    assert stored == result
    for key in ('source', 'source_url', 'data_kind', 'mode', 'cities', 'status'):
        assert result[key] == expected[key]
    assert len(result['cities']) == 176
    assert result['refresh_interval_seconds'] == 3600
    assert {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*') if p.is_file()} == {
        *build_pages.ASSETS, 'data/weather.json', '.nojekyll'}
    assert 'data-weather-url="data/weather.json"' in (tmp_path / 'index.html').read_text(encoding='utf-8')
    assert 'data-weather-url="../data/weather.json"' in (tmp_path / 'legacy/index.html').read_text(encoding='utf-8')
    assert 'href="/' not in (tmp_path / 'index.html').read_text(encoding='utf-8')
    assert {'dublin-ie', 'helsinki', 'paris-fr', 'madrid-es'} <= {c['id'] for c in result['cities']}


@pytest.mark.parametrize('failure', ['total', 'partial', 'stale', 'malformed'])
def test_failed_refresh_keeps_previous_site(tmp_path, failure):
    build_pages.build_site(tmp_path, weather_batch)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    def failing(cities):
        batch = weather_batch(cities)
        if failure == 'total':
            return {c['id']: URLError('offline') for c in cities}
        if failure == 'partial':
            batch[cities[0]['id']] = URLError('offline')
        if failure == 'stale':
            for value in batch.values():
                value['current']['time'] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        if failure == 'malformed':
            return {c['id']: {} for c in cities}
        return batch

    with pytest.raises(ValueError, match='Incomplete or stale'):
        build_pages.build_site(tmp_path, failing)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_rejects_unexpected_files_in_public_output(tmp_path):
    (tmp_path / '.env').write_text('private')
    with pytest.raises(ValueError, match='Unexpected output entry'):
        build_pages.build_site(tmp_path, weather_batch)
    assert not (tmp_path / 'data/weather.json').exists()
