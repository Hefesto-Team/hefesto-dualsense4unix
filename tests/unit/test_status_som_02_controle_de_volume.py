"""SOM-02 — o alto-falante que FUNCIONA: controle deslizante, mudo e devolução.

Até esta leva o bloco "Alto-falante" era uma barra e um rótulo que só sabia
dizer ``não ajustado``. Agora ele tem comando — e comando de um registrador
**sem leitura**, o que faz cada regra aqui ser uma trava contra uma armadilha
MEDIDA na sprint, e não preferência de desenho:

* mandar ``speaker.set`` sem ``volume`` toma a posse e emudece o controle em
  ZERO (armadilha 1);
* um botão de mudo que seja a PRIMEIRA escrita tranca o alto-falante em zero e
  o próprio botão não tem como soltá-lo (armadilha 2);
* o mesmo pedido escreve o volume do alto-falante E o do fone (armadilha 3);
* a posse morre com o cabo (armadilha 4).

Como em `test_status_som_e_janela.py`, TODA medida de geometria é feita com o
card MONTADO E ALOCADO numa `Gtk.OffscreenWindow`: widget sem alocação devolve
1x1 em tudo, e um teste de layout sobre ele passaria com qualquer desenho.

Cada teste diz no docstring qual é a MORDIDA — o que arrancar do
`controller_card.py` para vê-lo em vermelho.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("status som 02 controle de volume")

import contextlib
from collections.abc import Iterator
from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.theme import (
    ESCALA_PADRAO,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (

    DICA_SPEAKER_DEVOLVER,
    DICA_SPEAKER_ESCALA,
    DICA_SPEAKER_SEM_DADO,
    TEXTO_BOTAO_SPEAKER_ATIVAR,
    TEXTO_BOTAO_SPEAKER_DEVOLVER,
    TEXTO_BOTAO_SPEAKER_SEM_DADO,
    TEXTO_BOTAO_SPEAKER_SILENCIAR,
    TEXTO_SELO_SAIDA_MUDA,
    TEXTO_SPEAKER_SEM_DADO,
    ControllerCard,
)
from hefesto_dualsense4unix.core.speaker_scale import (
    _SPEAKER_REG_MUDO_ATE,
    _SPEAKER_REG_SATURA_EM,
    fracao_do_volume,
    percentual_do_volume,
    volume_do_percentual,
)

#: A largura que a aba Status recebe na tela dela, maximizada em 1920x1080.
LARGURA_DA_TELA_DELA = 1870

# OS QUATRO TESTES DE ORÇAMENTO DESTA PÁGINA SAÍRAM EM 06/09/2026 (`GTK-3`), e
# não porque deixaram de importar: eles montavam o `tab_status_box` do
# `gui/main.glade` numa `Gtk.OffscreenWindow` e mediam o card DENTRO da janela
# GTK — a superfície que a decisão dela aposentou
# (`D-0609-GTK-LEVA-INTEIRA`). Eram
# `test_a_aba_status_com_dois_cards_continua_cabendo_na_janela`,
# `test_a_coluna_do_som_nao_e_a_mais_alta_da_faixa` e os dois de trilho do
# SOM-03 (`…um_pixel_de_trilho_por_ponto_percentual`,
# `…nao_e_mais_curto_que_a_barra_que_ele_comanda`).
#
# **O QUE SE PERDE, escrito porque se perde mesmo:** o requisito do SOM-03 —
# *"a escala tem cerca de 30 pixels de largura, é só a bolinha"* — mediu o
# `Gtk.Scale` do `controller_card.py` espremido pela aba. O card continua vivo
# e é MOTOR (`app/widgets/`, que a sprint manda ficar), mas na interface nova
# ele é desenhado em HTML: o trilho que a pessoa arrasta hoje é um
# `<input type="range">`, e nenhuma régua desta casa mede a largura DELE. Quem
# for fechar essa linha começa por `interface/paginas/01-jogar.html`.
#
# O que ficou aqui é o que não dependia da janela: as dez armadilhas do
# registrador do alto-falante, os dois selos, o custo do card compacto e a
# aritmética de volume — 17 testes.



def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)

_INPUTS: dict[str, Any] = {
    "lx": 60,
    "ly": 200,
    "rx": 180,
    "ry": 90,
    "l2_raw": 200,
    "r2_raw": 40,
    "buttons": ["cross"],
    "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    "touchpad": {
        "touching": True,
        "x": 1440,
        "y": 270,
        "width": 1920,
        "height": 1080,
    },
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

#: O estado que produz o card MAIS ALTO que a aba consegue montar: com o
#: giroscópio em streaming, o card ganha a linha de movimento. Medir o
#: orçamento de altura contra o card curto seria medir o caso que não aperta —
#: e foi assim que a mordida da linha única passou a primeira vez que rodou.
_ESTADO_ALTO: dict[str, Any] = {
    "native_mode": False,
    "rumble_ff": {
        "per_vpad": [
            {"player": 1, "motion_streaming": True, "motion_hz": 250.0}
        ]
    },
}


class _LeituraMic:
    """Dublê da `LeituraMic` — o card lê `nivel`, `muted` e (E5) `saida_muda`."""

    def __init__(self, saida_muda: bool | None = None) -> None:
        self.nivel = 0.6
        self.muted = False
        if saida_muda is not None:
            self.saida_muda = saida_muda


#: As janelas ficam vivas numa lista de módulo: o Python coleta a referência
#: local assim que a função retorna, e um card sem toplevel volta a reportar
#: 1x1 no meio da asserção.
_janelas_vivas: list[Any] = []

#: Quantas rodadas do laço de eventos esperar pela alocação antes de desistir.
#: Generoso de propósito: o custo de uma rodada a mais é microssegundos, e o
#: custo de desistir cedo é um teste de layout que mede 1x1.
_CICLOS_ATE_ALOCAR: Final[int] = 200


def _assentar(janela: Any, widget: Any) -> None:
    """Roda o laço de eventos ATÉ o widget receber alocação de verdade.

    POR QUE ISTO EXISTE, e é a lição da leva: um `while Gtk.events_pending()`
    sozinho é uma aposta. Ele drena a fila que existe NAQUELE instante, e no
    runner de 01/08 (Xvfb, `gtk-real`) a fila estava vazia antes de o GTK ter
    feito a negociação de tamanho — o card saiu **1x1**, o `Gtk.Scale` devolveu
    `range_rect.width == -1`, e a asserção reprovou com "-1px de trilho", que
    descreve a bancada e não o desenho. Nesta máquina o mesmo código alocava,
    porque a fila chegava preenchida: o teste passava aqui e reprovava lá.

    Aqui a espera é pela CONDIÇÃO — alocação maior que 1x1 — e não por um número
    de rodadas ou por um relógio. Espera por relógio seria a mesma aposta com
    outra cara, e teste que depende de tempo é teste que reprova sozinho no dia
    em que o runner estiver carregado.

    Se a condição não vier em :data:`_CICLOS_ATE_ALOCAR` rodadas, a função
    devolve mesmo assim: quem chama tem a guarda de bancada e é ela que sabe
    dizer, com o nome certo, que a medida não pode ser lida.
    """
    for _ in range(_CICLOS_ATE_ALOCAR):
        while Gtk.events_pending():
            Gtk.main_iteration()
        if widget.get_allocated_width() > 1 and widget.get_allocated_height() > 1:
            return
        # `get_surface()` obriga a OffscreenWindow a renderizar, e a renderização
        # obriga a negociação de tamanho que a fila vazia não tinha disparado.
        with contextlib.suppress(Exception):
            janela.get_surface()
        janela.queue_resize()

    # ÚLTIMO RECURSO, e ele tem uma razão de existir que não é teimosia: as
    # bancadas que montam a aba a partir do glade usam uma `Gtk.Window` de
    # verdade, e não uma `OffscreenWindow`. Sob Xvfb **não há gerenciador de
    # janelas**, e sem ele ninguém entrega o tamanho à janela: ela pode nunca
    # ser mapeada e o filho fica em 1x1 para sempre, por mais que o laço rode.
    # Foi o que reprovou o CI da tag v0.6.0 num teste que passara no push do
    # branch minutos antes — a assinatura de corrida, não de desenho.
    #
    # Aqui a bancada faz o papel do gerenciador ausente: dá à janela o tamanho
    # que ela mesma pediu. Isso NÃO falseia a medição — o que se mede depois é
    # como o card REPARTE a largura que recebeu, e a largura que ele recebe é a
    # de projeto, exatamente como na tela dela. O que se elimina é o caso em que
    # ele não recebe largura nenhuma.
    with contextlib.suppress(Exception):
        janela.realize()
        largura, altura = janela.get_size_request()
        if largura > 1 and altura > 1:
            aloc = Gdk.Rectangle()
            aloc.x, aloc.y, aloc.width, aloc.height = 0, 0, largura, altura
            janela.size_allocate(aloc)
            while Gtk.events_pending():
                Gtk.main_iteration()


def _entry_com(speaker: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    """Uma entrada de ``state_full.controllers`` com (ou sem) a chave `speaker`.

    Sem posse a chave NÃO EXISTE — é assim que o daemon publica, e é o estado
    normal de qualquer sessão em que ninguém mexeu no volume.
    """
    entrada = dict(_ENTRY)
    entrada.update(extra)
    if speaker is None:
        entrada.pop("speaker", None)
    else:
        entrada["speaker"] = speaker
    return entrada


def _card(
    *,
    compact: bool = False,
    largura: int = LARGURA_DA_TELA_DELA,
    speaker: dict[str, Any] | None = None,
    mic: Any = None,
) -> Any:
    """Card montado, alocado e atualizado — a bancada de todos os testes."""
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(largura, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_entry_com(speaker), _ESTADO, mic if mic is not None else _LeituraMic())
    janela.resize(largura, 900)
    _assentar(janela, card)
    return card


class _Pedidos:
    """Registra o que a interface MANDOU — e por onde mandou.

    ``agendados`` guarda as funções entregues a ``run_in_thread`` SEM executá-
    las: é isso que prova que o clique não bloqueia a thread do GTK. Quem
    executa é o teste, na hora que quiser, chamando `rodar()`.
    """

    def __init__(self) -> None:
        self.agendados: list[Any] = []
        self.chamadas: list[dict[str, Any]] = []

    def run_in_thread(self, fn: Any, _ok: Any, _err: Any = None) -> None:
        self.agendados.append(fn)

    def speaker_set(self, **kwargs: Any) -> bool:
        self.chamadas.append(kwargs)
        return True

    def rodar(self) -> None:
        pendentes, self.agendados = self.agendados, []
        for fn in pendentes:
            fn()


@pytest.fixture
def pedidos(monkeypatch: pytest.MonkeyPatch) -> _Pedidos:
    espiao = _Pedidos()
    monkeypatch.setattr(ipc_bridge, "run_in_thread", espiao.run_in_thread)
    monkeypatch.setattr(ipc_bridge, "speaker_set", espiao.speaker_set)
    return espiao


class _AltoFalanteDeMentira:
    """O ``set_speaker_volume`` do backend como a SPRINT o mediu — sem guardas.

    Cópia fiel de ``core/backend_pydualsense.py`` no estado em que as quatro
    armadilhas foram executadas: sem `volume` e sem preferência, `pref` cai
    para 0, a posse é tomada e o efetivo vai a zero.

    **Por que sem a guarda que o backend ganhou depois.** O que este arquivo
    afere é a INTERFACE, e a interface não pode depender de uma guarda do outro
    lado do socket: daemon velho com janela nova é combinação real (o
    `speaker.set` existe no protocolo desde a D4). Se o dublê trouxesse a
    guarda, arrancar a insensibilidade do botão não produziria defeito nenhum
    aqui — e o teste passaria com a cura arrancada, que é a definição de teste
    que não testa nada.
    """

    def __init__(self) -> None:
        # fone, alto-falante, microfone, roteamento — `_volumes_audio`.
        self.volumes: list[int | None] = [None, None, None, None]
        self.pref: int | None = None

    def aplicar(self, pedido: dict[str, Any]) -> None:
        if pedido.get("release"):
            self.volumes = [None, None, None, None]
            self.pref = None
            return
        volume = pedido.get("volume")
        muted = pedido.get("muted")
        pref = self.pref
        if volume is not None:
            pref = max(0, min(255, int(volume)))
        if pref is None:
            pref = 0
        self.pref = pref
        efetivo = 0 if muted else pref
        # Armadilha 3: o MESMO valor vai para o fone e para o alto-falante.
        self.volumes[0] = efetivo
        self.volumes[1] = efetivo

    def estado(self) -> dict[str, Any] | None:
        """O que o daemon publicaria em ``state_full`` (`speaker_state_for`)."""
        if self.volumes[1] is None:
            return None
        efetivo = int(self.volumes[1])
        base = self.pref if self.pref is not None else efetivo
        return {"volume": max(0, min(255, int(base))), "muted": efetivo == 0}


@pytest.fixture(scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema COM a escala de fonte da sessão, e desfaz no fim.

    Os orçamentos de largura e altura são medidos com a fonte que de fato SAI:
    sem isto, ~90% da janela mediria os 13,33px do padrão do Pango e o número
    aferido não seria o da tela dela.
    """

    # A ESCALA É FIXADA — 25/08/2026. Esta fixture chamava `escala_fonte()`,
    # que lê o `gui_preferences.json` de QUEM RODA (nesta máquina, 6), e mexe
    # em `Gtk.Settings`, que é singleton do PROCESSO. Dois efeitos, os dois
    # medidos: o teste muda de veredito conforme a escala de quem roda, e a
    # escala vaza para os arquivos que rodam depois na mesma sessão do pytest.
    # Foi assim que dois testes de `test_layout_orcamento_altura.py`
    # reprovavam em lote e passavam sozinhos.
    #
    # A régua declarada é a `ESCALA_PADRAO`: é com ela que o produto nasce em
    # quem instala. A escala maior é escolha dela, e o que ela custa é OUTRA
    # pergunta, com outro teto.
    delta = ESCALA_PADRAO
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



