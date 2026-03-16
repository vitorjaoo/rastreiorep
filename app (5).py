"""
app.py — Portal Unificado
Admin:   login com "admin" + senha master
Cliente: login com CNPJ + senha cadastrada
"""

import base64
import hashlib
import streamlit as st
from datetime import datetime

import db
from extrator_pdf import extrair_dados_nf, extrair_dados_boleto, pdf_para_base64

st.set_page_config(page_title="Portal do Cliente", page_icon="📦", layout="wide")

db.criar_tabelas()

def hash_senha(s): return hashlib.sha256(s.encode()).hexdigest()

def formatar_valor(v):
    if v is None: return "—"
    return f"R$ {float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")

def badge(status: str) -> str:
    mapa = {
        "ativo":     ("#dbeafe","#1e40af","Em andamento"),
        "entregue":  ("#d1fae5","#065f46","Entregue"),
        "cancelado": ("#fee2e2","#991b1b","Cancelado"),
        "pago":      ("#d1fae5","#065f46","Pago"),
        "aberto":    ("#fef3c7","#92400e","Em aberto"),
        "vencido":   ("#fee2e2","#991b1b","Vencido"),
    }
    bg, cor, texto = mapa.get(status, ("#f3f4f6","#374151", status))
    return f'<span style="background:{bg};color:{cor};padding:2px 10px;border-radius:20px;font-size:12px;font-weight:600">{texto}</span>'

def botao_pdf(pdf_base64: str, nome_arquivo: str, label: str, key: str):
    if not pdf_base64:
        st.caption("PDF não disponível")
        return
    st.download_button(label=label, data=base64.b64decode(pdf_base64),
                       file_name=nome_arquivo, mime="application/pdf",
                       use_container_width=True, key=key)

