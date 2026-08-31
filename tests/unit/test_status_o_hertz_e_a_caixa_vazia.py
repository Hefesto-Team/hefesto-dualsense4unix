"""STATUS-DIZ-O-QUE-VÊ-01/T1 e T2 — a caixa vazia de 910px e o hertz que sumiu.

Duas réguas, e as duas medem a MESMA faixa do card único (a linha 2 do corpo,
onde mora a bateria):

* **T1** — nenhum widget SEM CONTEÚDO paga largura nessa faixa. Até 25/08 um
  `Gtk.Box` sem nenhum filho ficava lá com `expand=True, fill=True` e recebia
  ~910px de alocação — medido na foto de 23/08 (corpo do card em x=289,
  "Bateria:" em x=1211);
* **T2** — o hertz do giroscópio CHEGA À TELA no card que a aba monta. Ele
  saiu em 17/08/2026 pela SEM-BARRA-DA-VERDADE-01, que desempacotou a linha
  da verdade sem que ninguém notasse que ela era a única portadora do número.

As duas montam o card **como a aba o monta** — `compact=False`,
`mostrar_estado_global=True` (`status_actions.py`) —, e não com o padrão do
construtor: um teste que mede o modo compacto mede um card que produção
nenhuma constrói (§2.1 da sprint).

**Armadilha de GTK já paga:** widget sem alocação devolve 1x1, e uma asserção
sobre 1x1 passa com qualquer desenho. Toda medida aqui é feita depois de
drenar o laço principal DUAS vezes, com a janela redimensionada entre elas.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status: o hertz e a caixa vazia")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard
from tests.unit.test_status_faixa_blocos import _ENTRY

#: A largura que a aba Status recebe na tela dela, maximizada em 1920x1080.
#: O número tem de ser GRANDE: numa janela estreita a caixa vazia não teria
#: 910px para receber, e o teste passaria com a cura arrancada.
LARGURA_DA_TELA_DELA = 1870

#: O teto do vão morto, em px. Um widget de conteúdo zero pode custar 1px de
#: alocação-fantasma do GTK (o `{-1,-1,1,1}` de quem nunca foi alocado); 4px
#: é a folga que separa isso de um slot que expande.
TETO_DO_VAO_MORTO = 4

#: O hertz que a fixture alimenta. Três dígitos de propósito: é a ordem de
#: grandeza real do IMU do DualSense, e é o número que a sprint cita.
HZ_DA_FIXTURE = 194.0

#: O estado global com o espelho de motion ATIVO no vpad do jogador 1 — a
#: única configuração em que `texto_motion` tem hertz para dizer.
_ESTADO_COM_GIRO: dict[str, Any] = {
    "native_mode": False,
    "rumble_ff": {
        "per_vpad": [
            {"player": 1, "motion_streaming": True, "motion_hz": HZ_DA_FIXTURE}
        ]
    },
}

#: O mesmo estado, sem espelho: o giroscópio não flui, e a linha se cala. É
#: com ele que T1 mede — o vão morto tem de ser zero TAMBÉM quando a linha
#: não tem o que dizer, que é o caso em que a caixa vazia se justificava.
_ESTADO_SEM_GIRO: dict[str, Any] = {"native_mode": False, "rumble_ff": {"per_vpad": []}}

_janelas_vivas: list[Any] = []


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")


def _card_como_a_aba_monta(estado: dict[str, Any]) -> Any:
    """O card do jeito que `status_actions._sync_status_cards` o constrói.

    `compact=False, mostrar_estado_global=True` não é escolha deste teste: é a
    chamada literal de `status_actions.py`, e é a única que produção faz.
    """
    card = ControllerCard(compact=False, mostrar_estado_global=True)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, estado, LeituraMic(nivel=0.6, muted=False))
    janela.resize(LARGURA_DA_TELA_DELA, 900)
    for _ in range(2):
        while Gtk.events_pending():
            Gtk.main_iteration()
    return card


def _sem_conteudo(widget: Any) -> bool:
    """True quando o widget não tem NADA dentro para mostrar.

    Um `Gtk.Container` sem nenhum filho visível e um `Gtk.Label` de texto
    vazio são as duas formas que um vão morto assume nesta casa. Qualquer
    outro widget conta como conteúdo — inclusive um desenho, que não tem
    filhos nem texto.
    """
    if isinstance(widget, Gtk.Label):
        return not widget.get_text().strip()
    if isinstance(widget, Gtk.Container):
        return not [f for f in widget.get_children() if f.get_visible()]
    return False


def _textos_da_arvore(widget: Any) -> list[str]:
    """Todo `get_text()` VISÍVEL da árvore, de cima para baixo."""
    achados: list[str] = []
    if not widget.get_visible():
        return achados
    ler = getattr(widget, "get_text", None)
    if callable(ler):
        try:
            texto = ler()
        except TypeError:  # pragma: no cover — `get_text` de outra assinatura
            texto = None
        if isinstance(texto, str) and texto.strip():
            achados.append(texto)
    if isinstance(widget, Gtk.Container):
        for filho in widget.get_children():
            achados.extend(_textos_da_arvore(filho))
    return achados


# ---------------------------------------------------------------------------
# T1 — a caixa vazia de 910px
# ---------------------------------------------------------------------------


def test_status_faixa_gyro_bateria() -> None:
    """Nenhum widget sem conteúdo paga largura na faixa da bateria.

    **A mordida:** devolva o `slot_motion` — um `Gtk.Box` sem filhos com
    `faixa.pack_start(slot_motion, True, True, 0)` — e troque o `pack_end` da
    bateria por `pack_start`. O teste reprova com o NÚMERO (≈910px), não com
    "falhou": é a alocação medida que ele imprime.

    Medido com o giroscópio CALADO de propósito. Era esse o caso em que a
    caixa vazia se defendia ("sem o slot a bateria saltaria da direita para a
    esquerda"), e é ele que o `pack_end` resolve sem cobrar pixel.
    """
    card = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)
    faixa = card._faixa_gyro_bateria
    largura_da_faixa = faixa.get_allocation().width

    assert largura_da_faixa > 100, (
        "a faixa não foi alocada de verdade (mediu "
        f"{largura_da_faixa}px): widget sem alocação devolve 1x1 e a asserção "
        "abaixo passaria com qualquer desenho"
    )

    vaos_mortos = {
        type(filho).__name__: filho.get_allocation().width
        for filho in faixa.get_children()
        if filho is not card._battery_row
        and filho.get_visible()
        and _sem_conteudo(filho)
    }
    caros = {nome: px for nome, px in vaos_mortos.items() if px > TETO_DO_VAO_MORTO}

    assert not caros, (
        f"a faixa da bateria (largura {largura_da_faixa}px) paga largura a "
        f"widget SEM NENHUM CONTEÚDO: {caros}. O teto é "
        f"{TETO_DO_VAO_MORTO}px — o que expande tem de ter o que mostrar"
    )


def test_a_bateria_fica_ancorada_na_direita_com_a_linha_calada() -> None:
    """A bateria não salta quando o giroscópio se cala.

    Era o único serviço que o slot vazio prestava, e o `pack_end` o presta de
    graça. **A mordida:** troque `faixa.pack_end(linha_bateria, ...)` por
    `pack_start` e o teste reprova nomeando os dois x.
    """
    com = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    sem = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)

    def direita_da_bateria(card: Any) -> int:
        alloc = card._battery_row.get_allocation()
        return alloc.x + alloc.width

    assert direita_da_bateria(com) == direita_da_bateria(sem), (
        "a bateria mudou de lugar entre o giroscópio fluindo "
        f"(direita em x={direita_da_bateria(com)}) e o giroscópio calado "
        f"(x={direita_da_bateria(sem)}): ela tem de ficar ancorada na direita "
        "nos dois estados"
    )


# ---------------------------------------------------------------------------
# T2 — o hertz volta à tela
# ---------------------------------------------------------------------------


def test_o_hertz_chega_a_tela() -> None:
    """O número do giroscópio aparece no card que a aba monta.

    **A mordida, e ela é dupla:** com a árvore de 24/08 este teste REPROVA —
    é essa reprovação, registrada antes do conserto, que o valida. Arranque o
    `faixa.pack_start(motion, ...)` do `_montar_ui` e ele reprova de novo,
    imprimindo a árvore inteira de textos visíveis para provar que "Hz" não
    está em nenhum deles.

    Ele varre `get_text()` da árvore e não o `_motion_label` direto de
    propósito: o defeito de 17/08 foi exatamente um rótulo ALIMENTADO e não
    empacotado — ler o widget pelo atributo teria passado o tempo todo.
    """
    card = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    textos = _textos_da_arvore(card)
    com_hz = [t for t in textos if "Hz" in t]

    assert com_hz, (
        "o hertz do giroscópio não chega à tela do card único: nenhum dos "
        f"{len(textos)} textos visíveis contém 'Hz'. Árvore: {textos}"
    )
    assert any(str(int(HZ_DA_FIXTURE)) in t for t in com_hz), (
        f"a tela diz 'Hz' mas não o número alimentado ({int(HZ_DA_FIXTURE)}): "
        f"{com_hz}"
    )


def test_o_hertz_se_cala_quando_o_giroscopio_nao_flui() -> None:
    """Sem espelho de motion, a linha some — não inventa número nenhum.

    A metade que impede a cura de virar mentira: um rótulo que diz "~0 Hz" ou
    fica com o último valor é pior que a ausência. **A mordida:** faça o
    `_update_motion` parar de chamar `hide()` e o teste reprova.
    """
    card = _card_como_a_aba_monta(_ESTADO_SEM_GIRO)
    com_hz = [t for t in _textos_da_arvore(card) if "Hz" in t]

    assert not com_hz, (
        "o card afirma hertz com o espelho de motion DESLIGADO no vpad: "
        f"{com_hz}"
    )


# ---------------------------------------------------------------------------
# T3 — o comentário que a leva seguinte tornou falso
# ---------------------------------------------------------------------------

#: As frases que afirmavam, dentro do código, que a linha da VERDADE dizia o
#: giroscópio no card único. Elas deixaram de ser verdade em 17/08/2026 e
#: sobreviveram oito dias porque nada as media.  (noqa-acento: verbo medir, imperfeito)
#: Estão aqui em pedaços curtos
#: de propósito: é a AFIRMAÇÃO que fica proibida, não a redação dela.
_PROMESSAS_CADUCAS: tuple[str, ...] = (
    "o giroscópio é dito pela linha da verdade",
    "quem a empacota é o bloco do motion",
    "o lugar dela é a faixa da linha 2",
)


def test_nenhum_comentario_promete_a_linha_da_verdade_na_tela() -> None:
    """T3 — a régua que faltava em 17/08: o comentário casa com a árvore.

    O defeito de T3 não foi um `pack` errado; foi um comentário que continuou
    afirmando o que a leva seguinte desfez, em DOIS lugares, por oito dias. E
    o `_update_motion` decidia não pintar citando esse comentário.

    **Esta é a mordida que eu inventei** — a sprint não declarou nenhuma para
    T3, e "o portão é a revisão de A-1" não sobrevive a um `/clear`. Ela tem
    duas metades e as duas mordem:

    * devolva qualquer uma das três frases de `_PROMESSAS_CADUCAS` ao módulo e
      o teste reprova nomeando o arquivo, a linha e a frase;
    * empacote o `_verdade_label` de volta sem mexer nos comentários e o teste
      reprova pelo outro lado — a árvore passou a dizer o que o texto nega.

    O que ele NÃO faz: proibir a linha da verdade de voltar. Se ela voltar, o
    conserto é escrever o comentário novo — que é exatamente o trabalho que
    ninguém fez em 17/08.
    """
    import inspect
    import re

    from hefesto_dualsense4unix.app.widgets import controller_card as modulo

    # Achatar o módulo inteiro numa linha só, sem `#` e sem espaço repetido,
    # e guardar de que LINHA veio cada caractere. Uma varredura por linha
    # seria burlada pela quebra de linha do próprio comentário — o defeito
    # de 17/08 sobreviveu partido em duas linhas, e um portão que não o
    # pegasse por isso seria régua que só sabe passar.
    achatado: list[str] = []
    linha_do_caractere: list[int] = []
    for numero, linha in enumerate(inspect.getsource(modulo).splitlines(), start=1):
        pedaco = re.sub(r"\s+", " ", linha.lstrip().lstrip("#").strip())
        if not pedaco:
            continue
        if achatado:
            achatado.append(" ")
            linha_do_caractere.append(numero)
        achatado.append(pedaco)
        linha_do_caractere.extend([numero] * len(pedaco))
    texto_achatado = "".join(achatado)

    achados = []
    for frase in _PROMESSAS_CADUCAS:
        onde = texto_achatado.find(frase)
        if onde >= 0:
            achados.append(
                f"{modulo.__name__}:{linha_do_caractere[onde]}: {frase!r}"
            )
    assert not achados, (
        "o código volta a afirmar que a linha da VERDADE diz o giroscópio na "
        "tela do card único — falso desde 17/08/2026 (SEM-BARRA-DA-VERDADE-01 "
        f"a desempacotou a pedido dela): {achados}"
    )

    card = _card_como_a_aba_monta(_ESTADO_COM_GIRO)
    assert card._verdade_label is not None, (
        "o `_verdade_label` sumiu do card único: ele é decisão medida de "
        "01/08 guardada de propósito (o caminho de volta), e apagá-lo pede "
        "sprint própria — não é efeito colateral de T1/T2"
    )
    assert card._verdade_label.get_parent() is None, (
        "o `_verdade_label` voltou à tela e os comentários deste módulo ainda "
        "dizem que ele está fora dela. Se a volta é intencional, reescreva os "
        "comentários do `_montar_ui`, do `_montar_estado_global` e do "
        "`_update_motion` — foi o que ninguém fez em 17/08"
    )