# ---------------------------------------------------------------------------
# Entrega 1 — o controle deslizante, e o preço na própria interface
# ---------------------------------------------------------------------------


def test_sem_posse_o_controle_deslizante_convida_sem_afirmar_posicao() -> None:
    """Critério 1 da sprint, inteiro: existe, está HABILITADO, e não mente.

    Sem posse o daemon não publica a chave `speaker`, e mover é a única forma
    de o volume passar a ser conhecido — então o controle deslizante é o
    CONVITE e precisa estar clicável. O que ele não pode é afirmar posição: o
    cursor no meio com o rótulo ``não ajustado`` desenharia 50 % e o negaria
    por escrito na linha de cima.

    A mordida: deixar o controle insensível sem posse (o reflexo natural de
    quem copia o botão de mudo) derruba a segunda asserção; pôr o cursor em 50
    para "não parecer vazio" derruba a terceira.
    """
    card = _card(speaker=None)

    assert card._speaker_escala.get_visible() is True
    assert card._speaker_escala.get_sensitive() is True, (
        "o controle deslizante nasceu insensível: sem posse ele é a ÚNICA "
        "forma de o volume passar a ser conhecido"
    )
    assert card._speaker_escala.get_value() == 0, (
        f"o cursor está em {card._speaker_escala.get_value()} com o rótulo "
        f"dizendo {TEXTO_SPEAKER_SEM_DADO!r}: a tela afirma uma posição que "
        "ninguém ajustou"
    )
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO
    assert "%" not in card._speaker_label.get_text()


