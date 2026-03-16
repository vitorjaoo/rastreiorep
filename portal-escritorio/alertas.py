"""
alertas.py — verifica vencimentos e envia notificações
Roda todo dia via GitHub Actions (cron)

Uso: python alertas.py
"""

import os
import sys
import resend
import libsql_client
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

TURSO_URL   = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
RESEND_KEY  = os.getenv("RESEND_API_KEY")
EMAIL_FROM  = os.getenv("EMAIL_REMETENTE", "portal@seuescritorio.com.br")
DIAS_AVISO  = int(os.getenv("DIAS_AVISO", "5"))   # avisar com X dias de antecedência


# ─── DB direto (sem Streamlit) ────────────────────────────────────────────────

def get_titulos_vencendo():
    with libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN) as c:
        rs = c.execute(
            """SELECT t.id, cl.nome, cl.email, cl.whatsapp,
                      t.numero_titulo, t.valor, t.vencimento
               FROM titulos t
               JOIN clientes cl ON cl.id = t.cliente_id
               WHERE t.status = 'aberto'
                 AND date(t.vencimento) <= date('now', ? || ' days')
                 AND date(t.vencimento) >= date('now')
               ORDER BY t.vencimento ASC""",
            [str(DIAS_AVISO)]
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


def get_titulos_vencidos():
    with libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN) as c:
        rs = c.execute(
            """SELECT t.id, cl.nome, cl.email, cl.whatsapp,
                      t.numero_titulo, t.valor, t.vencimento
               FROM titulos t
               JOIN clientes cl ON cl.id = t.cliente_id
               WHERE t.status = 'aberto'
                 AND date(t.vencimento) < date('now')
               ORDER BY t.vencimento ASC"""
        )
        return [dict(zip(rs.columns, row)) for row in rs.rows]


# ─── Email ────────────────────────────────────────────────────────────────────

def enviar_email(destinatario: str, nome_cliente: str, titulos: list, tipo: str):
    resend.api_key = RESEND_KEY

    if tipo == "vencendo":
        assunto = f"⚠️ Título(s) vencendo em breve — {nome_cliente}"
        cor = "#F59E0B"
        titulo_header = "Títulos com vencimento próximo"
        mensagem_intro = f"Olá, {nome_cliente}! Os seguintes títulos vencem nos próximos {DIAS_AVISO} dias:"
    else:
        assunto = f"🔴 Título(s) vencidos — {nome_cliente}"
        cor = "#EF4444"
        titulo_header = "Títulos em atraso"
        mensagem_intro = f"Olá, {nome_cliente}! Os seguintes títulos estão vencidos:"

    linhas_titulos = ""
    for t in titulos:
        valor_fmt = f"R$ {float(t['valor']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        linhas_titulos += f"""
        <tr>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0">{t['numero_titulo']}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;font-weight:600">{valor_fmt}</td>
          <td style="padding:10px;border-bottom:1px solid #f0f0f0;color:{cor};font-weight:600">{t['vencimento']}</td>
        </tr>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f9f9f9;padding:20px">
      <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">
        <div style="background:{cor};padding:20px 24px">
          <h2 style="color:white;margin:0;font-size:18px">{titulo_header}</h2>
        </div>
        <div style="padding:24px">
          <p style="color:#374151;margin-bottom:20px">{mensagem_intro}</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
              <tr style="background:#f3f4f6">
                <th style="padding:10px;text-align:left;color:#6b7280">Título</th>
                <th style="padding:10px;text-align:left;color:#6b7280">Valor</th>
                <th style="padding:10px;text-align:left;color:#6b7280">Vencimento</th>
              </tr>
            </thead>
            <tbody>{linhas_titulos}</tbody>
          </table>
          <div style="margin-top:24px;padding:16px;background:#f9fafb;border-radius:8px">
            <p style="margin:0;color:#6b7280;font-size:13px">
              Acesse o portal para baixar seus boletos ou entre em contato com nosso escritório.
            </p>
          </div>
        </div>
        <div style="padding:16px 24px;background:#f9fafb;border-top:1px solid #e5e7eb">
          <p style="margin:0;font-size:12px;color:#9ca3af;text-align:center">
            Portal do Cliente — Escritório
          </p>
        </div>
      </div>
    </body>
    </html>"""

    try:
        resend.Emails.send({
            "from": EMAIL_FROM,
            "to": [destinatario],
            "subject": assunto,
            "html": html,
        })
        print(f"  ✅ Email enviado para {destinatario}")
        return True
    except Exception as e:
        print(f"  ❌ Erro ao enviar email para {destinatario}: {e}")
        return False


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n{'='*50}")
    print(f"Portal Escritório — Alertas de vencimento")
    print(f"Rodando em: {hoje}")
    print(f"{'='*50}\n")

    # Agrupa por cliente
    def agrupar_por_cliente(titulos):
        grupos = {}
        for t in titulos:
            chave = (t["nome"], t["email"])
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(t)
        return grupos

    # ── Vencendo em breve ──
    vencendo = get_titulos_vencendo()
    print(f"📋 Títulos vencendo em {DIAS_AVISO} dias: {len(vencendo)}")
    enviados = 0
    for (nome, email), titulos in agrupar_por_cliente(vencendo).items():
        if email:
            print(f"  → {nome} ({email}): {len(titulos)} título(s)")
            if enviar_email(email, nome, titulos, "vencendo"):
                enviados += 1
    print(f"  Emails enviados: {enviados}\n")

    # ── Vencidos ──
    vencidos = get_titulos_vencidos()
    print(f"🔴 Títulos vencidos: {len(vencidos)}")
    enviados = 0
    for (nome, email), titulos in agrupar_por_cliente(vencidos).items():
        if email:
            print(f"  → {nome} ({email}): {len(titulos)} título(s) vencido(s)")
            if enviar_email(email, nome, titulos, "vencido"):
                enviados += 1
    print(f"  Emails enviados: {enviados}\n")

    print("✅ Alertas concluídos.\n")


if __name__ == "__main__":
    main()
