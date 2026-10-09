"""python seed.py: 고정된 한국어 더미 데이터를 customer.db에 일괄 삽입한다.

Python 3.10+, requirements.txt의 버전을 사용한다. random/Faker 시드는 42,
기준일은 2026-10-09로 고정한다. 주문일은 [2024-10-09, 2026-10-09)에
일별로 균등 분포하며 상태 비율 9:0.7:0.3은 90%/7%/3%로 적용한다.
동일 데이터가 있으면 건수를 확인하고 종료하며 다른 기존 데이터는 덮어쓰지 않는다.
이전 모델의 빈 DB는 새 스키마로 갱신한다. 모든 삽입은 한 트랜잭션이다.
"""

from collections import Counter
from datetime import date, timedelta
from importlib.metadata import version
import random
from time import perf_counter

from faker import Faker
from sqlalchemy import Connection, func, inspect, select, text

from database import DB_PATH, engine
from models import Base


SEED = 42
REFERENCE_DATE = date(2026, 10, 9)
START_DATE = REFERENCE_DATE.replace(year=REFERENCE_DATE.year - 2)
DAY_COUNT = (REFERENCE_DATE - START_DATE).days
BATCH_SIZE = 5_000
COUNTS = {"customers": 10_000, "products": 500, "employees": 300, "orders": 100_000}
CATEGORIES = ("전자제품", "생활용품", "의류", "식품", "스포츠")


def build_data() -> dict[str, list[dict]]:
    """로컬 RNG를 사용하므로 호출할 때마다 같은 데이터를 생성한다."""
    if version("Faker") != "40.41.0":
        raise RuntimeError("Reproducibility requires Faker==40.41.0; install requirements.txt")
    rng = random.Random(SEED)
    fake = Faker("ko_KR")
    fake.seed_instance(SEED)
    grades = ["VIP"] * 500 + ["일반"] * 7_000 + ["신규"] * 2_500
    rng.shuffle(grades)
    customers = []
    for customer_id, grade in enumerate(grades, 1):
        local, domain = fake.email().split("@", 1)
        customers.append({
            "customer_id": customer_id,
            "customer_name": fake.name(),
            # Faker 이메일에 고유 ID를 붙여 UNIQUE 충돌을 예방한다.
            "email": f"{local}.customer{customer_id}@{domain}",
            "phone": fake.phone_number(),
            "address": fake.address(),
            "registered_date": (START_DATE - timedelta(days=rng.randint(1, 730))).isoformat(),
            "grade": grade,
        })

    products = [{
        "product_id": i,
        "product_name": f"{CATEGORIES[(i - 1) % 5]} 상품 {i:03d}",
        "category": CATEGORIES[(i - 1) % 5],
        "price": rng.randint(1, 2_000) * 1_000,
        "stock_quantity": rng.randint(0, 1_000),
        "is_active": 1,
    } for i in range(1, COUNTS["products"] + 1)]

    employees = []
    for employee_id in range(1, COUNTS["employees"] + 1):
        local, domain = fake.email().split("@", 1)
        employees.append({
            "employee_id": employee_id,
            "employee_name": fake.name(),
            "email": f"{local}.employee{employee_id}@{domain}",
            "department": rng.choice(("영업", "고객지원", "물류", "관리", "상품기획")),
            "hired_date": (START_DATE - timedelta(days=rng.randint(1, 1_825))).isoformat(),
            "is_active": 1,
        })

    statuses = ["완료"] * 90_000 + ["배송중"] * 7_000 + ["취소"] * 3_000
    # 각 날짜의 건수 차이가 최대 1건이 되도록 배정한 다음 섞는다.
    date_offsets = [i % DAY_COUNT for i in range(COUNTS["orders"])]
    rng.shuffle(statuses)
    rng.shuffle(date_offsets)
    orders = []
    for order_id, (status, offset) in enumerate(zip(statuses, date_offsets), 1):
        product_id = rng.randint(1, COUNTS["products"])
        orders.append({
            "order_id": order_id,
            "customer_id": rng.randint(1, COUNTS["customers"]),
            "product_id": product_id,
            "employee_id": rng.randint(1, COUNTS["employees"]),
            "order_date": (START_DATE + timedelta(days=offset)).isoformat(),
            "quantity": rng.randint(1, 5),
            "unit_price": products[product_id - 1]["price"],
            "status": status,
            # total_amount는 DB의 generated column이 계산한다.
        })
    return {"customers": customers, "products": products, "employees": employees, "orders": orders}


