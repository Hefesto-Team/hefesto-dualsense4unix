"""MIC-FASE-01 — o primeiro aperto do botão do microfone LIGA.

**A QUEIXA DELA, 17/09/2026**, e ela é de uso, não de código: o primeiro aperto
do botão físico do microfone, depois de conectar o controle, não ligava nada.
Ela precisava apertar duas vezes.

**A CAUSA, medida no journal DELA às 01:47:13.** O `hid-playstation` não
entrega o botão do microfone como evento evdev: ele CONSOME a borda e faz um
toggle CEGO do próprio estado — ``ds->mic_muted = !ds->mic_muted``
(`assets/dkms/hid-playstation/hid-playstation.c:1673`) — sobre um campo que
vive numa struct zerada e portanto nasce ``false`` = NÃO-mudo (`:279`). O
primeiro aperto depois de cada conexão chega, sempre, como ``mudo=True``.

E `mic_button_loop` traduzia isso numa linha::

    await ligar_o_microfone(daemon, uniq, ligado=not mudo)   # ligado = False

``ligado=False`` é DESLIGAR. Como ninguém estava eleito, o ato caía no ramo da
recusa de `_eleger_ou_devolver` e o produto respondia a frase que ela leu no
cartão — *"ninguém está com o microfone da mesa, então não há o que devolver"*
—, apagando de quebra o LED que o kernel acabara de acender::

    01:47:13  mic_da_mesa_borda  mudo=True seq=1
              mic_da_mesa_mudo_de_quem_nao_elegeu  dono=None eleito=None
              mic_ato  canal=False feito=False ligado=False
    01:52:42  mic_da_mesa_borda  mudo=False seq=2      (o SEGUNDO aperto)
              mic_ato  canal=True feito=True firmware=True ligado=True

**O CONTRATO É DELA, de 17/09/2026:** o botão físico *"alterna o mudo"* DESTE
controle; *"A ideia é termos 4 controles BT cada qual com seu Mic ligado"* —
o desenho que já é o de hoje (OS-QUATRO-NO-AR-01). São DUAS perguntas: *"está
no ar"* é de cada controle, até quatro; *"é a fonte padrão"* é de um só.

A cura é `hotkey._o_que_a_borda_pede`, e ela reusa a condição que já existia:
``fora_do_padrao and not no_ar.esta(uniq)``.

------------------------------------------------------------------------------
POR QUE ESTA RÉGUA MONTA A CENA INTEIRA, E NO TEMPO
------------------------------------------------------------------------------

Nenhuma das réguas de microfone desta casa montava a sequência *"controle
recém-conectado + PRIMEIRO aperto"*. Elas medem endereço, repique, eco, recusa
e as duas metades do ato — nunca a FASE.

Então aqui:

* os **dois laços do produto** sobem juntos — `mic_da_mesa_loop`, que vê a
  borda e lhe dá endereço, e `mic_button_loop`, que a traduz em ato. Chamar
  `ligar_o_microfone` direto mediria o ato, e o defeito não estava no ato:
  estava na TRADUÇÃO da borda;
* a cena **espera as duas guardas passarem** — `INPUT_GRACE_SEC` (0,3 s) e
  `MIC_SOSSEGO_S` (1,0 s). Sem a espera a régua mede a carência, não o gesto,
  e daria verde com a cura arrancada;
* o dublê do backend **é o kernel**: `apertar()` faz o mesmo toggle cego do
  `hid-playstation`, sobre um estado que nasce não-mudo. É daí que a fase
  errada nasce, e uma régua que publicasse a borda à mão estaria digitando a
  premissa em vez de produzi-la.

**A SEGUNDA METADE DA MORDIDA, e sem ela a primeira mente.** Afirmar só que o
ato ficou `feito` deixa passar a cura que elege o canal de um microfone que o
kernel acabou de mutar: `_metade_do_firmware` é IDEMPOTENTE no caminho do
plástico e devolve `MetadeDoAto(True)` sem escrever byte nenhum — exatamente
quando o bit está no valor errado para a fase invertida. Por isso
`TestOBitDoFirmware` afirma o BYTE: o mudo tem de sair ``False`` no aparelho, e
a posse tem de voltar ao kernel depois, senão a cura mata o botão dela.

------------------------------------------------------------------------------
COMO ARRANCAR A CURA (as três saídas estão no relatório da sprint)
------------------------------------------------------------------------------

1. Em `hotkey.mic_button_loop`, troque ``ligado = _o_que_a_borda_pede(...)`` de
   volta por ``ligado = not mudo``. Reprovam os três testes de
   `TestOPrimeiroAperto` e os dois de `TestOBitDoFirmware`.
2. Só a segunda metade: mantenha a tradução curada e faça
   `_metade_do_firmware` devolver `MetadeDoAto(True)` antes de comparar o bit.
   `TestOPrimeiroAperto` continua VERDE e `TestOBitDoFirmware` reprova — que é
   a prova de que a segunda metade morde sozinha.

Os endereços são SINTÉTICOS e mascarados (octetos 4 e 5 zerados): um endereço
real da bancada dela não entra em arquivo versionado, e há dois portões sobre
isso.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.lifecycle import INPUT_GRACE_SEC
from hefesto_dualsense4unix.daemon.subsystems import (
    hotkey,
    mic_da_mesa,
    recado_do_microfone,
)
from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
    recusa_de_quem_nao_elegeu,
)

#: O controle dela, recém-conectado. Vem na grafia do PLÁSTICO (sem
#: dois-pontos), que é como `bordas_do_mic()` o entrega — a identidade nasce do
#: fd, não do report.
P1 = "aabbcc000011"

#: O vizinho, para a cena da mesa de dois.
P2 = "aabbcc000022"

#: A ESPERA QUE FAZ ESTA RÉGUA MEDIR O GESTO, e não as guardas. A carência
#: pós-conexão é contada do nascimento do laço das bordas; o sossego é por
#: controle. Somá-las com folga é o que garante que a borda que chegar depois
#: daqui seja lida como gesto — se a régua não esperar, ela dá verde sobre uma
#: borda engolida, com a cura arrancada ou não.
ESPERA_DAS_GUARDAS_S: float = INPUT_GRACE_SEC + hotkey.MIC_SOSSEGO_S + 0.15

#: A frase que ela leu no cartão às 01:47:13. É texto DELA, e vive no módulo da
#: eleição — redigitá-la aqui criaria a segunda verdade sobre a mesma recusa.
A_FRASE_DO_JOURNAL = recusa_de_quem_nao_elegeu(None).motivo


# ---------------------------------------------------------------------------
# Os dublês — e o do backend É O KERNEL, de propósito
# ---------------------------------------------------------------------------


class _Resultado:
    """O que `eleger_o_controle`/`devolver_o_microfone` devolvem."""

    def __init__(self, *, ok: bool, ativo: str | None = None, motivo: str = "") -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _EleitorDublado:
    """`EleitorDeMicrofone` de bancada, com o MESMO contrato do campo `eleito`.

    Ele só passa a valer o `uniq` na eleição CONFERIDA e cai na devolução
    conferida. Um dublê que zerasse sempre seria mais frouxo que o produto, e
    esta casa já pagou por isso: *"o portão não mordia porque o dublê trazia o
    mesmo default falso"*.
    """

    def __init__(self, *, elege_ok: bool = True, devolve_ok: bool = True) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.eleito: str | None = None
        self._elege_ok = elege_ok
        self._devolve_ok = devolve_ok

    def eleger_o_controle(self, uniq: str, conectados: list[str]) -> _Resultado:
        del conectados
        self.chamadas.append(("eleger", uniq))
        if not self._elege_ok:
            return _Resultado(ok=False, motivo="a bancada recusou de propósito")
        self.eleito = uniq
        return _Resultado(ok=True, ativo=f"hefesto_mic_{uniq[-6:]}")

    def devolver_o_microfone(self) -> _Resultado:
        self.chamadas.append(("devolver", None))
        if not self._devolve_ok:
            return _Resultado(ok=False, motivo="não há microfone para onde voltar")
        self.eleito = None
        return _Resultado(ok=True, ativo="mic_da_placa_mae")


class _BackendComOKernelDentro:
    """O backend dublado, e o que ele dubla é o `hid-playstation`.

    **`apertar()` NÃO PUBLICA BORDA — ele faz o que o driver faz.** O kernel
    guarda o PRÓPRIO estado (``ds->mic_muted``), que nasce ``False`` numa
    struct zerada, e a cada borda do botão o inverte e manda o valor novo ao
    firmware. A borda que o produto vê é a mudança do bit ``STATUS_MIC_MUDO``
    no report de entrada — ou seja, a CONSEQUÊNCIA, não o aperto.

    Escrever a premissa (*"chega uma borda com mudo=True"*) direto no barramento
    seria digitar o defeito em vez de produzi-lo. Aqui ele nasce da mesma
    aritmética que o produz no aparelho dela.

    **A NOSSA ESCRITA NÃO CONTA BORDA**, e isso também é o produto: o backend
    real marca o que pedimos (`_marcar_o_mudo_que_pedimos`) e engole o eco em
    `_registrar_borda_do_mic`. Um dublê que contasse o eco faria o laço
    processar o próprio ato duas vezes — o defeito de 10/09/2026.
    """

    def __init__(self, uniqs: tuple[str, ...] = (P1,)) -> None:
        self.uniqs = list(uniqs)
        #: `ds->mic_muted` do driver. Nasce `False` porque a struct é zerada.
        self._kernel_mudo = dict.fromkeys(uniqs, False)
        #: O bit `STATUS_MIC_MUDO` que o firmware publica no report.
        self._firmware_mudo = dict.fromkeys(uniqs, False)
        self._seq = dict.fromkeys(uniqs, 0)
        self.leds: dict[str, bool] = {}
        #: Cada `set_microphone_mute` que chegou, com endereço.
        self.escritas_do_mudo: list[tuple[bool | None, str | None]] = []

    # -- o lado do kernel ---------------------------------------------------

    def apertar(self, uniq: str) -> None:
        """O dedo dela no botão. O driver alterna o estado dele e escreve."""
        self._kernel_mudo[uniq] = not self._kernel_mudo[uniq]
        self._escrever_no_firmware(uniq, self._kernel_mudo[uniq], conta_borda=True)

    def _escrever_no_firmware(
        self, uniq: str, mudo: bool, *, conta_borda: bool
    ) -> None:
        if self._firmware_mudo[uniq] == mudo:
            # Sem mudança no bit não há borda: é o report repetindo o mesmo
            # valor, e o contador do backend real só sobe na TRANSIÇÃO.
            return
        self._firmware_mudo[uniq] = mudo
        if conta_borda:
            self._seq[uniq] += 1

    # -- o que o produto chama ----------------------------------------------

    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {u: (self._seq[u], self._firmware_mudo[u], None) for u in self.uniqs}

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool] | None:
        alvo = uniq if uniq in self._firmware_mudo else None
        if alvo is None:
            return None
        return {
            "fone_plugado": False,
            "mic_externo": False,
            "mic_mudo": self._firmware_mudo[alvo],
        }

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        self.escritas_do_mudo.append((muted, uniq))
        if uniq not in self._firmware_mudo:
            return False
        if muted is None:
            # A POSSE VOLTA AO KERNEL. O bit de validação some do report e o
            # campo não muda de valor — ver `_PinnedPyDualSense.
            # set_microphone_mute`.
            return True
        self._escrever_no_firmware(uniq, bool(muted), conta_borda=False)
        return True

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.leds[uniq or "<sem endereço>"] = bool(aceso)

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True} for u in self.uniqs]

    def is_connected(self) -> bool:
        return bool(self.uniqs)

    # -- o que a régua lê ---------------------------------------------------

    def mudo_no_firmware(self, uniq: str) -> bool:
        return self._firmware_mudo[uniq]


class _Config:
    mic_button_toggles_system = True


class _Daemon:
    """O mínimo do daemon que os dois laços tocam.

    **`_run_blocking` NÃO ACEITA KEYWORDS**, e isso não é economia: é a
    assinatura do daemon real (`daemon/lifecycle.py`). Um dublê com `**kw` é
    mais frouxo que o produto, e foi assim que a máscara que nunca gravou um
    byte atravessou uma leva inteira com o teste verde — ver `hotkey._mutar`.
    """

    def __init__(self, backend: _BackendComOKernelDentro, eleitor: _EleitorDublado) -> None:
        self.bus = EventBus()
        self.config = _Config()
        self.controller = backend
        self._eleitor_de_microfone = eleitor
        self._tasks: list[asyncio.Task[Any]] = []
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    def is_paused(self) -> bool:
        return False

    def is_native_mode(self) -> bool:
        return False

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args)


def _a_mesa(
    uniqs: tuple[str, ...] = (P1,), *, elege_ok: bool = True
) -> tuple[_Daemon, _BackendComOKernelDentro, _EleitorDublado]:
    backend = _BackendComOKernelDentro(uniqs)
    eleitor = _EleitorDublado(elege_ok=elege_ok)
    return _Daemon(backend, eleitor), backend, eleitor


# ---------------------------------------------------------------------------
# A cena: os DOIS laços do produto, no tempo
# ---------------------------------------------------------------------------


async def _com_os_dois_lacos(daemon: _Daemon, corpo: Any) -> None:
    """Sobe `mic_da_mesa_loop` + `mic_button_loop`, roda `corpo`, derruba tudo.

    A ordem importa: o consumidor assina o tópico dentro do laço, então esperar
    o `subscriber_count` é o que impede a régua de publicar para ninguém e dar
    verde sobre o vazio.
    """
    consumidor = asyncio.create_task(hotkey.mic_button_loop(daemon))  # type: ignore[arg-type]
    for _ in range(40):
        await asyncio.sleep(0.005)
        if daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA):
            break
    assert daemon.bus.subscriber_count(EventTopic.MIC_DA_MESA) == 1, (
        "o `mic_button_loop` não assinou o tópico — a cena mediria o vazio"
    )
    bordas = asyncio.create_task(mic_da_mesa.mic_da_mesa_loop(daemon))  # type: ignore[arg-type]
    try:
        await corpo()
    finally:
        daemon._parando = True
        await _derrubar(bordas, consumidor, *daemon._tasks)


async def _derrubar(*tarefas: asyncio.Task[Any]) -> None:
    """Cancela e ESPERA todas — inclusive as que o próprio ato criou.

    `_agendar_a_devolucao_da_posse` pendura uma task em `daemon._tasks`, e ela
    pode já ter terminado quando a cena acaba. `gather(..., return_exceptions=
    True)` é o que trata os dois desfechos sem transformar "terminou" em
    reprovação — e sem deixar «Task was destroyed but it is pending» vazar
    para o teste seguinte.
    """
    for tarefa in tarefas:
        tarefa.cancel()
    if tarefas:
        await asyncio.gather(*tarefas, return_exceptions=True)


async def _drenar(segundos: float = 0.5) -> None:
    """Deixa a borda atravessar os dois laços e o ato terminar.

    O laço das bordas varre a `INTERVALO_S` (0,05 s) e o ato tem um `await` por
    metade; a confirmação da posse tem passo de `PASSO_DA_CONFIRMACAO_S`
    (0,1 s). Meio segundo cobre os três com folga e continua curto.
    """
    fim = asyncio.get_running_loop().time() + segundos
    while asyncio.get_running_loop().time() < fim:
        await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def _sem_eco_de_teste_vizinho() -> Any:
    """`hotkey._ECO_DO_ATO` é global por módulo: zerar antes e depois.

    Ele guarda `{uniq: (instante, mudo)}` das escritas do ATO, e um resíduo de
    outro arquivo faria a primeira borda desta cena ser engolida como eco — o
    verde mais caro que existe, porque é verde sobre nada.
    """
    hotkey._ECO_DO_ATO.clear()
    yield
    hotkey._ECO_DO_ATO.clear()


def _recado(daemon: _Daemon, uniq: str) -> Any:
    return getattr(daemon, recado_do_microfone.ATRIBUTO, {}).get(uniq)


# ---------------------------------------------------------------------------
# 1. O PRIMEIRO APERTO — a cena dela, às 01:47:13
# ---------------------------------------------------------------------------


class TestOPrimeiroAperto:
    @pytest.mark.asyncio
    async def test_o_primeiro_aperto_depois_de_conectar_elege_o_canal(self) -> None:
        """A cena inteira: controle novo na mesa, um aperto, o canal é dele.

        Com a cura arrancada esta régua reprova com o ato de DESLIGAR: o
        eleitor não recebe nenhuma eleição e `eleito` fica `None`.
        """
        daemon, backend, eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert backend.mudo_no_firmware(P1) is not None  # a cena existiu
        assert ("eleger", P1) in eleitor.chamadas, (
            "o primeiro aperto não elegeu nada — a borda `mudo=True` do toggle "
            "cego do kernel foi lida como DESLIGAR, que é o defeito de "
            f"01:47:13. Chamadas ao eleitor: {eleitor.chamadas}"
        )
        assert eleitor.eleito == P1
        assert hotkey._no_ar_da_sessao(daemon).esta(P1), (
            "o controle elegeu e não entrou no ar — metade do ato"
        )

    @pytest.mark.asyncio
    async def test_o_primeiro_aperto_nao_recebe_a_frase_de_recusa(self) -> None:
        """A frase que ela leu no cartão não pode mais nascer deste gesto.

        É o sintoma exato do journal: `mic_da_mesa_mudo_de_quem_nao_elegeu` com
        `dono=None`, e o cartão dela dizendo que não há o que devolver.
        """
        daemon, backend, _eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        recado = _recado(daemon, P1)
        assert recado is not None, "o gesto dela não deixou recado nenhum"
        assert recado.motivo != A_FRASE_DO_JOURNAL, (
            "o aperto para LIGAR voltou com a recusa de quem nunca elegeu — é "
            f"a frase de 01:47:13, palavra por palavra: {recado.motivo!r}"
        )
        assert recado.gesto == "eleger" and recado.ok is True, (
            f"o recado do primeiro aperto ficou {recado.gesto!r}/{recado.ok}"
        )

    @pytest.mark.asyncio
    async def test_o_led_do_plastico_fica_aceso(self) -> None:
        """O contrato do LED é dela: *aceso = este mic está no ar*.

        No journal o primeiro aperto APAGAVA a luz que o kernel acabara de
        acender. Com a fase reancorada ela fica acesa, porque o canal é dele.
        """
        daemon, backend, _eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert backend.leds.get(P1) is True, (
            "o primeiro aperto apagou o LED que o kernel tinha acendido — a "
            f"luz dele ficou {backend.leds!r}"
        )


# ---------------------------------------------------------------------------
# 2. O BIT DO FIRMWARE — a segunda metade, e ela morde sozinha
# ---------------------------------------------------------------------------


class TestOBitDoFirmware:
    @pytest.mark.asyncio
    async def test_o_bit_do_mudo_sai_nao_mudo_no_aparelho(self) -> None:
        """Sem isto a cura elege o canal de um microfone que o kernel mutou.

        `_metade_do_firmware` é idempotente no caminho do plástico e devolve
        `MetadeDoAto(True)` sem escrever byte nenhum quando o bit já está no
        valor pedido. Com a fase INVERTIDA é exatamente esse o caso, e uma
        régua que só olhasse `ato.feito` passaria verde sobre uma voz que não
        sai do aparelho.
        """
        daemon, backend, _eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            assert backend.mudo_no_firmware(P1) is True, (
                "a premissa da cena caiu: o kernel tinha de ter MUTADO o "
                "microfone no primeiro aperto"
            )
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert (False, P1) in backend.escritas_do_mudo, (
            "o produto elegeu o canal e não desfez o mudo que o kernel acabou "
            f"de escrever — o aparelho ficou mudo. Escritas: "
            f"{backend.escritas_do_mudo!r}"
        )
        assert backend.mudo_no_firmware(P1) is False, (
            "o bit `STATUS_MIC_MUDO` ficou LIGADO com o canal no ar: a voz "
            "dela não sai, e o ato responde «feito»"
        )

    @pytest.mark.asyncio
    async def test_a_posse_do_mudo_volta_ao_kernel(self) -> None:
        """Escrever o byte toma a posse; não devolvê-la mata o botão dela.

        *"o botão do Controle sempre controla a interface"* (decisão dela,
        30/08/2026). `_confirmar_e_devolver` relê até o aparelho concordar e
        então manda `None`, que é o *"devolvo a posse ao `hid-playstation`"*.
        Uma cura que escrevesse o bit e ficasse com o campo deixaria o próximo
        aperto sem efeito nenhum.
        """
        daemon, backend, _eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert (None, P1) in backend.escritas_do_mudo, (
            "a posse do `common[9]` ficou NOSSA depois do gesto — o botão "
            f"físico dela morre no toque seguinte. Escritas: "
            f"{backend.escritas_do_mudo!r}"
        )


# ---------------------------------------------------------------------------
# 3. O RISCO QUE NÃO PODE REABRIR — e ele é de privacidade
# ---------------------------------------------------------------------------


class TestQuemEstaNoArContinuaPodendoSair:
    @pytest.mark.asyncio
    async def test_quem_esta_no_ar_sai_do_ar_ao_apertar(self) -> None:
        """A segunda linha da tabela NÃO muda, e é ela que protege o silêncio.

        Inverter o ramo da recusa sem distinguir faria um aperto de CALAR virar
        um aperto de LIGAR — o defeito de privacidade com o sinal trocado. A
        cena: ela já pôs o microfone no ar pela TELA, e então aperta o plástico.
        O toque tem de tirá-lo do ar.
        """
        daemon, backend, eleitor = _a_mesa()

        async def corpo() -> None:
            # A TELA — o 🎙 do card, que é o outro chamador de
            # `ligar_o_microfone` e não tem fase para reancorar.
            await hotkey.ligar_o_microfone(daemon, P1, ligado=True)  # type: ignore[arg-type]
            assert hotkey._no_ar_da_sessao(daemon).esta(P1)
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert ("devolver", None) in eleitor.chamadas, (
            "quem estava no ar apertou o botão e o produto NÃO o tirou do ar — "
            f"o gesto de calar virou um gesto de ligar: {eleitor.chamadas}"
        )
        assert not hotkey._no_ar_da_sessao(daemon).esta(P1), (
            "o microfone continuou no ar depois de ela mandar calar"
        )
        assert backend.leds.get(P1) is False, (
            "a luz ficou acesa sobre um microfone que saiu do ar"
        )

    @pytest.mark.asyncio
    async def test_o_me_cale_da_tela_de_quem_nunca_elegeu_continua_recusado(
        self,
    ) -> None:
        """A recusa de quem nunca elegeu é texto DELA, e continua viva.

        A cura mora na tradução da BORDA, e não em `_eleger_ou_devolver`: o
        caminho da tela entrega o `ligado` que ela clicou, e um clique já é a
        intenção. Se alguém mover a reancoragem para dentro do ato, este teste
        reprova — e é isso que impede a cura de alcançar o chamador errado.
        """
        daemon, _backend, eleitor = _a_mesa((P1, P2))

        try:
            ato = await hotkey.ligar_o_microfone(daemon, P2, ligado=False)  # type: ignore[arg-type]
        finally:
            daemon._parando = True
            await _derrubar(*daemon._tasks)

        assert ato.ligado is False
        assert ato.canal_no_sistema.feita is False
        assert ato.canal_no_sistema.motivo == A_FRASE_DO_JOURNAL, (
            "a frase de recusa dela sumiu do caminho da tela — ou a "
            f"reancoragem da fase vazou para dentro do ato: {ato.motivo!r}"
        )
        assert ("eleger", P2) not in eleitor.chamadas, (
            "o «me cale» da tela virou uma eleição — é o defeito de "
            "privacidade com o sinal trocado"
        )


# ---------------------------------------------------------------------------
# 4. A MESA DE DOIS — a reancoragem é POR CONTROLE
# ---------------------------------------------------------------------------


class TestAMesaDeDois:
    @pytest.mark.asyncio
    async def test_o_segundo_controle_tambem_liga_no_primeiro_aperto(self) -> None:
        """Os quatro ficam no ar juntos: o P2 entrar não tira o P1.

        `OS-QUATRO-NO-AR-01` (13/09/2026) é o desenho que ela descreveu em
        17/09 — *"4 controles BT cada qual com seu Mic ligado"*. A fase errada
        alcançava os quatro, porque cada handle tem o seu `ds->mic_muted`
        zerado.
        """
        daemon, backend, eleitor = _a_mesa((P1, P2))

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()
            backend.apertar(P2)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert ("eleger", P1) in eleitor.chamadas

        # O QUE A CURA ALCANÇA HOJE, E O QUE FALTA — correção de 17/09/2026.
        #
        # Esta linha exigia `("eleger", P2)` e, para satisfazê-la, a primeira
        # escrita da reancoragem REABRIU um defeito de privacidade: com a P1 no
        # ar, a P2 apertando o botão dela para se calar tomava o microfone da
        # P1 (`eleitor.eleito` ia de …0011 para …0022). A suíte pegou antes de
        # chegar nela.
        #
        # A causa não é a fase: é que `eleger` faz DUAS coisas de uma vez —
        # põe o controle no ar E o torna a fonte padrão. Enquanto forem o mesmo
        # ato, "o P2 entra" e "o P2 toma o padrão da P1" são inseparáveis, e a
        # segunda não pode acontecer sem gesto explícito.
        #
        # A separação é o que falta, e está escrita na MIC-FASE-01: *"estar no
        # ar" é de cada controle, até quatro; "ser a fonte padrão" é de um só*.
        # Com a mesa SEM DONO — que é a cena da queixa dela, um controle só —
        # a cura vale inteira, e é o que os outros casos desta classe medem.
        assert ("eleger", P2) not in eleitor.chamadas, (
            "o segundo controle TOMOU o padrão do primeiro. Enquanto `eleger` "
            "for um ato só, a reancoragem vale apenas com a mesa sem dono — "
            f"ver MIC-FASE-01, §o que falta: {eleitor.chamadas}"
        )
        no_ar = hotkey._no_ar_da_sessao(daemon)
        # OS DOIS NO AR JUNTOS AINDA NÃO SAI DESTE GESTO — e o motivo é o mesmo
        # da asserção acima: `eleger` põe no ar E torna padrão num ato só.
        # Impedir a segunda (privacidade) impede a primeira junto.
        #
        # `OS-QUATRO-NO-AR-01` continua valendo e é medido onde nasceu: pelo
        # caminho da TELA e do IPC, quatro canais coexistem. O que falta é o
        # gesto do PLÁSTICO alcançar isso com a mesa já tendo dono, e isso
        # espera a separação escrita na MIC-FASE-01.
        assert no_ar.esta(P1), "quem apertou primeiro, com a mesa livre, entra"
        assert not no_ar.esta(P2), (
            "o P2 entrou no ar por um caminho que também o faria tomar o "
            "padrão da P1 — enquanto `eleger` for um ato só, isto tem de "
            f"continuar fechado: {sorted(no_ar.todos()) if hasattr(no_ar, 'todos') else no_ar}"
        )
        assert backend.mudo_no_firmware(P1) is False
        # E O FIRMWARE DA P2 FICA MUDO, que é a consequência coerente: o
        # kernel virou o bit na borda e nós NÃO o desfizemos, porque não
        # pusemos a P2 no ar. Desfazê-lo aqui seria escrever `common[9]` num
        # controle que o produto recusou — tomaria a posse do campo do kernel
        # e mataria o botão físico dela no toque seguinte, que é exatamente o
        # que a `_metade_do_firmware` documenta e evita.
        assert backend.mudo_no_firmware(P2) is True, (
            "a P2 foi recusada, logo o bit que o kernel acabou de virar fica "
            "como está — não se toma a posse do `common[9]` de quem não entrou"
        )
