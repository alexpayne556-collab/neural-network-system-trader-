"""
COSMOS MIGRATION: Initialize database schema from schema.sql
Run this once to set up the database structure.
"""

import sqlite3
import os
from pathlib import Path


def migrate(db_path: str = "cosmo.sqlite") -> None:
    """Run schema migration."""
    repo_root = Path(__file__).resolve().parent.parent
    schema_file = repo_root / "schema" / "schema.sql"
    
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open(schema_file, "r") as f:
        schema_sql = f.read()
    
    # Execute schema
    cursor.executescript(schema_sql)
    conn.commit()
    conn.close()
    
    print(f"✓ Database initialized: {db_path}")
    print(f"✓ Schema loaded from: {schema_file}")


if __name__ == "__main__":
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else "cosmo.sqlite"
    migrate(db_path)
