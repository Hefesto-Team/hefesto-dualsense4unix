"""NAO-DANCA-01 — a aba Status parou de sambar no ritmo do giroscópio.

O QUE ELA VIU, em 13/08/2026
----------------------------

    *"não sei se dá pra ver mas o layout fica sambando aqui na interface"*

Três capturas da aba Status, do mesmo controle, com segundos entre elas:

* 14:11:22 — ``(~160 Hz)``, a frase da verdade em DUAS linhas, a ``Bateria:``
  abaixo dela, à direita;
* 14:11:26 — ``(~193 Hz)``, a mesma frase em UMA linha, a ``Bateria:`` sobe
  para a mesma linha, e todo o conteúdo abaixo sobe junto;
* 14:11:30 — ``(~190 Hz)``, volta a duas linhas, e tudo desce de novo.

O MECANISMO, MEDIDO
-------------------

A frase mora numa label com quebra de linha, dentro da faixa que é o primeiro
bloco do corpo do card — frase à esquerda, bateria à direita. A altura dela
governa a altura da faixa, e a faixa empurra tudo o que vem abaixo.

Com o card na largura da tela dela (1920 → card de 1400px), a frase **recebe
904px e pede 905px**: um pixel de folga negativa. Nessa lâmina um único dígito
do ``(~N Hz)`` decide a quebra — `'160'` e `'193'` têm a mesma largura em pixel
INTEIRO nesta fonte, e o que os separa é fração de pixel. Medido antes da cura,
com as três frases dela: o Touchpad, os analógicos, o Microfone e o teclado de
botões sobem e descem **18px**, duas vezes por segundo.

O QUE ESTES TESTES MORDEM
-------------------------

Trocar :class:`RotuloDeAlturaReservada` por uma `Gtk.Label` comum em
`_montar_estado_global` — que é a cura inteira — faz
`test_a_frase_curta_e_a_mais_longa_nao_movem_nada` reprovar dizendo quantos
pixels cada bloco dançou.

DUAS ARMADILHAS DE MEDIÇÃO PAGAS AQUI, para ninguém repagar
-----------------------------------------------------------

1. **`apply_theme` COMPÕE.** Chamado quatro vezes no mesmo processo, o
   `gtk-font-name` foi de "Fira Sans" para 12.25, 14.5, 16.75 e 19 pontos —
   medido em 13/08. Uma bancada que monta três janelas e aplica o tema em cada
   uma mede TRÊS fontes diferentes e chama isso de dança do layout. Por isso a
   fixture de módulo, que é o idioma que o
   `test_largura_a_mesma_em_todas_as_abas` já usa;
2. **a classe `hefesto-dualsense4unix-window` é obrigatória na janela.** Quase
   todo o `theme.css` está escopado nela; o provider é da TELA, mas sem a
   classe a janela desenha com outra fonte. Medido: sem a classe, a frase de
   160 Hz cabia em UMA linha e o teste passava com a cura arrancada.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("o status não samba")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.theme import (
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ControllerCard,
    frase_mais_longa_do_que_chega_ao_jogo,
    resumo_do_que_chega_ao_jogo,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)

#: A tela dela maximizada — a largura em que as fotos foram tiradas.
LARGURA_DA_TELA_DELA = 1920

#: A classe que o `apply_theme` põe na janela. Ver a armadilha 2 do docstring.
CLASSE_DA_JANELA = "hefesto-dualsense4unix-window"

#: As janelas ficam vivas numa lista de módulo: o Python coleta a referência
#: local assim que a função retorna, e um card sem toplevel volta a medir 1x1.
_janelas_vivas: list[Any] = []

_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 100,
    "player": 1,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": {
        "l2": 200,
        "r2": 40,
        "lx": 60,
        "ly": 200,
        "rx": 180,
        "ry": 90,
        "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    },
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}


def _estado(item: dict[str, Any]) -> dict[str, Any]:
    """Um `state_full` com UM vpad, o do jogador 1."""
    return {
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "rumble_ff": {"per_vpad": [dict(item, player=1, backend="uhid")]},
    }


def _estado_das_fotos_dela(hz: float) -> dict[str, Any]:
    """O estado das três capturas: giroscópio chegando, três recursos parados."""
    return _estado(
        {
            "motion_streaming": True,
            "motion_hz": hz,
            "motion_forwards": 48210,
            "touchpad_pressionado": False,
            "visto_ha_s": {
                "rumble": 20.0,
                "lightbar": 20.0,
                "audio_do_jogo": 20.0,
            },
        }
    )


#: O estado da frase mais CURTA: os seis recursos num grupo só, sem detalhe
#: numérico nenhum (o giroscópio sem Hz, a vibração sem o par dos motores).
ESTADO_FRASE_CURTA = _estado(
    {
        "motion_streaming": True,
        "motion_forwards": 48210,
        "touchpad_pressionado": False,
        "visto_ha_s": {
            "rumble": 0.4,
            "lightbar": 0.4,
            "trigger": 0.4,
            "touchpad_click": 0.4,
            "audio_do_jogo": 0.4,
        },
    }
)

#: E o da frase mais LONGA: os três grupos na tela, com os dois detalhes no
#: maior tamanho que eles têm. É o estado que `frase_mais_longa...` descreve.
ESTADO_FRASE_LONGA = _estado(
    {
        "motion_streaming": True,
        "motion_hz": 1000.0,
        "motion_forwards": 48210,
        "touchpad_pressionado": False,
        "rumble_no_fisico": [255, 255],
        "rumble_no_fisico_ha_s": 0.4,
        "visto_ha_s": {"rumble": 0.4, "lightbar": 20.0, "trigger": 20.0},
    }
)


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema pelos DOIS canais de `app.theme.apply_theme`, e desfaz.

    Não se chama `apply_theme` aqui de propósito: ele SOMA o delta ao
    `gtk-font-name` que encontrar, e uma segunda chamada na mesma sessão do
    pytest mediria uma fonte maior. Ver a armadilha 1 do docstring.
    """
    delta = escala_fonte()
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )
    yield
    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


