"""
Política de autonomia do agente.

Define, de forma explícita e centralizada, o que o agente pode fazer sozinho,
o que é bloqueado e o que depende de aprovação humana. Manter essa política
separada da lógica dos nós deixa a governança auditável e fácil de explicar.

Níveis de autonomia:
  - AUTOMATICO: a ação é executada sem intervenção.
  - APROVACAO:  a ação só é executada após confirmação humana explícita.
  - BLOQUEADO:  a ação nunca é executada por este agente.
"""

from __future__ import annotations

AUTOMATICO = "automatico"
APROVACAO = "aprovacao"
BLOQUEADO = "bloqueado"

# Tabela de política por ação. Serve também como documentação viva da
# governança (é usada no README e pode ser impressa pela CLI).
POLITICA_AUTONOMIA: dict[str, dict] = {
    "ler_arquivo": {
        "nivel": AUTOMATICO,
        "descricao": "Leitura de arquivo de código dentro das extensões e limites permitidos.",
    },
    "analisar_codigo": {
        "nivel": AUTOMATICO,
        "descricao": "Análise por IA e por regras determinísticas.",
    },
    "gravar_relatorio_local": {
        "nivel": AUTOMATICO,
        "descricao": "Escrita do relatório em Markdown dentro da sandbox reports/.",
    },
    "notificacao_externa": {
        "nivel": APROVACAO,
        "descricao": (
            "Envio do resultado a um serviço externo (webhook do Discord). "
            "Exige aprovação humana quando o nível de risco é alto."
        ),
        "condicao": "requer aprovação apenas quando nivel_risco == 'alto'",
    },
    "destino_externo_nao_autorizado": {
        "nivel": BLOQUEADO,
        "descricao": "Envio a qualquer host fora da allowlist do Discord (proteção anti-SSRF).",
    },
}


def nivel_da_acao(acao: str) -> str:
    """Retorna o nível de autonomia configurado para uma ação."""
    entrada = POLITICA_AUTONOMIA.get(acao)
    return entrada["nivel"] if entrada else BLOQUEADO


def requer_aprovacao(acao: str, contexto: dict | None = None) -> bool:
    """
    Decide se uma ação exige aprovação humana no contexto atual.

    Regra específica de `notificacao_externa`: só exige aprovação quando o
    nível de risco da execução é alto. Ações marcadas como APROVACAO em
    qualquer situação retornam True; ações BLOQUEADO também retornam True
    (nunca devem seguir sem decisão explícita).
    """
    contexto = contexto or {}
    nivel = nivel_da_acao(acao)

    if nivel == AUTOMATICO:
        return False
    if acao == "notificacao_externa":
        return contexto.get("nivel_risco") == "alto"
    return True  # APROVACAO (genérico) ou BLOQUEADO


def acao_permitida(acao: str) -> bool:
    """Indica se a ação é permitida (não bloqueada) por política."""
    return nivel_da_acao(acao) != BLOQUEADO


def descrever_politica() -> str:
    """Devolve um resumo textual da política, para logs, CLI e documentação."""
    linhas = ["Política de autonomia:"]
    for acao, cfg in POLITICA_AUTONOMIA.items():
        linhas.append(f"  - {acao} [{cfg['nivel']}]: {cfg['descricao']}")
    return "\n".join(linhas)
