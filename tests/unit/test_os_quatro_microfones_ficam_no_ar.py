"""OS-QUATRO-NO-AR-01 — os quatro microfones ficam no ar ao mesmo tempo.

A pergunta de 13/09/2026 era *"com dois controles ligados, quer os dois
microfones funcionando ao mesmo tempo, cada um no seu canal?"*, e a resposta
dela está citada no topo da sprint: sim, para os quatro. O desenho do §1 é de
quem coordena, por delegação:

    no ar              por controle, os quatro juntos
    fonte padrão       uma só — o último que ela ligou e continua no ar

**O QUE ESTA RÉGUA MEDE é o ato de verdade** (`hotkey.ligar_o_microfone`, a
função única do 🎙 da tela e do botão do plástico), com o `EleitorDeMicrofone`
DO PRODUTO, o registro da palavra DO PRODUTO e o `BtMicSubsystem` DO PRODUTO.
Dublê só nas bordas: o `pactl` (`eleicao_de_microfone._rodar`), o backend do
controle e as pontes de rádio.

**NENHUM TESTE DAQUI FALA COM O MUNDO.** A fixture `_ninguem_roda_processo`
troca `subprocess.run` e `subprocess.Popen` por uma recusa: um `pactl` que
escapasse do dublê reprova o teste em vez de chegar ao servidor de som dela.

Os endereços são da faixa sintética da casa, com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import pathlib
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey, recado_do_microfone
from hefesto_dualsense4unix.integrations import audio_control
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

P1 = "aa:bb:cc:00:00:a1"
P2 = "aa:bb:cc:00:00:b7"
P3 = "aa:bb:cc:00:00:c3"
P4 = "aa:bb:cc:00:00:d9"

#: A mesa dela: dois no rádio, dois no cabo.
MESA_DELA: tuple[tuple[str, str], ...] = (
    (P1, "bluetooth"),
    (P2, "usb"),
    (P3, "usb"),
    (P4, "bluetooth"),
)

#: O microfone da máquina — para onde o padrão volta quando ninguém está no ar.
PLACA = "alsa_input.pci-0000_00_1f.3.analog-stereo"
TERCEIRO = "alsa_input.um_terceiro_que_o_wireplumber_escolheu"


def _n(uniq: str) -> str:
    return norm_mac(uniq) or uniq


def _canal(uniq: str) -> str:
    """O nó por controle, com a mesma grafia que `canal_do_microfone` publica."""
    return f"hefesto_mic_{_n(uniq)[-6:]}"


# ---------------------------------------------------------------------------
# As bordas dubladas
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ninguem_roda_processo(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _recusa(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(f"um teste desta régua tentou rodar processo: {args!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()
    yield
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()


class _PipeWire:
    """O `pactl` que a eleição vê. O eleitor por cima dele é o do produto.

    Ele SABE RECUSAR nos três jeitos que importam aqui: o WirePlumber
    reelegendo um terceiro por cima (`reeleger_para`), o canal de um controle
    sumindo (`publicados`) e o servidor que não responde (`responde`).
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.publicados: dict[str, str] = {_n(u): _canal(u) for u, _ in MESA_DELA}
        self.ativo: str | None = PLACA
        self.escritas: list[str] = []
        self.reeleger_para: str | None = None
        self.responde = True
        monkeypatch.setattr(ele, "_rodar", self._rodar)
        monkeypatch.setattr(ele, "fonte_se_sustenta", lambda _nome: True)
        monkeypatch.setattr(ele, "melhor_fonte_elegivel", lambda: PLACA)
        monkeypatch.setattr(ele, "casamento_usb_agora", lambda _uniqs: None)
        monkeypatch.setattr(ele, "SETTLE_PASSOS", 2)
        monkeypatch.setattr(ele, "SETTLE_PASSO_S", 0.0)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSOS", 1)
        monkeypatch.setattr(ele, "ESPERA_DO_CANAL_PASSO_S", 0.0)
        # O que o laço do canal lê a cada dois segundos, pelos mesmos donos.
        monkeypatch.setattr(
            audio_control, "fonte_de_captura_do_uniq", self._fonte_do_uniq
        )
        monkeypatch.setattr(audio_control, "volume_da_captura", lambda **_k: 100)
        monkeypatch.setattr(hotkey, "_fonte_esta_muda", lambda _fonte: False)

    def _listagem(self) -> str:
        nomes = [PLACA, *self.publicados.values()]
        return "\n".join(
            f"{i}\t{nome}\tmodule-pipe-source.c\ts16le 1ch 48000Hz\tSUSPENDED"
            for i, nome in enumerate(nomes, start=40)
        )

    def _rodar(self, argv: list[str]) -> tuple[int, str]:
        if not self.responde:
            return (127, "")
        if argv[:2] == ["pactl", "get-default-source"]:
            return (0, self.ativo or "")
        if argv[:2] == ["pactl", "set-default-source"]:
            self.escritas.append(argv[2])
            self.ativo = self.reeleger_para or argv[2]
            return (0, "")
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            return (0, self._listagem())
        raise AssertionError(f"pactl que esta régua não conhece: {argv}")

    def _fonte_do_uniq(self, uniq: str, **_k: Any) -> str | None:
        if not self.responde:
            return None
        return self.publicados.get(_n(uniq))


