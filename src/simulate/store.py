"""Write tables to the two DuckDB files. Truth and observed never share a file."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def write_tables(path: Path, tables: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    for name, df in tables.items():
        con.register("_tmp", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _tmp")
        con.unregister("_tmp")
    con.close()
