"""O GESTO DELA PÕE O MICROFONE NO AR — a costura, não a ponte.

`test_o_microfone_pelo_radio_alimenta_o_no.py` mede a PONTE obedecendo à
palavra dela. Este arquivo mede o caminho que leva a palavra até lá, e as três
perguntas que ele responde são as três que a medição de 08/09/2026 nomeou como
risco:

1. **O ATO diz a palavra?** (risco 4 — *"a cura nasce cobrindo um chamador
   só"*.) A costura tem de ficar em `hotkey._metade_do_canal`, por onde passam
   os DOIS chamadores de `ligar_o_microfone` — o 🎙 da tela e a borda do botão
   do plástico. Feita em `ipc_handlers._handle_mic_canal_set`, o plástico
   ficaria de fora **com a suíte verde**, e a regra dela é explícita: *"o botão
   fisico do mic se ligado no microfone ele fica ligado tambem.  # (noqa-acento) dela
   indepente se nativo ou virtual"*.

2. **A palavra sobrevive ao hotplug?** (risco 5.) No rádio a reconexão é
   rotina: o gerenciador derruba a ponte e ergue outra, e a nova nasce sem
   saber de nada. Se o latch morasse na ponte, a primeira reconexão o apagaria
   e o microfone cairia em silêncio — o mesmo sintoma que a cura fecha,
   voltando por outra porta.

3. **As cinco portas de saída fecham?** O latch não é *"liga e deixa ligado
   para sempre"* porque cinco coisas o matam, e nenhuma delas é nova.

NENHUM TESTE DESTE ARQUIVO FALA COM O DAEMON DELA, com o PipeWire ou com um
hidraw: tudo aqui é o registro em memória e dublês.

OS ENDEREÇOS SÃO SINTÉTICOS E MASCARADOS — octetos 4 e 5 zerados, a máscara da
casa.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as eleicao

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


# ---------------------------------------------------------------------------
# Os dublês
# ---------------------------------------------------------------------------


class _PonteDeMentira:
    """O mínimo que `_aplicar_a_palavra_dela` toca — e a porta que ela chama."""

    def __init__(self, uniq: str, caminho: str | None = None) -> None:
        self.no = _no(uniq, caminho)
        self.ditos: list[bool | None] = []

    def dizer_o_pedido_dela(self, ligado: bool | None) -> None:
        self.ditos.append(ligado)


class _GerenciadorDeMentira:
    """O gerenciador, com o que o `_loop` do subsystem realmente chama.

    `reconciliar` faz o que o de produção faz e que importa aqui: ergue uma
    ponte NOVA para cada nó que ainda não tem uma — e a nova nasce **sem
    memória**, que é o hotplug de rádio inteiro.
    """

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
    """Um registro PRÓPRIO — nunca o singleton do processo.

    Escrever no `PEDIDOS` do módulo contaminaria o teste seguinte, que é
    exatamente o que o `registro=` injetável do subsystem existe para evitar.
    """
    return bt_mic.RegistroDePedidosDeCanal()


@pytest.fixture()
def subsystem(registro):  # type: ignore[no-untyped-def]
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._gerenciador = _GerenciadorDeMentira()
    return sub


# ---------------------------------------------------------------------------
# MORDIDA 1 — O ATO DIZ A PALAVRA, e é no ponto que cobre os dois botões
# ---------------------------------------------------------------------------


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


class _EleitorDeMentira:
    def __init__(self) -> None:
        self.eleito: str | None = None

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> Any:
        self.eleito = uniq
        return eleicao.ResultadoDaEleicao(ok=True, alvo=uniq, ativo=f"fonte-de-{uniq}")

    def devolver_o_microfone(self) -> Any:
        self.eleito = None
        return eleicao.ResultadoDaEleicao(ok=True, ativo="fonte-de-antes")


class _DaemonDeMentira:
    def __init__(self) -> None:
        self.controller = _BackendDeMentira()
        self._eleitor_de_microfone = _EleitorDeMentira()
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
    """Instala o subsystem como quem atende a palavra dela, e restaura depois.

    É o MESMO mecanismo que o produto usa (`registrar_dizedor_do_no_ar`), e é
    de propósito: um gancho de mentira mediria o teste, não o produto.
    """
    anteriores = eleicao.registrar_dizedor_do_no_ar(
        subsystem.no_ar, subsystem.esquecer_a_palavra
    )
    yield subsystem
    eleicao.registrar_dizedor_do_no_ar(*anteriores)


def test_o_ato_do_microfone_diz_a_palavra_dela(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """MORDIDA 1: `ligar_o_microfone` põe o pedido dela no registro.

    **E ISTO COBRE OS DOIS BOTÕES DE UMA VEZ.** `ligar_o_microfone` é a função
    única do ato — `test_o_microfone_e_um_estado_so` prova, por nome, que o
    `mic_button_loop` (o plástico) e o `_handle_mic_canal_set` (a tela) chamam
    ela e mais ninguém. Medir aqui é medir os dois.

    ARRANQUE A COSTURA (tire o `dizer_no_ar(uniq, ligado)` de
    `hotkey._metade_do_canal`) e esta régua REPROVA.
    """
    d = _DaemonDeMentira()
    ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert ato.canal_no_sistema.feita
    assert registro.no_ar() == {"aabbcc000001": True}, (
        "o ato ligou o canal e NÃO disse que o microfone ia ao ar — pelo rádio "
        "o 0x32 continua seguindo só o ouvinte, e a source que a eleição "
        f"acabou de escolher está SUSPENDED: {registro.no_ar()}"
    )


def test_o_ato_de_calar_tambem_e_dito(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """O mudo dela é palavra, não ausência de palavra.

    `False` tem de chegar como `False`, e não como *"esqueça"*: é ele que vence
    um aplicativo gravando. Um ato de calar que só apagasse o pedido deixaria o
    microfone dela no ar enquanto qualquer app tivesse o nó aberto.
    """
    d = _DaemonDeMentira()
    d._eleitor_de_microfone.eleito = P1
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=False))
    assert registro.no_ar() == {"aabbcc000001": False}, (
        f"o ato de calar não chegou ao registro: {registro.no_ar()}"
    )


def test_sem_ninguem_atendendo_o_ato_nao_explode(registro) -> None:  # type: ignore[no-untyped-def]
    """Subsystem no chão: a palavra não é atendida e o ato segue igual.

    O lado inseguro seria o contrário — o toque no botão do microfone dela
    virando um traceback no laço do daemon. É a mesma regra de `pedir_canal`.
    """
    anteriores = eleicao.registrar_dizedor_do_no_ar(None, None)
    try:
        d = _DaemonDeMentira()
        ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
        assert ato.canal_no_sistema.feita
        assert eleicao.dizer_no_ar(P1, True) is False
        assert eleicao.esquecer_a_palavra(P1) is False
    finally:
        eleicao.registrar_dizedor_do_no_ar(*anteriores)


# ---------------------------------------------------------------------------
# MORDIDA 2 — A PALAVRA SOBREVIVE AO HOTPLUG (risco 5)
# ---------------------------------------------------------------------------


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
    # A RECONEXÃO: mesmo endereço, outro nó. A ponte velha cai, nasce uma nova
    # — e a nova não sabe de nada.
    _uma_volta_do_laco(subsystem, monkeypatch, [_no(P1, "/dev/hidraw9")])
    assert "/dev/hidraw5" not in subsystem._gerenciador.pontes
    nova = subsystem._gerenciador.pontes["/dev/hidraw9"]
    assert nova.ditos[-1:] == [True], (
        "a ponte que nasceu depois do hotplug não recebeu o pedido dela; no "
        f"rádio isso é o microfone caindo sozinho na reconexão: {nova.ditos}"
    )


def test_a_palavra_vai_para_a_ponte_certa_e_so_para_ela(subsystem) -> None:  # type: ignore[no-untyped-def]
    """Quatro na mesa: ligar o microfone de um não liga o dos outros três.

    É a mesma regra que `alvos()` já cumpre para o canal, medida aqui para a
    palavra: `None` é o que a ponte de quem não pediu nada tem de receber.
    """
    p1 = subsystem._gerenciador.erguer(P1)
    p2 = subsystem._gerenciador.erguer(P2)
    subsystem.no_ar(P1, True)
    assert p1.ditos[-1:] == [True], f"o dono não recebeu a palavra: {p1.ditos}"
    assert p2.ditos[-1:] == [None], (
        f"ligar o microfone de um mexeu no do vizinho: {p2.ditos}"
    )


# ---------------------------------------------------------------------------
# MORDIDA 3 — AS PORTAS DE SAÍDA. O latch não fica ligado para sempre.
# ---------------------------------------------------------------------------


def test_o_controle_que_sai_da_mesa_perde_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Quarta porta: quem sai do rádio perde a palavra junto com o pedido.

    Sem isto a reconexão traria o microfone de volta ao ar sozinha, que é o
    *"liga sozinho"* pela porta dos fundos.
    """
    subsystem.no_ar(P1, True)
    subsystem.no_ar(P2, True)
    registro.esquecer_ausentes(frozenset({"aabbcc000002"}))
    assert registro.no_ar() == {"aabbcc000002": True}, (
        "a palavra de quem saiu da mesa sobreviveu — a reconexão dele "
        f"ressuscitaria o microfone: {registro.no_ar()}"
    )


