"""
Observabilidade do agente: logs estruturados + métricas de latência.

Produz DOIS sinais correlacionados por um mesmo `run_id`:

  1. Logs estruturados (JSON), um evento por linha, gravados em
     `logs/agent.jsonl`. Cada evento registra run_id, nó, tipo de evento,
     nível, timestamp e campos extras (latência, erros, decisões).
  2. Métricas de latência por nó, agregadas em memória durante a execução e
     escritas ao final em `logs/metricas.jsonl` (uma linha por execução).

Como os dois sinais compartilham o `run_id`, é possível reconstruir uma
execução: ver a sequência de nós, decisões, erros e a latência de cada etapa.

Os arquivos de log são dados de runtime e NÃO são versionados (logs/ no
.gitignore).
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

DIRETORIO_LOGS = Path("logs")
ARQUIVO_LOG = DIRETORIO_LOGS / "agent.jsonl"
ARQUIVO_METRICAS = DIRETORIO_LOGS / "metricas.jsonl"

# Registro de métricas em memória, por run_id. Protegido por lock porque os
# nós paralelos do grafo podem escrever ao mesmo tempo.
_METRICAS: dict[str, list[dict]] = {}
_LOCK = threading.Lock()


import functools
import time


def novo_run_id() -> str:
    """Gera um identificador curto e único para correlacionar uma execução."""
    return uuid.uuid4().hex[:12]


def instrumentar(nome: str, func):
    """
    Decora um nó do grafo para medir latência e emitir logs estruturados.

    Registra os eventos "inicio" e "fim" (com latencia_ms) de cada nó e alimenta
    o resumo de métricas. Em caso de exceção, emite um evento "erro" (nível
    ERROR) com a latência até a falha e propaga a exceção.
    """
    @functools.wraps(func)
    def wrapper(state):
        run_id = state.get("run_id", "sem-run-id")
        inicio = time.perf_counter()
        log_evento(run_id, nome, "inicio")
        try:
            resultado = func(state)
        except Exception as exc:  # noqa: BLE001 — loga e repropaga
            latencia = (time.perf_counter() - inicio) * 1000
            log_evento(run_id, nome, "erro", nivel="ERROR",
                       erro=f"{type(exc).__name__}: {exc}", latencia_ms=round(latencia, 2))
            registrar_metrica(run_id, nome, latencia)
            raise
        latencia = (time.perf_counter() - inicio) * 1000
        registrar_metrica(run_id, nome, latencia)
        log_evento(run_id, nome, "fim", latencia_ms=round(latencia, 2))
        return resultado

    return wrapper


def _escrever_linha(caminho: Path, registro: dict) -> None:
    """Acrescenta um registro JSON (uma linha) a um arquivo de log."""
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        # Observabilidade nunca deve derrubar o agente.
        pass


def log_evento(run_id: str, no: str, evento: str, nivel: str = "INFO", **campos) -> None:
    """
    Emite um log estruturado (JSON) para um evento de um nó.

    Campos padrão: timestamp, run_id, nivel, no, evento. Campos extras
    (ex.: latencia_ms, erro, decisao) são anexados via **campos.
    """
    registro = {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "run_id": run_id,
        "nivel": nivel,
        "no": no,
        "evento": evento,
        **campos,
    }
    _escrever_linha(ARQUIVO_LOG, registro)


def registrar_metrica(run_id: str, no: str, latencia_ms: float) -> None:
    """Acumula a latência de um nó para o resumo de métricas da execução."""
    with _LOCK:
        _METRICAS.setdefault(run_id, []).append({
            "no": no,
            "latencia_ms": round(latencia_ms, 2),
        })


def resumo_metricas(run_id: str) -> dict:
    """Consolida as métricas coletadas de uma execução."""
    with _LOCK:
        registros = list(_METRICAS.get(run_id, []))
    total = round(sum(r["latencia_ms"] for r in registros), 2)
    return {
        "run_id": run_id,
        "total_nos": len(registros),
        "latencia_total_ms": total,
        "por_no": registros,
    }


def flush_metricas(run_id: str) -> dict:
    """
    Escreve o resumo de métricas da execução em `logs/metricas.jsonl` e o
    remove da memória. Retorna o resumo (útil para a CLI e evidências).
    """
    resumo = resumo_metricas(run_id)
    resumo["timestamp"] = datetime.now().isoformat(timespec="seconds")
    _escrever_linha(ARQUIVO_METRICAS, resumo)
    with _LOCK:
        _METRICAS.pop(run_id, None)
    return resumo
