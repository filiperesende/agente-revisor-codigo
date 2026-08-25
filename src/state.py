"""
Estado compartilhado do agente (memória de curto prazo da execução).

O LangGraph passa este dicionário entre todos os nós do grafo. Cada nó lê e
escreve campos aqui, funcionando como a "memória" da execução: o que foi lido,
o que já foi analisado e o que ainda falta produzir.
"""

from __future__ import annotations

from typing import Annotated, TypedDict
from operator import add


class Achado(TypedDict):
    """Um problema encontrado no código pelo agente."""

    severidade: str  # "alta" | "media" | "baixa"
    categoria: str   # ex.: "bug", "seguranca", "estilo", "performance"
    linha: str       # linha ou trecho aproximado (string para tolerar "N/A")
    descricao: str   # explicação do problema
    sugestao: str    # como corrigir


class ReviewState(TypedDict, total=False):
    """
    Estado que trafega entre os nós do grafo.

    Campos preenchidos ao longo do fluxo:
      - entrada do usuário: caminho do arquivo a revisar
      - contexto/memória: metadados calculados (linguagem, nº de linhas, tamanho)
      - resultado da análise: lista de achados estruturados
      - saída final: relatório em Markdown e caminho do arquivo gravado
    """

    # --- Entrada ---
    caminho_arquivo: str

    # --- Preenchido pela leitura/validação ---
    codigo_fonte: str
    valido: bool

    # --- Contexto / memória da execução ---
    contexto: dict

    # --- Resultado dos ramos paralelos de análise ---
    # Cada campo é escrito por um único nó (single-writer), evitando conflito
    # de atualização concorrente durante a paralelização do grafo.
    achados_ia: list[Achado]        # produzidos pelo LLM (Gemini ou mock)
    achados_estatica: list[Achado]  # produzidos pela análise determinística
    motor_analise: str              # motor efetivamente usado pela IA

    # --- Resultado consolidado (fan-in) ---
    achados: list[Achado]

    # --- Saída final ---
    relatorio_markdown: str
    caminho_relatorio: str

    # --- Integração externa (tool de notificação via webhook) ---
    notificacao: dict

    # --- Diagnóstico (lista acumulável com reducer `add`) ---
    logs: Annotated[list[str], add]
    erros: Annotated[list[str], add]
