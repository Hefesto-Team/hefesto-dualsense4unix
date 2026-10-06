"""O número do jogador se reorganiza na hora.

A cura 1 da O-NUMERO-DO-JOGADOR-SE-REORGANIZA-NA-HORA-E-O-JOGO-VE-01.

**O que o usuário viu, 29/09, ~18h10:** com os quatro na mesa, o P2 e o P3 desligados
pelo PS, e o roxo (o P4) *«ficou no player 4 durante muito muito tempo»*. O
diário mediu 5 min 3 s da saída ao P2 no aparelho: o lugar guardado venceu às
18:00:13 (30 s, a ``D-2409-O-ASSENTO-GUARDADO-NAO-ANDA``), e o gatilho da
numeração só armou às 18:04:44,9 — 300 s depois da última volta do laço.

**A causa:** o vencimento do lugar guardado muda o número sem evento nenhum, e
o único que perguntava pelo número (``armar_gatilho_da_cor_por_numeracao``) só
rodava na VOLTA do ``reconnect_loop``. Desde a família 5 da
O-REPOUSO-ESPERA-O-EVENTO-01 a volta dorme até
``TETO_DA_VOLTA_PELO_EVENTO_SEC`` (300 s) esperando um evento de ``/dev``, e o
vencimento é só relógio.

**A cura (a 1 da sprint):** a numeração se confere também em cada fatia da
espera (``_wait_online_or_hotplug``), logo depois do
``disparar_gatilhos_devidos``. A conferência é a mesma leitura que a tela faz a
10 Hz (``numeros_da_mesa``, memória sob o lock) e só arma quando a tabela
MUDA; armado, a fatia encolhe e o disparo cai 1,5 s depois.

**A bancada:** o ``ControllerIdentityRegistry`` de produção com relógio
injetado, a espera de produção (``_wait_online_or_hotplug``) com o dono do
evento ARMADO numa ``/dev`` de mentira (a receita das réguas da família 5, em
``test_o_repouso_espera_o_evento.py``) e um ``/dev/input`` que não muda. O
relógio é um só: ele move o registro, o ``time.monotonic`` do módulo da espera
(o mecanismo do gatilho) e cada fatia. Os escritores da cor são o único
dublê do controller, e cada um pergunta ao MESMO dono que o real
(``numero_da_lampada``) no instante em que escreve. Na régua 7, a bancada de
jogo aberto da O-ASSENTO-GUARDADO-NAO-ANDA-02 (backend real, co-op real,
registro real).

O número esperado sai da conta escrita aqui (a fila e quem saiu), nunca da
saída do produto.

AS MORDIDAS (29/09/2026, cada uma devolvida com o md5 conferido):

- a chamada da fatia arrancada: 36 de 46 reprovam — as 29 da régua 1 (a
  espera chega ao teto de 300 s sem armar, com o prazo de um DualSense ou de
  um externo), a 3 e a 4 que passam pelo vencimento, e as quatro da régua 7
  (as lâmpadas não se liberam e o P4 segue no boneco 4);
- a fatia que arma devolvendo True (acordar a volta e o ``connect()``): 34
  reprovam (a espera tem de ir até o teto);
- ``armar_gatilho_da_cor_por_numeracao`` armando sem comparar: as nove da
  régua 2 reprovam (o gatilho arma em toda fatia com a mesa parada);
- o contador da régua 3 enxerga um provedor de externos que lê arquivo: é a
  prova positiva, ``test_o_contador_enxerga_quem_le_arquivo``;
- ``_congelar_locked`` com os guardados na conta: a régua 4 reprova;
- sem a guarda da R-04 (``fixos`` vazio no ``coop._ordenar``): reprova
  ``test_o_p1_que_voltou_tarde_segue_no_boneco_do_posto``.

**A guarda da R-04 só trabalha com o vpad do posto FORA de ordem**, e isso só
acontece depois que o P1 volta tarde (o P2 segue no posto, com a carta 2). Nos
outros três casos da régua 7 ela não morde, e está medido: o primário é a
carta 1 (O-MODO-XBOX-NAO-E-QUEDA-02, item 4), e com o posto vago a carta dele é
a do lugar em que espera — o vpad do posto nunca sai do boneco. O quarto caso
é o que a sprint pedia: a fatia renumera com o posto fora de ordem, e o vpad
dele não entra na lista de recriação.

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

import hefesto_dualsense4unix.daemon.connection as cx
from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch
from hefesto_dualsense4unix.core.lightbar_gatilho import ATRASO_APOS_A_ULTIMA_CONEXAO_S
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    _present_ranks_of,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    prazo_do_lugar_guardado,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    P1,
    P2,
    P3,
    P4,
    Relogio,
    montar,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    config_isolado as config_isolado,
)
from tests.unit.test_o_repouso_espera_o_evento import contando
from tests.unit.test_o_repouso_espera_o_evento import (
    raizes as raizes,
)

QUATRO = (P1, P2, P3, P4)

PRAZO = prazo_do_lugar_guardado()
FATIA = cx.RECONNECT_HOTPLUG_POLL_INTERVAL_SEC
TIQUE_LENTO = 2.0
TETO = cx.TETO_DA_VOLTA_PELO_EVENTO_SEC


class _Tempo:
    """O ``time`` do módulo da espera, com o ``monotonic`` no relógio de mentira."""

    def __init__(self, relogio: Relogio) -> None:
        self._relogio = relogio

    def monotonic(self) -> float:
        return self._relogio()

    def __getattr__(self, nome: str) -> Any:
        return getattr(time, nome)


class _OsDoisEscritores:
    """O que a tarefa do gatilho da lightbar chama no controller."""

    def __init__(self, reg: ControllerIdentityRegistry, relogio: Relogio) -> None:
        self.reg = reg
        self.relogio = relogio
        self.radio: list[tuple[float, dict[str, int]]] = []
        self.cabo: list[float] = []

    def numeros(self) -> dict[str, int]:
        fora: dict[str, int] = {}
        for uniq in QUATRO:
            numero = self.reg.numero_da_lampada(uniq, assign=False)
            if numero is not None:
                fora[uniq] = numero
        return fora

    def reescrever_lightbar_por_hidraw(self) -> dict[str, bool]:
        numeros = self.numeros()
        self.radio.append((self.relogio(), numeros))
        return {uniq: True for uniq in numeros}

    def repintar_o_cabo_por_sysfs(self) -> dict[str, bool]:
        self.cabo.append(self.relogio())
        return {}


class _DaemonDaEspera:
    """O que a espera e o gatilho da lightbar usam do daemon."""

    def __init__(self, reg: ControllerIdentityRegistry, controller: Any) -> None:
        self.identity_registry = reg
        self.controller = controller
        self._stop_event: asyncio.Event | None = None

    def _is_stopping(self) -> bool:
        return self._stop_event is not None and self._stop_event.is_set()

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()


class _Espera:
    """Roda a espera de PRODUÇÃO com o relógio de mentira."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        daemon: Any,
        relogio: Relogio,
        *,
        ate: float,
        tique: Callable[[], None] | None = None,
        agenda: dict[float, Callable[[], None]] | None = None,
    ) -> None:
        self.daemon = daemon
        self.relogio = relogio
        self.decorrido = 0.0
        self.armados: list[tuple[float, str]] = []
        agenda = dict(sorted((agenda or {}).items()))
        proximo_tique = [relogio() + TIQUE_LENTO]

        async def esperar(_daemon: Any, segundos: float) -> None:
            relogio.avancar(segundos)
            self.decorrido += segundos
            while tique is not None and relogio() >= proximo_tique[0]:
                tique()
                proximo_tique[0] += TIQUE_LENTO
            while agenda and next(iter(agenda)) <= self.decorrido:
                agenda.pop(next(iter(agenda)))()
            if self.decorrido >= ate:
                daemon.stop()
            await asyncio.sleep(0)

        async def nada(*_a: Any, **_kw: Any) -> int:
            return 0

        armar_de_producao = cx.armar_gatilho

        def armar(d: Any, nome: str, *, evento: str, quantos: int = 1) -> bool:
            self.armados.append((relogio(), evento))
            return armar_de_producao(d, nome, evento=evento, quantos=quantos)

        monkeypatch.setattr(cx, "_wait_or_stop", esperar)
        monkeypatch.setattr(cx, "vigiar_escritor_cru", nada)
        monkeypatch.setattr(cx, "vigiar_o_sequestro", nada)
        monkeypatch.setattr(cx, "time", _Tempo(relogio))
        monkeypatch.setattr(cx, "armar_gatilho", armar)

    def rodar(self, watch: Any, *, conta: list[list[tuple[str, str]]] | None = None) -> bool:
        """A espera inteira; ``conta`` recebe o que o fio da espera abriu."""

        async def _rodar() -> bool:
            self.daemon._stop_event = asyncio.Event()
            if conta is None:
                return await cx._wait_online_or_hotplug(self.daemon, watch)
            with contando() as anotado:
                devolveu = await cx._wait_online_or_hotplug(self.daemon, watch)
            conta.append(list(anotado))
            return devolveu

        return asyncio.run(asyncio.wait_for(_rodar(), timeout=60.0))

    def armou_por_numeracao(self) -> list[float]:
        return [t for t, evento in self.armados if evento == "numeracao_da_mesa_mudou"]