class _Backend:
    """O backend dos quatro. As chaves são normalizadas, como no produto."""

    def __init__(self) -> None:
        self.mudo: dict[str, bool] = {_n(u): True for u, _ in MESA_DELA}
        self.leds: dict[str, bool] = {}
        self.escritas_de_luz: list[tuple[str, bool]] = []

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [
            {"uniq": u, "connected": True, "transport": t} for u, t in MESA_DELA
        ]

    def audio_status_for(self, uniq: str | None = None) -> dict[str, Any]:
        return {"mic_mudo": self.mudo.get(_n(uniq or ""))}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        if isinstance(muted, bool):
            self.mudo[_n(uniq or "")] = muted
        return True

    def set_mic_led(self, aceso: Any, *, uniq: str | None = None) -> None:
        self.leds[_n(uniq or "")] = bool(aceso)
        self.escritas_de_luz.append((_n(uniq or ""), bool(aceso)))


class _Daemon:
    def __init__(self, backend: _Backend) -> None:
        self.controller = backend
        self._tasks: list[Any] = []
        self.config = SimpleNamespace(mic_button_toggles_system=True)
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        """Sem `**kwargs` — a assinatura do daemon real."""
        return fn(*args)


class _PonteDeMentira:
    def __init__(self, uniq: str, caminho: str) -> None:
        self.no = SimpleNamespace(uniq=uniq, caminho=caminho)
        self.ditos: list[bool | None] = []

    def dizer_o_pedido_dela(self, ligado: bool | None) -> None:
        self.ditos.append(ligado)


class _GerenciadorDeMentira:
    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, nos: list[Any]) -> None:
        vivos = {no.caminho for no in nos}
        for caminho in [c for c in self.pontes if c not in vivos]:
            del self.pontes[caminho]
        for no in nos:
            self.pontes.setdefault(no.caminho, _PonteDeMentira(no.uniq, no.caminho))

    def dormir(self, _segundos: float) -> bool:
        return True

    def parar(self) -> None:
        self.pontes.clear()


@pytest.fixture()
def mesa(monkeypatch: pytest.MonkeyPatch) -> Any:
    pipewire = _PipeWire(monkeypatch)
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._gerenciador = _GerenciadorDeMentira()
    backend = _Backend()
    sub._backend = backend
    anteriores = ele.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar
    )
    pedidor_anterior = ele.registrar_pedidor_de_canal(sub.pedir_canal)
    try:
        yield SimpleNamespace(
            pipewire=pipewire,
            registro=registro,
            sub=sub,
            backend=backend,
            daemon=_Daemon(backend),
        )
    finally:
        ele.registrar_dizedor_do_no_ar(*anteriores)
        ele.registrar_pedidor_de_canal(pedidor_anterior)


def _apertar(m: Any, uniq: str, *, ligado: bool) -> Any:
    """O botão do plástico: o kernel já alternou o bit quando a borda chega."""
    m.backend.mudo[_n(uniq)] = not ligado
    return asyncio.run(hotkey.ligar_o_microfone(m.daemon, uniq, ligado=ligado))


def _voltas_do_canal(m: Any, voltas: int) -> None:
    """Roda o `canal_do_microfone_loop` DE PRODUÇÃO por `voltas` varreduras.

    A parada entra pelo `_uniqs_conectados` da volta seguinte, e devolvendo a
    mesa inteira: o laço sai no primeiro `_is_stopping()` do `for`, sem limpar
    as leituras que a última volta deixou.
    """
    reais = hotkey._uniqs_conectados
    contagem = {"n": 0}

    def _contando(daemon: Any) -> list[str]:
        contagem["n"] += 1
        if contagem["n"] > voltas:
            m.daemon._parando = True
        return reais(daemon)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hotkey, "_uniqs_conectados", _contando)
        mp.setattr(hotkey, "CANAL_TTL_S", 0.0)
        asyncio.run(hotkey.canal_do_microfone_loop(m.daemon))
    m.daemon._parando = False


