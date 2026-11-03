"""Warenkorb-Logik: anzeigen, ändern, Gutscheine, Checkout."""
from datetime import date

from db import get_conn

FREE_SHIPPING_FROM = 50.0   # gilt für den Warenwert NACH Rabatt
SHIPPING_COST = 4.90
MAX_PER_ITEM = 10


def _eur(x):
    return f"{x:.2f}".replace(".", ",") + " €"


def _label(row):
    if row["type"] == "percent":
        return f"{row['value']:g} % Rabatt"
    if row["type"] == "fixed":
        return f"{_eur(row['value'])} Rabatt"
    return "Kostenloser Versand"


def _coupon_problem(row, subtotal):
    """Gibt eine Fehlermeldung zurück, wenn der Gutschein nicht einlösbar ist, sonst None."""
    if not row:
        return "Diesen Gutscheincode gibt es nicht."
    if row["valid_until"] and row["valid_until"] < date.today().isoformat():
        return "Dieser Gutschein ist abgelaufen."
    if row["max_uses"] is not None and row["used_count"] >= row["max_uses"]:
        return "Dieser Gutschein wurde bereits vollständig eingelöst."
    if subtotal < row["min_order"]:
        return f"Für diesen Gutschein gilt ein Mindestbestellwert von {_eur(row['min_order'])}."
    return None


def _discount(row, subtotal):
    if row["type"] == "percent":
        return round(subtotal * row["value"] / 100, 2)
    if row["type"] == "fixed":
        return round(min(row["value"], subtotal), 2)
    return 0.0


def get_cart(cart_id):
    with get_conn() as c:
        rows = c.execute(
            "SELECT p.id AS product_id, p.name, p.price, p.stock, ci.quantity FROM cart_items ci "
            "JOIN products p ON p.id = ci.product_id WHERE ci.cart_id = ? ORDER BY p.name", (cart_id,)).fetchall()
        crow = c.execute("SELECT cp.* FROM cart_coupon cc JOIN coupons cp ON cp.code = cc.code "
                         "WHERE cc.cart_id = ?", (cart_id,)).fetchone()
    items = []
    for r in rows:
        d = dict(r)
        d["line_total"] = round(d["price"] * d["quantity"], 2)
        items.append(d)
    subtotal = round(sum(i["line_total"] for i in items), 2)

    coupon, discount, free_ship = None, 0.0, False
    if crow:
        problem = _coupon_problem(crow, subtotal) if items else "Der Warenkorb ist leer."
        coupon = {"code": crow["code"], "label": _label(crow), "active": problem is None,
                  "message": problem, "discount": 0.0}
        if problem is None:
            discount = _discount(crow, subtotal)
            free_ship = crow["type"] == "free_shipping"
            coupon["discount"] = discount

    goods = round(subtotal - discount, 2)
    shipping = 0.0 if (not items or free_ship or goods >= FREE_SHIPPING_FROM) else SHIPPING_COST
    return {"items": items, "item_count": sum(i["quantity"] for i in items), "subtotal": subtotal,
            "coupon": coupon, "discount": discount, "shipping": shipping,
            "total": round(goods + shipping, 2), "free_shipping_from": FREE_SHIPPING_FROM}


def _set_quantity(cart_id, product_id, quantity):
    """Setzt die Menge (begrenzt durch Lagerbestand und Maximum). Gibt (Ergebnis, Fehler) zurück."""
    with get_conn() as c:
        p = c.execute("SELECT name, stock FROM products WHERE id=?", (product_id,)).fetchone()
        if not p:
            return None, "Produkt nicht gefunden."
        if quantity <= 0:
            c.execute("DELETE FROM cart_items WHERE cart_id=? AND product_id=?", (cart_id, product_id))
            return {"product": p["name"], "quantity_in_cart": 0, "capped": False}, None
        if p["stock"] <= 0:
            return None, f"{p['name']} ist leider ausverkauft."
        final = min(quantity, p["stock"], MAX_PER_ITEM)
        c.execute("INSERT INTO cart_items VALUES (?,?,?) ON CONFLICT(cart_id, product_id) "
                  "DO UPDATE SET quantity=excluded.quantity", (cart_id, product_id, final))
        return {"product": p["name"], "quantity_in_cart": final, "capped": final < quantity}, None


def _result(cart_id, res, err):
    if err:
        return {"error": err}
    return {"ok": True, **res, "cart": get_cart(cart_id)}


