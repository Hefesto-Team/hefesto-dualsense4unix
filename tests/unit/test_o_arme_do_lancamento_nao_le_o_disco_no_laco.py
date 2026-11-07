"""O arme do lançamento não lê o disco no laço.

O-ARME-DO-LANCAMENTO-NAO-LE-O-DISCO-NO-LACO-01. Medido em 07/11/2026, com o caderno e o escrevente
de produção: a borda do arme tocava 21 arquivos no fio do laço (a allowlist, a roupa, a pasta de
perfis, o perfil de novo na ativação, o `maquina.json`, o `session.json`, o `dono-do-p1` e a
escrita do `ultimo_jogo.json`), e 582 com a autoridade `game` (a varredura do `/proc`). O ping e
o ambiente do wrapper armavam no laço sem folha nenhuma, e o ambiente lia os perfis mais duas vezes.

O `Daemon` aqui é o de verdade, com a borda do aparelho dublada pela régua da
O-JOGO-SEGUINTE-VESTE-A-PROPRIA-ROUPA-01. Duas coisas ficam fora da conta: o import preguiçoso do
Python, que abre o `.pyc` uma vez por processo, e o `volume` do microfone do perfil, que roda o
`pactl` em `Daemon.apply_profile_mic` em toda ativação, a do `AutoSwitcher` inclusive: é processo
de fora, não leitura do arme.

Mordidas (arranque a cura, veja reprovar, devolva):

- `_armar_o_jogo`: `steam_input_appids()` em vez de `leitura.na_allowlist`;
- `_armar_o_jogo`: `roupa_gravada(appid, None, lido_ate=epoch)` em vez de `leitura.roupa`;
- `_armar_o_jogo`: `_steam_profiles(daemon)` em vez de `leitura.perfil`;
- `arm_launch_profile`: `_ativar` sem o `ja_lido`, e o perfil volta a ser lido na ativação;
- `ProfileManager._ativar`: `lembrar_o_ultimo_jogo` direto;
- `Daemon._perfil_do_arranjo`: tire a leitura do arme;
- `lembrar_o_dono_do_p1`: tire o `_DONO_GRAVADO`;
- `_a_autoridade_e_do_proprio_jogo`: chame `_ha_outro_jogo_vivo`;
- `ambiente_do_lancamento`: `no_fio=False` com a folha;
- `_jogos_do_comum`: use sempre `steam_input_appids()`;
- `_agendar_arming_do_launch`: não passe a folha ao `o_ambiente_no_status`;
- `_armar_launch`: chame o arme sem a folha;
- `a_folha_com_o_arme`: tire a memória, e a roupa volta a cada passada do caderno;
- `_o_que_o_arme_leu`: tire `com_as_bandeiras_lidas`, e o desktop e o Nativo gravam no laço;
- `_o_que_o_arme_leu`: tire `com_o_computador_lido`, e o `maquina.json` volta ao laço;
- `_vista_do_point_and_click`: `load_profile(nome)` direto;
- `_escrever_a_bandeira`: tire o `lidas.textos[nome] = texto`, e quem lê depois vê a de antes;
- `_folha_do_pedido`: tire o `try`, e a folha que levanta derruba o `daemon.status`;
- `_gravar_fora_do_laco`: `FIO_DO_PERFIL.submit(gravar)` sempre.
"""
from __future__ import annotations

import ast
import asyncio
import json
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
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import (
    FIO_DO_PERFIL,
    ProfileManager,
    ligar_o_freestyle,
)
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit import test_o_relogio_do_lancamento_nao_le_o_disco_no_tique as relogio
from tests.unit.test_o_jogo_seguinte_veste_a_propria_roupa import (  # noqa: F401
    COMUM,
    EDGE,
    EPOCH_A,
    JOGO_A,
    JOGO_B,
    _hermetico,
    _Mesa,
    _perfil,
)

