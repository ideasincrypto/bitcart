import secrets

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Query, load_only
from sqlalchemy.orm import relationship as sqa_relationship

from api import settings
from api.db import Base
from api.ext.moneyformat import currency_table


class OnlyIdQuery(Query):
    def all(self):
        return self.all(self.options(load_only("id")))


def relationship(*args, **kwargs):
    return sqa_relationship(lazy="selectin", *args, **kwargs)


class User(Base):
    # __tablename__ = "users"

    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_superuser = Column(Boolean(), default=False)
    created = Column(DateTime(True), nullable=False)


# TODO
"""class WalletUpdateRequest(UpdateRequest):
    async def apply(self):
        coin = settings.get_coin(self._instance.currency)
        if await coin.validate_key(self._instance.xpub):
            return await super().apply()
        else:
            raise HTTPException(422, "Wallet key invalid")"""


class Wallet(Base):
    # __tablename__ = "wallets"
    # _update_request_cls = WalletUpdateRequest

    name = Column(String(length=1000), index=True)
    xpub = Column(String(length=1000), index=True)
    currency = Column(String(length=1000), index=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User)
    created = Column(DateTime(True), nullable=False)
    lightning_enabled = Column(Boolean(), default=False)

    @classmethod
    async def create(cls, **kwargs):
        kwargs["currency"] = kwargs.get("currency") or "btc"
        coin = settings.get_coin(kwargs.get("currency"))
        if await coin.validate_key(kwargs.get("xpub")):
            return await super().create(**kwargs)
        else:
            raise HTTPException(422, "Wallet key invalid")


class Notification(Base):
    # __tablename__ = "notifications"

    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User)
    name = Column(String(length=1000), index=True)
    provider = Column(String(length=10000))
    data = Column(JSON)
    created = Column(DateTime(True), nullable=False)


class Template(Base):
    # __tablename__ = "templates"

    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User)
    name = Column(String(length=100000), index=True)
    text = Column(Text())
    created = Column(DateTime(True), nullable=False)
    _unique_constaint = UniqueConstraint("user_id", "name")


WalletxStore = Table(
    "walletsxstores",
    Base.metadata,
    Column("wallet_id", Integer, ForeignKey("wallets.id", ondelete="SET NULL")),
    Column("store_id", Integer, ForeignKey("stores.id", ondelete="SET NULL")),
)


"""class WalletxStore(Base):
    # __tablename__ = "walletsxstores"

    wallet_id = Column(Integer, ForeignKey("wallets.id", ondelete="SET NULL"))
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"))
"""

NotificationxStore = Table(
    "notificationsxstores",
    Base.metadata,
    Column("notification_id", Integer, ForeignKey("notifications.id", ondelete="SET NULL")),
    Column("store_id", Integer, ForeignKey("stores.id", ondelete="SET NULL")),
)

"""class NotificationxStore(Base):
    # __tablename__ = "notificationsxstores"

    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="SET NULL"))
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"))"""


class Store(Base):
    # __tablename__ = "stores"
    # _update_request_cls = StoreUpdateRequest TODO

    name = Column(String(1000), index=True)
    default_currency = Column(Text)
    email = Column(String(1000), index=True)
    email_host = Column(String(1000))
    email_password = Column(String(1000))
    email_port = Column(Integer)
    email_use_ssl = Column(Boolean)
    email_user = Column(String(1000))
    checkout_settings = Column(JSON)
    templates = Column(JSON)
    wallets = relationship("Wallet", secondary=WalletxStore)
    notifications = relationship("Notification", secondary=NotificationxStore)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User)
    created = Column(DateTime(True), nullable=False)

    @hybrid_method
    def get_setting(self, scheme):
        data = self.checkout_settings or {}
        return scheme(**data)

    async def set_setting(self, scheme):
        json_data = jsonable_encoder(scheme, exclude_unset=True)
        await self.update(checkout_settings=json_data).apply()


class Discount(Base):
    # __tablename__ = "discounts"

    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User)
    name = Column(String(length=1000), index=True)
    percent = Column(Integer)
    description = Column(Text, index=True)
    promocode = Column(Text)
    currencies = Column(String(length=10000), index=True)
    end_date = Column(DateTime(True), nullable=False)
    created = Column(DateTime(True), nullable=False)


DiscountxProduct = Table(
    "discountsxproducts",
    Base.metadata,
    Column("discount_id", Integer, ForeignKey("discounts.id", ondelete="SET NULL")),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="SET NULL")),
)
"""class DiscountxProduct(Base):
    # __tablename__ = "discountsxproducts"

    discount_id = Column(Integer, ForeignKey("discounts.id", ondelete="SET NULL"))
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))"""


