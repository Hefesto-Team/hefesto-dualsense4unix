"""FOCO-ERRANTE-01 — a janela da Steam levava o perfil do jogo junto.

Sprint: `2026-08-18-FOCO-ERRANTE-01-o-x-aponta-para-a-steam-e-leva-o-perfil-junto.md`
em `docs/process/sprints/`.

O defeito, MEDIDO no journal dela em 18/08 entre 00:15 e 01:09: **treze trocas
de perfil** entre `Dont Scream` e `Navegação`, e **toda** troca para `Navegação`
trazia `wm_class=steam`. Uma delas cinco segundos depois da anterior. A janela
que rouba o foco não é a loja que ela abriu — é uma janela INVISÍVEL do cliente
Steam (instância `steamwebhelper`, **classe** `steam`, `WM_NAME` vazio) que toma
o foco do X sob XWayland. O backend usa a classe, o daemon lê literalmente
`"steam"`, o perfil `Navegação` dela casa com `steam`, e gatilhos e lightbar do
jogo são reescritos pelos do desktop no meio da partida.

**A armadilha que esta leva existe para não repetir**, e ela está medida: o
sinal óbvio — `launch_env.launch_session_appid()` — expira em
`WRAPPER_MARKER_WINDOW_SEC = 900` s. No instante do roubo o marker tinha
**1296 s**. Uma cura construída sobre aquela função teria respondido `None` e
**não teria evitado o defeito**. Por isso `jogo_do_wrapper_vivo()` existe: a
janela de frescor sai, e a corroboração por `AppId=` na linha de comando entra
no lugar dela para cobrir o PID reciclado.

**O falso positivo é pior que o defeito**, e por isso `test_sem_jogo_vivo...` e
`test_o_jogo_morre_e_a_guarda_solta` não são opcionais: uma guarda só por
`wm_class` prenderia o perfil do jogo PARA SEMPRE assim que ela fechasse o jogo
e ficasse na biblioteca da Steam.

Tudo hermético: `FakeController`, `StateStore` real, `ProfileManager` real,
diretório de perfis em `tmp_path` e o marker do wrapper em `tmp_path`. Nenhum
teste toca hardware, D-Bus, ou o `~/.config` dela.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.launch_env import launch_session_appid
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import (
    AutoSwitcher,
    jogo_do_wrapper_vivo,
)
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

#: O jogo dela no journal de 18/08 ("DON'T SCREAM").
APPID = 2497900

#: A classe que a Steam dá à janela do jogo.
CLASSE_DO_JOGO = f"steam_app_{APPID}"

#: A janela do jogo em foco, como o backend a entrega.
JANELA_DO_JOGO = {"wm_class": CLASSE_DO_JOGO, "wm_name": "DON'T SCREAM"}

#: A janela que rouba o foco: classe `steam`, **nome vazio** — a assinatura da
#: janela de serviço do `steamwebhelper` medida nas trinta amostras de 01h04.
JANELA_DO_CLIENTE_STEAM = {"wm_class": "steam", "wm_name": ""}

#: OUTRO jogo, para a guarda cruzada (marker de A não segura o perfil de B).
OUTRO_APPID = 1599660

#: A idade do marker `last_run` no instante EXATO do roubo do perfil
#: (marker de 00:31:38, roubo às 00:53:14). É o número que reprova qualquer
#: cura montada sobre `launch_session_appid`, cuja janela é de 900 s.
IDADE_MEDIDA_SEG = 1296


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis em `tmp_path` (mesmo padrão do resto da suíte).

    Obrigatório em todo teste que carregue ou salve perfil: sem ele a suíte
    escreve no diretório de perfis REAL dela (CANÁRIO-FS-01).
    """
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return alvo


def _perfil(nome: str, *, janela: str | None = None, prioridade: int = 10) -> Profile:
    """Perfil mínimo com gatilhos e lightbar — o que a troca reescreve."""
    return Profile(
        name=nome,
        match=MatchAny() if janela is None else MatchCriteria(window_class=[janela]),
        priority=0 if janela is None else prioridade,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Rigid", params=[0, 100]),
        ),
        leds=LedsConfig(lightbar=(129, 61, 156)),
    )


def _bancada(perfis: list[Profile]) -> tuple[ProfileManager, StateStore]:
    for perfil in perfis:
        save_profile(perfil)
    fc = FakeController()
    fc.connect()
    store = StateStore()
    return ProfileManager(controller=fc, store=store), store


