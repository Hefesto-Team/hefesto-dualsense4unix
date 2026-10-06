"""MIC-FASE-01 — o primeiro aperto do botão do microfone LIGA."""

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

P1 = "aabbcc000011"

P2 = "aabbcc000022"

ESPERA_DAS_GUARDAS_S: float = INPUT_GRACE_SEC + hotkey.MIC_SOSSEGO_S + 0.15

A_FRASE_DO_JOURNAL = recusa_de_quem_nao_elegeu(None).motivo


class _Resultado:
    """O que `eleger_o_controle`/`devolver_o_microfone` devolvem."""

    def __init__(self, *, ok: bool, ativo: str | None = None, motivo: str = "") -> None:
        self.ok = ok
        self.ativo = ativo
        self.motivo = motivo


class _EleitorDublado:
    """`EleitorDeMicrofone` de bancada, com o MESMO contrato do campo `eleito`."""

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

    def passar_o_padrao(
        self, no_ar: list[str], conectados: list[str], calou: str | None = None
    ) -> _Resultado:
        """A pergunta de `EleitorDeMicrofone.passar_o_padrao`, com o contrato dela."""
        for candidato in no_ar:
            passado = self.eleger_o_controle(candidato, conectados)
            if passado.ok:
                return passado
        volta = self.devolver_o_microfone()
        if volta.ok or calou is None:
            return volta
        if self.eleito == calou:
            self.eleito = None
        return _Resultado(ok=True)


class _BackendComOKernelDentro:
    """O backend dublado, e o que ele dubla é o `hid-playstation`."""

    def __init__(self, uniqs: tuple[str, ...] = (P1,)) -> None:
        self.uniqs = list(uniqs)
        self._kernel_mudo = dict.fromkeys(uniqs, False)
        self._firmware_mudo = dict.fromkeys(uniqs, False)
        self._seq = dict.fromkeys(uniqs, 0)
        self._pedido: dict[str, bool] = {}
        self.leds: dict[str, bool] = {}
        self.escritas_do_mudo: list[tuple[bool | None, str | None]] = []


    def apertar(self, uniq: str) -> None:
        """O dedo do usuário no botão: o backend conta o aperto, o driver alterna e escreve."""
        self._pedido[uniq] = not self._firmware_mudo[uniq]
        self._seq[uniq] += 1
        self._kernel_mudo[uniq] = not self._kernel_mudo[uniq]
        self._firmware_mudo[uniq] = self._kernel_mudo[uniq]


    def bordas_do_mic(self) -> dict[str, tuple[int, bool, float | None]]:
        return {
            u: (self._seq[u], self._pedido.get(u, self._firmware_mudo[u]), None)
            for u in self.uniqs
        }

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
            # campo não muda de valor — ver `_PinnedPyDualSense.
            return True
        self._firmware_mudo[uniq] = bool(muted)
        return True

    def set_mic_led(self, aceso: bool, *, uniq: str | None = None) -> None:
        self.leds[uniq or "<sem endereço>"] = bool(aceso)

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True} for u in self.uniqs]

    def is_connected(self) -> bool:
        return bool(self.uniqs)


    def mudo_no_firmware(self, uniq: str) -> bool:
        return self._firmware_mudo[uniq]


class _Config:
    mic_button_toggles_system = True


class _Daemon:
    """O mínimo do daemon que os dois laços tocam."""

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


async def _com_os_dois_lacos(daemon: _Daemon, corpo: Any) -> None:
    """Sobe `mic_da_mesa_loop` + `mic_button_loop`, roda `corpo`, derruba tudo."""
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
    """Cancela e ESPERA todas — inclusive as que o próprio ato criou."""
    for tarefa in tarefas:
        tarefa.cancel()
    if tarefas:
        await asyncio.gather(*tarefas, return_exceptions=True)


async def _drenar(segundos: float = 0.5) -> None:
    """Deixa a borda atravessar os dois laços e o ato terminar."""
    fim = asyncio.get_running_loop().time() + segundos
    while asyncio.get_running_loop().time() < fim:
        await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def _sem_eco_de_teste_vizinho() -> Any:
    """`hotkey._ECO_DO_ATO` é global por módulo: zerar antes e depois."""
    hotkey._ECO_DO_ATO.clear()
    yield
    hotkey._ECO_DO_ATO.clear()


def _recado(daemon: _Daemon, uniq: str) -> Any:
    return getattr(daemon, recado_do_microfone.ATRIBUTO, {}).get(uniq)


class TestOPrimeiroAperto:
    @pytest.mark.asyncio
    async def test_o_primeiro_aperto_depois_de_conectar_elege_o_canal(self) -> None:
        """A cena inteira: controle novo na mesa, um aperto, o canal é dele."""
        daemon, backend, eleitor = _a_mesa()

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert backend.mudo_no_firmware(P1) is not None
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
        """A frase que ela leu no cartão não pode mais nascer deste gesto."""
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
        """O contrato do LED é do usuário: *aceso = este mic está no ar*."""
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


class TestOBitDoFirmware:
    @pytest.mark.asyncio
    async def test_o_bit_do_mudo_sai_nao_mudo_no_aparelho(self) -> None:
        """Sem isto a cura elege o canal de um microfone que o kernel mutou."""
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
        """Escrever o byte toma a posse; não devolvê-la mata o botão dela."""
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


class TestQuemEstaNoArContinuaPodendoSair:
    @pytest.mark.asyncio
    async def test_quem_esta_no_ar_sai_do_ar_ao_apertar(self) -> None:
        """A segunda linha da tabela NÃO muda, e é ela que protege o silêncio."""
        daemon, backend, eleitor = _a_mesa()

        async def corpo() -> None:
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
        """A recusa de quem nunca elegeu é texto DO USUÁRIO, e continua viva."""
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


class TestAMesaDeDois:
    @pytest.mark.asyncio
    async def test_o_segundo_controle_tambem_liga_no_primeiro_aperto(self) -> None:
        """Os quatro ficam no ar juntos: o P2 entrar não tira o P1."""
        daemon, backend, eleitor = _a_mesa((P1, P2))

        async def corpo() -> None:
            await _drenar(ESPERA_DAS_GUARDAS_S)
            backend.apertar(P1)
            await _drenar()
            backend.apertar(P2)
            await _drenar()

        await _com_os_dois_lacos(daemon, corpo)

        assert ("eleger", P1) in eleitor.chamadas

        assert ("eleger", P2) not in eleitor.chamadas, (
            "o segundo controle TOMOU o padrão do primeiro. Enquanto `eleger` "
            "for um ato só, a reancoragem vale apenas com a mesa sem dono — "
            f"ver MIC-FASE-01, §o que falta: {eleitor.chamadas}"
        )
        no_ar = hotkey._no_ar_da_sessao(daemon)
        assert no_ar.esta(P1), "quem apertou primeiro, com a mesa livre, entra"
        assert not no_ar.esta(P2), (
            "o P2 entrou no ar por um caminho que também o faria tomar o "
            "padrão da P1 — enquanto `eleger` for um ato só, isto tem de "
            f"continuar fechado: {sorted(no_ar.todos()) if hasattr(no_ar, 'todos') else no_ar}"
        )
        assert backend.mudo_no_firmware(P1) is False
        assert backend.mudo_no_firmware(P2) is True, (
            "a P2 foi recusada, logo o bit que o kernel acabou de virar fica "
            "como está — não se toma a posse do `common[9]` de quem não entrou"
        )
