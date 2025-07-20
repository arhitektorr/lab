from flask import Flask, request, jsonify
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="")  # ← Вставь сюда свой OpenAI API ключ

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)

spreadsheet_id = ""  # ← Вставь сюда ID своей таблицы
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
        "Твоя задача — выбрать только те названия из списка, которые подходят. "
        "Если в сообщении нет ничего понятного — верни пустой ответ. "
        "Не придумывай названия. Не объясняй. Верни только подходящие названия анализов через запятую."
    )

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]
    )

    raw_text = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", raw_text)

    # Фильтрируем некорректные ответы
    bad_phrases = ["пожалуйста", "напишите", "не понял", "что вы хотите", "анализы вы хотите сдать"]
    if any(phrase in raw_text.lower() for phrase in bad_phrases):
        return []

    return [kw.strip().lower() for kw in raw_text.split(",") if kw.strip()]

# === 🔍 Поиск в таблице по ключевым словам ===
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

# === 🌐 Эндпоинт анализа запроса ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "")
    if not user_message:
        return jsonify({"response": "❗ Запрос пустой."})

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи GPT:", keywords)

    if not keywords:
        return jsonify({"response": "❌ Ничего не найдено по вашему запросу. Попробуйте сформулировать точнее."})

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 {row['Цена']} руб.\n⏱️ Срок — {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        return jsonify({"response": "\n\n".join(response_lines)})
    else:
        return jsonify({"response": "❌ Ничего не найдено по вашему запросу. Попробуйте переформулировать."})

# === ▶ Запуск приложения ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
