"""SOM-04, entrega 1 — o som que confirma o que a tela não consegue confirmar.

O pedido dela, literal: *"faz os botões silenciar e devolver emitirem os sons
tá bom?"*. A razão de fundo é mais forte que o pedido: **o registrador de
volume do DualSense não tem leitura** (SOM-02, o preço da camada 2). O número
que o bloco mostra é o que NÓS mandamos, então nada na tela pode confirmar que
o gesto valeu. O som é a leitura que falta.

Este arquivo afere a FIAÇÃO no card. O motor — escolher o arquivo, achar o
tocador, recusar quando não dá — é aferido em
`test_som_04_confirmacao_e_rota.py`, e o botão de rota em
`test_status_som_04_rota.py`.

O FATO que a fiação inteira defende, medido nesta bancada em 01/08/2026::

    $ paplay --device=nao_existe_mesmo bell.oga ; echo $?   -> 0
    $ paplay --device= bell.oga ; echo $?                   -> 0

O tocador aceita sink vazio ou inexistente, sai com ZERO e toca no sink
PADRÃO. Com o padrão dela no HDMI, a confirmação do alto-falante do controle
sairia pela televisão — e ela concluiria que o alto-falante quebrou.

Toda medida de geometria é feita com o card MONTADO E ALOCADO numa
`Gtk.OffscreenWindow`: widget sem alocação devolve 1x1 e um teste de layout
sobre ele passa com qualquer desenho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status som 04 som de confirmacao")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk, Pango

from hefesto_dualsense4unix.app import audio_saida, ipc_bridge
from hefesto_dualsense4unix.app.audio_saida import (
    MOTIVO_SEM_TOCADOR,
    MOTIVO_TOCOU,
    ResultadoDoSom,
)
from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.theme import (
    escala_fonte,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    _SELO_CHARS,
    DICA_BLOCO_SPEAKER,
    DICA_SPEAKER_POSSE_NOSSA,
    TEXTO_SELO_SAIDA_MUDA,
    TEXTO_SELO_SEM_SOM,
    ControllerCard,
)

#: O nome REAL do sink do controle nesta máquina, copiado de
#: `pactl list sinks short`. Nome inventado esconderia o detalhe que importa: o
#: sufixo `-00` é desempate posicional do PipeWire, não identidade.
SINK_CONTROLE = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

#: A largura com que a janela ABRE. É o orçamento duro da aba Status.
LARGURA_DE_PROJETO = 1180

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {"touching": True, "x": 1440, "y": 270, "width": 1920, "height": 1080},
}
_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 80,
    "player": None,
    "player_slot": 1,
    "lightbar_rgb": [97, 53, 131],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": _INPUTS,
    "vpad_backend": "uhid",
    "vpad_motivo": None,
    "audio": {
        "fone_plugado": False,
        "mic_externo": False,
        "mic_mudo": False,
        "mic_mudo_desejado": None,
    },
}
_ESTADO: dict[str, Any] = {"native_mode": False}

#: Volume com posse. Depois do remapeamento da régua (SOM-03/`core.speaker_scale`)
#: o registrador é mudo até 38 e satura em 102 — 90 é um valor de posse REAL,
#: dentro da faixa audível, e não o 180 da escala linear de antes.
POSSE: dict[str, Any] = {"volume": 90, "muted": False}

#: A faixa vertical que a aba Status entrega aos cards, em px.
#:
#: Remedido em 01/08/2026 (noite) — ver o docstring de
#: `test_o_selo_com_recado_cabe_na_faixa_dos_cards`. O mesmo número está em
#: `test_status_som_02_controle_de_volume.py`, e o dono absoluto do orçamento
#: continua sendo `test_layout_orcamento_altura.py`, que MEDE a faixa em vez
#: de repetir o número.
FAIXA_DOS_CARDS_PX = 550

_janelas_vivas: list[Any] = []


class _LeituraMic:
    """Dublê da `LeituraMic` — o card lê `nivel`, `muted` e `saida_muda`."""

    def __init__(self, saida_muda: bool | None = None) -> None:
        self.nivel = 0.6
        self.muted = False
        self.saida_muda = saida_muda


@pytest.fixture(scope="module", autouse=True)
def _tema_na_escala_que_sai() -> Any:
    """O tema COM a escala de fonte da sessão, desfeito no fim.

    Sem isto ~90% da janela mediria os 13,33px do padrão do Pango, e o número
    aferido não seria o da tela dela (esta bancada roda em +3).
    """
    delta = escala_fonte()
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    provider.load_from_data(
        escalar_css((GUI_DIR / "theme.css").read_text(encoding="utf-8"), delta).encode(
            "utf-8"
        )
    )
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


def _card(
    *,
    compact: bool = False,
    largura: int = LARGURA_DE_PROJETO,
    speaker: dict[str, Any] | None = None,
    mic: Any = None,
    sink: str = SINK_CONTROLE,
) -> Any:
    """Card montado, alocado, atualizado e COM o sink de saída definido."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    entrada = dict(_ENTRY)
    if speaker is not None:
        entrada["speaker"] = speaker
    card.update(entrada, _ESTADO, mic if mic is not None else _LeituraMic())
    card.definir_sink_de_saida(sink)
    janela.resize(largura, 900)
    while Gtk.events_pending():
        Gtk.main_iteration()
    return card


