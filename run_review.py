"""
CLI do Agente Revisor de Código.

Uso:
    python run_review.py <caminho_do_arquivo>

Exemplo:
    python run_review.py examples/exemplo_com_bugs.py

Carrega variáveis de ambiente do arquivo .env (se existir), executa o agente
LangGraph sobre o arquivo informado e imprime um resumo. O relatório completo
é gravado em reports/.
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

from src.agent import revisar_arquivo
from src.llm import usando_gemini


def main(argv: list[str]) -> int:
    load_dotenv()  # carrega GOOGLE_API_KEY / GEMINI_API_KEY do .env, se houver

    if len(argv) < 2:
        print("Uso: python run_review.py <caminho_do_arquivo>")
        return 2

    caminho = argv[1]
    motor = "Gemini (real)" if usando_gemini() else "Mock (heurístico, sem chave)"
    print(f"🔎 Revisando: {caminho}")
    print(f"⚙️  Motor de análise: {motor}\n")

    estado = revisar_arquivo(caminho)

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

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
