"""
Camada de LLM do agente.

Se houver uma chave de API do Gemini no ambiente (GOOGLE_API_KEY ou
GEMINI_API_KEY), usa o modelo real via `langchain-google-genai`. Caso
contrário, cai automaticamente para um cliente MOCK baseado em heurísticas,
para que o agente funcione e seja demonstrável sem depender de chave.

A chave NUNCA é escrita em código: é lida apenas de variáveis de ambiente.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

CAMINHO_PROMPT = Path(__file__).parent / "prompts" / "revisao_codigo.md"

# Modelo padrão. Pode ser sobrescrito pela variável de ambiente GEMINI_MODEL,
# sem alterar o código (requisito 4.10 do projeto).
MODELO_GEMINI_PADRAO = "gemini-3.6-flash"


def obter_modelo() -> str:
    """Nome do modelo Gemini, configurável por variável de ambiente."""
    return os.getenv("GEMINI_MODEL", MODELO_GEMINI_PADRAO)


def carregar_template_prompt() -> str:
    """Lê o template de prompt de revisão a partir do arquivo do projeto."""
    return CAMINHO_PROMPT.read_text(encoding="utf-8")


def _obter_chave_api() -> str | None:
    """Busca a chave do Gemini nas variáveis de ambiente aceitas."""
    return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")


def usando_gemini() -> bool:
    """Indica se o agente vai usar o Gemini real (True) ou o mock (False)."""
    return _obter_chave_api() is not None


def _extrair_json(texto: str) -> list[dict]:
    """
    Extrai um array JSON de uma resposta de LLM de forma tolerante.

    Modelos às vezes embrulham o JSON em ```json ... ``` ou adicionam texto.
    """
    texto = texto.strip()
    # Remove cercas de código markdown, se houver.
    texto = re.sub(r"^```(?:json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()

    inicio = texto.find("[")
    fim = texto.rfind("]")
    if inicio == -1 or fim == -1 or fim < inicio:
        return []
    try:
        dados = json.loads(texto[inicio : fim + 1])
        return dados if isinstance(dados, list) else []
    except json.JSONDecodeError:
        return []


def _texto_da_resposta(content) -> str:
    """
    Normaliza o conteúdo da resposta do modelo para texto.

    Versões recentes do Gemini retornam o conteúdo como uma lista de blocos
    (ex.: [{"type": "text", "text": "..."}]) em vez de uma string simples.
    Esta função extrai o texto em ambos os formatos.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        partes = []
        for bloco in content:
            if isinstance(bloco, dict):
                partes.append(bloco.get("text", ""))
            elif isinstance(bloco, str):
                partes.append(bloco)
        return "".join(partes)
    return str(content)


def analisar_com_gemini(codigo: str, contexto: dict) -> list[dict]:
    """Chama o Gemini para revisar o código e retorna a lista de achados."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    template = carregar_template_prompt()
    prompt = template.format(
        linguagem=contexto.get("linguagem", "Desconhecida"),
        caminho=contexto.get("caminho_arquivo", ""),
        total_linhas=contexto.get("total_linhas", 0),
        codigo=codigo,
    )

    modelo = ChatGoogleGenerativeAI(
        model=obter_modelo(),
        google_api_key=_obter_chave_api(),
        temperature=0,
    )
    resposta = modelo.invoke(prompt)
    return _extrair_json(_texto_da_resposta(resposta.content))


def analisar_com_mock(codigo: str, contexto: dict) -> list[dict]:
    """
    Cliente MOCK: heurísticas simples para simular a revisão sem chave de API.

    Não substitui o LLM real, mas garante que o fluxo do agente seja
    demonstrável offline e nos testes.
    """
    achados: list[dict] = []
    linhas = codigo.splitlines()

    padroes = [
        (r"\beval\s*\(", "seguranca", "alta",
         "Uso de eval() pode executar código arbitrário.",
         "Evite eval(); use alternativas seguras como json.loads ou ast.literal_eval."),
        (r"(?i)(api_key|senha|password|secret|token)\s*=\s*['\"][^'\"]+['\"]",
         "seguranca", "alta",
         "Possível credencial fixa no código (hardcoded).",
         "Mova segredos para variáveis de ambiente (.env) e não versione."),
        (r"except\s*:", "bug", "media",
         "Bloco except genérico captura todos os erros silenciosamente.",
         "Capture exceções específicas e trate ou registre o erro."),
        (r"\bprint\s*\(", "estilo", "baixa",
         "Uso de print() para diagnóstico.",
         "Prefira a biblioteca logging em código de produção."),
        (r"==\s*None|!=\s*None", "estilo", "baixa",
         "Comparação com None usando == ou !=.",
         "Use 'is None' / 'is not None'."),
        (r"\bTODO\b|\bFIXME\b", "estilo", "baixa",
         "Marcador TODO/FIXME pendente.",
         "Resolva a pendência ou registre uma issue rastreável."),
    ]

    for i, linha in enumerate(linhas, start=1):
        for regex, categoria, severidade, descricao, sugestao in padroes:
            if re.search(regex, linha):
                achados.append({
                    "severidade": severidade,
                    "categoria": categoria,
                    "linha": str(i),
                    "descricao": descricao,
                    "sugestao": sugestao,
                })

    return achados


def analisar_codigo(codigo: str, contexto: dict) -> tuple[list[dict], str]:
    """
    Ponto de entrada da análise. Escolhe Gemini ou mock automaticamente.

    Retorna (achados, motor_utilizado). Se o Gemini falhar em tempo de
    execução, cai para o mock para não interromper o fluxo do agente.
    """
    if usando_gemini():
        try:
            return analisar_com_gemini(codigo, contexto), "gemini"
        except Exception:  # noqa: BLE001 — fallback resiliente e documentado
            return analisar_com_mock(codigo, contexto), "mock (fallback após erro no Gemini)"
    return analisar_com_mock(codigo, contexto), "mock (sem chave de API)"
