"""SQLite-Datenbank mit Fake-Daten für den Demo-Shop."""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "shop.db"

SCHEMA = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY, name TEXT, category TEXT,
    price REAL, stock INTEGER, description TEXT
);
CREATE TABLE customers (
    id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, city TEXT
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT,
    status TEXT, tracking_number TEXT, total REAL
);
CREATE TABLE order_items (
    order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price REAL
);
CREATE TABLE shop_info (topic TEXT PRIMARY KEY, text TEXT);
"""

CART_SCHEMA = """
CREATE TABLE IF NOT EXISTS cart_items (
    cart_id TEXT, product_id INTEGER, quantity INTEGER,
    PRIMARY KEY (cart_id, product_id)
);
CREATE TABLE IF NOT EXISTS coupons (
    code TEXT PRIMARY KEY, type TEXT, value REAL, min_order REAL DEFAULT 0,
    valid_until TEXT, max_uses INTEGER, used_count INTEGER DEFAULT 0, description TEXT
);
CREATE TABLE IF NOT EXISTS cart_coupon (cart_id TEXT PRIMARY KEY, code TEXT);
"""

def _coupons():
    today = date.today()
    return [  # code, type, value, min_order, valid_until, max_uses, used_count, description
        ("WILLKOMMEN10", "percent", 10, 0, None, None, 0, "10 % auf alles"),
        ("SOMMER20", "percent", 20, 100, (today + timedelta(days=90)).isoformat(), None, 0, "20 % ab 100 € Warenwert"),
        ("SPAR15", "fixed", 15, 80, None, None, 0, "15 € Rabatt ab 80 € Warenwert"),
        ("GRATISVERSAND", "free_shipping", 0, 0, None, None, 0, "Kostenloser Versand"),
        ("ABGELAUFEN5", "percent", 5, 0, (today - timedelta(days=30)).isoformat(), None, 0, "Testfall: abgelaufen"),
        ("AUSGESCHOEPFT", "percent", 50, 0, None, 1, 1, "Testfall: bereits aufgebraucht"),
    ]

PRODUCTS = [
    ("Trailrunner Laufschuhe", "Schuhe", 89.90, 24, "Leichte Trailrunning-Schuhe mit griffiger Sohle."),
    ("City Sneaker Weiß", "Schuhe", 69.00, 40, "Klassischer Sneaker aus Leder für den Alltag."),
    ("Winterstiefel Alpin", "Schuhe", 129.00, 8, "Wasserdichte, gefütterte Stiefel bis -25 °C."),
    ("Merino Wanderjacke", "Jacken", 159.00, 12, "Atmungsaktive Jacke aus Merinowolle."),
    ("Regenjacke Storm", "Jacken", 99.50, 30, "Wasserdicht, winddicht, packbar."),
    ("Daunenweste Light", "Jacken", 79.90, 0, "Ultraleichte Weste, 90 % Daune."),
    ("Rucksack Tour 28L", "Rucksäcke", 74.90, 18, "Tagesrucksack mit Regenhülle und Rückenbelüftung."),
    ("Trekkingrucksack 55L", "Rucksäcke", 149.00, 6, "Großer Rucksack für Mehrtagestouren."),
    ("Isomatte Comfort", "Camping", 54.90, 15, "Selbstaufblasend, 5 cm dick."),
    ("Schlafsack Nordlicht", "Camping", 119.00, 9, "Komfortbereich bis -5 °C, 1,1 kg."),
    ("Campingkocher Mini", "Camping", 34.90, 50, "Kompakter Gaskocher, 2,5 kW."),
    ("Stirnlampe Beam 400", "Camping", 29.90, 35, "400 Lumen, wiederaufladbar, wasserdicht."),
    ("Trinkflasche Edelstahl 750ml", "Zubehör", 24.90, 80, "Hält 12 h heiß und 24 h kalt."),
    ("Wandersocken 3er-Pack", "Zubehör", 19.90, 100, "Merinomischung, blasenfrei."),
    ("Trekkingstöcke Carbon", "Zubehör", 89.00, 14, "Ultraleicht, 3-teilig, faltbar."),
    ("GPS-Uhr Summit", "Elektronik", 249.00, 5, "GPS, Höhenmesser, 14 Tage Akku."),
    ("Powerbank Outdoor 20000", "Elektronik", 44.90, 22, "Spritzwassergeschützt, USB-C."),
    ("Funktionsshirt Run", "Bekleidung", 34.90, 60, "Schnelltrocknend, geruchshemmend."),
    ("Softshellhose Alpin", "Bekleidung", 109.00, 11, "Elastisch, wind- und wasserabweisend."),
    ("Mütze Merino", "Bekleidung", 22.90, 45, "Weich, warm, kratzfrei."),
]

SHOP_INFO = {
    "versand": "Versand mit DHL in 2-4 Werktagen. Kostenlos ab 50 €, sonst 4,90 €. Versand in DE, AT, CH.",
    "rückgabe": "30 Tage Rückgaberecht ab Erhalt. Ware muss ungetragen und original verpackt sein. Rücksendung kostenlos innerhalb Deutschlands.",
    "zahlung": "Zahlung per Kreditkarte, PayPal, Rechnung (14 Tage) oder Vorkasse.",
    "kontakt": "Support: support@trailhaus-demo.de, Mo-Fr 9-17 Uhr, Tel. 0800 123 456.",
}

NAMES = ["Anna Becker", "Ben Schulz", "Clara Wolf", "David Keller", "Eva Neumann", "Felix Braun",
         "Greta Lang", "Hannes Roth", "Ida Vogel", "Jonas Berg"]
CITIES = ["Berlin", "Hamburg", "München", "Köln", "Stuttgart", "Freiburg", "Leipzig", "Dresden"]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _seed():
    DB_PATH.unlink(missing_ok=True)
    rnd = random.Random(42)
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO products (name,category,price,stock,description) VALUES (?,?,?,?,?)", PRODUCTS)
    conn.executemany("INSERT INTO shop_info VALUES (?,?)", SHOP_INFO.items())
    for i, n in enumerate(NAMES, 1):
        email = n.lower().replace(" ", ".").replace("ü", "ue") + "@example.com"
        conn.execute("INSERT INTO customers VALUES (?,?,?,?)", (i, n, email, rnd.choice(CITIES)))
    today = date.today()
    for oid in range(1001, 1031):
        cust = rnd.randint(1, len(NAMES))
        age = rnd.randint(0, 25)
        status = ("bestellt" if age < 2 else "versandt" if age < 6 else
                  rnd.choice(["zugestellt"] * 5 + ["storniert"]))
        tracking = f"DHL{rnd.randint(10**9, 10**10 - 1)}" if status in ("versandt", "zugestellt") else None
        total = 0
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,0)",
                     (oid, cust, (today - timedelta(days=age)).isoformat(), status, tracking))
        for pid in rnd.sample(range(1, len(PRODUCTS) + 1), rnd.randint(1, 3)):
            qty = rnd.randint(1, 2)
            price = PRODUCTS[pid - 1][2]
            total += qty * price
            conn.execute("INSERT INTO order_items VALUES (?,?,?,?)", (oid, pid, qty, price))
        conn.execute("UPDATE orders SET total=? WHERE id=?", (round(total, 2), oid))
    conn.commit()
    conn.close()


def init_db(force=False):
    if force or not DB_PATH.exists():
        _seed()
    conn = get_conn()
    conn.executescript(CART_SCHEMA)  # idempotent: ergänzt auch eine bereits vorhandene shop.db
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders)")}
    if "coupon_code" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN coupon_code TEXT")
    if "discount" not in cols:
        conn.execute("ALTER TABLE orders ADD COLUMN discount REAL DEFAULT 0")
    conn.executemany("INSERT OR IGNORE INTO coupons VALUES (?,?,?,?,?,?,?,?)", _coupons())
    conn.execute("INSERT OR IGNORE INTO shop_info VALUES ('rabatt', ?)",
                 ("Gutscheine gibt es bei Aktionen und im Newsletter. Pro Bestellung ist ein Code einlösbar, "
                  "Codes lassen sich im Warenkorb eingeben. Einzelne Codes haben einen Mindestbestellwert oder ein Ablaufdatum.",))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db(force=True)
    print(f"Datenbank erstellt: {DB_PATH}")
