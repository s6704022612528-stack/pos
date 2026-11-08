"""seed_data.py - fill the POS database with realistic convenience-store data.

What it creates (about 120 days of history ending yesterday):
  - 5 employees (1 manager, 4 cashiers), passwords stored as PBKDF2 hashes
  - 200 members (some "lapsed": they stop buying after the first 60 days)
  - 50 products in the 8 categories (3 "dead" products with no sales in the last 30 days)
  - ~5,500 bills with items, payments (cash/transfer), VAT 7%, some discounts,
    ~3% cancelled bills, restocking and a few stock adjustments (StockMovement)

Run from the project root (venv active), after 01_schema.sql has been executed:
    python scripts\\seed_data.py

Safe to re-run: it wipes the data tables (not Category) and refills them.
Dev-only login for every employee: password "1234" (change it in real use!).

Optional environment variables (or put them in .env):
    POS_SERVER   default "localhost"
    POS_DRIVER   default "ODBC Driver 17 for SQL Server"
    POS_DATABASE default "POS"
    POS_FAST     "1" turns ON pyodbc fast_executemany (faster; off by default)
"""
import hashlib
import os
import random
import secrets
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

DAYS = 120            # how many days of history
SEED = 42             # same seed -> same data every run
VAT_RATE = Decimal("0.07")
DEV_PASSWORD = "1234"

