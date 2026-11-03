# Trailhaus – Fake-Shop mit KI-Chatbot

Demo-Onlineshop (Outdoor-Ausrüstung) mit SQLite-Datenbank und einem Chatbot auf Basis von Claude (Tool Use).
Der Bot beantwortet Fragen zu Produkten, Bestellungen, Versand und Rückgabe – ausschließlich auf Basis der Datenbank.

## Start

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."                 # Windows (PowerShell): $env:ANTHROPIC_API_KEY="sk-ant-..."
python app.py
```

Dann `http://localhost:5000` öffnen und unten rechts auf 💬 klicken.

## Error when Starting
When getting script execution error from powershell:
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
then start
 .\.venv\Scripts\Activate.ps1    


## Dateien

| Datei | Zweck |
|---|---|
| `db.py` | Schema + Fake-Daten (20 Produkte, 10 Kunden, 30 Bestellungen). `python db.py` setzt die DB zurück |
| `cart.py` | Warenkorb (pro Browser per Cookie) und Checkout: legt Bestellung an, reduziert Lagerbestand |
| `tools.py` | Datenbank-Funktionen + Tool-Definitionen für Claude |
| `chatbot.py` | Chat-Logik inkl. System-Prompt und Tool-Use-Schleife |
| `app.py` | Flask-Server (Shop, REST-API, `/api/chat`) |
| `test_chatbot.py` | Automatische Testfragen (`python test_chatbot.py`) |
| `templates/index.html` | Shop-Oberfläche mit Chat-Widget |

## Warenkorb

- Im Shop: „In den Warenkorb“, Menge ändern, entfernen, Versandkosten (frei ab 50 €), „Zur Kasse“ mit Name + E-Mail.
- Der Checkout legt eine echte Bestellung in der DB an (Status „bestellt“) und reduziert den Lagerbestand. Die Bestellung ist danach per Chatbot abfragbar (Bestellnummer + E-Mail).
- Der Chatbot kann den Warenkorb anzeigen sowie Produkte hinzufügen/entfernen, aber nicht selbst bestellen.
- REST-API: `GET /api/cart`, `POST /api/cart/items`, `PATCH|DELETE /api/cart/items/<id>`, `POST /api/checkout`.

## Gutscheincodes

Pro Warenkorb ist ein Code einlösbar (Eingabe im Warenkorb oder per Chatbot). Geprüft wird serverseitig: Existenz, Ablaufdatum, Einlösungslimit, Mindestbestellwert. Beim Checkout wird der Code erneut geprüft und als verbraucht gezählt; die Bestellung speichert Code und Rabatt.

| Code | Wirkung | Bedingung |
|---|---|---|
| `WILLKOMMEN10` | 10 % Rabatt | – |
| `SOMMER20` | 20 % Rabatt | ab 100 € Warenwert |
| `SPAR15` | 15 € Rabatt | ab 80 € Warenwert |
| `GRATISVERSAND` | Versand kostenlos | – |
| `ABGELAUFEN5` | – | Testfall: abgelaufen |
| `AUSGESCHOEPFT` | – | Testfall: bereits eingelöst (Limit 1) |

Der Bot darf Codes nur einlösen, wenn der Kunde sie nennt. Er darf keine verraten (Testfall in `test_chatbot.py`). Neue Codes: Eintrag in `_coupons()` in `db.py` (bei bestehender DB wird er beim Start ergänzt).
REST: `POST /api/cart/coupon {"code": "..."}`, `DELETE /api/cart/coupon`.

## Testen

- Gültige Kunden-E-Mails und Bestellnummern: `http://localhost:5000/api/customers`
- Beispielfragen: „Habt ihr wasserdichte Jacken unter 100 €?“, „Wo ist Bestellung 1005? Meine Mail: …“, „Wie lange habe ich Rückgaberecht?“, „Leg mir zwei Paar Wandersocken in den Warenkorb“
- Automatisch: `python test_chatbot.py` – eigene Fälle in der Liste `CASES` ergänzen.
- Prüfenswert: Verweigert der Bot Auskünfte bei falscher E-Mail? Erfindet er Produkte? Reagiert er sinnvoll auf Off-Topic-Fragen oder Prompt-Injection-Versuche?

## Anpassen

- Modell ändern: `export CLAUDE_MODEL=claude-haiku-5-5` (günstiger) oder `claude-opus-5-5`.
- Verhalten des Bots: `SYSTEM_PROMPT` in `chatbot.py`.
- Neue Fähigkeiten: Funktion in `tools.py` schreiben, in `TOOL_DEFS` und `REGISTRY` eintragen.