class _Pedidos:
    """Espião de `run_in_thread` + `speaker_set` + `tocar_confirmacao`.

    ``agendados`` guarda o que foi entregue a `run_in_thread` SEM executar: é
    isso que prova que o clique não bloqueia a thread do GTK. `rodar()` executa
    a função E o callback de sucesso, que é o que o `GLib.idle_add` faria.
    """

    def __init__(self, resultado: Any = None) -> None:
        self.agendados: list[tuple[Any, Any]] = []
        self.pedidos_ipc: list[dict[str, Any]] = []
        self.sons: list[dict[str, Any]] = []
        self.resposta_ipc = True
        self.resultado = resultado or ResultadoDoSom.de(MOTIVO_TOCOU, SINK_CONTROLE)

    def run_in_thread(self, fn: Any, ok: Any, _err: Any = None) -> None:
        self.agendados.append((fn, ok))

    def speaker_set(self, **kwargs: Any) -> bool:
        self.pedidos_ipc.append(kwargs)
        return self.resposta_ipc

    def tocar_confirmacao(self, sink: str, **kwargs: Any) -> Any:
        self.sons.append({"sink": sink, **kwargs})
        return self.resultado

    def rodar(self) -> None:
        pendentes, self.agendados = self.agendados, []
        for fn, ok in pendentes:
            ok(fn())


