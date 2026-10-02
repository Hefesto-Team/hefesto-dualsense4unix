"""SOM-02 — o alto-falante que FUNCIONA: controle deslizante, mudo e devolução."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("status som 02 controle de volume")

import contextlib
from collections.abc import Iterator
from typing import Any, Final

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

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

LARGURA_DA_TELA_DELA = 1870


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


_janelas_vivas: list[Any] = []

_CICLOS_ATE_ALOCAR: Final[int] = 200


def _assentar(janela: Any, widget: Any) -> None:
    """Roda o laço de eventos ATÉ o widget receber alocação de verdade."""
    for _ in range(_CICLOS_ATE_ALOCAR):
        while Gtk.events_pending():
            Gtk.main_iteration()
        if widget.get_allocated_width() > 1 and widget.get_allocated_height() > 1:
            return
        with contextlib.suppress(Exception):
            janela.get_surface()
        janela.queue_resize()

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
    """Registra o que a interface MANDOU — e por onde mandou."""

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
    """O ``set_speaker_volume`` do backend como a SPRINT o mediu — sem guardas."""

    def __init__(self) -> None:
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
    """Aplica o tema COM a escala de fonte da sessão, e desfaz no fim."""

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


def test_sem_posse_o_controle_deslizante_convida_sem_afirmar_posicao() -> None:
    """Critério 1 da sprint, inteiro: existe, está HABILITADO, e não mente."""
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
    """O preço fica NA INTERFACE, e antes do gesto — não numa nota de rodapé."""
    card = _card(speaker=None)

    dica = card._speaker_escala.get_tooltip_text()

    assert dica == DICA_SPEAKER_ESCALA
    assert "fone" in dica, "a dica não diz que o fone vai junto (armadilha 3)"
    assert "não devolve" in dica, "a dica não diz que não existe leitura"
    assert TEXTO_BOTAO_SPEAKER_DEVOLVER in dica, "a dica não diz como sair"


def test_o_volume_vai_sempre_explicito_e_fora_da_thread_do_gtk(
    pedidos: _Pedidos,
) -> None:
    """Armadilha 1 + a regra do congelamento, num teste só."""
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
    """``value-changed`` dispara por pixel; o IPC é bloqueante e de uma thread."""
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


def test_e_impossivel_mandar_mudo_antes_de_um_volume(
    pedidos: _Pedidos,
) -> None:
    """Armadilha 2, medida — e a guarda é a INSENSIBILIDADE, não a boa vontade."""
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

    backend.aplicar({"muted": True})
    backend.aplicar({"muted": False})
    assert backend.estado() == {"volume": 0, "muted": True}


def test_silenciar_e_ativar_devolvem_o_mesmo_volume(
    pedidos: _Pedidos,
) -> None:
    """Critério 3: 180 -> mudo -> 180, o ciclo inteiro pela interface."""
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
    assert backend.volumes[0] == backend.volumes[1] == 180


def test_devolver_so_existe_com_posse_e_manda_release(
    pedidos: _Pedidos,
) -> None:
    """Devolver para de MANDAR; não restaura valor nenhum — e a dica diz isso."""
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
    """A cadeia inteira: `release` -> a chave `speaker` some -> "não ajustado"."""
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


@pytest.mark.parametrize("compact", [False, True])
def test_o_bloco_do_alto_falante_nunca_se_esconde(compact: bool) -> None:
    """MIC-PRESENTE-01, aplicada ao vizinho de baixo — nos DOIS cards."""
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
    """SENSOR-VIVO-01/E5: quando o SISTEMA é quem mutou, a faixa diz isso."""
    sem_leitura = _card(speaker={"volume": 180, "muted": False})
    assert sem_leitura._speaker_selo_saida.get_visible() is False

    aberta = _card(speaker={"volume": 180, "muted": False, "saida_muda": False})
    assert aberta._speaker_selo_saida.get_visible() is False

    muda = _card(speaker={"volume": 180, "muted": False, "saida_muda": True})
    assert muda._speaker_selo_saida.get_visible() is True
    assert muda._speaker_selo_saida.get_text() == TEXTO_SELO_SAIDA_MUDA
    assert muda._speaker_label.get_text() == f"{percentual_do_volume(180)} %"
    assert percentual_do_volume(180) == 100

    pelo_monitor = _card(speaker=None, mic=_LeituraMic(saida_muda=True))
    assert pelo_monitor._speaker_selo_saida.get_visible() is True
    assert pelo_monitor._speaker_label.get_text() == TEXTO_SPEAKER_SEM_DADO


def test_o_controle_novo_custa_zero_largura_no_card_compacto(
    _tema_na_escala_que_sai: None,
) -> None:
    """O mesmo teste que o botão do microfone passou, agora para o deslizante."""
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


PISO_DO_TRILHO_PX: Final[int] = 100


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
    """A exceção que o remapeamento NÃO pode engolir."""
    assert volume_do_percentual(0) == 0
    assert volume_do_percentual(-5) == 0
    assert percentual_do_volume(0) == 0


def test_a_barra_que_le_e_o_controle_que_manda_nunca_se_contradizem() -> None:
    """A trava do requisito: leitura e comando dizem o MESMO número."""
    for pct in range(0, 101):
        bruto = volume_do_percentual(pct)
        de_volta = percentual_do_volume(bruto)
        assert abs(de_volta - pct) <= 1, (
            f"a tela manda {pct} %, o registrador guarda {bruto} e a barra "
            f"relê {de_volta} %: leitura e comando falam réguas diferentes"
        )
        assert fracao_do_volume(bruto) * 100 == pytest.approx(
            percentual_do_volume(bruto), abs=0.5
        )


def _linhas_do_bloco_do_som(card: Any) -> list[Any]:
    """As linhas VISÍVEIS do miolo do bloco, sem o rótulo do próprio bloco."""
    caixa = card._speaker_box
    filhos = caixa.get_children()
    filhos = filhos[0].get_children() if not card._compact else filhos[1:]
    return [f for f in filhos if f.get_visible()]


@pytest.mark.parametrize("compact", [False, True])
def test_o_bloco_do_som_nao_gasta_linha_com_o_que_pode_dividir(
    compact: bool, _tema_na_escala_que_sai: None
) -> None:
    """A mesma regra de altura, dita sem um único pixel — e por isso estável."""
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
