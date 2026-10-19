#!/usr/bin/env python3
"""Recria o banco SQLite a partir de db/schema.sql (+ db/seed.sql).

Uso (da raiz do repositório):
    python db/init_db.py            # recria com dados de teste
    python db/init_db.py --no-seed  # recria só a estrutura

Só usa a biblioteca padrão do Python (3.8+), não precisa instalar nada.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
ROOT = DB_DIR.parent
DB_PATH = DB_DIR / "app.db"
SCHEMA = DB_DIR / "schema.sql"
SEED = DB_DIR / "seed.sql"


def apagar_banco():
    try:
        DB_PATH.unlink()
    except FileNotFoundError:
        pass
    except PermissionError:
        sys.exit(f"Não consegui apagar {DB_PATH.name}: feche ele no DB Browser/VS Code e rode de novo.")


def rodar_arquivo(conn, caminho):
    print(f"  -> {caminho.relative_to(ROOT)}")
    conn.executescript(caminho.read_text(encoding="utf-8"))


def resumo(conn):
    tabelas = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    print(f"\nBanco criado em {DB_PATH.relative_to(ROOT)} com {len(tabelas)} tabela(s):")
    for t in tabelas:
        n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"  {t:<20} {n} linha(s)")


def main():
    parser = argparse.ArgumentParser(description="Recria o banco SQLite do projeto.")
    parser.add_argument("--no-seed", action="store_true", help="não insere os dados de teste")
    args = parser.parse_args()

    apagar_banco()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        print("Aplicando:")
        rodar_arquivo(conn, SCHEMA)
        if not args.no_seed and SEED.exists():
            rodar_arquivo(conn, SEED)
        conn.commit()

        problemas = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if problemas:
            raise sqlite3.IntegrityError(f"chaves estrangeiras quebradas: {problemas}")

        resumo(conn)
    except sqlite3.Error as e:
        conn.close()
        apagar_banco()
        sys.exit(f"\nERRO no SQL: {e}\nO banco não foi criado. Corrija o .sql e rode de novo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
