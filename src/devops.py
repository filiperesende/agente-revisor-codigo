"""
DevOps inteligente: análise de logs, detecção de anomalias e estimativa de risco.

Este módulo trabalha sobre os sinais de observabilidade (métricas de latência) e
sobre a memória persistente (histórico de revisões) para:

  - detectar anomalias de latência (nós muito mais lentos que o normal);
  - estimar tendência e risco de falha a partir do histórico de execuções;
  - explicar logs de etapas do pipeline com apoio de IA (com fallback heurístico).

É consumido pela CLI `run_devops_analysis.py`.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import llm, memoria, observability

# Acima deste limiar, a latência de um único nó é considerada anômala.
LIMIAR_ANOMALIA_MS = 10_000  # 10 segundos


# --------------------------------------------------------------------------- #
# Métricas / anomalias
# --------------------------------------------------------------------------- #
def carregar_metricas(caminho: Path | None = None) -> list[dict]:
    """Lê o arquivo de métricas (uma execução por linha)."""
    caminho = Path(caminho) if caminho else observability.ARQUIVO_METRICAS
    if not caminho.exists():
        return []
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha:
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
    return registros


def latencia_por_no(metricas: list[dict]) -> dict[str, list[float]]:
    """Agrega as latências observadas por nó ao longo das execuções."""
    agg: dict[str, list[float]] = {}
    for execucao in metricas:
        for no in execucao.get("por_no", []):
            agg.setdefault(no["no"], []).append(float(no["latencia_ms"]))
    return agg


def resumo_por_no(metricas: list[dict]) -> dict[str, dict]:
    """Média e máximo de latência por nó."""
    resumo = {}
    for no, lats in latencia_por_no(metricas).items():
        resumo[no] = {
            "execucoes": len(lats),
            "media_ms": round(statistics.mean(lats), 2),
            "max_ms": round(max(lats), 2),
        }
    return resumo


def detectar_anomalias(metricas: list[dict], limiar_ms: float = LIMIAR_ANOMALIA_MS) -> list[dict]:
    """Retorna os nós cuja latência ultrapassou o limiar em alguma execução."""
    anomalias = []
    for execucao in metricas:
        for no in execucao.get("por_no", []):
            if float(no["latencia_ms"]) >= limiar_ms:
                anomalias.append({
                    "run_id": execucao.get("run_id"),
                    "timestamp": execucao.get("timestamp"),
                    "no": no["no"],
                    "latencia_ms": no["latencia_ms"],
                })
    return anomalias


# --------------------------------------------------------------------------- #
# Estimativa de tendência / risco
# --------------------------------------------------------------------------- #
def estimar_risco(arquivo: str, caminho: Path | None = None) -> dict:
    """
    Estima tendência e risco de falha de um arquivo a partir do histórico.

    Usa a memória persistente de revisões: calcula a proporção de execuções de
    risco alto (probabilidade simples) e a tendência do número de achados
    (comparando a média da primeira metade das execuções com a segunda).
    """
    historico = memoria.recuperar_historico(arquivo, limite=50, caminho=caminho)
    n = len(historico)
    if n == 0:
        return {"arquivo": arquivo, "execucoes": 0, "risco_estimado": "desconhecido"}

    totais = [int(h.get("total_achados", 0)) for h in historico]
    altos = sum(1 for h in historico if h.get("nivel_risco") == "alto")
    prob_alto = round(altos / n, 2)

    # Tendência: média da 1a metade vs 2a metade das execuções.
    meio = n // 2
    if meio >= 1:
        media_ini = statistics.mean(totais[:meio])
        media_fim = statistics.mean(totais[meio:])
        if media_fim > media_ini:
            tendencia = "piora"
        elif media_fim < media_ini:
            tendencia = "melhora"
        else:
            tendencia = "estável"
    else:
        tendencia = "indefinida (poucas execuções)"

    # Classificação simples de risco.
    if prob_alto >= 0.5 or tendencia == "piora":
        risco = "alto"
    elif prob_alto > 0:
        risco = "medio"
    else:
        risco = "baixo"

    return {
        "arquivo": arquivo,
        "execucoes": n,
        "prob_risco_alto": prob_alto,
        "tendencia_achados": tendencia,
        "achados_por_execucao": totais,
        "risco_estimado": risco,
    }


# --------------------------------------------------------------------------- #
# Explicação de logs (IA com fallback heurístico)
# --------------------------------------------------------------------------- #
def explicar_log_etapa(etapa: str, saida: str, exit_code: int) -> tuple[str, str]:
    """
    Explica o log de uma etapa do pipeline usando IA (com fallback heurístico).

    Retorna (explicacao, motor). Se o LLM não estiver disponível ou falhar, gera
    uma explicação heurística determinística.
    """
    prompt = (
        "Você é um engenheiro de DevOps. Explique de forma objetiva, em 3 a 5 "
        f"linhas, o resultado da etapa '{etapa}' de um pipeline de CI. Diga se "
        f"passou ou falhou (exit code = {exit_code}) e o que o log indica. "
        f"Log da etapa:\n---\n{saida[:3000]}\n---"
    )
    explicacao, motor = llm.explicar(prompt)
    if explicacao is None:
        return _explicacao_heuristica(etapa, saida, exit_code), motor
    return explicacao, motor


def _explicacao_heuristica(etapa: str, saida: str, exit_code: int) -> str:
    """Explicação determinística usada quando o LLM não está disponível."""
    status = "passou" if exit_code == 0 else "falhou"
    ultima = saida.strip().splitlines()[-1] if saida.strip() else "(sem saída)"
    return (
        f"A etapa '{etapa}' {status} (exit code {exit_code}). "
        f"Última linha do log: {ultima!r}. "
        + ("Nenhuma ação necessária." if exit_code == 0
           else "Verifique o log acima para identificar a causa da falha.")
    )