def test_a_dica_do_controle_diz_o_preco_antes_do_clique() -> None:
    """O preço fica NA INTERFACE, e antes do gesto — não numa nota de rodapé.

    Três verdades, e nenhuma delas é opcional: a posse passa a ser nossa, ela
    vale para o alto-falante E para o fone (o backend escreve os dois bytes), e
    não há leitura — quem manda segue sendo a janela até Devolver ou a
    desconexão.

    A mordida: apagar qualquer uma das três da :data:`DICA_SPEAKER_ESCALA`
    derruba a asserção correspondente.
    """
    card = _card(speaker=None)

    dica = card._speaker_escala.get_tooltip_text()

    assert dica == DICA_SPEAKER_ESCALA
    assert "fone" in dica, "a dica não diz que o fone vai junto (armadilha 3)"
    assert "não devolve" in dica, "a dica não diz que não existe leitura"
    # Ancorado na CONSTANTE, não no texto: em 16/08 o rótulo virou
    # "Liberar" (decisão dela) e este teste reprovou sem que nada de
    # estrutural tivesse mudado. A dica tem de citar o botão que existe,
    # qualquer que seja o nome dele.
    assert TEXTO_BOTAO_SPEAKER_DEVOLVER in dica, "a dica não diz como sair"


def test_o_volume_vai_sempre_explicito_e_fora_da_thread_do_gtk(
    pedidos: _Pedidos,
) -> None:
    """Armadilha 1 + a regra do congelamento, num teste só.

    ``speaker.set {}`` não é consulta: sem `volume` e sem preferência guardada
    o backend toma a posse e manda ZERO — medido, com o estado publicado
    virando ``{'volume': 0, 'muted': True}``. Por isso o pedido do controle
    deslizante carrega SEMPRE um inteiro explícito.

    E ele sai por ``run_in_thread``: o IPC é bloqueante, e foi num clique
    bloqueante que esta interface já congelou. A prova é que, com o
    ``run_in_thread`` dublado sem executar nada, NENHUMA chamada chegou ao
    ``speaker_set`` — se alguém trocar o pedido por uma chamada direta, ela
    aparece antes do `rodar()`.

    A mordida: trocar ``speaker_set(volume=..., uniq=...)`` por
    ``speaker_set(uniq=...)`` derruba a asserção do `volume`; chamar o
    `speaker_set` direto no callback derruba a de cima.
    """
    card = _card(speaker=None)

    card._speaker_escala.set_value(70)
    card._on_speaker_escala_solta(card._speaker_escala, None)

    assert pedidos.chamadas == [], (
        "o pedido chegou ao IPC ANTES do salto de thread: o clique está "
        "bloqueando a thread do GTK"
    )
    assert len(pedidos.agendados) == 1
    pedidos.rodar()

    assert len(pedidos.chamadas) == 1
    pedido = pedidos.chamadas[0]
    assert pedido.get("volume") == volume_do_percentual(70)
    assert isinstance(pedido["volume"], int)
    assert pedido.get("uniq") == _ENTRY["uniq"], (
        "o pedido foi sem `uniq`: com quatro controles o daemon aplicaria no "
        "primário e mexeria no volume de outra pessoa"
    )
    assert "muted" not in pedido and not pedido.get("release")