casa_do_relogio = relogio.casa
_RAIZ = Path(__file__).resolve().parents[2]
_MATERIALIZAR = le.materialize_launch_env
_ALLOWLIST = le.steam_input_appids
_STAT = os.stat
_EVENTOS = {"open", "os.scandir", "os.listdir", "os.mkdir", "os.rename", "os.remove"}
_ROTAS = ("tique", "ping", "status do wrapper")
_XBOX: dict[str, Any] = {"kind": "gamepad", "gamepad_flavor": "xbox", "caminho": "xbox"}
_MODOS: dict[str, dict[str, Any] | None] = {
    "DualSense": {"kind": "gamepad", "gamepad_flavor": "dualsense"},
    "Xbox": _XBOX,
    "Nintendo": {"kind": "gamepad", "gamepad_flavor": "nintendo"},
    "Nativo": {"kind": "native"},
    "desktop": {"kind": "desktop"},
    "Navegação": {"kind": "desktop", "arranjo": "navegacao"},
    "Point and click": {"kind": "desktop", "arranjo": "point_and_click"},
    "sem modo": None,
}
_MESAS = {
    "1 no cabo": ("usb", 0),
    "1 no rádio": ("bt", 0),
    "4 no cabo": ("usb", 3),
    "4 no rádio": ("bt", 3),
}


class _Espia:
    """O que o fio vigiado faz de arquivo, fora do `.pyc` do import preguiçoso."""

    def __init__(self) -> None:
        self.fio: int | None = None
        self.vistos: list[str] = []

    def auditar(self, evento: str, args: tuple[Any, ...]) -> None:
        if self.fio == threading.get_ident() and evento in _EVENTOS:
            caminho = str(args[0]) if args else ""
            if not caminho.endswith((".py", ".pyc")) and "__pycache__" not in caminho:
                self.vistos.append(f"{evento} {caminho}")

    def stat(self, caminho: Any, *a: Any, **k: Any) -> os.stat_result:
        if self.fio == threading.get_ident() and "__pycache__" not in str(caminho):
            self.vistos.append(f"stat {caminho}")
        return _STAT(caminho, *a, **k)


_ESPIA = _Espia()
sys.addaudithook(_ESPIA.auditar)


def _levanta(*_a: Any, **_k: Any) -> Any:
    raise OSError("sem disco")


@pytest.fixture(autouse=True)
def _espia_desligada() -> Iterator[None]:
    yield
    _ESPIA.fio = None


@pytest.fixture()
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """O disco do lançamento em tmp, com a escrita e a allowlist de produção."""
    perfis = tmp_path / "perfis"
    perfis.mkdir()
    allowlist = tmp_path / "steam_input_apps.txt"
    monkeypatch.setattr(xdg_paths, "profiles_dir", lambda ensure=False: perfis)
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: perfis)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.steam_launch_options.steam_input_allowlist_path",
        lambda: allowlist,
    )
    monkeypatch.setattr(le, "materialize_launch_env", _MATERIALIZAR)
    monkeypatch.setattr(le, "steam_input_appids", _ALLOWLIST)
    return SimpleNamespace(pasta=tmp_path, perfis=perfis, allowlist=allowlist)


def _perfil_denso(
    casa: SimpleNamespace, modo: dict[str, Any] | None = _XBOX, **campos: Any
) -> None:
    """O perfil de fábrica inteiro, com o jogo no `match`, o `modo` dado e os `campos`."""
    dados = json.loads(
        (_RAIZ / "assets" / "profiles_default" / "freestyle.json").read_text(encoding="utf-8"))
    dados["name"] = "Denso"
    dados["match"] = {"type": "criteria", "window_class": [f"steam_app_{JOGO_A}"]}
    dados["mode"] = modo
    dados["mic"].pop("volume")
    (casa.perfis / "denso.json").write_text(json.dumps({**dados, **campos}), encoding="utf-8")


