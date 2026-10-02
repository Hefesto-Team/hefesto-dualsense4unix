"""Desligar a barra e salvar não pode apagar a cor que ela escolheu.

O ACHADO MAIS GRAVE DA LEVA DE 03/09/2026, e o juiz que o nomeou disse que ele
não estava marcado como o mais grave por ninguém:

    "Desligar" a barra de luz e depois "Salvar Perfil" apaga a cor escolhida
    por ela, para sempre, em silêncio.

A CAUSA ERA DE VOCABULÁRIO: o Salvar lia ``lightbar_rgb`` cru do estado do
daemon e o gravava como override daquele controle. Com a barra apagada esse
campo é ``(0, 0, 0)``, e o esquema **não tem campo de aceso/apagado**, só a
cor: gravar o preto não guarda "estava apagada", guarda PRETO por cima da
escolha dela.

DESDE 27/09 (`D-2709-O-SALVAR-LE-O-PERFIL`) o Salvar não lê a luz do aparelho
em estado nenhum: apagada, desconhecida ou acesa noutra cor, o que sai é a
cor do disco. A cor que ela ESCOLHE vai ao disco no clique do tom
(`a04_iluminacao._guardar_a_cor_no_perfil`), e o «Desligar» grava o brilho
em 0% e deixa a cor (`D-2509-O-DESLIGAR-E-O-BRILHO-EM-ZERO`).

A MORDIDA: devolva ao ``rodape.salvar`` a cor que o aparelho publica
(``lightbar_rgb`` cru no override de cada controle) e
:func:`test_barra_apagada_nao_grava_cor` reprova com o preto no disco.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit.ponte_do_rodape import PonteDoRodape

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import rodape

#: A COR DELA, e ela é o azul que o resto da casa usa nos exemplos.
COR_DELA = (0, 0, 255)

#: O ENDEREÇO DE RÁDIO DA BANCADA, com a máscara da casa (octetos 4 e 5
#: zerados). Nada de MAC real em arquivo versionado.
#:
#: SEM OS DOIS-PONTOS de propósito: é assim que o daemon publica o `uniq`, e é
#: assim que o mapa `source_controllers` do rascunho o guarda. Pedir com o
#: formato do `comum` (com dois-pontos) não dá erro — dá override nenhum, que
#: se lê como "a cura não gravou" quando o que houve foi um endereço que não
#: casa com chave alguma.
UNIQ = "aabbcc0000ff"


class _Ctx:
    """O mínimo de ``Contexto`` que o «Salvar» do rodapé recebe."""

    def __init__(self, conectados: list[dict[str, Any]], perfil: str) -> None:
        self.conectados = conectados
        self.mesa = conectados
        self.state = {"active_profile": perfil}


def _controle(rgb: tuple[int, int, int] | None, *, acesa: bool,
              fonte: str = "sysfs", uniq: str = UNIQ) -> dict[str, Any]:
    """Um controle do estado do daemon, no vocabulário que ele publica."""
    return {"uniq": uniq, "lightbar_rgb": list(rgb) if rgb else None,
            "lightbar_on": acesa, "lightbar_source": fonte}


def _salvar(perfil: str, *conectados: dict[str, Any]) -> Any:
    """O «Salvar Perfil» do rodapé, e o perfil que ficou no disco."""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    rodape.salvar(_Ctx(list(conectados), perfil), {"gesto": "salvar"}, PonteDoRodape())
    return load_profile(perfil)


def _cor_do_controle(prof: Any, uniq: str = UNIQ) -> tuple[int, int, int] | None:
    """A cor que o disco dá a ESTE controle: a do override, ou a global que ele herda."""
    dono = (prof.controllers or {}).get(uniq)
    leds = getattr(dono, "leds", None)
    if leds is not None and "lightbar" in leds.model_fields_set:
        return tuple(leds.lightbar)
    return tuple(prof.leds.lightbar)


@pytest.fixture
def perfil_com_a_cor_dela(monkeypatch: pytest.MonkeyPatch) -> str:
    """Um perfil no disco de mentira, com a cor dela guardada.

    O ``conftest`` desta casa já desvia ``HOME`` e os quatro ``XDG_*`` para um
    lar de mentira; aqui só se grava dentro dele.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    nome = "perfil-da-prova"
    # `match` É OBRIGATÓRIO no esquema, e `MatchAny` é o que o resto da
    # suíte usa quando a regra de casamento não é o que se está medindo.
    p = Profile(name=nome, match=MatchAny(), priority=100)
    # O ESQUEMA DO DISCO CHAMA O CAMPO DE `lightbar`; o rascunho da GUI o
    # chama de `lightbar_rgb`. São o mesmo dado com dois nomes.
    p.leds.lightbar = COR_DELA
    save_profile(p, origem="teste")
    assert tuple(load_profile(nome).leds.lightbar) == COR_DELA
    return nome


def test_barra_apagada_nao_grava_cor(perfil_com_a_cor_dela: str) -> None:
    """Com a barra desligada, a cor do disco fica: é a cor para quando acender."""
    salvo = _salvar(perfil_com_a_cor_dela, _controle((0, 0, 0), acesa=False))
    assert _cor_do_controle(salvo) == COR_DELA, (
        "a barra apagada virou cor no disco — é o preto viajando por cima da "
        "escolha dela")


def test_cor_desconhecida_tambem_nao_grava(perfil_com_a_cor_dela: str) -> None:
    """Sem fonte, não há cor a afirmar — e o disco não muda."""
    salvo = _salvar(perfil_com_a_cor_dela,
                    _controle(None, acesa=True, fonte="desconhecida"))
    assert _cor_do_controle(salvo) == COR_DELA


def test_barra_acesa_noutra_cor_tambem_nao_grava(
        perfil_com_a_cor_dela: str) -> None:
    """Acesa noutra cor (a camada da mão, o automático, a luz pós-brilho): o disco fica.

    Até 27/09 esta régua cobrava o contrário — a cor acesa no disco —, porque
    em 03/09 o clique no tom ainda não gravava. Quem leva a escolha dela ao
    disco hoje é o clique (`test_a_cor_escolhida_vai_ao_disco_e_o_trilho_nao_reescala.py`).
    """
    salvo = _salvar(perfil_com_a_cor_dela,
                    _controle((126, 184, 212), acesa=True))
    assert _cor_do_controle(salvo) == COR_DELA


def test_dois_controles_um_apagado_e_um_aceso(
        perfil_com_a_cor_dela: str) -> None:
    """Na mesa de dois, nenhum dos dois leva a luz do aparelho ao disco.

    É a forma que a fita da luz já pagou uma vez nesta casa: um controle sem
    cor apagava a tira INTEIRA. Aqui nenhum dos dois ganha override.
    """
    outro = "aabbcc0000ee"
    salvo = _salvar(perfil_com_a_cor_dela,
                    _controle((0, 0, 0), acesa=False),
                    _controle((255, 0, 0), acesa=True, uniq=outro))
    assert _cor_do_controle(salvo) == COR_DELA, "o apagado gravou cor"
    assert _cor_do_controle(salvo, outro) == COR_DELA, (
        "o controle aceso levou a luz do aparelho ao disco")
