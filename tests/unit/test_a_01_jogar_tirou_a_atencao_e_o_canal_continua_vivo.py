#!/usr/bin/env python3
"""A coluna Atenção saiu da Jogar — e as onze fontes NÃO saíram com ela."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.jogar.painel`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}

DA_COLUNA = ("atencao-conta", "aviso-selo", "aviso-texto", "aviso-vivo")


def _ctx(state: dict[str, Any] | None = None) -> Contexto:
    return Contexto(state=dict(state if state is not None else VIVO),
                    mesa=[], conectados=[], estados={})


def test_a_faixa_da_atencao_saiu_das_duas_paginas() -> None:
    """Nem na bancada nem no publicado — e o publicado é o que ela abre."""
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        assert 'class="col-atencao"' not in corpo, f"{onde_}: a faixa voltou"
        assert 'class="aviso-item' not in corpo, f"{onde_}: as linhas voltaram"
        assert 'data-lista="avisos"' not in corpo, f"{onde_}: a lista voltou"
        for campo in DA_COLUNA:
            assert f'data-campo="{campo}"' not in corpo, (
                f"{onde_}: o endereço {campo!r} voltou à página")


def test_o_botao_que_ela_mandou_deixar_ficou() -> None:
    """*"deixar só o reconectar controles"* — e "só" não quer dizer "nenhum"."""
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        assert corpo.count('data-gesto="reconectar"') == 1, (
            f"{onde_}: o botão Reconectar Controles não está exatamente uma vez")
        assert "Reconectar Controles" in corpo, f"{onde_}: o rótulo dele sumiu"


def test_o_pacote_parou_de_emitir_os_quatro_enderecos() -> None:
    """Endereço emitido sem elemento onde pousar é ÓRFÃO, e tem quem o acuse."""
    fora = aba.pacote(_ctx())
    for campo in DA_COLUNA:
        assert campo not in fora, (
            f"`pacote()` voltou a emitir {campo!r}, e a página não tem onde "
            f"pousá-lo — é o órfão que o `casamento.py` acusa")
        assert campo not in aba.DA_PAGINA, (
            f"{campo!r} voltou a `DA_PAGINA`: a `cobertura` passaria a prometer "
            f"um endereço que a página não tem")


def test_o_travessao_solto_dos_externos_morreu() -> None:
    """O `—` que ela viu logo abaixo dos quatro cartões, na mesma ordem.

    ELE NÃO ERA A LINHA DE RESSALVA nem parte da faixa Atenção — medido no DOM
    vivo, com os quatro DualSense na mesa: era o campo `externos`, que devolvia
    `""`. `escrever()` troca vazio por travessão de propósito, a `.ext-vaga` é
    `display:contents`, e o traço virava um item anônimo da grade `.pecas` — um
    quinto assento, na linha de baixo, encostado à esquerda.

    A MORDIDA está na régua dona do campo
    (`test_a_interface_ve_os_controles_que_o_hefesto_so_ve`): devolva `""` em
    qualquer um dos DOIS `return` de `_html_dos_externos`. Aqui a cobrança é a
    da TELA — o que a página publicada mostra entre os cartões e o botão.
    """
    import monta

    assert aba.pacote(_ctx())["externos"] == monta.NADA_A_DIZER, (
        "sem externo o campo voltou a ser `''`, e o piloto escreve `—` nele")
    corpo = onde.pagina("01-jogar.html", publicado=True).read_text(encoding="utf-8")
    meio = corpo.split('data-lista="cartoes"', 1)[-1].split(
        '<div class="faixa-final', 1)[0]
    assert "ext-vaga" in meio, "o bloco dos externos saiu da grade dos assentos"
    assert 'data-campo="aviso' not in meio, "sobrou endereço de aviso no meio"


def test_as_onze_fontes_continuam_de_pe_e_com_porta_propria() -> None:
    """`coluna_de_atencao` responde a lista que a aba Sistema recebe."""
    fora = aba.coluna_de_atencao(_ctx())
    assert isinstance(fora, list)
    for aviso in fora:
        assert set(aviso) == {"selo", "texto", "fonte"}, (
            f"a porta do canal mudou de vocabulário: {sorted(aviso)}")


def test_o_servico_calado_ainda_encontra_o_canal() -> None:
    """A fonte que fala quando TODAS as outras calam continua no canal."""
    selos = [a["selo"] for a in aba._avisos(_ctx({}))]
    assert aba.SELO_DO_SERVICO in selos, (
        "o canal perdeu a fonte do serviço calado quando a tela saiu")


def test_a_unica_fonte_com_segunda_casa_e_o_exame() -> None:
    """A porta do canal é UMA: quem chama as fontes é só o `a01_jogar`.

    Das onze fontes, só o exame da mesa (`a08_conexoes._exame`) é publicado
    noutra aba — a Conexões, de onde ele vem. As outras perderam a tela em
    07/09 e voltaram a ela em 28/09 pela aba Sistema, que as recebe por
    `coluna_de_atencao` (`a09_sistema._avisos_do_produto`) e não as chama uma a
    uma: uma segunda aba chamando a fonte direto seria o segundo dono da mesma
    linha.

    A MORDIDA: chame uma das fontes de outro pacote de aba e esta régua
    reprova; faça a 09 deixar de chamar `coluna_de_atencao` e a última
    asserção reprova.
    """
    pacotes = INTERFACE / "pacotes"
    fontes = {
        "texto_do_cadeado_cego": "o detector de janela cego",
        "aviso_de_opt_out_antigo": "o opt-out antigo",
        "cura_do_travamento": "a cura do travamento do USB",
        "divergencia_de_mascara": "a divergência de máscara",
        "servico_calado": "o serviço calado",
        "AVISOS_DA_TELA": "as seis de `painel`",
    }
    for fonte, oque in fontes.items():
        casas = sorted(
            p.name for p in pacotes.glob("a??_*.py")
            if fonte in p.read_text(encoding="utf-8"))
        chamam = [c for c in casas
                  if f"{fonte}(" in (pacotes / c).read_text(encoding="utf-8")
                  or f"{fonte}:" in (pacotes / c).read_text(encoding="utf-8")]
        assert chamam in ([], ["a01_jogar.py"]), (
            f"{oque} é chamada direto por {chamam} — a porta do canal é "
            "`a01_jogar.coluna_de_atencao`, e uma segunda porta é um segundo "
            "dono da mesma linha")
    do_sistema = (pacotes / "a09_sistema.py").read_text(encoding="utf-8")
    assert "a01_jogar.coluna_de_atencao(ctx)" in do_sistema, (
        "a aba Sistema deixou de receber o canal — os avisos voltam a ficar "
        "calados no produto")
