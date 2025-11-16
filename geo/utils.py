from django.conf import settings
import requests

from .models import GeocodedAddress


YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x"


def fetch_coordinates(address: str):
    """
    Возвращает объект GeocodedAddress для адреса.

    1) Сначала ищет в таблице GeocodedAddress.
    2) Если нет, обращается к Yandex Geocoder API, сохраняет ответ в БД и возвращает координаты.
    3) Если не удалось найти, возвращает None.
    """
    if not address:
        print("Пустой адрес")
        return None

    cached = GeocodedAddress.objects.filter(address=address).first()
    if cached and cached.lat is not None and cached.lng is not None:
        print(f"Из кеша: {address} -> ({cached.lat}, {cached.lng})")
        return cached

    api_key = getattr(settings, "YANDEX_GEOCODER_API_KEY", None)
    if not api_key:
        print("Нет API-ключа Яндекса в settings.YANDEX_GEOCODER_API_KEY")
        return cached

    params = {
        "apikey": api_key,
        "geocode": address,
        "format": "json",
    }

    try:
        response = requests.get(YANDEX_GEOCODER_URL, params=params, timeout=5)
    except Exception as e:
        print(f"Ошибка сети при запросе к Яндекс Геокодеру для '{address}': {e}")
        return cached

    if response.status_code != 200:
        print(f"Яндекс вернул статус {response.status_code} для '{address}': {response.text[:200]}")
        return cached

    response_data = response.json()
    try:
        members = response_data["response"]["GeoObjectCollection"]["featureMember"]
        if not members:
            print(f"Яндекс не нашёл объект для '{address}'")
            return cached

        geo_object = members[0]["GeoObject"]
        pos = geo_object["Point"]["pos"]
        lon_str, lat_str = pos.split()
        lat, lon = float(lat_str), float(lon_str)
    except Exception as e:
        print(f"Ошибка разбора ответа Яндекса для '{address}': {e}")
        return cached

    obj, _ = GeocodedAddress.objects.update_or_create(
        address=address,
        defaults={
            "lat": lat,
            "lng": lon,
            "provider": "yandex",
        },
    )

    print(f"От Яндекса: {address} -> ({lat}, {lon})")
    return obj
