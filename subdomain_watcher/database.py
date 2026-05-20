"""Database models and async engine setup for subdomain watcher."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

_DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///subdomain-watcher.db"


class Base(DeclarativeBase):
    """Base class for all database models."""


class Subdomain(Base):
    """Model representing a discovered subdomain."""

    __tablename__ = "subdomains"

    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subdomain: Mapped[str] = mapped_column(String(255), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("domain", "subdomain", name="uq_domain_subdomain"),
    )

    def __repr__(self) -> str:
        return f"<Subdomain {self.subdomain} (domain={self.domain})>"


class Database:
    """Async database connection manager."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or _DEFAULT_DATABASE_URL
        self.engine = create_async_engine(self.database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_db(self) -> None:
        """Create all tables in the database."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Close the database engine."""
        await self.engine.dispose()

    async def get_known_subdomains(self, domain: str) -> set[str]:
        """Get all known subdomains for a domain."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Subdomain.subdomain).where(Subdomain.domain == domain),
            )
            return {row[0] for row in result.fetchall()}

    async def add_subdomain(self, domain: str, subdomain: str) -> Subdomain:
        """Add a new subdomain to the database."""
        async with self.session_factory() as session:
            db_subdomain = Subdomain(domain=domain, subdomain=subdomain)
            session.add(db_subdomain)
            await session.commit()
            await session.refresh(db_subdomain)
            return db_subdomain

    async def update_last_seen(self, domain: str, subdomains: list[str]) -> None:
        """Update last_seen timestamp for existing subdomains."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(Subdomain).where(
                    Subdomain.domain == domain,
                    Subdomain.subdomain.in_(subdomains),
                ),
            )
            for subdomain in result.scalars():
                subdomain.last_seen = datetime.now(UTC)
            await session.commit()
