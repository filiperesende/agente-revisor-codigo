"""
Configuração compartilhada do pytest.

A presença deste arquivo na raiz do projeto adiciona o diretório raiz ao
sys.path, permitindo que os testes importem o pacote `src` diretamente
(ex.: `from src.validation import ...`).
"""

import pytest


@pytest.fixture
def ambiente_isolado(tmp_path, monkeypatch):
    """
    Torna a execução do agente hermética para testes de integração/E2E.

    - Força o motor MOCK (remove chaves de API), garantindo resultado
      determinístico e sem chamadas de rede.
    - Desativa a notificação externa (remove a URL do webhook).
    - Redireciona relatórios, histórico e logs para um diretório temporário,
      evitando efeitos colaterais no projeto.

    Devolve o `tmp_path` para os testes que precisarem inspecionar artefatos.
    """
    from src import memoria, observability, tools

    # Força mock e desativa integrações externas.
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

    # Isola artefatos de runtime em tmp_path.
    monkeypatch.setattr(tools, "DIRETORIO_RELATORIOS", tmp_path / "reports")
    monkeypatch.setattr(memoria, "ARQUIVO_HISTORICO", tmp_path / "historico.jsonl")
    monkeypatch.setattr(observability, "ARQUIVO_LOG", tmp_path / "agent.jsonl")
    monkeypatch.setattr(observability, "ARQUIVO_METRICAS", tmp_path / "metricas.jsonl")

    return tmp_path
