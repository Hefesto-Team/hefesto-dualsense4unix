"""O relógio do lançamento não lê o disco no tique.

O-RELOGIO-DO-LANCAMENTO-NAO-LE-O-DISCO-NO-TIQUE-01. Medido em 07/11/2026 com `strace`: uma passada
do relógio `launch` abre o `last_run`, o `last_exit`, o `steam_input_apps.txt` e varre a pasta de
perfis com um `stat` por perfil, tudo no fio do laço. Com um desses leitores dormindo 2 s o tique
caía de 93 para 5,2 por segundo. O `_poll_loop` de produção roda aqui, com o escrevente armado
como o `ipc_server` arma: sem ele a materialização é inline e o laço para por outro motivo.

Mordidas (arranque a cura, veja reprovar, devolva):

- `arm_launch_profile`: leia `read_last_run_marker(base_dir)` mesmo com `folha`;
- `steam_input_exception_appid`: use `steam_input_appids()` e `launch_session_appid` com `folha`;
- `_o_selo_do_laco`: devolva sempre `selo_dos_perfis()`;
- `_foto_do_lancamento`: some a sessão ao `em_cena` com `_em_cena_com_a_sessao`, e o disco preso
  num leitor só reprova: a folha chega, o sossego vence e a foto lê a sessão no fio do laço;
- `CadernoDoLancamento._ler_sempre`: tire o `call_soon_threadsafe`, e o prazo do arme reprova;
- `_a_folha_mudou`: tire a guarda da parada;
- `_avisar_se_o_jogo_ja_congelou`: pergunte sempre a `launch_session_appid()`;
- `_a_parte_de_fora`: use `foto.em_cena` sem somar a sessão;
- `arm_launch_profile`: tire o `_a_folha_nao_viu_o_arme`, e dois lançamentos em 60 s fazem a folha
  velha rearmar o jogo de antes por cima do que o ping acabou de armar.
"""
from __future__ import annotations

import asyncio
import contextlib
import itertools
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from tests.unit import test_o_tique_tem_orcamento as orcamento

HZ = 120
APPID = 7070707
DORME_S = 0.25
PASSO_S = 0.002
PRAZO_S = 8.0
PERIODO_S = 0.2
SOSSEGO_S = 0.1
FASES_EM_TIQUES = (4, 17, 29)
LEITURAS_DE_CALMA = 6
TIQUES_MEDIDOS = 72
PARADA_MAXIMA_S = DORME_S * 0.75
IDADE_DO_JOGO_S = int(le.LAUNCH_ARM_WINDOW_SEC) + 60
LEITORES = (
    "read_last_run_marker",
    "read_last_run_pid",
    "read_last_exit_marker",
    "read_last_exit_pid",
    "steam_input_appids",
    "selo_dos_perfis",
)
MESAS = {
    "4 cabos": ("usb", "usb", "usb", "usb"),
    "3 cabos e 1 rádio": ("usb", "usb", "usb", "bt"),
    "2 e 2": ("usb", "bt", "usb", "bt"),
    "1 cabo e 3 rádios": ("bt", "bt", "usb", "bt"),
    "4 rádios": ("bt", "bt", "bt", "bt"),
    "1 só": ("usb",),
    "1 só no rádio": ("bt",),
}
MASCARAS = ("xbox360", "dualsense", "dualsense_edge", "dualshock4")


class _Espia:
    """Anota o que o fio vigiado faz de arquivo: `open`, varredura de pasta e `stat`."""

    def __init__(self) -> None:
        self.fio: int | None = None
        self.vistos: list[str] = []

    def auditar(self, evento: str, args: tuple[Any, ...]) -> None:
        if self.fio == threading.get_ident() and evento in {"open", "os.scandir", "os.listdir"}:
            self.vistos.append(f"{evento} {args[0] if args else ''}")

    def stat(self, caminho: Any, *a: Any, **k: Any) -> os.stat_result:
        if self.fio == threading.get_ident():
            self.vistos.append(f"stat {caminho}")
        return _STAT_DE_VERDADE(caminho, *a, **k)


_STAT_DE_VERDADE = os.stat
_ESPIA = _Espia()
sys.addaudithook(_ESPIA.auditar)