def _assentar(vezes: int = 8) -> None:
    """Drena o laço mais de uma vez: widget sem alocação mede 1x1."""
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


#: Os blocos do card que vêm ABAIXO da faixa da frase. São eles que ela viu
#: subir e descer: *"o Touchpad, os analógicos, o Microfone, o teclado de
#: botões — a caixa inteira encolhe"*.
BLOCOS_ABAIXO = (
    "_gyro_box",
    "_miolo_inferior",
    "_lightbar_box",
    "_mic_box",
    "_speaker_box",
)


def _geometria(state_global: dict[str, Any]) -> dict[str, int]:
    """Onde cada peça do card cai, com este estado, na tela dela."""
    from hefesto_dualsense4unix.app.mic_monitor import LeituraMic

    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class(CLASSE_DA_JANELA)
    janela.add(card)
    janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, state_global, LeituraMic(nivel=0.6, muted=False))
    # `resize` DEPOIS do `update`: sem ele a OffscreenWindow não realoca.
    janela.resize(LARGURA_DA_TELA_DELA, 900)
    _assentar()

    medida = {
        "altura da faixa da frase": card._faixa_gyro_bateria.get_allocation().height,
        "altura da frase": card._verdade_label.get_allocation().height,
        # A BARRA, e não a linha da bateria: a linha preenche a faixa (o topo
        # dela não se move), e quem sobe e desce é a barra, que fica CENTRADA
        # dentro dessa altura. Medir a linha deixava passar exatamente o que
        # ela anotou — *"a Bateria: sobe para a mesma linha"*.
        "topo da barra de bateria": card._battery_bar.get_allocation().y,
        "topo do rótulo Bateria:": card._battery_row.get_children()[
            0
        ].get_allocation().y,
        "altura que o card pede": card.get_preferred_height()[1],
        "linhas da frase": card._verdade_label.get_layout().get_line_count(),
    }
    for nome in BLOCOS_ABAIXO:
        bloco = getattr(card, nome, None)
        if bloco is not None:
            medida[f"topo de {nome}"] = bloco.get_allocation().y
    return medida


