"""SOM-04, entrega 2 — o botão que manda o som do sistema para o controle.

A pergunta dela, literal: *"na hora do jogo vai funcionar a vera?"* Até esta
leva, não: o áudio do jogo ia para o HDMI e o controle deslizante do bloco
"Alto-falante" ajustava um alto-falante que não estava recebendo som nenhum.

Este arquivo afere a FIAÇÃO — onde o botão mora, quanto ele custa de tela, e
que nenhum `pactl` roda na thread do GTK. O motor (ler, trocar, desfazer,
rotular) é aferido em `test_som_04_confirmacao_e_rota.py`.

**Por que o botão não está no bloco "Alto-falante", que é onde a sprint o
pediu.** Medido em 01/08/2026 com o card montado e alocado numa
`Gtk.OffscreenWindow`, na escala de fonte da sessão (+3) e na janela de
projeto: um botão a mais no bloco custa +0px de largura e **+36px de altura**,
e leva o card de 442 para **478px** contra os **467px** da faixa. Não cabe. E
há uma razão de significado que sobrevive à medição: a saída padrão é um fato
do SISTEMA, não do controle — com dois cards lado a lado haveria dois botões
para um único interruptor global, e só um deles poderia estar certo.

OS TRÊS TESTES DE GEOMETRIA SAÍRAM EM 06/09/2026 (`GTK-3`)
-----------------------------------------------------------

Eles montavam o `gui/main.glade` numa `Gtk.OffscreenWindow` do tamanho de
projeto e mediam ONDE o botão mora, quanto ele custa de largura e se ele cabe
no vão do grid. A superfície que eles mediam é a janela GTK, aposentada por
decisão dela (`D-0609-GTK-LEVA-INTEIRA`) — eram
`test_o_botao_mora_no_bloco_do_alto_falante_e_nasce_insensivel`,
`test_o_botao_da_rota_custa_zero_do_orcamento_da_aba` e
`test_o_botao_ocupa_o_vao_horizontal_que_ja_existia`.

**O que fica é a FIAÇÃO, que é o motor e não muda de dono:** nenhum `pactl` na
thread do GTK, o tique de reconexão que relê a rota, o ciclo completo de ida e
volta, o clique sem alvo e o caso de dois controles. A medição *"+0px de
largura e +36px de altura"* do cabeçalho acima continua sendo o registro do
porquê de o botão não morar no bloco "Alto-falante" — ela é decisão medida, e
esta casa não a apaga; o que morreu foi a régua que a reconferia na janela.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("status som 04 rota")

from typing import Any, NamedTuple

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

import pytest

pytest.importorskip("cairo")

from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.audio_saida import (
    TEXTO_ROTA_PARA_O_CONTROLE,
    TEXTO_ROTA_VOLTAR,
    EstadoDaRota,
)
from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.theme import (
    ESCALA_PADRAO,
    escalar_css,
    escalar_nome_da_fonte,
)

#: O id do botão no Glade. Ele é CONTRATO entre o Glade e a mixin, e trocá-lo
#: sem trocar os dois lados deixa a aba montar e o botão morto para sempre.
ID_BOTAO = "btn_som_no_controle"

SINK_CONTROLE = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
SINK_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _gtk_pronto(), reason="sem GTK/display utilizável")

_janelas_vivas: list[Any] = []


@pytest.fixture(scope="module", autouse=True)
def _tema_na_escala_que_sai() -> Any:
    """O tema COM a escala de fonte da sessão, e desfeito no fim.

    Sem isto, ~90% da janela mediria os 13,33px do padrão do Pango e o número
    aferido não seria o da tela dela (a sessão desta bancada roda em +3).
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




# ---------------------------------------------------------------------------
# A fiação na mixin — e nenhum subprocess na thread do GTK
# ---------------------------------------------------------------------------


class _Pactl:
    """Dublê do `pactl` que ANOTA tudo — inclusive de que thread foi chamado."""

    def __init__(self, padrao: str = SINK_HDMI) -> None:
        self.padrao = padrao
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "get-default-sink"]:
            return self.padrao + "\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            return f"1\t{SINK_CONTROLE}\tPipeWire\n2\t{SINK_HDMI}\tPipeWire\n"
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.padrao = argv[2]
        return ""


class _Adiados:
    """Guarda o que foi entregue a `run_in_thread` SEM executar.

    É isso que prova que o clique e a releitura não bloqueiam a thread do GTK:
    quem executa é o teste, na hora que quiser.
    """

    def __init__(self) -> None:
        self.pendentes: list[tuple[Any, Any]] = []

    def run_in_thread(self, fn: Any, ok: Any, _err: Any = None) -> None:
        self.pendentes.append((fn, ok))

    def rodar(self) -> None:
        while self.pendentes:
            fn, ok = self.pendentes.pop(0)
            ok(fn())


