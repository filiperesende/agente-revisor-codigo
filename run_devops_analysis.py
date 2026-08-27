"""
Análise de DevOps inteligente (Fase G).

Executa as etapas do pipeline (lint e testes), usa IA para explicar os logs de
cada etapa, detecta anomalias de latência a partir das métricas coletadas e
estima o risco de um arquivo com base no histórico de revisões.

Uso:
    python run_devops_analysis.py [arquivo_para_risco]

Exemplo:
    python run_devops_analysis.py examples/exemplo_com_bugs.py
"""

from __future__ import annotations

import subprocess
import sys

from dotenv import load_dotenv

from src import devops


def _rodar(cmd: list[str]) -> tuple[str, int]:
    """Executa um comando capturando stdout+stderr e o código de saída."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).strip(), proc.returncode


def _explicar_etapa(nome: str, cmd: list[str]) -> None:
    saida, rc = _rodar(cmd)
    explicacao, motor = devops.explicar_log_etapa(nome, saida, rc)
    print(f"\n── Etapa: {nome} (exit={rc}, explicado por: {motor}) ──")
    print(explicacao)


def main(argv: list[str]) -> int:
    load_dotenv(".env")
    arquivo_risco = argv[1] if len(argv) > 1 else "examples/exemplo_com_bugs.py"

    print("=" * 70)
    print("ANÁLISE DE DEVOPS INTELIGENTE")
    print("=" * 70)

    # 1) IA explica os logs de DUAS etapas do pipeline.
    _explicar_etapa("lint (ruff)", [sys.executable, "-m", "ruff", "check", "src", "tests"])
    _explicar_etapa("testes (pytest)", [sys.executable, "-m", "pytest", "-q"])

    # 2) Detecção de anomalias de latência a partir das métricas.
    print("\n── Detecção de anomalias (latência) ──")
    metricas = devops.carregar_metricas()
    if not metricas:
        print("Sem métricas registradas ainda. Rode o agente ao menos uma vez.")
    else:
        anomalias = devops.detectar_anomalias(metricas)
        resumo = devops.resumo_por_no(metricas)
        print(f"Execuções analisadas: {len(metricas)}")
        for no, dados in sorted(resumo.items(), key=lambda x: -x[1]["media_ms"])[:3]:
            print(f"  {no}: média={dados['media_ms']} ms, máx={dados['max_ms']} ms "
                  f"({dados['execucoes']} exec.)")
        if anomalias:
            print(f"\n⚠️  {len(anomalias)} anomalia(s) de latência (>= "
                  f"{devops.LIMIAR_ANOMALIA_MS} ms):")
            for a in anomalias[-3:]:
                print(f"  run={a['run_id']} nó={a['no']} latência={a['latencia_ms']} ms")
        else:
            print("Nenhuma anomalia de latência detectada.")

    # 3) Estimativa de risco/tendência a partir do histórico.
    print(f"\n── Estimativa de risco: {arquivo_risco} ──")
    risco = devops.estimar_risco(arquivo_risco)
    if risco.get("execucoes", 0) == 0:
        print("Sem histórico para este arquivo.")
    else:
        print(f"Execuções no histórico: {risco['execucoes']}")
        print(f"Probabilidade de risco alto: {risco['prob_risco_alto']}")
        print(f"Tendência de achados: {risco['tendencia_achados']}")
        print(f"Risco estimado: {risco['risco_estimado'].upper()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
