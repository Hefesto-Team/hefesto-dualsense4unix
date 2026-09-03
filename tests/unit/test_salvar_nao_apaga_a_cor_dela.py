"""Desligar a barra e salvar não pode apagar a cor que ela escolheu.

O ACHADO MAIS GRAVE DA LEVA DE 03/09/2026, e o juiz que o nomeou disse que ele
não estava marcado como o mais grave por ninguém:

    "Desligar" a barra de luz e depois "Salvar Perfil" apaga a cor escolhida
    por ela, para sempre, em silêncio.

A CAUSA ERA DE VOCABULÁRIO. ``_draft_do_ativo`` lia ``lightbar_rgb`` cru do
estado do daemon e o gravava como override daquele controle. Com a barra
apagada esse campo é ``(0, 0, 0)`` — e o ``LedsDraft`` **não tem campo de
aceso/apagado**, só a cor. Gravar o preto não guarda "estava apagada": guarda
PRETO por cima da escolha dela, e o caminho de volta não existe.

A CURA É REUSO, e não regra nova: :func:`controller_card.rotulo_lightbar` já é o
dono desta leitura na GUI estável, e devolve a cor base como ``None`` exatamente
nos dois estados em que não há cor a afirmar — *cor desconhecida* e *apagada*.
Reler os campos crus aqui seria uma segunda verdade, e a aba 04 já pagou o preço
dessa: o ``c.get("lightbar_on", True)`` que morava lá tinha o padrão INVERTIDO e
afirmava ACESA na ausência do campo.

A MORDIDA: troque o ``rotulo_lightbar`` de volta por ``c.get("lightbar_rgb")``
em ``rodape._draft_do_ativo`` e :func:`test_barra_apagada_nao_grava_cor`
reprova — o preto volta a viajar para o disco.
"""

from __future__ import annotations

from typing import Any

import pytest

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
    """O mínimo de ``Contexto`` que ``_draft_do_ativo`` lê."""

    def __init__(self, conectados: list[dict[str, Any]],
                 state: dict[str, Any] | None = None) -> None:
        self.conectados = conectados
        self.state = state or {}


def _controle(rgb: tuple[int, int, int] | None, *, acesa: bool,
              fonte: str = "sysfs") -> dict[str, Any]:
    """Um controle do estado do daemon, no vocabulário que ele publica."""
    return {"uniq": UNIQ, "lightbar_rgb": list(rgb) if rgb else None,
            "lightbar_on": acesa, "lightbar_source": fonte}


def _cor_gravada(draft: Any) -> tuple[int, int, int] | None:
    """A cor que o rascunho levaria ao disco PARA ESTE controle, ou ``None``.

    Ler o override e não o global é o ponto inteiro: a cor viva vira override
    daquele aparelho (``ControllerOverrides.leds``), e é lá que o estrago
    aconteceria.
    """
    dono = draft.controller_override(UNIQ)
    if dono is None or getattr(dono, "leds", None) is None:
        return None
    cor = dono.leds.lightbar
    return None if cor is None else tuple(cor)


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
    # chama de `lightbar_rgb`. São o mesmo dado com dois nomes, e este
    # teste atravessa a fronteira entre os dois — por isso os dois aparecem.
    p.leds.lightbar = COR_DELA
    save_profile(p, origem="teste")
    assert tuple(load_profile(nome).leds.lightbar) == COR_DELA
    return nome


def test_barra_apagada_nao_grava_cor(perfil_com_a_cor_dela: str) -> None:
    """Com a barra desligada, o rascunho não carrega cor para aquele controle.

    Não gravar é o certo: o esquema só sabe dizer QUAL cor, não SE está acesa,
    e o que está no disco é a cor para quando acender.
    """
    ctx = _Ctx([_controle((0, 0, 0), acesa=False)])
    draft = rodape._draft_do_ativo(perfil_com_a_cor_dela, ctx)
    assert draft is not None
    assert _cor_gravada(draft) is None, (
        "a barra apagada virou um override de cor — é o preto viajando por "
        "cima da escolha dela")


def test_cor_desconhecida_tambem_nao_grava(perfil_com_a_cor_dela: str) -> None:
    """Sem fonte, não há cor a afirmar — e afirmar seria inventar.

    O ``(0,0,0)`` de um sysfs que ninguém escreveu pode ser o azul-kernel
    brilhando neste exato momento; é a mesma refutação que a GUI estável
    carrega em ``rotulo_lightbar``.
    """
    ctx = _Ctx([_controle(None, acesa=True, fonte="desconhecida")])
    draft = rodape._draft_do_ativo(perfil_com_a_cor_dela, ctx)
    assert draft is not None
    assert _cor_gravada(draft) is None


def test_barra_acesa_continua_gravando(perfil_com_a_cor_dela: str) -> None:
    """A cura não pode ter matado o que a função existe para fazer.

    Uma guarda que recusasse tudo passaria os dois testes de cima e deixaria o
    Salvar sem gravar cor nenhuma — o oposto do pedido dela, que é a interface
    nova ser de ação imediata.
    """
    viva = (126, 184, 212)
    ctx = _Ctx([_controle(viva, acesa=True)])
    draft = rodape._draft_do_ativo(perfil_com_a_cor_dela, ctx)
    assert draft is not None
    assert _cor_gravada(draft) == viva


def test_um_controle_apagado_nao_derruba_o_aceso(
        perfil_com_a_cor_dela: str) -> None:
    """Na mesa de dois, o apagado é pulado e o aceso continua gravando.

    É a forma que a fita da luz já pagou uma vez nesta casa: um controle sem
    cor apagava a tira INTEIRA. A guarda tem de ser por controle, nunca pela
    mesa.
    """
    viva = (255, 0, 0)
    outro = "aabbcc0000ee"
    apagado = _controle((0, 0, 0), acesa=False)
    aceso = dict(_controle(viva, acesa=True), uniq=outro)
    draft = rodape._draft_do_ativo(perfil_com_a_cor_dela, _Ctx([apagado, aceso]))
    assert draft is not None
    assert _cor_gravada(draft) is None, "o apagado gravou cor"
    dono = draft.controller_override(outro)
    assert dono is not None and tuple(dono.leds.lightbar) == viva, (
        "o controle aceso perdeu o override porque o vizinho estava apagado")