def test_arrastar_nao_vira_rajada_de_ipc(pedidos: _Pedidos) -> None:
    """``value-changed`` dispara por pixel; o IPC é bloqueante e de uma thread.

    Durante o arrasto NADA é mandado — o que existe é um repouso armado, de
    disparo único. Quem manda é o fim do gesto (ou o repouso, para o que não
    tem fim de gesto, como a roda do mouse).

    A mordida: mandar o pedido dentro do ``value-changed`` faz o arrasto de
    cinco passos virar cinco pedidos e derruba a primeira asserção.
    """
    card = _card(speaker=None)

    card._on_speaker_escala_pega(card._speaker_escala, None)
    for valor in (10, 20, 30, 40, 50):
        card._speaker_escala.set_value(valor)

    assert pedidos.agendados == [], (
        f"{len(pedidos.agendados)} pedidos durante UM arrasto: a interface "
        "está mandando um IPC por pixel"
    )
    assert card._speaker_repouso_id is not None, "o repouso não foi armado"

    card._on_speaker_escala_solta(card._speaker_escala, None)
    pedidos.rodar()

    assert len(pedidos.chamadas) == 1
    assert pedidos.chamadas[0]["volume"] == volume_do_percentual(50)
    assert card._speaker_repouso_id is None, (
        "o repouso continuou armado depois de o gesto terminar: ele vai "
        "disparar um segundo pedido com o mesmo valor"
    )
    # Disparo ÚNICO: um repouso que devolvesse True se re-armaria sozinho e
    # viraria o periódico que o gate de timers do card proíbe.
    assert card._on_speaker_repouso() is False


def test_repintar_a_leitura_nao_manda_pedido_de_volta(
    pedidos: _Pedidos,
) -> None:
    """O tique de 10 Hz repinta o controle — e repintar NÃO é comandar.

    Sem a guarda, cada releitura de ``daemon.state_full`` moveria o cursor, o
    ``value-changed`` armaria o repouso e o repouso mandaria o valor de volta
    ao daemon: um eco entre leitura e comando, dez vezes por segundo.

    A mordida: tirar o `_speaker_pintando` de `_pintar_escala_do_speaker` faz
    o repouso ser armado no primeiro tique e derruba as duas asserções.
    """
    card = _card(speaker={"volume": 180, "muted": False})

    assert card._speaker_escala.get_value() == percentual_do_volume(180)
    assert card._speaker_repouso_id is None, (
        "a releitura do estado armou um pedido: a tela está mandando de volta "
        "o que acabou de ler"
    )
    assert pedidos.agendados == []
    assert pedidos.chamadas == []


# ---------------------------------------------------------------------------
# Entrega 2 — o botão de mudo, com a primeira linha INSENSÍVEL
# ---------------------------------------------------------------------------


def test_e_impossivel_mandar_mudo_antes_de_um_volume(
    pedidos: _Pedidos,
) -> None:
    """Armadilha 2, medida — e a guarda é a INSENSIBILIDADE, não a boa vontade.

    O dublê do backend reproduz o que a sprint executou: com `muted` como
    PRIMEIRA escrita, `pref` cai para 0, a posse é tomada, e o "desmudo"
    seguinte restaura... zero. O par tranca em ``{'volume': 0, 'muted': True}``
    e o próprio botão não tem como soltá-lo.

    O teste prova as duas metades: que a armadilha é real (o dublê cai nela
    quando alguém manda o mudo direto) e que a interface NÃO tem como cair
    nela — o botão nasce insensível e o clique não manda nada.

    A mordida: fazer `acao_speaker_mudo` devolver `sensivel=True` sem posse faz
    o clique mandar `{muted: True}`, o dublê trancar em zero e as asserções de
    baixo caírem.
    """
    backend = _AltoFalanteDeMentira()
    card = _card(speaker=backend.estado())

    assert card._speaker_botao_mudo.get_sensitive() is False
    assert (
        card._speaker_botao_mudo._rotulo_hefesto.get_text()
        == TEXTO_BOTAO_SPEAKER_SEM_DADO
    )
    assert card._speaker_botao_mudo.get_tooltip_text() == DICA_SPEAKER_SEM_DADO

    card._on_speaker_mudo_clicado(card._speaker_botao_mudo)
    pedidos.rodar()

    assert pedidos.chamadas == [], (
        f"a interface mandou {pedidos.chamadas} sem volume conhecido: é a "
        "sequência que tranca o alto-falante em zero"
    )
    assert backend.estado() is None, "a posse foi tomada sem ninguém pedir"

    # A armadilha existe, e é isto que a insensibilidade evita: bastam dois
    # cliques para o alto-falante ficar mudo sem saída pelo próprio botão.
    backend.aplicar({"muted": True})
    backend.aplicar({"muted": False})
    assert backend.estado() == {"volume": 0, "muted": True}


