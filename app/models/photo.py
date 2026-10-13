"""Photo stored in the database.

Bytes are validated, metadata-stripped, re-encoded and downscaled by
``app.photos.processing`` before they ever reach here. The
``mime_type`` is the canonical WebP or JPEG mime we re-encoded to.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Photo(SQLModel, table=True):
    __tablename__ = "photo"

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="found_item.id", index=True)
    mime_type: str = Field(max_length=32)
    width: int = Field(default=0)
    height: int = Field(default=0)
    bytes_: bytes = Field(default=b"", sa_column_kwargs={"name": "data"})
    sha256: str = Field(max_length=64, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())