@pytest.fixture()
def pedidos(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos()
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    monkeypatch.setattr(audio_saida, "tocar_confirmacao", espiao.tocar_confirmacao)
    return espiao


# ---------------------------------------------------------------------------
# O som sai no sink DO CONTROLE — e nas quatro ações
# ---------------------------------------------------------------------------


def test_as_quatro_acoes_do_bloco_confirmam_no_sink_do_controle(
    pedidos: _Pedidos,
) -> None:
    """O pedido dela por inteiro: volume, Silenciar, Ativar e Devolver.

    E a regra 1, que é a que não pode falhar: **o sink vai explícito, e é o do
    CONTROLE**. Se o áudio for para o sink padrão, ela clica, não ouve nada, e
    conclui que o alto-falante quebrou.

    Mordida: passar ``""`` em vez de ``self._speaker_sink`` em
    `_confirmar_com_som` — que é o que um "toca o som de confirmação" ingênuo
    faz. Medido: o tocador aceita o vazio, sai com zero e toca no PADRÃO. A
    asserção dos sinks cai nas quatro ações de uma vez.
    """
    # 1) mover o controle deslizante
    card = _card(speaker=POSSE)
    card._speaker_escala.set_value(70)
    card._enviar_volume_do_controle()
    pedidos.rodar()

    # 2) Silenciar  3) Ativar — o mesmo botão, os dois estados
    for estado in ({"volume": 90, "muted": False}, {"volume": 90, "muted": True}):
        c = _card(speaker=estado)
        c._on_speaker_mudo_clicado(None)
        pedidos.rodar()

    # 4) Devolver
    c = _card(speaker=POSSE)
    c._on_speaker_devolucao_clicada(None)
    pedidos.rodar()

    assert len(pedidos.sons) == 4, (
        "as QUATRO ações do bloco confirmam com som: mover o volume, "
        f"Silenciar, Ativar e Devolver — saíram {len(pedidos.sons)}"
    )
    assert {s["sink"] for s in pedidos.sons} == {SINK_CONTROLE}, (
        "todo som sai no sink DO CONTROLE, explicitamente — nunca no padrão"
    )


def test_o_som_nao_sai_antes_de_o_daemon_aceitar_o_pedido(
    pedidos: _Pedidos,
) -> None:
    """A confirmação é DAQUELE pedido: sem pedido aceito, não há o que confirmar.

    Mordida: tocar fora do ``if ok`` de `_pedir`. Com o daemon recusando (ou
    offline), a janela passa a emitir um som de confirmação para uma mudança
    que não aconteceu — a mesma família de mentira que a SOM-01 recusou ao não
    publicar "0 %".
    """
    pedidos.resposta_ipc = False
    card = _card(speaker=POSSE)
    card._on_speaker_devolucao_clicada(None)
    pedidos.rodar()

    assert pedidos.pedidos_ipc, "o pedido foi mandado"
    assert pedidos.sons == [], "e nenhum som saiu, porque o daemon recusou"


def test_o_clique_nao_bloqueia_a_thread_do_gtk(pedidos: _Pedidos) -> None:
    """Regra 2: o som roda fora da thread do GTK, junto do IPC que já rodava.

    O tocador é subprocess (medido: 0,35s de ponta a ponta) e o IPC é
    bloqueante. Esta interface já congelou por chamada bloqueante num clique.

    Mordida: chamar `self._confirmar_com_som()` direto no handler do `clicked`,
    em vez de dentro do `_pedir` que já vai para a worker. A primeira asserção
    cai na hora.
    """
    card = _card(speaker=POSSE)
    card._on_speaker_mudo_clicado(None)

    assert pedidos.sons == [], (
        "nada de subprocess na thread do GTK: o som fica na fila do "
        "run_in_thread, junto do IPC"
    )
    assert pedidos.pedidos_ipc == [], "e o IPC também"
    assert len(pedidos.agendados) == 1, "um único trabalho agendado por clique"

    pedidos.rodar()
    assert len(pedidos.sons) == 1


def test_arrastar_o_controle_nao_vira_metralhadora_de_sons(
    pedidos: _Pedidos,
) -> None:
    """Regra 3: um som por GESTO, nunca um por pixel.

    ``value-changed`` dispara por pixel de arrasto. O som segue o mesmo repouso
    de 250ms que o IPC já seguia, e o fim do gesto (`button-release`) manda uma
    vez só — com a deduplicação do mesmo volume por cima, para o repouso que
    dispara logo depois de soltar.

    Mordida: tocar direto em `_on_speaker_escala_mudou`, ou tirar a
    deduplicação `if volume == self._speaker_volume_enviado` de
    `_enviar_volume_do_controle`. Um arrasto de 12 posições passa a render 12
    (ou 2) sons e a asserção do 1 cai.
    """
    card = _card(speaker=POSSE)
    card._on_speaker_escala_pega(None, None)  # a mão dela desceu
    for percentual in range(30, 90, 5):  # doze "pixels" de arrasto
        card._speaker_escala.set_value(percentual)
    card._on_speaker_escala_solta(None, None)  # soltou
    card._on_speaker_repouso()  # e o repouso dispara logo atrás
    pedidos.rodar()

    assert len(pedidos.sons) == 1, (
        f"um som por gesto, não um por pixel: saíram {len(pedidos.sons)} para "
        "um arrasto só"
    )
    assert len(pedidos.pedidos_ipc) == 1, "e um pedido de IPC só, pelo mesmo motivo"


# ---------------------------------------------------------------------------
# Não finge, e não erra calado
# ---------------------------------------------------------------------------


def test_quando_o_som_nao_sai_a_tela_diz_que_nao_saiu_e_por_que(
    pedidos: _Pedidos,
) -> None:
    """Regra 4: se não houver como tocar, não finja — e não erre calado.

    Um clique que promete som e não entrega é pior que nenhum som. O selo diz
    QUE não houve confirmação; a dica do bloco diz POR QUÊ (a divisão é medida:
    a frase inteira no selo estoura a largura do card — ver o teste do
    orçamento).

    Mordida: fazer `_on_som_de_confirmacao` descartar o recado (o "errar
    calado"), ou não repintar o selo. As três asserções caem juntas.
    """
    pedidos.resultado = ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, SINK_CONTROLE)
    card = _card(speaker=POSSE)
    assert not card._speaker_selo_saida.get_visible(), "antes do clique, nada"

    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    # SOM-CANAL-01/E4 (02/08/2026) — decisão dela: *"essa parte do sem som faz
    # sentido continuar na interface? o slicer mostra isso"*. O selo passou a
    # mostrar SÓ a camada 1 (`Saída muda`), e o recado do som vive na dica.
    #
    # **O custo fica registrado, e é real:** a regra 4 da SOM-04 diz "se não
    # houver como tocar, não finja — e não erre calado", e uma dica exige
    # passar o mouse. O que continua sendo travado aqui é o essencial: o
    # recado é PRODUZIDO e CHEGA à dica. O que mudou foi onde ele aparece.
    assert not card._speaker_selo_saida.get_visible(), (
        "o selo mostra só a camada 1 desde a SOM-CANAL-01/E4"
    )
    # SOM-CANAL-01/E4: o recado saiu do selo e vive na dica do bloco.
    assert TEXTO_SELO_SEM_SOM not in card._speaker_selo_saida.get_text()
    assert "paplay" in card._speaker_box.get_tooltip_text(), (
        "e a dica do bloco tem de dizer POR QUÊ — errar calado é a falha que "
        "esta leva não pode ter"
    )