def _eleito(m: Any) -> str | None:
    return m.daemon._eleitor_de_microfone.eleito


# ---------------------------------------------------------------------------
# 1. Ligar o segundo não desliga o primeiro
# ---------------------------------------------------------------------------


def test_liga_um_liga_outro_e_os_dois_ficam_no_ar(mesa: Any) -> None:
    """Liga A, liga B: A e B no ar, as duas luzes acesas, o padrão é B.

    MORDIDA: em `hotkey._apagar_a_luz_de_quem_perdeu_o_canal`, tire a guarda
    `_no_ar_da_sessao(daemon).esta(dono_antes)` — que é devolver o
    `esquecer_a_palavra` na perda do padrão — e A sai do ar com a luz apagada.
    """
    assert _apertar(mesa, P1, ligado=True).feito
    assert _apertar(mesa, P4, ligado=True).feito

    assert mesa.registro.no_ar() == {_n(P1): True, _n(P4): True}, (
        "ligar o segundo microfone tirou o primeiro do ar: "
        f"{mesa.registro.no_ar()}"
    )
    assert mesa.backend.leds == {_n(P1): True, _n(P4): True}, (
        f"a luz de quem continua no ar apagou: {mesa.backend.leds}"
    )
    assert _eleito(mesa) == P4
    assert mesa.pipewire.ativo == _canal(P4), "o padrão é o último que ela ligou"