class Product(Base):
    # __tablename__ = "products"
    # _update_request_cls = DiscountXProductUpdateRequest TODO

    name = Column(String(length=1000), index=True)
    price = Column(Numeric(16, 8), nullable=False)
    quantity = Column(Numeric(16, 8), nullable=False)
    download_url = Column(String(100000))
    category = Column(Text)
    description = Column(Text)
    image = Column(String(100000))
    store_id = Column(
        Integer,
        ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"),
        index=True,
    )
    status = Column(String(1000), nullable=False)
    templates = Column(JSON)
    store = relationship("Store")
    discounts = relationship("Discount", secondary=DiscountxProduct)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    invoices = relationship("ProductxInvoice", back_populates="product")
    user = relationship(User)
    created = Column(DateTime(True), nullable=False)


class ProductxInvoice(Base):
    # __tablename__ = "productsxinvoices"

    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"))
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"))
    count = Column(Integer)
    product = relationship("Product", back_populates="invoices")
    invoice = relationship("Invoice", back_populates="products")


class PaymentMethod(Base):
    # __tablename__ = "paymentmethods"

    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"))
    amount = Column(Numeric(16, 8), nullable=False)
    rate = Column(Numeric(16, 8))
    discount = Column(Integer)
    confirmations = Column(Integer, nullable=False)
    recommended_fee = Column(Numeric(16, 8), nullable=False)
    currency = Column(String(length=1000), index=True)
    payment_address = Column(Text, nullable=False)
    payment_url = Column(Text, nullable=False)
    rhash = Column(Text)
    lightning = Column(Boolean(), default=False)
    node_id = Column(Text)

    async def to_dict(self, index: int = None):
        data = super().to_dict()
        invoice_id = data.pop("invoice_id")
        invoice = await Invoice.query.where(Invoice.id == invoice_id).gino.first()
        data["amount"] = currency_table.format_currency(self.currency, self.amount)
        data["rate"] = currency_table.format_currency(invoice.currency, self.rate, fancy=False)
        data["rate_str"] = currency_table.format_currency(invoice.currency, self.rate)
        data["name"] = self.get_name(index)
        return data

    def get_name(self, index: int = None):
        name = f"{self.currency} (⚡)" if self.lightning else self.currency
        if index:
            name += f" ({index})"
        return name.upper()


class Invoice(Base):
    # __tablename__ = "invoices"
    # _update_request_cls = InvoiceUpdateRequest TODO

    price = Column(Numeric(16, 8), nullable=False)
    currency = Column(Text)
    paid_currency = Column(String(length=1000))
    status = Column(String(1000), nullable=False)
    expiration = Column(Integer)
    buyer_email = Column(String(10000))
    discount = Column(Integer)
    promocode = Column(Text)
    notification_url = Column(Text)
    redirect_url = Column(Text)
    products = relationship("ProductxInvoice", back_populates="invoice")
    store_id = Column(
        Integer,
        ForeignKey("stores.id", deferrable=True, initially="DEFERRED", ondelete="SET NULL"),
        index=True,
    )
    order_id = Column(Text)
    store = relationship("Store")
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"))
    user = relationship(User, backref="invoices")
    created = Column(DateTime(True), nullable=False)

    @classmethod
    async def create(cls, **kwargs):
        from api import crud
        from api.invoices import InvoiceStatus

        store_id = kwargs["store_id"]
        kwargs["status"] = InvoiceStatus.PENDING
        store = await Store.get(store_id)
        await crud.stores.get_store(None, None, store, True)
        if not store.wallets:
            raise HTTPException(422, "No wallet linked")
        if not kwargs.get("user_id"):
            kwargs["user_id"] = store.user_id
        kwargs.pop("products", None)
        return await super().create(**kwargs), store.wallets


class Setting(Base):
    # __tablename__ = "settings"

    name = Column(Text)
    value = Column(Text)
    created = Column(DateTime(True), nullable=False)


class Token(Base):
    # __tablename__ = "tokens"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.id, ondelete="SET NULL"), index=True)
    app_id = Column(String)
    redirect_url = Column(String)
    permissions = Column(ARRAY(String))
    created = Column(DateTime(True), nullable=False)

    @classmethod
    async def create(cls, **kwargs):
        kwargs["id"] = secrets.token_urlsafe()
        return await super().create(**kwargs)