def _lancar(casa: SimpleNamespace) -> tuple[int, int]:
    """O `.env` do jogo, gravado antes do `exec`, com a roupa do comum, e o `last_run` dele."""
    do_jogo = casa.pasta / f"steam_app_{JOGO_A}.env"
    do_jogo.write_text("# roupa: 0ce6 (comum)\nA=1\n", encoding="utf-8")
    gravado_em = time.time() - 3600
    os.utime(do_jogo, (gravado_em, gravado_em))
    marca = (JOGO_A, int(time.time()))
    (casa.pasta / "last_run").write_text(
        f"appid={marca[0]}\nepoch={marca[1]}\npid={os.getpid()}\n", encoding="utf-8")
    return marca


def _servidor(mesa: _Mesa, casa: SimpleNamespace) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

    servidor = IpcServer(
        controller=mesa.d.controller, store=mesa.d.store,
        profile_manager=ProfileManager(controller=mesa.d.controller, store=mesa.d.store),
        socket_path=casa.pasta / "arme.sock", daemon=mesa.d,
    )
    mesa.d._ipc_server = servidor
    return servidor


async def _o_arme_em_producao(
    mesa: _Mesa, casa: SimpleNamespace, rota: str, *, antes: Callable[[], None] = lambda: None,
) -> list[str]:
    """O arme pela `rota`, com o caderno e o escrevente de produção; o que o fio do laço tocou."""
    laco = asyncio.get_running_loop()

    def devolver(acao: Callable[[], None]) -> None:
        laco.call_soon_threadsafe(acao)

    escrevente = le.armar_o_escrevente(devolver, laco)
    servidor = _servidor(mesa, casa)
    try:
        caderno = le.CadernoDoLancamento(laco, lambda: None, 60.0, daemon=mesa.d)
        mesa.d._caderno_do_lancamento = caderno
        while caderno.folha() is None:
            await asyncio.sleep(0.005)
        await asyncio.sleep(0)
        antes()
        _ESPIA.vistos = []
        _ESPIA.fio = threading.get_ident()
        try:
            if rota == "tique":
                gp._reconciliar_launch(mesa.d)
            elif rota == "ping":
                await servidor._armar_launch()
            else:
                params = {"appid": JOGO_A}
                servidor._agendar_arming_do_launch(
                    params, {}, await servidor._folha_do_pedido(params))
        finally:
            _ESPIA.fio = None
    finally:
        await asyncio.to_thread(le.desarmar_o_escrevente, escrevente)
    return _ESPIA.vistos


def _medir(
    mesa: _Mesa, casa: SimpleNamespace, rota: str, monkeypatch: pytest.MonkeyPatch,
    antes: Callable[[], None] = lambda: None,
) -> list[str]:
    monkeypatch.setattr(os, "stat", _ESPIA.stat)
    vistos = asyncio.run(_o_arme_em_producao(mesa, casa, rota, antes=antes))
    FIO_DO_PERFIL.submit(lambda: None).result(timeout=5)
    return vistos


@pytest.mark.parametrize("rota", _ROTAS)
@pytest.mark.parametrize("mesa_de", _MESAS, ids=list(_MESAS))
def test_o_jogo_com_perfil_arma_sem_tocar_arquivo_no_laco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str, mesa_de: str,
) -> None:
    """Perfil denso com o caminho Xbox, de um a quatro jogadores, no cabo e no rádio."""
    _perfil_denso(casa)
    transporte, secundarios = _MESAS[mesa_de]
    mesa = _Mesa(monkeypatch, transporte, secundarios)
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d._launch_armed_for == marca
    assert mesa.d._pad_travado_pelo_lancamento == marca
    assert mesa.d.store.active_profile == "Denso"
    assert mesa.d._gamepad_device.flavor == "xbox", "o caminho do perfil não foi vestido"
    assert session_mod.o_ultimo_jogo() == "Denso", "o último jogo não chegou ao disco"


def _pousar_em(mesa: _Mesa, de_onde: str) -> None:
    """O modo em que o serviço estava quando o jogo abriu."""
    if de_onde == "mouse":
        mesa.d.set_mouse_emulation(True, origin="profile")
    elif de_onde == "Nativo":
        mesa.d.set_native_mode(True, origin="profile")


