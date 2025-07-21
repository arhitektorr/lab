from flask import Flask, request, jsonify
import os
import re
import gspread
from google.oauth2.service_account import Credentials
import openai

# === 🔑 OpenAI ===
client = openai.OpenAI(api_key="sk-prAA")

# === 📊 Google Sheets ===
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
gs_client = gspread.authorize(creds)
spreadsheet_id = ""
sheet = gs_client.open_by_key(spreadsheet_id).sheet1

# Предварительно грузим список анализов для поиска (это повысит точность поиска через GPT и ручной поиск)
header_row = sheet.row_values(2)
rows = sheet.get_all_records(head=2, expected_headers=header_row)
all_test_names = [str(row.get("Наименование", "")).strip().lower() for row in rows]

# === ⚙️ Flask App ===
app = Flask(__name__)

def clean_name(name):
    return re.sub(r"\s+", " ", name.strip().lower())

# === 🔍 GPT-извлечение ключевых слов ===
def extract_keywords_from_text(text):
    # Промпт, теперь GPT вернет только то, что реально есть в таблице
    prompt = (
        "Ты помощник медицинской лаборатории. Тебе дали полный список анализов (ниже), "
        "и пользователь пишет, что он бы хотел проверить. "
        "Верни только те названия анализов, которые ТИПОГРАФИЧЕСКИ точно встречаются в полном списке анализов. "
        "Если пользователь пишет 'витамины' или что-то обобщенное, выбери только название из списка. "
        "Пример вывода: 'витамин d, витамин b12, ферритин'. "
        "Только список через запятую, никаких фраз и пояснений.\n\n"
        f"Полный список анализов:\n{'; '.join(all_test_names)}\n\n"
        "Запрос пользователя:\n"
        f"{text}"
    )
    response = client.chat.completions.create(
        model="gpt-4o",  # gpt-4o дешевле, но можно gpt-4.1
        messages=[
            {"role": "system", "content": prompt}
        ]
    )
    keywords = response.choices[0].message.content.strip()
    print("🧠 GPT вернул ключевые слова:", keywords)
    return [clean_name(kw) for kw in keywords.split(",") if kw.strip()]

# Улучшенный Excat match и подстрочное сравнение (учитываем только точные совпадения с учетом морфологии)
def contains_exact_word(text, word):
    pattern = r'(^|\W)' + re.escape(word) + r'($|\W)'
    return re.search(pattern, text.lower())

def search_rows_by_keywords(keywords):
    matches = []
    for row in rows:
        name = clean_name(row.get("Наименование", ""))
        if any(kw in name for kw in keywords):
            matches.append(row)
    # Убираем дубли по наименованию (на случай повторяющихся анализов)
    unique_matches = []
    seen = set()
    for m in matches:
        na = clean_name(m.get("Наименование", ""))
        if na not in seen:
            unique_matches.append(m)
            seen.add(na)
    return unique_matches

# === 🌐 API ===
@app.route("/analyze", methods=["POST"])
def analyze():
    user_message = request.json.get("text", "")
    if not user_message.strip():
        return "❗ Запрос пустой.", 200, {'Content-Type': 'text/plain; charset=utf-8'}

    keywords = extract_keywords_from_text(user_message)
    print("🔑 Ключи GPT:", keywords)

    results = search_rows_by_keywords(keywords)

    if results:
        response_lines = [
            f"{i+1}️⃣ {row['Наименование']}\n"
            f"💰 Цена — {row['Цена']} руб.\n"
            f"⏱️ Срок — {row['Срок исп.']}\n"
            for i, row in enumerate(results[:10])
        ]
        text_response = "\n".join(response_lines)
        return text_response, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    else:
        return "❌ Ничего не найдено по вашему запросу.", 200, {'Content-Type': 'text/plain; charset=utf-8'}

# === ▶ Запуск ===
if __name__ == "__main__":
    app.run(debug=True, port=5000)
