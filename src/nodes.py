"""
Nós do grafo do agente.

Cada função abaixo é um nó do LangGraph. Recebe o estado atual e retorna um
dicionário com os campos que devem ser atualizados no estado compartilhado.

Fluxo:
    validar_entrada -> preparar_contexto
                    -> [analisar_com_ia | analisar_estatico]  (paralelo)
                    -> consolidar_achados                     (fan-in)
                    -> [priorizar_achados]                    (condicional: risco alto)
                    -> gerar_relatorio -> escrever_relatorio
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import analise_estatica, llm, notificacao
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


def analisar_com_ia(state: ReviewState) -> dict:
    """
    Nó 3a (ramo paralelo) — Análise dirigida pelo modelo (Gemini ou mock).

    Representa a parte de "decisão do modelo" do fluxo. Escreve apenas em
    campos exclusivos deste nó (`achados_ia`, `motor_analise`) para permitir
    execução paralela sem conflito de atualização no estado compartilhado.
    """
    codigo = state["codigo_fonte"]
    contexto = state.get("contexto", {})

    brutos, motor = llm.analisar_codigo(codigo, contexto)
    achados = normalizar_achados(brutos)

    return {
        "achados_ia": achados,
        "motor_analise": motor,
        "logs": [f"[analisar_com_ia] motor={motor}, achados={len(achados)}"],
    }


def analisar_estatico(state: ReviewState) -> dict:
    """
    Nó 3b (ramo paralelo) — Análise estática determinística (sem LLM).

    Representa a parte de "regras determinísticas" do fluxo. Roda em paralelo
    com `analisar_com_ia` e escreve apenas em `achados_estatica`.
    """
    codigo = state["codigo_fonte"]
    achados = normalizar_achados(analise_estatica.analisar(codigo))

    return {
        "achados_estatica": achados,
        "logs": [f"[analisar_estatico] regras determinísticas, achados={len(achados)}"],
    }


def consolidar_achados(state: ReviewState) -> dict:
    """
    Nó 4 (fan-in) — Une os resultados dos dois ramos paralelos.

    Junta os achados da IA e da análise estática, remove duplicatas e atualiza
    a memória (contexto) com os totais consolidados. É aqui que os dois ramos
    convergem antes da decisão de priorização.
    """
    contexto = dict(state.get("contexto", {}))
    ia = state.get("achados_ia", [])
    estatica = state.get("achados_estatica", [])

    consolidados = _mesclar_sem_duplicatas(ia + estatica)
    por_sev = {
        s: sum(1 for a in consolidados if a["severidade"] == s)
        for s in ("alta", "media", "baixa")
    }

    contexto["motor_analise"] = state.get("motor_analise", "desconhecido")
    contexto["total_achados"] = len(consolidados)
    contexto["achados_ia"] = len(ia)
    contexto["achados_estatica"] = len(estatica)
    contexto["por_severidade"] = por_sev

    return {
        "achados": consolidados,
        "contexto": contexto,
        "logs": [
            f"[consolidar_achados] ia={len(ia)}, estatica={len(estatica)}, "
            f"consolidados={len(consolidados)} (alta={por_sev['alta']})"
        ],
    }


def priorizar_achados(state: ReviewState) -> dict:
    """
    Nó 5 (condicional) — Priorização acionada quando há risco alto.

    Só é executado pela aresta condicional quando existe pelo menos um achado
    de severidade alta. Marca o nível de risco da execução na memória, o que
    orienta o relatório e prepara o gate de aprovação humana (Fase C).
    """
    contexto = dict(state.get("contexto", {}))
    achados = state.get("achados", [])
    alta = [a for a in achados if a["severidade"] == "alta"]

    contexto["nivel_risco"] = "alto"
    contexto["requer_atencao"] = True
    contexto["achados_prioritarios"] = len(alta)

    return {
        "contexto": contexto,
        "logs": [f"[priorizar_achados] risco ALTO: {len(alta)} achado(s) prioritário(s)"],
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
    nivel_risco = contexto.get("nivel_risco", "normal")

    linhas = [
        "# Relatório de Revisão de Código",
        "",
        f"- **Arquivo:** `{contexto.get('caminho_arquivo', '')}`",
        f"- **Linguagem:** {contexto.get('linguagem', 'Desconhecida')}",
        f"- **Linhas analisadas:** {contexto.get('total_linhas', 0)}",
        f"- **Motor de análise:** {contexto.get('motor_analise', 'desconhecido')}",
        f"- **Nível de risco:** {nivel_risco.upper()}",
        f"- **Data:** {contexto.get('iniciado_em', '')}",
        "",
    ]

    if nivel_risco == "alto":
        linhas.extend([
            "> ⚠️ **Atenção:** foram encontrados problemas de severidade alta. "
            "Recomenda-se revisão humana antes de prosseguir.",
            "",
        ])

    linhas.extend([
        "## Resumo",
        "",
        f"- Total de problemas encontrados: **{total}**",
        f"- Severidade alta: {por_sev['alta']} | média: {por_sev['media']} | baixa: {por_sev['baixa']}",
        f"- Origem: IA={contexto.get('achados_ia', 0)} | "
        f"estática={contexto.get('achados_estatica', 0)}",
        "",
        "## Detalhes",
        "",
    ])

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


def notificar_node(state: ReviewState) -> dict:
    """
    Nó 6 — Notificação externa (uso da tool de webhook do Discord).

    Monta o payload a partir do contexto/achados e chama a tool de notificação.
    Se o webhook não estiver configurado, a etapa é pulada sem erro. Nenhuma
    exceção da integração externa interrompe o fluxo do agente.
    """
    contexto = state.get("contexto", {})
    achados = state.get("achados", [])

    payload = {
        "arquivo": contexto.get("caminho_arquivo") or state.get("caminho_arquivo", ""),
        "linguagem": contexto.get("linguagem", "Desconhecida"),
        "total_achados": contexto.get("total_achados", len(achados)),
        "por_severidade": contexto.get("por_severidade", {}),
        "nivel_risco": contexto.get("nivel_risco", "normal"),
        "caminho_relatorio": state.get("caminho_relatorio"),
    }

    resultado = notificacao.enviar_notificacao(payload)
    return {
        "notificacao": resultado,
        "logs": [f"[notificar] status={resultado.get('status')}"],
    }


def rota_apos_validacao(state: ReviewState) -> str:
    """
    Aresta condicional 1: decide o próximo passo após a validação.

    Retorna "continuar" se a entrada é válida, ou "encerrar" caso contrário.
    É aqui que o grafo toma a decisão de seguir ou abortar o fluxo.
    """
    return "continuar" if state.get("valido") else "encerrar"


def rota_apos_consolidacao(state: ReviewState) -> str:
    """
    Aresta condicional 2: decide se a execução precisa de priorização.

    Se houver ao menos um achado de severidade alta, o fluxo passa pelo nó de
    priorização (que marca o risco). Caso contrário, segue direto ao relatório.
    """
    achados = state.get("achados", [])
    tem_risco_alto = any(a["severidade"] == "alta" for a in achados)
    return "priorizar" if tem_risco_alto else "seguir"


def _mesclar_sem_duplicatas(achados: list) -> list:
    """
    Remove achados duplicados vindos dos dois ramos de análise.

    Considera duplicata quando categoria, linha e descrição coincidem — caso
    em que a IA e a análise estática apontaram o mesmo problema.
    """
    vistos: set[tuple] = set()
    unicos = []
    for a in achados:
        chave = (a.get("categoria"), a.get("linha"), a.get("descricao"))
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(a)
    return unicos
