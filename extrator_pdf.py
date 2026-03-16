import base64

def pdf_para_base64(arquivo_bytes: bytes) -> str:
    return base64.b64encode(arquivo_bytes).decode("utf-8")

def extrair_dados_nf(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    return {
        "numero_nf": "", "valor": 0.0, "data_emissao": "",
        "cnpj": "", "nome": "", "chave": "", "sucesso": True,
    }

def extrair_dados_boleto(arquivo_bytes: bytes, nome_arquivo: str) -> dict:
    return {
        "numero_titulo": "", "valor": 0.0, "vencimento": "",
        "cnpj": "", "nome": "", "sucesso": True,
    }
