"""O GESTO DELA PÕE O MICROFONE NO AR — a costura, não a ponte."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as eleicao

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"

#: A MESA DELA — quatro DualSense, dois no cabo e dois no rádio, na disposição
MESA_DELA: tuple[tuple[str, str], ...] = (
    (P1, "bluetooth"),
    (P2, "usb"),
    (P3, "usb"),
    (P4, "bluetooth"),
)


class _PonteDeMentira:
    """O mínimo que `_aplicar_a_palavra_dela` toca — e a porta que ela chama."""

    def __init__(self, uniq: str, caminho: str | None = None) -> None:
        self.no = _no(uniq, caminho)
        self.ditos: list[bool | None] = []

    def dizer_o_pedido_dela(self, ligado: bool | None) -> None:
        self.ditos.append(ligado)


class _GerenciadorDeMentira:
    """O gerenciador, com o que o `_loop` do subsystem realmente chama."""

    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}
        self.voltas = 0

    def erguer(self, uniq: str, caminho: str | None = None) -> _PonteDeMentira:
        ponte = _PonteDeMentira(uniq, caminho)
        self.pontes[ponte.no.caminho] = ponte
        return ponte

    def reconciliar(self, nos: list[Any]) -> None:
        self.voltas += 1
        vivos = {no.caminho for no in nos}
        for caminho in [c for c in self.pontes if c not in vivos]:
            del self.pontes[caminho]
        for no in nos:
            if no.caminho not in self.pontes:
                self.erguer(no.uniq, no.caminho)

    def dormir(self, segundos: float) -> bool:
        """True = pararam. Uma volta por chamada de `_loop`, e o teste não espera."""
        return True

    def parar(self) -> None:
        self.pontes.clear()


def _no(uniq: str, caminho: str | None = None) -> Any:
    return type(
        "No", (), {"uniq": uniq, "caminho": caminho or f"/dev/hidraw-{uniq[-2:]}"}
    )()


def _uma_volta_do_laco(subsystem, monkeypatch, nos: list[Any]) -> None:  # type: ignore[no-untyped-def]
    """Roda o `_loop` DE PRODUÇÃO exatamente uma vez, com os nós que o teste dá.

    Dirigir o laço de verdade é o que separa esta régua de uma que confere o
    TEXTO do código: se alguém tirar o `_aplicar_a_palavra_dela()` de dentro do
    laço, ninguém entrega a palavra à ponte nova e o teste reprova pelo EFEITO.

    A `novidade` vai marcada para que o `_dormir` não espere os `RECONCILIA_S`;
    quem manda parar é o `dormir()` do gerenciador, que devolve True.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as _bt

    monkeypatch.setattr(_bt, "nos_dualsense_bluetooth", lambda: list(nos))
    subsystem._registro.novidade.set()
    subsystem._loop()


@pytest.fixture()
def registro() -> bt_mic.RegistroDePedidosDeCanal:
    """Um registro PRÓPRIO — nunca o singleton do processo."""
    return bt_mic.RegistroDePedidosDeCanal()


@pytest.fixture()
def subsystem(registro):  # type: ignore[no-untyped-def]
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._gerenciador = _GerenciadorDeMentira()
    return sub


class _BackendDeMentira:
    def __init__(self) -> None:
        self.mic_mudo = True
        self.leds: list[tuple[Any, str | None]] = []

    def audio_status_for(self, uniq: str | None = None) -> dict[str, Any]:
        return {"fone_plugado": False, "mic_externo": False, "mic_mudo": self.mic_mudo}

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        if isinstance(muted, bool):
            self.mic_mudo = muted
        return True

    def set_mic_led(self, aceso: Any, uniq: str | None = None) -> bool:
        self.leds.append((aceso, uniq))
        return True

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": P1, "connected": True, "transport": "bluetooth"}]


RECUSA_SEM_CANAL = (
    "o PipeWire não publica canal de captura nenhum para o "
    "controle — no rádio isso precisa da ponte de microfone"
)


