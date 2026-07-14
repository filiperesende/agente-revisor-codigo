"""
Ferramentas integradas ao agente.

Cada ferramenta executa uma ação real e controlada sobre o sistema de arquivos:
  1. `ler_arquivo_codigo`  -> leitura de arquivo de código (entrada do agente)
  2. `escrever_relatorio`  -> escrita do relatório final em Markdown (saída)

As ferramentas aplicam limites de segurança (extensões permitidas, tamanho
máximo, proteção contra path traversal) para evitar ações fora do escopo.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Limites de segurança da ferramenta ---
EXTENSOES_PERMITIDAS = {
    ".py", ".js", ".ts", ".java", ".go", ".rb", ".php",
    ".c", ".cpp", ".cs", ".rs", ".kt", ".swift", ".sql",
}
TAMANHO_MAXIMO_BYTES = 100 * 1024  # 100 KB — evita processar arquivos gigantes

# Diretório onde os relatórios podem ser gravados (sandbox de escrita).
DIRETORIO_RELATORIOS = Path("reports")

# Mapa simples de extensão -> linguagem, usado para dar contexto ao LLM.
MAPA_LINGUAGENS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".java": "Java", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".cpp": "C++", ".cs": "C#", ".rs": "Rust",
    ".kt": "Kotlin", ".swift": "Swift", ".sql": "SQL",
}


class FerramentaError(Exception):
    """Erro controlado emitido pelas ferramentas."""


def detectar_linguagem(caminho: str) -> str:
    """Retorna o nome da linguagem a partir da extensão do arquivo."""
    return MAPA_LINGUAGENS.get(Path(caminho).suffix.lower(), "Desconhecida")


def ler_arquivo_codigo(caminho: str) -> str:
    """
    Ferramenta 1: lê o conteúdo de um arquivo de código de forma controlada.

    Valida existência, extensão permitida e tamanho máximo antes de ler.
    Levanta `FerramentaError` em qualquer condição inválida.
    """
    if not caminho or not isinstance(caminho, str):
        raise FerramentaError("Caminho do arquivo não informado.")

    p = Path(caminho).expanduser()

    if not p.exists():
        raise FerramentaError(f"Arquivo não encontrado: {caminho}")
    if not p.is_file():
        raise FerramentaError(f"O caminho não é um arquivo: {caminho}")
    if p.suffix.lower() not in EXTENSOES_PERMITIDAS:
        raise FerramentaError(
            f"Extensão '{p.suffix}' não permitida. "
            f"Permitidas: {', '.join(sorted(EXTENSOES_PERMITIDAS))}"
        )

    tamanho = p.stat().st_size
    if tamanho == 0:
        raise FerramentaError("Arquivo está vazio.")
    if tamanho > TAMANHO_MAXIMO_BYTES:
        raise FerramentaError(
            f"Arquivo muito grande ({tamanho} bytes). "
            f"Limite: {TAMANHO_MAXIMO_BYTES} bytes."
        )

    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FerramentaError("Arquivo não é texto UTF-8 válido.") from exc


def escrever_relatorio(conteudo: str, nome_arquivo: str) -> str:
    """
    Ferramenta 2: grava o relatório em Markdown dentro de `reports/`.

    Protege contra path traversal: apenas o nome do arquivo é usado, qualquer
    caminho é descartado. Retorna o caminho final do relatório gravado.
    """
    if not conteudo:
        raise FerramentaError("Conteúdo do relatório está vazio.")

    # Usa somente o nome base, ignorando diretórios embutidos (../, /etc, etc.)
    nome_seguro = os.path.basename(nome_arquivo)
    if not nome_seguro.endswith(".md"):
        nome_seguro += ".md"

    DIRETORIO_RELATORIOS.mkdir(parents=True, exist_ok=True)
    destino = DIRETORIO_RELATORIOS / nome_seguro
    destino.write_text(conteudo, encoding="utf-8")
    return str(destino)
