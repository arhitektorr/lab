from flask import Flask, request, jsonify
import os
import re
import gspread
from google.oauth2.service_account import Credentials
import openai
import threading
import time

app = Flask(__name__)

# === Конфиг ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "your-spreadsheet-id")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
CACHE_TTL = 300  # секунд

# === OpenAI ===
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scope)
gs_client = gspread.authorize(creds)

# === Кэш для данных из Google Sheets ===
class SheetCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self.data = []
        self.last_update = 0
        self.lock = threading.Lock()
    
    def get_data(self):
        with self.lock:
            now = time.time()
            if now - self.last_update > self.ttl or not self.data:
                print("🔄 Обновление данных из Google Sheets...")
                sheet = gs_client.open_by_key(SPREADSHEET_ID).sheet1
                header_row = sheet.row_values(2)
                self.data = sheet.get_all_records(head=2, expected_headers=header_row)
                self.last_update = now
            return self.data

sheet_cache = SheetCache(CACHE_TTL)

# === GPT: Извлечение релевантных ключей ===
def extract_keywords_from_text(text):
    system_prompt = (
        "Ты — медицинский ассистент. Твоя задача — анализировать пользовательский запрос "
        "и возвращать только те ключевые слова, которые однозначно соответствуют лабораторным анализам. "
        "Не добавляй слова, которых нет в запросе. Не повторяй слова. "
        "Ответ: только список ключевых слов через запятую, на русском языке, в нижнем регистре, без точек, без объяснений. "
        "Если запрос не относится к медицинским анализам — верни 'нет ключевых слов'."
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1
        )
        keywords = response.choices[0].message.content.strip()
        print("🧠 GPT ключевые слова:", keywords)
        if keywords.lower() == "нет ключевых слов":
            return []
        # Удаляем дубликаты и пробелы
        return list({kw.strip().lower() for kw in keywords.split(",") if kw.strip()})
    except Exception as e:
        print(f"❌ Ошибка OpenAI: {str(e)}")
        return []

# === Поиск по ключевым словам ===
def contains_word(text, word):
    # Морфологический поиск: ищем слово и его окончания
    pattern = r'\b' + re.escape(word) + r'(а|у|е|ом|ы|ов|ах|ам|ия|ий|ие|ию|ием|ии)?\b'
    return re.search(pattern, str(text).lower())

def search_rows_by_keywords(keywords, rows):
    matches = []
    for row in rows:
        fields = [
            str(row.get("Наименование", "")).lower(),
            str(row.get("Описание", "")).lower(),
            str(row.get("Синонимы", "")).lower(),
        ]
        for kw in keywords:
            if any(contains_word(f, kw) for f in fields):
                matches.append(row)
                break
    return matches

# === API ===
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        user_message = request.json.get("text", "").strip()
        if not user_message:
            return jsonify({"error": "Пустой запрос"}), 400

        print("📩 Запрос:", user_message)
        keywords = extract_keywords_from_text(user_message)
        print("🔑 Ключевые слова:", keywords)

        if not keywords:
            return jsonify({"response": "Не удалось определить медицинские анализы по вашему запросу"})

        rows = sheet_cache.get_data()
        results = search_rows_by_keywords(keywords, rows)

        if results:
            response_data = [
                {
                    "name": row.get("Наименование", ""),
                    "price": row.get("Цена", ""),
                    "duration": row.get("Срок исп.", ""),
                    "description": row.get("Описание", "")
                }
                for row in results[:10]
            ]
            return jsonify({"response": response_data})
        else:
            return jsonify({"response": "Анализы не найдены"})
    except Exception as e:
        print(f"⚠️ Ошибка: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# === Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
