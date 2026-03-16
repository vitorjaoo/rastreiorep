"""
app_admin.py — Painel do escritório
Acesso: streamlit run app_admin.py
"""

import base64
import hashlib
import streamlit as st
import pandas as pd
from datetime import datetime

import db
from extrator_pdf import (
    extrair_dados_nf,
    extrair_dados_boleto,
    pdf_para_base64,
)

# ─── Config ───────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Admin — Portal Escritório",
    page_icon="🏢",
    layout="wide",
)

# ─── Auth simples ─────────────────────────────────────────────────────────────

def check_admin():
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        st.title("🏢 Painel Administrativo")
        senha = st.text_input("Senha admin", type="password")
        if st.button("Entrar"):
            if senha == st.secrets.get("ADMIN_SENHA", ""):
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Senha incorreta")
        st.stop()

check_admin()

# ─── Init banco ───────────────────────────────────────────────────────────────

db.criar_tabelas()

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏢 Admin")
    st.caption(f"Hoje: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    st.divider()
    pagina = st.radio(
        "Menu",
        ["📤 Upload Documentos", "👥 Clientes", "📄 Notas Fiscais", "💰 Títulos"],
        label_visibility="collapsed"
    )
    st.divider()
    if st.button("🚪 Sair"):
        st.session_state.admin_ok = False
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# UPLOAD DOCUMENTOS
# ═══════════════════════════════════════════════════════════════════════════════

if pagina == "📤 Upload Documentos":
    st.title("📤 Upload de Documentos")
    st.caption("A IA lê o PDF e preenche os campos automaticamente.")

    clientes = db.listar_clientes()
    if not clientes:
        st.warning("Cadastre pelo menos um cliente antes de fazer upload.")
        st.stop()

    opcoes_clientes = {f"{c['nome']} — {c['cnpj']}": c["id"] for c in clientes}

    tab_nf, tab_boleto = st.tabs(["📄 Nota Fiscal", "🧾 Boleto / Título"])

    # ── Upload NF ──
    with tab_nf:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("1. Selecione o PDF")
            arquivo = st.file_uploader("PDF da Nota Fiscal", type=["pdf"], key="upload_nf")

            if arquivo:
                bytes_pdf = arquivo.read()
                st.success(f"✅ {arquivo.name} ({len(bytes_pdf)//1024} KB)")

                with st.spinner("🤖 Claude lendo o PDF..."):
                    dados = extrair_dados_nf(bytes_pdf, arquivo.name)

                if dados["sucesso"]:
                    st.success("Dados extraídos automaticamente!")
                    st.session_state["nf_dados"] = dados
                    st.session_state["nf_bytes"] = bytes_pdf
                    st.session_state["nf_nome"] = arquivo.name
                else:
                    st.error(f"Erro na extração: {dados.get('erro')}")
                    st.session_state["nf_dados"] = {}

        with col2:
            st.subheader("2. Confirme os dados")

            dados = st.session_state.get("nf_dados", {})

            cliente_sel = st.selectbox("Cliente", list(opcoes_clientes.keys()), key="nf_cliente")

            numero_nf    = st.text_input("Número da NF",   value=dados.get("numero_nf", ""))
            valor        = st.number_input("Valor (R$)",   value=float(dados.get("valor", 0)), min_value=0.0, format="%.2f")
            data_emissao = st.text_input("Data de emissão", value=dados.get("data_emissao", ""))

            st.divider()
            st.subheader("3. Rastreio (opcional)")
            codigo_rastreio = st.text_input("Código de rastreio")
            transportadora  = st.text_input("Transportadora")

            if st.button("💾 Salvar NF", type="primary", use_container_width=True):
                bytes_pdf = st.session_state.get("nf_bytes")
                nome_arq  = st.session_state.get("nf_nome", "nf.pdf")
                if not bytes_pdf:
                    st.error("Faça o upload do PDF primeiro.")
                elif not numero_nf:
                    st.error("Informe o número da NF.")
                else:
                    cliente_id = opcoes_clientes[cliente_sel]
                    pdf_b64    = pdf_para_base64(bytes_pdf)
                    db.inserir_nf(
                        cliente_id, numero_nf, valor, data_emissao,
                        pdf_b64, nome_arq, codigo_rastreio, transportadora
                    )
                    st.success(f"✅ NF {numero_nf} salva com sucesso!")
                    st.session_state.pop("nf_dados", None)
                    st.session_state.pop("nf_bytes", None)
                    st.rerun()

    # ── Upload Boleto ──
    with tab_boleto:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("1. Selecione o PDF")
            arquivo_b = st.file_uploader("PDF do Boleto/Título", type=["pdf"], key="upload_boleto")

            if arquivo_b:
                bytes_pdf_b = arquivo_b.read()
                st.success(f"✅ {arquivo_b.name} ({len(bytes_pdf_b)//1024} KB)")

                with st.spinner("🤖 Claude lendo o boleto..."):
                    dados_b = extrair_dados_boleto(bytes_pdf_b, arquivo_b.name)

                if dados_b["sucesso"]:
                    st.success("Dados extraídos automaticamente!")
                    st.session_state["bol_dados"] = dados_b
                    st.session_state["bol_bytes"] = bytes_pdf_b
                    st.session_state["bol_nome"]  = arquivo_b.name
                else:
                    st.error(f"Erro: {dados_b.get('erro')}")
                    st.session_state["bol_dados"] = {}

        with col2:
            st.subheader("2. Confirme os dados")

            dados_b = st.session_state.get("bol_dados", {})

            cliente_sel_b  = st.selectbox("Cliente", list(opcoes_clientes.keys()), key="bol_cliente")
            numero_titulo  = st.text_input("Número do título", value=dados_b.get("numero_titulo", ""))
            valor_b        = st.number_input("Valor (R$)",     value=float(dados_b.get("valor", 0)), min_value=0.0, format="%.2f", key="val_bol")
            vencimento     = st.text_input("Vencimento",       value=dados_b.get("vencimento", ""))

            # Vincular a uma NF
            nfs_cliente_id = opcoes_clientes.get(cliente_sel_b)
            nfs_disponiveis = db.listar_nfs(nfs_cliente_id) if nfs_cliente_id else []
            opcoes_nf = {"(nenhuma)": None}
            opcoes_nf.update({f"NF {n['numero_nf']} — {n['data_emissao']}": n["id"] for n in nfs_disponiveis})
            nf_vinculada = st.selectbox("Vincular à NF", list(opcoes_nf.keys()))

            if st.button("💾 Salvar Título", type="primary", use_container_width=True):
                bytes_pdf_b = st.session_state.get("bol_bytes")
                nome_arq_b  = st.session_state.get("bol_nome", "boleto.pdf")
                if not bytes_pdf_b:
                    st.error("Faça o upload do PDF primeiro.")
                elif not numero_titulo:
                    st.error("Informe o número do título.")
                elif not vencimento:
                    st.error("Informe a data de vencimento.")
                else:
                    cliente_id_b = opcoes_clientes[cliente_sel_b]
                    pdf_b64_b    = pdf_para_base64(bytes_pdf_b)
                    nf_id        = opcoes_nf[nf_vinculada]
                    db.inserir_titulo(
                        cliente_id_b, numero_titulo, valor_b,
                        vencimento, pdf_b64_b, nome_arq_b, nf_id
                    )
                    st.success(f"✅ Título {numero_titulo} salvo!")
                    st.session_state.pop("bol_dados", None)
                    st.session_state.pop("bol_bytes", None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ═══════════════════════════════════════════════════════════════════════════════

elif pagina == "👥 Clientes":
    st.title("👥 Clientes")

    with st.expander("➕ Cadastrar novo cliente"):
        with st.form("form_cliente"):
            col1, col2 = st.columns(2)
            with col1:
                nome      = st.text_input("Nome da empresa *")
                cnpj      = st.text_input("CNPJ *")
            with col2:
                email     = st.text_input("E-mail")
                whatsapp  = st.text_input("WhatsApp (com DDD)")
            senha     = st.text_input("Senha de acesso ao portal *", type="password")
            submitted = st.form_submit_button("Cadastrar", type="primary")

            if submitted:
                if not nome or not cnpj or not senha:
                    st.error("Nome, CNPJ e senha são obrigatórios.")
                else:
                    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
                    try:
                        db.criar_cliente(nome, cnpj, email, whatsapp, senha_hash)
                        st.success(f"✅ Cliente {nome} cadastrado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro: {e} — CNPJ já cadastrado?")

    clientes = db.listar_clientes()
    if clientes:
        df = pd.DataFrame(clientes)
        df["ativo"] = df["ativo"].map({1: "✅ Ativo", 0: "❌ Inativo"})
        st.dataframe(
            df[["nome", "cnpj", "email", "whatsapp", "ativo"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum cliente cadastrado ainda.")


# ═══════════════════════════════════════════════════════════════════════════════
# NOTAS FISCAIS
# ═══════════════════════════════════════════════════════════════════════════════

elif pagina == "📄 Notas Fiscais":
    st.title("📄 Notas Fiscais")

    nfs = db.listar_todas_nfs()
    if nfs:
        df = pd.DataFrame(nfs)

        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            filtro_cliente = st.selectbox("Filtrar cliente", ["Todos"] + df["cliente"].unique().tolist())
        with col2:
            filtro_status = st.selectbox("Status", ["Todos", "ativo", "cancelado"])

        if filtro_cliente != "Todos":
            df = df[df["cliente"] == filtro_cliente]
        if filtro_status != "Todos":
            df = df[df["status"] == filtro_status]

        # Editar rastreio inline
        st.subheader("Rastreio de entregas")
        for _, row in df.iterrows():
            with st.expander(f"NF {row['numero_nf']} — {row['cliente']} — R$ {row['valor']:,.2f}"):
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    cod = st.text_input("Código rastreio", value=row["codigo_rastreio"] or "", key=f"cod_{row['id']}")
                with col2:
                    transp = st.text_input("Transportadora", value=row["transportadora"] or "", key=f"tr_{row['id']}")
                with col3:
                    st.write("")
                    st.write("")
                    if st.button("Salvar", key=f"sv_{row['id']}"):
                        db.atualizar_rastreio(row["id"], cod, transp)
                        st.success("Salvo!")
                        st.rerun()

        st.divider()
        st.subheader("Todas as NFs")
        st.dataframe(
            df[["cliente", "numero_nf", "valor", "data_emissao", "status", "transportadora"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhuma NF cadastrada ainda.")


# ═══════════════════════════════════════════════════════════════════════════════
# TÍTULOS
# ═══════════════════════════════════════════════════════════════════════════════

elif pagina == "💰 Títulos":
    st.title("💰 Títulos Financeiros")

    titulos = db.listar_todos_titulos()
    if titulos:
        df = pd.DataFrame(titulos)

        # Métricas rápidas
        em_aberto = df[df["status"] == "aberto"]["valor"].sum()
        pagos      = df[df["status"] == "pago"]["valor"].sum()
        vencidos   = df[(df["status"] == "aberto") & (df["vencimento"] < datetime.now().strftime("%d/%m/%Y"))]["valor"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("Em aberto", f"R$ {em_aberto:,.2f}")
        col2.metric("Recebido", f"R$ {pagos:,.2f}")
        col3.metric("Vencidos", f"R$ {vencidos:,.2f}")

        st.divider()

        # Marcar como pago
        st.subheader("Gerenciar títulos")
        for _, row in df[df["status"] == "aberto"].iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            col1.write(f"**{row['cliente']}** — {row['numero_titulo']}")
            col2.write(f"R$ {row['valor']:,.2f}")
            col3.write(f"📅 {row['vencimento']}")
            with col4:
                if st.button("✅ Pago", key=f"pago_{row['id']}"):
                    db.marcar_titulo_pago(row["id"])
                    st.success("Marcado como pago!")
                    st.rerun()

        st.divider()
        st.subheader("Todos os títulos")
        st.dataframe(
            df[["cliente", "numero_titulo", "valor", "vencimento", "status"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum título cadastrado ainda.")
