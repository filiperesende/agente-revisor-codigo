"""Arquivo de exemplo com problemas propositais, para demonstrar o agente."""

API_KEY = "sk-1234567890abcdef"  # credencial fixa (problema de segurança)


def dividir(a, b):
    return a / b  # não trata divisão por zero


def buscar_usuario(lista, id):
    for u in lista:
        if u["id"] == id:
            return u
    # TODO: tratar usuário não encontrado


def processar(entrada):
    try:
        resultado = eval(entrada)  # uso perigoso de eval
        print(resultado)  # print de diagnóstico
        return resultado
    except:  # except genérico
        pass


def verificar(valor):
    if valor == None:  # comparação com None usando ==
        return False
    return True
