from flask import Flask, request, jsonify
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="sk-...")  # Вставь свой API ключ

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)

spreadsheet_id = "1Ao-FgsBLHau3SDH3HfjTOlmO1q16F8EBKsU46znOHgE"  # Заменить на свой
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)
available_names = [str(row.get("Наименование", "")).strip() for row in rows]

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🧠 GPT: анализ запроса и извлечение ключей ===
def extract_keywords_from_text(text):
    available_str = ", ".join(available_names[:300])  # ограничение по токенам

    prompt = (
        "Ты бот лаборатории. Ниже список анализов из прайса:\n"
        f"{available_str}\n\n"
        "Пользователь написал, какие анализы он хочет сдать. "
        "Верни только названия из прайса, которые подходят под запрос. "
        "Никаких выдуманных названий, никаких пояснений — только список подходящих анализов через запятую."
    )

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", raw)
    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]

# === 🔎 Поиск в таблице по ключевым словам ===
def search_rows_by_keywords(keywords):
    matches = []
    for row in rows:
        name = str(row.get("Наименование", "")).lower()
        if any(kw in name for kw in keywords):
            matches.append(row)
    return matches

# === 🌐 Эндпоинт анализа запроса ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "").strip()
    if not user_message:
        return jsonify({"response": "❗ Пустой запрос. Уточните, какие анализы вас интересуют."})

    keywords = extract_keywords_from_text(user_message)

    if not keywords or all(len(kw) < 2 for kw in keywords):
        return jsonify({"response": "❌ Не удалось понять ваш запрос. Попробуйте уточнить формулировку."})

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 Цена: {row['Цена']} руб.\n⏱️ Срок: {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        return jsonify({"response": "\n\n".join(response_lines)})
    else:
        return jsonify({"response": "❌ Ничего не найдено по вашему запросу. Попробуйте уточнить запрос."})

# === ▶ Запуск приложения  фф===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