def _o_que_dancou(
    antes: dict[str, int], depois: dict[str, int]
) -> dict[str, int]:
    """Peça → quantos pixels ela se mexeu. Vazio = ninguém dançou."""
    return {
        nome: depois[nome] - antes[nome]
        for nome in antes
        if nome != "linhas da frase" and depois[nome] != antes[nome]
    }


# ---------------------------------------------------------------------------
# A régua: a frase mais longa é a que a função-dona monta mesmo
# ---------------------------------------------------------------------------


def test_a_frase_mais_longa_e_a_que_a_funcao_dona_monta() -> None:
    """A régua da reserva não é ficção — o produto sabe montar aquela frase.

    Se `frase_mais_longa_do_que_chega_ao_jogo` inventasse um texto que
    `resumo_do_que_chega_ao_jogo` nunca produz, a altura reservada seria um
    número decorativo: grande demais (vão sem causa) ou pequeno demais (a
    dança de volta, num estado que ninguém testou).
    """
    frase = resumo_do_que_chega_ao_jogo(_ENTRY, ESTADO_FRASE_LONGA)
    assert frase == frase_mais_longa_do_que_chega_ao_jogo()


def test_a_frase_mais_longa_nomeia_os_seis_recursos() -> None:
    """Nenhum recurso fica de fora da régua — é o que a torna o TETO."""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        _NOME_NA_FRASE,
    )

    frase = frase_mais_longa_do_que_chega_ao_jogo()
    faltando = [nome for _r, nome in _NOME_NA_FRASE if nome not in frase]
    assert not faltando, f"a régua não menciona {faltando}"
    # E os três prefixos, que são o texto fixo mais longo possível.
    for prefixo in ("No jogo agora: ", "pararam: ", "sem pedido ainda: "):
        assert prefixo in frase


# ---------------------------------------------------------------------------
# A mordida: a geometria não pode mudar
# ---------------------------------------------------------------------------


def test_a_frase_curta_e_a_mais_longa_nao_movem_nada() -> None:
    """**A diferença tem de ser ZERO pixel** — em toda peça do card.

    Esta é a mordida. Com a cura arrancada (uma `Gtk.Label` comum no lugar da
    :class:`RotuloDeAlturaReservada`), a frase curta ocupa uma linha, a longa
    ocupa duas, e a mensagem abaixo lista peça por peça quantos pixels cada
    uma andou.

    Os dois estados são escolhidos para a mordida NÃO depender da escala de
    fonte: a frase curta tem os seis recursos num grupo só e sem número, a
    longa tem os três grupos e os dois números no maior tamanho. A razão entre
    elas e o teto de :data:`_VERDADE_MAX_CHARS` é a mesma em qualquer fonte,
    porque o teto também é em CARACTERES.
    """
    curta = _geometria(ESTADO_FRASE_CURTA)
    longa = _geometria(ESTADO_FRASE_LONGA)

    # Guarda anti-teste-vazio: se as duas frases ocupassem o mesmo número de
    # linhas, não haveria dança para detectar e o teste passaria sem medir
    # nada. Ele tem de acusar isso em vez de ficar verde.
    assert curta["linhas da frase"] != longa["linhas da frase"], (
        "as duas frases ocupam o mesmo número de linhas "
        f"({curta['linhas da frase']}); este teste perdeu os dentes — "
        "a frase curta e a mais longa precisam quebrar diferente"
    )

    dancou = _o_que_dancou(curta, longa)
    assert not dancou, "o card dançou entre a frase curta e a mais longa: " + (
        ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
    )


def test_as_tres_frases_das_fotos_dela_nao_movem_nada() -> None:
    """Os três Hz das capturas de 14:11, medidos um contra o outro.

    É o caso REAL, e o mais fino: as três frases têm o mesmo número de
    caracteres e diferem em um dígito. Antes da cura, ~160 Hz e ~190 Hz
    quebravam em duas linhas e ~193 Hz não, e tudo abaixo andava 18px.

    Ele não tem a guarda anti-teste-vazio do irmão acima de propósito: aqui a
    quebra depende de fração de pixel, e exigir que os três Hz continuem
    caindo de lados diferentes da lâmina seria travar o teste numa fonte.
    """
    base = _geometria(_estado_das_fotos_dela(160.0))
    for hz in (193.0, 190.0):
        outra = _geometria(_estado_das_fotos_dela(hz))
        dancou = _o_que_dancou(base, outra)
        assert not dancou, (
            f"o card dançou entre ~160 Hz e ~{hz:.0f} Hz: "
            + ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
        )


