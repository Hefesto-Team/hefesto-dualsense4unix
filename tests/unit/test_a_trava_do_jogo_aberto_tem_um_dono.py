"""A-TRAVA-DO-JOGO-ABERTO-TEM-UM-DONO-01 — a trava do jogo aberto tem um dono.

O que se mediu em 30/09 (o Future Knight, das 03:02 às 03:24, quatro DualSense no
rádio): a trava R-04 funciona — às 03:06:59 ela segurou a única troca
automática do P1 —, mas a pergunta «posso recriar o pad com o jogo aberto?» se
fazia em cinco lugares, de três jeitos, e um deles (o juiz da máscara do co-op,
`CoopManager.sync`) não perguntava: o perfil automático escrevia a máscara por
peça no registro com o P1 segurado, e o P2 seria recriado no meio da partida no
primeiro evento de `/dev/input`. E o gesto dela passava calado: achar quem
recriou às 03:07:09 custou juntar cinco eventos.

A cura: um dono da pergunta (`gamepad._recriacao_bloqueada_por_jogo`), com a
tabela das origens que passam com o jogo aberto, cada uma com a decisão dela; a
linha `pad_recriado_com_o_jogo_aberto` de quem passa; o aviso de espera UMA vez
por origem por episódio; e todos os juízes perguntando a ele.

Nenhuma régua confere a saída contra ela mesma: o sinal de jogo é dado, e o
esperado sai da entrada (a origem de quem pede, a máscara do registro). Os ids
das decisões estão escritos aqui, e conferidos contra o CSV dela — nunca lidos
da tabela do dono. A mordida de cada uma está no docstring dela.

Os endereços são da faixa forjada da casa.
"""
from __future__ import annotations

import ast
import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
import structlog.testing

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    _zerar_registro_de_mascaras,
    mascara_efetiva,
    registro_de_mascaras,
)
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

