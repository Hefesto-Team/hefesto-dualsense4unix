"""O neutralizador só troca o «ela» que é a pessoa (AS-FERRAMENTAS-DE-MANUTENCAO-...-01).

A regra «ela VERBO» casa por palavra. Quando a frase já pôs antes um substantivo feminino
técnico (a carona, a cura), o «ela» é o pronome dele, e trocá-lo por «o usuário» diz outra
coisa. As frases abaixo são escritas à mão: nenhuma régua lê arquivo do produto, porque o
texto do produto é justamente o que a outra sprint reescreve.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "neutralizar-o-texto.py"


def _modulo() -> Any:
    spec = importlib.util.spec_from_file_location("neutralizar_o_texto_do_pronome", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# A forma da frase de `cura_por_estrada.py`: o substantivo e o «ela» na mesma frase, com
# dois-pontos no meio (eles não fecham a frase).
DA_CARONA = '''def lancadores():
    """O que a carona devolve: os lançadores em que ela escreveu.

    É uma tupla.
    """
'''

# A forma da frase de `quem_gravou_o_brilho.py`: a pessoa dizendo, sem substantivo técnico antes.
DA_PESSOA = '''"""Lê as cópias do perfil e diz quem gravou o brilho.

Nasceu da queixa do brilho baixo (ela disse «Não fui eu» sobre o 8%).
"""
'''


def test_o_ela_da_carona_nao_vira_o_usuario() -> None:
    modulo = _modulo()
    assert modulo.reescrever_arquivo(DA_CARONA, "py") == DA_CARONA
    frase = "# a carona devolve: os lançadores em que ela escreveu"
    assert modulo.reescrever_prosa(frase) == frase


def test_o_ela_da_cura_nao_vira_o_usuario() -> None:
    modulo = _modulo()
    frase = "# a cura roda uma vez, e depois ela escreveu no arquivo"
    assert modulo.reescrever_prosa(frase) == frase


def test_o_ela_da_maiuscula_e_da_quebra_de_comentario_tambem_fica() -> None:
    modulo = _modulo()
    quebrado = "# a carona devolve os lançadores\n# em que ela escreveu\n"
    assert modulo.reescrever_prosa(quebrado) == quebrado
    gritado = "# a carona devolve o que ELA escreveu"
    assert modulo.reescrever_prosa(gritado) == gritado


def test_a_frase_que_continua_na_linha_de_comentario_de_baixo_tambem_fica() -> None:
    """No arquivo, cada linha de comentário de Python e de shell é um trecho à parte.

    A guarda lê as linhas de cima do mesmo bloco: sem isso a frase quebrada em duas
    linhas passava pelo `reescrever_prosa` e era trocada pelo `reescrever_arquivo`.
    """
    modulo = _modulo()
    em_py = (
        "def f():\n    # a carona devolve os lançadores\n    # em que ela escreveu\n    return 1\n"
    )
    assert modulo.reescrever_arquivo(em_py, "py") == em_py
    em_sh = "# a cura roda uma vez, e depois\n# ela escreveu no arquivo\n"
    assert modulo.reescrever_arquivo(em_sh, "sh") == em_sh
    # o bloco acaba no código ou na linha em branco, e a guarda acaba com ele
    com_codigo = "# a carona devolve os lançadores\nx = 1\n# ela pediu o contrário\n"
    trocado = com_codigo.replace("ela pediu", "o usuário pediu")
    assert modulo.reescrever_arquivo(com_codigo, "py") == trocado
    com_vazia = "# a carona devolve os lançadores\n\n# ela pediu o contrário\n"
    trocado = com_vazia.replace("ela pediu", "o usuário pediu")
    assert modulo.reescrever_arquivo(com_vazia, "sh") == trocado


def test_o_ela_da_pessoa_continua_trocado() -> None:
    modulo = _modulo()
    novo = modulo.reescrever_arquivo(DA_PESSOA, "py")
    assert "o usuário disse «Não fui eu»" in novo
    assert "ela disse" not in novo
    assert modulo.reescrever_prosa("# ela pediu o contrário") == "# o usuário pediu o contrário"


def test_o_substantivo_de_outra_frase_nao_protege_o_ela() -> None:
    """A guarda é da MESMA frase: ponto final ou linha em branco a encerra."""
    modulo = _modulo()
    assert modulo.reescrever_prosa("# a carona devolve o resto. Ela disse que sim") == (
        "# a carona devolve o resto. O usuário disse que sim"
    )
    assert modulo.reescrever_prosa("# a cura roda\n#\n# ela pediu o contrário") == (
        "# a cura roda\n#\n# o usuário pediu o contrário"
    )


def test_o_substantivo_que_nao_e_da_lista_nao_protege() -> None:
    """A lista é curta e medida: «sprint» fica fora dela, e o narrador continua achado."""
    modulo = _modulo()
    assert modulo.reescrever_prosa("# nasceu da sprint X (ela disse que não)") == (
        "# nasceu da sprint X (o usuário disse que não)"
    )


def test_o_que_ela_declarou_vira_o_que_o_usuario_declarou() -> None:
    """A forma «que ela VERBO» (declarou, deu, ensinou, tirou, dispensou) é a pessoa."""
    modulo = _modulo()
    assert modulo.reescrever_prosa("# o nome que ela deu ao controle") == (
        "# o nome que o usuário deu ao controle"
    )
    assert modulo.reescrever_prosa("# o que ela declarou da entrada") == (
        "# o que o usuário declarou da entrada"
    )
    # a carona da mesma frase é o antecedente do «ela»: fica
    da_carona = "# a carona devolve o que ela declarou da entrada"
    assert modulo.reescrever_prosa(da_carona) == da_carona


def test_a_data_do_dela_entre_parenteses_perde_so_a_pessoa() -> None:
    """O pronome entre parênteses antes da data sai, e a data fica."""
    modulo = _modulo()
    assert modulo.reescrever_prosa("# a ordem (dela, 02/10/2026) vale") == (
        "# a ordem (02/10/2026) vale"
    )
    assert modulo.reescrever_prosa("# a ordem (dela, 02/10) vale") == "# a ordem (02/10) vale"