def table_counts(connection: Connection) -> dict[str, int]:
    return {
        name: connection.scalar(select(func.count()).select_from(Base.metadata.tables[name]))
        for name in COUNTS
    }


def prepare_schema(connection: Connection) -> None:
    """기존 데이터가 있는 구형 스키마를 자동 삭제하지 않는다."""
    Base.metadata.create_all(connection)
    inspector = inspect(connection)
    matches = all(
        {column["name"] for column in inspector.get_columns(name)} == set(table.columns.keys())
        and {check["name"]: check["sqltext"] for check in inspector.get_check_constraints(name)}
        == {check.name: str(check.sqltext) for check in table.constraints if hasattr(check, "sqltext")}
        for name, table in Base.metadata.tables.items()
    )
    if not matches:
        if any(table_counts(connection).values()):
            raise RuntimeError("Existing populated schema requires migration; no data was overwritten.")
        Base.metadata.drop_all(connection)
        Base.metadata.create_all(connection)


def matches_existing(connection: Connection, data: dict[str, list[dict]]) -> bool:
    """재실행 시 내용까지 비교해 중복 삽입을 막는다."""
    for name, expected in data.items():
        table = Base.metadata.tables[name]
        columns = list(expected[0])
        query = select(*(table.c[column] for column in columns)).order_by(*table.primary_key.columns)
        existing = connection.execute(query).mappings()
        try:
            for row in expected:
                actual = next(existing, None)
                if actual is None or dict(actual) != row:
                    return False
            if next(existing, None) is not None:
                return False
        finally:
            existing.close()
    return True


def validate(connection: Connection) -> None:
    """건수, 분포, 금액, FK를 확인하며 실패하면 전체 삽입을 롤백한다."""
    def require(condition: bool, message: str) -> None:
        if not condition:
            raise RuntimeError(message)

    require(table_counts(connection) == COUNTS, "Unexpected table counts")
    grades = dict(connection.execute(text("SELECT grade, COUNT(*) FROM customers GROUP BY grade")).all())
    statuses = dict(connection.execute(text("SELECT status, COUNT(*) FROM orders GROUP BY status")).all())
    require(grades == {"VIP": 500, "일반": 7_000, "신규": 2_500}, "Unexpected grade distribution")
    require(statuses == {"완료": 90_000, "배송중": 7_000, "취소": 3_000}, "Unexpected status distribution")
    categories = dict(connection.execute(text("SELECT category, COUNT(*) FROM products GROUP BY category")).all())
    require(categories == {category: 100 for category in CATEGORIES}, "Unexpected categories")
    invalid_prices = connection.scalar(text("SELECT COUNT(*) FROM products WHERE price < 1000 OR price > 2000000"))
    require(invalid_prices == 0, "Invalid product prices")
    invalid_amounts = connection.scalar(text("""
        SELECT COUNT(*) FROM orders o JOIN products p ON p.product_id = o.product_id
        WHERE o.quantity NOT BETWEEN 1 AND 5 OR o.unit_price != p.price
           OR o.total_amount != p.price * o.quantity
    """))
    require(invalid_amounts == 0, "Invalid order quantities or amounts")
    days = dict(connection.execute(text("SELECT order_date, COUNT(*) FROM orders GROUP BY order_date")).all())
    expected_days = Counter((START_DATE + timedelta(days=i % DAY_COUNT)).isoformat() for i in range(COUNTS["orders"]))
    require(days == dict(expected_days), "Unexpected date distribution")
    require(not connection.exec_driver_sql("PRAGMA foreign_key_check").all(), "Invalid foreign keys")


def main() -> None:
    started = perf_counter()
    data = build_data()
    with engine.begin() as connection:
        # 스키마 변경과 삽입을 함께 롤백하고 동시 실행도 직렬화한다.
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        prepare_schema(connection)
        counts = table_counts(connection)
        if any(counts.values()):
            if counts != COUNTS or not matches_existing(connection, data):
                raise RuntimeError("Existing data differs from this seed; no data was overwritten.")
            print("Existing seed data verified; no duplicate inserts.")
        else:
            for name, rows in data.items():
                for offset in range(0, len(rows), BATCH_SIZE):
                    connection.execute(Base.metadata.tables[name].insert(), rows[offset:offset + BATCH_SIZE])
            print(f"Bulk insert completed (batch size: {BATCH_SIZE:,}).")
        validate(connection)
        counts = table_counts(connection)
    print(f"Database: {DB_PATH}")
    for name, count in counts.items():
        print(f"{name}: {count:,}")
    print(f"Validation passed. Elapsed: {perf_counter() - started:.2f}s")


if __name__ == "__main__":
    main()
