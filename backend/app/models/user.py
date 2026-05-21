from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.backtest import BacktestSession
    from app.models.score import SportteryMatchScore


class User (Base, TimestampMixin):
    """运营/操盘用户表 (users)."""

    __tablename__ = "users"
    __table_args__ = ({"comment": "运营/操盘用户"},)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, comment="主键",
    )
    phone: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True,
        comment="登录手机号",
    )
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="姓名/昵称",
    )
    role: Mapped[str] = mapped_column(
        Enum("admin", "member", name="user_role"),
        nullable=False,
        default="member",
        comment="角色: admin 管理员 / member 普通用户",
    )
    password_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="密码哈希",
    )
    bankroll_cny: Mapped[Decimal] = mapped_column(
        DECIMAL(12, 2), nullable=False, default=Decimal("10000.00"),
        comment="可用本金(CNY), 用于 Kelly 仓位计算",
    )

    scores: Mapped[list[SportteryMatchScore]] = relationship(back_populates="user")
    backtests: Mapped[list[BacktestSession]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"
