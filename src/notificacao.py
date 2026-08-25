"""
Tool de notificação externa via webhook do Discord.

Esta é a tool integrada por webhook exigida pelo projeto (critério 8). Ela
recebe o resumo de uma revisão, valida o payload com um schema Pydantic e
envia uma mensagem formatada (embed) para um canal do Discord.

Controles aplicados:
  - Validação de schema do payload (Pydantic) antes de qualquer envio.
  - Validação da URL de destino: só aceita webhooks HTTPS do Discord, evitando
    que dados da revisão sejam enviados a endpoints arbitrários (anti-SSRF).
  - Timeout por requisição e retry limitado com backoff.
  - Skip gracioso: se a variável de ambiente não estiver configurada, a etapa é
    pulada sem erro, mantendo o agente demonstrável offline.

O segredo (URL do webhook) NUNCA é escrito em código: vem só do ambiente.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field, ValidationError

# --- Limites e política da tool ---
TIMEOUT_PADRAO = 10          # segundos por requisição
TENTATIVAS_PADRAO = 3        # nº máximo de tentativas (retry limitado)
HOSTS_PERMITIDOS = {"discord.com", "discordapp.com", "canary.discord.com"}
PREFIXO_CAMINHO = "/api/webhooks/"

# Cores dos embeds por nível de risco (formato inteiro do Discord).
CORES = {"alto": 0xE74C3C, "normal": 0x2ECC71}


class PayloadNotificacao(BaseModel):
    """Schema do payload aceito pela tool. Valida tipos e limites."""

    arquivo: str = Field(min_length=1)
    linguagem: str = Field(min_length=1)
    total_achados: int = Field(ge=0)
    por_severidade: dict[str, int] = Field(default_factory=dict)
    nivel_risco: str = Field(default="normal")
    caminho_relatorio: str | None = None


class NotificacaoError(Exception):
    """Erro controlado emitido pela tool de notificação."""


def _obter_webhook_url() -> str | None:
    """Lê a URL do webhook do Discord do ambiente (nunca do código)."""
    return os.getenv("DISCORD_WEBHOOK_URL") or None


def esta_configurado() -> bool:
    """Indica se há uma URL de webhook configurada no ambiente."""
    return _obter_webhook_url() is not None


def _validar_url(url: str) -> None:
    """
    Garante que a URL é um webhook HTTPS legítimo do Discord.

    Bloqueia qualquer outro destino para evitar vazamento de dados da revisão
    para endpoints não autorizados (proteção contra SSRF/exfiltração).
    """
    partes = urlparse(url)
    if partes.scheme != "https":
        raise NotificacaoError("A URL do webhook deve usar HTTPS.")
    if partes.hostname not in HOSTS_PERMITIDOS:
        raise NotificacaoError(
            f"Host '{partes.hostname}' não é um webhook do Discord permitido."
        )
    if not partes.path.startswith(PREFIXO_CAMINHO):
        raise NotificacaoError("A URL não tem o formato de webhook do Discord.")


def montar_mensagem_discord(payload: PayloadNotificacao) -> dict:
    """Constrói o corpo (embed) da mensagem do Discord a partir do payload."""
    por_sev = payload.por_severidade
    resumo_sev = (
        f"🔴 {por_sev.get('alta', 0)}  "
        f"🟡 {por_sev.get('media', 0)}  "
        f"🟢 {por_sev.get('baixa', 0)}"
    )
    risco = payload.nivel_risco.lower()
    titulo = "🔎 Revisão de Código concluída"
    if risco == "alto":
        titulo = "⚠️ Revisão de Código — RISCO ALTO"

    campos = [
        {"name": "Arquivo", "value": f"`{payload.arquivo}`", "inline": True},
        {"name": "Linguagem", "value": payload.linguagem, "inline": True},
        {"name": "Total de achados", "value": str(payload.total_achados), "inline": True},
        {"name": "Severidade", "value": resumo_sev, "inline": False},
        {"name": "Nível de risco", "value": risco.upper(), "inline": True},
    ]
    if payload.caminho_relatorio:
        campos.append(
            {"name": "Relatório", "value": f"`{payload.caminho_relatorio}`", "inline": False}
        )

    return {
        "embeds": [
            {
                "title": titulo,
                "color": CORES.get(risco, CORES["normal"]),
                "fields": campos,
            }
        ]
    }


def enviar_notificacao(
    payload_bruto: dict,
    *,
    timeout: int = TIMEOUT_PADRAO,
    tentativas: int = TENTATIVAS_PADRAO,
) -> dict:
    """
    Envia a notificação da revisão para o Discord.

    Retorna sempre um dicionário de status (não levanta exceção para o grafo),
    com um dos estados:
      - "pulado":  webhook não configurado.
      - "invalido": payload ou URL inválidos (não envia).
      - "enviado":  sucesso.
      - "falha":    todas as tentativas falharam (rede/HTTP).
    """
    url = _obter_webhook_url()
    if not url:
        return {"status": "pulado", "motivo": "DISCORD_WEBHOOK_URL não configurada."}

    # 1) Validação de schema e de destino antes de qualquer chamada externa.
    try:
        payload = PayloadNotificacao(**payload_bruto)
        _validar_url(url)
    except ValidationError as exc:
        return {"status": "invalido", "motivo": f"Payload inválido: {exc.error_count()} erro(s)."}
    except NotificacaoError as exc:
        return {"status": "invalido", "motivo": str(exc)}

    corpo = montar_mensagem_discord(payload)

    # 2) Envio com retry limitado e backoff exponencial simples.
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.post(url, json=corpo, timeout=timeout)
            if resp.status_code in (200, 204):
                return {"status": "enviado", "tentativas": tentativa, "http_status": resp.status_code}
            # 429 (rate limit) e 5xx são transitórios: vale tentar de novo.
            ultimo_erro = f"HTTP {resp.status_code}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                break  # erro não recuperável (ex.: 401/404): não insiste.
        except requests.RequestException as exc:
            ultimo_erro = f"{type(exc).__name__}: {exc}"

        if tentativa < tentativas:
            time.sleep(min(2 ** (tentativa - 1), 4))  # backoff: 1s, 2s, 4s...

    return {"status": "falha", "motivo": ultimo_erro, "tentativas": tentativas}