def test_o_som_que_sai_nao_deixa_recado_nenhum(pedidos: _Pedidos) -> None:
    """Som que sai É o recado. Escrever "toquei" ao lado dele seria ruído.

    E o selo tem de VOLTAR a sumir quando a confirmação volta a funcionar —
    um recado grudado na tela depois de resolvido é a janela mentindo devagar.

    Mordida: não limpar `_speaker_recado_do_som` no caminho de sucesso.
    """
    pedidos.resultado = ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, SINK_CONTROLE)
    card = _card(speaker=POSSE)
    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()
    # SOM-CANAL-01/E4: o recado do som deixou de acender o selo — ele
    # vive na dica do bloco desde 02/08 (decisão dela).
    assert not card._speaker_selo_saida.get_visible()

    pedidos.resultado = ResultadoDoSom.de(MOTIVO_TOCOU, SINK_CONTROLE)
    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    assert not card._speaker_selo_saida.get_visible(), "o recado sai quando resolve"
    # SOM-ACORDADO-01: a primeira linha da dica passou a depender da POSSE, e
    # aqui há posse (`POSSE`). A `DICA_BLOCO_SPEAKER` descreve o estado SEM
    # posse — *"o volume é do firmware do controle"* — e com o daemon mandando
    # o volume ela mentiria justamente no estado que virou o normal. O que este
    # teste afere continua sendo o mesmo: a dica é a linha-base e MAIS NADA.
    assert card._speaker_box.get_tooltip_text() == DICA_SPEAKER_POSSE_NOSSA
    assert _card(speaker=None)._speaker_box.get_tooltip_text().startswith(
        DICA_BLOCO_SPEAKER
    ), "e sem posse a linha-base continua sendo a de sempre"


