from sqlalchemy import text

from app.config import get_settings
from app.db.models import Base
from app.db.session import engine


def init_db() -> None:
    """Create the application database (MySQL) and tables if they do not exist."""
    settings = get_settings()
    url = settings.sqlalchemy_url

    if url.startswith("mysql"):
        admin_url = url.rsplit("/", 1)[0]
        from sqlalchemy import create_engine

        admin_engine = create_engine(admin_url, pool_pre_ping=True)
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
        admin_engine.dispose()

    Base.metadata.create_all(bind=engine)