def tela_login():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""<div style="text-align:center;margin-bottom:2rem">
            <div style="font-size:40px">📦</div>
            <h2 style="margin:8px 0 4px">Portal do Cliente</h2>
            <p style="color:#6b7280;font-size:14px;margin:0">Acesse seus documentos e pedidos</p>
        </div>""", unsafe_allow_html=True)
        with st.form("form_login"):
            cnpj  = st.text_input("CNPJ ou usuário", placeholder="00.000.000/0001-00")
            senha = st.text_input("Senha", type="password")
            ok    = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if ok:
            if not cnpj or not senha:
                st.error("Preencha todos os campos."); return
            if cnpj.strip().lower() == "admin" and senha == st.secrets.get("ADMIN_SENHA","admin123"):
                st.session_state.update({"perfil":"admin","usuario":{"nome":"Administrador"}}); st.rerun(); return
            cli = db.buscar_cliente_cnpj(cnpj.strip())
            if not cli: st.error("CNPJ não encontrado."); return
            if hash_senha(senha) != cli["senha_hash"]: st.error("Senha incorreta."); return
            if not cli["ativo"]: st.error("Acesso desativado."); return
            st.session_state.update({"perfil":"cliente","usuario":cli}); st.rerun()
        st.markdown('<p style="text-align:center;font-size:12px;color:#9ca3af;margin-top:1rem">Primeiro acesso? Solicite suas credenciais ao escritório.</p>', unsafe_allow_html=True)

def interface_admin():
    with st.sidebar:
        st.markdown("### 🏢 Painel Admin")
        st.caption(datetime.now().strftime("%d/%m/%Y %H:%M"))
        st.divider()
        pag = st.radio("", ["📤 Upload","👥 Clientes","📄 Notas Fiscais","💰 Títulos"], label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.clear(); st.rerun()

    if pag == "📤 Upload":
        st.title("📤 Upload de Documentos")
        clientes = db.listar_clientes()
        if not clientes:
            st.warning("Cadastre um cliente antes de fazer upload."); st.stop()
        opcoes = {f"{c['nome']} — {c['cnpj']}": c["id"] for c in clientes}
        tab_nf, tab_bol = st.tabs(["📄 Nota Fiscal","🧾 Boleto / Título"])

        with tab_nf:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("1. PDF da NF")
                arq = st.file_uploader("Selecione", type=["pdf"], key="up_nf")
                if arq:
                    byt = arq.read()
                    st.success(f"✅ {arq.name} ({len(byt)//1024} KB)")
                    dados = extrair_dados_nf(byt, arq.name)
                    if dados["sucesso"]:
                        st.session_state.update({"nf_d":dados,"nf_b":byt,"nf_n":arq.name})
            with c2:
                st.subheader("2. Confirme e salve")
                d = st.session_state.get("nf_d", {})
                cli_sel   = st.selectbox("Cliente", list(opcoes.keys()), key="nf_cli")
                numero_nf = st.text_input("Número da NF",    value=d.get("numero_nf",""))
                valor_nf  = st.number_input("Valor (R$)",    value=float(d.get("valor",0)), min_value=0.0, format="%.2f")
                data_nf   = st.text_input("Data de emissão", value=d.get("data_emissao",""))
                status_nf = st.selectbox("Status", ["ativo","entregue","cancelado"])
                obs_nf    = st.text_input("Observação (visível ao cliente)", placeholder="Ex: Saiu para entrega")
                st.divider()
                st.subheader("Rastreio (opcional)")
                cod_rast = st.text_input("Código de rastreio")
                transp   = st.text_input("Transportadora")
                if st.button("💾 Salvar NF", type="primary", use_container_width=True):
                    byt = st.session_state.get("nf_b")
                    if not byt: st.error("Faça upload do PDF primeiro.")
                    elif not numero_nf: st.error("Informe o número da NF.")
                    else:
                        db.inserir_nf(opcoes[cli_sel], numero_nf, valor_nf, data_nf,
                                      pdf_para_base64(byt), st.session_state.get("nf_n","nf.pdf"),
                                      cod_rast, transp, status_nf, obs_nf)
                        st.success(f"✅ NF {numero_nf} salva!")
                        for k in ["nf_d","nf_b","nf_n"]: st.session_state.pop(k,None)
                        st.rerun()

        with tab_bol:
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("1. PDF do Boleto")
                arq_b = st.file_uploader("Selecione", type=["pdf"], key="up_bol")
                if arq_b:
                    byt_b = arq_b.read()
                    st.success(f"✅ {arq_b.name} ({len(byt_b)//1024} KB)")
                    dados_b = extrair_dados_boleto(byt_b, arq_b.name)
                    if dados_b["sucesso"]:
                        st.session_state.update({"bol_d":dados_b,"bol_b":byt_b,"bol_n":arq_b.name})
            with c2:
                st.subheader("2. Confirme e salve")
                db_ = st.session_state.get("bol_d", {})
                cli_sel_b     = st.selectbox("Cliente", list(opcoes.keys()), key="bol_cli")
                numero_titulo = st.text_input("Número do título", value=db_.get("numero_titulo",""))
                valor_bol     = st.number_input("Valor (R$)", value=float(db_.get("valor",0)), min_value=0.0, format="%.2f", key="vb")
                vencimento    = st.text_input("Vencimento", value=db_.get("vencimento",""))
                nfs_cli = db.listar_nfs(opcoes.get(cli_sel_b, 0))
                op_nf = {"(nenhuma)": None}
                op_nf.update({f"NF {n['numero_nf']} — {n['data_emissao']}": n["id"] for n in nfs_cli})
                nf_vinc = st.selectbox("Vincular à NF", list(op_nf.keys()))
                if st.button("💾 Salvar Título", type="primary", use_container_width=True):
                    byt_b = st.session_state.get("bol_b")
                    if not byt_b: st.error("Faça upload do PDF primeiro.")
                    elif not numero_titulo or not vencimento: st.error("Preencha número e vencimento.")
                    else:
                        db.inserir_titulo(opcoes[cli_sel_b], numero_titulo, valor_bol, vencimento,
                                          pdf_para_base64(byt_b), st.session_state.get("bol_n","boleto.pdf"), op_nf[nf_vinc])
                        st.success(f"✅ Título {numero_titulo} salvo!")
                        for k in ["bol_d","bol_b","bol_n"]: st.session_state.pop(k,None)
                        st.rerun()

    elif pag == "👥 Clientes":
        st.title("👥 Clientes")
        with st.expander("➕ Novo cliente"):
            with st.form("form_cli"):
                c1, c2 = st.columns(2)
                with c1:
                    nome_c = st.text_input("Nome *"); cnpj_c = st.text_input("CNPJ *")
                with c2:
                    email_c = st.text_input("E-mail"); wpp_c = st.text_input("WhatsApp")
                senha_c = st.text_input("Senha de acesso *", type="password")
                if st.form_submit_button("Cadastrar", type="primary"):
                    if not nome_c or not cnpj_c or not senha_c: st.error("Nome, CNPJ e senha são obrigatórios.")
                    else:
                        try:
                            db.criar_cliente(nome_c, cnpj_c, email_c, wpp_c, hash_senha(senha_c))
                            st.success(f"✅ {nome_c} cadastrado!"); st.rerun()
                        except Exception as e: st.error(f"Erro: {e}")
        clientes = db.listar_clientes()
        if clientes:
            st.dataframe([{"Nome": c["nome"], "CNPJ": c["cnpj"], "Email": c["email"] or "—",
                           "WhatsApp": c["whatsapp"] or "—",
                           "Status": "✅ Ativo" if c["ativo"] else "❌ Inativo"} for c in clientes],
                         use_container_width=True, hide_index=True)
        else: st.info("Nenhum cliente cadastrado.")

    elif pag == "📄 Notas Fiscais":
        st.title("📄 Notas Fiscais")
        nfs = db.listar_todas_nfs()
        if nfs:
            c1, c2 = st.columns(2)
            with c1: filtro_cli = st.selectbox("Cliente", ["Todos"] + list({n["cliente"] for n in nfs}))
            with c2: filtro_st  = st.selectbox("Status", ["Todos","ativo","entregue","cancelado"])
            nfs_f = [n for n in nfs if (filtro_cli=="Todos" or n["cliente"]==filtro_cli)
                                    and (filtro_st=="Todos" or n["status"]==filtro_st)]
            st.subheader("Editar status / rastreio")
            for row in nfs_f:
                with st.expander(f"NF {row['numero_nf']} — {row['cliente']} — {formatar_valor(row['valor'])}"):
                    c1,c2,c3 = st.columns([2,2,1])
                    cod = c1.text_input("Código rastreio", value=row.get("codigo_rastreio") or "", key=f"cod_{row['id']}")
                    tra = c2.text_input("Transportadora",  value=row.get("transportadora")  or "", key=f"tra_{row['id']}")
                    c3.write(""); c3.write("")
                    if c3.button("Salvar", key=f"sv_{row['id']}"):
                        db.atualizar_rastreio(row["id"], cod, tra); st.success("Salvo!"); st.rerun()
                    c4, c5 = st.columns([2,3])
                    status_opts = ["ativo","entregue","cancelado"]
                    idx = status_opts.index(row["status"]) if row["status"] in status_opts else 0
                    novo_st  = c4.selectbox("Status", status_opts, index=idx, key=f"st_{row['id']}")
                    nova_obs = c5.text_input("Observação", value=row.get("observacao") or "", key=f"ob_{row['id']}")
                    if st.button("Atualizar status", key=f"ust_{row['id']}"):
                        db.atualizar_status_nf(row["id"], novo_st, nova_obs); st.success("Atualizado!"); st.rerun()
            st.divider()
            st.dataframe([{"Cliente": n["cliente"], "NF": n["numero_nf"],
                           "Valor": formatar_valor(n["valor"]), "Emissão": n["data_emissao"],
                           "Status": n["status"], "Obs": n.get("observacao") or "—"} for n in nfs_f],
                         use_container_width=True, hide_index=True)
        else: st.info("Nenhuma NF cadastrada.")

    elif pag == "💰 Títulos":
        st.title("💰 Títulos Financeiros")
        titulos = db.listar_todos_titulos()
        if titulos:
            em_aberto = [t for t in titulos if t["status"]=="aberto"]
            pagos_l   = [t for t in titulos if t["status"]=="pago"]
            c1,c2,c3  = st.columns(3)
            c1.metric("Em aberto", formatar_valor(sum(float(t["valor"] or 0) for t in em_aberto)))
            c2.metric("Recebido",  formatar_valor(sum(float(t["valor"] or 0) for t in pagos_l)))
            c3.metric("Títulos abertos", len(em_aberto))
            st.divider()
            for t in em_aberto:
                c1,c2,c3,c4 = st.columns([3,2,2,1])
                c1.write(f"**{t['cliente']}** — {t['numero_titulo']}")
                c2.write(formatar_valor(t["valor"])); c3.write(f"📅 {t['vencimento']}")
                if c4.button("✅ Pago", key=f"pago_{t['id']}"):
                    db.marcar_titulo_pago(t["id"]); st.success("Pago!"); st.rerun()
            st.divider()
            st.dataframe([{"Cliente": t["cliente"], "Título": t["numero_titulo"],
                           "Valor": formatar_valor(t["valor"]), "Vencimento": t["vencimento"],
                           "Status": t["status"]} for t in titulos],
                         use_container_width=True, hide_index=True)
        else: st.info("Nenhum título cadastrado.")

def interface_cliente(cliente: dict):
    with st.sidebar:
        st.markdown(f"### 👤 {cliente['nome'].split()[0]}")
        st.caption(f"CNPJ: {cliente['cnpj']}")
        st.divider()
        pag = st.radio("", ["📄 Notas Fiscais","📦 Rastreio","💰 Financeiro"], label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.clear(); st.rerun()

    if pag == "📄 Notas Fiscais":
        st.title("📄 Suas Notas Fiscais")
        nfs = db.listar_nfs(cliente["id"])
        if not nfs:
            st.info("Nenhuma nota fiscal disponível no momento.")
        else:
            c1,c2,c3 = st.columns(3)
            c1.metric("Total de NFs", len(nfs))
            c2.metric("Com rastreio", sum(1 for n in nfs if n.get("codigo_rastreio")))
            c3.metric("Valor total",  formatar_valor(sum(float(n["valor"] or 0) for n in nfs)))
            st.divider()
            for nf in nfs:
                with st.container(border=True):
                    c1,c2,c3 = st.columns([3,2,2])
                    with c1:
                        st.write(f"**NF {nf['numero_nf']}**")
                        st.caption(f"Emitida em {nf['data_emissao']}")
                    c2.write(f"**{formatar_valor(nf['valor'])}**")
                    c3.markdown(badge(nf.get("status","ativo")), unsafe_allow_html=True)
                    if nf.get("observacao"):
                        st.info(f"💬 {nf['observacao']}")
                    if nf.get("codigo_rastreio"):
                        st.caption(f"📦 {nf.get('transportadora','') or 'Transportadora'} · `{nf['codigo_rastreio']}`")
                    dados_pdf = db.get_pdf_nf(nf["id"])
                    if dados_pdf and dados_pdf.get("pdf_base64"):
                        botao_pdf(dados_pdf["pdf_base64"],
                                  dados_pdf["nome_arquivo"] or f"NF_{nf['numero_nf']}.pdf",
                                  "⬇️ Baixar NF (PDF)", key=f"dl_nf_{nf['id']}")

    elif pag == "📦 Rastreio":
        st.title("📦 Rastreio de Entregas")
        nfs = [n for n in db.listar_nfs(cliente["id"]) if n.get("codigo_rastreio")]
        if not nfs:
            st.info("Nenhuma remessa com código de rastreio disponível.")
        else:
            for nf in nfs:
                with st.container(border=True):
                    c1,c2 = st.columns([3,1])
                    with c1:
                        st.write(f"**NF {nf['numero_nf']}** — {nf.get('transportadora','')}")
                        st.caption(f"Emitida em {nf['data_emissao']}")
                    c2.markdown(badge(nf.get("status","ativo")), unsafe_allow_html=True)
                    st.code(nf["codigo_rastreio"], language=None)
                    transp = (nf.get("transportadora") or "").lower()
                    cod    = nf["codigo_rastreio"]
                    if "correios" in transp:
                        st.link_button("🔗 Rastrear nos Correios","https://rastreamento.correios.com.br", use_container_width=True)
                    elif "jadlog" in transp:
                        st.link_button("🔗 Rastrear na Jadlog", f"https://www.jadlog.com.br/jadlog/tracking.jad?cte={cod}", use_container_width=True)
                    else:
                        st.link_button("🔍 Buscar rastreio", f"https://www.google.com/search?q=rastrear+{cod}", use_container_width=True)

    elif pag == "💰 Financeiro":
        st.title("💰 Títulos Financeiros")
        titulos = db.listar_titulos(cliente["id"])
        if not titulos:
            st.info("Nenhum título financeiro disponível.")
        else:
            hoje = datetime.now().strftime("%Y-%m-%d")
            em_aberto = [t for t in titulos if t["status"]=="aberto"]
            pagos_l   = [t for t in titulos if t["status"]=="pago"]
            c1,c2,c3  = st.columns(3)
            c1.metric("Em aberto", formatar_valor(sum(float(t["valor"] or 0) for t in em_aberto)))
            c2.metric("Quitado",   formatar_valor(sum(float(t["valor"] or 0) for t in pagos_l)))
            c3.metric("Títulos abertos", len(em_aberto))
            st.divider()
            for t in titulos:
                sv = t["status"]
                if sv == "aberto":
                    try:
                        p = t["vencimento"].split("/")
                        if f"{p[2]}-{p[1]}-{p[0]}" < hoje: sv = "vencido"
                    except Exception: pass
                with st.container(border=True):
                    c1,c2,c3 = st.columns([3,2,2])
                    with c1:
                        st.write(f"**Título {t['numero_titulo']}**")
                        st.caption(f"Vencimento: {t['vencimento']}")
                    c2.write(f"**{formatar_valor(t['valor'])}**")
                    c3.markdown(badge(sv), unsafe_allow_html=True)
                    if t["status"] == "aberto":
                        dados_pdf = db.get_pdf_titulo(t["id"])
                        if dados_pdf and dados_pdf.get("boleto_base64"):
                            botao_pdf(dados_pdf["boleto_base64"],
                                      dados_pdf["nome_arquivo"] or f"Boleto_{t['numero_titulo']}.pdf",
                                      "⬇️ Baixar Boleto (PDF)", key=f"dl_bol_{t['id']}")

perfil = st.session_state.get("perfil")
if not perfil: tela_login()
elif perfil == "admin": interface_admin()
elif perfil == "cliente": interface_cliente(st.session_state["usuario"])
