from flask import Flask, request, jsonify
import os
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="Mus8aOwbBIg4TAA")  # ← Замени на свой

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)
spreadsheet_id = "1Ao-"
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🔍 GPT-извлечение ключевых слов ===
def extract_keywords_from_text(text):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты бот медицинской лаборатории. Извлекай конкретные названия анализов, витаминов и микроэлементов из запроса пользователя. "
                    "Возвращай только список через запятую, без пояснений. Примеры:\n"
                    "Запрос: 'Хочу проверить витамины' → 'витамин D, витамин B12, фолиевая кислота, железо, магний'\n"
                    "Запрос: 'Нужно сдать анализы на печень' → 'АЛТ, АСТ, билирубин, щелочная фосфатаза'\n"
                    "Запрос: 'Обследование щитовидки' → 'ТТГ, Т3 свободный, Т4 свободный, антитела к ТПО'"
                )
            },
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    keywords = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", keywords)
    return [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]

# === 🔎 Улучшенный поиск по ключам ===
def contains_exact_word(text, word):
    # Учитываем разные формы слов и опечатки
    pattern = r'\b' + re.escape(word) + r'(а|у|е|ом|ы|ов|ах|ам|и|я|ю|ем|ой|ий|ь)?\b'
    return re.search(pattern, text.lower())

def search_rows_by_keywords(keywords):
    matches = []
    keyword_variants = {}
    
    # Создаем варианты ключевых слов (например, "вит.D" → "витамин D")
    variants_map = {
        "вит.d": "витамин d",
        "b12": "витамин b12",
        "ттг": "тиреотропный гормон",
        # Добавьте другие варианты по необходимости
    }
    
    expanded_keywords = []
    for kw in keywords:
        expanded_keywords.append(kw)
        if kw in variants_map:
            expanded_keywords.append(variants_map[kw])
    
    for row in rows:
        name = str(row.get("Наименование", "")).lower()
        description = str(row.get("Описание", "")).lower()
        
        # Проверяем как по названию, так и по описанию
        for kw in set(expanded_keywords):  # Используем set для уникальности
            if (contains_exact_word(name, kw) or 
                contains_exact_word(description, kw)):
                matches.append(row)
                break
    
    return matches

# === 📝 Форматирование ответа ===
def format_response(results):
    if not results:
        return "❌ Анализы не найдены. Уточните, пожалуйста, что именно вы хотите проверить."
    
    response_lines = []
    for i, row in enumerate(results[:10], 1):  # Ограничиваем 10 результатами
        name = row.get("Наименование", "Анализ")
        price = row.get("Цена", "?")
        days = row.get("Срок исп.", "?")
        
        response_lines.append(
            f"{i}️⃣ {name}\n"
            f"💰 Цена — {price} руб.\n"
            f"⏱️ Срок — {days}\n"
        )
    
    return "\n".join(response_lines)

# === 🌐 API ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "").strip()
    if not user_message:
        return jsonify({"response": "❗ Пожалуйста, укажите, какие анализы вас интересуют."})
    
    try:
        keywords = extract_keywords_from_text(user_message)
        print("🔑 Извлеченные ключевые слова:", ", ".join(keywords))
        
        results = search_rows_by_keywords(keywords)
        response_text = format_response(results)
        
        return jsonify({
            "response": response_text,
            "keywords": keywords  # Для отладки
        })
        
    except Exception as e:
        print(f"⚠️ Ошибка: {str(e)}")
        return jsonify({
            "response": "🔧 Произошла техническая ошибка. Пожалуйста, попробуйте позже или уточните ваш запрос."
        })

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
