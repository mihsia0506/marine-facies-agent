"""
title: Sea Day (Date/Place -> Tide/Wave/WaterTemp/Wind)
author: you
version: 0.2.0
description: Input (date, place). Query Storm Glass for tide, wave height, water temperature, wind speed for the whole day.
"""

from __future__ import annotations

import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, date as _date
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


STORMGLASS_WEATHER_POINT = "https://api.stormglass.io/v2/weather/point"
STORMGLASS_TIDE_EXTREMES_POINT = "https://api.stormglass.io/v2/tide/extremes/point"
GOOGLE_GEOCODE_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"


def _http_get_json(
    url: str, headers: Optional[Dict[str, str]] = None, timeout_sec: int = 15
) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _day_range_to_utc_timestamps(date_yyyy_mm_dd: str, tz_name: str) -> Tuple[int, int]:
    if ZoneInfo is None:
        raise RuntimeError(
            "zoneinfo not available. Use Python 3.9+ or provide timestamps directly."
        )
    tz = ZoneInfo(tz_name)
    day_start_local = datetime.strptime(date_yyyy_mm_dd, "%Y-%m-%d").replace(tzinfo=tz)
    next_day_start_local = day_start_local + timedelta(days=1)
    start_utc = int(day_start_local.astimezone(ZoneInfo("UTC")).timestamp())
    end_utc = int(next_day_start_local.astimezone(ZoneInfo("UTC")).timestamp())
    return start_utc, end_utc


def _google_geocode_place(
    place: str,
    api_key: str,
    language: str = "zh-TW",
    region: str = "tw",
    timeout_sec: int = 10,
) -> Dict[str, Any]:
    place = (place or "").strip()
    if not place:
        return {"ok": False, "error": "place is required"}

    if not api_key:
        return {"ok": False, "error": "Missing GOOGLE_MAPS_API_KEY env var"}

    params = {
        "address": place,
        "key": api_key,
        "language": language,
        "region": region,
    }
    url = GOOGLE_GEOCODE_ENDPOINT + "?" + urllib.parse.urlencode(params)

    try:
        data = _http_get_json(url, headers=None, timeout_sec=timeout_sec)
    except Exception as e:
        return {"ok": False, "error": f"HTTP/parse error: {e.__class__.__name__}: {e}"}

    status = data.get("status", "UNKNOWN")
    if status != "OK":
        return {
            "ok": False,
            "query": place,
            "status": status,
            "error": data.get("error_message") or f"Geocoding failed: {status}",
        }

    results = data.get("results") or []
    if not results:
        return {"ok": False, "query": place, "status": status, "error": "No results"}

    top = results[0]
    geometry = top.get("geometry", {}) or {}
    location = geometry.get("location", {}) or {}
    lat = location.get("lat")
    lng = location.get("lng")

    if lat is None or lng is None:
        return {
            "ok": False,
            "query": place,
            "status": status,
            "error": "Missing lat/lng in response",
        }
    return {
        "ok": True,
        "lat": lat,
        "lng": lng,
        "formatted_address": top.get("formatted_address"),
    }