def test_silenciar_e_ativar_devolvem_o_mesmo_volume(
    pedidos: _Pedidos,
) -> None:
    """Critério 3: 180 -> mudo -> 180, o ciclo inteiro pela interface.

    Com um volume de verdade na mão, o par funciona: `muted=True` manda zero e
    guarda a preferência, `muted=False` a devolve. O rótulo acompanha —
    ``mudo`` sem perder o volume preferido, e a porcentagem de volta depois.

    A mordida: mandar `volume=0` no lugar de `muted=True` (o atalho "é só
    baixar tudo") apaga a preferência no dublê e o "Ativar" volta com 0 %.
    """
    backend = _AltoFalanteDeMentira()
    backend.aplicar({"volume": 180})
    card = _card(speaker=backend.estado())

    assert (
        card._speaker_botao_mudo._rotulo_hefesto.get_text()
        == TEXTO_BOTAO_SPEAKER_SILENCIAR
    )
    card._on_speaker_mudo_clicado(card._speaker_botao_mudo)
    pedidos.rodar()
    assert pedidos.chamadas[-1] == {"muted": True, "uniq": _ENTRY["uniq"]}
    backend.aplicar(pedidos.chamadas[-1])

    card.update(_entry_com(backend.estado()), _ESTADO, _LeituraMic())
    assert backend.volumes[1] == 0, "o alto-falante não emudeceu"
    assert card._speaker_label.get_text() == "Mudo"
    assert (
        card._speaker_botao_mudo._rotulo_hefesto.get_text()
        == TEXTO_BOTAO_SPEAKER_ATIVAR
    )

    card._on_speaker_mudo_clicado(card._speaker_botao_mudo)
    pedidos.rodar()
    assert pedidos.chamadas[-1] == {"muted": False, "uniq": _ENTRY["uniq"]}
    backend.aplicar(pedidos.chamadas[-1])

    assert backend.estado() == {"volume": 180, "muted": False}, (
        f"o volume voltou como {backend.estado()}: o mudo perdeu a preferência "
        "de 180 pelo caminho"
    )
    # Armadilha 3, dita na tela e verdadeira no report: fone e alto-falante
    # recebem o MESMO valor, e é isso que a dica promete.
    assert backend.volumes[0] == backend.volumes[1] == 180


# ---------------------------------------------------------------------------
# Entrega 3 (o lado da janela) — a devolução da posse
# ---------------------------------------------------------------------------


def test_devolver_so_existe_com_posse_e_manda_release(
    pedidos: _Pedidos,
) -> None:
    """Devolver para de MANDAR; não restaura valor nenhum — e a dica diz isso.

    Sem posse não há o que devolver e o botão fica insensível: um `release`
    ali pediria ao daemon que soltasse um byte que ele nunca tomou. Com posse,
    o pedido é `release=True` e NADA além — reaproveitar `muted: null` como
    devolução criaria duas leituras para o mesmo payload (aqui a ausência de
    `muted` já significa "não mexer").

    A mordida: mandar `muted=False` no lugar do `release` derruba a asserção do
    payload; deixar o botão sensível sem posse derruba a primeira.
    """
    sem_posse = _card(speaker=None)
    assert sem_posse._speaker_botao_devolver.get_sensitive() is False
    sem_posse._on_speaker_devolucao_clicada(sem_posse._speaker_botao_devolver)
    pedidos.rodar()
    assert pedidos.chamadas == []

    card = _card(speaker={"volume": 180, "muted": False})
    botao = card._speaker_botao_devolver
    assert botao.get_sensitive() is True
    assert botao._rotulo_hefesto.get_text() == TEXTO_BOTAO_SPEAKER_DEVOLVER
    assert botao.get_tooltip_text() == DICA_SPEAKER_DEVOLVER
    assert "continua até você desconectar" in DICA_SPEAKER_DEVOLVER, (
        "a dica promete restauração: não há leitura, logo não há restauração"
    )

    card._on_speaker_devolucao_clicada(botao)
    pedidos.rodar()

    assert pedidos.chamadas == [{"release": True, "uniq": _ENTRY["uniq"]}]


def test_depois_da_devolucao_a_tela_volta_a_nao_sei(pedidos: _Pedidos) -> None:
    """A cadeia inteira: `release` -> a chave `speaker` some -> "não ajustado".

    É o mesmo caminho da armadilha 4 (desconectar o controle apaga a posse), e
    por isso vale a pena aferi-lo aqui: o card não pode guardar o último valor
    conhecido como se ainda valesse.

    A mordida: pintar o volume a partir do valor MANDADO (em vez da releitura)
    faz a porcentagem sobreviver ao release e derruba as asserções.
    """
    backend = _AltoFalanteDeMentira()
    backend.aplicar({"volume": 180})
    card = _card(speaker=backend.estado())
    assert card._speaker_label.get_text() != TEXTO_SPEAKER_SEM_DADO

    card._on_speaker_devolucao_clicada(card._speaker_botao_devolver)
    pedidos.rodar()
    backend.aplicar(pedidos.chamadas[-1])
    card.update(_entry_com(backend.estado()), _ESTADO, _LeituraMic())

    assert backend.estado() is None
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO
    assert card._speaker_escala.get_value() == 0
    assert card._speaker_botao_mudo.get_sensitive() is False
    assert card._speaker_botao_devolver.get_sensitive() is False
    assert card._speaker_box.get_visible() is True


