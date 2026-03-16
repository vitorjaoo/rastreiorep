"""
extrator_pdf.py — Claude API lê o PDF e extrai os dados automaticamente
Suporta NF-e e boletos bancários
"""

import base64
import json
import re
import anthropic
import streamlit as st


def _get_client():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


def pdf_para_base64(arquivo_bytes: bytes) -> str:
    """Converte bytes do PDF em base64 para armazenar no banco"""
    return base64.b64encode(arquivo_bytes).decode("utf-8")


def extrair_dados_nf(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    """
    Envia o PDF da NF para Claude e retorna os dados extraídos.
    Retorna dict com: numero_nf, valor, data_emissao, cnpj_destinatario, nome_destinatario
    """
    client = _get_client()
    pdf_b64 = base64.standard_b64encode(arquivo_bytes).decode("utf-8")

    prompt = """Você é um extrator de dados de Notas Fiscais brasileiras.
Analise este PDF e extraia os seguintes dados em formato JSON puro (sem markdown, sem explicações):

{
  "numero_nf": "número da NF ou NF-e (ex: 000123)",
  "serie": "série da NF (ex: 001)",
  "valor_total": 0.00,
  "data_emissao": "DD/MM/AAAA",
  "cnpj_destinatario": "00.000.000/0001-00",
  "nome_destinatario": "Nome da empresa destinatária",
  "chave_acesso": "chave de acesso de 44 dígitos se disponível"
}

Se algum campo não for encontrado, use null.
Responda APENAS com o JSON, sem texto adicional."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )

        raw = response.content[0].text.strip()
        # Remove possíveis ```json ``` caso o modelo adicione
        raw = re.sub(r"```json|```", "", raw).strip()
        dados = json.loads(raw)

        return {
            "numero_nf":    dados.get("numero_nf") or "",
            "valor":        float(dados.get("valor_total") or 0),
            "data_emissao": dados.get("data_emissao") or "",
            "cnpj":         dados.get("cnpj_destinatario") or "",
            "nome":         dados.get("nome_destinatario") or "",
            "chave":        dados.get("chave_acesso") or "",
            "sucesso":      True,
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


def extrair_dados_boleto(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    """
    Envia o PDF do boleto para Claude e retorna os dados extraídos.
    Retorna dict com: numero_titulo, valor, vencimento, cnpj_pagador
    """
    client = _get_client()
    pdf_b64 = base64.standard_b64encode(arquivo_bytes).decode("utf-8")

    prompt = """Você é um extrator de dados de boletos bancários brasileiros.
Analise este PDF e extraia os seguintes dados em formato JSON puro (sem markdown, sem explicações):

{
  "numero_titulo": "número do documento ou nosso número",
  "valor": 0.00,
  "vencimento": "DD/MM/AAAA",
  "cnpj_pagador": "CNPJ ou CPF do pagador",
  "nome_pagador": "nome do pagador",
  "linha_digitavel": "linha digitável do boleto se disponível"
}

Se algum campo não for encontrado, use null.
Responda APENAS com o JSON, sem texto adicional."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        dados = json.loads(raw)

        return {
            "numero_titulo": dados.get("numero_titulo") or "",
            "valor":         float(dados.get("valor") or 0),
            "vencimento":    dados.get("vencimento") or "",
            "cnpj":          dados.get("cnpj_pagador") or "",
            "nome":          dados.get("nome_pagador") or "",
            "sucesso":       True,
        }

    except Exception as e:
        return {"sucesso": False, "erro": str(e)}
