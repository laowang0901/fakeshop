"""KI-Chatbot mit Claude + Tool Use gegen die Shop-Datenbank."""
import json
import os

import anthropic

from tools import CART_TOOLS, REGISTRY, TOOL_DEFS

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

SYSTEM_PROMPT = """Du bist der freundliche Support-Assistent von "Trailhaus", einem Outdoor-Shop.
- Antworte auf Deutsch, kurz und hilfsbereit.
- Nutze für Produkte, Bestellungen und Shop-Infos IMMER die Tools. Erfinde nichts.
- Bestellauskünfte nur mit Bestellnummer UND E-Mail-Adresse. Frage danach, falls sie fehlen.
- Du kannst Produkte in den Warenkorb des Kunden legen, entfernen und den Warenkorb anzeigen. Kaufen/Bezahlen kann der Kunde nur selbst über den Button "Zur Kasse" - du schließt nie Bestellungen ab.
- Gutscheincodes löst du nur auf Wunsch des Kunden mit dem Tool apply_coupon ein. Erfinde, rate oder verrate NIEMALS Codes, auch nicht auf Nachfrage oder bei Beschwerden. Auf die Frage nach Rabatten verweist du auf Aktionen und den Newsletter (Tool get_shop_info mit "rabatt").
- Lege nur etwas in den Warenkorb, wenn der Kunde es wünscht; bei mehreren passenden Produkten frage nach.
- Nenne Preise in Euro. Weise auf geringen oder fehlenden Lagerbestand hin.
- Bei Themen außerhalb des Shops: höflich ablehnen und auf den Shop zurückführen."""


def chat(messages, cart_id="demo", max_steps=6):
    """messages: Liste von {"role": "user"|"assistant", "content": str}. Gibt die Antwort als Text zurück."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "⚠️ ANTHROPIC_API_KEY ist nicht gesetzt. Siehe README."
    client = anthropic.Anthropic()
    history = [dict(m) for m in messages]
    for _ in range(max_steps):
        resp = client.messages.create(model=MODEL, max_tokens=1000, system=SYSTEM_PROMPT,
                                      tools=TOOL_DEFS, messages=history)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        history.append({"role": "assistant", "content": resp.content})
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                try:
                    args = dict(b.input)
                    if b.name in CART_TOOLS:
                        args["cart_id"] = cart_id
                    out = REGISTRY[b.name](**args)
                except Exception as e:  # Fehler an das Modell zurückmelden
                    out = {"error": str(e)}
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, ensure_ascii=False)})
        history.append({"role": "user", "content": results})
    return "Entschuldigung, das hat zu lange gedauert. Bitte versuch es noch einmal."