class _EleitorDeMentira:
    """O eleitor dublado — e ele SABE RECUSAR, que é o que o real faz."""

    def __init__(self, *, recusa: str | None = None) -> None:
        self.eleito: str | None = None
        self.recusa = recusa
        self.eleicoes: list[str] = []

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> Any:
        del conectados
        self.eleicoes.append(uniq)
        if self.recusa is not None:
            return eleicao.ResultadoDaEleicao(ok=False, motivo=self.recusa)
        self.eleito = uniq
        return eleicao.ResultadoDaEleicao(ok=True, alvo=uniq, ativo=f"fonte-de-{uniq}")

    def devolver_o_microfone(self) -> Any:
        if self.recusa is not None:
            return eleicao.ResultadoDaEleicao(ok=False, motivo=self.recusa)
        self.eleito = None
        return eleicao.ResultadoDaEleicao(ok=True, ativo="fonte-de-antes")

    def passar_o_padrao(
        self, no_ar: list[str], conectados: list[str], calou: str | None = None
    ) -> Any:
        """A pergunta de `EleitorDeMicrofone.passar_o_padrao`: quem está no ar,"""
        for candidato in no_ar:
            passado = self.eleger_o_controle(candidato, conectados)
            if passado.ok:
                return passado
        return self.devolver_o_microfone()


