import requests
import csv
import json

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zZQZcpqE5wGdx3kET5X3TjNKJcshQDG0xSG0GzyIZ7s/export?format=csv"

r = requests.get(SHEET_URL)
r.raise_for_status()

r.encoding = "utf-8"

lines = r.text.splitlines()
reader = csv.reader(lines)

questions = []

for i, row in enumerate(reader):
    if i == 0:
        continue
    if len(row) < 2:
        continue
    q = row[1].strip()
    if q:
        questions.append(q)

questions = list(set(questions))

data = {"questions": questions}

with open("questions.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("questions updated:", len(questions))