# ---------------------------------------------------------------------------
# Entrega 5 — o que a tela diz quando não há leitura (+ SENSOR-VIVO-01/E5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("compact", [False, True])
def test_o_bloco_do_alto_falante_nunca_se_esconde(compact: bool) -> None:
    """MIC-PRESENTE-01, aplicada ao vizinho de baixo — nos DOIS cards.

    Esconder um bloco de uma faixa horizontal muda a largura de todos os
    vizinhos, e sumir é indistinguível de "este controle não tem alto-falante".
    Vale com dado, sem dado e sem leitor de inputs.

    A mordida: um `self._speaker_box.hide()` em qualquer um dos três caminhos
    derruba a asserção correspondente.
    """
    card = _card(compact=compact, largura=600 if compact else LARGURA_DA_TELA_DELA)
    assert card._speaker_box.get_visible() is True

    card.update(_entry_com(None), _ESTADO, None)
    while Gtk.events_pending():
        Gtk.main_iteration()
    assert card._speaker_box.get_visible() is True
    assert card._speaker_escala.get_visible() is True

    card.reset_inputs()
    while Gtk.events_pending():
        Gtk.main_iteration()
    assert card._speaker_box.get_visible() is True
    assert card._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO


def test_a_dica_do_bloco_explica_o_silencio() -> None:
    """Uma linha no lugar do nada: a diferença entre "não sei" e "quebrado".

    E sem posse ela leva junto o CAMINHO ("use o controle deslizante
    primeiro"), porque no GTK3 um botão insensível não recebe evento e não
    mostra dica própria — a explicação ficaria invisível justamente no estado
    em que é necessária.

    A mordida: tirar o `set_tooltip_text` do bloco derruba as duas.
    """
    sem_posse = _card(speaker=None)
    com_posse = _card(speaker={"volume": 180, "muted": False})

    dica_sem = sem_posse._speaker_box.get_tooltip_text() or ""
    dica_com = com_posse._speaker_box.get_tooltip_text() or ""

    assert "não o devolve" in dica_sem and "não o devolve" in dica_com
    assert DICA_SPEAKER_SEM_DADO in dica_sem
    assert DICA_SPEAKER_SEM_DADO not in dica_com


def test_o_selo_de_saida_muda_so_aparece_com_leitura_da_camada_1() -> None:
    """SENSOR-VIVO-01/E5: quando o SISTEMA é quem mutou, a faixa diz isso.

    Com o sink do controle mudo no PipeWire, mover o volume do registrador HID
    não produz som nenhum — e o bloco pareceria mentiroso mostrando uma
    porcentagem. O selo aparece SÓ quando a leitura da camada 1 disser que a
    saída está muda, e **nada** quando não houver como saber: um selo aceso por
    ausência de leitura seria a mesma mentira, do outro lado.

    As duas posições aceitas são as duas de onde a leitura pode vir — o payload
    do daemon e a leitura de PipeWire da própria janela.

    A mordida: acender o selo com `saida_muda` ausente (tratando None como
    "mudo") derruba o primeiro caso; ignorar a chave do payload derruba o
    segundo.
    """
    sem_leitura = _card(speaker={"volume": 180, "muted": False})
    assert sem_leitura._speaker_selo_saida.get_visible() is False

    aberta = _card(speaker={"volume": 180, "muted": False, "saida_muda": False})
    assert aberta._speaker_selo_saida.get_visible() is False

    muda = _card(speaker={"volume": 180, "muted": False, "saida_muda": True})
    assert muda._speaker_selo_saida.get_visible() is True
    assert muda._speaker_selo_saida.get_text() == TEXTO_SELO_SAIDA_MUDA
    # E o bloco continua dizendo o que a camada 2 sabe: são duas verdades
    # diferentes, e o selo não apaga a outra. O número é DERIVADO da régua
    # medida (SOM-03) e não escrito à mão: com a régua linear antiga um
    # registrador em 180 lia "71 %", e a medição no hardware mostrou que 180
    # já está saturado — o que a camada 2 sabe é "no máximo", e é isso que o
    # rótulo tem de dizer enquanto a camada 1 diz que nada sai.
    assert muda._speaker_label.get_text() == f"{percentual_do_volume(180)} %"
    assert percentual_do_volume(180) == 100

    pelo_monitor = _card(speaker=None, mic=_LeituraMic(saida_muda=True))
    assert pelo_monitor._speaker_selo_saida.get_visible() is True
    assert pelo_monitor._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO


# ---------------------------------------------------------------------------
# Os dois orçamentos — reaferidos nesta bancada, não presumidos
# ---------------------------------------------------------------------------


def test_o_controle_novo_custa_zero_largura_no_card_compacto(
    _tema_na_escala_que_sai: None,
) -> None:
    """O mesmo teste que o botão do microfone passou, agora para o deslizante.

    A largura é a restrição DURA desta aba: com 2+ controles os cards vão lado
    a lado e a rolagem horizontal é `never`, então o mínimo de cada card sobe
    somado até a janela. O botão do microfone custou zero porque o mínimo dele
    (38px) fica abaixo do mínimo do bloco; o controle deslizante (34px) e os
    dois botões novos passam pelo mesmo crivo.

    A aferição NÃO é contra um número escrito à mão: o piso é DERIVADO dos
    filhos que o bloco já tinha antes da SOM-02 (o rótulo da moldura, a barra
    de leitura e o rótulo de valor), e o que se cobra é que nenhum dos filhos
    novos passe desse piso.

    Medido nesta bancada, com a fonte na escala da sessão e o card compacto:
    rótulo "Alto-falante" 80px, barra 60px, rótulo de valor ``não ajustado``
    89px — é ELE quem dita o mínimo do bloco, e não o título, o que já valia
    antes desta leva. Os filhos novos: controle deslizante 34px, linha dos dois
    botões 80px. Nenhum chega aos 89.

    A mordida: dar ao controle deslizante o piso de 160px da barra fina (o
    reflexo de "ele tem que ter o tamanho da barra") leva o mínimo do bloco de
    89 para 206px e a aba com dois cards de 1148 para 1272px.
    """
    card = _card(compact=True, largura=600)

    rotulo_do_bloco = card._speaker_box.get_children()[0]
    assert rotulo_do_bloco.get_text() == "Alto-falante"
    piso_de_antes = max(
        rotulo_do_bloco.get_preferred_width()[0],
        card._speaker_bar.get_preferred_width()[0],
        card._speaker_label.get_preferred_width()[0],
    )
    minimo_do_bloco = card._speaker_box.get_preferred_width()[0]
    minimo_da_escala = card._speaker_escala.get_preferred_width()[0]
    minimo_dos_botoes = (
        card._speaker_botao_mudo.get_parent().get_preferred_width()[0]
    )

    assert minimo_do_bloco == piso_de_antes, (
        f"o bloco pede {minimo_do_bloco}px e os filhos que ele já tinha só "
        f"{piso_de_antes}px: o comando novo passou a decidir a largura da "
        "coluna, e ela sobe somada nos cards lado a lado"
    )
    assert minimo_da_escala <= piso_de_antes, (
        f"o controle deslizante pede {minimo_da_escala}px contra os "
        f"{piso_de_antes}px que o bloco já custava"
    )
    assert minimo_dos_botoes <= piso_de_antes, (
        f"a linha dos botões pede {minimo_dos_botoes}px contra os "
        f"{piso_de_antes}px que o bloco já custava"
    )