@pytest.mark.parametrize("de_onde", ["gamepad", "mouse", "Nativo"])
@pytest.mark.parametrize("modo", _MODOS, ids=list(_MODOS))
@pytest.mark.parametrize("rota", _ROTAS)
def test_todo_modo_arma_sem_tocar_arquivo_e_as_bandeiras_chegam_ao_disco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str, modo: str, de_onde: str,
) -> None:
    """Do modo de antes para o do perfil, em todo par: a troca grava fora do laço, e grava."""
    _perfil_denso(casa, _MODOS[modo])
    mesa = _Mesa(monkeypatch, "bt", 1)
    _pousar_em(mesa, de_onde)
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d._launch_armed_for == marca
    assert mesa.d.store.active_profile == "Denso"
    kind = (_MODOS[modo] or {}).get("kind")
    if kind == "native":
        assert session_mod.load_native_mode()[0] is True, "a bandeira do Nativo não chegou ao disco"
    elif kind == "desktop":
        assert mesa.d._gamepad_device is None
        assert session_mod.load_native_mode()[0] is False, "a saída do Nativo não foi gravada"
        if de_onde == "gamepad":
            assert session_mod.load_gamepad_preference()[0] is False, "o pad não foi gravado"
    elif kind == "gamepad":
        assert session_mod.load_native_mode()[0] is False, "a saída do Nativo não foi gravada"


def test_o_point_and_click_de_um_perfil_vem_da_lista_que_o_arme_leu(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A escolha «perfil:» do Point and click não abre o arquivo dele no laço."""
    loader.save_profile(_perfil(JOGO_B))
    _perfil_denso(
        casa, _MODOS["Point and click"],
        mouse={"enabled": True, "point_and_click": f"perfil:jogo_{JOGO_B}"})
    mesa = _Mesa(monkeypatch, "usb", 0)
    _lancar(casa)

    assert _medir(mesa, casa, "tique", monkeypatch) == []

    assert mesa.d.store.active_profile == "Denso"
    assert mesa.d._gamepad_device is None
    assert mesa.d._arranjo_lido_no_arme is None


def test_as_bandeiras_lidas_respondem_o_que_se_gravou_e_gravam_na_ordem(
    casa: SimpleNamespace,
) -> None:
    """Quem lê depois da gravação vê a nova; o disco só muda quando a entrega roda."""
    session_mod.save_gamepad_emulation(True, "xbox")
    session_mod.save_mouse_emulation(False, speed=4, scroll_speed=2)
    lidas = session_mod.ler_as_bandeiras_do_modo()
    entregues: list[Callable[[], None]] = []

    with session_mod.com_as_bandeiras_lidas(lidas, entregues.append):
        session_mod.save_gamepad_emulation(False)
        session_mod.save_mouse_emulation(True)
        assert session_mod.load_gamepad_preference() == (False, None)
        assert session_mod.load_mouse_preference() == (True, 4, 2)

    assert session_mod.load_gamepad_preference() == (True, "xbox"), "o disco mudou no laço"
    assert len(entregues) == 3
    for entrega in entregues:
        entrega()
    assert session_mod.load_gamepad_preference() == (False, None)
    assert session_mod.load_mouse_preference() == (True, 4, 2)


def test_fora_do_laco_o_arme_grava_as_bandeiras_antes_de_voltar(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem laço rodando não há entrada a segurar: a CLI vê o disco gravado na volta do arme."""
    _perfil_denso(casa, _MODOS["Nativo"])
    mesa = _Mesa(monkeypatch, "usb", 0)
    _lancar(casa)
    folha = le.a_folha_com_o_arme(mesa.d)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.FIO_DO_PERFIL.submit",
        lambda *_a, **_k: pytest.fail("fora do laço, a gravação esperou o fio"))

    le.arm_launch_profile(mesa.d, folha=folha)

    assert session_mod.load_native_mode()[0] is True


