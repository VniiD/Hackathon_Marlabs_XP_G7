# Banco de dados (SQLite)

Banco local e relacional. A estrutura vive em SQL puro; o `app.db` é gerado a partir dele.

| Arquivo       | O que é                                        |
|---------------|------------------------------------------------|
| `schema.sql`  | `CREATE TABLE ...` (fonte da verdade)          |
| `seed.sql`    | dados de teste                                 |
| `init_db.py`  | apaga e recria o `app.db`                      |
| `app.db`      | banco gerado (versionado como banco de teste)  |

## Como usar

Precisa só de Python 3.8+ (sem instalar nada). Da raiz do repositório:

```bash
python db/init_db.py            # recria com dados de teste
python db/init_db.py --no-seed  # recria só as tabelas
```

## Fluxo para mudar o banco

1. Edite `db/schema.sql` (e `db/seed.sql` se precisar).
2. Rode `python db/init_db.py`.
3. Commit dos `.sql` **e** do `app.db` juntos.

> Não edite o `app.db` direto na mão: na próxima vez que alguém rodar o script, a mudança some. Mude sempre o `.sql`.
>
> Em time: como o `app.db` é binário, o Git não faz merge dele. Se der conflito, faça o merge dos `.sql` e rode o script de novo.

## Atenção: chave estrangeira no código do app

No SQLite as FKs vêm **desligadas** por padrão, em toda conexão nova. Ligue sempre que abrir o banco:

```python
# Python
conn = sqlite3.connect("db/app.db")
conn.execute("PRAGMA foreign_keys = ON")
```

```js
// Node (better-sqlite3)
const db = new Database("db/app.db");
db.pragma("foreign_keys = ON");
```

## Ver o banco

- [DB Browser for SQLite](https://sqlitebrowser.org/) (app desktop)
- Extensão **SQLite Viewer** no VS Code
