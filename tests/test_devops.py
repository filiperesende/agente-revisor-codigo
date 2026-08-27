"""
Testes das funções determinísticas de DevOps (`src/devops.py`).

Cobrem detecção de anomalias de latência e estimativa de tendência/risco a
partir do histórico, sem depender de LLM nem de rede.
"""

import json

from src import devops


class TestDeteccaoAnomalias:
    def test_detecta_no_acima_do_limiar(self):
        metricas = [{
            "run_id": "r1",
            "por_no": [
                {"no": "analisar_com_ia", "latencia_ms": 59000.0},
                {"no": "analisar_estatico", "latencia_ms": 1.2},
            ],
        }]
        anomalias = devops.detectar_anomalias(metricas, limiar_ms=10_000)
        assert len(anomalias) == 1
        assert anomalias[0]["no"] == "analisar_com_ia"

    def test_sem_anomalia_quando_tudo_rapido(self):
        metricas = [{"run_id": "r1", "por_no": [{"no": "x", "latencia_ms": 5.0}]}]
        assert devops.detectar_anomalias(metricas) == []

    def test_resumo_por_no_agrega_media_e_max(self):
        metricas = [
            {"por_no": [{"no": "a", "latencia_ms": 10.0}]},
            {"por_no": [{"no": "a", "latencia_ms": 30.0}]},
        ]
        resumo = devops.resumo_por_no(metricas)
        assert resumo["a"]["execucoes"] == 2
        assert resumo["a"]["media_ms"] == 20.0
        assert resumo["a"]["max_ms"] == 30.0


class TestEstimativaRisco:
    def _escrever_historico(self, tmp_path, registros):
        arq = tmp_path / "historico.jsonl"
        arq.write_text(
            "\n".join(json.dumps(r) for r in registros) + "\n", encoding="utf-8"
        )
        return arq

    def test_sem_historico_retorna_desconhecido(self, tmp_path):
        arq = tmp_path / "vazio.jsonl"
        risco = devops.estimar_risco("x.py", caminho=arq)
        assert risco["execucoes"] == 0
        assert risco["risco_estimado"] == "desconhecido"

    def test_risco_alto_quando_maioria_alta(self, tmp_path):
        registros = [
            {"arquivo": "x.py", "total_achados": 5, "nivel_risco": "alto"},
            {"arquivo": "x.py", "total_achados": 6, "nivel_risco": "alto"},
        ]
        arq = self._escrever_historico(tmp_path, registros)
        risco = devops.estimar_risco("x.py", caminho=arq)
        assert risco["execucoes"] == 2
        assert risco["prob_risco_alto"] == 1.0
        assert risco["risco_estimado"] == "alto"

    def test_tendencia_piora_classifica_alto(self, tmp_path):
        registros = [
            {"arquivo": "x.py", "total_achados": 2, "nivel_risco": "normal"},
            {"arquivo": "x.py", "total_achados": 2, "nivel_risco": "normal"},
            {"arquivo": "x.py", "total_achados": 8, "nivel_risco": "normal"},
            {"arquivo": "x.py", "total_achados": 9, "nivel_risco": "normal"},
        ]
        arq = self._escrever_historico(tmp_path, registros)
        risco = devops.estimar_risco("x.py", caminho=arq)
        assert risco["tendencia_achados"] == "piora"
        assert risco["risco_estimado"] == "alto"

    def test_risco_baixo_sem_alta_e_estavel(self, tmp_path):
        registros = [
            {"arquivo": "x.py", "total_achados": 3, "nivel_risco": "normal"},
            {"arquivo": "x.py", "total_achados": 3, "nivel_risco": "normal"},
        ]
        arq = self._escrever_historico(tmp_path, registros)
        risco = devops.estimar_risco("x.py", caminho=arq)
        assert risco["prob_risco_alto"] == 0.0
        assert risco["risco_estimado"] == "baixo"
