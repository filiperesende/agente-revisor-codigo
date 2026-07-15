"""
Definição do agente com LangGraph.

Monta o StateGraph com os nós, as conexões entre eles e a aresta condicional
que decide se o fluxo continua após a validação. Este módulo expõe
`construir_agente()`, que devolve o grafo compilado pronto para executar.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    analisar_codigo,
    escrever_relatorio_node,
    gerar_relatorio,
    preparar_contexto,
    rota_apos_validacao,
    validar_entrada,
)
from .state import ReviewState


def construir_agente():
    """Constrói e compila o grafo de estados do agente revisor de código."""
    grafo = StateGraph(ReviewState)

    # --- Nós (etapas principais do processo) ---
    grafo.add_node("validar_entrada", validar_entrada)
    grafo.add_node("preparar_contexto", preparar_contexto)
    grafo.add_node("analisar_codigo", analisar_codigo)
    grafo.add_node("gerar_relatorio", gerar_relatorio)
    grafo.add_node("escrever_relatorio", escrever_relatorio_node)

    # --- Conexões (fluxo do agente) ---
    grafo.add_edge(START, "validar_entrada")

    # Aresta condicional: tomada de decisão após a validação.
    grafo.add_conditional_edges(
        "validar_entrada",
        rota_apos_validacao,
        {
            "continuar": "preparar_contexto",
            "encerrar": END,
        },
    )

    grafo.add_edge("preparar_contexto", "analisar_codigo")
    grafo.add_edge("analisar_codigo", "gerar_relatorio")
    grafo.add_edge("gerar_relatorio", "escrever_relatorio")
    grafo.add_edge("escrever_relatorio", END)

    return grafo.compile()


def revisar_arquivo(caminho_arquivo: str) -> ReviewState:
    """
    Executa o agente para um arquivo e devolve o estado final.

    Ponto de entrada de alto nível usado pela CLI e pelos testes.
    """
    agente = construir_agente()
    estado_inicial: ReviewState = {"caminho_arquivo": caminho_arquivo}
    return agente.invoke(estado_inicial)
