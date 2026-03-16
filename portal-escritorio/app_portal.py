"""
app_portal.py — Portal do Cliente
Acesso: streamlit run app_portal.py
"""

import base64
import hashlib
import streamlit as st
from datetime import datetime

import db

# ─── Config ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Portal do Cliente",
    page_icon="📦",
    layout="centered",
)

# CSS minimalista
st.markdown("""
<style>
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-entregue { background: #d1fae5; color: #065f46; }
  .badge-transito { background: #dbeafe; color: #1e40af; }
  .badge-aberto   { background: #fef3c7; color: #92400e; }
  .badge-pago     { background: #d1fae5; color: #065f46; }
  .badge-vencido  { background: #fee2e2; color: #991b1b; }
</style>
""", unsafe_allow_html=True)


# ─── Init banco ───────────────────────────────────────────────────────────────

db.criar_tabelas()


# ─── Login ────────────────────────────────────────────────────────────────────

def fazer_login():
    st.title("📦 Portal do Cliente")
    st.caption("Acesse seus documentos e pedidos")

    with st.form("login"):
        cnpj  = st.text_input("CNPJ", placeholder="00.000.000/0001-00")
        senha = st.text_input("Senha", type="password")
        ok    = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if ok:
        if not cnpj or not senha:
            st.error("Preencha CNPJ e senha.")
            return

        cliente = db.buscar_cliente_cnpj(cnpj)
        if not cliente:
            st.error("CNPJ não encontrado.")
            return

        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        if senha_hash != cliente["senha_hash"]:
            st.error("Senha incorreta.")
            return

        if not cliente["ativo"]:
            st.error("Acesso desativado. Entre em contato com o escritório.")
            return

        st.session_state["cliente"] = cliente
        st.rerun()

    st.divider()
    st.caption("Primeiro acesso? Entre em contato com o escritório para receber suas credenciais.")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def botao_download_pdf(pdf_base64: str, nome_arquivo: str, label: str):
    """Renderiza botão de download do PDF diretamente"""
    if not pdf_base64:
        st.caption("PDF não disponível")
        return
    pdf_bytes = base64.b64decode(pdf_base64)
    st.download_button(
        label=label,
        data=pdf_bytes,
        file_name=nome_arquivo,
        mime="application/pdf",
        use_container_width=True,
    )


def formatar_valor(valor):
    if valor is None:
        return "—"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def badge_status(status: str) -> str:
    mapa = {
        "ativo":     ("badge-transito", "Em aberto"),
        "pago":      ("badge-pago",     "Pago"),
        "aberto":    ("badge-aberto",   "Em aberto"),
        "vencido":   ("badge-vencido",  "Vencido"),
        "entregue":  ("badge-entregue", "Entregue"),
        "cancelado": ("badge-vencido",  "Cancelado"),
    }
    css, texto = mapa.get(status, ("badge-transito", status))
    return f'<span class="status-badge {css}">{texto}</span>'


# ─── Portal Principal ─────────────────────────────────────────────────────────