def _os_dois_perfis() -> list[Profile]:
    """O disco dela, reduzido ao par que brigou: o jogo e a navegação."""
    return [
        _perfil("dont_scream", janela=CLASSE_DO_JOGO, prioridade=97),
        _perfil("navegacao", janela="steam", prioridade=50),
    ]


def _switcher(
    manager: ProfileManager,
    store: StateStore,
    *,
    jogo_vivo: Any = None,
) -> AutoSwitcher:
    return AutoSwitcher(
        manager=manager,
        window_reader=lambda: {},
        store=store,
        jogo_vivo_reader=jogo_vivo,
    )


def _entrar_no_jogo(sw: AutoSwitcher, store: StateStore) -> float:
    """Leva o autoswitch ao perfil do jogo pelo caminho normal, e devolve `now`.

    É o que JÁ funcionava — seis entradas corretas no journal dela em 18/08 —
    e todo teste daqui parte deste estado.
    """
    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)
    assert store.active_profile == "dont_scream", "o autoswitch não entrou no jogo"
    return 1.0


def _focar_a_steam(sw: AutoSwitcher, inicio: float, tiques: int = 20) -> None:
    """Segura a janela do cliente Steam em foco por `tiques` a 2 Hz."""
    for i in range(tiques):
        sw._tick(dict(JANELA_DO_CLIENTE_STEAM), inicio + 0.5 * (i + 1))


# --- o marker do wrapper, escrito como o `hefesto-launch.sh` o escreve --------


def _marker(
    tmp_path: Path,
    *,
    appid: int = APPID,
    idade_seg: int = 0,
    pid: int | None = None,
) -> Path:
    """Grava `last_run` com a idade pedida, e devolve o `base_dir`."""
    base = tmp_path / "launch_env"
    base.mkdir(exist_ok=True)
    (base / "last_run").write_text(
        f"appid={appid}\n"
        f"epoch={int(time.time()) - idade_seg}\n"
        f"pid={pid if pid is not None else os.getpid()}\n",
        encoding="utf-8",
    )
    return base


def _proc_falso(tmp_path: Path, *, cmdline: bytes, pid: int | None = None) -> Path:
    """Um `/proc` de mentira com a `cmdline` pedida, e devolve o `proc_dir`.

    A costura existe para o teste ser hermético; o teste
    `test_a_corroboracao_le_o_proc_de_verdade` prova, contra um processo REAL,
    que o parser não depende dela.
    """
    raiz = tmp_path / "proc"
    alvo = raiz / str(pid if pid is not None else os.getpid())
    alvo.mkdir(parents=True, exist_ok=True)
    (alvo / "cmdline").write_bytes(cmdline)
    return raiz


#: A linha de comando medida na máquina dela (PID 38036, 18/08):
#: `.../reaper SteamLaunch AppId=2497900 -- ... DontScream-Win64-Shipping.exe`
CMDLINE_MEDIDA = (
    b"/home/x/.steam/steam/ubuntu12_32/reaper\0SteamLaunch\0"
    b"AppId=2497900\0--\0/x/DontScream-Win64-Shipping.exe\0"
)


# ---------------------------------------------------------------------------
# 1) O defeito inteiro
# ---------------------------------------------------------------------------


def test_a_janela_do_cliente_steam_nao_troca_o_perfil_com_o_jogo_vivo(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 1: o defeito de 18/08, reduzido a dez segundos de tique.

    Arranque a guarda do `_tick` (o bloco
    `_recusa_a_janela_do_cliente_steam`) e o perfil troca para `navegacao` —
    exatamente as treze linhas do journal dela.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora)

    assert store.active_profile == "dont_scream"
    trocas = [r for r in registros if r["event"] == "profile_autoswitch"]
    assert trocas == [], f"o perfil foi roubado: {trocas}"