# ---------------------------------------------------------------------------
# SOM-03 — o controle deslizante tem de dar para ARRASTAR
# ---------------------------------------------------------------------------

#: Piso do trilho do controle deslizante, em px de TRILHO (e não de widget).
#:
#: Não é preferência de desenho: o controle vai de 0 a 100 e cada ponto
#: percentual precisa de ao menos UM pixel próprio para ser alcançável com o
#: ponteiro. Abaixo disso o gesto deixa de escolher o valor — ele escolhe uma
#: faixa de valores, e qual deles sai depende de um pixel a mais ou a menos.
#:
#: Medido na tela dela em 01/08, com a janela na largura de projeto e o
#: controle dividindo a linha com os dois botões: **14px de trilho para 100
#: pontos**, ou 7,1 pontos por pixel — *"é só a bolinha, sem trilho"*.
#:
#: Por que o trilho e não a alocação: a alocação inclui o respiro que o tema
#: reserva nas pontas (24px medidos nesta bancada, 12 de cada lado), e esse
#: número é do TEMA, não nosso. `get_range_rect()` devolve o retângulo em que
#: o cursor de fato anda, que é a grandeza que o dedo dela usa.
PISO_DO_TRILHO_PX: Final[int] = 100




# ---------------------------------------------------------------------------
# SOM-03/E2 — o curso do controle tem de produzir SOM em todo o percurso
# ---------------------------------------------------------------------------


def test_o_curso_inteiro_do_controle_cabe_na_faixa_que_soa() -> None:
    """Medição no hardware em 01/08: o registrador é fortemente NÃO-LINEAR.

    Tom de 1 kHz no sink, o microfone do próprio DualSense como instrumento,
    Goertzel no bin de 1 kHz, sink e mixer ALSA travados e só o registrador
    variando. A curva (registrador cru -> magnitude)::

        0 -> 3,9    13 -> 5,3    26 -> 3,1    38 -> 6,2     <- tudo MUDO
        51 -> 35    64 -> 172    76 -> 687                  <- a faixa audível
        102 -> 8759  128 -> 8488  255 -> 8793               <- saturado

    Com a régua linear ``pct * 255 / 100`` que a SOM-02 usava, o controle
    deslizante que a SOM-03 acabou de alargar para 240px seria 240px de curso
    em que **os primeiros 15 % emudecem, tudo o que se ouve cabe entre 15 % e
    40 %, e os últimos 60 % não fazem nada**. Alargar o controle sem isto seria
    dar mais pixels ao trecho inerte.

    Este teste cobra as três pontas do remapeamento de APRESENTAÇÃO:

    1. o topo do curso é a saturação e não passa dela — nenhum pedaço do curso
       cai na região em que o volume não muda mais;
    2. nenhuma porcentagem acima de zero cai na região MUDA — pedir 1 % e
       receber silêncio seria o mesmo defeito, do outro lado;
    3. o curso é monótono e percorre a faixa audível inteira.

    A mordida: devolver ``volume_do_percentual`` a ``round(pct * 255 / 100)``
    derruba (1) com 255 contra uma saturação em 102 e (2) com 1 % virando um
    registrador 3, que a curva mede como mudo.
    """
    assert volume_do_percentual(100) == _SPEAKER_REG_SATURA_EM, (
        f"100 % da tela manda {volume_do_percentual(100)} cru e o registrador "
        f"satura em {_SPEAKER_REG_SATURA_EM}: a diferença é curso do controle "
        "que não muda nada no ouvido"
    )
    for pct in range(1, 101):
        bruto = volume_do_percentual(pct)
        assert bruto > _SPEAKER_REG_MUDO_ATE, (
            f"{pct} % da tela manda o registrador {bruto}, que a medição de "
            f"01/08 põe na região MUDA (até {_SPEAKER_REG_MUDO_ATE}): esse "
            "pedaço do curso não faz som nenhum"
        )
        assert bruto <= _SPEAKER_REG_SATURA_EM, (
            f"{pct} % da tela manda {bruto}, acima da saturação"
        )
    percurso = [volume_do_percentual(p) for p in range(0, 101)]
    assert percurso == sorted(percurso), "o curso deixou de ser monótono"


def test_zero_por_cento_e_mudo_de_verdade_e_nao_o_piso_da_faixa_util() -> None:
    """A exceção que o remapeamento NÃO pode engolir.

    O resto do curso é a régua da faixa audível, mas o zero da tela tem de
    virar zero no REGISTRADOR — e não :data:`_SPEAKER_REG_MUDO_ATE`. Os dois
    soam igual (silêncio), só que apenas um é o valor que o resto do sistema
    reconhece como desligado: o perfil o persiste, o CLI o lê e
    ``acao_speaker_mudo`` decide a partir dele.

    A mordida: mapear 0 % para o piso da faixa útil (o atalho natural de quem
    escreve ``PISO + pct * faixa / 100`` sem o caso especial) faz o zero da
    tela gravar 38 no perfil dela.
    """
    assert volume_do_percentual(0) == 0
    assert volume_do_percentual(-5) == 0
    assert percentual_do_volume(0) == 0