def _sentar_na_ordem(
    reg: ControllerIdentityRegistry, relogio: Relogio, ordem: tuple[str, ...]
) -> None:
    """Cada um chega na SUA onda: a fila do momento é a ordem dada."""
    na_mesa: list[str] = []
    for uniq in ordem:
        na_mesa.append(uniq)
        reg.sync_connected(list(na_mesa))
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)


def _mesa_assentada(
    ordem: tuple[str, ...],
) -> tuple[Relogio, ControllerIdentityRegistry, _OsDoisEscritores, _DaemonDaEspera]:
    """A mesa de ``ordem``, estável, com as lâmpadas liberadas (a adoção já pintou)."""
    relogio = Relogio()
    reg = ControllerIdentityRegistry(clock=relogio)
    _sentar_na_ordem(reg, relogio, ordem)
    relogio.avancar(id_mod.JANELA_MESA_ESTAVEL_SEC + 1.0)
    reg.sync_connected(list(ordem))
    assert reg.liberar_as_lampadas() is True
    escritores = _OsDoisEscritores(reg, relogio)
    daemon = _DaemonDaEspera(reg, escritores)
    assert escritores.numeros() == {u: n + 1 for n, u in enumerate(ordem)}
    return relogio, reg, escritores, daemon


def _a_volta(daemon: Any) -> None:
    """O que a volta do laço faz antes de dormir: conferir a numeração."""
    cx.armar_gatilho_da_cor_por_numeracao(daemon)