def test_a_recusa_preserva_o_gatilho_e_a_lightbar_do_jogo(
    perfis_isolados: Path,
) -> None:
    """O que ela PERDIA, no vocabulário do aparelho.

    O journal já dizia que `mode` e `rumble_policy` estavam protegidos
    (`ignorado_janela_de_jogo`); gatilho e lightbar não tinham guarda nenhuma.
    Aqui a conta é feita no controle: nenhuma escrita nova depois da recusa.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    controller: Any = manager.controller
    lightbar_do_jogo = controller.last_led
    assert lightbar_do_jogo is not None, "o perfil do jogo nem chegou ao LED"
    escritas = store.counter("profile.activated")

    _focar_a_steam(sw, agora)

    assert controller.last_led == lightbar_do_jogo
    assert store.counter("profile.activated") == escritas


# ---------------------------------------------------------------------------
# 2) O falso positivo — e ele é PIOR que o defeito
# ---------------------------------------------------------------------------


def test_sem_jogo_vivo_a_janela_da_steam_troca_normalmente(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 2: arranque o termo de VITALIDADE e este teste reprova.

    Uma guarda só por `wm_class` prenderia o perfil do jogo para sempre assim
    que ela fechasse o jogo e ficasse na biblioteca da Steam. É o cadeado
    permanente da armadilha nº 4 da sprint, e ele é pior que o defeito.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: None)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_o_jogo_morre_e_a_guarda_solta(perfis_isolados: Path) -> None:
    """O ensaio E-4 da sprint, em memória: a MESMA janela, uma variável só.

    A guarda segura enquanto o jogo vive e SOLTA quando ele morre, sem gesto
    nenhum dela. Sem esta prova, a cura teria virado cadeado.
    """
    manager, store = _bancada(_os_dois_perfis())
    vivo = [True]
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID if vivo[0] else None)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora, tiques=10)
    assert store.active_profile == "dont_scream"

    vivo[0] = False
    # Dois tiques = 1 s, que é o que o ensaio E-4 espera ver no journal.
    sw._tick(dict(JANELA_DO_CLIENTE_STEAM), agora + 6.0)
    sw._tick(dict(JANELA_DO_CLIENTE_STEAM), agora + 6.5)

    assert store.active_profile == "navegacao"


# ---------------------------------------------------------------------------
# 3) A guarda é SÓ para a Steam
# ---------------------------------------------------------------------------


def test_janela_de_outro_app_troca_o_perfil_mesmo_com_o_jogo_vivo(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 3: alargue a guarda para qualquer janela e isto reprova.

    É a política de 23/07 (o irmão de
    `test_perfil_especifico_fora_de_jogo_reverte_normalmente`) e o ensaio E-5:
    ela abre o Firefox com o jogo vivo, e o perfil de desktop entra.
    """
    manager, store = _bancada([*_os_dois_perfis(), _perfil("web", janela="firefox")])
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    for i in range(6):
        sw._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, agora + 0.5 * i)

    assert store.active_profile == "web"