def test_a_barra_que_le_e_o_controle_que_manda_nunca_se_contradizem() -> None:
    """A trava do requisito: leitura e comando dizem o MESMO número.

    São duas peças com dois significados (E5), e é justamente por isso que o
    remapeamento seria perigoso: se o controle mandasse 50 % pela régua nova e
    a barra relesse o cru pela régua velha, a tela passaria a se contradizer
    sozinha — 50 % no cursor e 20 % na barra logo acima.

    A cura não é combinar as duas contas, é ter UMA: barra, rótulo e controle
    passam todos por `fracao_do_volume` / `percentual_do_volume`, e
    `volume_do_percentual` é o inverso dela. Aqui se afere a volta completa,
    que é o que a tela faz a 10 Hz — manda a porcentagem, o daemon devolve o
    cru, a tela relê.

    O ponto percentual de tolerância é a resolução do registrador aparecendo:
    a faixa útil tem 64 passos para 100 pontos de tela. Não é discordância —
    as três peças saltam JUNTAS para o mesmo número, porque saem da mesma
    função.

    A mordida: remapear só o envio (``volume_do_percentual``) e deixar a
    leitura em ``bruto / 255`` — a saída mais provável de quem lê o pedido do
    hardware e mexe no lugar mais óbvio — faz 50 % voltar como 27 % e derruba
    todos os casos de uma vez.
    """
    for pct in range(0, 101):
        bruto = volume_do_percentual(pct)
        de_volta = percentual_do_volume(bruto)
        assert abs(de_volta - pct) <= 1, (
            f"a tela manda {pct} %, o registrador guarda {bruto} e a barra "
            f"relê {de_volta} %: leitura e comando falam réguas diferentes"
        )
        # E a barra desenha exatamente a mesma grandeza que o rótulo escreve.
        assert fracao_do_volume(bruto) * 100 == pytest.approx(
            percentual_do_volume(bruto), abs=0.5
        )



def _linhas_do_bloco_do_som(card: Any) -> list[Any]:
    """As linhas VISÍVEIS do miolo do bloco, sem o rótulo do próprio bloco.

    No card de um controle o bloco é um `Gtk.Frame` (o título é o rótulo da
    moldura, fora do miolo); no compacto é uma caixa cujo primeiro filho é o
    título. Esta função devolve as duas coisas na mesma moeda.
    """
    caixa = card._speaker_box
    filhos = caixa.get_children()
    filhos = filhos[0].get_children() if not card._compact else filhos[1:]
    return [f for f in filhos if f.get_visible()]


@pytest.mark.parametrize("compact", [False, True])
def test_o_bloco_do_som_nao_gasta_linha_com_o_que_pode_dividir(
    compact: bool, _tema_na_escala_que_sai: None
) -> None:
    """A mesma regra de altura, dita sem um único pixel — e por isso estável.

    A coluna do som é a mais alta do card compacto, e ali toda linha do bloco
    é uma linha do CARD. O bloco tem três assuntos e portanto tem direito a
    três linhas:

    1. a LEITURA — a barra mais o número que ela desenha;
    2. o COMANDO — o controle deslizante, sozinho na linha dele (é isso que
       lhe dá trilho: `GtkBox` vertical entrega a largura inteira ao filho
       único da linha);
    3. as AÇÕES — silenciar e devolver.

    Uma QUARTA linha é sempre o mesmo defeito: um rótulo de 19px ocupando
    sozinho uma linha inteira que ele podia dividir. Era o que o card compacto
    fazia — barra / controle / número / botões — e custava 21px de card em
    todas as fontes.

    Por que contar linhas e não pixels: o número de linhas não muda com a
    fonte, com o tema, com o Xvfb nem com o runner. Foi um orçamento em pixels
    absolutos que reprovou no CI medindo a mesma faixa como 431px num arquivo
    e 383px noutro, no mesmo processo.

    A mordida: devolver o rótulo de valor à linha só dele no card compacto
    (``miolo.pack_start(valor, ...)`` entre o controle e os botões) faz o miolo
    ir a quatro linhas e derruba o caso compacto — conferido em 01/08, com o
    card compacto caindo de 434 para 448px de altura pedida.
    """
    card = ControllerCard(compact=compact)
    janela = Gtk.OffscreenWindow()
    janela.add(card)
    janela.set_size_request(600 if compact else LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(
        _entry_com({"volume": 180, "muted": False}), _ESTADO, _LeituraMic()
    )
    _assentar(janela, card)

    linhas = _linhas_do_bloco_do_som(card)

    assert len(linhas) <= 3, (
        f"o bloco do alto-falante do card "
        f"{'compacto' if compact else 'de um controle'} gasta "
        f"{len(linhas)} linhas para três assuntos (leitura, comando, ações): "
        "a linha a mais é altura de card em toda fonte"
    )
    # E as três continuam sendo as três: o controle deslizante SOZINHO na dele,
    # que é o que lhe dá trilho.
    linha_do_controle = card._speaker_escala.get_parent()
    assert linha_do_controle is not None
    irmaos = [
        f for f in linha_do_controle.get_children() if f.get_visible()
    ]
    assert card._speaker_escala in irmaos
    assert linha_do_controle.get_orientation() == Gtk.Orientation.VERTICAL, (
        "o controle deslizante voltou a dividir a linha com alguém: numa caixa "
        "horizontal ele recebe o natural dele (34px) e o resto vai para os "
        "vizinhos, que era o defeito dos 30px"
    )
