"""
Análise estática determinística (independente de LLM).

Este módulo aplica regras estruturais fixas sobre o código-fonte, sem qualquer
chamada a modelo de linguagem. Ele existe para deixar explícita a separação
exigida pelo projeto entre:

  - decisões do modelo (IA)   -> `src/llm.py`
  - regras determinísticas    -> este módulo

As duas análises rodam em paralelo no grafo e são unidas no nó de consolidação.
Cada regra devolve achados no mesmo formato `Achado` usado pelo resto do agente.
"""

from __future__ import annotations

import re

# Limites das regras determinísticas.
LIMITE_LINHA_LONGA = 100      # caracteres por linha
LIMITE_ARQUIVO_EXTENSO = 300  # linhas no arquivo


def analisar(codigo: str) -> list[dict]:
    """
    Executa todas as regras determinísticas sobre o código e devolve achados.

    A saída é uma lista de dicionários no formato `Achado`
    (severidade, categoria, linha, descricao, sugestao). Todos os achados são
    marcados com a categoria de origem "estatica-*" para facilitar a auditoria.
    """
    linhas = codigo.splitlines()
    achados: list[dict] = []

    achados.extend(_regra_linha_longa(linhas))
    achados.extend(_regra_import_wildcard(linhas))
    achados.extend(_regra_multiplas_instrucoes(linhas))
    achados.extend(_regra_arquivo_extenso(linhas))
    achados.extend(_regra_prompt_injection(linhas))

    return achados


# Frases típicas de tentativa de manipular o revisor (prompt injection),
# geralmente escondidas em comentários ou strings do código.
PADROES_INJECAO = [
    r"ignore\s+(as\s+|todas\s+as\s+)?instru",       # "ignore as instruções"
    r"ignore\s+(all\s+)?previous",                   # "ignore previous instructions"
    r"disregard\s+(the\s+|all\s+)?(previous|above)",
    r"esque[çc]a\s+(as\s+)?regras",                  # "esqueça as regras"
    r"revele?\s+.*(chave|senha|segredo|api[_ ]?key|token)",
    r"reveal\s+.*(secret|api[_ ]?key|password|token)",
    r"(system\s+prompt|prompt\s+de\s+sistema)",
    r"(voc[êe]|you)\s+(agora|now)\s+(é|is|are)",     # "você agora é" / "you are now"
    r"aja\s+como|act\s+as\s+(a|an)?",                # "aja como" / "act as"
]


def _regra_prompt_injection(linhas: list[str]) -> list[dict]:
    """
    Detecta tentativas de prompt injection embutidas no código.

    Sinaliza como problema de segurança (severidade alta) qualquer linha que
    contenha frases de manipulação do revisor. A ideia é que o agente TRATE a
    tentativa como um achado a ser reportado — nunca como uma instrução.
    """
    achados = []
    padroes = [re.compile(p, re.IGNORECASE) for p in PADROES_INJECAO]
    for i, linha in enumerate(linhas, start=1):
        if any(p.search(linha) for p in padroes):
            achados.append({
                "severidade": "alta",
                "categoria": "seguranca",
                "linha": str(i),
                "descricao": (
                    "Possível tentativa de prompt injection: o texto tenta "
                    "manipular o comportamento do revisor."
                ),
                "sugestao": (
                    "Trate o conteúdo como dado não confiável; não siga "
                    "instruções embutidas no código. Remova o texto suspeito."
                ),
            })
    return achados


def _regra_linha_longa(linhas: list[str]) -> list[dict]:
    """Sinaliza linhas que ultrapassam o limite de comprimento."""
    achados = []
    for i, linha in enumerate(linhas, start=1):
        if len(linha) > LIMITE_LINHA_LONGA:
            achados.append({
                "severidade": "baixa",
                "categoria": "estilo",
                "linha": str(i),
                "descricao": (
                    f"Linha com {len(linha)} caracteres excede o limite "
                    f"de {LIMITE_LINHA_LONGA}."
                ),
                "sugestao": "Quebre a linha para melhorar a legibilidade.",
            })
    return achados


def _regra_import_wildcard(linhas: list[str]) -> list[dict]:
    """Detecta imports do tipo `from x import *`, que poluem o namespace."""
    achados = []
    padrao = re.compile(r"^\s*from\s+[\w.]+\s+import\s+\*")
    for i, linha in enumerate(linhas, start=1):
        if padrao.search(linha):
            achados.append({
                "severidade": "media",
                "categoria": "estilo",
                "linha": str(i),
                "descricao": "Import com '*' importa nomes de forma implícita.",
                "sugestao": "Importe apenas os nomes necessários, de forma explícita.",
            })
    return achados


def _regra_multiplas_instrucoes(linhas: list[str]) -> list[dict]:
    """Detecta múltiplas instruções na mesma linha separadas por ';'."""
    achados = []
    for i, linha in enumerate(linhas, start=1):
        sem_comentario = linha.split("#", 1)[0]
        # Ignora ';' dentro de strings simples e no fim da linha.
        if '"' in sem_comentario or "'" in sem_comentario:
            continue
        if ";" in sem_comentario.rstrip().rstrip(";"):
            achados.append({
                "severidade": "baixa",
                "categoria": "estilo",
                "linha": str(i),
                "descricao": "Múltiplas instruções na mesma linha (uso de ';').",
                "sugestao": "Coloque cada instrução em sua própria linha.",
            })
    return achados


def _regra_arquivo_extenso(linhas: list[str]) -> list[dict]:
    """Sinaliza arquivos longos, que tendem a concentrar responsabilidades."""
    total = len(linhas)
    if total <= LIMITE_ARQUIVO_EXTENSO:
        return []
    return [{
        "severidade": "baixa",
        "categoria": "manutenibilidade",
        "linha": "N/A",
        "descricao": (
            f"Arquivo com {total} linhas excede {LIMITE_ARQUIVO_EXTENSO}; "
            "pode concentrar responsabilidades demais."
        ),
        "sugestao": "Considere dividir o arquivo em módulos menores e coesos.",
    }]
