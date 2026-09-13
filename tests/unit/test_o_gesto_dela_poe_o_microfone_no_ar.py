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
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"

#: A MESA DELA — quatro DualSense, dois no cabo e dois no rádio, na disposição
#: medida em 08/09/2026. As réguas da sexta porta exercitam os QUATRO, e não é
#: enfeite: a leva anterior foi derrubada por um teste que prometia a mesa dela
#: no nome e exercitava DOIS controles no corpo, escolhendo o único arranjo em
#: que o defeito não aparece.
MESA_DELA: tuple[tuple[str, str], ...] = (
    (P1, "bluetooth"),
    (P2, "usb"),
    (P3, "usb"),
    (P4, "bluetooth"),
)


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


#: A recusa que o eleitor REAL devolve mais vezes por rádio — a ponte demora a
#: publicar e `eleger_o_controle` responde isto (`eleicao_de_microfone`, o ramo
#: `if not fontes`). Copiada palavra por palavra de lá de propósito: um dublê
#: que inventasse a própria frase mediria a si mesmo.
RECUSA_SEM_CANAL = (
    "o PipeWire não publica canal de captura nenhum para o "
    "controle — no rádio isso precisa da ponte de microfone"
)


class _EleitorDeMentira:
    """O eleitor dublado — e ele SABE RECUSAR, que é o que o real faz.

    **ELE DEVOLVIA `ok=True` SEMPRE, e isso cegou a suíte inteira** (achado do
    advogado do diabo, 08/09/2026). O eleitor REAL tem CINCO recusas em
    `eleger_por_uniq` mais a de `eleger_o_controle`, e a última é o desfecho
    COMUM por rádio. Com um dublê que nunca recusa, nenhum teste deste arquivo
    podia ver a SEXTA PORTA — o ato recusado deixando a palavra dela LIGADA —,
    e ela atravessou a leva inteira com doze réguas verdes.

    É a cicatriz de `_mutar` outra vez, na mesma semana: *um dublê mais frouxo
    que a função real envenena a suíte inteira*.

    **E A POSSE SÓ MUDA QUANDO A ELEIÇÃO É CONFERIDA**, como no real: lá
    `eleger_por_uniq` só escreve `self.eleito` dentro do `if resultado.ok`.
    Marcar o dono na intenção é a mentira de segunda geração que o módulo
    inteiro existe para não contar, e um dublê que a comete ensina o teste a
    aceitá-la.
    """

    def __init__(self, *, recusa: str | None = None) -> None:
        self.eleito: str | None = None
        #: `None` = elege; uma frase = recusa com ela, como o eleitor real.
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
    """Instala o subsystem como quem atende a palavra dela, e restaura depois.

    É o MESMO mecanismo que o produto usa (`registrar_dizedor_do_no_ar`), e é
    de propósito: um gancho de mentira mediria o teste, não o produto.

    **OS TRÊS, como o `_instalar_o_gancho_da_procura` do produto instala.**
    Registrar dois deixaria `palavra_no_ar` sempre `None`, e o desfazer da
    sexta porta só saberia apagar — que é justamente o chute que ele evita.
    """
    anteriores = eleicao.registrar_dizedor_do_no_ar(
        subsystem.no_ar, subsystem.esquecer_a_palavra, subsystem.palavra_no_ar
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
    anteriores = eleicao.registrar_dizedor_do_no_ar(None, None, None)
    try:
        d = _DaemonDeMentira()
        ato = asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
        assert ato.canal_no_sistema.feita
        assert eleicao.dizer_no_ar(P1, True) is False
        assert eleicao.esquecer_a_palavra(P1) is False
        assert eleicao.palavra_no_ar(P1) is None
        # E O ATO RECUSADO TAMBÉM NÃO EXPLODE sem ninguém atendendo: o
        # desfazer da sexta porta passa pelos mesmos ganchos ausentes.
        recusado = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
        ato2 = asyncio.run(hotkey.ligar_o_microfone(recusado, P1, ligado=True))
        assert ato2.canal_no_sistema.feita is False
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

    E o par com o LED é o ponto: quem sai do ar DE FATO perde a luz, e sem esta
    linha o plástico diria *"saí do ar"* com o 0x32 ainda ligado — a mentira de
    segunda geração pelo lado de dentro. Desde 13/09/2026 (OS-QUATRO-NO-AR-01)
    perder só o PADRÃO não chama esquecer: os quatro ficam no ar juntos.
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


def test_perder_o_padrao_nao_apaga_a_luz_nem_a_palavra_do_ex_dono(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """O laço da luz e o do microfone continuam o MESMO — e agora os dois FICAM.

    FATO SUBSTITUÍDO (13/09/2026, OS-QUATRO-NO-AR-01). Esta régua se chamava
    `test_a_luz_do_ex_dono_e_a_palavra_dele_caem_no_mesmo_gesto` e cobrava que
    o P1 perdesse a luz e a palavra quando o P2 ganhava o padrão. Era o
    um-de-cada-vez que a sprint desfez: os quatro ficam no ar juntos, e só a
    fonte padrão do sistema é de um. O par luz-palavra continua valendo — quem
    sai do ar de fato perde os dois juntos, e isso está em
    `test_os_quatro_microfones_ficam_no_ar.py`.

    ARRANQUE a guarda `_no_ar_da_sessao(daemon).esta(dono_antes)` de
    `_apagar_a_luz_de_quem_perdeu_o_canal` e esta régua REPROVA: a luz do P1
    apaga e a palavra dele some.
    """
    d = _DaemonDeMentira()
    d.controller.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"uniq": P1, "connected": True, "transport": "bluetooth"},
        {"uniq": P2, "connected": True, "transport": "bluetooth"},
    ]
    asyncio.run(hotkey.ligar_o_microfone(d, P1, ligado=True))
    assert registro.no_ar() == {"aabbcc000001": True}
    # O P2 aperta o botão DELE e ganha o padrão. O P1 não tocou em nada.
    asyncio.run(hotkey.ligar_o_microfone(d, P2, ligado=True))
    assert (False, P1) not in d.controller.leds, (
        f"a luz do ex-dono apagou sem ele sair do ar: {d.controller.leds}"
    )
    assert registro.no_ar() == {"aabbcc000001": True, "aabbcc000002": True}, (
        "ligar o microfone do P2 tirou o do P1 do ar: "
        f"{registro.no_ar()}"
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


# ---------------------------------------------------------------------------
# MORDIDA 5 — A SEXTA PORTA: o ato RECUSADO não deixa a palavra ligada
# ---------------------------------------------------------------------------
#
# Achada pelo advogado do diabo em 08/09/2026, DEPOIS de esta frente declarar
# "as cinco portas, todas com régua". As cinco de cima são condições sobre
# quando a palavra nasce e morre; a sexta é sobre o ato que NÃO aconteceu:
# `_metade_do_canal` dizia a palavra ANTES da eleição e nada a desfazia quando
# `resultado.ok` era `False`. A tela dizia RECUSADO, o LED não acendia, e a
# varredura seguinte entregava `True` à ponte — 0x32 LIGADO.
#
# A SUÍTE ERA CEGA A ELA porque o `_EleitorDeMentira` devolvia `ok=True`
# SEMPRE. Ele agora sabe recusar, com a frase que o eleitor real usa.
#
# AS RÉGUAS DAQUI EXERCITAM A MESA DELA INTEIRA — os quatro DualSense.


def _mesa_de_quatro(daemon: Any) -> None:
    """Põe os QUATRO DualSense dela no backend do dublê, com o transporte."""
    daemon.controller.describe_controllers = lambda: [  # type: ignore[method-assign]
        {"uniq": uniq, "connected": True, "transport": transporte}
        for uniq, transporte in MESA_DELA
    ]


def test_o_ato_recusado_nao_deixa_o_microfone_no_ar(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """A SEXTA PORTA, nos quatro controles dela.

    ARRANQUE A CURA (tire o `_devolver_a_palavra` do ramo `not resultado.ok`
    de `hotkey._metade_do_canal`) e esta régua REPROVA nos quatro: cada um
    deles fica com `no_ar()[uniq] is True` depois de o produto ter respondido
    que o canal não foi tocado.

    A recusa é a REAL e a mais comum por rádio — `eleger_o_controle` responde
    isto sempre que a ponte de microfone ainda não publicou o nó, que é o
    desfecho normal do primeiro toque.
    """
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
    """Desfazer a PALAVRA não desfaz o PEDIDO — e a distinção é dela.

    *"Ninguém perde nada quando outro é eleito — perder o padrão não é perder o
    canal"*. O pedido é o que faz a ponte de rádio subir; sem ele o segundo
    toque dela recusaria pela mesma razão que o primeiro, para sempre.

    Se alguém "curar" a sexta porta chamando `soltar` em vez de
    `esquecer_a_palavra`, esta régua REPROVA.
    """
    d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
    _mesa_de_quatro(d)
    asyncio.run(hotkey.ligar_o_microfone(d, P4, ligado=True))
    assert registro.abertos() == {"aabbcc000004"}, (
        "o ato recusado levou junto o PEDIDO de canal — a ponte não tem mais "
        f"como nascer, e o toque seguinte recusa pela mesma razão: {registro.abertos()}"
    )


def test_o_ato_recusado_devolve_a_palavra_que_ja_valia(gancho, registro) -> None:  # type: ignore[no-untyped-def]
    """Um ato que não aconteceu não muda NADA — nem para menos.

    O P1 está no ar por um ato que deu certo. O toque seguinte é recusado (a
    ponte caiu no meio, o WirePlumber reelegeu, o que for): desfazer não pode
    ser *apagar sempre*, senão a recusa tira do ar um microfone que ela pôs lá
    e que continua sendo dela.

    ARRANQUE a leitura do `antes` (troque o `_devolver_a_palavra` por um
    `esquecer_a_palavra` seco) e esta régua REPROVA.
    """
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
    """SÓ o `ligado=True` se desfaz. O mudo dela não depende de eleição.

    A recusa de quem não elegeu diz, com todas as letras, que *"este botão
    apagou a luz deste controle e não mexeu no canal de áudio de ninguém"* — o
    microfone DELE tem de sair do ar do mesmo jeito. Desfazer o mudo aqui
    poria de volta no ar uma voz que ela mandou calar.

    Ponha um `if True:` no lugar do `if not ligado: return` de
    `_devolver_a_palavra` e esta régua REPROVA.
    """
    d = _DaemonDeMentira(_EleitorDeMentira(recusa=RECUSA_SEM_CANAL))
    _mesa_de_quatro(d)
    asyncio.run(hotkey.ligar_o_microfone(d, P2, ligado=False))
    assert registro.no_ar() == {"aabbcc000002": False}, (
        "o mudo dela foi desfeito por uma recusa de eleição — a voz volta ao "
        f"ar sem ela ter pedido: {registro.no_ar()}"
    )


def test_a_ponte_nao_recebe_pedido_ligado_depois_da_recusa(subsystem, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """O DESFECHO no aparelho, medido pelo LAÇO DE PRODUÇÃO nos quatro.

    As três réguas acima medem o registro; esta mede o que chega à PONTE, que
    é quem escreve o `0x32`. É a diferença entre *"o estado interno está
    certo"* e *"o controle dela não está transmitindo"*.

    O `_loop` é o de produção, e as pontes são as que ele mesmo ergue.
    """
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
