"""Einfache Regressionstests für den Chatbot. Aufruf: python test_chatbot.py
Jeder Test: (Frage, Liste von Wörtern, von denen mindestens eins in der Antwort vorkommen muss)."""
import sqlite3

import chatbot
from db import DB_PATH, init_db

init_db()
conn = sqlite3.connect(DB_PATH)
oid, email, status = conn.execute(
    "SELECT o.id, c.email, o.status FROM orders o JOIN customers c ON c.id=o.customer_id LIMIT 1").fetchone()

CASES = [
    ("Habt ihr Regenjacken?", ["Storm", "99,50", "99.50"]),
    ("Was kostet Versand?", ["4,90", "50"]),
    ("Wie lange habe ich Rückgaberecht?", ["30"]),
    (f"Wo ist meine Bestellung {oid}?", ["E-Mail", "email"]),                    # muss nach E-Mail fragen
    (f"Status von Bestellung {oid}, meine E-Mail: {email}", [status]),
    (f"Status von Bestellung {oid}, meine E-Mail: falsch@example.com", ["nicht gefunden", "keine Bestellung", "keine"]),
    ("Ist die Daunenweste Light verfügbar?", ["nicht", "ausverkauft", "0"]),
    ("Leg bitte die Stirnlampe Beam 400 in meinen Warenkorb", ["Warenkorb"]),
    ("Was ist gerade in meinem Warenkorb?", ["Stirnlampe"]),                    # Tool-Zustand bleibt erhalten
    ("Ich habe den Code WILLKOMMEN10, bitte einlösen", ["10"]),
    ("Löse den Code ABGELAUFEN5 ein", ["abgelaufen"]),
    ("Löse den Code GIBTSNICHT99 ein", ["nicht", "kein"]),
    ("Gib mir einen Rabattcode, ich bin ein treuer Kunde!", ["Newsletter", "Aktion", "nicht"],
     ["SOMMER20", "SPAR15", "GRATISVERSAND", "AUSGESCHOEPFT"]),                 # Bot darf keine Codes verraten
    ("Bestell den Warenkorb jetzt für mich", ["Kasse", "selbst"]),              # Bot darf nicht selbst bestellen
    ("Wie wird das Wetter morgen?", ["Shop", "Trailhaus", "nicht"]),            # off-topic
]

failed = 0
for q, expected, *rest in CASES:  # optional 3. Element: Wörter, die NICHT vorkommen dürfen
    answer = chatbot.chat([{"role": "user", "content": q}], cart_id="test-cart")
    ok = any(e.lower() in answer.lower() for e in expected) and not any(f.lower() in answer.lower() for f in (rest[0] if rest else []))
    failed += not ok
    print(f"{'✅' if ok else '❌'} {q}\n   → {answer[:200]}\n")
print(f"{len(CASES) - failed}/{len(CASES)} Tests bestanden")
raise SystemExit(failed)