class _Botao:
    """Botão de mentira: registra rótulo, sensibilidade e dica."""

    def __init__(self) -> None:
        self.rotulo = ""
        self.sensivel = False
        self.dica = ""
        self.handlers: list[Any] = []

    def set_label(self, v: str) -> None:
        self.rotulo = v

    def set_sensitive(self, v: bool) -> None:
        self.sensivel = bool(v)

    def set_tooltip_text(self, v: str) -> None:
        self.dica = v

    def connect(self, _sinal: str, fn: Any) -> None:
        self.handlers.append(fn)


class _Builder:
    def __init__(self, botao: Any) -> None:
        self._w: dict[str, Any] = {ID_BOTAO: botao}

    def get_object(self, wid: str) -> Any:
        return self._w.get(wid)


class _Host(StatusActionsMixin):
    def __init__(self, botao: Any) -> None:
        self.builder = _Builder(botao)


class _Bancada(NamedTuple):
    host: Any
    botao: _Botao
    pactl: _Pactl
    adiados: _Adiados
    #: A memória do sink anterior — o mesmo papel do `gui_preferences.json` no
    #: produto. Ela está aqui porque é onde mora a diferença entre desfazer e
    #: fingir que desfez, e um teste que só olhe o sink padrão não a enxerga.
    memoria: dict[str, str]


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    """Host da mixin + `pactl` dublado + `run_in_thread` que NÃO executa."""
    from hefesto_dualsense4unix.app import audio_saida

    botao = _Botao()
    host = _Host(botao)
    pactl = _Pactl()
    adiados = _Adiados()
    memoria = {"v": ""}
    monkeypatch.setattr(ipc_bridge, "run_in_thread", adiados.run_in_thread)
    host._rota_de_som = audio_saida.RotaDeSaida(
        runner=pactl,
        ler_memoria=lambda: memoria["v"],
        gravar_memoria=lambda s: memoria.__setitem__("v", s),
    )
    host._rota_sink = SINK_CONTROLE
    return _Bancada(host, botao, pactl, adiados, memoria)


def test_a_leitura_da_rota_nao_roda_pactl_na_thread_do_gtk(
    bancada: _Bancada,
) -> None:
    """A regra 5 da entrega, aferida onde ela pode ser quebrada.

    O `pactl` é subprocess e esta interface já congelou por chamada bloqueante
    num tique. Depois de `_refresh_rota_de_som` NADA pode ter rodado ainda:
    o trabalho tem de estar na fila do `run_in_thread`.

    Mordida: trocar o `ipc_bridge.run_in_thread(_ler, ...)` por `_ler()` direto
    e aplicar o resultado na hora — o reflexo natural de quem quer o botão
    certo já no primeiro quadro. A primeira asserção cai na hora.
    """
    host, botao, pactl, adiados = bancada[:4]

    host._refresh_rota_de_som()

    assert pactl.chamadas == [], (
        "nenhum subprocess pode rodar na thread do GTK: o trabalho fica na "
        "fila do run_in_thread"
    )
    assert len(adiados.pendentes) == 1
    assert botao.rotulo == "", "o botão só é repintado DEPOIS da leitura"

    adiados.rodar()
    assert pactl.chamadas, "e aí sim a leitura acontece, na worker"
    assert botao.rotulo == TEXTO_ROTA_PARA_O_CONTROLE
    assert botao.sensivel
    assert "sistema inteiro" in botao.dica.lower()


def test_o_tique_de_reconexao_e_quem_rele_a_rota_sem_timer_novo(
    bancada: _Bancada,
) -> None:
    """A carona é a entrega: o gate de timers desta mixin trava o número deles.

    A rota muda por gesto humano; 0,5 Hz é imperceptível e evita três `pactl`
    por ciclo no tique rápido de 10 Hz (trinta subprocessos por segundo).

    Mordida: tirar a chamada de `_refresh_rota_de_som` do
    `_tick_reconnect_state`. O botão para de se atualizar sozinho e a asserção
    da fila cai. Pôr um `GLib.timeout_add` novo no lugar faz cair o gate de
    timers em `test_status_cards.py`.
    """
    host, _botao, _pactl, adiados = bancada[:4]
    host._reconnect_inflight = True  # o IPC do reconnect pendurado

    assert host._tick_reconnect_state() is True
    assert len(adiados.pendentes) == 1, (
        "a releitura da rota tem de acontecer mesmo com o IPC do reconnect "
        "pendurado: são leituras independentes"
    )


def test_um_ciclo_nao_empilha_em_cima_do_outro(
    bancada: _Bancada,
) -> None:
    """Guarda de reentrância, no molde do `_reconnect_inflight`.

    Mordida: apagar o `if self._rota_inflight: return`. Cada tique passa a
    somar um pedido de subprocess na fila do executor de UMA worker.
    """
    host, _botao, _pactl, adiados = bancada[:4]
    host._refresh_rota_de_som()
    host._refresh_rota_de_som()
    host._refresh_rota_de_som()
    assert len(adiados.pendentes) == 1