def _watch_parado(entradas: Path) -> InputDirWatch:
    """O ``/dev/input`` de mentira, já lido: sem nó novo, ``poll()`` é False."""
    watch = InputDirWatch(root=str(entradas))
    watch.poll()
    return watch


ORDENS = [QUATRO[i:] + QUATRO[:i] for i in range(4)]
SAEM = [
    grupo for n in (1, 2, 3) for grupo in itertools.combinations((1, 2, 3), n)
]


@pytest.mark.usefixtures("config_isolado")
class TestOPrazoVenceEOGatilhoArma:
    @pytest.mark.parametrize("saem", SAEM, ids=["sai-" + "-".join(map(str, s)) for s in SAEM])
    @pytest.mark.parametrize("ordem", ORDENS, ids=[f"fica-{o[3][-2:]}" for o in ORDENS])
    def test_a_fatia_arma_e_as_lampadas_andam(
        self,
        raizes: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        ordem: tuple[str, ...],
        saem: tuple[int, ...],
    ) -> None:
        entradas, _dev = raizes
        relogio, reg, escritores, daemon = _mesa_assentada(ordem)
        ficam = [u for pos, u in enumerate(ordem, start=1) if pos not in saem]
        esperado = {u: n + 1 for n, u in enumerate(ficam)}

        reg.sync_connected(ficam)
        saida = relogio()
        _a_volta(daemon)
        assert escritores.numeros() == {u: n + 1 for n, u in enumerate(ordem) if u in ficam}

        espera = _Espera(
            monkeypatch,
            daemon,
            relogio,
            ate=TETO + FATIA,
            tique=lambda: reg.sync_connected(ficam),
        )
        devolveu = espera.rodar(_watch_parado(entradas))

        vence = saida + PRAZO
        armou = espera.armou_por_numeracao()
        assert armou, (
            f"o prazo venceu em {vence - saida:.0f} s e ninguém armou o gatilho "
            f"da numeração na espera (o teto é {TETO:.0f} s)"
        )
        assert vence <= armou[0] <= vence + FATIA, (
            f"o gatilho armou {armou[0] - saida:.2f} s depois da saída; "
            f"o prazo venceu aos {PRAZO:.0f} s e a fatia é de {FATIA:.0f} s"
        )
        assert len(armou) == 1, f"armou mais de uma vez: {armou}"
        pinturas = [(t, n) for t, n in escritores.radio if n == esperado]
        assert pinturas, f"as lâmpadas nunca disseram {esperado}: {escritores.radio}"
        assert pinturas[0][0] <= vence + FATIA + ATRASO_APOS_A_ULTIMA_CONEXAO_S, (
            f"as lâmpadas andaram {pinturas[0][0] - vence:.2f} s depois do prazo"
        )
        assert escritores.cabo, "o cabo não foi repintado junto"
        assert devolveu is False, "a espera acordou como hotplug sem nó novo"
        assert espera.decorrido == pytest.approx(TETO), "a fatia não pode encurtar a volta"

    def test_o_prazo_de_um_externo_tambem_arma(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A outra causa sem hotplug: o lugar guardado de um controle EXTERNO vence.

        A fila é única (NUM-01): o P1, depois um externo, depois o P2 — 1, 2 e
        3. O externo sai, o lugar dele fica guardado 30 s no registro DELE, e
        quando vence o P2 passa a 2 sem que nada mude em ``/dev`` nem no
        registro dos DualSense. A ponte é a de produção
        (``ExternalLedSync._wire_presence_providers`` e o lifecycle).
        """
        entradas, _dev = raizes
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        externos = ExternalIdentityRegistry(clock=relogio)
        reg.set_external_reserve_provider(lambda: set(externos.snapshot().values()))
        reg.set_external_presence_provider(externos.lugares_da_mesa)
        reg.set_external_release_provider(externos.soltar_os_lugares_guardados)
        externos.set_dualsense_release_provider(
            lambda: reg.soltar_os_lugares_guardados(motivo="chegou_gente_nova")
        )
        externos.set_dualsense_presence_provider(lambda: _present_ranks_of(reg))
        externo = "aa:bb:cc:00:00:0e"

        reg.sync_connected([P1])
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        assert externos.slot_for(externo, reserve=1) == 2
        externos.sync_connected([externo])
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        reg.sync_connected([P1, P2])
        relogio.avancar(id_mod.JANELA_MESA_ESTAVEL_SEC + 1.0)
        reg.sync_connected([P1, P2])
        assert reg.liberar_as_lampadas() is True
        escritores = _OsDoisEscritores(reg, relogio)
        daemon = _DaemonDaEspera(reg, escritores)
        assert escritores.numeros() == {P1: 1, P2: 3}, "a conta escrita aqui: P1, externo, P2"

        externos.sync_connected([])
        saida = relogio()
        _a_volta(daemon)

        def tique() -> None:
            reg.sync_connected([P1, P2])
            externos.sync_connected([])

        espera = _Espera(monkeypatch, daemon, relogio, ate=TETO + FATIA, tique=tique)
        assert espera.rodar(_watch_parado(entradas)) is False

        vence = saida + PRAZO
        armou = espera.armou_por_numeracao()
        assert armou and vence <= armou[0] <= vence + FATIA, (
            f"o prazo do externo venceu aos {PRAZO:.0f} s e a fatia armou em {armou}"
        )
        pinturas = [t for t, n in escritores.radio if n == {P1: 1, P2: 2}]
        assert pinturas and pinturas[0] <= vence + FATIA + ATRASO_APOS_A_ULTIMA_CONEXAO_S, (
            f"as lâmpadas do P2 não disseram 2 depois do prazo do externo: {escritores.radio}"
        )
        assert espera.decorrido == pytest.approx(TETO), "a fatia não pode encurtar a volta"


@pytest.mark.usefixtures("config_isolado")
class TestAMesaParadaNaoArma:
    def test_trezentos_segundos_de_fatias_nenhum_gatilho(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entradas, _dev = raizes
        relogio, reg, escritores, daemon = _mesa_assentada(QUATRO)
        _a_volta(daemon)
        espera = _Espera(
            monkeypatch,
            daemon,
            relogio,
            ate=TETO + FATIA,
            tique=lambda: reg.sync_connected(list(QUATRO)),
        )
        assert espera.rodar(_watch_parado(entradas)) is False
        assert espera.armados == [], f"a mesa parada armou: {espera.armados}"
        assert escritores.radio == []
        assert espera.decorrido == pytest.approx(TETO), "uma volta por teto, como na família 5"

    @pytest.mark.parametrize("sai", QUATRO, ids=["p1", "p2", "p3", "p4"])
    def test_dentro_do_prazo_nenhum_gatilho(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, sai: str
    ) -> None:
        entradas, _dev = raizes
        relogio, reg, escritores, daemon = _mesa_assentada(QUATRO)
        ficam = [u for u in QUATRO if u != sai]
        reg.sync_connected(ficam)
        _a_volta(daemon)
        espera = _Espera(
            monkeypatch,
            daemon,
            relogio,
            ate=PRAZO - 0.5,
            tique=lambda: reg.sync_connected(ficam),
        )
        espera.rodar(_watch_parado(entradas))
        assert espera.armados == [], f"armou dentro do prazo: {espera.armados}"
        assert escritores.numeros() == {u: n + 1 for n, u in enumerate(QUATRO) if u != sai}

    @pytest.mark.parametrize("sai", QUATRO, ids=["p1", "p2", "p3", "p4"])
    def test_quem_troca_de_transporte_dentro_do_prazo_nao_arma(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, sai: str
    ) -> None:
        """A troca de cabo por rádio da fala do usuário: sai e volta em segundos."""
        entradas, _dev = raizes
        relogio, reg, escritores, daemon = _mesa_assentada(QUATRO)
        ficam = [u for u in QUATRO if u != sai]
        na_mesa = [ficam]
        reg.sync_connected(ficam)
        _a_volta(daemon)

        voltou: list[float] = []

        def voltar() -> None:
            voltou.append(relogio())
            na_mesa[0] = list(QUATRO)
            reg.sync_connected(list(QUATRO))

        espera = _Espera(
            monkeypatch,
            daemon,
            relogio,
            ate=TETO + FATIA,
            tique=lambda: reg.sync_connected(na_mesa[0]),
            agenda={4.0: voltar},
        )
        espera.rodar(_watch_parado(entradas))
        assert all(t >= voltou[0] for t, _e in espera.armados), (
            f"armou com ele fora, dentro do prazo: {espera.armados}"
        )
        assert len(espera.armados) <= 1, f"armou mais de uma vez: {espera.armados}"
        original = {u: n + 1 for n, u in enumerate(QUATRO)}
        assert all(numeros == original for _t, numeros in escritores.radio), (
            f"o número de alguém andou na troca de transporte: {escritores.radio}"
        )
        assert escritores.numeros() == original


def _com_os_externos(reg: ControllerIdentityRegistry) -> ExternalIdentityRegistry:
    """A ponte de produção: os lugares dos externos na conta da mesa."""
    externos = ExternalIdentityRegistry()
    reg.set_external_presence_provider(externos.lugares_da_mesa)
    return externos


@pytest.mark.usefixtures("config_isolado")
class TestAFatiaNaoAbreArquivo:
    def test_cento_e_cinquenta_fatias_de_mesa_parada(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entradas, _dev = raizes
        relogio, reg, _escritores, daemon = _mesa_assentada(QUATRO)
        _com_os_externos(reg)
        _a_volta(daemon)
        espera = _Espera(monkeypatch, daemon, relogio, ate=TETO + FATIA)
        conta: list[list[tuple[str, str]]] = []
        espera.rodar(_watch_parado(entradas), conta=conta)
        assert espera.decorrido / FATIA == pytest.approx(150)
        assert conta == [[]], f"a espera abriu ou listou: {conta[0][:10]}"

    def test_o_prazo_que_vence_no_meio_nao_abre_nada(
        self, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entradas, _dev = raizes
        relogio, reg, escritores, daemon = _mesa_assentada(QUATRO)
        _com_os_externos(reg)
        reg.sync_connected([P1, P4])
        _a_volta(daemon)
        espera = _Espera(monkeypatch, daemon, relogio, ate=TETO + FATIA)
        conta: list[list[tuple[str, str]]] = []
        espera.rodar(_watch_parado(entradas), conta=conta)
        assert espera.armou_por_numeracao(), "a régua não passou pelo vencimento"
        assert escritores.radio, "a régua não passou pelo disparo"
        assert conta == [[]], f"a espera abriu ou listou: {conta[0][:10]}"

    def test_o_contador_enxerga_quem_le_arquivo(
        self,
        raizes: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A prova de que o contador vê: um provedor de externos que lê arquivo."""
        entradas, _dev = raizes
        relogio, reg, _escritores, daemon = _mesa_assentada(QUATRO)
        arquivo = tmp_path / "externos.json"
        arquivo.write_text(json.dumps([]), encoding="utf-8")
        reg.set_external_presence_provider(
            lambda: set(json.loads(arquivo.read_text(encoding="utf-8")))
        )
        _a_volta(daemon)
        espera = _Espera(monkeypatch, daemon, relogio, ate=10 * FATIA)
        conta: list[list[tuple[str, str]]] = []
        espera.rodar(_watch_parado(entradas), conta=conta)
        abertos = [c for e, c in conta[0] if e == "open" and c == str(arquivo)]
        assert abertos, f"o contador não viu o arquivo: {conta[0][:10]}"


D, E, F = P1, P2, P3


@pytest.fixture
def fila_gravada(config_isolado: Path) -> bytes:
    """A fila de ontem no disco: D, E, F, nessa ordem."""
    relogio = Relogio()
    reg = ControllerIdentityRegistry(clock=relogio)
    _sentar_na_ordem(reg, relogio, (D, E, F))
    relogio.avancar(id_mod.JANELA_MESA_ESTAVEL_SEC + 1.0)
    reg.sync_connected([D, E, F])
    assert reg.snapshot() == {D: 1, E: 2, F: 3}
    return (config_isolado / "controllers.json").read_bytes()


def _a_sessao_de_hoje(config: Path, gravada: bytes) -> tuple[Relogio, ControllerIdentityRegistry]:
    """E chega, D chega, F chega, e D sai — tudo antes de a mesa assentar."""
    (config / "controllers.json").write_bytes(gravada)
    relogio = Relogio()
    reg = ControllerIdentityRegistry(clock=relogio)
    reg.load()
    assert reg.snapshot() == {D: 1, E: 2, F: 3}
    for na_mesa in ([E], [E, D], [E, D, F], [E, F]):
        reg.sync_connected(na_mesa)
        relogio.avancar(1.0)
    assert not reg.mesa_congelada()
    return relogio, reg


class TestAOrdemCongeladaEAMesma:
    def test_a_fatia_congela_o_mesmo_que_a_volta(
        self,
        raizes: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
        config_isolado: Path,
        fila_gravada: bytes,
    ) -> None:
        entradas, _dev = raizes

        relogio, reg = _a_sessao_de_hoje(config_isolado, fila_gravada)
        relogio.avancar(TETO)
        reg.numeros_da_mesa()
        na_volta = reg.snapshot()

        relogio, reg = _a_sessao_de_hoje(config_isolado, fila_gravada)
        daemon = _DaemonDaEspera(reg, _OsDoisEscritores(reg, relogio))
        _a_volta(daemon)
        espera = _Espera(monkeypatch, daemon, relogio, ate=TETO + FATIA)
        espera.rodar(_watch_parado(entradas))
        assert reg.mesa_congelada(), "a régua não passou pelo congelamento"
        na_fatia = reg.snapshot()

        assert na_fatia == na_volta, (
            f"a fatia congelou outra ordem: na volta {na_volta}, na fatia {na_fatia}"
        )
        assert na_fatia == {D: 1, E: 2, F: 3}


class _WatchParado:
    """O ``/dev/input`` da bancada de jogo não muda durante a espera."""

    def poll(self) -> bool:
        return False


@pytest.fixture
def jogo_aberto(
    config_isolado: Path, raizes: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[tuple[str, ...]], Any]]:
    """A bancada de jogo aberto com os quatro, as lâmpadas liberadas e ``saem`` fora."""

    def _montar(saem: tuple[str, ...]) -> Any:
        bancada = montar(monkeypatch, 4, "mista", jogo=True)
        assert bancada.reg.liberar_as_lampadas() is True
        relogio = bancada.tempo
        assert isinstance(relogio, Relogio)
        escritores = _OsDoisEscritores(bancada.reg, relogio)
        radio = escritores.reescrever_lightbar_por_hidraw
        monkeypatch.setattr(bancada.inst, "reescrever_lightbar_por_hidraw", radio)
        monkeypatch.setattr(
            bancada.inst, "repintar_o_cabo_por_sysfs", escritores.repintar_o_cabo_por_sysfs
        )
        daemon = bancada.daemon
        daemon._stop_event = None
        daemon._is_stopping = lambda: (
            daemon._stop_event is not None and daemon._stop_event.is_set()
        )

        async def _run_blocking(fn: Any, *args: Any) -> Any:
            return fn(*args)

        daemon._run_blocking = _run_blocking
        daemon.stop = lambda: daemon._stop_event.set()
        monkeypatch.setattr(cx, "_o_barramento_hid_mudou", lambda _d: False)
        for uniq in saem:
            bancada.mesa.levantar(uniq)
        bancada.tique()
        _a_volta(daemon)
        return bancada, escritores

    yield _montar


