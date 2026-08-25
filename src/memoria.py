"""
Memória persistente de revisões (recuperação contextual do domínio).

Cada revisão concluída é registrada em disco (data/historico.jsonl, um JSON por
linha). Nas execuções seguintes, o agente recupera a última revisão do MESMO
arquivo para comparar o que mudou (nº de achados, nível de risco) e alimentar a
estimativa de tendência/risco.

Formato de cada registro:
    {
      "timestamp": "2026-08-24T22:30:00",
      "arquivo": "examples/exemplo_com_bugs.py",
      "linguagem": "Python",
      "total_achados": 7,
      "por_severidade": {"alta": 2, "media": 1, "baixa": 4},
      "nivel_risco": "alto",
      "motor_analise": "gemini"
    }

O arquivo de histórico é dado de runtime e NÃO é versionado (data/ no .gitignore).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# Local do histórico (sandbox de dados de runtime).
DIRETORIO_DADOS = Path("data")
ARQUIVO_HISTORICO = DIRETORIO_DADOS / "historico.jsonl"

# Campos persistidos por revisão.
CAMPOS = (
    "timestamp", "arquivo", "linguagem",
    "total_achados", "por_severidade", "nivel_risco", "motor_analise",
)


def registrar_revisao(registro: dict, caminho: Path = ARQUIVO_HISTORICO) -> None:
    """
    Acrescenta um registro de revisão ao histórico (append-only).

    Preenche o timestamp automaticamente se ausente. Falhas de escrita não
    devem interromper o agente, então erros de I/O são propagados apenas se
    o chamador quiser tratá-los.
    """
    registro = {**registro}
    registro.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    # Mantém apenas os campos previstos, em ordem estável.
    linha = {campo: registro.get(campo) for campo in CAMPOS}

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def _ler_registros(caminho: Path = ARQUIVO_HISTORICO) -> list[dict]:
    """Lê todos os registros válidos do histórico, ignorando linhas corrompidas."""
    if not caminho.exists():
        return []
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            continue  # ignora linha malformada, não quebra a recuperação
    return registros


def recuperar_ultima_revisao(
    arquivo: str, caminho: Path = ARQUIVO_HISTORICO
) -> dict | None:
    """Recupera o registro mais recente de revisão para um dado arquivo."""
    anteriores = [r for r in _ler_registros(caminho) if r.get("arquivo") == arquivo]
    return anteriores[-1] if anteriores else None


def recuperar_historico(
    arquivo: str, limite: int = 10, caminho: Path = ARQUIVO_HISTORICO
) -> list[dict]:
    """
    Recupera os últimos `limite` registros de um arquivo (mais antigos -> recentes).

    Usado para análise de tendência/risco (Fase G).
    """
    anteriores = [r for r in _ler_registros(caminho) if r.get("arquivo") == arquivo]
    return anteriores[-limite:] if limite > 0 else anteriores