def portal(cliente: dict):
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"Olá, {cliente['nome'].split()[0]}! 👋")
        st.caption(f"CNPJ: {cliente['cnpj']}")
    with col2:
        if st.button("Sair", use_container_width=True):
            st.session_state.pop("cliente", None)
            st.rerun()

    tab_nf, tab_rastreio, tab_fin = st.tabs(["📄 Notas Fiscais", "📦 Rastreio", "💰 Financeiro"])

    # ═══════════════════════════════════════════════════════════════════════
    # ABA 1 — NOTAS FISCAIS
    # ═══════════════════════════════════════════════════════════════════════
    with tab_nf:
        nfs = db.listar_nfs(cliente["id"])

        if not nfs:
            st.info("Nenhuma nota fiscal disponível no momento.")
        else:
            # Métricas
            col1, col2, col3 = st.columns(3)
            col1.metric("Total de NFs", len(nfs))
            col2.metric("Com rastreio", sum(1 for n in nfs if n.get("codigo_rastreio")))
            valor_total = sum(float(n["valor"] or 0) for n in nfs)
            col3.metric("Valor total", formatar_valor(valor_total))

            st.divider()

            for nf in nfs:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(f"**NF {nf['numero_nf']}**")
                        st.caption(f"Emitida em {nf['data_emissao']}")
                    with col2:
                        st.write(f"**{formatar_valor(nf['valor'])}**")
                    with col3:
                        st.markdown(badge_status("ativo"), unsafe_allow_html=True)

                    if nf.get("codigo_rastreio"):
                        st.caption(f"📦 Rastreio: `{nf['codigo_rastreio']}` — {nf.get('transportadora', '')}")

                    # Download do PDF
                    dados_pdf = db.get_pdf_nf(nf["id"])
                    if dados_pdf and dados_pdf.get("pdf_base64"):
                        botao_download_pdf(
                            dados_pdf["pdf_base64"],
                            dados_pdf["nome_arquivo"] or f"NF_{nf['numero_nf']}.pdf",
                            "⬇️ Baixar NF (PDF)"
                        )

    # ═══════════════════════════════════════════════════════════════════════
    # ABA 2 — RASTREIO
    # ═══════════════════════════════════════════════════════════════════════
    with tab_rastreio:
        nfs_com_rastreio = [n for n in db.listar_nfs(cliente["id"]) if n.get("codigo_rastreio")]

        if not nfs_com_rastreio:
            st.info("Nenhuma remessa com código de rastreio disponível no momento.")
        else:
            for nf in nfs_com_rastreio:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**NF {nf['numero_nf']}** — {nf.get('transportadora', 'Transportadora')}")
                        st.caption(f"Emitida em {nf['data_emissao']}")
                    with col2:
                        st.markdown(badge_status("ativo"), unsafe_allow_html=True)

                    st.code(nf["codigo_rastreio"], language=None)

                    transportadora = (nf.get("transportadora") or "").lower()

                    if "correios" in transportadora:
                        url = f"https://rastreamento.correios.com.br/app/index.php"
                        st.link_button("🔗 Rastrear nos Correios", url, use_container_width=True)
                    elif "jadlog" in transportadora:
                        url = f"https://www.jadlog.com.br/jadlog/tracking.jad?cte={nf['codigo_rastreio']}"
                        st.link_button("🔗 Rastrear na Jadlog", url, use_container_width=True)
                    elif "sequoia" in transportadora or "tnt" in transportadora:
                        url = "https://sequoialog.com.br/rastreamento"
                        st.link_button("🔗 Rastrear na Sequoia", url, use_container_width=True)
                    else:
                        url = f"https://www.google.com/search?q=rastrear+{nf['codigo_rastreio']}+{nf.get('transportadora','')}"
                        st.link_button("🔍 Buscar rastreio", url, use_container_width=True)

    # ═══════════════════════════════════════════════════════════════════════
    # ABA 3 — FINANCEIRO
    # ═══════════════════════════════════════════════════════════════════════
    with tab_fin:
        titulos = db.listar_titulos(cliente["id"])

        if not titulos:
            st.info("Nenhum título financeiro disponível.")
        else:
            hoje = datetime.now().strftime("%Y-%m-%d")

            # Métricas
            em_aberto = [t for t in titulos if t["status"] == "aberto"]
            pagos_list = [t for t in titulos if t["status"] == "pago"]

            total_aberto = sum(float(t["valor"] or 0) for t in em_aberto)
            total_pago   = sum(float(t["valor"] or 0) for t in pagos_list)

            col1, col2, col3 = st.columns(3)
            col1.metric("Em aberto", formatar_valor(total_aberto))
            col2.metric("Quitado",   formatar_valor(total_pago))
            col3.metric("Títulos abertos", len(em_aberto))

            st.divider()

            for titulo in titulos:
                # Determina status visual
                status_vis = titulo["status"]
                if status_vis == "aberto":
                    # Converte DD/MM/AAAA para AAAA-MM-DD para comparar
                    try:
                        parts = titulo["vencimento"].split("/")
                        venc_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        if venc_iso < hoje:
                            status_vis = "vencido"
                    except Exception:
                        pass

                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.write(f"**Título {titulo['numero_titulo']}**")
                        st.caption(f"Vencimento: {titulo['vencimento']}")
                    with col2:
                        st.write(f"**{formatar_valor(titulo['valor'])}**")
                    with col3:
                        st.markdown(badge_status(status_vis), unsafe_allow_html=True)

                    if titulo["status"] == "aberto":
                        dados_pdf = db.get_pdf_titulo(titulo["id"])
                        if dados_pdf and dados_pdf.get("boleto_base64"):
                            botao_download_pdf(
                                dados_pdf["boleto_base64"],
                                dados_pdf["nome_arquivo"] or f"Boleto_{titulo['numero_titulo']}.pdf",
                                "⬇️ Baixar Boleto (PDF)"
                            )


# ─── Roteamento ───────────────────────────────────────────────────────────────

if "cliente" not in st.session_state:
    fazer_login()
else:
    portal(st.session_state["cliente"])