def test_a_leitura_sem_as_bandeiras_cai_no_caminho_de_sempre(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bandeira que não se lê vale como ausente, e o computador sem leitura vai ao disco."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    _lancar(casa)
    monkeypatch.setattr(session_mod, "_texto_no_disco", _levanta)

    leitura = le.a_folha_com_o_arme(mesa.d).arme

    assert leitura is not None and set(leitura.bandeiras.values()) == {None}


@pytest.mark.parametrize("rota", _ROTAS)
def test_o_jogo_sem_perfil_veste_a_roupa_gravada_sem_tocar_arquivo(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str,
) -> None:
    """A roupa do arquivo, lida fora do laço, é a que o pad veste, com o perfil ativo de antes."""
    loader.save_profile(_perfil(JOGO_B))
    mesa = _Mesa(monkeypatch, "usb", 1)
    mesa.d.store.set_active_profile(f"jogo_{JOGO_B}")
    mesa.d._hidraw_broker_client = object()
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d._launch_armed_for == marca
    assert set(mesa.roupas().values()) == {COMUM}
    assert mesa.d._arranjo_lido_no_arme is None, "a leitura do arme ficou de pé depois dele"


@pytest.mark.parametrize("rota", _ROTAS)
def test_a_allowlist_arma_sem_tocar_arquivo_e_sem_a_mascara(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str,
) -> None:
    """O jogo marcado ativa o perfil e não veste a roupa nem o modo dele."""
    loader.save_profile(_perfil(JOGO_A, flavor="xbox", caminho="xbox"))
    casa.allowlist.write_text(f"{JOGO_A}\n", encoding="utf-8")
    mesa = _Mesa(monkeypatch, "bt", 0)
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d._launch_armed_for == marca
    assert set(mesa.roupas().values()) == {EDGE}


@pytest.mark.parametrize("rota", _ROTAS)
def test_o_freestyle_ligado_arma_sem_tocar_arquivo(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str,
) -> None:
    loader.save_profile(_perfil(JOGO_A, flavor="xbox", caminho="xbox"))
    mesa = _Mesa(monkeypatch, "usb", 0)
    ligar_o_freestyle(mesa.d.store, True)
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d._launch_armed_for == marca
    assert set(mesa.roupas().values()) == {EDGE}, "o Freestyle veste o Edge"


@pytest.mark.parametrize("modo", ["Xbox", "Nativo", "desktop"])
@pytest.mark.parametrize("rota", _ROTAS)
def test_a_autoridade_do_jogo_que_acabou_se_decide_sem_o_proc_no_laco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str, modo: str,
) -> None:
    """O jogo anterior fechou e a histerese segura `game`: a varredura foi feita fora do laço."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    _perfil_denso(casa, _MODOS[modo])
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_B, EPOCH_A, COMUM)
    mesa.fechar_o_jogo(10.0)
    monkeypatch.setattr(
        mesa.d, "_gather_game_signal_inputs", Daemon._gather_game_signal_inputs.__get__(mesa.d))
    _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d.display_authority == "daemon", "a autoridade do jogo que acabou ficou"


@pytest.mark.parametrize("caso", ["sem lançamento", "outro jogo", "fora da janela"])
def test_o_status_do_wrapper_sem_lancamento_dele_nao_toca_arquivo(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, caso: str,
) -> None:
    """O `daemon.status {appid}` que não arma também monta o ambiente fora do laço."""
    _perfil_denso(casa)
    mesa = _Mesa(monkeypatch, "usb", 0)
    appid, epoch = {
        "outro jogo": (JOGO_B, int(time.time())),
        "fora da janela": (JOGO_A, int(time.time() - le.LAUNCH_ARM_WINDOW_SEC - 30)),
    }.get(caso, (0, 0))
    if appid:
        (casa.pasta / "last_run").write_text(
            f"appid={appid}\nepoch={epoch}\npid={os.getpid()}\n", encoding="utf-8")

    assert _medir(mesa, casa, "status do wrapper", monkeypatch) == []

    assert mesa.d._launch_armed_for != (appid, epoch)


@pytest.mark.parametrize("rota", _ROTAS)
def test_a_autoridade_do_proprio_jogo_fica_sem_o_proc_no_laco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, rota: str,
) -> None:
    """O tique viu o jogo antes do ping: a autoridade é dele, e ele não se encerra."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    loader.save_profile(_perfil(JOGO_A))
    mesa = _Mesa(monkeypatch, "usb", 0)
    mesa.abrir_o_jogo(JOGO_A, EPOCH_A, COMUM)
    monkeypatch.setattr(
        mesa.d, "_gather_game_signal_inputs", Daemon._gather_game_signal_inputs.__get__(mesa.d))
    marca = _lancar(casa)

    assert _medir(mesa, casa, rota, monkeypatch) == []

    assert mesa.d.display_authority == "game"
    assert mesa.d._launch_armed_for == marca