def test_desmarcar_o_modo_apaga_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Quinta porta: `soltar` (o "Aplicar" dela) leva a palavra junto.

    O interruptor do card vence o botão do controle — e derrubar a ponte sem
    apagar a palavra deixaria o pedido esperando a próxima ponte subir.
    """
    subsystem.no_ar(P1, True)
    registro.soltar(P1)
    assert registro.no_ar() == {}, (
        f"desmarcar o modo derrubou a ponte e guardou o pedido: {registro.no_ar()}"
    )


def test_a_sessao_que_acaba_leva_a_palavra(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """`limpar()` é o `stop()` do subsystem: os pedidos morrem com a sessão.

    Guardá-los faria o próximo boot subir microfone sem ninguém ter pedido
    nada — o mesmo motivo que o `limpar()` já tinha para os pedidos de canal.
    """
    subsystem.no_ar(P1, True)
    registro.limpar()
    assert registro.no_ar() == {}, (
        f"a palavra dela sobreviveu ao fim da sessão: {registro.no_ar()}"
    )


def test_perder_a_eleicao_esquece_a_palavra_e_nao_a_nega(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Perder o canal por gesto ALHEIO devolve a decisão ao ouvinte.

    Não é `dizer_no_ar(False)`: ela não pediu para ser calada, só deixou de ser
    a dona do canal. `False` venceria um aplicativo gravando; esquecer devolve
    o comportamento de 06/09/2026, que é a resposta certa para *"ninguém disse
    nada"*.

    E o par com o LED é o ponto: `_apagar_a_luz_de_quem_perdeu_o_canal` apaga a
    luz do ex-dono, e sem esta linha o plástico diria *"saí do ar"* com o 0x32
    ainda ligado — a mentira de segunda geração pelo lado de dentro.
    """
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


