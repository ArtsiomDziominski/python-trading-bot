"""One-off: print PostgreSQL DDL from models."""
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql

from app.db.base import Base
import app.models  # noqa: F401

for table in Base.metadata.sorted_tables:
    print(str(CreateTable(table).compile(dialect=postgresql.dialect())) + ";\n")
