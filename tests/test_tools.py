"""
Testes das ferramentas do agente (`src/tools.py`).

Cobrem o uso controlado das ferramentas e seus limites de segurança:
extensões permitidas, tamanho máximo, arquivo vazio e proteção contra
path traversal na escrita do relatório.
"""

import pytest

from src import tools
from src.tools import (
    FerramentaError,
    detectar_linguagem,
    ler_arquivo_codigo,
    escrever_relatorio,
    TAMANHO_MAXIMO_BYTES,
)


class TestDetectarLinguagem:
    def test_extensao_conhecida(self):
        assert detectar_linguagem("app.py") == "Python"
        assert detectar_linguagem("main.ts") == "TypeScript"

    def test_extensao_desconhecida(self):
        assert detectar_linguagem("arquivo.xyz") == "Desconhecida"


class TestLerArquivoCodigo:
    def test_le_arquivo_valido(self, tmp_path):
        arquivo = tmp_path / "codigo.py"
        arquivo.write_text("print('ola')", encoding="utf-8")
        assert ler_arquivo_codigo(str(arquivo)) == "print('ola')"

    def test_caminho_vazio_levanta_erro(self):
        with pytest.raises(FerramentaError):
            ler_arquivo_codigo("")

    def test_arquivo_inexistente_levanta_erro(self, tmp_path):
        with pytest.raises(FerramentaError, match="não encontrado"):
            ler_arquivo_codigo(str(tmp_path / "nao_existe.py"))

    def test_extensao_nao_permitida_levanta_erro(self, tmp_path):
        arquivo = tmp_path / "nota.txt"
        arquivo.write_text("conteudo", encoding="utf-8")
        with pytest.raises(FerramentaError, match="não permitida"):
            ler_arquivo_codigo(str(arquivo))

    def test_arquivo_vazio_levanta_erro(self, tmp_path):
        arquivo = tmp_path / "vazio.py"
        arquivo.write_text("", encoding="utf-8")
        with pytest.raises(FerramentaError, match="vazio"):
            ler_arquivo_codigo(str(arquivo))

    def test_arquivo_muito_grande_levanta_erro(self, tmp_path):
        arquivo = tmp_path / "grande.py"
        arquivo.write_text("x" * (TAMANHO_MAXIMO_BYTES + 1), encoding="utf-8")
        with pytest.raises(FerramentaError, match="muito grande"):
            ler_arquivo_codigo(str(arquivo))


class TestEscreverRelatorio:
    def test_grava_relatorio_e_retorna_caminho(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tools, "DIRETORIO_RELATORIOS", tmp_path)
        destino = escrever_relatorio("# Relatório", "saida.md")
        assert destino.endswith("saida.md")
        assert (tmp_path / "saida.md").read_text(encoding="utf-8") == "# Relatório"

    def test_adiciona_extensao_md_quando_ausente(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tools, "DIRETORIO_RELATORIOS", tmp_path)
        destino = escrever_relatorio("conteudo", "relatorio")
        assert destino.endswith("relatorio.md")

    def test_protege_contra_path_traversal(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tools, "DIRETORIO_RELATORIOS", tmp_path)
        destino = escrever_relatorio("conteudo", "../../etc/passwd.md")
        # Apenas o nome base é usado; nada escapa do diretório de relatórios.
        assert destino == str(tmp_path / "passwd.md")
        assert (tmp_path / "passwd.md").exists()

    def test_conteudo_vazio_levanta_erro(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tools, "DIRETORIO_RELATORIOS", tmp_path)
        with pytest.raises(FerramentaError, match="vazio"):
            escrever_relatorio("", "saida.md")