# (name, category, cost, sell, popularity weight, reorder level, dead?)
PRODUCTS = [
    ("น้ำดื่ม 600 มล.", "เครื่องดื่ม", 3.5, 7, 10, 40, False),
    ("น้ำดื่ม 1.5 ลิตร", "เครื่องดื่ม", 6, 12, 5, 30, False),
    ("โคล่า 325 มล.", "เครื่องดื่ม", 9, 15, 7, 30, False),
    ("น้ำอัดลมรสส้ม 325 มล.", "เครื่องดื่ม", 9, 15, 3, 20, False),
    ("ชาเขียวพร้อมดื่ม 500 มล.", "เครื่องดื่ม", 11, 20, 6, 30, False),
    ("กาแฟกระป๋อง 180 มล.", "เครื่องดื่ม", 12, 20, 5, 25, False),
    ("เครื่องดื่มชูกำลัง 150 มล.", "เครื่องดื่ม", 7, 12, 5, 30, False),
    ("น้ำส้ม 250 มล.", "เครื่องดื่ม", 10, 18, 3, 20, False),
    ("เครื่องดื่มเกลือแร่ 500 มล.", "เครื่องดื่ม", 12, 20, 3, 20, False),
    ("โซดา 325 มล.", "เครื่องดื่ม", 5, 10, 2, 20, False),
    ("มันฝรั่งทอดกรอบ 48 กรัม", "ขนมและของกินเล่น", 14, 25, 6, 25, False),
    ("สาหร่ายทอดกรอบ", "ขนมและของกินเล่น", 9, 15, 4, 25, False),
    ("ช็อกโกแลตแท่ง", "ขนมและของกินเล่น", 11, 20, 4, 20, False),
    ("ลูกอมมินต์", "ขนมและของกินเล่น", 6, 10, 4, 20, False),
    ("หมากฝรั่ง", "ขนมและของกินเล่น", 8, 15, 4, 20, False),
    ("บิสกิตครีม", "ขนมและของกินเล่น", 8, 14, 3, 20, False),
    ("เยลลี่ผลไม้", "ขนมและของกินเล่น", 9, 15, 2, 15, False),
    ("ถั่วอบกรอบ", "ขนมและของกินเล่น", 12, 20, 2, 15, False),
    ("ไอศกรีมแท่ง", "ขนมและของกินเล่น", 12, 25, 5, 20, False),
    ("บะหมี่กึ่งสำเร็จรูป ถ้วย", "อาหารพร้อมทาน", 10, 18, 8, 40, False),
    ("บะหมี่กึ่งสำเร็จรูป ซอง", "อาหารพร้อมทาน", 5, 8, 5, 40, False),
    ("ข้าวกล่องไก่ทอด", "อาหารพร้อมทาน", 28, 45, 5, 15, False),
    ("แซนด์วิชทูน่า", "อาหารพร้อมทาน", 22, 35, 4, 15, False),
    ("ไส้กรอกอบ", "อาหารพร้อมทาน", 9, 15, 4, 20, False),
    ("ขนมปังแผ่น", "อาหารพร้อมทาน", 20, 32, 3, 15, False),
    ("ข้าวปั้นไส้หมูหยอง", "อาหารพร้อมทาน", 14, 25, 5, 15, False),
    ("ไข่ต้ม", "อาหารพร้อมทาน", 6, 10, 3, 20, False),
    ("นมจืดกล่อง 200 มล.", "นมและผลิตภัณฑ์นม", 8, 14, 6, 30, False),
    ("นมเปรี้ยวพร้อมดื่ม", "นมและผลิตภัณฑ์นม", 7, 12, 4, 25, False),
    ("โยเกิร์ตถ้วย", "นมและผลิตภัณฑ์นม", 12, 20, 3, 15, False),
    ("นมช็อกโกแลตกล่อง", "นมและผลิตภัณฑ์นม", 9, 15, 4, 25, False),
    ("ชีสแผ่น", "นมและผลิตภัณฑ์นม", 25, 40, 1, 10, False),
    ("แปรงสีฟัน", "ของใช้ส่วนตัว", 15, 29, 2, 10, False),
    ("ยาสีฟัน 50 กรัม", "ของใช้ส่วนตัว", 22, 39, 2, 10, False),
    ("สบู่ก้อน", "ของใช้ส่วนตัว", 12, 20, 2, 10, False),
    ("แชมพูซอง", "ของใช้ส่วนตัว", 3, 6, 2, 20, False),
    ("ผ้าอนามัย", "ของใช้ส่วนตัว", 14, 25, 2, 10, False),
    ("ทิชชู่เปียก", "ของใช้ส่วนตัว", 18, 30, 2, 10, False),
    ("หน้ากากอนามัย 3 ชิ้น", "ของใช้ส่วนตัว", 6, 12, 1, 10, False),
    ("กระดาษทิชชู่ 4 ม้วน", "ของใช้ในบ้าน", 28, 45, 2, 10, False),
    ("ถุงขยะ", "ของใช้ในบ้าน", 20, 35, 1, 8, False),
    ("ผงซักฟอกซอง", "ของใช้ในบ้าน", 6, 10, 2, 15, False),
    ("ไฟแช็ก", "ของใช้ในบ้าน", 6, 12, 3, 15, False),
    ("ร่มพับ", "ของใช้ในบ้าน", 90, 159, 0.3, 3, True),
    ("ถ่านไฟฉาย AA 2 ก้อน", "ของใช้ในบ้าน", 22, 39, 0.3, 5, True),
    ("ปลั๊กไฟ 3 ช่อง", "ของใช้ในบ้าน", 85, 149, 0.3, 3, True),
    ("เบียร์ลาเกอร์ 620 มล.", "บุหรี่และเครื่องดื่มแอลกอฮอล์", 48, 65, 3, 24, False),
    ("เบียร์ลาเกอร์ 330 มล.", "บุหรี่และเครื่องดื่มแอลกอฮอล์", 30, 42, 2, 24, False),
    ("บัตรเติมเงิน 50 บาท", "บัตรเติมเงินและอื่นๆ", 48.5, 50, 2, 20, False),
    ("บัตรเติมเงิน 100 บาท", "บัตรเติมเงินและอื่นๆ", 97, 100, 2, 20, False),
]
ALCOHOL_CATEGORY = "บุหรี่และเครื่องดื่มแอลกอฮอล์"