def test_a_leitura_fora_do_laco_responde_como_a_do_arme_na_hora(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A roupa, a allowlist e o perfil da folha são os que o arme leria do disco."""
    loader.save_profile(_perfil(JOGO_A, flavor="xbox", caminho="xbox"))
    mesa = _Mesa(monkeypatch, "usb", 0)
    marca = _lancar(casa)

    leitura = le.a_folha_com_o_arme(mesa.d).arme
    na_hora = le._ler_o_arme(mesa.d, marca, le.steam_input_appids())

    assert leitura is not None
    assert leitura.marker == na_hora.marker == marca
    assert leitura.roupa == na_hora.roupa == COMUM
    assert leitura.na_allowlist == na_hora.na_allowlist is False
    assert leitura.perfil == na_hora.perfil
    assert leitura.outro_jogo() == na_hora.outro_jogo()


def test_a_varredura_que_levanta_chega_ao_arme_como_levantou(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Na dúvida, fica: a falha da varredura fora do laço não vira «nenhum outro jogo»."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    _lancar(casa)

    def quebrada(_d: Any, _a: int) -> tuple[bool, list[int]]:
        raise OSError("sem /proc")

    monkeypatch.setattr(le, "_ha_outro_jogo_vivo", quebrada)
    leitura = le.a_folha_com_o_arme(mesa.d).arme

    assert leitura is not None
    with pytest.raises(OSError, match="sem /proc"):
        leitura.outro_jogo()


def test_a_folha_le_o_arme_uma_vez_por_lancamento_e_nada_sem_lancamento(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesa parada não relê perfil; o `marker` novo relê a roupa, e o selo novo, os perfis."""
    roupas: list[int] = []
    perfis: list[int] = []
    gravada, carregar = le.roupa_gravada, le._load_profiles

    def contar_a_roupa(appid: int, *a: Any, **k: Any) -> int:
        roupas.append(appid)
        return gravada(appid, *a, **k)

    def contar_os_perfis(leitor: Any) -> list[Any]:
        if getattr(leitor, "perfis_lidos", None) is None:
            perfis.append(1)
        return carregar(leitor)

    monkeypatch.setattr(le, "roupa_gravada", contar_a_roupa)
    monkeypatch.setattr(le, "_load_profiles", contar_os_perfis)
    mesa = _Mesa(monkeypatch, "usb", 0)
    loader.save_profile(_perfil(JOGO_A))
    perfis.clear()

    assert le.a_folha_com_o_arme(mesa.d).perfis is None
    assert (roupas, perfis) == ([], []), "sem lançamento, nada de perfil na folha"

    _lancar(casa)
    folha = le.a_folha_com_o_arme(mesa.d)
    for _passada in range(3):
        repetida = le.a_folha_com_o_arme(mesa.d, folha)
        assert repetida.arme is folha.arme
        folha = repetida
    assert (roupas, perfis) == ([JOGO_A], [1])

    loader.save_profile(_perfil(JOGO_B))
    folha = le.a_folha_com_o_arme(mesa.d, folha)
    assert (roupas, perfis) == ([JOGO_A, JOGO_A], [1, 1])

    (casa.pasta / "last_run").write_text(
        f"appid={JOGO_B}\nepoch={int(time.time()) + 1}\npid={os.getpid()}\n", encoding="utf-8")
    folha = le.a_folha_com_o_arme(mesa.d, folha)
    assert roupas == [JOGO_A, JOGO_A, JOGO_B]
    assert perfis == [1, 1], "o selo é o mesmo: a lista segue a lida"


def test_o_lancamento_fora_da_janela_nao_le_o_arme(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A folha do pedido traz os perfis para o ambiente, e nada do arme."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    loader.save_profile(_perfil(JOGO_A))
    velho = int(time.time() - le.LAUNCH_ARM_WINDOW_SEC - 30)
    (casa.pasta / "last_run").write_text(
        f"appid={JOGO_A}\nepoch={velho}\npid={os.getpid()}\n", encoding="utf-8")

    folha = le.a_folha_do_pedido(mesa.d)

    assert folha.arme is None and folha.perfis is not None and len(folha.perfis) == 1


def test_a_folha_sem_a_leitura_do_marker_nao_arma_nem_le(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A folha sem o arme espera a seguinte: o marker não fica armado sem ter armado."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    marca = _lancar(casa)
    monkeypatch.setattr(le, "_armar_o_jogo", lambda *_a: pytest.fail("armou sem a leitura"))

    resposta = le.arm_launch_profile(mesa.d, folha=le.ler_a_folha())

    assert resposta is None
    assert mesa.d._launch_armed_for != marca


def test_o_ultimo_jogo_grava_no_fio_do_perfil_e_fora_do_laco_na_hora(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No laço, o fio do perfil; fora dele, antes de a ativação voltar."""
    import hefesto_dualsense4unix.profiles.manager as manager

    fios: list[str] = []

    def anotar(nome: str) -> None:
        fios.append(threading.current_thread().name)

    monkeypatch.setattr(session_mod, "lembrar_o_ultimo_jogo", anotar)

    async def no_laco() -> None:
        manager._lembrar_o_ultimo_jogo_fora_do_laco("Jogo")

    asyncio.run(no_laco())
    FIO_DO_PERFIL.submit(lambda: None).result(timeout=5)
    manager._lembrar_o_ultimo_jogo_fora_do_laco("Jogo")

    assert fios[0].startswith("hefesto-perfil")
    assert fios[1] == threading.main_thread().name


def test_o_dono_igual_nao_volta_ao_arquivo_e_o_novo_grava(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    arquivo = casa.pasta / "run" / "dono"
    monkeypatch.setenv(gp.DONO_DO_P1_ENV, str(arquivo))
    gp.lembrar_o_dono_do_p1("aa:bb:cc:00:00:01")
    gp.lembrar_o_dono_do_p1("aa:bb:cc:00:00:02")
    assert arquivo.read_text(encoding="ascii") == "aa:bb:cc:00:00:02"
    monkeypatch.setattr(os, "stat", _ESPIA.stat)

    _ESPIA.vistos = []
    _ESPIA.fio = threading.get_ident()
    gp.lembrar_o_dono_do_p1("aa:bb:cc:00:00:02")
    _ESPIA.fio = None

    assert _ESPIA.vistos == []
    gp.lembrar_o_dono_do_p1("aa:bb:cc:00:00:01")
    assert arquivo.read_text(encoding="ascii") == "aa:bb:cc:00:00:01"


def test_o_tique_nao_cai_na_borda_do_arme_com_o_disco_preso(
    casa_do_relogio: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A roupa dorme 2 s no fio do caderno: a entrada anda, e o arme chega depois da volta."""
    monkeypatch.setattr(le, "materialize_launch_env", _MATERIALIZAR)
    monkeypatch.setattr(le, "steam_input_appids", _ALLOWLIST)
    marca = (JOGO_A, int(time.time()))
    (casa_do_relogio.base / "last_run").write_text(
        f"appid={marca[0]}\nepoch={marca[1]}\npid={os.getpid()}\n", encoding="utf-8")
    relogio._dormindo(monkeypatch, "roupa_gravada")
    segundos = 3.5
    daemon = relogio._Daemon(segundos)

    asyncio.run(daemon.rodar())

    assert daemon._launch_armed_for == marca
    assert len(daemon.despachos) / segundos > 40
    assert relogio._pior_buraco(daemon) < 1.0, f"o laço parou {relogio._pior_buraco(daemon):.2f} s"


def test_o_disco_preso_no_caderno_nao_segura_a_trava_da_escrita(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leitura presa não tem trava de ninguém: quem escreve o lançamento segue livre."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    _lancar(casa)
    lendo, soltar = threading.Event(), threading.Event()
    gravada = le.roupa_gravada

    def presa(*a: Any, **k: Any) -> int:
        lendo.set()
        soltar.wait(3.0)
        return gravada(*a, **k)

    monkeypatch.setattr(le, "roupa_gravada", presa)
    fio = threading.Thread(target=le.a_folha_com_o_arme, args=(mesa.d,), daemon=True)
    fio.start()
    assert lendo.wait(2.0)
    try:
        assert le._TRAVA_DA_ESCRITA.acquire(blocking=False), "a leitura segurou a trava da escrita"
        le._TRAVA_DA_ESCRITA.release()
    finally:
        soltar.set()
        fio.join(3.0)


def test_o_status_do_wrapper_arma_na_resposta_com_a_leitura_fora_do_laco(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resposta do `daemon.status {appid}` sai do estado armado, e o laço seguiu andando."""
    loader.save_profile(_perfil(JOGO_A, flavor="xbox", caminho="xbox"))
    mesa = _Mesa(monkeypatch, "usb", 0)
    marca = _lancar(casa)
    fios: list[str] = []
    ler = le.a_folha_do_pedido

    def lenta(daemon: Any) -> Any:
        fios.append(threading.current_thread().name)
        time.sleep(0.5)
        return ler(daemon)

    monkeypatch.setattr(le, "a_folha_do_pedido", lenta)
    servidor = _servidor(mesa, casa)

    async def corpo() -> tuple[int, Any]:
        voltas = 0

        async def contar() -> None:
            nonlocal voltas
            while True:
                voltas += 1
                await asyncio.sleep(0.02)

        contador = asyncio.ensure_future(contar())
        resposta = await servidor._handle_daemon_status({"appid": JOGO_A})
        contador.cancel()
        return voltas, resposta

    voltas, resposta = asyncio.run(corpo())

    assert fios and threading.main_thread().name not in fios
    assert voltas >= 10, f"o laço andou {voltas} voltas em 0,5 s"
    assert mesa.d._launch_armed_for == marca
    assert resposta["ambiente"]["appid"] == JOGO_A


def test_a_folha_do_pedido_que_levanta_nao_derruba_o_status(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O `daemon.status` do wrapper responde, e o arme cai no caminho de sempre."""
    mesa = _Mesa(monkeypatch, "usb", 0)
    marca = _lancar(casa)
    servidor = _servidor(mesa, casa)
    monkeypatch.setattr(le, "a_folha_do_pedido", _levanta)

    resposta = asyncio.run(servidor._handle_daemon_status({"appid": JOGO_A}))

    assert resposta["ambiente"]["appid"] == JOGO_A
    assert mesa.d._launch_armed_for == marca


def test_todo_arme_de_producao_passa_a_folha() -> None:
    """Sem `folha` o arme lê o disco: nenhum chamador de produção pode ser essa forma."""
    sem_folha: list[str] = []
    for arquivo in sorted((_RAIZ / "src").rglob("*.py")):
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func.attr if isinstance(no.func, ast.Attribute) else getattr(
                no.func, "id", None)
            if alvo == "arm_launch_profile" and "folha" not in {k.arg for k in no.keywords}:
                sem_folha.append(f"{arquivo.name}:{no.lineno}")

    assert sem_folha == []
