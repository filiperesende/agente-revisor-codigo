"""
Testes de integração do agente (fluxo do grafo LangGraph ponta a ponta).

Diferente dos testes unitários, aqui exercitamos o grafo inteiro com o motor
MOCK (determinístico, sem rede), validando paralelização, consolidação,
decisão de risco, gate de notificação, defesa contra injeção, memória e
observabilidade. A fixture `ambiente_isolado` garante execução hermética.
"""

from src.agent import revisar_arquivo

ARQUIVO_BUGS = "examples/exemplo_com_bugs.py"
ARQUIVO_INJECAO = "examples/exemplo_prompt_injection.py"


class TestFluxoPrincipal:
    def test_fluxo_completo_produz_estado_coerente(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_BUGS)

        assert estado["valido"] is True
        # Motor mock (sem chave de API no ambiente isolado).
        assert "mock" in estado["contexto"]["motor_analise"]
        # Paralelização: os dois ramos preencheram seus campos exclusivos.
        assert "achados_ia" in estado
        assert "achados_estatica" in estado
        # Consolidação produziu achados e totais no contexto.
        assert len(estado["achados"]) > 0
        assert estado["contexto"]["total_achados"] == len(estado["achados"])
        # Saída estruturada gerada.
        assert "# Relatório de Revisão de Código" in estado["relatorio_markdown"]

    def test_risco_alto_aciona_priorizacao(self, ambiente_isolado):
        # O arquivo tem credencial fixa e eval() -> severidade alta no mock.
        estado = revisar_arquivo(ARQUIVO_BUGS)
        assert estado["contexto"]["nivel_risco"] == "alto"

    def test_observabilidade_preenchida(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_BUGS)
        assert estado["run_id"]
        assert estado["metricas"]["total_nos"] >= 1
        assert estado["metricas"]["latencia_total_ms"] >= 0


class TestGovernanca:
    def test_notificacao_pulada_sem_webhook(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_BUGS)
        assert estado["notificacao"]["status"] == "pulado"


class TestSeguranca:
    def test_prompt_injection_detectado_como_seguranca(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_INJECAO)
        seg_alta = [
            a for a in estado["achados"]
            if a["categoria"] == "seguranca" and a["severidade"] == "alta"
        ]
        assert seg_alta, "esperava ao menos um achado de segurança/alta"
        assert any("injection" in a["descricao"].lower() for a in seg_alta)

    def test_segredo_nao_vaza_no_relatorio(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_INJECAO)
        assert "admin123" not in estado["relatorio_markdown"]


class TestEntradaInvalida:
    def test_arquivo_inexistente_encerra_fluxo(self, ambiente_isolado):
        estado = revisar_arquivo("nao_existe.py")
        assert estado["valido"] is False
        assert estado["erros"]
        # Fluxo abortado na validação: não chega a produzir achados.
        assert not estado.get("achados")


class TestMemoria:
    def test_segunda_execucao_recupera_anterior(self, ambiente_isolado):
        revisar_arquivo(ARQUIVO_BUGS)  # primeira revisão
        estado = revisar_arquivo(ARQUIVO_BUGS)  # segunda deve comparar
        assert "Comparação com a revisão anterior" in estado["relatorio_markdown"]
        assert "Revisão anterior:" in estado["relatorio_markdown"]