def test_a_saida_muda_tem_prioridade_sobre_o_recado_do_som(
    pedidos: _Pedidos,
) -> None:
    """Os dois informantes do selo dizem a MESMA verdade — ela é dita uma vez.

    Com o sink do controle mudo no PipeWire (a camada 1), o motivo da recusa do
    som É a saída muda. O selo mostra o fato PERSISTENTE do sistema, e não o
    sintoma dele.

    Mordida: inverter a prioridade em `_aplicar_selo_do_som`. O selo passa a
    dizer "sem som" onde a causa tem nome, e a linha que a SENSOR-VIVO-01
    conquistou some da tela.
    """
    pedidos.resultado = ResultadoDoSom.de(audio_saida.MOTIVO_SAIDA_MUDA, SINK_CONTROLE)
    card = _card(speaker=POSSE, mic=_LeituraMic(saida_muda=True))
    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    assert card._speaker_selo_saida.get_text() == TEXTO_SELO_SAIDA_MUDA
    assert card._speaker_selo_saida.get_visible()


def test_com_dois_controles_nao_ha_sink_e_o_som_nao_e_chutado(
    pedidos: _Pedidos,
) -> None:
    """`escolher_sink` recusa de propósito, e o card obedece sem inventar.

    O nome do sink não carrega identidade (o `-00` é ordem de conexão, não
    número de série), então com dois DualSense a `status_actions` repassa "".
    Tocar assim cairia no sink PADRÃO — medido.

    Mordida: fazer `definir_sink_de_saida` guardar um valor padrão quando
    recebe "" (o reflexo de quem quer o som "sempre funcionando"). O sink vazio
    deixa de chegar ao motor e a asserção cai.
    """
    card = _card(speaker=POSSE, sink="")
    card._on_speaker_mudo_clicado(None)
    pedidos.rodar()

    assert [s["sink"] for s in pedidos.sons] == [""], (
        "o card repassa o vazio ao motor, que é quem recusa — o card não "
        "inventa sink nem cala o motor"
    )


# ---------------------------------------------------------------------------
# O orçamento de tela, contra o layout NOVO (SOM-03)
# ---------------------------------------------------------------------------


