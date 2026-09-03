"""O número de série de um aparelho não entra em arquivo versionado.

O PEDIDO É DELA — 03/09/2026. Ao ver o serial do controle dela aparecer numa
leitura de ``daemon.state_full``, a pergunta foi *"vale um portão para número de
série?"*, e a resposta foi **sim, faz o portão pro número de série**.

**A CASA JÁ SABIA QUE FALTAVA, e pagou por isso.** A docstring de
``cor_do_plastico.mascarar_serial`` registra, com data:

    *"Ele já foi escrito com o serial VERDADEIRO de um dos controles da bancada
    — a docstring da função que mascara serial era, ela mesma, o vazamento, e o
    `check_anonymity.sh` passava verde porque varre a forma de um MAC, não a de
    um serial (15/08/2026)."*

O serial de fábrica identifica a unidade dela **tão bem quanto o MAC**, e a
regra desta casa é sobre ARQUIVO VERSIONADO — não sobre a palavra "MAC".

**POR FORMA, E NUNCA POR LISTA.** Listar os seriais reais seria exatamente o
vazamento que o portão existe para impedir. É a mesma razão que
``test_anonimato_de_fixtures`` escreve para o endereço de rádio.

A MORDIDA: este arquivo escreve um serial com a FORMA de aparelho num arquivo de
mentira e exige que o portão o acuse; e escreve o mascarado, e exige que passe.

E HÁ DUAS RÉGUAS DE SERIAL, o que é regra desta casa e não redundância — a mesma
razão que sustenta as duas de MAC. A distinção, medida em 03/09/2026:

* ``test_docs_mac_anonimato.py::test_nenhum_serial_de_fabrica_real_no_repo`` é a
  AUTORITATIVA. Ela existe desde 15/08, mede a forma EXATA de um DualSense
  (``[A-Z][A-Z0-9]{16}``, com dígito nas posições que a fábrica usa) e alcança
  três formas de escrita: texto, hexdump com o serial atravessando a quebra de
  linha, e corrida hexadecimal colada. É ela que acusou o forjado deste arquivo
  quando ele nasceu com um valor próprio.
* ``scripts/check_numero_de_serie.py`` é a RÁPIDA e a LARGA. Ela mede só texto,
  mas de 15 a 20 caracteres — o que alcança serial de aparelho que NÃO é
  DualSense (8BitDo, Pro Controller) —, e custa 1,2 s contra os 12 s da outra.

O QUE ISSO COMPRA, e é a lição que 03/09 pagou duas vezes: a autoritativa é
teste de SUÍTE, e a suíte roda no FIM. Entre o commit que vaza e a reprovação
havia um dia inteiro de trabalho — foi assim com os 37 endereços de rádio crus
desta manhã. A rápida reprova antes do commit.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts/check_numero_de_serie.py"


def _carregar():
    """O portão, importado do fonte — nunca uma cópia da regra."""
    spec = importlib.util.spec_from_file_location("_serial", PORTAO)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_serial"] = mod
    spec.loader.exec_module(mod)
    return mod


PORTA = _carregar()

#: O FORJADO CANÔNICO DESTA CASA, e ele é reusado de propósito: já vive na
#: lista `ruido` de ``test_docs_mac_anonimato.py`` desde 15/08/2026, e inventar
#: um segundo obrigaria a manter DUAS listas de isenção para a mesma regra.
#:
#: Ele tem a forma de um serial de aparelho — dezessete caracteres, maiúsculas e
#: dígitos —, mas o prefixo `ZZ9Y` não sai de fábrica nenhuma.
FORJADO_COM_A_FORMA = "ZZ9Y02Q0000000000"  # serial-de-mentira: o forjado da casa


def _acusa(texto: str, tmp_path: pathlib.Path) -> list[str]:
    alvo = tmp_path / "algum_arquivo.py"
    alvo.write_text(texto, encoding="utf-8")
    return PORTA.acusa(alvo)


def test_um_serial_com_a_forma_e_acusado(tmp_path: pathlib.Path) -> None:
    """A forma de dezessete de um DualSense reprova."""
    achados = _acusa(f'SERIAL = "{FORJADO_COM_A_FORMA}"\n', tmp_path)
    assert achados, (
        "o portão deixou passar um token com a forma exata do serial de um "
        "DualSense — dezessete caracteres, letras e dígitos misturados")


def test_o_acusado_nao_e_reimpresso_inteiro_na_mensagem(tmp_path: pathlib.Path) -> None:
    """A mensagem do portão não pode reimprimir o serial inteiro.

    Um portão de anonimato que ECOA o segredo na reprovação vaza pelo log do
    CI, que é público. Ele diz os seis primeiros — os mesmos que a máscara
    deixa à mostra — e o tamanho.
    """
    achados = _acusa(f'SERIAL = "{FORJADO_COM_A_FORMA}"\n', tmp_path)
    junto = " ".join(achados)
    assert FORJADO_COM_A_FORMA not in junto, (
        f"a mensagem do portão reimprime o serial inteiro: {junto}")
    assert FORJADO_COM_A_FORMA[:6] in junto, (
        "a mensagem não diz nem o prefixo — quem lê não acha a linha")


def test_o_mascarado_passa(tmp_path: pathlib.Path) -> None:
    """O que já está mascarado não é vazamento — e a máscara tem dono."""
    sys.path.insert(0, str(RAIZ / "scripts/ensaios"))
    from cor_do_plastico import mascarar_serial

    mascarado = mascarar_serial(FORJADO_COM_A_FORMA)
    assert "#" in mascarado, "a máscara mudou de forma"
    assert not _acusa(f'SERIAL = "{mascarado}"\n', tmp_path)


def test_a_marca_de_mentira_isenta_a_linha(tmp_path: pathlib.Path) -> None:
    """`serial-de-mentira` na MESMA linha isenta o token."""
    linha = f'S = "{FORJADO_COM_A_FORMA}"  # serial-de-mentira: forjado no teste\n'
    assert not _acusa(linha, tmp_path)


def test_a_marca_na_linha_de_baixo_nao_isenta(tmp_path: pathlib.Path) -> None:
    """A varredura é por LINHA, e a marca fora dela não alcança nada.

    Sem esta prova a convenção seria só uma frase no docstring — e a primeira
    pessoa que a escrevesse na linha de baixo teria um portão vermelho e
    nenhuma pista do porquê.
    """
    texto = (f'S = "{FORJADO_COM_A_FORMA}"\n'
             "# serial-de-mentira: escrito no lugar errado\n")
    assert _acusa(texto, tmp_path), (
        "a marca na linha de baixo isentou o token — a varredura deixou de ser "
        "por linha, e a mensagem do portão ensina o contrário")


@pytest.mark.parametrize("token,porque", [
    ("CONFIGURACAOPADRAODE", "sigla longa, sem dígito que baste"),
    ("20260903150000000", "carimbo de tempo: só dígito"),
    ("0000000000C2CEF2", "endereço de buffer de um log do Proton"),
])
def test_o_que_nao_e_serial_nao_reprova(token: str, porque: str,
                                        tmp_path: pathlib.Path) -> None:
    """Um portão que acusa o que não é o defeito é um portão que alguém desliga.

    Os três vêm da árvore de verdade — o terceiro apareceu na varredura de
    calibração, num fixture de log.
    """
    assert not _acusa(f'X = "{token}"\n', tmp_path), (
        f"o portão acusou o que não é serial: {porque}")


def test_o_hexadecimal_sem_a_fileira_de_zeros_continua_acusado(
        tmp_path: pathlib.Path) -> None:
    """A isenção do endereço de memória exige as DUAS condições.

    Só-hexadecimal **e** uma fileira de seis zeros. Aceitar qualquer coisa
    hexadecimal abriria a porta larga: um serial que por acaso só use A-F
    passaria, e é justamente o caso que a isenção não pode cobrir.
    """
    # serial-de-mentira: o valor abaixo é o caso-limite deste próprio teste
    assert _acusa('X = "ABCDEF1234567890"\n', tmp_path), (  # serial-de-mentira
        "um token só-hexadecimal SEM fileira de zeros foi isentado — a "
        "isenção do endereço de memória virou porta larga")


def test_a_arvore_de_hoje_esta_limpa() -> None:
    """E o portão roda sobre a árvore de verdade, sem achar nada.

    É a metade que impede a régua de passar por vacuidade: as provas acima
    medem arquivos de mentira, e esta mede o repositório.
    """
    violacoes: list[str] = []
    for caminho in PORTA.arquivos_versionados():
        violacoes.extend(PORTA.acusa(caminho))
    assert not violacoes, (
        "há serial de aparelho sem máscara na árvore:\n  "
        + "\n  ".join(violacoes[:10]))
