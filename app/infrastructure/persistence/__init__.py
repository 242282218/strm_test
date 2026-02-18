"""
Infrastructure persistence module.

Contains repository implementations and database mappings.
"""

from app.infrastructure.persistence.strm_repository_impl import SqlAlchemyStrmRepository

__all__ = ["SqlAlchemyStrmRepository"]