def test_o_recado_do_som_nao_gasta_um_pixel_de_largura(pedidos: _Pedidos) -> None:
    """O selo tem TETO, e o teto é a entrega — não estética.

    A primeira versão desta leva pôs a frase inteira no selo. Medido, com o
    card montado e alocado na escala de fonte da sessão: o mínimo do bloco
    saltou de 174 para 383px e o do card de 1040 para **1223**, estourando os
    1180px com que a janela abre. No compacto era pior: 550 para 827, o que com
    dois cards lado a lado pede 1690px.

    São DUAS curas, e cada uma tem asserção própria de propósito: sozinhas elas
    se cobrem (com o texto curto o teto nunca entra em ação; com o teto posto a
    frase inteira é cortada), e um teste que só olhasse a largura final passaria
    com qualquer uma das duas arrancada. Só as duas juntas estouram — e cura
    sem vermelho próprio é cura sem teste.

    Mordida A: tirar o `set_ellipsize`/`set_max_width_chars` do selo em
    `_montar_speaker` — cai a asserção do teto.
    Mordida B: pôr `self._speaker_recado_do_som` no texto do selo em vez de
    :data:`TEXTO_SELO_SEM_SOM` — cai a asserção do texto curto.
    Mordida A+B juntas: cai a asserção da largura, com o card em 1223px.

    POR QUE O TETO É DERIVADO, E NÃO UM NÚMERO (corrigido em 01/08/2026, depois
    de o runner reprovar): a primeira versão comparava com `1040` e `550`, os
    valores medidos NESTA bancada. No job `gtk-real` a fonte é outra e o card
    compacto pediu 556 contra os 550 literais — reprovando por 6px enquanto a
    condição que importa continuava satisfeita, porque dois cards compactos com
    556 pedem 1136 e a janela abre com 1180.

    Um teto literal em pixels não sobrevive a uma troca de fonte, e esta casa já
    mediu que a largura disponível nem sequer é monótona na escala da fonte. O
    teto passa a ser a pergunta de verdade — "os cards cabem na janela em que a
    aba vive?" —, derivada de `LARGURA_DE_PROJETO`, que por sua vez sai do
    glade. A asserção `depois == antes`, que é a entrega real desta página (o
    recado não gasta um pixel), não depende de fonte nenhuma e continua intacta.
    """
    pedidos.resultado = ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, SINK_CONTROLE)
    #: Quantos cards daquele tipo a aba Status põe lado a lado antes de rolar:
    #: o card largo é um só; os compactos vêm em dupla.
    for compact, por_linha in ((False, 1), (True, 2)):
        teto = LARGURA_DE_PROJETO // por_linha
        limpo = _card(compact=compact, speaker=POSSE)
        antes = limpo.get_preferred_width()[0]

        card = _card(compact=compact, speaker=POSSE)
        card._on_speaker_mudo_clicado(None)
        pedidos.rodar()
        while Gtk.events_pending():
            Gtk.main_iteration()
        depois = card.get_preferred_width()[0]
        selo = card._speaker_selo_saida

        # Cura A — o teto existe no widget.
        assert selo.get_ellipsize() == Pango.EllipsizeMode.END, (
            "o selo precisa de elipse: sem ela o texto dele decide o mínimo do "
            "bloco, e daí o do card e o da janela"
        )
        assert 0 < selo.get_max_width_chars() <= _SELO_CHARS, (
            f"o teto do selo tem de ser no máximo {_SELO_CHARS} caracteres — "
            f"recebido {selo.get_max_width_chars()}"
        )
        # Cura B — o texto do selo é o SELO, não a frase.
        # SOM-CANAL-01/E4: o selo mostra SÓ a camada 1; o recado do som
        # vive na DICA do bloco desde 02/08 (decisão dela).
        assert TEXTO_SELO_SEM_SOM not in selo.get_text(), (
            "o selo diz QUE não houve confirmação; quem diz POR QUÊ é a dica "
            f"do bloco — recebido {selo.get_text()!r}"
        )
        # E o resultado das duas juntas.
        assert depois == antes, (
            f"o recado do som mexeu na largura mínima do card "
            f"{'compacto' if compact else 'de um controle'}: {antes} -> "
            f"{depois}px, num teto de {LARGURA_DE_PROJETO}"
        )
        assert depois <= teto, f"o card pede {depois}px de {teto}"


def test_o_selo_com_recado_cabe_na_faixa_dos_cards(pedidos: _Pedidos) -> None:
    """A altura: o selo é a única peça do bloco que entra e sai em execução.

    A faixa dos cards da aba entrega **550px**, remedido em 01/08/2026 (noite)
    com a janela no tamanho de projeto (1180x830) e a escala de fonte da
    sessão, por `status_players_scroll.get_allocated_height()`.

    **O número anterior era 467 e caducou** — ele é anterior à
    ESTADO-TRES-LINHAS-01, que levou o frame "Estado" de cinco linhas para
    três e devolveu essa altura aos cards sem que ninguém remedisse. Com o
    frame ESCONDIDO (CARD-ÚNICO-01, um controle só) a faixa chega a 708px,
    mas o teto fica no pior caso de propósito: um limite que dependa da regra
    de visibilidade quebra no dia em que ela mudar.

    O selo aceso custa 21px, e é a peça mais fina da aba — é por isso que ela
    está escrita aqui.

    Mordida: dar ao selo uma linha própria a mais, ou pôr o recado num rótulo
    NOVO em vez de reusar o selo. O card passa da faixa e os botões caem
    abaixo da dobra da janela de projeto.
    """
    pedidos.resultado = ResultadoDoSom.de(MOTIVO_SEM_TOCADOR, SINK_CONTROLE)
    for compact in (False, True):
        card = _card(compact=compact, speaker=POSSE)
        card._on_speaker_mudo_clicado(None)
        pedidos.rodar()
        while Gtk.events_pending():
            Gtk.main_iteration()
        altura = card.get_preferred_height()[1]
        assert altura <= FAIXA_DOS_CARDS_PX, (
            f"o card {'compacto' if compact else 'de um controle'} com o "
            f"recado aceso pede {altura}px da faixa de {FAIXA_DOS_CARDS_PX}"
        )
