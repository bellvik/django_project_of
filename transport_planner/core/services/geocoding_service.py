import time
import random
import requests
from abc import ABC, abstractmethod
from django.conf import settings

class BaseGeocodingService(ABC):
    @abstractmethod
    def geocode(self, query: str):
        pass

class StubGeocodingService(BaseGeocodingService):
    """Заглушка для геокодирования. Возвращает фиктивные координаты."""
    
    EKB_PLACES = {
        "жд вокзал": {"address": "Екатеринбург, Вокзальная ул., 22", "lat": 56.838011, "lon": 60.597465},
        "цирк": {"address": "Екатеринбург, ул. 8 Марта, 43", "lat": 56.837814, "lon": 60.613200},
        "площадь 1905 года": {"address": "Екатеринбург, пл. 1905 года", "lat": 56.8379, "lon": 60.5975},
        "упи": {"address": "Екатеринбург, ул. Мира, 19", "lat": 56.8440, "lon": 60.6532},
        "киноплекс": {"address": "Екатеринбург, ул. Луначарского, 137", "lat": 56.8512, "lon": 60.6123},
    }
    
    def geocode(self, query):
        time.sleep(0.3 + random.random() * 0.5)
        
        query_lower = query.lower()
        results = []

        if query_lower in self.EKB_PLACES:
            place = self.EKB_PLACES[query_lower]
            results.append({
                "address": place["address"],
                "lat": place["lat"],
                "lon": place["lon"],
                "score": 0.95
            })
        else:
            for name, place in self.EKB_PLACES.items():
                if query_lower in name or name in query_lower:
                    results.append({
                        "address": place["address"],
                        "lat": place["lat"] + random.uniform(-0.005, 0.005),
                        "lon": place["lon"] + random.uniform(-0.005, 0.005),
                        "score": 0.7 + random.random() * 0.2
                    })
        
        if not results:
            results.append({
                "address": f"Екатеринбург, район запроса: {query}",
                "lat": 56.8380 + random.uniform(-0.02, 0.02),
                "lon": 60.5975 + random.uniform(-0.02, 0.02),
                "score": 0.5
            })
        
        return {
            "results": results[:3],
            "source": "stub_geocoder"
        }


class TomTomGeocodingService(BaseGeocodingService):
    """Реальный сервис геокодирования через TomTom Search API"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.tomtom.com/search/2/search"
    
    def geocode(self, query: str):
        try:
            params = {
                'key': self.api_key,
                'query': query,
                'limit': 5,
                'language': 'ru-RU',
                'countrySet': 'RU',
                'lat': 56.8379,
                'lon': 60.5975,
            }
            
            response = requests.get(f"{self.base_url}/{query}.json", params=params)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('results', []):
                address_obj = item.get('address', {})
                address_parts = []
                if address_obj.get('streetName'):
                    street = address_obj['streetName']
                    if address_obj.get('streetNumber'):
                        street += f", {address_obj['streetNumber']}"
                    address_parts.append(street)
                
                if address_obj.get('municipality'):
                    address_parts.append(address_obj['municipality'])
                
                if address_obj.get('countrySubdivision'):
                    address_parts.append(address_obj['countrySubdivision'])
                
                address = ', '.join(address_parts)
                position = item.get('position', {})
                lat = position.get('lat')
                lon = position.get('lon')
                
                if lat and lon:
                    results.append({
                        "address": address,
                        "lat": lat,
                        "lon": lon,
                        "score": item.get('score', 0) / 10,  
                        "type": item.get('type', '')
                    })
            
            return {
                "results": results[:3],
                "source": "tomtom",
                "total_results": data.get('summary', {}).get('totalResults', 0)
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Ошибка TomTom Geocoding API: {e}")
            
            stub_service = StubGeocodingService()
            return stub_service.geocode(query)