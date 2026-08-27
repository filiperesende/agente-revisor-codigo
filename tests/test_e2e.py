"""
Teste E2E (end-to-end) do Agente Revisor.

Executa o agente de ponta a ponta e verifica os artefatos produzidos em disco:
o relatório em Markdown, o resumo de métricas e o histórico persistente. Usa a
fixture `ambiente_isolado` para não afetar os diretórios reais do projeto.
"""

from pathlib import Path

from src.agent import revisar_arquivo

ARQUIVO_BUGS = "examples/exemplo_com_bugs.py"


class TestExecucaoPontaAPonta:
    def test_relatorio_gravado_em_disco(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_BUGS)

        caminho = estado.get("caminho_relatorio")
        assert caminho, "esperava um caminho de relatório no estado final"

        arquivo = Path(caminho)
        assert arquivo.exists()
        conteudo = arquivo.read_text(encoding="utf-8")
        assert "# Relatório de Revisão de Código" in conteudo
        assert "## Resumo" in conteudo
        assert "## Detalhes" in conteudo
        # Gravado dentro da sandbox isolada do teste.
        assert str(ambiente_isolado) in str(arquivo.resolve())

    def test_metricas_e_historico_persistidos(self, ambiente_isolado):
        revisar_arquivo(ARQUIVO_BUGS)

        metricas = ambiente_isolado / "metricas.jsonl"
        historico = ambiente_isolado / "historico.jsonl"
        assert metricas.exists(), "métricas não foram persistidas"
        assert historico.exists(), "histórico não foi persistido"

        # Uma execução => uma linha de métricas.
        linhas_metricas = metricas.read_text(encoding="utf-8").strip().splitlines()
        assert len(linhas_metricas) == 1

    def test_logs_estruturados_gerados(self, ambiente_isolado):
        estado = revisar_arquivo(ARQUIVO_BUGS)
        run_id = estado["run_id"]

        logs = ambiente_isolado / "agent.jsonl"
        assert logs.exists()
        conteudo = logs.read_text(encoding="utf-8")
        # Os logs correlacionam pela mesma run_id da execução.
        assert run_id in conteudo
