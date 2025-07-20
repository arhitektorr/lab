from flask import Flask, request, Response
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="")  # ← Вставь свой OpenAI API ключ

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)
spreadsheet_id = ""  # ← Вставь ID таблицы
sheet = gs_client.open_by_key(spreadsheet_id).sheet1
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🧠 Извлечение ключевых слов через GPT ===
def extract_keywords_from_text(text):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты бот лаборатории. Пользователь пишет, какие анализы он хочет сдать — в свободной форме. "
                    "Верни список только конкретных анализов (например: 'глюкоза', 'витамин D', 'ферритин'), "
                    "только из запроса, никаких выдуманных или предполагаемых слов. "
                    "Если запрос не имеет отношения к анализам или непонятен — верни пустой ответ (ничего). "
                    "Ответ должен быть строго списком ключевых слов через запятую, без лишних слов и пояснений."
                )
            },
            {"role": "user", "content": text}
        ]
    )
    keywords = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", keywords)
    return [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]

# === 🔍 Поиск по таблице ===
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

# === 🌐 Эндпоинт ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "")
    if not user_message:
        return Response("❗ Запрос пустой.", content_type="text/plain; charset=utf-8")

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи GPT:", keywords)

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 Цена — {row['Цена']} руб.\n⏱️ Срок — {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        return Response("\n\n" + "\n\n".join(response_lines), content_type="text/plain; charset=utf-8")
    else:
        return Response("❌ Ничего не найдено по вашему запросу. Попробуйте уточнить формулировку.", content_type="text/plain; charset=utf-8")

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
