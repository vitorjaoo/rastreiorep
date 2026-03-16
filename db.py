"""
db.py — conexão com Turso (libSQL) e criação das tabelas
Compatível com migração futura para Oracle (SQL padrão)
"""

import libsql_client
import streamlit as st


def get_client():
    """Retorna cliente Turso usando credenciais do secrets.toml"""
    return libsql_client.create_client_sync(
        url=st.secrets["TURSO_DATABASE_URL"],
        auth_token=st.secrets["TURSO_AUTH_TOKEN"],
    )


def criar_tabelas():
    """Cria todas as tabelas se não existirem — roda na inicialização"""
    with get_client() as client:
        client.batch([
            libsql_client.Statement("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome        TEXT NOT NULL,
                    cnpj        TEXT UNIQUE NOT NULL,
                    email       TEXT,
                    whatsapp    TEXT,
                    senha_hash  TEXT NOT NULL,
                    ativo       INTEGER DEFAULT 1,
                    criado_em   TEXT DEFAULT (datetime('now'))
                )
            """),
            libsql_client.Statement("""
                CREATE TABLE IF NOT EXISTS notas_fiscais (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id      INTEGER NOT NULL,
                    numero_nf       TEXT,
                    valor           REAL,
                    data_emissao    TEXT,
                    status          TEXT DEFAULT 'ativo',
                    pdf_base64      TEXT,
                    nome_arquivo    TEXT,
                    codigo_rastreio TEXT,
                    transportadora  TEXT,
                    criado_em       TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
                )
            """),
            libsql_client.Statement("""
                CREATE TABLE IF NOT EXISTS titulos (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    cliente_id      INTEGER NOT NULL,
                    numero_titulo   TEXT,
                    valor           REAL,
                    vencimento      TEXT,
                    status          TEXT DEFAULT 'aberto',
                    boleto_base64   TEXT,
                    nome_arquivo    TEXT,
                    nf_id           INTEGER,
                    criado_em       TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
                    FOREIGN KEY (nf_id)      REFERENCES notas_fiscais(id)
                )
            """),
        ])


# ─── Clientes ────────────────────────────────────────────────────────────────

def listar_clientes():
    with get_client() as c:
        rs = c.execute("SELECT id, nome, cnpj, email, whatsapp, ativo FROM clientes ORDER BY nome")
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def buscar_cliente_cnpj(cnpj: str):
    with get_client() as c:
        rs = c.execute(
            "SELECT id, nome, cnpj, email, whatsapp, senha_hash, ativo FROM clientes WHERE cnpj = ?",
            [cnpj]
        )
        if rs.rows:
            return dict(zip(rs.columns, rs.rows[0]))
    return None


def criar_cliente(nome, cnpj, email, whatsapp, senha_hash):
    with get_client() as c:
        c.execute(
            "INSERT INTO clientes (nome, cnpj, email, whatsapp, senha_hash) VALUES (?, ?, ?, ?, ?)",
            [nome, cnpj, email, whatsapp, senha_hash]
        )


def atualizar_cliente(cliente_id, nome, email, whatsapp):
    with get_client() as c:
        c.execute(
            "UPDATE clientes SET nome=?, email=?, whatsapp=? WHERE id=?",
            [nome, email, whatsapp, cliente_id]
        )


# ─── Notas Fiscais ────────────────────────────────────────────────────────────

def listar_nfs(cliente_id: int):
    with get_client() as c:
        rs = c.execute(
            """SELECT id, numero_nf, valor, data_emissao, status,
                      nome_arquivo, codigo_rastreio, transportadora, criado_em
               FROM notas_fiscais
               WHERE cliente_id = ?
               ORDER BY criado_em DESC""",
            [cliente_id]
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def listar_todas_nfs():
    with get_client() as c:
        rs = c.execute(
            """SELECT nf.id, c.nome as cliente, nf.numero_nf, nf.valor,
                      nf.data_emissao, nf.status, nf.nome_arquivo,
                      nf.codigo_rastreio, nf.transportadora, nf.criado_em
               FROM notas_fiscais nf
               JOIN clientes c ON c.id = nf.cliente_id
               ORDER BY nf.criado_em DESC"""
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def inserir_nf(cliente_id, numero_nf, valor, data_emissao, pdf_base64, nome_arquivo,
               codigo_rastreio="", transportadora=""):
    with get_client() as c:
        c.execute(
            """INSERT INTO notas_fiscais
               (cliente_id, numero_nf, valor, data_emissao, pdf_base64,
                nome_arquivo, codigo_rastreio, transportadora)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [cliente_id, numero_nf, valor, data_emissao,
             pdf_base64, nome_arquivo, codigo_rastreio, transportadora]
        )


def get_pdf_nf(nf_id: int):
    with get_client() as c:
        rs = c.execute(
            "SELECT pdf_base64, nome_arquivo FROM notas_fiscais WHERE id = ?",
            [nf_id]
        )
        if rs.rows:
            return dict(zip(rs.columns, rs.rows[0]))
    return None


def atualizar_rastreio(nf_id, codigo_rastreio, transportadora):
    with get_client() as c:
        c.execute(
            "UPDATE notas_fiscais SET codigo_rastreio=?, transportadora=? WHERE id=?",
            [codigo_rastreio, transportadora, nf_id]
        )


# ─── Títulos ──────────────────────────────────────────────────────────────────

def listar_titulos(cliente_id: int):
    with get_client() as c:
        rs = c.execute(
            """SELECT id, numero_titulo, valor, vencimento, status,
                      nome_arquivo, nf_id, criado_em
               FROM titulos
               WHERE cliente_id = ?
               ORDER BY vencimento ASC""",
            [cliente_id]
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def listar_todos_titulos():
    with get_client() as c:
        rs = c.execute(
            """SELECT t.id, c.nome as cliente, t.numero_titulo, t.valor,
                      t.vencimento, t.status, t.nome_arquivo, t.nf_id, t.criado_em
               FROM titulos t
               JOIN clientes c ON c.id = t.cliente_id
               ORDER BY t.vencimento ASC"""
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def inserir_titulo(cliente_id, numero_titulo, valor, vencimento,
                   boleto_base64, nome_arquivo, nf_id=None):
    with get_client() as c:
        c.execute(
            """INSERT INTO titulos
               (cliente_id, numero_titulo, valor, vencimento,
                boleto_base64, nome_arquivo, nf_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [cliente_id, numero_titulo, valor, vencimento,
             boleto_base64, nome_arquivo, nf_id]
        )


def get_pdf_titulo(titulo_id: int):
    with get_client() as c:
        rs = c.execute(
            "SELECT boleto_base64, nome_arquivo FROM titulos WHERE id = ?",
            [titulo_id]
        )
        if rs.rows:
            return dict(zip(rs.columns, rs.rows[0]))
    return None


def marcar_titulo_pago(titulo_id: int):
    with get_client() as c:
        c.execute("UPDATE titulos SET status='pago' WHERE id=?", [titulo_id])


def titulos_vencendo(dias: int = 5):
    """Retorna títulos em aberto que vencem nos próximos N dias"""
    with get_client() as c:
        rs = c.execute(
            """SELECT t.id, c.nome, c.email, c.whatsapp,
                      t.numero_titulo, t.valor, t.vencimento
               FROM titulos t
               JOIN clientes c ON c.id = t.cliente_id
               WHERE t.status = 'aberto'
                 AND date(t.vencimento) <= date('now', ? || ' days')
                 AND date(t.vencimento) >= date('now')
               ORDER BY t.vencimento ASC""",
            [str(dias)]
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]
