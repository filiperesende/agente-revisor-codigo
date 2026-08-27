"""
Testes das validações de entrada e saída (`src/validation.py`).

Cobrem o critério de "validação básica": rejeição de entrada malformada e
normalização defensiva da saída do LLM antes de gerar o relatório.
"""

from src.validation import normalizar_achados, validar_caminho_entrada


class TestValidarCaminhoEntrada:
    def test_caminho_valido_retorna_true(self):
        ok, msg = validar_caminho_entrada("exemplo.py")
        assert ok is True
        assert msg == ""

    def test_caminho_none_retorna_false(self):
        ok, msg = validar_caminho_entrada(None)
        assert ok is False
        assert msg != ""

    def test_caminho_vazio_retorna_false(self):
        ok, msg = validar_caminho_entrada("")
        assert ok is False
        assert msg != ""

    def test_caminho_apenas_espacos_retorna_false(self):
        ok, msg = validar_caminho_entrada("   ")
        assert ok is False
        assert "branco" in msg.lower()

    def test_caminho_nao_string_retorna_false(self):
        ok, msg = validar_caminho_entrada(123)
        assert ok is False
        assert msg != ""


class TestNormalizarAchados:
    def test_entrada_nao_lista_retorna_lista_vazia(self):
        assert normalizar_achados("não é lista") == []
        assert normalizar_achados(None) == []
        assert normalizar_achados({"severidade": "alta"}) == []

    def test_itens_nao_dict_sao_descartados(self):
        brutos = ["texto solto", 42, None, {"descricao": "achado real"}]
        achados = normalizar_achados(brutos)
        assert len(achados) == 1
        assert achados[0]["descricao"] == "achado real"

    def test_severidade_invalida_vira_baixa(self):
        achados = normalizar_achados([{"severidade": "crítica"}])
        assert achados[0]["severidade"] == "baixa"

    def test_severidade_valida_normalizada_para_minuscula(self):
        achados = normalizar_achados([{"severidade": "ALTA"}])
        assert achados[0]["severidade"] == "alta"

    def test_chaves_ausentes_recebem_padroes(self):
        achados = normalizar_achados([{}])
        item = achados[0]
        assert item["severidade"] == "baixa"
        assert item["categoria"] == "geral"
        assert item["linha"] == "N/A"
        assert item["descricao"] == ""
        assert item["sugestao"] == ""

    def test_todas_as_chaves_presentes_na_saida(self):
        achados = normalizar_achados([{"descricao": "x"}])
        assert set(achados[0].keys()) == {
            "severidade", "categoria", "linha", "descricao", "sugestao",
        }

    def test_campos_preservados_e_convertidos_para_texto(self):
        brutos = [{
            "severidade": "media",
            "categoria": "seguranca",
            "linha": 42,
            "descricao": "SQL injection",
            "sugestao": "usar prepared statements",
        }]
        item = normalizar_achados(brutos)[0]
        assert item["severidade"] == "media"
        assert item["categoria"] == "seguranca"
        assert item["linha"] == "42"  # convertido para string
        assert item["descricao"] == "SQL injection"
