import gspread
import re
from google.oauth2.service_account import Credentials

# Ключевое слово
keyword = "Тестостерон"

# Авторизация
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
client = gspread.authorize(creds)

# Открытие таблицы
spreadsheet_id = "1Ao-FgsBLHau3SDH3HfjTOlmO1q16F8EBKsU46znOHgE"
sheet = client.open_by_key(spreadsheet_id).sheet1

# Заголовки
header_row = sheet.row_values(2)
print("Фактические заголовки:", header_row)

rows = sheet.get_all_records(head=2, expected_headers=header_row)

# 🔎 Универсальный фильтр: точное слово в разных формах
def contains_exact_word(text, word):
    text = str(text).lower()
    word = word.lower()
    # ищем слово как отдельное, с падежами: кал, кала, кали, кале, калу и т.д.
    pattern = r'\b' + re.escape(word) + r'(а|у|е|ом|ы|ов|ам|ах)?\b'
    return re.search(pattern, text) is not None

# Поиск только по "Наименование"
matches = []
for row in rows:
    name = str(row.get("Наименование", "")).lower()
    if contains_exact_word(name, keyword):
        matches.append(row)

# Вывод результата
if matches:
    print("🔍 Найдено:")
    for row in matches:
        print(f"{row['Наименование']} — {row['Цена']} руб. ({row['Срок исп.']})")
else:
    print("❌ Ничего не найдено по слову 'кал'.")