@pytest.fixture()
def casa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    """Os arquivos do lançamento num lar de mentira, e o laço sem a máquina."""
    base = tmp_path / "launch_env"
    perfis = tmp_path / "perfis"
    base.mkdir()
    perfis.mkdir()
    for numero in range(4):
        (perfis / f"p{numero}.json").write_text("{}", encoding="utf-8")
    allowlist = tmp_path / "steam_input_apps.txt"

    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: base)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.xdg_paths.profiles_dir", lambda *a, **k: perfis
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.steam_launch_options.steam_input_allowlist_path",
        lambda: allowlist,
    )
    monkeypatch.setattr(co.CoopManager, "sync", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_recolher_os_cedidos", lambda self: None)
    monkeypatch.setattr(co.CoopManager, "_promote_pending", lambda self: None)
    monkeypatch.setattr(lc, "reconciliar_as_mascaras", lambda daemon: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    monkeypatch.setattr(gp, "esconder_o_fisico_para_o_jogo", lambda d, **k: True)
    monkeypatch.setattr(gp, "_set_evdev_grab", lambda d, ligado: None)
    monkeypatch.setattr(gp, "rehide_physical_hidraw", lambda d: None)
    monkeypatch.setattr(lc, "INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr(os, "stat", _ESPIA.stat)
    return SimpleNamespace(base=base, perfis=perfis, allowlist=allowlist)


def _com_jogo(casa: SimpleNamespace, epoch: int | None = None) -> None:
    """O jogo da allowlist aberto: passou da janela do arme, segue na do jogo vivo."""
    quando = epoch if epoch is not None else int(time.time()) - IDADE_DO_JOGO_S
    (casa.base / "last_run").write_text(
        f"appid={APPID}\nepoch={quando}\npid={os.getpid()}\n", encoding="utf-8"
    )
    casa.allowlist.write_text(f"{APPID}\n", encoding="utf-8")


class _Daemon(orcamento._DaemonDeLaco):
    """O daemon de laço com o `_reconciliar_launch` DE VERDADE, parando por relógio."""

    def __init__(
        self,
        segundos: float,
        mascara: str = "xbox360",
        *,
        ate: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(tiques=10**9, poll_hz=HZ)
        self.ate = time.perf_counter() + segundos
        self.pronto = ate
        self.estourou = False
        self.display_authority = "unknown"
        self.config.gamepad_emulation_enabled = True
        self.config.gamepad_flavor = mascara

    def _is_stopping(self) -> bool:
        self.inicio_do_tique = time.perf_counter()
        self.numero_do_tique += 1
        if self.pronto is not None and self.pronto():
            return True
        self.estourou = time.perf_counter() >= self.ate
        return self.estourou

    def is_native_mode(self) -> bool:
        return self._native_mode

    async def rodar(self) -> None:
        laco = asyncio.get_running_loop()

        def devolver(acao: Callable[[], None]) -> None:
            with contextlib.suppress(RuntimeError):
                laco.call_soon_threadsafe(acao)

        escrevente = le.armar_o_escrevente(devolver, laco)
        try:
            await super().rodar()
        finally:
            self.fim = time.perf_counter()
            if escrevente is not None:
                await asyncio.to_thread(le.desarmar_o_escrevente, escrevente)


def _dormindo(monkeypatch: pytest.MonkeyPatch, *nomes: str) -> None:
    for nome in nomes:
        original = getattr(le, nome)

        def lento(*a: Any, _f: Callable[..., Any] = original, **k: Any) -> Any:
            time.sleep(DORME_S)
            return _f(*a, **k)

        monkeypatch.setattr(le, nome, lento)


def _esperar(pronto: Callable[[], bool], prazo_s: float = PRAZO_S) -> bool:
    fim = time.monotonic() + prazo_s
    while not pronto():
        if time.monotonic() >= fim:
            return False
        time.sleep(PASSO_S)
    return True


async def _esperar_no_laco(pronto: Callable[[], bool], prazo_s: float = PRAZO_S) -> bool:
    fim = time.monotonic() + prazo_s
    while not pronto():
        if time.monotonic() >= fim:
            return False
        await asyncio.sleep(PASSO_S)
    return True


@pytest.fixture()
def relogio_curto(monkeypatch: pytest.MonkeyPatch) -> float:
    """O relógio `launch` num período menor e o sossego mais curto: as esperas escalam com eles."""
    monkeypatch.setattr(gp, "LAUNCH_RECONCILE_INTERVAL_SEC", PERIODO_S)
    monkeypatch.setattr(
        lc,
        "RELOGIOS_LENTOS",
        tuple(
            (nome, PERIODO_S if nome == "launch" else periodo, fase)
            for nome, periodo, fase in lc.RELOGIOS_LENTOS
        ),
    )
    monkeypatch.setattr(le, "JANELA_DE_SOSSEGO_SEC", SOSSEGO_S)
    return PERIODO_S


def _pior_buraco(daemon: _Daemon) -> float:
    """O maior vão sem entrada, contando o fim: parada que atravessa o fim também é parada."""
    instantes = [*sorted(daemon.despachos.values()), daemon.fim]
    return max((b - a for a, b in itertools.pairwise(instantes)), default=0.0)


@pytest.mark.parametrize("jogo", [False, True], ids=["sem jogo", "com jogo"])
def test_o_tique_nao_cai_com_o_disco_preso(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, jogo: bool
) -> None:
    """Todo leitor dormindo: antes da cura o tique despencava; depois, fica perto de 100."""
    if jogo:
        _com_jogo(casa)
    _dormindo(monkeypatch, *LEITORES)
    daemon = _Daemon(PRAZO_S, ate=lambda: len(daemon.despachos) >= TIQUES_MEDIDOS)
    inicio = time.perf_counter()

    asyncio.run(daemon.rodar())

    assert not daemon.estourou, f"{TIQUES_MEDIDOS} tiques não vieram em {PRAZO_S} s"
    por_segundo = len(daemon.despachos) / (daemon.fim - inicio)
    assert por_segundo > 40, f"o tique caiu a {por_segundo:.1f} por segundo"
    assert _pior_buraco(daemon) < PARADA_MAXIMA_S, f"o laço parou {_pior_buraco(daemon):.2f} s"


@pytest.mark.parametrize("leitor", ["read_last_run_marker", "read_last_exit_marker"])
def test_um_leitor_preso_nao_para_o_laco_na_rematerializacao(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, relogio_curto: float, leitor: str
) -> None:
    """Só um leitor preso: a folha chega e o sossego vence, com a foto ainda fora do disco."""
    _com_jogo(casa)
    _dormindo(monkeypatch, leitor)
    fotos: list[float] = []
    tirar = le._foto_do_lancamento

    def contar(*a: Any, **k: Any) -> Any:
        fotos.append(time.perf_counter())
        return tirar(*a, **k)

    monkeypatch.setattr(le, "_foto_do_lancamento", contar)
    daemon = _Daemon(
        PRAZO_S, ate=lambda: bool(fotos) and time.perf_counter() - fotos[0] > DORME_S
    )
    inicio = time.perf_counter()

    asyncio.run(daemon.rodar())

    assert fotos and not daemon.estourou, "o sossego não venceu: a régua não mediu nada"
    assert daemon.fim - fotos[0] > DORME_S / 2, "a foto caiu perto demais do fim da corrida"
    assert len(daemon.despachos) / (daemon.fim - inicio) > 40
    assert _pior_buraco(daemon) < PARADA_MAXIMA_S, f"o laço parou {_pior_buraco(daemon):.2f} s"


def test_a_foto_nao_le_a_sessao_e_a_escrita_sim(casa: SimpleNamespace) -> None:
    """A foto, no laço, sabe só o foco; a sessão vem da parte de fora, sem atraso nenhum."""
    _com_jogo(casa)
    daemon = SimpleNamespace(
        store=SimpleNamespace(window_detect_current_class="steam_app_9900020")
    )

    em_cena = le._em_cena_de_memoria(daemon)

    assert em_cena == frozenset({9900020})
    assert le._em_cena_com_a_sessao(em_cena) == {9900020, APPID}


def _sentar(daemon: _Daemon, transportes: tuple[str, ...], mascara: str) -> None:
    """A mesa de verdade para o `_snapshot`: um físico e um pad virtual por jogador."""
    daemon._gamepad_device.backend = "uinput"
    daemon._gamepad_device.flavor = mascara
    daemon._coop_manager._pares_de_fora = {}
    daemon._coop_manager._players = {
        uniq: SimpleNamespace(
            vpad=SimpleNamespace(backend="uinput", flavor=mascara), externo=False
        )
        for uniq in (f"aa:bb:cc:00:00:{numero:02x}" for numero in range(1, len(transportes)))
    }
    daemon.controller.describe_controllers = lambda: [
        {"connected": True, "transport": transporte} for transporte in transportes
    ]


async def _o_que_a_passada_toca(daemon: _Daemon) -> list[str]:
    """Os arquivos de UMA passada do relógio em regime, no fio do laço."""
    gp._reconciliar_launch(daemon)
    caderno = daemon._caderno_do_lancamento
    prazo = time.monotonic() + 5.0
    while caderno.folha() is None and time.monotonic() < prazo:
        await asyncio.sleep(PASSO_S)
    await asyncio.sleep(0)
    daemon._launch_env_sossego_em = None
    daemon._launch_env_assinatura = le._assinatura_da_mesa(daemon)
    _ESPIA.vistos = []
    _ESPIA.fio = threading.get_ident()
    try:
        gp._reconciliar_launch(daemon)
    finally:
        _ESPIA.fio = None
    return _ESPIA.vistos


@pytest.mark.parametrize("mesa", MESAS, ids=list(MESAS))
@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.parametrize("jogo", [False, True], ids=["sem jogo", "com jogo"])
def test_a_passada_do_relogio_nao_toca_arquivo_no_fio_do_laco(
    casa: SimpleNamespace, mesa: str, mascara: str, jogo: bool
) -> None:
    """P1 a P4, toda mesa e toda máscara: nenhum `open`, varredura ou `stat` no fio do laço."""
    if jogo:
        _com_jogo(casa)
    daemon = _Daemon(0.0, mascara)
    transportes = MESAS[mesa]
    _sentar(daemon, transportes, mascara)

    assert asyncio.run(_o_que_a_passada_toca(daemon)) == []

    _nativo, _ligado, vestida, backends, fisicos = le._snapshot(daemon)
    assert vestida == mascara
    assert fisicos == len(backends) == len(transportes), "a mesa não chegou ao `_snapshot`"


@pytest.mark.parametrize(
    ("nativo", "emulando"), [(True, False), (False, False)], ids=["nativo", "mouse e teclado"]
)
@pytest.mark.parametrize("jogo", [False, True], ids=["sem jogo", "com jogo"])
def test_a_passada_nao_toca_arquivo_fora_do_modo_pad(
    casa: SimpleNamespace, nativo: bool, emulando: bool, jogo: bool
) -> None:
    """Sem pad virtual o relógio segue o mesmo: nativo e mouse e teclado, sem disco no laço."""
    if jogo:
        _com_jogo(casa)
    daemon = _Daemon(0.0)
    daemon._native_mode = nativo
    daemon.config.gamepad_emulation_enabled = emulando
    daemon._gamepad_device = None

    assert asyncio.run(_o_que_a_passada_toca(daemon)) == []


@pytest.mark.parametrize("anterior", [APPID, APPID + 1], ids=["o mesmo jogo", "outro jogo"])
def test_a_folha_velha_nao_rearma_o_jogo_de_antes(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, anterior: int
) -> None:
    """Dois lançamentos em 60 s: o ping arma o novo pelo disco, e a folha atrasada não o desfaz."""
    armados: list[tuple[int, int]] = []

    def armar(_d: Any, appid: int, epoch: int, _base: Any) -> dict[str, Any]:
        armados.append((appid, epoch))
        return {"armado": True}

    monkeypatch.setattr(le, "_armar_o_jogo", armar)
    epoch = int(time.time())
    antes = (anterior, epoch - 30)
    novo = (APPID, epoch)
    daemon = _Daemon(0.0)

    def gravar(marca: tuple[int, int]) -> None:
        (casa.base / "last_run").write_text(
            f"appid={marca[0]}\nepoch={marca[1]}\npid={os.getpid()}\n", encoding="utf-8"
        )

    async def corpo() -> None:
        gravar(antes)
        caderno = le.CadernoDoLancamento(asyncio.get_running_loop(), lambda: None, 60.0)
        daemon._caderno_do_lancamento = caderno
        while caderno.folha() is None:
            await asyncio.sleep(PASSO_S)
        gp._reconciliar_launch(daemon)
        gravar(novo)
        le.arm_launch_profile(daemon)
        gp._reconciliar_launch(daemon)
        caderno._folha = le.ler_a_folha()
        gp._reconciliar_launch(daemon)

    asyncio.run(corpo())

    assert armados == [antes, novo]
    assert daemon._launch_armed_for == novo


def test_o_lancamento_novo_arma_no_prazo_de_hoje(
    casa: SimpleNamespace, relogio_curto: float
) -> None:
    """O marker gravado arma em até um período do relógio, como o tique que lia o disco."""
    feito = threading.Event()
    daemon = _Daemon(PRAZO_S, ate=feito.is_set)
    prazos: list[float] = []

    def lancar() -> None:
        try:
            _esperar(lambda: getattr(daemon, "_caderno_do_lancamento", None) is not None)
            caderno = daemon._caderno_do_lancamento
            _esperar(lambda: caderno.folha() is not None)
            for numero, fase in enumerate(FASES_EM_TIQUES):
                alvo = daemon.numero_do_tique + fase
                _esperar(lambda alvo=alvo: daemon.numero_do_tique >= alvo)
                epoch = int(time.time())
                marca = (APPID + numero, epoch)
                t0 = time.perf_counter()
                (casa.base / "last_run").write_text(
                    f"appid={marca[0]}\nepoch={epoch}\npid={os.getpid()}\n", encoding="utf-8"
                )
                _esperar(lambda marca=marca: daemon._launch_armed_for == marca, 3.0)
                prazos.append(time.perf_counter() - t0)
        finally:
            feito.set()

    daemon._launch_armed_for = None
    fio = threading.Thread(target=lancar, daemon=True)
    fio.start()
    asyncio.run(daemon.rodar())
    fio.join(1.0)

    assert not daemon.estourou, f"os três lançamentos não armaram em {PRAZO_S} s"
    assert len(prazos) == 3
    assert max(prazos) < relogio_curto * 1.3, f"o arme demorou {max(prazos):.2f} s"


def test_o_disco_preso_atrasa_o_arme_e_nao_a_entrada(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leitura presa espera sozinha: a entrada anda, e o arme chega depois da volta."""
    epoch = int(time.time())
    (casa.base / "last_run").write_text(
        f"appid={APPID}\nepoch={epoch}\npid={os.getpid()}\n", encoding="utf-8"
    )
    _dormindo(monkeypatch, "read_last_run_marker")
    daemon = _Daemon(
        PRAZO_S,
        ate=lambda: getattr(daemon, "_launch_armed_for", None) == (APPID, epoch)
        and len(daemon.despachos) >= TIQUES_MEDIDOS,
    )
    inicio = time.perf_counter()

    asyncio.run(daemon.rodar())

    assert not daemon.estourou, "o arme não chegou depois da volta da leitura presa"
    assert daemon._launch_armed_for == (APPID, epoch)
    assert len(daemon.despachos) / (daemon.fim - inicio) > 40
    assert _pior_buraco(daemon) < PARADA_MAXIMA_S


def test_a_saida_do_jogo_da_allowlist_devolve_o_fisico_no_prazo(
    casa: SimpleNamespace, relogio_curto: float
) -> None:
    """O `last_exit` entra pela folha: a exceção do Steam Input liga e desliga sem disco."""
    _com_jogo(casa)
    feito = threading.Event()
    daemon = _Daemon(PRAZO_S, ate=feito.is_set)
    vistos: list[bool] = []

    def sair() -> None:
        try:
            vistos.append(_esperar(lambda: gp.steam_input_excecao_ativa(daemon)))
            (casa.base / "last_exit").write_text(
                f"epoch={int(time.time())}\npid={os.getpid()}\n", encoding="utf-8"
            )
            vistos.append(_esperar(lambda: not gp.steam_input_excecao_ativa(daemon)))
        finally:
            feito.set()

    fio = threading.Thread(target=sair, daemon=True)
    fio.start()
    asyncio.run(daemon.rodar())
    fio.join(1.0)

    assert vistos == [True, True], "a exceção não ligou, ou não desligou, no prazo"


def test_o_perfil_novo_ainda_chega_ao_vigia(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, relogio_curto: float
) -> None:
    """Um perfil que nasce fora da janela muda o selo da folha, e o vigia arma o sossego."""
    daemon = _Daemon(PRAZO_S)
    vistos: list[Any] = []
    passadas: list[float] = []
    vigiar = le.vigiar_a_mesa

    def contar(*a: Any, **k: Any) -> Any:
        passadas.append(time.perf_counter())
        return vigiar(*a, **k)

    monkeypatch.setattr(le, "vigiar_a_mesa", contar)

    async def corpo() -> None:
        tarefa = asyncio.create_task(daemon.rodar())
        assentou = await _esperar_no_laco(lambda: len(passadas) >= 1)
        daemon._launch_env_sossego_em = None
        daemon._launch_env_assinatura = le._assinatura_da_mesa(daemon)
        base = len(passadas)
        calmo = await _esperar_no_laco(lambda: len(passadas) >= base + 2)
        vistos.append(daemon._launch_env_sossego_em)
        (casa.perfis / "novo.json").write_text("{}", encoding="utf-8")
        chegou = await _esperar_no_laco(lambda: daemon._launch_env_sossego_em is not None)
        vistos.append(daemon._launch_env_sossego_em)
        daemon.ate = 0.0
        await tarefa
        assert assentou and calmo and chegou, "o vigia não andou no prazo"

    asyncio.run(corpo())

    assert vistos[0] is None, "o vigia acusou mudança sem a pasta mudar"
    assert vistos[1] is not None, "o perfil novo não chegou ao vigia"


def test_o_vigia_e_o_recibo_leem_a_mesma_conta(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No laço com caderno, a assinatura sai da folha: nem o recibo vai ao disco."""
    monkeypatch.setattr(le, "selo_dos_perfis", le.selo_dos_perfis)
    daemon = _Daemon(0.0)

    async def corpo() -> tuple[Any, Any]:
        caderno = le.CadernoDoLancamento(asyncio.get_running_loop(), lambda: None, 0.05)
        daemon._caderno_do_lancamento = caderno
        while caderno.folha() is None:
            await asyncio.sleep(PASSO_S)
        folha = caderno.folha()
        monkeypatch.setattr(le, "selo_dos_perfis", lambda: pytest.fail("disco no laço"))
        return folha, le._assinatura_da_mesa(daemon)

    folha, assinatura = asyncio.run(corpo())

    assert folha.selo in assinatura


def test_fora_do_laco_a_conta_vai_ao_disco(casa: SimpleNamespace) -> None:
    """A folha é do fio do laço: outro fio, como o do escrevente, nunca recebe a atrasada."""
    daemon = _Daemon(0.0)

    async def corpo() -> tuple[Any, Any]:
        caderno = le.CadernoDoLancamento(asyncio.get_running_loop(), lambda: None, 60.0)
        daemon._caderno_do_lancamento = caderno
        while caderno.folha() is None:
            await asyncio.sleep(PASSO_S)
        return le._a_folha_pronta(daemon), await asyncio.to_thread(le._a_folha_pronta, daemon)

    no_laco, em_outro_fio = asyncio.run(corpo())

    assert no_laco is not None
    assert em_outro_fio is None


@pytest.mark.parametrize(
    ("pid_da_saida", "jogo_vivo"),
    [(os.getpid(), False), (os.getpid() + 1, True)],
    ids=["a saída é deste lançamento", "a saída é de outro lançamento"],
)
def test_a_folha_responde_a_sessao_como_o_disco(
    casa: SimpleNamespace, pid_da_saida: int, jogo_vivo: bool
) -> None:
    """O `last_exit` só encerra o lançamento dele: a folha carrega o pid da saída."""
    _com_jogo(casa)
    (casa.base / "last_exit").write_text(
        f"epoch={int(time.time())}\npid={pid_da_saida}\n", encoding="utf-8"
    )

    pela_folha = le._sessao_da_folha(le.ler_a_folha(), None)

    assert pela_folha == le.launch_session_appid()
    assert (pela_folha == APPID) is jogo_vivo


def test_o_aviso_do_jogo_congelado_nao_le_a_sessao_no_laco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cobertura muda com o jogo de pé: o aviso pergunta à folha, nunca ao disco."""
    _com_jogo(casa)
    daemon = _Daemon(0.0)
    avisos: list[Any] = []
    monkeypatch.setattr(le.logger, "warning", lambda evento, **k: avisos.append((evento, k)))

    async def corpo() -> None:
        caderno = le.CadernoDoLancamento(asyncio.get_running_loop(), lambda: None, 60.0)
        daemon._caderno_do_lancamento = caderno
        while caderno.folha() is None:
            await asyncio.sleep(PASSO_S)
        monkeypatch.setattr(
            le, "launch_session_appid", lambda **k: pytest.fail("a sessão foi ao disco")
        )
        antes = (False, True, "xbox360", ("uinput",), 2, False, (), ())
        depois = (False, True, "xbox360", ("uinput", "uinput"), 2, False, (), ())
        le._avisar_se_o_jogo_ja_congelou(daemon, antes, depois)

    asyncio.run(corpo())

    assert [evento for evento, _ in avisos] == ["launch_env_mudou_depois_do_exec"]
    assert avisos[0][1]["appid"] == APPID


def test_a_escrita_soma_a_sessao_que_a_foto_nao_leu(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O jogo do wrapper, fora do foco, segue em cena na divergência que se publica."""
    _com_jogo(casa)
    somadas: list[set[int]] = []
    somar = le._em_cena_com_a_sessao

    def anotar(*a: Any, **k: Any) -> set[int]:
        somadas.append(somar(*a, **k))
        raise OSError("a régua para aqui")

    monkeypatch.setattr(le, "_em_cena_com_a_sessao", anotar)
    foto = le._foto_do_lancamento(_Daemon(0.0), no_fio=True, com_as_vozes=False)

    with pytest.raises(OSError, match="a régua para aqui"):
        le._a_parte_de_fora(foto, lambda acao: None)

    assert somadas == [{APPID}]


def test_o_caderno_so_chama_quando_a_folha_muda(casa: SimpleNamespace) -> None:
    """Leitura igual não acorda o laço; leitura nova acorda uma vez."""
    chamadas: list[Any] = []

    async def corpo() -> tuple[int, int]:
        caderno = le.CadernoDoLancamento(
            asyncio.get_running_loop(), lambda: chamadas.append(caderno.folha()), 0.02
        )
        lidas = []
        ler = le.ler_a_folha

        def contar() -> Any:
            lidas.append(1)
            return ler()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(le, "ler_a_folha", contar)
            assert await _esperar_no_laco(lambda: len(lidas) >= LEITURAS_DE_CALMA)
            antes = len(chamadas)
            _com_jogo(casa)
            base = len(lidas)
            assert await _esperar_no_laco(
                lambda: chamadas[-1].marker is not None and len(lidas) >= base + LEITURAS_DE_CALMA
            )
        return antes, len(chamadas)

    antes, depois = asyncio.run(corpo())

    assert antes == 1
    assert depois in {2, 3}, "o marker e a allowlist podem cair em uma ou duas leituras"
    assert chamadas[-1].marker is not None


def test_o_fio_do_caderno_acaba_com_o_laco(casa: SimpleNamespace) -> None:
    """Laço fechado, fio morto: nada fica lendo o disco de um serviço que parou."""

    async def corpo() -> le.CadernoDoLancamento:
        caderno = le.CadernoDoLancamento(asyncio.get_running_loop(), lambda: None, 0.02)
        assert await _esperar_no_laco(lambda: caderno.folha() is not None)
        return caderno

    caderno = asyncio.run(corpo())
    caderno._fio.join(2.0)

    assert not caderno._fio.is_alive()


def test_o_ping_do_wrapper_le_o_marker_fresco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem `folha`, o arme lê o disco: o ping chega antes de o caderno ver o marker novo."""
    monkeypatch.setattr(le, "_armar_o_jogo", lambda *a, **k: {"armado": True})
    daemon = _Daemon(0.0)
    folha_velha = le.ler_a_folha()
    epoch = int(time.time())
    (casa.base / "last_run").write_text(
        f"appid={APPID}\nepoch={epoch}\npid={os.getpid()}\n", encoding="utf-8"
    )

    assert le.arm_launch_profile(daemon, folha=folha_velha, now=epoch + 1.0) is None
    assert le.arm_launch_profile(daemon, now=epoch + 1.0) == {"armado": True}


def test_a_folha_em_branco_nao_arma_nem_acusa_mudanca(casa: SimpleNamespace) -> None:
    """Antes da primeira leitura nada vai ao disco, e a mesa não se compara com o vazio."""
    daemon = _Daemon(0.0)
    daemon._launch_env_assinatura = "a de antes"
    feitos: list[str] = []
    bloqueio = threading.Event()

    def preso() -> le.FolhaDoLancamento:
        bloqueio.wait(3.0)
        return le.FOLHA_EM_BRANCO

    async def corpo() -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(le, "ler_a_folha", preso)
            mp.setattr(le, "tique_da_escada", lambda d: feitos.append("memória"))

            def exceção(_d: Any, *, folha: Any) -> None:
                feitos.append("exceção" if folha is le.FOLHA_EM_BRANCO else "folha lida")

            mp.setattr(gp, "sync_steam_input_exception", exceção)
            gp._reconciliar_launch(daemon)
            bloqueio.set()

    asyncio.run(corpo())

    assert feitos == ["memória", "exceção"]
    assert daemon._launch_env_assinatura == "a de antes"
    assert getattr(daemon, "_launch_env_sossego_em", None) is None


def test_o_fio_que_morre_ganha_outro_caderno(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um defeito que mate o fio não deixa o lançamento cego: o relógio abre outro caderno."""
    daemon = _Daemon(0.0)
    monkeypatch.setattr(threading, "excepthook", lambda _args: None)
    ler = le.ler_a_folha

    def quebrada() -> le.FolhaDoLancamento:
        raise OSError("defeito no leitor")

    async def corpo() -> tuple[bool, le.FolhaDoLancamento | None]:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(le, "ler_a_folha", quebrada)
            gp._reconciliar_launch(daemon)
            morto = daemon._caderno_do_lancamento
            morto._fio.join(2.0)
        assert not morto.vivo()
        gp._reconciliar_launch(daemon)
        novo = daemon._caderno_do_lancamento
        prazo = time.monotonic() + 5.0
        while novo.folha() is None and time.monotonic() < prazo:
            await asyncio.sleep(PASSO_S)
        return novo is not morto, novo.folha()

    trocou, folha = asyncio.run(corpo())

    assert trocou
    assert folha == ler()


def test_o_caderno_novo_herda_a_folha_do_que_morreu(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Jogo da allowlist aberto e fio morto: a exceção do Steam Input não cai por um vão."""
    _com_jogo(casa)
    daemon = _Daemon(0.0)
    monkeypatch.setattr(threading, "excepthook", lambda _args: None)

    def quebrada() -> le.FolhaDoLancamento:
        raise OSError("defeito no leitor")

    async def corpo() -> tuple[Any, Any]:
        def pedir() -> Any:
            return le.a_folha_do_relogio(daemon, lambda: None, 0.02)

        pedir()
        primeiro = daemon._caderno_do_lancamento
        while primeiro.folha() is None:
            await asyncio.sleep(PASSO_S)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(le, "ler_a_folha", quebrada)
            primeiro._fio.join(2.0)
            assert not primeiro.vivo()
            return primeiro.folha(), pedir()

    antes, herdada = asyncio.run(corpo())

    assert antes is not None
    assert herdada is antes


def test_a_folha_que_chega_depois_da_parada_nao_reconcilia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O serviço parando não arma jogo nenhum."""
    chamadas: list[Any] = []
    monkeypatch.setattr(gp, "_reconciliar_launch", chamadas.append)
    parada = threading.Event()
    daemon = SimpleNamespace(_stop_event=parada)

    gp._a_folha_mudou(daemon)  # type: ignore[arg-type]
    parada.set()
    gp._a_folha_mudou(daemon)  # type: ignore[arg-type]

    assert chamadas == [daemon]


@pytest.fixture(autouse=True)
def _espia_desligada() -> Iterator[None]:
    yield
    _ESPIA.fio = None
