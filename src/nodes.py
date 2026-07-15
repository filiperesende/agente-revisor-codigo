"""
Nós do grafo do agente.

Cada função abaixo é um nó do LangGraph. Recebe o estado atual e retorna um
dicionário com os campos que devem ser atualizados no estado compartilhado.

Fluxo:
    validar_entrada -> preparar_contexto -> analisar_codigo
                    -> gerar_relatorio -> escrever_relatorio
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import llm
from .state import ReviewState
from .tools import (
    FerramentaError,
    detectar_linguagem,
    escrever_relatorio,
    ler_arquivo_codigo,
)
from .validation import normalizar_achados, validar_caminho_entrada


def validar_entrada(state: ReviewState) -> dict:
    """
    Nó 1 — Validação + leitura do arquivo (uso da ferramenta de leitura).

    Valida o caminho recebido, lê o arquivo pela ferramenta controlada e
    marca o estado como válido/invalido. É o nó que decide se o fluxo segue.
    """
    caminho = state.get("caminho_arquivo", "")

    ok, motivo = validar_caminho_entrada(caminho)
    if not ok:
        return {"valido": False, "erros": [motivo], "logs": ["[validar_entrada] entrada inválida"]}

    try:
        codigo = ler_arquivo_codigo(caminho)
    except FerramentaError as exc:
        return {
            "valido": False,
            "erros": [str(exc)],
            "logs": [f"[validar_entrada] falha ao ler arquivo: {exc}"],
        }

    return {
        "valido": True,
        "codigo_fonte": codigo,
        "logs": [f"[validar_entrada] arquivo lido com sucesso ({len(codigo)} caracteres)"],
    }


def preparar_contexto(state: ReviewState) -> dict:
    """
    Nó 2 — Preparação do contexto (memória da execução).

    Calcula metadados do arquivo (linguagem, nº de linhas, tamanho) e guarda
    no estado. Esse contexto acompanha os próximos nós e alimenta o prompt.
    """
    codigo = state["codigo_fonte"]
    caminho = state["caminho_arquivo"]

    contexto = {
        "caminho_arquivo": caminho,
        "linguagem": detectar_linguagem(caminho),
        "total_linhas": len(codigo.splitlines()),
        "total_caracteres": len(codigo),
        "iniciado_em": datetime.now().isoformat(timespec="seconds"),
    }
    return {
        "contexto": contexto,
        "logs": [f"[preparar_contexto] linguagem={contexto['linguagem']}, "
                 f"linhas={contexto['total_linhas']}"],
    }


def analisar_codigo(state: ReviewState) -> dict:
    """
    Nó 3 — Análise pelo agente (chamada ao LLM Gemini ou mock).

    Envia o código e o contexto ao motor de análise e valida/normaliza a
    saída antes de guardá-la no estado.
    """
    codigo = state["codigo_fonte"]
    contexto = dict(state.get("contexto", {}))

    brutos, motor = llm.analisar_codigo(codigo, contexto)
    achados = normalizar_achados(brutos)

    # Atualiza a memória com o resultado da análise.
    contexto["motor_analise"] = motor
    contexto["total_achados"] = len(achados)

    return {
        "achados": achados,
        "contexto": contexto,
        "logs": [f"[analisar_codigo] motor={motor}, achados={len(achados)}"],
    }


def gerar_relatorio(state: ReviewState) -> dict:
    """
    Nó 4 — Geração da resposta final estruturada (relatório em Markdown).
    """
    contexto = state.get("contexto", {})
    achados = state.get("achados", [])

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    achados_ordenados = sorted(achados, key=lambda a: ordem.get(a["severidade"], 3))

    total = len(achados_ordenados)
    por_sev = {s: sum(1 for a in achados if a["severidade"] == s) for s in ("alta", "media", "baixa")}

    linhas = [
        "# Relatório de Revisão de Código",
        "",
        f"- **Arquivo:** `{contexto.get('caminho_arquivo', '')}`",
        f"- **Linguagem:** {contexto.get('linguagem', 'Desconhecida')}",
        f"- **Linhas analisadas:** {contexto.get('total_linhas', 0)}",
        f"- **Motor de análise:** {contexto.get('motor_analise', 'desconhecido')}",
        f"- **Data:** {contexto.get('iniciado_em', '')}",
        "",
        "## Resumo",
        "",
        f"- Total de problemas encontrados: **{total}**",
        f"- Severidade alta: {por_sev['alta']} | média: {por_sev['media']} | baixa: {por_sev['baixa']}",
        "",
        "## Detalhes",
        "",
    ]

    if total == 0:
        linhas.append("Nenhum problema encontrado pelo agente. ✅")
    else:
        emoji = {"alta": "🔴", "media": "🟡", "baixa": "🟢"}
        for i, a in enumerate(achados_ordenados, start=1):
            linhas.extend([
                f"### {i}. {emoji.get(a['severidade'], '')} [{a['severidade'].upper()}] {a['categoria']}",
                f"- **Linha:** {a['linha']}",
                f"- **Problema:** {a['descricao']}",
                f"- **Sugestão:** {a['sugestao']}",
                "",
            ])

    relatorio = "\n".join(linhas)
    return {
        "relatorio_markdown": relatorio,
        "logs": [f"[gerar_relatorio] relatório gerado ({total} achados)"],
    }


def escrever_relatorio_node(state: ReviewState) -> dict:
    """
    Nó 5 — Escrita do relatório em disco (uso da ferramenta de escrita).
    """
    relatorio = state["relatorio_markdown"]
    origem = Path(state["caminho_arquivo"]).stem
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    nome = f"review-{origem}-{stamp}.md"

    try:
        destino = escrever_relatorio(relatorio, nome)
    except FerramentaError as exc:
        return {"erros": [str(exc)], "logs": [f"[escrever_relatorio] falha: {exc}"]}

    return {
        "caminho_relatorio": destino,
        "logs": [f"[escrever_relatorio] relatório salvo em {destino}"],
    }


def rota_apos_validacao(state: ReviewState) -> str:
    """
    Aresta condicional: decide o próximo passo após a validação.

    Retorna "continuar" se a entrada é válida, ou "encerrar" caso contrário.
    É aqui que o grafo toma a decisão de seguir ou abortar o fluxo.
    """
    return "continuar" if state.get("valido") else "encerrar"