class _DaemonDeMentira:
    def __init__(self, eleitor: Any = None) -> None:
        self.controller = _BackendDeMentira()
        self._eleitor_de_microfone = eleitor or _EleitorDeMentira()
        self._tasks: list[Any] = []
        self.config = type("Cfg", (), {"mic_button_toggles_system": True})()
        self.store = type("Store", (), {"native_mode_active": False})()

    def is_native_mode(self) -> bool:
        return False

    def _is_stopping(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        """Sem `**kwargs` — a assinatura do daemon REAL. Ver a cicatriz de 04/09."""
        return fn(*args)


@pytest.fixture(autouse=True)
def _sem_eco() -> Any:
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()
    yield
    hotkey._ECO_DO_ATO.clear()
    hotkey._CANAL_POR_UNIQ.clear()


@pytest.fixture()
def gancho(subsystem):  # type: ignore[no-untyped-def]
    """Instala o subsystem como quem atende a palavra dela, e restaura depois."""
    anteriores = eleicao.registrar_dizedor_do_no_ar(
        subsystem.no_ar, subsystem.esquecer_a_palavra, subsystem.palavra_no_ar
    )
    yield subsystem
    eleicao.registrar_dizedor_do_no_ar(*anteriores)


def test_o_ato_do_microfone_diz_a_palavra_dela(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """MORDIDA 1: `ligar_o_microfone` põe o pedido dela no registro."""
    d = _DaemonDeMentira()
    ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert ato.canal_no_sistema.feita
    assert registro.no_ar() == {"aabbcc000001": True}, (
        "o ato ligou o canal e NÃO disse que o microfone ia ao ar — pelo rádio "
        "o 0x32 continua seguindo só o ouvinte, e a source que a eleição "
        f"acabou de escolher está SUSPENDED: {registro.no_ar()}"
    )


def test_o_ato_de_calar_tambem_e_dito(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """O mudo dela é palavra, não ausência de palavra."""
    d = _DaemonDeMentira()
    d._eleitor_de_microfone.eleito = P1
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=False))
    assert registro.no_ar() == {"aabbcc000001": False}, (
        f"o ato de calar não chegou ao registro: {registro.no_ar()}"
    )


def test_sem_ninguem_atendendo_o_ato_nao_explode(registro) -> None:  # type: ignore[no-untyped-def]
    """Subsystem no chão: a palavra não é atendida e o ato segue igual."""
    anteriores = eleicao.registrar_dizedor_do_no_ar(None, None, None)
    try:
        d = _DaemonDeMentira()
        ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
        assert ato.canal_no_sistema.feita
        assert eleicao.dizer_no_ar(P1, True) is False
        assert eleicao.esquecer_a_palavra(P1) is False
        assert eleicao.palavra_no_ar(P1) is None
        recusado = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
        ato2 = asyncio.run(hotkey.ligar_o_microfone(recusado, P1, ligado=True))
        assert ato2.canal_no_sistema.feita is False
    finally:
        eleicao.registrar_dizedor_do_no_ar(*anteriores)


def test_a_ponte_que_nasce_depois_recebe_a_palavra_dela(subsystem, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Reconexão de rádio é ROTINA: a ponte nova tem de saber o que ela pediu.

    Se o latch morasse na `PonteMicBluetooth`, a primeira reconexão o apagaria
    e o microfone cairia em silêncio — o mesmo sintoma que esta cura fecha,
    voltando por outra porta.

    **O HOTPLUG AQUI É O `hidrawN` RENUMERANDO**, e não o controle saindo da
    mesa: o gerenciador casa as pontes por CAMINHO, então uma reconexão que
    devolva outro `/dev/hidrawN` para o mesmo endereço derruba a ponte e ergue
    outra — com o controle presente o tempo todo, e a palavra dela intacta no
    registro. (O controle que SAI da mesa é outro caso, e ali a palavra morre
    de propósito: ver `test_o_controle_que_sai_da_mesa_perde_a_palavra`.)

    **O LAÇO DE PRODUÇÃO RODA AQUI**, não uma chamada à mão de
    `_aplicar_a_palavra_dela`: uma régua que chama a cura por fora dá verde
    mesmo com a cura desligada do caminho. ARRANQUE A REAPLICAÇÃO (tire o
    `self._aplicar_a_palavra_dela()` de dentro do `_loop`, depois do
    `reconciliar`) e esta régua REPROVA.
    """
    assert subsystem.no_ar(P1, True) is True
    _uma_volta_do_laco(subsystem, monkeypatch, [_no(P1, "/dev/hidraw5")])
    velha = subsystem._gerenciador.pontes["/dev/hidraw5"]
    assert velha.ditos[-1:] == [True]
    _uma_volta_do_laco(subsystem, monkeypatch, [_no(P1, "/dev/hidraw9")])
    assert "/dev/hidraw5" not in subsystem._gerenciador.pontes
    nova = subsystem._gerenciador.pontes["/dev/hidraw9"]
    assert nova.ditos[-1:] == [True], (
        "a ponte que nasceu depois do hotplug não recebeu o pedido dela; no "
        f"rádio isso é o microfone caindo sozinho na reconexão: {nova.ditos}"
    )


def test_a_palavra_vai_para_a_ponte_certa_e_so_para_ela(subsystem) -> None:  # type: ignore[no-untyped-def]
    """Quatro na mesa: ligar o microfone de um não liga o dos outros três."""
    p1 = subsystem._gerenciador.erguer(P1)
    p2 = subsystem._gerenciador.erguer(P2)
    subsystem.no_ar(P1, True)
    assert p1.ditos[-1:] == [True], f"o dono não recebeu a palavra: {p1.ditos}"
    assert p2.ditos[-1:] == [None], (
        f"ligar o microfone de um mexeu no do vizinho: {p2.ditos}"
    )


def test_o_controle_que_sai_da_mesa_perde_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Quarta porta: quem sai do rádio perde a palavra junto com o pedido."""
    subsystem.no_ar(P1, True)
    subsystem.no_ar(P2, True)
    registro.esquecer_ausentes(frozenset({"aabbcc000002"}))
    assert registro.no_ar() == {"aabbcc000002": True}, (
        "a palavra de quem saiu da mesa sobreviveu — a reconexão dele "
        f"ressuscitaria o microfone: {registro.no_ar()}"
    )


def test_desmarcar_o_modo_apaga_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Quinta porta: `soltar` (o "Aplicar" dela) leva a palavra junto."""
    subsystem.no_ar(P1, True)
    registro.soltar(P1)
    assert registro.no_ar() == {}, (
        f"desmarcar o modo derrubou a ponte e guardou o pedido: {registro.no_ar()}"
    )


def test_a_sessao_que_acaba_leva_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """`limpar()` é o `stop()` do subsystem: os pedidos morrem com a sessão."""
    subsystem.no_ar(P1, True)
    registro.limpar()
    assert registro.no_ar() == {}, (
        f"a palavra dela sobreviveu ao fim da sessão: {registro.no_ar()}"
    )


def test_perder_a_eleicao_esquece_a_palavra_e_nao_a_nega(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Perder o canal por gesto ALHEIO devolve a decisão ao ouvinte."""
    subsystem.no_ar(P1, True)
    assert registro.no_ar() == {"aabbcc000001": True}
    assert subsystem.esquecer_a_palavra(P1) is True
    assert registro.no_ar() == {}, (
        "o ex-dono do canal ficou com o microfone no ar depois de perder a "
        f"eleição: {registro.no_ar()}"
    )
    assert registro.abertos() == {"aabbcc000001"}, (
        "esquecer a palavra derrubou o CANAL dele também — *perder o padrão "
        f"não é perder o canal*: {registro.abertos()}"
    )


def test_perder_o_padrao_nao_apaga_a_luz_nem_a_palavra_do_ex_dono(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """O laço da luz e o do microfone continuam o MESMO — e agora os dois FICAM."""
    d = _DaemonDeMentira()
    d.controller.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"uniq": P1, "connected": True, "transport": "bluetooth"},
        {"uniq": P2, "connected": True, "transport": "bluetooth"},
    ]
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert registro.no_ar() == {"aabbcc000001": True}
    asyncio.run(hotkey.ligar_o_microfone(d, P2, ligado=True))
    assert (False, P1) not in d.controller.leds, (
        f"a luz do ex-dono apagou sem ele sair do ar: {d.controller.leds}"
    )
    assert registro.no_ar() == {"aabbcc000001": True, "aabbcc000002": True}, (
        "ligar o microfone do P2 tirou o do P1 do ar: "
        f"{registro.no_ar()}"
    )


def test_um_uniq_ilegivel_nao_abre_pedido_fantasma(registro) -> None:  # type: ignore[no-untyped-def]
    """`norm_mac` só filtra hex: uma palavra qualquer vira endereço."""
    assert registro.dizer_no_ar("nao-e-um-mac", True) is False
    assert registro.no_ar() == {}, f"nasceu um pedido fantasma: {registro.no_ar()}"


def test_dizer_o_mesmo_duas_vezes_nao_acorda_o_laco(registro) -> None:  # type: ignore[no-untyped-def]
    """A `novidade` é BORDA — repetir o que já está dito não é notícia."""
    assert registro.dizer_no_ar(P1, True) is True
    registro.novidade.clear()
    assert registro.dizer_no_ar(P1, True) is True
    assert not registro.novidade.is_set(), (
        "repetir a mesma palavra acordou o laço de reconciliação"
    )
    assert registro.dizer_no_ar(P1, False) is True
    assert registro.novidade.is_set(), "a palavra MUDOU e o laço não foi acordado"


def test_ligar_pede_o_canal_e_calar_nao_o_solta(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Sem ponte não há a quem entregar a palavra — mas calar não desconecta."""
    subsystem.no_ar(P1, True)
    assert registro.abertos() == {"aabbcc000001"}, (
        "ligar o microfone não pediu o canal — sem ponte de pé o 0x32 não tem "
        f"para onde ir: {registro.abertos()}"
    )
    subsystem.no_ar(P1, False)
    assert registro.abertos() == {"aabbcc000001"}, (
        f"calar o microfone derrubou o canal dele: {registro.abertos()}"
    )
    assert registro.no_ar() == {"aabbcc000001": False}


# AS RÉGUAS DAQUI EXERCITAM A MESA DELA INTEIRA — os quatro DualSense.


def _mesa_de_quatro(daemon: Any) -> None:
    """Põe os QUATRO DualSense dela no backend do dublê, com o transporte."""
    daemon.controller.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"uniq": uniq, "connected": True, "transport": transporte}
        for uniq, transporte in MESA_DELA
    ]


def test_o_ato_recusado_nao_deixa_o_microfone_no_ar(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """A SEXTA PORTA, nos quatro controles dela."""
    for uniq, _ in MESA_DELA:
        d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
        _mesa_de_quatro(d)
        ato = asyncio.run(hotkey.ligar_o_microfone(d, uniq, ligado=True))
        assert ato.feito is False, f"{uniq}: a recusa saiu como ato feito"
        assert ato.canal_no_sistema.feita is False
        assert registro.no_ar() == {}, (
            f"{uniq}: o ato foi RECUSADO e a palavra dela ficou ligada — a "
            "tela diz recusado, o LED não acende, e a varredura seguinte "
            f"entrega `True` à ponte: {registro.no_ar()}"
        )


def test_o_canal_recusado_continua_pedido_para_a_ponte_poder_nascer(  # type: ignore[no-untyped-def]
    gancho, registro
) -> None:
    """Desfazer a PALAVRA não desfaz o PEDIDO — e a distinção é dela."""
    d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
    _mesa_de_quatro(d)
    asyncio.run(hotkey.ligar_o_microfone(d, P4, ligado=True))
    assert registro.abertos() == {"aabbcc000004"}, (
        "o ato recusado levou junto o PEDIDO de canal — a ponte não tem mais "
        f"como nascer, e o toque seguinte recusa pela mesma razão: {registro.abertos()}"
    )


def test_o_ato_recusado_devolve_a_palavra_que_ja_valia(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """Um ato que não aconteceu não muda NADA — nem para menos."""
    eleitor = _EleitorDeMentira()
    d = _DaemonDeMentira(eleitor)
    _mesa_de_quatro(d)
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert registro.no_ar() == {"aabbcc000001": True}
    eleitor.recusa = RECUSA_SEM_CANAL
    ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert ato.feito is False
    assert registro.no_ar() == {"aabbcc000001": True}, (
        "a recusa apagou a palavra que já valia — o microfone dela saiu do ar "
        f"por causa de um ato que não aconteceu: {registro.no_ar()}"
    )


def test_o_mudo_recusado_continua_calando(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """SÓ o `ligado=True` se desfaz. O mudo dela não depende de eleição."""
    d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
    _mesa_de_quatro(d)
    asyncio.run(hotkey.ligar_o_microfone(d, P2, ligado=False))
    assert registro.no_ar() == {"aabbcc000002": False}, (
        "o mudo dela foi desfeito por uma recusa de eleição — a voz volta ao "
        f"ar sem ela ter pedido: {registro.no_ar()}"
    )


def test_a_ponte_nao_recebe_pedido_ligado_depois_da_recusa(subsystem, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """O DESFECHO no aparelho, medido pelo LAÇO DE PRODUÇÃO nos quatro."""
    anteriores = eleicao.registrar_dizedor_do_no_ar(
        subsystem.no_ar, subsystem.esquecer_a_palavra, subsystem.palavra_no_ar
    )
    try:
        nos = [_no(uniq) for uniq, _ in MESA_DELA]
        for uniq, _ in MESA_DELA:
            d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
            _mesa_de_quatro(d)
            asyncio.run(hotkey.ligar_o_microfone(d, uniq, ligado=True))
        _uma_volta_do_laco(subsystem, monkeypatch, nos)
        assert len(subsystem._gerenciador.pontes) == 4
        for ponte in subsystem._gerenciador.pontes.values():
            assert ponte.ditos[-1:] == [None], (
                f"a ponte de {ponte.no.uniq} recebeu {ponte.ditos[-1:]} depois "
                "de o ato ter sido RECUSADO — o 0x32 sai LIGADO com a tela "
                "dizendo recusado e o LED apagado"
            )
    finally:
        eleicao.registrar_dizedor_do_no_ar(*anteriores)
