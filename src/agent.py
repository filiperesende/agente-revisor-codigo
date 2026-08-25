"""
Definição do agente com LangGraph.

Monta o StateGraph com os nós, as conexões entre eles e a aresta condicional
que decide se o fluxo continua após a validação. Este módulo expõe
`construir_agente()`, que devolve o grafo compilado pronto para executar.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes import (
    analisar_com_ia,
    analisar_estatico,
    consolidar_achados,
    escrever_relatorio_node,
    gerar_relatorio,
    notificar_node,
    preparar_contexto,
    priorizar_achados,
    rota_apos_consolidacao,
    rota_apos_validacao,
    validar_entrada,
)
from .state import ReviewState


def construir_agente():
    """Constrói e compila o grafo de estados do agente revisor de código.

    Topologia do fluxo:
        START
          -> validar_entrada
             --(condicional 1)--> preparar_contexto | END
          preparar_contexto
             --> analisar_com_ia     ┐  (execução paralela)
             --> analisar_estatico    ┘
          analisar_com_ia / analisar_estatico
             --> consolidar_achados   (fan-in)
             --(condicional 2)--> priorizar_achados | gerar_relatorio
          gerar_relatorio -> escrever_relatorio -> notificar -> END
    """
    grafo = StateGraph(ReviewState)

    # --- Nós (etapas principais do processo) ---
    grafo.add_node("validar_entrada", validar_entrada)
    grafo.add_node("preparar_contexto", preparar_contexto)
    grafo.add_node("analisar_com_ia", analisar_com_ia)
    grafo.add_node("analisar_estatico", analisar_estatico)
    grafo.add_node("consolidar_achados", consolidar_achados)
    grafo.add_node("priorizar_achados", priorizar_achados)
    grafo.add_node("gerar_relatorio", gerar_relatorio)
    grafo.add_node("escrever_relatorio", escrever_relatorio_node)
    grafo.add_node("notificar", notificar_node)

    # --- Conexões (fluxo do agente) ---
    grafo.add_edge(START, "validar_entrada")

    # Aresta condicional 1: seguir ou abortar após a validação.
    grafo.add_conditional_edges(
        "validar_entrada",
        rota_apos_validacao,
        {
            "continuar": "preparar_contexto",
            "encerrar": END,
        },
    )

    # Paralelização: os dois ramos de análise partem do mesmo nó e rodam juntos.
    grafo.add_edge("preparar_contexto", "analisar_com_ia")
    grafo.add_edge("preparar_contexto", "analisar_estatico")

    # Fan-in: consolidar só executa quando os dois ramos terminam.
    grafo.add_edge("analisar_com_ia", "consolidar_achados")
    grafo.add_edge("analisar_estatico", "consolidar_achados")

    # Aresta condicional 2: priorizar quando há risco alto, senão seguir direto.
    grafo.add_conditional_edges(
        "consolidar_achados",
        rota_apos_consolidacao,
        {
            "priorizar": "priorizar_achados",
            "seguir": "gerar_relatorio",
        },
    )

    grafo.add_edge("priorizar_achados", "gerar_relatorio")
    grafo.add_edge("gerar_relatorio", "escrever_relatorio")
    grafo.add_edge("escrever_relatorio", "notificar")
    grafo.add_edge("notificar", END)

    return grafo.compile()


def revisar_arquivo(caminho_arquivo: str, aprovacao_concedida: bool = False) -> ReviewState:
    """
    Executa o agente para um arquivo e devolve o estado final.

    Ponto de entrada de alto nível usado pela CLI e pelos testes. O parâmetro
    `aprovacao_concedida` permite pré-autorizar ações que exigem aprovação
    humana (ex.: notificação externa em caso de risco alto).
    """
    agente = construir_agente()
    estado_inicial: ReviewState = {
        "caminho_arquivo": caminho_arquivo,
        "aprovacao_concedida": aprovacao_concedida,
    }
    return agente.invoke(estado_inicial)