def test_a_guarda_so_vale_para_o_jogo_do_perfil_corrente(
    perfis_isolados: Path,
) -> None:
    """MORDIDA nº 4: guarda cruzada — o marker de A não segura o perfil de B.

    Com o Sackboy vivo pelo wrapper e o perfil do `Dont Scream` corrente, a
    janela da Steam troca normalmente: a vitalidade que importa é a DO JOGO
    de quem está no controle agora.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: OUTRO_APPID)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_perfil_de_desktop_corrente_nao_ganha_guarda_nenhuma(
    perfis_isolados: Path,
) -> None:
    """A guarda exige que o perfil CORRENTE seja a regra própria de um jogo.

    Com um catch-all no controle, a janela da Steam continua trocando de perfil
    como sempre trocou — mesmo com um jogo vivo em segundo plano.
    """
    manager, store = _bancada([_perfil("desktop"), _perfil("navegacao", janela="steam")])
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    sw._tick({"wm_class": "nautilus"}, 0.0)
    sw._tick({"wm_class": "nautilus"}, 1.0)
    assert store.active_profile == "desktop"

    _focar_a_steam(sw, 1.0)

    assert store.active_profile == "navegacao"


# ---------------------------------------------------------------------------
# 5) Os 900 s — a armadilha medida
# ---------------------------------------------------------------------------


def test_o_jogo_vivo_nao_expira_aos_quinze_minutos(
    perfis_isolados: Path, tmp_path: Path
) -> None:
    """MORDIDA nº 5: o número medido, 1296 s, contra a janela de 900 s.

    Troque `jogo_do_wrapper_vivo()` por `launch_session_appid()` e este teste
    reprova nas TRÊS asserções: a função antiga responde `None`, a nova
    responde o appid, e só a nova segura o perfil no `_tick`.
    """
    base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG)
    proc = _proc_falso(tmp_path, cmdline=CMDLINE_MEDIDA)

    # A armadilha, dita em uma linha: a função que já existia teria falhado.
    assert launch_session_appid(base_dir=base) is None
    # E a função desta leva não falha, porque a janela de frescor saiu.
    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) == APPID

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(
        manager,
        store,
        jogo_vivo=lambda: jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc),
    )
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "dont_scream"


def test_marker_sem_pid_nao_atesta_vitalidade(tmp_path: Path) -> None:
    """Marker anterior ao NUMA-01 (sem `pid=`) não tem o que atestar.

    Sem PID não há vitalidade nem linha de comando para corroborar — recusar é
    o lado seguro, e é o que devolve o comportamento histórico.
    """
    base = tmp_path / "launch_env"
    base.mkdir()
    (base / "last_run").write_text(
        f"appid={APPID}\nepoch={int(time.time())}\n", encoding="utf-8"
    )

    assert jogo_do_wrapper_vivo(base_dir=base) is None


def test_sem_marker_nenhum_a_guarda_e_inerte(tmp_path: Path) -> None:
    """Máquina sem wrapper: a guarda nem chega a existir."""
    assert jogo_do_wrapper_vivo(base_dir=tmp_path / "vazio") is None


def test_o_last_exit_do_mesmo_launch_continua_invalidando(tmp_path: Path) -> None:
    """A correlação por pid do NUMA-01 sobrevive à retirada da janela de tempo.

    A ÚNICA coisa que `jogo_do_wrapper_vivo` muda em relação a
    `wrapper_game_running` é o `window_sec`. Se alguém reimplementar o critério
    à mão aqui, esta guarda reprova.
    """
    base = _marker(tmp_path, idade_seg=10)
    proc = _proc_falso(tmp_path, cmdline=CMDLINE_MEDIDA)
    (base / "last_exit").write_text(
        f"epoch={int(time.time())}\npid={os.getpid()}\n", encoding="utf-8"
    )

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None


# ---------------------------------------------------------------------------
# 6) O PID reciclado — o risco que os 900 s cobriam
# ---------------------------------------------------------------------------


def test_pid_reciclado_nao_segura_o_perfil(
    perfis_isolados: Path, tmp_path: Path
) -> None:
    """MORDIDA nº 6: arranque a corroboração por `AppId=` e isto reprova.

    Sem ela, um PID vivo QUALQUER (aqui, o próprio processo do pytest, cuja
    linha de comando não tem `AppId=` nenhum) passaria a valer por jogo — e o
    perfil do jogo ficaria preso a um número que o núcleo já reciclou.
    """
    base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG)
    proc = _proc_falso(
        tmp_path, cmdline=b"/usr/bin/python3\0-m\0pytest\0-q\0"
    )

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(
        manager,
        store,
        jogo_vivo=lambda: jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc),
    )
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_a_corroboracao_nao_confunde_appid_prefixo(tmp_path: Path) -> None:
    """`AppId=249790` não é `AppId=2497900` — a fronteira do número é dura."""
    base = _marker(tmp_path)
    proc = _proc_falso(tmp_path, cmdline=b"reaper\0SteamLaunch\0AppId=24979000\0")

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) is None


def test_a_corroboracao_e_insensivel_a_caixa(tmp_path: Path) -> None:
    """A Steam escreve `AppId=`; a casa não aposta na grafia de ninguém."""
    base = _marker(tmp_path)
    proc = _proc_falso(tmp_path, cmdline=b"reaper\0SteamLaunch\0APPID=2497900\0--\0")

    assert jogo_do_wrapper_vivo(base_dir=base, proc_dir=proc) == APPID


def test_a_corroboracao_le_o_proc_de_verdade(tmp_path: Path) -> None:
    """A régua contra um processo REAL — o `/proc` de mentira não pode mentir.

    "O instrumento mente mais que o produto": os testes acima usam um `/proc`
    fabricado, e um parser quebrado passaria em todos eles. Aqui há um processo
    de verdade, com `AppId=` na `argv` de verdade, separada por NUL de verdade.
    """
    filho = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            "SteamLaunch",
            f"AppId={APPID}",
            "--",
        ],
    )
    try:
        base = _marker(tmp_path, idade_seg=IDADE_MEDIDA_SEG, pid=filho.pid)
        assert jogo_do_wrapper_vivo(base_dir=base) == APPID
    finally:
        filho.kill()
        filho.wait(timeout=10)

    # E o mesmo marker, com o processo MORTO, deixa de atestar coisa nenhuma.
    assert jogo_do_wrapper_vivo(base_dir=base) is None


# ---------------------------------------------------------------------------
# 7) O journal não pode inundar
# ---------------------------------------------------------------------------


def test_a_recusa_loga_uma_vez_por_episodio(perfis_isolados: Path) -> None:
    """MORDIDA nº 7: arranque a chave de dedup e vira uma linha por tique.

    O poll é 2 Hz e o episódio medido no journal dela durou minutos: sem a
    chave seriam ~7 200 linhas por hora.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora, tiques=40)

    recusas = [
        r for r in registros if r["event"] == "autoswitch_recusou_a_janela_da_steam"
    ]
    assert len(recusas) == 1, f"{len(recusas)} linhas em 40 tiques"
    assert recusas[0]["candidato"] == "navegacao"
    assert recusas[0]["perfil_corrente"] == "dont_scream"
    assert recusas[0]["appid"] == APPID


