from flask import Flask, request, jsonify
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔐 OpenAI ===
client = openai.OpenAI(api_key="sk-...")  # ВСТАВЬ СВОЙ КЛЮЧ

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)

spreadsheet_id = "..."  # ВСТАВЬ ID своей таблицы
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)

# === 📌 Соберём доступные названия анализов
available_names = [str(row.get("Наименование", "")).strip() for row in rows]

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🧠 GPT: извлечение ключевых слов из текста ===
def extract_keywords_from_text(text):
    available_str = ", ".join(available_names[:300])  # Ограничим для GPT

    prompt = (
        "Ты бот лаборатории. Пользователь пишет, какие анализы он хочет сдать. "
        "Вот список всех анализов, доступных в прайсе:\n"
        f"{available_str}\n\n"
        "Верни только те названия, которые подходят под его запрос — без лишних слов, без выдумки. "
        "Если пользователь пишет ерунду или непонятный запрос — верни пустой ответ.\n"
        "Формат: просто список подходящих анализов через запятую, без пояснений и без кавычек."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]
    )

    raw = response.choices[0].message.content.strip()
    print("🧠 GPT вернул:", raw)

    # Если GPT всё же сгенерировал что-то странное
    if "ничего" in raw.lower() or raw.strip() == "":
        return []

    return [kw.strip().lower() for kw in raw.split(",") if kw.strip()]

# === 🔍 Поиск по ключевым словам в строке
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

# === 🌐 API
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "")
    if not user_message:
        return jsonify({"response": "❗ Запрос пустой."})

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи:", keywords)

    if not keywords:
        return jsonify({"response": "❌ Ничего не найдено по запросу. Попробуйте переформулировать."})

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 Цена — {row['Цена']} руб.\n⏱️ Срок — {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        return jsonify({"response": "\n\n".join(response_lines)})
    else:
        return jsonify({"response": "❌ Ничего не найдено по вашему запросу."})

# === ▶ Запуск
if __name__ == "__main__":
    app.run(debug=True, port=5000)