def _stormglass_weather(
    lat: float,
    lng: float,
    start_utc: int,
    end_utc: int,
    api_key: str,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    params = "swellHeight,waterTemperature,windSpeed"
    qs = urllib.parse.urlencode(
        {"lat": lat, "lng": lng, "params": params, "start": start_utc, "end": end_utc}
    )
    url = f"{STORMGLASS_WEATHER_POINT}?{qs}"
    headers = {"Authorization": api_key}
    return _http_get_json(url, headers=headers, timeout_sec=timeout_sec)


def _stormglass_tide_extremes(
    lat: float,
    lng: float,
    start_utc: int,
    end_utc: int,
    api_key: str,
    timeout_sec: int = 20,
) -> Dict[str, Any]:
    qs = urllib.parse.urlencode(
        {"lat": lat, "lng": lng, "start": start_utc, "end": end_utc}
    )
    url = f"{STORMGLASS_TIDE_EXTREMES_POINT}?{qs}"
    headers = {"Authorization": api_key}
    return _http_get_json(url, headers=headers, timeout_sec=timeout_sec)


def _safe_minmax(vals: List[float]) -> Optional[Dict[str, float]]:
    if not vals:
        return None
    return {"min": float(min(vals)), "max": float(max(vals))}


def _pick_value(param_obj: Any) -> Optional[float]:
    if isinstance(param_obj, (int, float)):
        return float(param_obj)
    if isinstance(param_obj, dict) and param_obj:
        first_key = next(iter(param_obj.keys()))
        v = param_obj.get(first_key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


class Tools:
    def __init__(self) -> None:
        self.storm_key = os.getenv("STORMGLASS_API_KEY", "").strip()
        self.google_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

    def sea_day(
        self,
        date: str,
        place: str,
        timezone: str = "Asia/Taipei",
        timeout_sec: int = 20,
    ) -> Dict[str, Any]:
        """
        Args:
            date: "YYYY-MM-DD" (local date in timezone)
            lat/lng: coordinates
            timezone: default Asia/Taipei
        """
        date = (date or "").strip()
        if not date:
            date = _date.today().isoformat()

        if not self.storm_key:
            return {"ok": False, "error": "Missing STORMGLASS_API_KEY env var"}

        # time range
        try:
            start_utc, end_utc = _day_range_to_utc_timestamps(date, timezone)
        except Exception:

            date = _date.today().isoformat()
            try:
                start_utc, end_utc = _day_range_to_utc_timestamps(date, timezone)
            except Exception as e:
                return {
                    "ok": False,
                    "stage": "time_range",
                    "error": f"{e.__class__.__name__}: {e}",
                }

        geocode_info = _google_geocode_place(
            place=place,
            api_key=self.google_key,
            language="zh-TW",
            region="tw",
            timeout_sec=min(10, timeout_sec),
        )
        if not geocode_info.get("ok"):
            return {
                "ok": False,
                "stage": "geocoding",
                "error": geocode_info.get("error", "Geocoding failed"),
                "geocode": geocode_info,
            }
        lat = float(geocode_info["lat"])
        lng = float(geocode_info["lng"])

        # queries
        try:
            weather = _stormglass_weather(
                lat, lng, start_utc, end_utc, self.storm_key, timeout_sec=timeout_sec
            )
        except Exception as e:
            return {
                "ok": False,
                "stage": "stormglass_weather",
                "error": f"{e.__class__.__name__}: {e}",
            }

        try:
            extremes = _stormglass_tide_extremes(
                lat, lng, start_utc, end_utc, self.storm_key, timeout_sec=timeout_sec
            )
        except Exception as e:
            extremes = {"error": f"{e.__class__.__name__}: {e}", "data": None}

        hours = weather.get("hours") or []
        hourly: List[Dict[str, Any]] = []
        wave_vals: List[float] = []
        wind_vals: List[float] = []
        water_temp_vals: List[float] = []

        for h in hours:
            # 取得原始 UTC 時間字串
            utc_time_str = h.get("time")
            local_time_str = utc_time_str
            
            if utc_time_str:
                try:
                    utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
                    local_dt = utc_dt.astimezone(ZoneInfo(timezone))
                    local_time_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

            tide_v = _pick_value(h.get("tide"))
            wave_v = _pick_value(h.get("swellHeight"))
            wt_v = _pick_value(h.get("waterTemperature"))
            wind_v = _pick_value(h.get("windSpeed"))


            if wave_v is not None:
                wave_vals.append(wave_v)
            if wt_v is not None:
                water_temp_vals.append(wt_v)
            if wind_v is not None:
                wind_vals.append(wind_v)

            hourly.append(
                {
                    "time_local": local_time_str,  # 新增轉換後的本地時間
                    "time_utc": utc_time_str,
                    "tide": tide_v,
                    "swellHeight": wave_v,
                    "waterTemperature": wt_v,
                    "windSpeed": wind_v,
                }
            )

        return {
            "ok": True,
            "query": {"date": date, "timezone": timezone},
            "location": {"lat": float(lat), "lng": float(lng)},
            "range_utc": {"start": start_utc, "end": end_utc},
            "summary": {
                "swellHeight": _safe_minmax(wave_vals),
                "waterTemperature": _safe_minmax(water_temp_vals),
                "windSpeed": _safe_minmax(wind_vals),
            },
            "hourly": hourly,
            "tide_extremes": extremes,
            "raw": {"stormglass_weather_meta": weather.get("meta")},
        }
