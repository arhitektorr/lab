from flask import Flask, request, jsonify
import os
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

app = Flask(__name__)

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="your-api-key")  # ← Убедитесь, что ключ правильный

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)
spreadsheet_id = "your-spreadsheet-id"
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)

# === 🔍 GPT-извлечение ключевых слов ===
def extract_keywords_from_text(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Используйте актуальную модель
            messages=[
                {
                    "role": "system",
                    "content": "Ты — медицинский поисковый ассистент. Анализируй запросы пользователей и строго выдавай только релевантные ключевые слова для поиска лабораторных анализов. Формат ответа: ключевые слова через запятую на русском языке в lowercase, без точек, без дополнительных объяснений. Если запрос не связан с медициной — отвечай 'Нет ключевых слов'."
                },
                {"role": "user", "content": text}
            ],
            temperature=0.3  # Для более предсказуемых результатов
        )
        
        keywords = response.choices[0].message.content.strip()
        print("🧠 GPT вернул ключевые слова:", keywords)
        
        if keywords == "Нет ключевых слов":
            return []
            
        return [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]
    
    except Exception as e:
        print(f"❌ Ошибка при запросе к OpenAI: {str(e)}")
        return []

# === 🔎 Поиск по ключам ===
def contains_exact_word(text, word):
    if not text or not word:
        return False
    pattern = r'\b' + re.escape(word) + r'(а|у|е|ом|ы|ов|ах|ам)?\b'
    return re.search(pattern, str(text).lower())

def search_rows_by_keywords(keywords):
    matches = []
    if not keywords:
        return matches
        
    for row in rows:
        name = str(row.get("Наименование", "")).lower()
        description = str(row.get("Описание", "")).lower()
        
        # Ищем совпадения в названии и описании
        for kw in keywords:
            if (contains_exact_word(name, kw) or 
                contains_exact_word(description, kw)):
                matches.append(row)
                break
                
    return matches

# === 🌐 API ===
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        user_message = request.json.get("text", "").strip()
        if not user_message:
            return jsonify({"error": "Пустой запрос"}), 400

        print("📩 Получен запрос:", user_message)
        keywords = extract_keywords_from_text(user_message)
        print("🔑 Извлеченные ключевые слова:", keywords)

        if not keywords:
            return jsonify({"response": "Не удалось определить медицинские анализы по вашему запросу"})

        results = search_rows_by_keywords(keywords)

        if results:
            response_data = [
                {
                    "name": row.get("Наименование", ""),
                    "price": row.get("Цена", ""),
                    "duration": row.get("Срок исп.", "")
                }
                for row in results[:10]  # Ограничиваем количество результатов
            ]
            return jsonify({"response": response_data})
        else:
            return jsonify({"response": "Анализы не найдены"})
            
    except Exception as e:
        print(f"⚠️ Ошибка обработки запроса: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
