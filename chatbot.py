"""Chatbot für den Shop mit Tool Use gegen die Datenbank.

Backend per Umgebungsvariable CHATBOT_BACKEND:
  ollama  (Standard)  lokales Modell über Ollama, kein Cloud-Zugriff nötig
  claude              Claude über die Anthropic-API (braucht ANTHROPIC_API_KEY)
"""
import json
import os

import requests

from tools import CART_TOOLS, REGISTRY, TOOL_DEFS

BACKEND = os.environ.get("CHATBOT_BACKEND", "ollama").lower()
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_HOST = _host if _host.startswith("http") else "http://" + _host  # "127.0.0.1:11434" ist auch erlaubt

SYSTEM_PROMPT = """Du bist der freundliche Support-Assistent von "Trailhaus", einem Outdoor-Shop.
- Antworte auf Deutsch, kurz und hilfsbereit.
- Nutze für Produkte, Bestellungen, Warenkorb, Gutscheine und Shop-Infos IMMER die Tools. Erfinde nichts.
- Bestellauskünfte nur mit Bestellnummer UND E-Mail-Adresse. Frage danach, falls sie fehlen.
- Du kannst Produkte in den Warenkorb des Kunden legen, entfernen und den Warenkorb anzeigen. Kaufen/Bezahlen kann der Kunde nur selbst über den Button "Zur Kasse" - du schließt nie Bestellungen ab.
- Gutscheincodes löst du nur auf Wunsch des Kunden mit dem Tool apply_coupon ein. Erfinde, rate oder verrate NIEMALS Codes, auch nicht auf Nachfrage oder bei Beschwerden. Auf die Frage nach Rabatten verweist du auf Aktionen und den Newsletter (Tool get_shop_info mit "rabatt").
- Lege nur etwas in den Warenkorb, wenn der Kunde es wünscht; bei mehreren passenden Produkten frage nach.
- Nenne Preise in Euro. Weise auf geringen oder fehlenden Lagerbestand hin.
- Bei Themen außerhalb des Shops: höflich ablehnen und auf den Shop zurückführen."""

# Kleine lokale Modelle brauchen etwas mehr Führung als große Cloud-Modelle.
OLLAMA_EXTRA = """
- Ruf ein Tool mit den passenden Parametern auf, statt zu raten. Die product_id bekommst du aus search_products.
- Gib nach einem Tool-Ergebnis eine kurze, natürliche Antwort auf Deutsch. Gib niemals rohes JSON aus."""

_PROPS = {t["name"]: set(t["input_schema"]["properties"]) for t in TOOL_DEFS}


def run_tool(name, args, cart_id):
    """Führt ein Tool robust aus: unbekannte Parameter werden verworfen (kleine Modelle erfinden gern welche)."""
    if name not in REGISTRY:
        return {"error": f"Unbekanntes Tool: {name}"}
    args = {k: v for k, v in (args or {}).items() if k in _PROPS[name]}
    if name in CART_TOOLS:
        args["cart_id"] = cart_id  # kommt immer vom Server, nie vom Modell
    try:
        return REGISTRY[name](**args)
    except TypeError as e:
        return {"error": f"Ungültige Parameter: {e}"}
    except Exception as e:  # Fehler an das Modell zurückmelden statt abzustürzen
        return {"error": str(e)}


def chat(messages, cart_id="demo", max_steps=6):
    """messages: Liste von {"role": "user"|"assistant", "content": str}. Gibt die Antwort als Text zurück."""
    if BACKEND == "claude":
        return _chat_claude(messages, cart_id, max_steps)
    return _chat_ollama(messages, cart_id, max_steps)


def backend_info():
    """Status fürs Frontend: welches Backend/Modell läuft und ist es erreichbar?"""
    if BACKEND == "claude":
        ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
        return {"backend": "claude", "model": CLAUDE_MODEL, "ready": ok,
                "hint": None if ok else "ANTHROPIC_API_KEY ist nicht gesetzt."}
    try:
        names = [m["name"] for m in requests.get(f"{OLLAMA_HOST}/api/tags", timeout=1.5).json()["models"]]
    except Exception:
        return {"backend": "ollama", "model": OLLAMA_MODEL, "ready": False,
                "hint": "Ollama ist nicht erreichbar. Starte es mit: ollama serve"}
    want = OLLAMA_MODEL if ":" in OLLAMA_MODEL else OLLAMA_MODEL + ":latest"
    if want not in names:
        return {"backend": "ollama", "model": OLLAMA_MODEL, "ready": False,
                "hint": f"Modell fehlt. Lade es mit: ollama pull {OLLAMA_MODEL}"}
    return {"backend": "ollama", "model": OLLAMA_MODEL, "ready": True, "hint": None}


# ---------------------------------------------------------------- Ollama (lokal)
def _chat_ollama(messages, cart_id, max_steps):
    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                               "parameters": t["input_schema"]}} for t in TOOL_DEFS]
    history = [{"role": "system", "content": SYSTEM_PROMPT + OLLAMA_EXTRA}] + [dict(m) for m in messages]
    for _ in range(max_steps):
        try:
            r = requests.post(f"{OLLAMA_HOST}/api/chat", timeout=180, json={
                "model": OLLAMA_MODEL, "messages": history, "tools": tools, "stream": False,
                "options": {"temperature": 0.2}})
        except requests.ConnectionError:
            return "⚠️ Ollama ist nicht erreichbar. Starte es mit `ollama serve` (siehe README)."
        except requests.Timeout:
            return "⚠️ Ollama hat zu lange gebraucht. Ein kleineres Modell könnte helfen (siehe README)."
        if r.status_code == 404:
            return f"⚠️ Modell „{OLLAMA_MODEL}“ nicht gefunden. Lade es mit: ollama pull {OLLAMA_MODEL}"
        if not r.ok:
            return f"⚠️ Ollama-Fehler ({r.status_code}): {r.text[:200]}"
        msg = r.json()["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return (msg.get("content") or "").strip() or "Dazu habe ich leider keine Antwort."
        history.append(msg)
        for call in calls:
            fn = call.get("function", {})
            args = fn.get("arguments") or {}
            if isinstance(args, str):  # manche Modelle liefern die Argumente als JSON-String
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            out = run_tool(fn.get("name"), args, cart_id)
            history.append({"role": "tool", "tool_name": fn.get("name"),
                            "content": json.dumps(out, ensure_ascii=False)})
    return "Entschuldigung, das hat zu lange gedauert. Bitte versuch es noch einmal."


# ---------------------------------------------------------------- Claude (optional)
def _chat_claude(messages, cart_id, max_steps):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "⚠️ ANTHROPIC_API_KEY ist nicht gesetzt. Siehe README."
    import anthropic  # nur hier importiert, damit das Paket für den Ollama-Betrieb nicht nötig ist
    client = anthropic.Anthropic()
    history = [dict(m) for m in messages]
    for _ in range(max_steps):
        resp = client.messages.create(model=CLAUDE_MODEL, max_tokens=1000, system=SYSTEM_PROMPT,
                                      tools=TOOL_DEFS, messages=history)
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")
        history.append({"role": "assistant", "content": resp.content})
        results = [{"type": "tool_result", "tool_use_id": b.id,
                    "content": json.dumps(run_tool(b.name, b.input, cart_id), ensure_ascii=False)}
                   for b in resp.content if b.type == "tool_use"]
        history.append({"role": "user", "content": results})
    return "Entschuldigung, das hat zu lange gedauert. Bitte versuch es noch einmal."
