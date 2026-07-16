"""
Validações básicas de entrada, saída e uso da ferramenta.

Garante que o agente não processe dados malformados e que a saída do LLM
esteja no formato esperado antes de gerar o relatório final.
"""

from __future__ import annotations

from .state import Achado

SEVERIDADES_VALIDAS = {"alta", "media", "baixa"}
CHAVES_ACHADO = {"severidade", "categoria", "linha", "descricao", "sugestao"}


def validar_caminho_entrada(caminho: str) -> tuple[bool, str]:
    """Valida a entrada do usuário (o caminho do arquivo) antes de ler."""
    if not caminho or not isinstance(caminho, str):
        return False, "Nenhum caminho de arquivo foi informado."
    if caminho.strip() == "":
        return False, "O caminho do arquivo está em branco."
    return True, ""


def normalizar_achados(brutos: list) -> list[Achado]:
    """
    Valida e normaliza a saída do LLM.

    Descarta itens fora do formato e preenche chaves ausentes, evitando que
    um retorno malformado do modelo quebre a geração do relatório.
    """
    achados: list[Achado] = []
    if not isinstance(brutos, list):
        return achados

    for item in brutos:
        if not isinstance(item, dict):
            continue

        severidade = str(item.get("severidade", "baixa")).lower().strip()
        if severidade not in SEVERIDADES_VALIDAS:
            severidade = "baixa"

        achados.append({
            "severidade": severidade,
            "categoria": str(item.get("categoria", "geral")).strip() or "geral",
            "linha": str(item.get("linha", "N/A")).strip() or "N/A",
            "descricao": str(item.get("descricao", "")).strip(),
            "sugestao": str(item.get("sugestao", "")).strip(),
        })

    return achados
