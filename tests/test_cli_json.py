"""
Teste do modo `--json` da CLI (`run_review._saida_json`).

O modo JSON é consumido pela automação low-code (n8n), então a saída precisa ser
um JSON válido com os campos esperados. Testamos o formatador diretamente, sem
executar o agente (rápido e sem rede).
"""

import json

from run_review import _saida_json


class TestSaidaJson:
    def test_saida_valida_contem_campos_esperados(self, capsys):
        estado = {
            "valido": True,
            "run_id": "abc123",
            "contexto": {
                "caminho_arquivo": "examples/x.py",
                "linguagem": "Python",
                "total_achados": 3,
                "por_severidade": {"alta": 1, "media": 0, "baixa": 2},
                "nivel_risco": "alto",
            },
            "caminho_relatorio": "reports/x.md",
            "achados": [1, 2, 3],
        }
        rc = _saida_json(estado)
        dados = json.loads(capsys.readouterr().out)

        assert rc == 0
        assert dados["valido"] is True
        assert dados["arquivo"] == "examples/x.py"
        assert dados["nivel_risco"] == "alto"
        assert dados["total_achados"] == 3
        assert dados["por_severidade"]["alta"] == 1

    def test_saida_invalida_retorna_codigo_erro(self, capsys):
        estado = {"valido": False, "erros": ["arquivo não encontrado"]}
        rc = _saida_json(estado)
        dados = json.loads(capsys.readouterr().out)

        assert rc == 1
        assert dados["valido"] is False
        assert dados["erros"] == ["arquivo não encontrado"]
