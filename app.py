"""Flask-Server: Shop-Frontend, REST-API und Chat-Endpunkt."""
import uuid

from flask import Flask, g, jsonify, render_template, request

import cart
import chatbot
from db import get_conn, init_db
from tools import get_order_status, search_products

app = Flask(__name__)
init_db()


@app.before_request
def ensure_cart_id():
    """Jeder Browser bekommt per Cookie einen eigenen Warenkorb."""
    g.cart_id = request.cookies.get("cart_id") or uuid.uuid4().hex
    g.new_cart = "cart_id" not in request.cookies


@app.after_request
def set_cart_cookie(resp):
    if g.get("new_cart"):
        resp.set_cookie("cart_id", g.cart_id, max_age=60 * 60 * 24 * 30, samesite="Lax")
    return resp


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/products")
def products():
    return jsonify(search_products(request.args.get("q"), request.args.get("category"), limit=100))


@app.get("/api/orders/<int:order_id>")
def order(order_id):
    return jsonify(get_order_status(order_id, request.args.get("email", "")))


@app.get("/api/customers")  # Hilfe zum Testen: gültige Fake-Logins
def customers():
    with get_conn() as c:
        rows = c.execute("SELECT cu.name, cu.email, group_concat(o.id) AS orders FROM customers cu "
                         "LEFT JOIN orders o ON o.customer_id=cu.id GROUP BY cu.id")
        return jsonify([dict(r) for r in rows])


@app.get("/api/cart")
def get_cart():
    return jsonify(cart.get_cart(g.cart_id))


@app.post("/api/cart/items")
def cart_add():
    d = request.get_json(silent=True) or {}
    return jsonify(cart.add_to_cart(g.cart_id, d.get("product_id"), d.get("quantity", 1)))


@app.patch("/api/cart/items/<int:product_id>")
def cart_update(product_id):
    d = request.get_json(silent=True) or {}
    return jsonify(cart.update_quantity(g.cart_id, product_id, d.get("quantity", 1)))


@app.delete("/api/cart/items/<int:product_id>")
def cart_remove(product_id):
    return jsonify(cart.remove_from_cart(g.cart_id, product_id))


@app.post("/api/cart/coupon")
def coupon_apply():
    res = cart.apply_coupon(g.cart_id, (request.get_json(silent=True) or {}).get("code"))
    return jsonify(res), (400 if "error" in res else 200)


@app.delete("/api/cart/coupon")
def coupon_remove():
    return jsonify(cart.remove_coupon(g.cart_id))


@app.post("/api/checkout")
def checkout():
    d = request.get_json(silent=True) or {}
    res = cart.checkout(g.cart_id, d.get("name"), d.get("email"))
    return jsonify(res), (400 if "error" in res else 200)


@app.post("/api/chat")
def chat():
    msgs = (request.get_json(silent=True) or {}).get("messages", [])
    msgs = [{"role": m["role"], "content": str(m["content"])[:2000]} for m in msgs[-20:]
            if m.get("role") in ("user", "assistant")]
    if not msgs:
        return jsonify({"error": "keine Nachricht"}), 400
    return jsonify({"reply": chatbot.chat(msgs, cart_id=g.cart_id)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