def test_a_luz_do_ex_dono_e_a_palavra_dele_caem_no_mesmo_gesto(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """O laço da luz e o do microfone são o MESMO — medido pelo produto.

    ARRANQUE o `esquecer_a_palavra(dono_antes)` de
    `_apagar_a_luz_de_quem_perdeu_o_canal` e esta régua REPROVA: a luz do P1
    apaga e o microfone dele continua no ar.
    """
    d = _DaemonDeMentira()
    d.controller.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"uniq": P1, "connected": True, "transport": "bluetooth"},
        {"uniq": P2, "connected": True, "transport": "bluetooth"},
    ]
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert registro.no_ar() == {"aabbcc000001": True}
    # O P2 aperta o botão DELE e ganha o canal. O P1 não tocou em nada.
    asyncio.run(hotkey.ligar_o_microfone(d, P2, ligado=True))
    assert (False, P1) in d.controller.leds, (
        f"a luz do ex-dono não apagou: {d.controller.leds}"
    )
    assert registro.no_ar() == {"aabbcc000002": True}, (
        "o P1 perdeu a luz e continuou com o microfone no ar — o LED passou a "
        f"mentir do lado de dentro: {registro.no_ar()}"
    )


# ---------------------------------------------------------------------------
# MORDIDA 4 — a chave, e a armadilha que `pedir` já documenta
# ---------------------------------------------------------------------------


def test_um_uniq_ilegivel_nao_abre_pedido_fantasma(registro) -> None:  # type: ignore[no-untyped-def]
    """`norm_mac` só filtra hex: uma palavra qualquer vira endereço.

    Medido em 03/09/2026 — ``"nao-e-um-mac"`` sai como ``"aeac"``. Sem os doze
    hex não há de quem seja o microfone, e um pedido fantasma que nenhum
    controle atende é um microfone que ninguém consegue soltar.
    """
    assert registro.dizer_no_ar("nao-e-um-mac", True) is False
    assert registro.no_ar() == {}, f"nasceu um pedido fantasma: {registro.no_ar()}"


def test_dizer_o_mesmo_duas_vezes_nao_acorda_o_laco(registro) -> None:  # type: ignore[no-untyped-def]
    """A `novidade` é BORDA — repetir o que já está dito não é notícia.

    Ela ACORDA a varredura; tocá-la a cada tique do botão faria o supervisor
    girar em falso sobre um estado que não mudou.
    """
    assert registro.dizer_no_ar(P1, True) is True
    registro.novidade.clear()
    assert registro.dizer_no_ar(P1, True) is True
    assert not registro.novidade.is_set(), (
        "repetir a mesma palavra acordou o laço de reconciliação"
    )
    assert registro.dizer_no_ar(P1, False) is True
    assert registro.novidade.is_set(), "a palavra MUDOU e o laço não foi acordado"


def test_ligar_pede_o_canal_e_calar_nao_o_solta(subsystem, registro) -> None:  # type: ignore[no-untyped-def]
    """Sem ponte não há a quem entregar a palavra — mas calar não desconecta.

    *"Ninguém perde nada quando outro é eleito — perder o padrão não é perder o
    canal"*. Calar o microfone é uma coisa; derrubar a ponte é outra, e quem a
    derruba é o controle sair da mesa ou ela desmarcar o modo.
    """
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