def test_os_quatro_da_mesa_dela_no_ar_e_cada_ponte_de_radio_recebe_o_sim(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Os quatro no ar, e o `_loop` do supervisor entrega o SIM às duas pontes.

    MORDIDA: a mesma da régua de cima. Com o esquecimento de volta, só o
    último fica com a palavra — e só uma ponte de rádio recebe `True`.
    """
    for uniq, _ in MESA_DELA:
        assert _apertar(mesa, uniq, ligado=True).feito, uniq

    assert mesa.registro.no_ar() == {_n(u): True for u, _ in MESA_DELA}
    assert mesa.backend.leds == {_n(u): True for u, _ in MESA_DELA}
    assert _eleito(mesa) == P4

    radio = [(u, f"/dev/hidraw{i}") for i, (u, t) in enumerate(MESA_DELA) if t == "bluetooth"]
    monkeypatch.setattr(
        bt, "nos_dualsense_bluetooth",
        lambda: [SimpleNamespace(uniq=u, caminho=c) for u, c in radio],
    )
    # O canal do cabo carrega módulo no servidor de som: fica fora desta régua.
    monkeypatch.setattr(mesa.sub, "_reconciliar_o_cabo", lambda _nos: None)
    mesa.sub._registro.novidade.set()
    mesa.sub._loop()

    pontes = mesa.sub._gerenciador.pontes
    assert sorted(p.no.uniq for p in pontes.values()) == sorted(u for u, _ in radio)
    for ponte in pontes.values():
        assert ponte.ditos[-1:] == [True], (
            f"a ponte de {ponte.no.uniq} não recebeu o pedido dela: {ponte.ditos}"
        )
    assert mesa.registro.no_ar() == {_n(u): True for u, _ in MESA_DELA}, (
        "a varredura apagou a palavra de quem está no cabo"
    )


# ---------------------------------------------------------------------------
# 2. Desligar
# ---------------------------------------------------------------------------


def test_desligar_o_padrao_passa_o_padrao_ao_ultimo_que_continua_no_ar(mesa: Any) -> None:
    """Liga A, B e C; desliga C (o padrão): o padrão é B, e A e B seguem no ar.

    MORDIDA: em `hotkey._passar_o_padrao_ou_devolver`, pule os candidatos e
    vá direto ao `devolver_o_microfone` — o padrão cai na placa da máquina com
    dois microfones no ar.
    """
    for uniq in (P1, P2, P3):
        assert _apertar(mesa, uniq, ligado=True).feito
    ato = _apertar(mesa, P3, ligado=False)

    assert ato.feito, ato.motivo
    assert _eleito(mesa) == P2
    assert mesa.pipewire.ativo == _canal(P2), (
        f"o padrão tinha de passar ao último ligado que continua no ar: "
        f"{mesa.pipewire.ativo}"
    )
    assert mesa.registro.no_ar() == {_n(P1): True, _n(P2): True, _n(P3): False}
    assert mesa.backend.leds == {_n(P1): True, _n(P2): True, _n(P3): False}


def test_desligar_quem_nao_e_o_padrao_tira_so_ele_do_ar(mesa: Any) -> None:
    """Liga A e B; desliga A: A sai, B continua no ar e continua o padrão.

    Não é recusa: A estava no ar, e o botão dele o tira do ar. O padrão do
    sistema não é tocado — nenhum `set-default-source` sai deste toque.

    MORDIDA: devolva o ramo `fora_do_padrao` de `_eleger_ou_devolver` à recusa
    de quem não elegeu, e o ato de A volta com `canal_no_sistema.feita=False`.
    """
    _apertar(mesa, P1, ligado=True)
    _apertar(mesa, P4, ligado=True)
    escritas = list(mesa.pipewire.escritas)

    ato = _apertar(mesa, P1, ligado=False)

    assert ato.feito, ato.motivo
    assert mesa.pipewire.escritas == escritas, "tirar A do ar mexeu no padrão"
    assert _eleito(mesa) == P4
    assert mesa.registro.no_ar() == {_n(P1): False, _n(P4): True}
    assert mesa.backend.leds == {_n(P1): False, _n(P4): True}
    recado = recado_do_microfone.publicar(mesa.daemon)["recados"][P1]
    assert (recado["gesto"], recado["ok"], recado["motivo"]) == ("devolver", True, "")


@pytest.mark.parametrize(
    "ordem", [(P4, P1), (P1, P4)], ids=["o-padrao-primeiro", "o-padrao-por-ultimo"]
)
def test_desligar_todos_o_padrao_volta_para_a_maquina(
    mesa: Any, ordem: tuple[str, str]
) -> None:
    """Desliga todos: o padrão volta ao microfone da máquina, como hoje.

    MORDIDA: a mesma da passagem do padrão. Com ela arrancada, desligar P4
    primeiro já devolve à placa e deixa P1 no ar SEM ser o padrão — e o toque
    seguinte de P1 vira recusa.
    """
    _apertar(mesa, P1, ligado=True)
    _apertar(mesa, P4, ligado=True)
    primeiro, segundo = ordem

    assert _apertar(mesa, primeiro, ligado=False).feito
    restante = P1 if primeiro == P4 else P4
    assert _eleito(mesa) == restante
    assert mesa.pipewire.ativo == _canal(restante)

    assert _apertar(mesa, segundo, ligado=False).feito
    assert _eleito(mesa) is None
    assert mesa.pipewire.ativo == PLACA
    assert mesa.registro.no_ar() == {_n(P1): False, _n(P4): False}
    assert mesa.backend.leds == {_n(P1): False, _n(P4): False}


# ---------------------------------------------------------------------------
# 3. Perder o padrão não é sair do ar
# ---------------------------------------------------------------------------


def test_perder_o_padrao_para_um_terceiro_nao_tira_do_ar(mesa: Any) -> None:
    """A no ar; B liga, a escrita passa e o WirePlumber reelege um TERCEIRO.

    Ninguém da mesa ficou com o padrão (a posse cai, pela régua do ativo
    relido), mas o canal de A continua no ar — a luz dele não apaga e a
    palavra dele fica. O ato de B foi recusado: a palavra dele é desfeita e
    ele não entra no ar.

    MORDIDA: a guarda de `_apagar_a_luz_de_quem_perdeu_o_canal`.
    """
    _apertar(mesa, P1, ligado=True)
    mesa.pipewire.reeleger_para = TERCEIRO

    ato = _apertar(mesa, P4, ligado=True)

    assert ato.feito is False
    assert _eleito(mesa) is None
    assert mesa.registro.no_ar() == {_n(P1): True}, mesa.registro.no_ar()
    assert mesa.backend.leds == {_n(P1): True, _n(P4): False}
    assert hotkey._no_ar_da_sessao(mesa.daemon).todos() == [P1]


def test_o_mesmo_controle_em_duas_grafias_e_um_controle_so(mesa: Any) -> None:
    """A tela manda `aa:bb:…`; o plástico, `aabb…`. É o mesmo controle.

    MORDIDA: compare `eleitor.eleito != uniq` cru em `_eleger_ou_devolver`, e o
    eleito que desliga pelo plástico recebe a recusa de quem não elegeu.
    """
    _apertar(mesa, P1, ligado=True)
    ato = _apertar(mesa, _n(P1), ligado=False)

    assert ato.feito, ato.motivo
    assert _eleito(mesa) is None
    assert mesa.pipewire.ativo == PLACA
    assert hotkey._no_ar_da_sessao(mesa.daemon).todos() == []


# ---------------------------------------------------------------------------
# 4. O canal de um cai de verdade
# ---------------------------------------------------------------------------


def test_a_ponte_de_um_cai_a_luz_dele_apaga_e_o_outro_nao_e_tocado(mesa: Any) -> None:
    """A e B no ar; o canal de A some. A luz de A apaga, e B não é tocado.

    UMA leitura sem canal não basta — é a janela da reconexão de rádio, em que
    a ponte velha cai e a nova sobe. DUAS seguidas, sim.

    MORDIDA: tire `await _conferir_quem_saiu_do_ar(daemon, uniqs)` do
    `canal_do_microfone_loop`, e A fica no ar para sempre sem canal.
    """
    _apertar(mesa, P1, ligado=True)
    _apertar(mesa, P4, ligado=True)
    luzes_antes = len(mesa.backend.escritas_de_luz)
    del mesa.pipewire.publicados[_n(P1)]

    _voltas_do_canal(mesa, 1)
    assert hotkey._no_ar_da_sessao(mesa.daemon).todos() == [P1, P4], (
        "uma leitura sem canal tirou A do ar — a reconexão de rádio derrubaria "
        "o microfone dela"
    )

    _voltas_do_canal(mesa, 1)
    assert hotkey._no_ar_da_sessao(mesa.daemon).todos() == [P4]
    assert mesa.backend.leds[_n(P1)] is False, "a luz de quem saiu do ar não apagou"
    assert _n(P1) not in mesa.registro.no_ar(), "o microfone saiu do ar e a palavra ficou"
    depois = mesa.backend.escritas_de_luz[luzes_antes:]
    assert [e for e in depois if e[0] == _n(P4)] == [], f"a luz de B foi tocada: {depois}"
    assert mesa.registro.no_ar() == {_n(P4): True}
    assert _eleito(mesa) == P4


def test_nao_saber_se_o_canal_existe_nunca_tira_do_ar(mesa: Any) -> None:
    """O servidor de som parou de responder: ninguém sai do ar por isso.

    Foi o que aconteceu por 47 minutos em 13/09/2026 (MIC-O-CANAL-DO-OUTRO-01).
    *"Não sei"* nunca vira *"saiu"*.

    MORDIDA: faça `eleicao_de_microfone.canal_publicado` devolver `False` com
    `rc != 0`, e os dois saem do ar em duas voltas.
    """
    _apertar(mesa, P1, ligado=True)
    _apertar(mesa, P4, ligado=True)
    mesa.pipewire.responde = False

    _voltas_do_canal(mesa, 3)

    assert hotkey._no_ar_da_sessao(mesa.daemon).todos() == [P1, P4]
    assert mesa.registro.no_ar() == {_n(P1): True, _n(P4): True}
    assert mesa.backend.leds == {_n(P1): True, _n(P4): True}


# ---------------------------------------------------------------------------
# 5. A aba Controles mostra cada microfone no ar
# ---------------------------------------------------------------------------


def test_a_aba_controles_mostra_cada_microfone_no_ar(mesa: Any) -> None:
    """Dois no ar, um deles padrão: o selo de OS DOIS diz ATIVO.

    O caminho é o do produto inteiro: o laço do canal lê, o `_merge_audio` do
    IPC publica o bloco `audio`, e `a02_controles.selo_composto` pinta.

    ANTES DESTA SPRINT o selo de A dizia MUDO — `canal_ativo` só era
    verdadeiro para o padrão do sistema, e A estava no ar no canal dele.

    MORDIDA: tire o `lido["canal_ativo"] = True` de `hotkey._ler_o_canal_deste`.
    """
    raiz = pathlib.Path(__file__).resolve().parents[2]
    interface = raiz / "src" / "hefesto_dualsense4unix" / "interface"
    if str(interface) not in sys.path:
        sys.path.insert(0, str(interface))
    import mesa_viva
    from pacotes import a02_controles as a02

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):  # type: ignore[misc]
        def __init__(self, d: _Daemon) -> None:
            self.controller = d.controller
            self.daemon = d

    _apertar(mesa, P1, ligado=True)
    _apertar(mesa, P4, ligado=True)
    _voltas_do_canal(mesa, 1)

    ativo = mesa_viva.selo_do_mic(False, True)
    mudo = mesa_viva.selo_do_mic(True, True)
    handlers = _Handlers(mesa.daemon)
    selos = {}
    for uniq in (P1, P2, P4):
        entrada: dict[str, Any] = {}
        handlers._merge_audio(entrada, uniq)
        selos[uniq] = a02.selo_composto(entrada["audio"])

    assert selos == {P1: ativo, P2: mudo, P4: ativo}, selos
