from flask import Flask, request, jsonify
import os
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="")

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)
spreadsheet_id = "1Ao-df"
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🔍 GPT-извлечение ключевых слов ===
def extract_keywords_from_text(text):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты бот лаборатории. Пользователь пишет, какие анализы хочет сдать. "
                    "Твоя задача — вернуть список конкретных витаминов или микроэлементов, через запятую. "
                    "Никаких общих слов: не пиши 'общий анализ крови', 'биохимия', 'печень', 'здоровье', 'чек-ап'. "
                    "Если пользователь пишет просто 'витамины', верни список типа: 'витамин D, витамин B12, фолиевая кислота, ферритин, магний, цинк'. "
                    "Ответ должен быть только списком ключевых слов, без объяснений и лишних слов."
                )
            },
            {"role": "user", "content": text}
        ]
    )
    keywords = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", keywords)
    return [kw.strip().lower() for kw in response.choices[0].message.content.split(",")]

# === 🔎 Поиск по ключам ===
def contains_exact_word(text, word):
    pattern = r'\b' + re.escape(word) + r'(а|у|е|ом|ы|ов|ах|ам)?\b'
    return re.search(pattern, text.lower())

def search_rows_by_keywords(keywords):
    matches = []
    for row in rows:
        name = str(row.get("Наименование", "")).lower()
        if any(contains_exact_word(name, kw) for kw in keywords):
            matches.append(row)
    return matches

# === 🌐 API ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "")
    if not user_message:
        return jsonify({"response": "❗ Запрос пустой."})

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи GPT:", keywords)

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 Цена — {row['Цена']} руб.\n⏱️ Срок — {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        return jsonify({"response": "\n\n".join(response_lines)})
    else:
        return jsonify({"response": "❌ Ничего не найдено по вашему запросу."})

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