MAC_P1 = "aa:bb:cc:00:00:01"
SECUNDARIOS = ("aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
NOS = {
    MAC_P1: "/dev/input/event5",
    SECUNDARIOS[0]: "/dev/input/event7",
    SECUNDARIOS[1]: "/dev/input/event9",
    SECUNDARIOS[2]: "/dev/input/event11",
}

DO_GESTO = "D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR"
DA_ORDEM = "D-2309-FORA-DE-ORDEM-SE-RECRIA-NA-HORA"
CAMPO_DA_DECISAO = "decisao"  # noqa-acento: nome do campo no diário


class _Pad:
    """Um boneco com o que o produto lê dele: máscara, canal e caminho."""

    def __init__(self, flavor: str, caminho: str | None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.parado = False

    def stop(self) -> None:
        self.parado = True

    def forward_analog(self, **_kw: int) -> None:
        return None

    def forward_buttons(self, _pressed: Any) -> None:
        return None


class _Leitor:
    """O leitor evdev de mentira: o grab confirma na hora."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        return None

    def snapshot(self) -> Any:
        return None


class _Nascidos:
    todos: ClassVar[list[_Pad]] = []


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Disco em tmp, o registro zerado, a borda do pad e do evdev dublada."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)

    def _fabrica(flavor: Any, **kw: Any) -> _Pad:
        pad = _Pad(mascara_efetiva(kw.get("identity"), flavor), kw.get("caminho"))
        _Nascidos.todos.append(pad)
        return pad

    _Nascidos.todos = []
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _d: None
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    monkeypatch.setattr("hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _Leitor)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})
    _zerar_registro_de_mascaras()
    yield
    _zerar_registro_de_mascaras()


def _na_mesa(monkeypatch: pytest.MonkeyPatch, secundarios: int) -> None:
    macs = (MAC_P1, *SECUNDARIOS[:secundarios])
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {mac: Path(NOS[mac]) for mac in macs},
    )


def _daemon(transporte: str = "usb") -> Any:
    """O `Daemon` real, sem aparelho; o sinal de jogo é dado pela régua."""
    d = Daemon(
        controller=FakeController(transport=transporte),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d.controller.primary_uniq = MAC_P1
    d._game_signal = SimpleNamespace(authority="daemon")
    return d


def _jogo(d: Any, autoridade: str) -> None:
    d._game_signal = SimpleNamespace(authority=autoridade)


def _a_mesa(d: Any, monkeypatch: pytest.MonkeyPatch, secundarios: int) -> CoopManager:
    """O P1 em DualSense e os secundários com o pad de pé, pelo `sync` de verdade."""
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    _na_mesa(monkeypatch, secundarios)
    mesa = coop_mod.get_coop_manager(d)
    mesa.sync()
    pads = {mac: p.vpad for mac, p in mesa._players.items()}
    assert len(pads) == secundarios and all(p is not None for p in pads.values()), (
        f"premissa: os {secundarios} secundários com o pad de pé ({pads})")
    return mesa


def _linhas(diario: list[dict[str, Any]], evento: str) -> list[dict[str, Any]]:
    return [x for x in diario if x.get("event") == evento]


def test_o_juiz_do_co_op_espera_o_jogo_e_converge_quando_ele_fecha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O registro diz Xbox para o P2 (o perfil automático), e `/dev/input` muda."""
    d = _daemon()
    mesa = _a_mesa(d, monkeypatch, 1)
    p2 = SECUNDARIOS[0]
    antes = mesa._players[p2].vpad
    _jogo(d, "game")
    registro_de_mascaras().set_mask(p2, "xbox")

    with structlog.testing.capture_logs() as diario:
        mesa.sync()

    assert mesa._players[p2].vpad is antes and not antes.parado, (
        "o juiz do co-op recriou o P2 com o jogo na autoridade")
    assert _linhas(diario, "coop_player_flavor_changed") == []
    assert [x["origem"] for x in _linhas(diario, "vpad_recriacao_bloqueada_por_jogo")] == [
        "coop_tique"]

    _jogo(d, "daemon")
    gp.reconciliar_as_mascaras(d)

    assert mesa._players[p2].vpad.flavor == "xbox", "o P2 não convergiu quando o jogo fechou"


def test_o_p1_morto_que_renasce_sozinho_leva_a_origem_ao_co_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O P1 derrubado pelo kernel renasce por caminho automático, com o jogo aberto."""
    d = _daemon()
    mesa = _a_mesa(d, monkeypatch, 1)
    p2 = SECUNDARIOS[0]
    antes = mesa._players[p2].vpad
    _jogo(d, "game")
    registro_de_mascaras().set_mask(p2, "xbox")
    morto = d._gamepad_device
    monkeypatch.setattr(gp, "vpad_vivo", lambda dev: dev is not morto)

    d.set_gamepad_emulation_desfecho(True, "xbox", origin="profile")

    assert d._gamepad_device is not morto, "premissa: o P1 morto renasceu"
    assert mesa._players[p2].vpad is antes, (
        "o P1 morto levou junto o P2 vivo, sem ninguém ter perguntado por ele")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("secundarios", [0, 1, 2, 3], ids=["1j", "2j", "3j", "4j"])
def test_o_gesto_dela_recria_e_diz_qual_decisao_deixou(
    secundarios: int, transporte: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o jogo aberto, o gesto dela (`manual`) troca para Xbox, nos quatro."""
    d = _daemon(transporte)
    mesa = _a_mesa(d, monkeypatch, secundarios) if secundarios else None
    if mesa is None:
        gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    _jogo(d, "game")

    with structlog.testing.capture_logs() as diario:
        desfecho = d.set_gamepad_emulation_desfecho(True, "xbox", origin="manual")

    assert desfecho == gp.EMU_APLICADO
    assert d._gamepad_device.flavor == "xbox"
    if mesa is not None:
        assert {p.vpad.flavor for p in mesa._players.values()} == {"xbox"}
    linhas = _linhas(diario, "pad_recriado_com_o_jogo_aberto")
    assert len(linhas) == 1 + secundarios, linhas
    assert {(x["origem"], x[CAMPO_DA_DECISAO]) for x in linhas} == {("manual", DO_GESTO)}


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_automatico_espera_o_jogo(transporte: str) -> None:
    """`origin="profile"` com o jogo aberto: o pad fica, e o desfecho diz que esperou."""
    d = _daemon(transporte)
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    antes = d._gamepad_device
    _jogo(d, "game")

    desfecho = gp.start_gamepad_emulation_desfecho(d, "xbox", origin="profile")

    assert desfecho == gp.EMU_BLOQUEADO_POR_JOGO
    assert d._gamepad_device is antes and not antes.parado


def test_a_ordem_do_co_op_passa_e_diz_a_decisao_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """A carta renumerada com o jogo aberto: o secundário renasce, e a linha diz a D-2309."""
    d = _daemon()
    mesa = _a_mesa(d, monkeypatch, 2)
    p3 = SECUNDARIOS[1]
    antes = mesa._players[p3].vpad
    _jogo(d, "game")
    cartas = {SECUNDARIOS[0]: 2, p3: 3}
    monkeypatch.setattr(mesa, "_carta_da_chave", lambda chave: cartas.get(chave, 1))
    monkeypatch.setattr(coop_mod, "planejar_a_ordem", lambda *a, **k: ([p3], True))

    with structlog.testing.capture_logs() as diario:
        mesa._ordenar(None)

    assert antes.parado and mesa._players[p3].vpad is not antes, "premissa: a ordem recriou"
    linhas = _linhas(diario, "pad_recriado_com_o_jogo_aberto")
    assert [(x["origem"], x[CAMPO_DA_DECISAO]) for x in linhas] == [("ordem_do_coop", DA_ORDEM)]


def test_o_aviso_da_espera_e_um_por_origem_e_so_com_o_que_recriar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sessenta tiques com o jogo aberto: uma linha de espera por origem."""
    d = _daemon()
    mesa = _a_mesa(d, monkeypatch, 1)
    _jogo(d, "game")

    with structlog.testing.capture_logs() as quieto:
        for _ in range(20):
            gp.reconciliar_as_mascaras(d)
            mesa.sync()
    assert _linhas(quieto, "vpad_recriacao_bloqueada_por_jogo") == [], (
        "o dono disse espera sem nada para trás")

    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    registro_de_mascaras().set_mask(SECUNDARIOS[0], "xbox")
    with structlog.testing.capture_logs() as diario:
        for volta in range(60):
            if volta % 3 == 0:
                gp.reconciliar_as_mascaras(d)
            elif volta % 3 == 1:
                mesa.sync()
            else:
                gp.start_gamepad_emulation_desfecho(d, "xbox", origin="profile")

    origens = sorted(x["origem"] for x in _linhas(diario, "vpad_recriacao_bloqueada_por_jogo"))
    assert origens == ["coop_tique", "profile", "reconciliacao"], origens


DESTRUIDORES = frozenset(
    {"stop_gamepad_emulation", "_teardown_player", "_derrubar_para_renascer", "reerguer_o_p1"})
LEITORES_DO_JOGO = frozenset({"display_authority", "_autoridade_do_jogo", "_jogo_com_a_autoridade"})

ISENTOS: dict[tuple[str, str], str] = {
    ("daemon/subsystems/coop.py", "_ordenar"): (
        "a autoridade decide o PLANO da ordem (o P1 fixo e a compactação); a "
        "recriação dos secundários passa pelo dono, com `ordem_do_coop`"),
}

SYNC_FORCADO: dict[tuple[str, str], bool] = {
    ("daemon/ipc_handlers.py", "_repintar_apos_renumeracao"): False,
    ("daemon/ipc_handlers.py", "_handle_coop_sync"): False,
    ("daemon/lifecycle.py", "set_gamepad_emulation_desfecho"): True,
    ("daemon/lifecycle.py", "vestir_a_mascara_do_aparelho"): True,
    ("daemon/lifecycle.py", "set_coop_enabled"): False,
    ("daemon/subsystems/gamepad.py", "resume_vpads_after_steam_input"): False,
    ("daemon/subsystems/gamepad.py", "reconciliar_as_mascaras"): False,
}


def _nome(no: ast.AST) -> str | None:
    if isinstance(no, ast.Name):
        return no.id
    if isinstance(no, ast.Attribute):
        return no.attr
    return None


def _funcoes() -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    saida = []
    for arq in sorted(SRC.rglob("*.py")):
        rel = str(arq.relative_to(SRC))
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                saida.append((rel, no))
    return saida


def test_quem_destroi_pad_nao_le_o_sinal_do_jogo() -> None:
    """Nenhuma função que derruba pad lê o sinal do jogo para decidir: pergunta ao dono."""
    achados = []
    for rel, func in _funcoes():
        chama = {_nome(x.func) for x in ast.walk(func) if isinstance(x, ast.Call)} & DESTRUIDORES
        le = [x for x in ast.walk(func) if _nome(x) in LEITORES_DO_JOGO
              and not (isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)))]
        if chama and le and (rel, func.name) not in ISENTOS:
            achados.append(f"{rel}:{le[0].lineno} ({func.name}) lê "
                           f"`{_nome(le[0])}` e chama {sorted(chama)}")
    assert not achados, "a pergunta do jogo aberto saiu do dono:\n  " + "\n  ".join(achados)


def test_o_dreno_da_pendencia_pergunta_ao_dono() -> None:
    """O `_drenar_modo_pendente` não lê o sinal direto (ele derruba pelo `apply_profile_mode`)."""
    for rel, func in _funcoes():
        if rel == "daemon/lifecycle.py" and func.name == "_drenar_modo_pendente":
            nomes = {_nome(x) for x in ast.walk(func)}
            assert "display_authority" not in nomes, (
                f"{rel}:{func.lineno} o dreno voltou a ler o sinal direto")
            assert "_recriacao_bloqueada_por_jogo" in nomes
            return
    pytest.fail("o `_drenar_modo_pendente` sumiu do `lifecycle.py`")


def test_o_ciclo_forcado_do_co_op_tem_os_chamadores_de_hoje() -> None:
    """Os chamadores de `sync(force=True)` são os sete, e só dois dizem a origem."""
    achados: dict[tuple[str, str], bool] = {}
    linhas: dict[tuple[str, str], int] = {}
    for rel, func in _funcoes():
        for x in ast.walk(func):
            if not (isinstance(x, ast.Call) and _nome(x.func) == "sync"):
                continue
            kws = {k.arg: k.value for k in x.keywords}
            forca = kws.get("force")
            if isinstance(forca, ast.Constant) and forca.value is True:
                achados[(rel, func.name)] = "origem" in kws
                linhas[(rel, func.name)] = x.lineno
    novos = {f"{r}:{linhas[(r, f)]} ({f})" for (r, f) in achados if (r, f) not in SYNC_FORCADO}
    assert not novos, f"ciclo forçado novo, sem passar pelo dono: {sorted(novos)}"
    assert achados == SYNC_FORCADO


def _decisoes_dela() -> dict[str, dict[str, str]]:
    with (RAIZ / "docs" / "data" / "decisoes-dela.csv").open(encoding="utf-8") as fh:
        return {linha["id"]: linha for linha in csv.DictReader(fh)}


def test_toda_origem_que_passa_aponta_uma_decisao_dela() -> None:
    """Cada chave da tabela aponta um id decidido por ela (não por delegação)."""
    decisoes = _decisoes_dela()
    for origem, decisao in gp.ORIGENS_QUE_PASSAM_COM_O_JOGO.items():
        linha = decisoes.get(decisao)
        assert linha is not None, f"{origem}: {decisao} não está no CSV"
        assert (linha["estado"], linha["quem_decidiu"]) == ("decidida", "ela"), (
            f"{origem}: {decisao} não é decisão dela ({linha['estado']}, {linha['quem_decidiu']})")
    assert set(gp.ORIGENS_QUE_PASSAM_COM_O_JOGO) == {"manual", "gesto_de_perfil", "ordem_do_coop"}
    assert set(gp.ORIGENS_QUE_PASSAM_COM_O_JOGO.values()) == {DO_GESTO, DA_ORDEM}


def test_toda_ativacao_e_mascara_por_peca_dizem_a_origem_pelo_nome() -> None:
    """O padrão `origin="manual"` do `activate` e do `apply_controller_mascaras` não vira gesto."""
    alvos = {"activate", "apply_controller_mascaras"}
    sem = []
    for arq in sorted(SRC.rglob("*.py")):
        for x in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if not isinstance(x, ast.Call):
                continue
            chamado = _nome(x.func)
            if chamado == "partial" and x.args and _nome(x.args[0]) in alvos:
                chamado = _nome(x.args[0])
            elif chamado not in alvos or not isinstance(x.func, ast.Attribute):
                continue
            if "origin" not in {k.arg for k in x.keywords}:
                sem.append(f"{arq.relative_to(SRC)}:{x.lineno}")
    assert not sem, f"chamadas sem `origin=` por nome: {sem}"


def test_a_sessao_do_pad_que_fecha_e_reabre_nao_abre_a_trava() -> None:
    """O jogo pelo processo; a sessão `uhid` do P1 fecha e reabre; o automático espera."""
    from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal, classify

    sinal = GameSignal()
    for sessao in (True, False, True):
        bruto = classify(
            window_healthy=True, window_class_current=None, window_seen_age=None,
            profile_rule_match=False, marker=None, marker_pid_alive=False,
            exit_marker=None, session_open=sessao, now=1000.0,
            appid_de_jogo_vivo=4235410,
        )
        sinal.evaluate(bruto, session_open=sessao)
        assert sinal.authority == "game", f"a sessão {sessao} mexeu na autoridade"
        d = SimpleNamespace(display_authority=sinal.authority, store=StateStore())
        assert gp._recriacao_bloqueada_por_jogo(
            d, origin="autoswitch", motivo="troca_de_mascara:dualsense->xbox") is True


def _sinal_que_vai(d: Any, de: str, para_inputs: dict[str, Any]) -> None:
    """O `_sync_game_signal` de verdade, com o sinal em `de` e as evidências dadas."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    from hefesto_dualsense4unix.daemon.subsystems.game_signal import GameSignal

    sinal = GameSignal()
    sinal.evaluate(de, session_open=False)  # type: ignore[arg-type]
    d._game_signal = sinal
    d._executor = ThreadPoolExecutor(max_workers=1)
    d._gather_game_signal_inputs = lambda: dict(para_inputs)
    try:
        asyncio.run(d._sync_game_signal())
    finally:
        d._executor.shutdown(wait=True)


_SEM_JOGO = {
    "window_healthy": True, "window_class_current": None, "window_seen_age": None,
    "profile_rule_match": False, "marker": None, "marker_pid_alive": False,
    "marker_pid": None, "exit_marker": None, "exit_pid": None,
    "appid_de_jogo_vivo": None, "session_open": False, "now": 1000.0,
}


def test_o_jogo_que_fecha_solta_a_trava_do_lancamento() -> None:
    """O jogo devolve a autoridade (`game` → `daemon`): a trava do lançamento acaba, e diz."""
    d = _daemon()
    gp.start_gamepad_emulation(d, "dualsense", origin="profile")
    d._pad_travado_pelo_lancamento = (4235410, 1000)

    with structlog.testing.capture_logs() as diario:
        _sinal_que_vai(d, "game", _SEM_JOGO)

    assert d.display_authority == "daemon"
    assert d._pad_travado_pelo_lancamento is None
    assert [x["motivo"] for x in _linhas(diario, "pad_do_lancamento_destravado")] == [
        "o_jogo_devolveu_a_autoridade"]
    assert gp.start_gamepad_emulation_desfecho(d, "xbox", origin="profile") == gp.EMU_APLICADO


def test_o_sinal_que_nao_sabe_nao_solta_a_trava_do_lancamento() -> None:
    """`game` → `unknown` (o detector cego, sem evidência) é «não sei»: a trava fica."""
    d = _daemon()
    d._pad_travado_pelo_lancamento = (4235410, 1000)

    _sinal_que_vai(d, "game", dict(_SEM_JOGO, window_healthy=False))

    assert d.display_authority == "unknown"
    assert d._pad_travado_pelo_lancamento == (4235410, 1000)


def test_o_appid_em_cena_so_vale_com_o_jogo_na_autoridade() -> None:
    """O appid da evidência (o marcador vivo, ou o processo) só responde com o sinal em `game`."""
    d = _daemon()
    _sinal_que_vai(d, "unknown", dict(_SEM_JOGO, appid_de_jogo_vivo=4235410))
    assert (d.display_authority, d.appid_em_cena) == ("game", 4235410)

    _sinal_que_vai(d, "game", _SEM_JOGO)
    assert (d.display_authority, d.appid_em_cena) == ("daemon", None)