# products often bought together (for the "bought together" business question)
PAIRS = [
    ("บะหมี่กึ่งสำเร็จรูป ถ้วย", "น้ำดื่ม 600 มล."),
    ("มันฝรั่งทอดกรอบ 48 กรัม", "โคล่า 325 มล."),
    ("กาแฟกระป๋อง 180 มล.", "ขนมปังแผ่น"),
    ("แซนด์วิชทูน่า", "นมจืดกล่อง 200 มล."),
    ("ข้าวกล่องไก่ทอด", "น้ำดื่ม 600 มล."),
    ("เบียร์ลาเกอร์ 620 มล.", "ถั่วอบกรอบ"),
]

HOUR_WEIGHTS = {6: 2, 7: 8, 8: 10, 9: 6, 10: 5, 11: 6, 12: 11, 13: 9, 14: 5, 15: 5,
                16: 6, 17: 9, 18: 11, 19: 10, 20: 8, 21: 6, 22: 4, 23: 2}

FIRST = ["สมชาย", "สมหญิง", "วิชัย", "สุดา", "ประยุทธ", "มาลี", "ธนากร", "พิมพ์ชนก", "อนุชา",
         "กนกวรรณ", "ณัฐพงศ์", "ศิริพร", "ชัยวัฒน์", "รัตนา", "ปิยะ", "จิราพร", "สุรชัย", "นภา",
         "เอกชัย", "วราภรณ์", "ทศพล", "อรทัย", "ธีรพงศ์", "ชนิดา", "พงศกร", "สุภาพร", "กิตติ",
         "ปาริชาต", "วีระ", "ลลิตา"]
LAST = ["ใจดี", "รักษา", "แสงทอง", "ศรีสุข", "พึ่งพา", "บุญมา", "สุขสวัสดิ์", "เจริญผล", "มั่นคง",
        "ทองดี", "วงศ์ใหญ่", "ชัยมงคล", "อินทร์แก้ว", "สายสุวรรณ", "ภูมิใจ", "พงษ์ไทย", "แก้วกาญจน์",
        "นามวงศ์", "ศรีวงษ์", "คำแสน"]
EMPLOYEES = [
    ("manager1", "ปรีชา มั่นคง", "manager"),
    ("cashier1", "สุนิสา ใจดี", "cashier"),
    ("cashier2", "อนุวัฒน์ แสงทอง", "cashier"),
    ("cashier3", "พิมพ์ลดา ศรีสุข", "cashier"),
    ("cashier4", "ธีรภัทร บุญมา", "cashier"),
]