def test_um_episodio_novo_volta_a_aparecer_no_journal(perfis_isolados: Path) -> None:
    """Dedup não pode virar silêncio: o episódio SEGUINTE tem de aparecer.

    É o irmão do `BUG-AUTOSWITCH-LOG-KEY-STUCK-01`: uma chave que nunca zera
    esconde o defeito da próxima vez que ele acontecer.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    with structlog.testing.capture_logs() as registros:
        _focar_a_steam(sw, agora, tiques=6)
        # Ela volta ao jogo: o episódio termina.
        sw._tick(dict(JANELA_DO_JOGO), agora + 5.0)
        sw._tick(dict(JANELA_DO_JOGO), agora + 5.5)
        # E a janela da Steam rouba o foco de novo — é o episódio SEGUINTE.
        _focar_a_steam(sw, agora + 6.0, tiques=6)

    recusas = [
        r for r in registros if r["event"] == "autoswitch_recusou_a_janela_da_steam"
    ]
    assert len(recusas) == 2


# ---------------------------------------------------------------------------
# As guardas — o que a cura não pode ter quebrado
# ---------------------------------------------------------------------------


def test_a_entrada_no_perfil_do_jogo_continua_barata(perfis_isolados: Path) -> None:
    """GUARDA (passa nos dois estados): a UX-04 continua de pé.

    Seis entradas corretas no perfil do jogo estão no journal dela em 18/08 —
    a hipótese tem de explicar o que JÁ funcionava, e a cura não pode custar
    isso.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)

    sw._tick(dict(JANELA_DO_JOGO), 0.0)
    sw._tick(dict(JANELA_DO_JOGO), 1.0)

    assert store.active_profile == "dont_scream"


def test_o_tique_cego_continua_retendo_o_perfil(perfis_isolados: Path) -> None:
    """GUARDA: a histerese UX-01 não foi tocada.

    Os 27 episódios de `x11_focus_gate_no_x_focus` de 18/08 são INOFENSIVOS, e
    têm de continuar sendo.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=lambda: APPID)
    agora = _entrar_no_jogo(sw, store)

    for i in range(10):
        sw._tick({}, agora + 0.5 * (i + 1))

    assert store.active_profile == "dont_scream"


def test_sem_leitor_injetado_a_guarda_nao_derruba_o_tique(
    perfis_isolados: Path,
) -> None:
    """GUARDA: o default de produção (ler o disco real) é inerte sem marker.

    O daemon não liga fio nenhum — `jogo_vivo_reader=None` cai em
    `jogo_do_wrapper_vivo()`, que num ambiente sem marker responde `None`. O
    autoswitch tem de seguir exatamente como sempre seguiu.
    """
    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"


def test_leitor_que_levanta_nao_derruba_o_tique(perfis_isolados: Path) -> None:
    """GUARDA: exceção na vitalidade vira "não sei", e "não sei" não recusa.

    A guarda é a EXCEÇÃO; uma exceção que falha tem de devolver o
    comportamento histórico, nunca congelar o perfil.
    """

    def _explode() -> int | None:
        raise RuntimeError("marker ilegível")

    manager, store = _bancada(_os_dois_perfis())
    sw = _switcher(manager, store, jogo_vivo=_explode)
    agora = _entrar_no_jogo(sw, store)

    _focar_a_steam(sw, agora)

    assert store.active_profile == "navegacao"