def test_o_ciclo_completo_ida_e_volta_pela_interface(
    bancada: _Bancada,
) -> None:
    """Regra 1: é reversível, e o desfazer é parte da entrega.

    O ciclo inteiro visto da tela: o botão oferece "Ouvir no controle", o
    clique muda a saída padrão do sistema, o botão passa a oferecer "Voltar ao
    anterior", e o segundo clique devolve a saída DELA.

    Mordida: fazer o clique mandar sempre `mandar_para_o_controle`, ignorando
    o ramo da volta. **O sink padrão acaba no mesmo lugar** — é a armadilha
    deste teste, e por isso ele olha também a MEMÓRIA: `mandar_para_o_controle`
    guarda "de onde veio" antes de trocar, então a volta deixaria gravado o
    sink do CONTROLE como "anterior". No próximo ciclo o botão ofereceria
    voltar para o controle estando no HDMI, e a dona perderia o caminho de
    volta de verdade. A asserção da memória vazia é a que morde.
    """
    host, botao, pactl, adiados = bancada[:4]
    memoria = bancada.memoria

    host._refresh_rota_de_som()
    adiados.rodar()
    assert botao.rotulo == TEXTO_ROTA_PARA_O_CONTROLE

    botao.handlers = []
    host._on_rota_de_som_clicada()
    adiados.rodar()
    assert pactl.padrao == SINK_CONTROLE, "o som foi para o controle"
    assert memoria["v"] == SINK_HDMI, "e de onde ele veio ficou guardado"
    assert botao.rotulo == TEXTO_ROTA_VOLTAR, "e o botão já oferece a volta"

    host._on_rota_de_som_clicada()
    adiados.rodar()
    assert pactl.padrao == SINK_HDMI, "a saída dela voltou para onde estava"
    assert memoria["v"] == "", (
        "a volta ESQUECE a memória: memória que sobrevive ao retorno faz o "
        "botão oferecer uma volta para onde o som já está"
    )
    assert botao.rotulo == TEXTO_ROTA_PARA_O_CONTROLE


def test_clique_sem_alvo_nao_escreve_nada(
    bancada: _Bancada,
) -> None:
    """Segunda tranca do botão insensível — para o clique por teclado ou teste.

    Mordida: apagar a guarda de três termos que abre
    `_on_rota_de_som_clicada` — a que exige ação presente, sensível e com alvo.
    Sem ela o clique passa a mandar "" ao `pactl`, que é justamente o caminho
    do sink padrão.
    """
    host, _botao, pactl, adiados = bancada[:4]
    host._rota_acao = None
    host._on_rota_de_som_clicada()
    adiados.rodar()
    assert pactl.chamadas == []

    # SOM-ACORDADO-01: a leitura da rota passou a viajar em PAR com o
    # "a regra do WirePlumber está instalada?" — a mesma worker, o mesmo ciclo.
    host._on_rota_lida(
        (
            EstadoDaRota(
                sink_padrao=SINK_CONTROLE, sink_do_controle="", no_controle=False
            ),
            True,
        )
    )
    pactl.chamadas.clear()
    host._on_rota_de_som_clicada()
    adiados.rodar()
    assert pactl.chamadas == [], "sem alvo não há escrita nenhuma"


def test_com_dois_controles_o_alvo_da_rota_fica_vazio() -> None:
    """Regra 6: `escolher_sink` recusa de propósito, e a mixin obedece.

    O nome do sink não carrega identidade — o `-00` é ordem de conexão, não
    número de série. Dois nomes distintos aqui seria a janela tendo de
    escolher por ela.

    Mordida: trocar o ``len(nomes) == 1`` por "pega o primeiro". Com dois
    controles publicando sinks diferentes, o botão passa a mandar o som para um
    controle escolhido pela ordem de iteração de um `set`.
    """
    host = _Host(_Botao())

    class _Monitor:
        def __init__(self, mapa: dict[str, str]) -> None:
            self.mapa = mapa

        def sink_de(self, uniq: str) -> str:
            return self.mapa.get(uniq, "")

    um = _Monitor({"aa": SINK_CONTROLE})
    assert host._sink_do_controle_para_a_rota(um, ("aa",)) == SINK_CONTROLE

    dois = _Monitor({"aa": SINK_CONTROLE, "bb": "alsa_output.outro_controle"})
    assert host._sink_do_controle_para_a_rota(dois, ("aa", "bb")) == ""

    nenhum = _Monitor({})
    assert host._sink_do_controle_para_a_rota(nenhum, ("aa", "bb")) == ""
    assert host._sink_do_controle_para_a_rota(None, ("aa",)) == ""


def test_sem_o_botao_no_builder_a_aba_nao_quebra() -> None:
    """Builder sem o botão, ou dublado por um teste de outra área.

    A aba tem de montar do mesmo jeito — a rota some, o resto fica. É a mesma
    linha do tema sem CSS e do monitor de mic indisponível.

    Mordida: tirar a guarda ``if botao is None`` de `_refresh_rota_de_som`.
    """
    host = _Host(None)
    host._refresh_rota_de_som()  # não pode levantar
    assert host._rota_inflight is False
