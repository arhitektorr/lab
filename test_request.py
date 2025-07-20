import requests
import json

data = {
    "text": "Болит почка"
}

response = requests.post("http://127.0.0.1:5000/analyze", json=data)

print("📡 Статус ответа:", response.status_code)

try:
    decoded = response.json()
    print("\n🔍 Ответ:\n" + decoded.get("response", "❌ Нет данных в ответе"))
except json.JSONDecodeError:
    print("❌ Ошибка при декодировании JSON:")
    print(response.text)