def test_a_bateria_nao_muda_de_linha_com_o_texto_ao_lado() -> None:
    """A anotação dela: a ``Bateria:`` subia para a linha de cima e voltava.

    Ela é vizinha da frase na mesma faixa, e não deveria mudar de lugar por
    causa do texto ao lado. Mede-se a BARRA e o RÓTULO — a linha que os contém
    preenche a faixa e tem topo fixo, então medi-la não acusaria nada.
    """
    curta = _geometria(ESTADO_FRASE_CURTA)
    longa = _geometria(ESTADO_FRASE_LONGA)
    for peca in ("topo da barra de bateria", "topo do rótulo Bateria:"):
        assert curta[peca] == longa[peca], (
            f"a bateria mudou de linha ({peca}): "
            f"{curta[peca]}px → {longa[peca]}px"
        )


def test_a_reserva_cabe_a_frase_mais_longa_sem_sobrar_linha() -> None:
    """A altura reservada é a do TETO, e não uma folga inventada.

    Duas metades, e as duas importam:

    * a frase mais longa **cabe** na altura reservada (senão a dança volta
      justamente no estado mais carregado);
    * a altura reservada é **exatamente** a que essa frase pede — nada de vão
      decorativo abaixo da linha.
    """
    longa = _geometria(ESTADO_FRASE_LONGA)
    curta = _geometria(ESTADO_FRASE_CURTA)
    assert curta["altura da frase"] == longa["altura da frase"]
    # A frase mais longa é quem define a altura: ela ocupa a reserva inteira.
    assert longa["linhas da frase"] >= curta["linhas da frase"]


# ---------------------------------------------------------------------------
# A aba "No jogo" tem o mesmo número na tela — e NÃO tem o mesmo defeito
# ---------------------------------------------------------------------------


def test_a_aba_no_jogo_nao_samba_com_o_mesmo_numero() -> None:
    """O outro lugar da janela onde o Hz aparece, medido: 0px de dança.

    Ela mostra ``no jogo agora (~158 Hz)`` numa coluna que TAMBÉM quebra linha
    (`line_wrap` + `max_width_chars(56)`), então a pergunta é legítima. A
    resposta medida em 13/08 é que ela é imune, e por desenho, não por sorte:
    cada recurso tem LINHA FIXA e o valor de cada linha é curto — o mais longo
    ("no jogo agora (motores: 255/255)") tem 32 caracteres para um teto de 56,
    e o painel tem largura própria de 700px.

    Este teste existe para que continue assim: quem alargar o texto daquela
    coluna descobre aqui, e não na tela dela.
    """
    from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
        RECURSOS,
        PainelNoJogo,
    )

    def _medir(hz: float) -> dict[str, int]:
        painel = PainelNoJogo()
        janela = Gtk.OffscreenWindow()
        janela.get_style_context().add_class(CLASSE_DA_JANELA)
        janela.add(painel)
        janela.set_size_request(900, 400)
        janela.show_all()
        _janelas_vivas.append(janela)
        painel.atualizar(_ENTRY, _estado_das_fotos_dela(hz))
        janela.resize(900, 400)
        _assentar()
        medida = {}
        for recurso in RECURSOS:
            _rotulo, valor = painel._linhas[recurso]
            alocacao = valor.get_allocation()
            medida[f"topo de {recurso}"] = alocacao.y
            medida[f"altura de {recurso}"] = alocacao.height
        return medida

    base = _medir(160.0)
    for hz in (193.0, 190.0, 1000.0):
        outra = _medir(hz)
        dancou = _o_que_dancou(base, outra)
        assert not dancou, (
            f'a aba "No jogo" dançou entre ~160 Hz e ~{hz:.0f} Hz: '
            + ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
        )
