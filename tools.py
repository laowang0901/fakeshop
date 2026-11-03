"""Datenbank-Abfragen, die der Chatbot als Tools nutzen darf."""
import cart
from db import get_conn

TOOL_DEFS = [
    {
        "name": "search_products",
        "description": "Sucht Produkte im Shop. Alle Filter sind optional. Liefert Name, Preis, Lagerbestand.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff in Name/Beschreibung"},
            "category": {"type": "string", "description": "Schuhe, Jacken, Rucksäcke, Camping, Zubehör, Elektronik, Bekleidung"},
            "max_price": {"type": "number"},
        }},
    },
    {
        "name": "get_order_status",
        "description": "Zeigt Status, Positionen und Tracking-Nummer einer Bestellung. Erfordert Bestellnummer UND E-Mail-Adresse des Kunden zur Verifizierung.",
        "input_schema": {"type": "object", "properties": {
            "order_id": {"type": "integer"}, "email": {"type": "string"}},
            "required": ["order_id", "email"]},
    },
    {
        "name": "get_shop_info",
        "description": "Allgemeine Shop-Infos: versand, rückgabe, zahlung, kontakt oder rabatt (Infos zu Gutscheinen).",
        "input_schema": {"type": "object", "properties": {
            "topic": {"type": "string", "enum": ["versand", "rückgabe", "zahlung", "kontakt", "rabatt"]}},
            "required": ["topic"]},
    },
    {
        "name": "view_cart",
        "description": "Zeigt den aktuellen Warenkorb des Kunden mit Positionen, Versandkosten und Gesamtsumme.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_to_cart",
        "description": "Legt ein Produkt (per product_id aus search_products) in den Warenkorb des Kunden.",
        "input_schema": {"type": "object", "properties": {
            "product_id": {"type": "integer"}, "quantity": {"type": "integer", "default": 1}},
            "required": ["product_id"]},
    },
    {
        "name": "remove_from_cart",
        "description": "Entfernt ein Produkt komplett aus dem Warenkorb des Kunden.",
        "input_schema": {"type": "object", "properties": {"product_id": {"type": "integer"}},
                         "required": ["product_id"]},
    },
    {
        "name": "apply_coupon",
        "description": "Löst einen Gutscheincode, den der Kunde nennt, im Warenkorb ein. Prüft Gültigkeit selbst und liefert eine Fehlermeldung, falls der Code nicht einlösbar ist.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
    },
    {
        "name": "remove_coupon",
        "description": "Entfernt den eingelösten Gutschein aus dem Warenkorb.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def search_products(query=None, category=None, max_price=None, limit=10):
    sql, args = "SELECT id,name,category,price,stock,description FROM products WHERE 1=1", []
    if query:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        args += [f"%{query}%"] * 2
    if category:
        sql += " AND category LIKE ?"
        args.append(f"%{category}%")
    if max_price is not None:
        sql += " AND price <= ?"
        args.append(max_price)
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql + " LIMIT ?", args + [limit])]


def get_order_status(order_id, email):
    with get_conn() as c:
        row = c.execute(
            "SELECT o.*, cu.name FROM orders o JOIN customers cu ON cu.id=o.customer_id "
            "WHERE o.id=? AND lower(cu.email)=lower(?)", (order_id, email)).fetchone()
        if not row:
            return {"error": "Keine Bestellung zu dieser Kombination aus Bestellnummer und E-Mail gefunden."}
        items = [dict(r) for r in c.execute(
            "SELECT p.name, i.quantity, i.unit_price FROM order_items i "
            "JOIN products p ON p.id=i.product_id WHERE i.order_id=?", (order_id,))]
        return {"order_id": row["id"], "customer": row["name"], "date": row["order_date"],
                "status": row["status"], "tracking_number": row["tracking_number"],
                "total": row["total"], "coupon_code": row["coupon_code"], "discount": row["discount"], "items": items}


def get_shop_info(topic):
    with get_conn() as c:
        row = c.execute("SELECT text FROM shop_info WHERE topic=?", (topic,)).fetchone()
        return {"text": row["text"]} if row else {"error": "Unbekanntes Thema"}


REGISTRY = {
    "search_products": search_products, "get_order_status": get_order_status, "get_shop_info": get_shop_info,
    "view_cart": cart.get_cart, "add_to_cart": cart.add_to_cart, "remove_from_cart": cart.remove_from_cart,
    "apply_coupon": cart.apply_coupon, "remove_coupon": cart.remove_coupon,
}
CART_TOOLS = {"view_cart", "add_to_cart", "remove_from_cart", "apply_coupon", "remove_coupon"}  # bekommen die cart_id vom Server, nicht vom Modell
