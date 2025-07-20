from flask import Flask, request, Response
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

# === ⚙️ Flask App ===
app = Flask(__name__)

# === 🧠 GPT: извлечение ключей из текста ===
def extract_keywords_from_text(text):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты бот лаборатории. Пользователь пишет, какие анализы хочет сдать. "
                    "Твоя задача — вернуть список конкретных витаминов, гормонов, микроэлементов или тестов через запятую. "
                    "Не пиши общие слова: например 'биохимия', 'здоровье', 'чек-ап', 'провериться', 'анализ крови'. "
                    "Если пользователь пишет что-то абстрактное, верни примерные подходящие анализы. "
                    "Если непонятно — ничего не выдумывай и верни пустой ответ. "
                    "Ответ должен быть строго списком ключевых слов через запятую, без пояснений."
                )
            },
            {"role": "user", "content": text}
        ]
    )
    keywords = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", keywords)
    return [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]

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
        return Response("❗ Запрос пустой.", content_type="text/plain; charset=utf-8")

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи GPT:", keywords)

    if not keywords:
        return Response("❌ Не удалось распознать, какие анализы вас интересуют. Попробуйте переформулировать запрос.", content_type="text/plain; charset=utf-8")

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n💰 Цена — {row['Цена']} руб.\n⏱️ Срок — {row['Срок исп.']}"
            for i, row in enumerate(results[:10])
        ]
        final_text = "\n\n".join(response_lines)
    else:
        final_text = "❌ Ничего не найдено по вашему запросу. Попробуйте иначе сформулировать."

    return Response(final_text, content_type="text/plain; charset=utf-8")

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
