"""
CLI do Agente Revisor de Código.

Uso:
    python run_review.py <caminho_do_arquivo> [--aprovar]

Exemplos:
    python run_review.py examples/exemplo_com_bugs.py
    python run_review.py examples/exemplo_com_bugs.py --aprovar

Carrega variáveis de ambiente do arquivo .env (se existir), executa o agente
LangGraph sobre o arquivo informado e imprime um resumo. O relatório completo
é gravado em reports/.

Governança: quando a revisão tem risco alto, o envio da notificação externa
(Discord) exige aprovação humana. Sem a flag `--aprovar`, a CLI pergunta antes
de enviar; a opção segura por padrão é NÃO enviar.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from src import notificacao
from src.agent import revisar_arquivo
from src.llm import usando_gemini
from src.nodes import montar_payload_notificacao


def _confirmar_envio(interativo: bool) -> bool:
    """Pergunta ao usuário se deve enviar a notificação externa.

    Em ambiente não interativo (sem terminal), retorna False — a decisão
    segura por padrão é não enviar sem aprovação explícita.
    """
    if not interativo:
        print("   (ambiente não interativo: envio não aprovado por padrão)")
        return False
    try:
        resposta = input("   Enviar notificação externa mesmo assim? [s/N]: ")
    except EOFError:
        return False
    return resposta.strip().lower() in {"s", "sim", "y", "yes"}


def main(argv: list[str]) -> int:
    load_dotenv()  # carrega GOOGLE_API_KEY / GEMINI_API_KEY do .env, se houver

    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}

    if not args:
        print("Uso: python run_review.py <caminho_do_arquivo> [--aprovar]")
        return 2

    caminho = args[0]
    auto_aprovar = "--aprovar" in flags

    motor = "Gemini (real)" if usando_gemini() else "Mock (heurístico, sem chave)"
    print(f"🔎 Revisando: {caminho}")
    print(f"⚙️  Motor de análise: {motor}\n")

    estado = revisar_arquivo(caminho, aprovacao_concedida=auto_aprovar)

    # Validação falhou: mostra os erros e encerra com código != 0.
    if not estado.get("valido", False):
        print("❌ Não foi possível revisar o arquivo:")
        for erro in estado.get("erros", []):
            print(f"   - {erro}")
        return 1

    contexto = estado.get("contexto", {})
    achados = estado.get("achados", [])
    nivel_risco = contexto.get("nivel_risco", "normal")
    print(f"📄 Linguagem: {contexto.get('linguagem')}")
    print(f"📏 Linhas: {contexto.get('total_linhas')}")
    print(
        f"🐛 Problemas encontrados: {len(achados)} "
        f"(IA={contexto.get('achados_ia', 0)}, estática={contexto.get('achados_estatica', 0)})"
    )
    if nivel_risco == "alto":
        print("⚠️  Nível de risco: ALTO — recomenda-se revisão humana.")

    for a in achados:
        print(f"   [{a['severidade'].upper()}] linha {a['linha']}: {a['descricao']}")

    if estado.get("caminho_relatorio"):
        print(f"\n✅ Relatório salvo em: {estado['caminho_relatorio']}")

    _tratar_notificacao(estado)

    metricas = estado.get("metricas") or {}
    if metricas:
        print(
            f"\n📊 run_id={metricas.get('run_id')} | "
            f"latência total: {metricas.get('latencia_total_ms')} ms "
            f"({metricas.get('total_nos')} nós) | logs: logs/agent.jsonl"
        )
    return 0


def _tratar_notificacao(estado) -> None:
    """Exibe o status da notificação e aplica o gate de aprovação humana."""
    notif = estado.get("notificacao")
    if not notif:
        return

    # Gate: o grafo pausou o envio porque o risco é alto e não houve aprovação.
    if notif.get("status") == "aguardando_aprovacao":
        print(f"\n🔒 Aprovação necessária: {notif.get('motivo')}")
        if _confirmar_envio(interativo=sys.stdin.isatty()):
            resultado = notificacao.enviar_notificacao(montar_payload_notificacao(estado))
            _imprimir_status_notificacao(resultado)
        else:
            print("🚫 Notificação NÃO enviada (bloqueada por decisão humana).")
        return

    _imprimir_status_notificacao(notif)


def _imprimir_status_notificacao(notif: dict) -> None:
    icones = {"enviado": "📣", "pulado": "⏭️", "falha": "⚠️", "invalido": "⛔"}
    icone = icones.get(notif.get("status"), "•")
    detalhe = notif.get("motivo") or f"tentativas={notif.get('tentativas', 1)}"
    print(f"{icone} Notificação Discord: {notif.get('status')} ({detalhe})")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
