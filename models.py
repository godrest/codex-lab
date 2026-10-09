"""고객, 상품, 직원, 주문 모델 (SQLAlchemy 2.x)."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """모든 모델이 공유하는 메타데이터."""


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("grade IN ('VIP', '일반', '신규')", name="ck_customers_grade"),
    )

    customer_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="고객 식별자")
    customer_name: Mapped[str] = mapped_column(Text, nullable=False, comment="고객 이름")
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, comment="고객 이메일")
    phone: Mapped[str | None] = mapped_column(Text, nullable=True, comment="전화번호")
    address: Mapped[str | None] = mapped_column(Text, nullable=True, comment="주소")
    registered_date: Mapped[str] = mapped_column(Text, nullable=False, comment="가입일 (YYYY-MM-DD)")
    grade: Mapped[str] = mapped_column(Text, nullable=False, comment="고객 등급 (VIP/일반/신규)")

    orders: Mapped[list[Order]] = relationship(back_populates="customer", passive_deletes="all")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price"),
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_quantity"),
        CheckConstraint("is_active IN (0, 1)", name="ck_products_is_active"),
    )

    product_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="상품 식별자")
    product_name: Mapped[str] = mapped_column(Text, nullable=False, comment="상품명")
    category: Mapped[str] = mapped_column(Text, nullable=False, comment="상품 분류")
    price: Mapped[int] = mapped_column(Integer, nullable=False, comment="현재 판매 단가 (원)")
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="현재 재고 수량")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, comment="판매 중 여부 (0/1)")

    orders: Mapped[list[Order]] = relationship(back_populates="product", passive_deletes="all")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("is_active IN (0, 1)", name="ck_employees_is_active"),
    )

    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="직원 식별자")
    employee_name: Mapped[str] = mapped_column(Text, nullable=False, comment="직원 이름")
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True, comment="직원 이메일")
    department: Mapped[str] = mapped_column(Text, nullable=False, comment="부서")
    hired_date: Mapped[str] = mapped_column(Text, nullable=False, comment="입사일 (YYYY-MM-DD)")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, comment="재직 여부 (0/1)")

    orders: Mapped[list[Order]] = relationship(back_populates="employee", passive_deletes="all")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orders_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_orders_unit_price"),
        CheckConstraint("status IN ('완료', '배송중', '취소')", name="ck_orders_status"),
        Index("ix_orders_customer_date", "customer_id", "order_date"),
        Index("ix_orders_employee_date", "employee_id", "order_date"),
        Index("ix_orders_product_id", "product_id"),
        Index("ix_orders_order_date", "order_date"),
    )

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True, comment="주문 식별자")
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False, comment="주문 고객 식별자",
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.product_id", ondelete="RESTRICT"),
        nullable=False, comment="주문 상품 식별자",
    )
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.employee_id", ondelete="RESTRICT"),
        nullable=False, comment="담당 직원 식별자",
    )
    order_date: Mapped[str] = mapped_column(Text, nullable=False, comment="주문일 (YYYY-MM-DD)")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="주문 수량")
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False, comment="주문 당시 단가 (원)")
    total_amount: Mapped[int] = mapped_column(
        Integer, Computed("unit_price * quantity", persisted=True), comment="주문 금액 (단가 × 수량, 원)",
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, comment="주문 상태")

    customer: Mapped[Customer] = relationship(back_populates="orders")
    product: Mapped[Product] = relationship(back_populates="orders")
    employee: Mapped[Employee] = relationship(back_populates="orders")
