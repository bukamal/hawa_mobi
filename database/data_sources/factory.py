# -*- coding: utf-8 -*-
from __future__ import annotations

from database.data_sources.local import LocalDataSource
from database.data_sources.remote import RemoteDataSource


def get_data_source(db):
    """Return the data source matching the current runtime mode."""
    if db.is_remote():
        return RemoteDataSource(db.get_rest_client())
    return LocalDataSource(db)