def money(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def hash_password(password):
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2_sha256$100000${salt}${digest}"


def generate(today=None, seed=SEED):
    """Build all the data in memory. Rows refer to employees/customers/products by list index."""
    rnd = random.Random(seed)
    today = today or date.today()
    start = today - timedelta(days=DAYS)
    last_day = today - timedelta(days=1)
    dead_from = today - timedelta(days=30)       # dead products: no sales from this day on
    lapse_from = start + timedelta(days=60)       # lapsed customers: no purchases from this day on

    products = [dict(name=n, cat=c, cost=money(co), price=money(p), weight=w, reorder=r, dead=d)
                for n, c, co, p, w, r, d in PRODUCTS]
    name_to_idx = {p["name"]: i for i, p in enumerate(products)}
    pairs = [(name_to_idx[a], name_to_idx[b]) for a, b in PAIRS]
    partner = {}
    for a, b in pairs:
        partner.setdefault(a, []).append(b)

    employees = [dict(username=u, name=n, role=r) for u, n, r in EMPLOYEES]
    manager_idx = 0
    cashier_idx = [i for i, e in enumerate(employees) if e["role"] == "cashier"]

    phones = set()
    customers = []
    while len(customers) < 200:
        phone = "08" + "".join(rnd.choice("0123456789") for _ in range(8))
        if phone in phones:
            continue
        phones.add(phone)
        customers.append(dict(phone=phone, name=f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                              weight=rnd.expovariate(1.0) + 0.05, lapsed=len(customers) % 7 == 0,
                              created=datetime.combine(start, datetime.min.time())
                              - timedelta(days=rnd.randint(0, 300)), points=0))

    # product pools by (exclude_dead, exclude_alcohol), cached
    pools = {}

    def pool(ex_dead, ex_alc):
        key = (ex_dead, ex_alc)
        if key not in pools:
            idx = [i for i, p in enumerate(products)
                   if not (ex_dead and p["dead"]) and not (ex_alc and p["cat"] == ALCOHOL_CATEGORY)]
            pools[key] = (idx, [products[i]["weight"] for i in idx])
        return pools[key]

    stock = [0] * len(products)
    movements, sales = [], []
    pending = set()
    sale_id = 0

    def move(p, mtype, qty, sid, emp, note, when):
        movements.append(dict(product=p, type=mtype, qty=qty, sale=sid, emp=emp, note=note,
                              at=when.replace(microsecond=0)))

    for day_no in range(DAYS):
        d = start + timedelta(days=day_no)
        if d > last_day:
            break

        # morning: first stock-in, or restock products that fell to the reorder level
        if day_no == 0:
            for p, pr in enumerate(products):
                q = pr["reorder"] * 10 + rnd.randint(0, pr["reorder"] * 2)
                stock[p] += q
                move(p, "receive", q, None, manager_idx, "initial stock",
                     datetime.combine(d, datetime.min.time()) + timedelta(hours=6))
        else:
            for p in sorted(pending):
                pr = products[p]
                q = pr["reorder"] * 8 + rnd.randint(0, pr["reorder"] * 2)
                stock[p] += q
                move(p, "receive", q, None, manager_idx, "restock from supplier",
                     datetime.combine(d, datetime.min.time()) + timedelta(hours=6, minutes=30))
            pending.clear()

        # occasional damaged/expired goods
        if rnd.random() < 0.12:
            p = rnd.randrange(len(products))
            if stock[p] > 10:
                q = rnd.randint(1, 3)
                stock[p] -= q
                move(p, "adjust", -q, None, manager_idx, "damaged or expired",
                     datetime.combine(d, datetime.min.time()) + timedelta(hours=22, minutes=30))

        # bills of the day
        n_bills = rnd.randint(38, 56) + (8 if d.weekday() in (4, 5) else 0)
        hours = rnd.choices(list(HOUR_WEIGHTS), list(HOUR_WEIGHTS.values()), k=n_bills)
        times = sorted(datetime.combine(d, datetime.min.time())
                       + timedelta(hours=h, minutes=rnd.randint(0, 59), seconds=rnd.randint(0, 59))
                       for h in hours)

        active_c = [i for i, c in enumerate(customers) if not (c["lapsed"] and d >= lapse_from)]
        active_w = [customers[i]["weight"] for i in active_c]

        for when in times:
            ex_dead = d >= dead_from
            ex_alc = 14 <= when.hour < 17          # Thai law: no alcohol sales 14:00-17:00
            idx, w = pool(ex_dead, ex_alc)
            n_items = rnd.choices([1, 2, 3, 4, 5, 6], [35, 30, 18, 10, 5, 2])[0]
            basket = []
            while len(basket) < n_items:
                p = rnd.choices(idx, w)[0]
                if p not in basket:
                    basket.append(p)
            for p in list(basket):
                for q in partner.get(p, []):
                    if q in idx and q not in basket and rnd.random() < 0.3:
                        basket.append(q)

            items = []
            for p in basket:
                qty = rnd.choices([1, 2, 3], [70, 22, 8])[0]
                qty = min(qty, stock[p])
                if qty > 0:
                    items.append((p, qty))
            if not items:
                continue

            sale_id += 1
            is_member = rnd.random() < 0.38
            cust = rnd.choices(active_c, active_w)[0] if is_member else None
            emp = rnd.choice(cashier_idx) if rnd.random() < 0.92 else manager_idx
            cancelled = rnd.random() < 0.03

            subtotal = sum(products[p]["price"] * q for p, q in items)
            discount = Decimal("0.00")
            if cust is not None and subtotal >= 100 and rnd.random() < 0.4:
                discount = money(subtotal * Decimal("0.05"))
            elif subtotal >= 50 and rnd.random() < 0.03:
                discount = money(rnd.choice([5, 10, 20]))
            discount = min(discount, subtotal)      # a discount can never exceed the bill
            vat = money((subtotal - discount) * VAT_RATE)
            total = subtotal - discount + vat

            payment = None
            if not cancelled:
                if rnd.random() < 0.62:
                    # smallest bank-note amounts that cover the total (round UP)
                    options = sorted({money((total / step).to_integral_value(rounding=ROUND_CEILING) * step)
                                      for step in (1, 20, 50, 100, 500, 1000)} | {total})
                    amount = rnd.choice(options[:3])
                    payment = dict(method="cash", amount=amount, change=amount - total, ref=None)
                else:
                    payment = dict(method="transfer", amount=total, change=Decimal("0.00"),
                                   ref=f"TRX{sale_id:08d}")
                payment["at"] = when

            for p, q in items:
                stock[p] -= q
                move(p, "sale", -q, sale_id, emp, None, when)
                if stock[p] <= products[p]["reorder"] and not products[p]["dead"]:
                    pending.add(p)
            if cancelled:
                undo_at = when + timedelta(minutes=rnd.randint(3, 15))
                for p, q in items:
                    stock[p] += q
                    move(p, "cancel", q, sale_id, emp, "bill cancelled", undo_at)
            elif cust is not None:
                customers[cust]["points"] += int(total // 25)

            sales.append(dict(id=sale_id, at=when.replace(microsecond=0), emp=emp, cust=cust,
                              subtotal=subtotal, discount=discount, vat=vat, total=total,
                              status="cancelled" if cancelled else "completed",
                              items=items, payment=payment))

    for p, pr in enumerate(products):
        pr["stock"] = stock[p]
        pr["created"] = datetime.combine(start, datetime.min.time())
    return dict(employees=employees, customers=customers, products=products,
                sales=sales, movements=movements)


def check(data):
    """Sanity checks that the generated numbers agree with each other."""
    prod, sales, moves = data["products"], data["sales"], data["movements"]
    by_prod = [0] * len(prod)
    for m in moves:
        by_prod[m["product"]] += m["qty"]
    assert all(by_prod[i] == prod[i]["stock"] for i in range(len(prod))), "stock != sum(movements)"
    assert all(p["stock"] >= 0 for p in prod), "negative stock"
    for s in sales:
        line = sum(prod[p]["price"] * q for p, q in s["items"])
        assert line == s["subtotal"]
        assert s["discount"] <= s["subtotal"], "discount larger than bill"
        assert s["vat"] >= 0 and s["total"] >= 0, "negative VAT or total"
        assert s["total"] == s["subtotal"] - s["discount"] + s["vat"]
        if s["payment"]:
            pay = s["payment"]
            assert pay["amount"] - pay["change"] == s["total"]
            assert pay["change"] >= 0 and pay["amount"] >= s["total"], "underpaid / negative change"
    assert len({m["sale"] for m in moves if m["sale"]}) <= len(sales)


def connect():
    import pyodbc
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    conn_str = (f"DRIVER={{{os.getenv('POS_DRIVER', 'ODBC Driver 17 for SQL Server')}}};"
                f"SERVER={os.getenv('POS_SERVER', 'localhost')};"
                f"DATABASE={os.getenv('POS_DATABASE', 'POS')};Trusted_Connection=yes;")
    return pyodbc.connect(conn_str)


def load(conn, data):
    cur = conn.cursor()
    # fast_executemany is optional (POS_FAST=1): faster, but off by default for simplicity.
    cur.fast_executemany = os.getenv("POS_FAST", "0") == "1"

    print("clearing old data ...")
    for table in ("StockMovement", "Payment", "SaleItem", "Sale", "Product", "Customer", "Employee"):
        cur.execute(f"DELETE FROM {table}")

    print("employees, customers, products ...")
    pw = hash_password(DEV_PASSWORD)
    cur.executemany("INSERT INTO Employee (Username, PasswordHash, FullName, [Role]) VALUES (?,?,?,?)",
                    [(e["username"], pw, e["name"], e["role"]) for e in data["employees"]])
    emp_id = {u: i for i, u in cur.execute("SELECT EmployeeID, Username FROM Employee").fetchall()}
    emp_ids = [emp_id[e["username"]] for e in data["employees"]]

    cur.executemany("INSERT INTO Customer (Phone, FullName, Points, CreatedAt) VALUES (?,?,?,?)",
                    [(c["phone"], c["name"], c["points"], c["created"].replace(microsecond=0))
                     for c in data["customers"]])
    cust_id = {ph: i for i, ph in cur.execute("SELECT CustomerID, Phone FROM Customer").fetchall()}
    cust_ids = [cust_id[c["phone"]] for c in data["customers"]]

    cat_id = {n: i for i, n in cur.execute("SELECT CategoryID, CategoryName FROM Category").fetchall()}
    cur.executemany(
        "INSERT INTO Product (Barcode, ProductName, CategoryID, CostPrice, SellPrice, StockQty, "
        "ReorderLevel, IsActive, CreatedAt) VALUES (?,?,?,?,?,?,?,?,?)",
        [(f"885{i + 1:010d}", p["name"], cat_id[p["cat"]], p["cost"], p["price"], p["stock"],
          p["reorder"], 1, p["created"]) for i, p in enumerate(data["products"])])
    prod_id = {b: i for i, b in cur.execute("SELECT ProductID, Barcode FROM Product").fetchall()}
    prod_ids = [prod_id[f"885{i + 1:010d}"] for i in range(len(data["products"]))]

    sales = data["sales"]
    print(f"{len(sales)} bills ...")
    cur.execute("SET IDENTITY_INSERT Sale ON")
    cur.executemany(
        "INSERT INTO Sale (SaleID, SaleDate, EmployeeID, CustomerID, Subtotal, DiscountAmount, "
        "VatAmount, TotalAmount, [Status]) VALUES (?,?,?,?,?,?,?,?,?)",
        [(s["id"], s["at"], emp_ids[s["emp"]], cust_ids[s["cust"]] if s["cust"] is not None else None,
          s["subtotal"], s["discount"], s["vat"], s["total"], s["status"]) for s in sales])
    cur.execute("SET IDENTITY_INSERT Sale OFF")

    cur.executemany(
        "INSERT INTO SaleItem (SaleID, ProductID, Quantity, UnitPrice, UnitCost) VALUES (?,?,?,?,?)",
        [(s["id"], prod_ids[p], q, data["products"][p]["price"], data["products"][p]["cost"])
         for s in sales for p, q in s["items"]])
    cur.executemany(
        "INSERT INTO Payment (SaleID, Method, Amount, ChangeAmount, RefNo, PaidAt) VALUES (?,?,?,?,?,?)",
        [(s["id"], s["payment"]["method"], s["payment"]["amount"], s["payment"]["change"],
          s["payment"]["ref"], s["payment"]["at"].replace(microsecond=0))
         for s in sales if s["payment"]])
    cur.executemany(
        "INSERT INTO StockMovement (ProductID, MovementType, Quantity, SaleID, EmployeeID, Note, CreatedAt) "
        "VALUES (?,?,?,?,?,?,?)",
        [(prod_ids[m["product"]], m["type"], m["qty"], m["sale"], emp_ids[m["emp"]], m["note"], m["at"])
         for m in data["movements"]])
    conn.commit()


def main():
    data = generate()
    check(data)
    print(f"generated: {len(data['sales'])} bills, {len(data['movements'])} stock movements")
    conn = connect()
    try:
        load(conn, data)
    except Exception:
        conn.rollback()
        raise
    cur = conn.cursor()
    for table in ("Category", "Product", "Customer", "Employee", "Sale", "SaleItem", "Payment", "StockMovement"):
        print(f"{table:14s} {cur.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]:>7,} rows")
    conn.close()


if __name__ == "__main__":
    main()