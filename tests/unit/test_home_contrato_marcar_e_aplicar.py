"""O portão do contrato MARCAR e APLICAR — I12 da INÍCIO NÃO MENTE-01.

O contrato mora em ``app/actions/contrato_da_mascara.py`` e é só dado. Este
arquivo é a régua que o faz valer: **nenhuma superfície da janela aplica modo
ou máscara além do rodapé**, salvo as exceções registradas com data.

POR QUE A RÉGUA MEDE `apply_mode`, E NÃO A STRING `gamepad.emulation.set`
-------------------------------------------------------------------------

Porque medir a string mediria a coisa errada, e o produto já provou isso: a
HARM-01 tirou o ``gamepad.emulation.set`` CRU da aba Emulação e o fez passar
pelo ``mode_transition``. Uma régua que procurasse a string daria a Emulação
por curada — ela não a escreve mais — enquanto a aba continua APLICANDO no
clique. O gesto é `apply_mode`; a string é só o último degrau dele.

O "ANTES" ESTÁ AQUI DENTRO, E É EXECUTÁVEL
-------------------------------------------

Hoje o portão **passaria vazio** se não houvesse registro: a Emulação aplica.
Ela está em ``EXCECOES_QUE_APLICAM_HOJE``, com data e razão, e há duas réguas
sobre esse registro:

* ``test_a_excecao_registrada_ainda_e_uma_excecao`` — se a Emulação parar de
  aplicar, a linha tem de SAIR. Exceção que sobrevive à própria cura vira
  norma;
* ``test_nenhuma_superficie_alem_do_rodape_aplica`` está marcado
  ``xfail(strict=True)``: é o contrato SEM exceção nenhuma. No dia em que a
  onda da Emulação fechar, ele passa, o `strict` reprova, e quem integrar é
  obrigado a apagar o `xfail` e o registro no mesmo gesto.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import contrato_da_mascara as contrato

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
APP = SRC / "app"


def _superficies_que_aplicam() -> dict[str, list[int]]:
    """`{caminho relativo: [linhas]}` de quem chama `apply_mode` dentro de `app/`.

    Só o pacote da JANELA: a CLI tem porta própria (``cmd_gamepad``), e ela não
    é superfície de tela — o contrato desta sprint é sobre o que a pessoa vê e
    clica.
    """
    achados: dict[str, list[int]] = {}
    for arquivo in sorted(APP.rglob("*.py")):
        relativo = str(arquivo.relative_to(SRC)).replace("\\", "/")
        if relativo == contrato.MECANISMO_DA_TRANSICAO:
            # O mecanismo DEFINE `apply_mode`; chamá-lo lá dentro seria a
            # própria implementação, não uma superfície decidindo aplicar.
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        linhas = [
            no.lineno
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and (
                (isinstance(no.func, ast.Name) and no.func.id == "apply_mode")
                or (
                    isinstance(no.func, ast.Attribute)
                    and no.func.attr == "apply_mode"
                )
            )
        ]
        if linhas:
            achados[relativo] = linhas
    return achados


def test_o_contrato_esta_no_disco_e_nomeia_os_dois_gestos() -> None:
    """Antes desta sprint ele existia só na cabeça de quem escreveu."""
    assert contrato.GESTO_MARCAR == "marcar"
    assert contrato.GESTO_APLICAR == "aplicar"
    assert contrato.SUPERFICIE_QUE_APLICA == "app/actions/footer_actions.py"
    assert "app/actions/home_actions.py" in contrato.SUPERFICIES_QUE_MARCAM


def test_a_regua_enxerga_quem_aplica() -> None:
    """Valide o instrumento contra o que você já sabe (A5, 23/08/2026).

    Duas respostas conhecidas: o rodapé aplica (é o dono declarado) e a
    Emulação aplica (é a exceção registrada). Uma varredura que não achasse
    nenhum dos dois deixaria o portão abaixo verde por cegueira.
    """
    quem = _superficies_que_aplicam()
    assert contrato.SUPERFICIE_QUE_APLICA in quem, (
        "a varredura não acha nem o rodapé, que é o dono declarado do gesto de "
        "aplicar. O instrumento está cego, e o verde do portão não vale nada."
    )
    assert "app/actions/emulation_actions.py" in quem, (
        "a varredura não acha a aba Emulação, que a sprint MEDIU aplicando no "
        "clique (`_apply_mode`). Ou a onda dela fechou — e aí o registro de "
        "exceção tem de sair —, ou o instrumento está cego."
    )


def test_nenhuma_superficie_nova_entrou_no_gesto_de_aplicar() -> None:
    """O portão de verdade: quem aplica é o rodapé, mais o que está registrado.

    Uma aba nova que resolva aplicar direto reprova aqui — que é exatamente o
    que faltava quando a Emulação passou a aplicar e ninguém percebeu que duas
    telas mandavam no mesmo valor.
    """
    permitidas = {contrato.SUPERFICIE_QUE_APLICA, *contrato.EXCECOES_QUE_APLICAM_HOJE}
    intrusas = sorted(set(_superficies_que_aplicam()) - permitidas)
    assert not intrusas, (
        f"estas superfícies aplicam modo/máscara sem serem o rodapé: "
        f"{intrusas}. O contrato é MARCAR nos seletores e APLICAR no rodapé "
        "(`app/actions/contrato_da_mascara.py`). Se a mudança é deliberada, "
        "ela precisa da palavra dela e de uma linha datada em "
        "`EXCECOES_QUE_APLICAM_HOJE` — não de um portão mais frouxo."
    )


def test_a_excecao_registrada_ainda_e_uma_excecao() -> None:
    """Exceção que sobreviveu à própria cura vira norma. Esta não vai.

    Mesma disciplina do `test_nenhuma_lapide_sobreviveu_a_propria_cura` do
    portão da promessa sem caminho.
    """
    quem = _superficies_que_aplicam()
    curadas = [alvo for alvo in contrato.EXCECOES_QUE_APLICAM_HOJE if alvo not in quem]
    assert not curadas, (
        f"{curadas} não aplica(m) mais nada, e continua(m) registrada(s) como "
        "exceção. Apague a linha de `EXCECOES_QUE_APLICAM_HOJE`: um registro "
        "que sobrevive à cura ensina a próxima pessoa a não acreditar nele."
    )


def test_toda_excecao_tem_data_e_razao() -> None:
    """Razão sem data envelhece calada — a régua do registro de lacunas."""
    import re

    for alvo, razao in contrato.EXCECOES_QUE_APLICAM_HOJE.items():
        assert re.search(r"\b\d{2}/\d{2}/\d{4}\b", razao), (
            f"a exceção de {alvo} não diz QUANDO foi medida"
        )
        assert "O QUE A FECHA" in razao, (
            f"a exceção de {alvo} não diz o que a fecha — sem isso ela é uma "
            "desculpa, não um registro"
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "a aba Emulação aplica no clique (MEDIDO em 24/08/2026). Fechá-la é a "
        "onda dela, e a redação de tela do contrato é palavra dela (D-B do "
        "SPRINT_ORDER §0.9). Quando ela fechar, este teste PASSA e o strict "
        "reprova — que é o gatilho para apagar este xfail e a linha de "
        "`EXCECOES_QUE_APLICAM_HOJE` no mesmo gesto."
    ),
)
def test_nenhuma_superficie_alem_do_rodape_aplica() -> None:
    """O contrato inteiro, sem exceção. É o alvo, e ainda não é o estado."""
    quem = sorted(set(_superficies_que_aplicam()) - {contrato.SUPERFICIE_QUE_APLICA})
    assert not quem, quem


def test_o_vocabulario_atravessa_a_fronteira_por_nome_publico() -> None:
    """A aba "No jogo" deixou de importar nome privado da aba Início.

    O alias é o MESMO objeto, nunca cópia: um segundo dono do vocabulário faria
    a aba No jogo dizer o rótulo velho no dia em que a Início mudasse o dele —
    em silêncio, que é como esta casa já perdeu um dia.
    """
    from hefesto_dualsense4unix.app.actions import home_actions
    from hefesto_dualsense4unix.app.widgets import painel_no_jogo

    assert contrato.ITENS_DE_MODO is home_actions._MODE_ITEMS
    assert contrato.ITENS_DE_MASCARA is home_actions._FLAVOR_ITEMS
    assert contrato.ROTULO_RECONCILIAR == home_actions.RECONCILIAR_LABEL
    assert painel_no_jogo._MODE_ITEMS is home_actions._MODE_ITEMS
    assert painel_no_jogo._FLAVOR_ITEMS is home_actions._FLAVOR_ITEMS

    fonte = (
        RAIZ / "src/hefesto_dualsense4unix/app/widgets/painel_no_jogo.py"
    ).read_text(encoding="utf-8")
    assert "from hefesto_dualsense4unix.app.actions.home_actions import (" not in fonte, (
        "a aba No jogo voltou a importar direto da aba Início. O contrato "
        "declara o dono do vocabulário; furar o `_` de outro módulo é o hábito "
        "que ele existe para tirar."
    )