def add_to_cart(cart_id, product_id, quantity=1):
    quantity = int(quantity)
    if quantity < 1:
        return {"error": "Die Menge muss mindestens 1 sein."}
    with get_conn() as c:
        row = c.execute("SELECT quantity FROM cart_items WHERE cart_id=? AND product_id=?",
                        (cart_id, product_id)).fetchone()
    return _result(cart_id, *_set_quantity(cart_id, int(product_id), (row["quantity"] if row else 0) + quantity))


def update_quantity(cart_id, product_id, quantity):
    return _result(cart_id, *_set_quantity(cart_id, int(product_id), int(quantity)))


def remove_from_cart(cart_id, product_id):
    return _result(cart_id, *_set_quantity(cart_id, int(product_id), 0))


# ---------- Gutscheine ----------
def apply_coupon(cart_id, code):
    code = (code or "").strip().upper()
    if not code:
        return {"error": "Bitte einen Gutscheincode eingeben."}
    cart = get_cart(cart_id)
    if not cart["items"]:
        return {"error": "Lege zuerst Produkte in den Warenkorb, dann kannst du einen Gutschein einlösen."}
    with get_conn() as c:
        row = c.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone()
    problem = _coupon_problem(row, cart["subtotal"])
    if problem:
        return {"error": problem}
    with get_conn() as c:  # ein Gutschein pro Warenkorb, ein neuer ersetzt den alten
        c.execute("INSERT OR REPLACE INTO cart_coupon VALUES (?,?)", (cart_id, code))
    return {"ok": True, "code": code, "label": _label(row), "cart": get_cart(cart_id)}


def remove_coupon(cart_id):
    with get_conn() as c:
        c.execute("DELETE FROM cart_coupon WHERE cart_id=?", (cart_id,))
    return {"ok": True, "cart": get_cart(cart_id)}


# ---------- Checkout ----------
def checkout(cart_id, name, email):
    """Legt aus dem Warenkorb eine Bestellung an, reduziert Lagerbestand, verbucht den Gutschein, leert den Korb."""
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name or "@" not in email:
        return {"error": "Bitte Name und gültige E-Mail-Adresse angeben."}
    cart = get_cart(cart_id)
    if not cart["items"]:
        return {"error": "Der Warenkorb ist leer."}
    if cart["coupon"] and not cart["coupon"]["active"]:  # nie stillschweigend ohne den gezeigten Rabatt bestellen
        return {"error": f"Gutschein {cart['coupon']['code']}: {cart['coupon']['message']} Bitte entferne den Gutschein oder passe den Warenkorb an."}
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        for i in cart["items"]:
            stock = conn.execute("SELECT stock FROM products WHERE id=?", (i["product_id"],)).fetchone()["stock"]
            if stock < i["quantity"]:
                conn.rollback()
                return {"error": f"{i['name']}: nur noch {stock} auf Lager. Bitte Menge anpassen."}
        code = None
        if cart["coupon"] and cart["coupon"]["active"]:
            code = cart["coupon"]["code"]
            row = conn.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone()
            problem = _coupon_problem(row, cart["subtotal"])  # zweite Prüfung innerhalb der Transaktion
            if problem:
                conn.rollback()
                return {"error": f"Gutschein {code}: {problem}"}
            conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code=?", (code,))
        cust = conn.execute("SELECT id FROM customers WHERE lower(email)=?", (email,)).fetchone()
        cid = cust["id"] if cust else conn.execute(
            "INSERT INTO customers (name, email, city) VALUES (?,?,?)", (name, email, "")).lastrowid
        oid = conn.execute("SELECT COALESCE(MAX(id), 1000) + 1 FROM orders").fetchone()[0]
        conn.execute("INSERT INTO orders (id, customer_id, order_date, status, tracking_number, total, coupon_code, discount) "
                     "VALUES (?,?,date('now'),'bestellt',NULL,?,?,?)", (oid, cid, cart["total"], code, cart["discount"]))
        for i in cart["items"]:
            conn.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid, i["product_id"], i["quantity"], i["price"]))
            conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (i["quantity"], i["product_id"]))
        conn.execute("DELETE FROM cart_items WHERE cart_id=?", (cart_id,))
        conn.execute("DELETE FROM cart_coupon WHERE cart_id=?", (cart_id,))
        conn.commit()
        return {"ok": True, "order_id": oid, "total": cart["total"], "discount": cart["discount"],
                "coupon_code": code, "email": email}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
