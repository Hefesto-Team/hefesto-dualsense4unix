"""Quem pede o reinício do serviço deixa o nome no diário.

Sprint QUEM-PEDE-O-REINICIO-DO-SERVICO-DEIXA-O-NOME-NO-DIARIO-01.

Medido em 22/11/2026: dez paradas e subidas do serviço entre 01h58 e 05h31 e o diário só trazia
`daemon_stop_requested` sem campo; nenhum caminho do produto dizia quem pedia. O que se prova:

1. a anotação (`utils/pedido_ao_servico.py`) grava uma linha por escrita inteira, lê só a recente
   (30 s na parada, 120 s na subida) e nunca levanta;
2. cada caminho do produto que pede ao systemd (bandeja, aba Sistema, troca adiada do install,
   linha de comando, instalador da unit, `o_basico`, `doctor`, `dsx_recover`, esquecer os
   controles) deixa a anotação com o nome dele ANTES do pedido: o systemd de mentira lê o arquivo
   no instante do pedido;
3. a anotação que falha não impede o pedido;
4. o serviço, ao parar, escreve `daemon_stop_requested quem=<nome>` (e `fora-do-produto` sem
   anotação recente), na subida `daemon_subiu_depois_de`, e a leitura roda fora do fio de quem
   parou: a parada não espera pela leitura;
5. uma régua por AST e por grep: nenhum pedido de `start`, `stop`, `restart` ou `try-restart` da
   unidade em `src/` e nos três scripts sem a anotação na mesma função.

MORDIDAS (22/11/2026): tirar a chamada à anotação de qualquer um dos pontos reprova a régua do
ponto e o caso dele; tirar `dizer_quem_pediu_a_parada` do `Daemon.stop` reprova o caso do diário
e `fora-do-produto` vira `quem` ausente.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.utils import pedido_ao_servico as pedido

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
SCRIPTS = RAIZ / "scripts"
sys.path.insert(0, str(SRC / "interface"))


@pytest.fixture(autouse=True)
def _o_runtime_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return tmp_path


def _o_que_o_systemd_leria(lido: list[Any]) -> Any:
    """O pedido de mentira: no instante do pedido, lê a anotação que está no arquivo."""

    def _ler(*_a: Any, **_k: Any) -> Any:
        lido.append(pedido.ler(30.0))
        return subprocess.CompletedProcess([], 0, "", "")

    return _ler


def test_a_anotacao_grava_uma_linha_e_le_so_a_recente() -> None:
    assert pedido.ler(30.0) is None
    assert pedido.anotar("restart", "bandeja", "reiniciar-do-menu")
    lido = pedido.ler(30.0)
    assert lido is not None
    assert (lido.verbo, lido.quem, lido.motivo, lido.pid) == (
        "restart", "bandeja", "reiniciar-do-menu", os.getpid())
    assert len(pedido.arquivo().read_text(encoding="utf-8").splitlines()) == 1
    assert pedido.ler(30.0, agora=time.time() + 31.0) is None
    assert pedido.ler(30.0, agora=time.time() + 5.0) is not None
    pedido.anotar("stop", "aba-sistema", "um\tmotivo\ncom quebra")
    outro = pedido.ler(30.0)
    assert outro is not None and outro.quem == "aba-sistema" and "\t" not in outro.motivo
    assert not list(pedido.arquivo().parent.glob("*.tmp"))


def test_a_anotacao_ilegivel_ou_sem_diretorio_nao_levanta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pedido.arquivo().parent.mkdir(parents=True, exist_ok=True)
    pedido.arquivo().write_text("lixo sem tabulação\n", encoding="utf-8")
    assert pedido.ler(30.0) is None
    ocupado = tmp_path / "ocupado"
    ocupado.write_text("sou um arquivo", encoding="utf-8")
    monkeypatch.setattr(pedido, "runtime_dir", lambda *a, **k: ocupado / "dentro")
    assert pedido.anotar("restart", "bandeja") is False


def test_a_subida_so_vale_para_start_e_restart() -> None:
    pedido.anotar("stop", "bandeja")
    assert pedido.a_subida_pedida() is None
    pedido.anotar("restart", "bandeja")
    subida = pedido.a_subida_pedida()
    assert subida is not None and subida.quem == "bandeja"


def test_a_bandeja_anota_antes_de_pedir_ao_systemd(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    lido: list[Any] = []
    monkeypatch.setattr(DaemonActionsMixin, "_invoke_systemctl",
                        lambda _s, args, **_k: _o_que_o_systemd_leria(lido)()
                        if args[0] in pedido.VERBOS else subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(ab, "repor_o_lancador", lambda: None)
    monkeypatch.setattr(ab, "garantir_a_bandeja", lambda: None)
    for verbo in ("restart", "stop", "start"):
        lido.clear()
        assert ab.mexer_no_servico(verbo)
        assert len(lido) == 1 and lido[0] is not None, verbo
        assert (lido[0].quem, lido[0].verbo) == ("bandeja", verbo)
        assert lido[0].motivo


def test_a_anotacao_que_falha_nao_impede_o_pedido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.app.actions import atos_da_bandeja as ab
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    ocupado = tmp_path / "ocupado"
    ocupado.write_text("arquivo no lugar da pasta", encoding="utf-8")
    monkeypatch.setattr(pedido, "runtime_dir", lambda *a, **k: ocupado / "dentro")
    pedidos: list[list[str]] = []
    monkeypatch.setattr(DaemonActionsMixin, "_invoke_systemctl",
                        lambda _s, args, **_k: pedidos.append(list(args))
                        or subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(ab, "repor_o_lancador", lambda: None)
    monkeypatch.setattr(ab, "garantir_a_bandeja", lambda: None)
    assert ab.mexer_no_servico("restart")
    assert any(p[0] == "restart" for p in pedidos)


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    from pacotes import a09_sistema as mod

    lido: list[Any] = []

    class _Janela:
        lido_no_pedido = lido

        def _invoke_systemctl(self, args: list[str], **_k: Any) -> Any:
            if args[0] in pedido.VERBOS:
                lido.append(pedido.ler(30.0))
            return subprocess.CompletedProcess(args, 0, "", "")

    mod._JANELA_ANTIGA[:] = [_Janela()]
    mod._LENTO.clear()
    yield mod
    mod._JANELA_ANTIGA.clear()
    mod._LENTO.clear()


def test_a_aba_sistema_anota_antes_de_pedir_ao_systemd(a09: ModuleType) -> None:
    lido = a09._matriz().lido_no_pedido
    for verbo, motivo in (("restart", "gesto-reiniciar"), ("stop", "gesto-desligar"),
                          ("start", "ativar-o-servico")):
        lido.clear()
        a09._systemctl(verbo, motivo)
        assert len(lido) == 1 and lido[0] is not None, verbo
        assert (lido[0].quem, lido[0].verbo, lido[0].motivo) == ("aba-sistema", verbo, motivo)
    lido.clear()
    a09._systemctl("enable")
    assert lido == []


def test_o_reinicio_que_passou_do_prazo_anota_o_start(
    a09: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    lido = a09._matriz().lido_no_pedido
    monkeypatch.setattr(a09, "_repor_o_lancador", lambda: None)
    a09._repor_quando_o_servico_voltar()
    assert lido and lido[0] is not None
    assert (lido[0].quem, lido[0].verbo) == ("aba-sistema", "start")


def test_a_troca_adiada_do_install_anota_antes_de_reiniciar() -> None:
    from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca

    lido: list[Any] = []

    def _rodar(cmd: Any) -> bool:
        if "restart" in cmd:
            lido.append(pedido.ler(30.0))
        return True

    feitos = troca.aplicar(["daemon"], rodar=_rodar, jogo_aberto=lambda: False)
    assert feitos == ["daemon"]
    assert len(lido) == 1 and lido[0] is not None
    assert (lido[0].quem, lido[0].verbo) == ("troca-do-install", "restart")


def test_o_instalador_da_unit_anota_com_o_nome_de_quem_chamou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.daemon import service_install as si

    lido: list[Any] = []
    monkeypatch.setattr(si.ServiceInstaller, "_systemctl",
                        lambda _s, *a, **_k: lido.append((a[0], pedido.ler(30.0))))
    si.ServiceInstaller().restart()
    si.ServiceInstaller(quem="linha-de-comando", motivo="daemon stop").stop()
    si.ServiceInstaller(dry_run=True).start()
    assert [(v, p.quem if p else None) for v, p in lido] == [
        ("restart", "instalacao-do-servico"), ("stop", "linha-de-comando"),
        ("start", "linha-de-comando")], lido
    assert lido[2][1].verbo == "stop", "o `dry_run` não anota: a anotação de antes segue"


def test_a_linha_de_comando_anota_com_o_proprio_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli.app import app
    from hefesto_dualsense4unix.daemon import service_install as si

    lido: list[Any] = []
    monkeypatch.setattr(si.ServiceInstaller, "_systemctl",
                        lambda _s, *a, **_k: lido.append((a[0], pedido.ler(30.0))))
    executor = CliRunner()
    for comando, verbo in (("restart", "restart"), ("stop", "stop")):
        lido.clear()
        assert executor.invoke(app, ["daemon", comando]).exit_code == 0
        assert len(lido) == 1 and lido[0][1] is not None
        assert (lido[0][0], lido[0][1].quem, lido[0][1].verbo) == (
            verbo, "linha-de-comando", verbo)
        assert lido[0][1].motivo == f"daemon {comando}"


def test_esquecer_os_controles_anota_o_stop_e_o_start(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import memoria_dos_controles as memoria

    lido: list[Any] = []

    def _rodar(cmd: list[str], **_k: Any) -> Any:
        if cmd[2] in pedido.VERBOS:
            lido.append((cmd[2], pedido.ler(30.0)))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.delenv(memoria.ENV_ENSAIO, raising=False)
    monkeypatch.setattr(memoria.subprocess, "run", _rodar)
    sistema = memoria.Sistema()
    sistema.parar_daemon()
    sistema.subir_daemon()
    assert [(v, p.quem if p else None) for v, p in lido] == [
        ("stop", "controles-esquecer"), ("start", "controles-esquecer")]


def _o_basico() -> ModuleType:
    caminho = SCRIPTS / "o_basico.py"
    if str(caminho.parent) not in sys.path:
        sys.path.insert(0, str(caminho.parent))
    spec = importlib.util.spec_from_file_location("o_basico_do_nome_no_diario", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["o_basico_do_nome_no_diario"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_o_basico_anota_antes_de_reiniciar_o_daemon() -> None:
    ob = _o_basico()
    lido: list[Any] = []

    def _rodar(cmd: list[str], _prazo: float) -> tuple[int, str]:
        lido.append(pedido.ler(30.0))
        return 1, "recusado de mentira"

    sessao = SimpleNamespace(
        maquina=SimpleNamespace(estado=lambda: {}, rodar=_rodar),
        declarar=lambda *a, **k: None)
    with pytest.raises(ob.Recusa):
        ob._reiniciar_o_daemon(sessao, "o --boot da sessão")
    assert len(lido) == 1 and lido[0] is not None
    assert (lido[0].quem, lido[0].verbo, lido[0].motivo) == (
        "o-basico", "restart", "o --boot da sessão")


def _funcao_do_shell(arquivo: Path, nome: str) -> str:
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    inicio = next(i for i, ln in enumerate(linhas) if ln.startswith(f"{nome}() {{"))
    fim = next(i for i in range(inicio, len(linhas)) if linhas[i] == "}")
    return "\n".join(linhas[inicio:fim + 1])


def test_o_doctor_e_o_recover_gravam_a_mesma_linha_que_o_python_le(
    tmp_path: Path,
) -> None:
    corpo = _funcao_do_shell(SCRIPTS / "doctor.sh", "anotar_o_pedido_ao_servico")
    subprocess.run(
        ["bash", "-c", f'APP_ID=hefesto-dualsense4unix\n{corpo}\n'
         'anotar_o_pedido_ao_servico try-restart doctor "--fix: a fila\ttem tabulação"'],
        check=True, env={**os.environ, "XDG_RUNTIME_DIR": str(tmp_path)})
    do_doctor = pedido.ler(30.0)
    assert do_doctor is not None
    assert (do_doctor.verbo, do_doctor.quem) == ("try-restart", "doctor")
    assert "\t" not in do_doctor.motivo and do_doctor.motivo.startswith("--fix")
    assert do_doctor.pid > 0
    pedido.arquivo().unlink()

    corpo = _funcao_do_shell(SCRIPTS / "dsx_recover.sh", "anotar_o_pedido")
    base = tmp_path / "run-user"
    subprocess.run(
        ["bash", "-c", f'APP_ID=hefesto-dualsense4unix\n{corpo}\n'
         'anotar_o_pedido 1234 "$(id -nu)" "a tempestade"'],
        check=True, env={**os.environ, "RUNTIME_BASE": str(base)})
    gravado = base / "1234" / "hefesto-dualsense4unix" / pedido.NOME_DO_ARQUIVO
    assert gravado.is_file()
    partes = gravado.read_text(encoding="utf-8").rstrip("\n").split("\t")
    assert partes[1:3] == ["restart", "dsx-recover"] and partes[4] == "a tempestade"
    assert float(partes[0]) == pytest.approx(time.time(), abs=30)


def _o_diario_da_parada(daemon: Any, esperar: str) -> dict[str, Any]:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    with capture_logs() as linhas:
        Daemon.stop(daemon)
        fim = time.monotonic() + 5.0
        while time.monotonic() < fim:
            achadas = [ln for ln in linhas if ln["event"] == esperar]
            if achadas:
                return dict(achadas[0])
            time.sleep(0.02)
    raise AssertionError(f"o diário não trouxe {esperar}: {linhas}")


def _um_daemon_para_parar() -> SimpleNamespace:
    return SimpleNamespace(_stop_event=asyncio.Event())


def test_a_parada_com_anotacao_recente_escreve_quem_pediu() -> None:
    pedido.anotar("restart", "bandeja", "reiniciar-do-menu")
    linha = _o_diario_da_parada(_um_daemon_para_parar(), "daemon_stop_requested")
    assert (linha["quem"], linha["motivo"], linha["verbo"]) == (
        "bandeja", "reiniciar-do-menu", "restart")


def test_a_parada_sem_anotacao_ou_com_anotacao_velha_diz_fora_do_produto() -> None:
    linha = _o_diario_da_parada(_um_daemon_para_parar(), "daemon_stop_requested")
    assert linha["quem"] == pedido.FORA_DO_PRODUTO
    pedido.arquivo().parent.mkdir(parents=True, exist_ok=True)
    pedido.arquivo().write_text(
        f"{time.time() - 31.0:.3f}\trestart\tbandeja\t{os.getpid()}\tvelha\n", encoding="utf-8")
    linha = _o_diario_da_parada(_um_daemon_para_parar(), "daemon_stop_requested")
    assert linha["quem"] == pedido.FORA_DO_PRODUTO


def test_a_leitura_da_anotacao_nao_atrasa_a_parada(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    solta = threading.Event()
    entrou = threading.Event()

    def _ler_devagar(*_a: Any, **_k: Any) -> Any:
        entrou.set()
        solta.wait(10.0)
        return None

    monkeypatch.setattr(pedido, "ler", _ler_devagar)
    daemon = _um_daemon_para_parar()
    try:
        inicio = time.monotonic()
        Daemon.stop(daemon)
        assert daemon._stop_event.is_set(), "a parada esperou pela leitura da anotação"
        assert time.monotonic() - inicio < 1.0
        assert entrou.wait(5.0), "a leitura não rodou fora do fio da parada"
    finally:
        solta.set()


def _a_subida_do_daemon(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.daemon import connection, lifecycle, subsystems
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador
    from hefesto_dualsense4unix.testing import FakeController

    estados = [ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                               transport="usb") for _ in range(5)]
    daemon = Daemon(
        controller=FakeController(transport="usb", states=estados),
        config=DaemonConfig(poll_hz=120, ipc_enabled=False, udp_enabled=False,
                            autoswitch_enabled=False))

    async def _subir(_d: Any, *, depois_do_controle: bool = False) -> None:
        daemon.stop()

    async def _nada(_d: Any) -> None:
        return None

    monkeypatch.setattr(lifecycle, "_importar_o_que_a_subida_usa", lambda: None)
    monkeypatch.setattr(o_padrao_do_computador, "migrar_uma_vez", lambda: None)
    monkeypatch.setattr(subsystems, "subir", _subir)
    monkeypatch.setattr(connection, "restore_last_profile", _nada)
    monkeypatch.setattr(connection, "reaplicar_som_em_todos_os_alvos", _nada)
    monkeypatch.setattr(connection, "reconnect_loop", lambda _d: asyncio.sleep(0))
    with capture_logs() as linhas:
        asyncio.run(asyncio.wait_for(daemon.run(), 20.0))
        fim = time.monotonic() + 3.0
        while time.monotonic() < fim and not any(
                ln["event"] == "daemon_subiu_depois_de" for ln in linhas):
            time.sleep(0.02)
        return [dict(ln) for ln in linhas]


def test_a_subida_diz_de_quem_foi_o_reinicio(monkeypatch: pytest.MonkeyPatch) -> None:
    pedido.anotar("restart", "aba-sistema", "gesto-reiniciar")
    linhas = _a_subida_do_daemon(monkeypatch)
    subida = [ln for ln in linhas if ln["event"] == "daemon_subiu_depois_de"]
    assert len(subida) == 1, linhas
    assert (subida[0]["quem"], subida[0]["verbo"]) == ("aba-sistema", "restart")


def test_a_subida_sem_pedido_do_produto_nao_inventa_quem(monkeypatch: pytest.MonkeyPatch) -> None:
    linhas = _a_subida_do_daemon(monkeypatch)
    assert not [ln for ln in linhas if ln["event"] == "daemon_subiu_depois_de"]


VERBOS_DA_UNIDADE = {"restart", "try-restart", "stop", "start"}
TERMINAIS = {"_invoke_systemctl", "_systemctl_do_usuario"}
TERMINAIS_POR_ARQUIVO = {"daemon/service_install.py": {"_systemctl"}}
OUTRAS_UNIDADES = ("bluetooth", ".path", "hefesto-bt-agent")
NOMES_DA_ANOTACAO = {"anotar", "_anotar_o_pedido"}


def _proprios(funcao: Any) -> list[Any]:
    """Os nós da função sem descer pelas funções aninhadas, que têm a própria vez."""
    import ast

    achados: list[Any] = []
    pilha = list(funcao.body)
    while pilha:
        no = pilha.pop()
        achados.append(no)
        for filho in ast.iter_child_nodes(no):
            if not isinstance(filho, ast.FunctionDef | ast.AsyncFunctionDef):
                pilha.append(filho)
    return achados


def _nome_da_chamada(chamada: Any) -> str:
    import ast

    f = chamada.func
    if isinstance(f, ast.Attribute):
        return str(f.attr)
    return str(f.id) if isinstance(f, ast.Name) else ""


def _sem_anotacao(texto: str, relativo: str) -> list[str]:
    """As funções que pedem o serviço ao systemd e não chamam a anotação: `arquivo:linha nome`."""
    import ast

    terminais = TERMINAIS | TERMINAIS_POR_ARQUIVO.get(relativo, set())
    faltam: list[str] = []
    for funcao in ast.walk(ast.parse(texto)):
        if not isinstance(funcao, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        nos = _proprios(funcao)
        chamadas = [n for n in nos if isinstance(n, ast.Call)]
        constantes = [str(n.value) for n in nos if isinstance(n, ast.Constant)
                      and isinstance(n.value, str)]
        pede_systemctl = any(_nome_da_chamada(c) in terminais for c in chamadas) or any(
            isinstance(a, ast.List | ast.Tuple) and a.elts
            and isinstance(a.elts[0], ast.Constant) and a.elts[0].value == "systemctl"
            for c in chamadas for a in [*c.args, *(x for g in c.args
                                                   if isinstance(g, ast.List) for x in g.elts)])
        if not pede_systemctl or not VERBOS_DA_UNIDADE & set(constantes):
            continue
        if any(o in c for c in constantes for o in OUTRAS_UNIDADES):
            continue
        if not any(_nome_da_chamada(c) in NOMES_DA_ANOTACAO for c in chamadas):
            faltam.append(f"{relativo}:{funcao.lineno} {funcao.name}")
    return faltam


def _os_arquivos_do_python() -> list[Path]:
    return [*sorted(SRC.rglob("*.py")), SCRIPTS / "o_basico.py"]


def _relativo(arquivo: Path) -> str:
    base = SRC if SRC in arquivo.parents else SCRIPTS
    return str(arquivo.relative_to(base))


def test_nenhum_pedido_de_python_ao_systemd_fica_sem_anotacao() -> None:
    faltam: list[str] = []
    for arquivo in _os_arquivos_do_python():
        faltam += _sem_anotacao(arquivo.read_text(encoding="utf-8"), _relativo(arquivo))
    assert not faltam, "pede ao systemd o serviço sem `pedido_ao_servico.anotar`: " + "; ".join(
        faltam)


def test_a_regua_do_python_enxerga_cada_ponto_quando_a_anotacao_sai() -> None:
    pontos = {"atos_da_bandeja.py", "a09_sistema.py", "troca_no_fim_do_jogo.py",
              "service_install.py", "o_basico.py", "memoria_dos_controles.py"}
    com_anotacao = [a for a in _os_arquivos_do_python() if a.name in pontos]
    assert {a.name for a in com_anotacao} == pontos
    for arquivo in com_anotacao:
        texto = arquivo.read_text(encoding="utf-8")
        mordido = re.sub(r"(?<!def )\b(_anotar_o_pedido|pedido_ao_servico\.anotar)\(", "nada(",
                         texto)
        assert _sem_anotacao(mordido, _relativo(arquivo)), (
            f"{arquivo.name}: sem a anotação a régua não reprovou")


COMANDO_DO_SERVICO = re.compile(
    r'^\s*systemctl --user (try-restart|restart|stop|start) "\$\{APP_ID\}\.service"')


def _scripts_sem_anotacao(texto: str, nome: str) -> list[str]:
    linhas = texto.splitlines()
    faltam: list[str] = []
    for i, linha in enumerate(linhas):
        if not COMANDO_DO_SERVICO.match(linha):
            continue
        inicio = max(j for j in range(i + 1) if re.match(r"^[a-z_]+\(\) \{", linhas[j]))
        if not any(linhas[j].strip().startswith("anotar_o_pedido")
                   for j in range(inicio + 1, i)):
            faltam.append(f"{nome}:{i + 1}")
    return faltam


def test_nenhum_pedido_de_shell_ao_systemd_fica_sem_anotacao() -> None:
    achados = 0
    for nome in ("doctor.sh", "dsx_recover.sh"):
        texto = (SCRIPTS / nome).read_text(encoding="utf-8")
        achados += len([ln for ln in texto.splitlines() if COMANDO_DO_SERVICO.match(ln)])
        assert not _scripts_sem_anotacao(texto, nome), nome
    assert achados == 2, "a régua deixou de enxergar os pedidos do shell"


def test_a_regua_do_shell_enxerga_cada_ponto_quando_a_anotacao_sai() -> None:
    for nome in ("doctor.sh", "dsx_recover.sh"):
        texto = (SCRIPTS / nome).read_text(encoding="utf-8")
        mordido = re.sub(r"^(\s*)anotar_o_pedido\w*\b.*$", r"\1true", texto, flags=re.M)
        assert _scripts_sem_anotacao(mordido, nome), f"{nome}: a régua não reprovou"
