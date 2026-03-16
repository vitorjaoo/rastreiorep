# Portal do Cliente — Escritório

Sistema completo para clientes acessarem NFs, boletos e rastrear entregas.

**Stack:** Python + Streamlit + Turso (libSQL) + Claude API

---

## Configuração em 5 passos

### 1. Clone e instale

```bash
git clone <seu-repositorio>
cd portal-escritorio
pip install -r requirements.txt
```

### 2. Crie o banco no Turso

1. Acesse https://turso.tech e crie uma conta gratuita
2. No dashboard: **Create Database** → dê um nome (ex: `portal-escritorio`)
3. Copie a **Database URL** (formato: `libsql://portal-escritorio-xxx.turso.io`)
4. Vá em **Tokens** → **Create Token** → copie o token gerado

### 3. Configure as credenciais

Edite `.streamlit/secrets.toml`:

```toml
TURSO_DATABASE_URL = "libsql://seu-banco.turso.io"
TURSO_AUTH_TOKEN   = "seu-token-aqui"

ANTHROPIC_API_KEY  = "sk-ant-..."   # https://console.anthropic.com

RESEND_API_KEY     = "re_..."       # https://resend.com (grátis até 3.000 emails/mês)
EMAIL_REMETENTE    = "portal@seudominio.com.br"

ADMIN_SENHA        = "sua-senha-segura"
```

### 4. Rode localmente

```bash
# Painel do escritório (você)
streamlit run app_admin.py --server.port 8501

# Portal do cliente (em outra aba)
streamlit run app_portal.py --server.port 8502
```

### 5. Suba no Streamlit Cloud (grátis)

1. Suba o projeto no GitHub (o `.gitignore` já protege suas senhas)
2. Acesse https://share.streamlit.io
3. Conecte seu repositório
4. Em **Secrets**, cole o conteúdo do `secrets.toml`
5. Deploy! Você terá duas URLs públicas

---

## GitHub Actions — Alertas automáticos

Configure os secrets no GitHub (Settings → Secrets → Actions):

| Secret | Valor |
|--------|-------|
| `TURSO_DATABASE_URL` | URL do banco Turso |
| `TURSO_AUTH_TOKEN` | Token do Turso |
| `RESEND_API_KEY` | Chave do Resend |
| `EMAIL_REMETENTE` | Email de envio |

O workflow `.github/workflows/alertas.yml` roda automaticamente todo dia às 8h.

---

## Fluxo diário (você, às 8h)

1. Abra `http://localhost:8501` (admin)
2. Menu **Upload Documentos**
3. Faça upload do PDF da NF → Claude extrai os dados automaticamente
4. Confirme/ajuste e salve
5. Repita para boletos
6. Clientes recebem email e acessam o portal automaticamente

---

## Migração para Oracle (futuramente)

O código usa SQL padrão em todo lugar. Para migrar:

1. Troque a conexão em `db.py` por `cx_Oracle` ou `oracledb`
2. Ajuste `INTEGER PRIMARY KEY AUTOINCREMENT` → `NUMBER GENERATED ALWAYS AS IDENTITY`
3. Ajuste `datetime('now')` → `SYSDATE`
4. Tudo mais permanece igual

---

## Estrutura do projeto

```
portal-escritorio/
├── app_admin.py          # Painel do escritório
├── app_portal.py         # Portal do cliente
├── db.py                 # Banco de dados (Turso)
├── extrator_pdf.py       # Claude API — lê PDFs
├── alertas.py            # Cron de vencimentos
├── requirements.txt
├── .gitignore
├── .streamlit/
│   └── secrets.toml      # Credenciais (não sobe pro Git)
└── .github/
    └── workflows/
        └── alertas.yml   # GitHub Actions
```