def _tique_lento(bancada: Any) -> None:
    """O batimento de 2 s sem o ``connect()``: o lifecycle, o poll e o co-op."""
    bancada.inst.read_state()
    bancada.reg.sync_connected(
        [u for u in bancada.inst.alvos_conectados().values() if isinstance(u, str)]
    )
    bancada.coop.sync()
    bancada.coop.forward_all()
    bancada.coop.forward_all()
    bancada.conferir_invariantes()


class TestComOJogoNaAutoridade:
    def test_os_secundarios_se_recriam_e_o_p1_fica(
        self, jogo_aberto: Callable[[tuple[str, ...]], Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fala do usuário: o P2 e o P3 desligam, o roxo (P4) vira P2 no jogo."""
        bancada, escritores = jogo_aberto((P2, P3))
        vpad_do_p1 = bancada.vpad_do_p1
        vpad_do_p4 = bancada.vpad_de(P4)
        saida = bancada.tempo()
        espera = _Espera(
            monkeypatch,
            bancada.daemon,
            bancada.tempo,
            ate=PRAZO + 3 * FATIA,
            tique=lambda: _tique_lento(bancada),
        )
        assert espera.rodar(_WatchParado()) is False

        armou = espera.armou_por_numeracao()
        assert armou and armou[0] <= saida + PRAZO + FATIA, (
            f"a numeração não armou na fatia depois do prazo: {armou}"
        )
        assert escritores.numeros() == {P1: 1, P4: 2}
        assert bancada.a_tela() == {P1: 1, P4: 2}
        assert bancada.o_jogo_ve() == {1: P1, 2: P4}, (
            f"o jogo não vê o roxo no jogador 2: {bancada.o_jogo_ve()}"
        )
        assert bancada.vpad_de(P4) is not vpad_do_p4, "o P4 não renasceu no boneco 2"
        assert bancada.daemon._gamepad_device is vpad_do_p1 and vpad_do_p1.vivo, (
            "a R-04: o vpad do P1 não se recria com o jogo na autoridade"
        )
        bancada.o_jogo_segue_a_tela()

    def test_o_p1_sai_e_o_vpad_dele_fica(
        self, jogo_aberto: Callable[[tuple[str, ...]], Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O P1 sai e o prazo passa: os outros descem, e o vpad do P1 não renasce."""
        bancada, escritores = jogo_aberto((P1,))
        vpad_do_p1 = bancada.vpad_do_p1
        saida = bancada.tempo()
        espera = _Espera(
            monkeypatch,
            bancada.daemon,
            bancada.tempo,
            ate=PRAZO + 3 * FATIA,
            tique=lambda: _tique_lento(bancada),
        )
        espera.rodar(_WatchParado())

        armou = espera.armou_por_numeracao()
        assert armou and armou[0] <= saida + PRAZO + FATIA, (
            f"a numeração não armou na fatia depois do prazo: {armou}"
        )
        assert escritores.numeros() == {P2: 1, P3: 2, P4: 3}
        assert bancada.daemon._gamepad_device is vpad_do_p1 and vpad_do_p1.vivo, (
            "a R-04: o vpad do P1 não se recria com o jogo na autoridade"
        )
        assert bancada.dono_do_vpad_do_p1() == P2
        bancada.o_jogo_segue_a_tela()

    def test_o_prazo_de_outro_vence_com_o_p1_fora_e_o_vpad_dele_espera(
        self, jogo_aberto: Callable[[tuple[str, ...]], Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O P2 sai, o P1 sai dez segundos depois, e o prazo do P2 vence primeiro."""
        bancada, escritores = jogo_aberto((P2,))
        vpad_do_p1 = bancada.vpad_do_p1
        for _ in range(5):
            bancada.tique()
        bancada.mesa.levantar(P1)
        bancada.tique()
        _a_volta(bancada.daemon)
        faltam = PRAZO - 6 * TIQUE_LENTO
        espera = _Espera(
            monkeypatch,
            bancada.daemon,
            bancada.tempo,
            ate=faltam + 3 * FATIA,
            tique=lambda: _tique_lento(bancada),
        )
        espera.rodar(_WatchParado())

        assert espera.armou_por_numeracao(), "o prazo do P2 venceu e a fatia não armou"
        assert escritores.numeros() == {P3: 2, P4: 3}
        assert bancada.daemon._gamepad_device is vpad_do_p1 and vpad_do_p1.vivo, (
            "a R-04: o vpad do P1 não se recria com o jogo na autoridade"
        )
        assert bancada.dono_do_vpad_do_p1() is None, "o posto do P1 ainda espera por ele"
        assert bancada.o_jogo_ve() == {1: None, 2: P3, 3: P4}, (
            f"o jogo não vê a mesa de agora: {bancada.o_jogo_ve()}"
        )

    def test_o_p1_que_voltou_tarde_segue_no_boneco_do_posto(
        self, jogo_aberto: Callable[[tuple[str, ...]], Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Onde a R-04 segura de verdade quando a fatia renumera."""
        bancada, escritores = jogo_aberto(())
        vpad_do_p1 = bancada.vpad_do_p1
        via = bancada.mesa.transporte_de(P1)
        bancada.mesa.levantar(P1)
        for _ in range(int(PRAZO / TIQUE_LENTO) + 3):
            bancada.tique()
            bancada.reg.liberar_as_lampadas()
        bancada.mesa.sentar(P1, transporte=via)
        for _ in range(3):
            bancada.tique()
            bancada.reg.liberar_as_lampadas()
        assert bancada.dono_do_vpad_do_p1() == P2, "o P2 assumiu o posto no prazo do P1"
        assert bancada.coop._p1_espera_o_jogo is True, (
            "a volta tardia do P1 recriou o vpad do posto com o jogo na autoridade"
        )
        assert bancada.o_jogo_ve() == {1: P2, 2: P1, 3: P3, 4: P4}

        bancada.mesa.levantar(P3)
        bancada.tique()
        _a_volta(bancada.daemon)
        vpad_do_p4 = bancada.vpad_de(P4)
        saida = bancada.tempo()
        espera = _Espera(
            monkeypatch,
            bancada.daemon,
            bancada.tempo,
            ate=PRAZO + 3 * FATIA,
            tique=lambda: _tique_lento(bancada),
        )
        with structlog.testing.capture_logs() as registros:
            espera.rodar(_WatchParado())

        armou = espera.armou_por_numeracao()
        assert armou and armou[0] <= saida + PRAZO + FATIA, (
            f"a numeração não armou na fatia depois do prazo do P3: {armou}"
        )
        assert escritores.numeros() == {P1: 1, P2: 2, P4: 3}
        recriadas = [r["recriar"] for r in registros if r["event"] == "coop_ordem_recriada"]
        assert recriadas == [[P4]], f"a fatia recriou além do P4: {recriadas}"
        assert bancada.vpad_de(P4) is not vpad_do_p4, "o P4 não renasceu no boneco 3"
        assert bancada.daemon._gamepad_device is vpad_do_p1 and vpad_do_p1.vivo, (
            "a R-04: o vpad do posto não se recria com o jogo na autoridade"
        )
        assert bancada.dono_do_vpad_do_p1() == P2
        assert bancada.o_jogo_ve() == {1: P2, 2: P1, 3: P4}


# ``CoopManager._numero_e_indice`` dizendo o ``player_index`` reprova as cinco

CARTA_DO_ROXO = 2
INDICE_DO_ROXO = 4


class _LeitorDoRoxo:
    """O ``EvdevReader`` do secundário: só o que o co-op pergunta ao registrar."""

    grab_state = "held"

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path

    def start(self) -> bool:
        return True

    def set_grab(self, _grab: bool) -> bool:
        return True

    def stop(self) -> None:
        pass


class _LeitorComGrabPendente(_LeitorDoRoxo):
    grab_state = "pending"


class _PadDoRoxo:
    """O pad virtual que a fábrica devolveria: ``uhid`` (espelho) ou ``uinput``."""

    def __init__(self, backend: str, *, caminho: str = "dualsense") -> None:
        self.backend = backend
        self.flavor = "dualsense"
        self.caminho = caminho
        self.mac = "02:fe:00:00:00:04"

    def stop(self) -> None:
        pass


class _EspelhoQueNaoAbre:
    """O ``PhysicalReportReader``: o co-op só o constrói e o liga."""

    def __init__(self, **_kw: Any) -> None:
        pass

    def start(self) -> None:
        pass


def _registro_com_o_roxo_na_carta_2() -> ControllerIdentityRegistry:
    """Os quatro na mesa, o P2 e o P3 saem, e o prazo passa: o roxo é a carta 2."""
    relogio, reg, _escritores, _daemon = _mesa_assentada(QUATRO)
    reg.sync_connected([P1, P4])
    relogio.avancar(PRAZO + 1.0)
    reg.sync_connected([P1, P4])
    assert reg.liberar_as_lampadas() is True
    assert reg.numero_da_lampada(P4, assign=False) == CARTA_DO_ROXO
    return reg


@pytest.fixture
def coop_do_roxo(config_isolado: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O ``CoopManager`` de produção com o registro de produção e o roxo a registrar."""
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    reg = _registro_com_o_roxo_na_carta_2()
    daemon = SimpleNamespace(
        config=DaemonConfig(coop_enabled=True, gamepad_emulation_enabled=True),
        controller=SimpleNamespace(primary_uniq=P1, hidraw_path=lambda _u: None),
        identity_registry=reg,
        display_authority="daemon",
        _gamepad_device=None,
        _coop_manager=None,
        store=None,
    )
    coop = CoopManager(daemon)  # type: ignore[arg-type]
    daemon._coop_manager = coop
    for indice in (2, 3):
        chave = f"path:/dev/input/event{20 + indice}"
        coop._players[chave] = _SecondaryPlayer(
            identity=chave, evdev_path=chave[5:], reader=_LeitorDoRoxo(), player_index=indice
        )
    monkeypatch.setattr(coop, "_prefetch_calibration", lambda _i: None)
    monkeypatch.setattr(coop, "_armar_sossego_do_launch_env", lambda _m: None)
    monkeypatch.setattr(coop, "_materialize_launch_env", lambda: None)
    monkeypatch.setattr(coop, "_broker_hide_player", lambda _p: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.physical_report_reader.PhysicalReportReader",
        _EspelhoQueNaoAbre,
    )
    return coop


def _linhas(registros: list[dict[str, Any]], evento: str) -> list[tuple[Any, Any]]:
    return [(r.get("player"), r.get("indice")) for r in registros if r["event"] == evento]


class _DiarioDoCoop:
    """O ``logger`` do co-op, anotando TODO nível: o ``calibracao_pendente`` é ``debug``."""

    def __init__(self) -> None:
        self.linhas: list[dict[str, Any]] = []

    def _anotar(self, evento: str, **campos: Any) -> None:
        self.linhas.append({"event": evento, **campos})

    debug = info = warning = _anotar


class TestODiarioDizACarta:
    def test_as_cinco_linhas_do_co_op(
        self, coop_do_roxo: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        coop = coop_do_roxo
        esperado = [(CARTA_DO_ROXO, INDICE_DO_ROXO)]
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorComGrabPendente
        )
        diario = _DiarioDoCoop()
        monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.coop.logger", diario)
        registros = diario.linhas
        coop._spawn_player(P4, "/dev/input/event40")
        roxo = coop._players[P4]
        assert roxo.player_index == INDICE_DO_ROXO, "a bancada não alocou o 4"
        monkeypatch.setattr(coop, "_calibration_pronta", lambda _i: (False, None))
        coop._promote_player(roxo)
        monkeypatch.setattr(coop, "_calibration_pronta", lambda _i: (True, None))
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_kw: _PadDoRoxo("uhid"),
        )
        coop._promote_player(roxo)
        coop.ceder_ao_primario(P1, P4)
        for evento in (
            "coop_player_grab_pending",
            "coop_player_calibracao_pendente",
            "coop_player_added",
            "coop_motion_reader_spawned",
            "coop_player_cedido_ao_primario",
        ):
            assert _linhas(registros, evento) == esperado, (
                f"{evento}: {_linhas(registros, evento)} — o diário tem de dizer "
                f"player={CARTA_DO_ROXO} (a carta) e indice={INDICE_DO_ROXO}"
            )

    def test_o_pad_degradado_tambem(
        self, coop_do_roxo: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        coop = coop_do_roxo
        monkeypatch.setattr(
            "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _LeitorDoRoxo
        )
        monkeypatch.setattr(coop, "_calibration_pronta", lambda _i: (True, None))
        monkeypatch.setattr(coop, "_pode_nascer_na_ordem", lambda _p: False)
        coop._spawn_player(P4, "/dev/input/event40")
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
            lambda *_a, **_kw: _PadDoRoxo("uinput"),
        )
        with structlog.testing.capture_logs() as registros:
            coop._promote_player(coop._players[P4])
        assert _linhas(registros, "vpad_degradado") == [(CARTA_DO_ROXO, INDICE_DO_ROXO)]

    def test_o_jogador_que_caiu_e_o_canal_sem_imu_dizem_a_carta(
        self, coop_do_roxo: Any
    ) -> None:
        from hefesto_dualsense4unix.daemon.launch_env import _jogadores_sem_imu
        from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import dedup_status

        coop = coop_do_roxo
        daemon = coop._daemon
        daemon.is_native_mode = lambda: False
        daemon._gamepad_device = _PadDoRoxo("uhid")
        coop._players[P4] = _SecondaryPlayer(
            identity=P4,
            evdev_path="/dev/input/event40",
            reader=_LeitorDoRoxo(),
            player_index=INDICE_DO_ROXO,
            vpad=_PadDoRoxo("uinput"),  # type: ignore[arg-type]
        )
        _ok, motivos = dedup_status(daemon)
        assert motivos == [f"jogador_{CARTA_DO_ROXO}_uinput"], motivos

        coop._players[P4].vpad = _PadDoRoxo("uinput", caminho="xbox")  # type: ignore[assignment]
        daemon._gamepad_device = _PadDoRoxo("uinput", caminho="xbox")
        assert _jogadores_sem_imu(daemon) == ["1", str(CARTA_DO_ROXO)]

    def test_o_canal_sem_imu_do_posto_diz_a_carta_de_quem_o_alimenta(
        self, coop_do_roxo: Any
    ) -> None:
        """O roxo cedido ao posto do P1 (o primário é ele): a lista do"""
        from hefesto_dualsense4unix.daemon.launch_env import _jogadores_sem_imu

        coop = coop_do_roxo
        daemon = coop._daemon
        daemon.controller.primary_uniq = P4
        daemon._gamepad_device = _PadDoRoxo("uinput", caminho="xbox")
        assert _jogadores_sem_imu(daemon) == [str(CARTA_DO_ROXO)]


PLAYER_IDS = {1: 0x04, 2: 0x0A, 3: 0x15, 4: 0x1B}


def _desenho(numero: int) -> tuple[bool, bool, bool, bool, bool]:
    valor = PLAYER_IDS[numero]
    return tuple(bool(valor >> i & 1) for i in range(5))  # type: ignore[return-value]


@pytest.mark.usefixtures("config_isolado")
class TestONumeroQueOJogoEscreveu:
    def test_a_cada_mudanca_e_de_novo_depois_da_sessao(self) -> None:
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
        from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
        from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

        _relogio, reg, _escritores, _daemon = _mesa_assentada((P1, P2))
        assert reg.numero_da_lampada(P2, assign=False) == 2, "a conta: o P2 é o segundo"
        inst = PyDualSenseController(evdev_reader=_null_evdev())
        inst._handles = {"AA:BB:CC:00:00:02": _FakeHandle()}  # type: ignore[assignment]
        inst._primary_key = "AA:BB:CC:00:00:02"
        daemon = SimpleNamespace(controller=inst, identity_registry=reg)

        def escreve(numero: int) -> list[dict[str, Any]]:
            with structlog.testing.capture_logs() as registros:
                gp.apply_game_player_leds(daemon, _desenho(numero), target_uniq=P2)
            return [r for r in registros if r["event"] == "o_numero_que_o_jogo_escreveu"]

        def par(linhas: list[dict[str, Any]]) -> list[tuple[Any, Any, Any]]:
            return [(r["jogo"], r["hefesto"], r["concorda"]) for r in linhas]

        primeira = escreve(1)
        assert par(primeira) == [(1, 2, False)], primeira
        assert par(escreve(1)) == [], "o mesmo número de novo não é mudança"
        assert par(escreve(2)) == [(2, 2, True)]
        gp.end_game_output_session(daemon, target_uniq=P2)
        assert par(escreve(2)) == [(2, 2, True)], "a sessão nova diz desde a primeira escrita"
        assert all(
            getattr(camada, "player_leds", None) is None
            for camadas in (
                inst._game_output_by_uniq,
                inst._desired_coop_by_uniq,
                inst._desired_by_uniq,
            )
            for camada in camadas.values()
        ), "o padrão do jogo virou camada no backend"
