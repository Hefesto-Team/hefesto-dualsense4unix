"""O controle volta ao Linux quando o Hefesto não sobe.

O-CONTROLE-VOLTA-AO-LINUX-QUANDO-O-HEFESTO-NAO-SOBE-01.

A DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01 conta a graça desde que o
ÚLTIMO cliente do broker some. O Hefesto que nunca sobe (o serviço desabilitado,
ou em ``failed`` antes de falar com o broker) não deixa cliente nenhum, e o
broker que nasce sem cliente nunca conta a graça: o controle fica fechado, sem
dono. A cura é a evidência POSITIVA do login, uma unit de usuário de presença
que manda o ``ping`` de sempre e fecha, e não um relógio desde o início do
broker (o daemon de verdade chega 34 s a 35 min depois dele).

A mesa de mentira é a da ``test_o_broker_esquece_o_controle_que_saiu.py``: o
``BrokerState``, o ``Broker``, o ``FsAclOps`` e o validador de produção, num
``/sys`` e num ``/dev`` em ``tmp_path``. O ``--ping`` roda como processo de
verdade e fala com o broker por um socket de verdade; o relógio é injetado.
"""
from __future__ import annotations

import os
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.broker.hidraw_broker import Broker, BrokerState
from hefesto_dualsense4unix.utils import identidade
from tests.unit import test_o_broker_esquece_o_controle_que_saiu as _mesa_de_mentira
from tests.unit.test_desligar_o_hefesto_devolve_o_controle_ao_linux import (
    OS_SEIS,
    Relogio,
    _aberto_para_a_sessao,
    _fechado,
    _tudo_do_aparelho,
)
from tests.unit.test_o_broker_esquece_o_controle_que_saiu import UID, Mesa, _retrato

mesa = _mesa_de_mentira.mesa

RAIZ = Path(__file__).resolve().parents[2]
GRACA = hb.GRACA_DA_ENTREGA_S
PRESENCA = "hefesto-dualsense4unix-presenca.service"
UNIT_PRESENCA = RAIZ / "assets" / PRESENCA
UNIT_DAEMON = RAIZ / "assets" / "hefesto-dualsense4unix.service"
UNIT_BROKER = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service"
#: O pad do Hefesto e um externo: a entrega não os toca.
OS_DE_FORA = (("hidraw11", "pad"), ("hidraw12", "teclado"))


def _estado(mesa: Mesa, *, marca: Path | None = None) -> tuple[BrokerState, list[str]]:
    diario: list[str] = []
    st = BrokerState(
        allowed_uid=UID,
        ops=mesa.ops(),
        dev_root=str(mesa.dev),
        sys_class_hidraw=str(mesa.sys_hidraw),
        sys_class_bluetooth=str(mesa.bluetooth),
        dev_input_root=str(mesa.dev_input),
        sys_class_input=str(mesa.sys_input),
        log=lambda evento, **_campos: diario.append(evento),
        sleep_fn=lambda _s: None,
        no_nasce_fechado=True,
        marca_da_entrega=None if marca is None else str(marca),
    )
    return st, diario


def _nascer_todos(mesa: Mesa) -> None:
    for n, (base, tipo) in enumerate((*OS_SEIS, *OS_DE_FORA), start=1):
        mesa.nascer(base, tipo, n)


def _retrato_de_fora(mesa: Mesa) -> list[tuple[str, tuple[int, bytes | None]]]:
    return [
        (no.name, _retrato(no))
        for base, _ in OS_DE_FORA
        for no in [mesa.dev / base, *mesa.aparelhos[base].entradas]
    ]


class Bancada:
    """O broker de produção num socket de verdade, servido por este processo."""

    def __init__(self, mesa: Mesa, pasta: Path) -> None:
        self.mesa = mesa
        self.relogio = Relogio()
        self.st, _ = _estado(mesa)
        self.eventos: list[str] = []
        self.sock_path = pasta / "b.sock"
        escuta = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        escuta.bind(str(self.sock_path))
        escuta.listen(4)
        self.broker = Broker(
            self.st,
            escuta,
            peercred_fn=lambda _s: (4242, UID, UID),
            log=lambda evento, **_k: self.eventos.append(evento),
            graca_da_entrega_s=GRACA,
            relogio=self.relogio,
        )

    def ping(self, pasta: Path, *argumentos: str) -> int:
        """O ``--ping`` como a unit de presença o roda, com o broker servindo."""
        casa = pasta / "casa"
        casa.mkdir(exist_ok=True)
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(casa),
            "XDG_STATE_HOME": str(casa / "estado"),
            "XDG_CONFIG_HOME": str(casa / "config"),
            "XDG_RUNTIME_DIR": str(casa / "run"),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "HEFESTO_BROKER_SOCKET": str(self.sock_path),
        }
        processo = subprocess.Popen(
            [sys.executable, "-m", "hefesto_dualsense4unix.integrations.hidraw_broker_client",
             *argumentos],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        abertos = self.eventos.count("peer_accepted") - self.eventos.count("peer_closed")
        prazo = time.monotonic() + 30
        while time.monotonic() < prazo:
            self.broker.step(timeout=0.05)
            if processo.poll() is not None and self.eventos.count("peer_accepted") - \
                    self.eventos.count("peer_closed") <= abertos:
                break
        else:
            processo.kill()
            pytest.fail("o --ping não terminou")
        for _ in range(5):
            self.broker.step(timeout=0.02)
        return int(processo.returncode)

    def tique(self, segundos: float) -> None:
        self.relogio.passa(segundos)
        self.broker.tique_da_entrega()


@pytest.fixture
def pasta() -> Iterator[Path]:
    """Curta: o caminho de um socket AF_UNIX cabe em 108 bytes."""
    caminho = Path(tempfile.mkdtemp(prefix="pres"))
    yield caminho
    shutil.rmtree(caminho, ignore_errors=True)


@pytest.fixture
def bancada(mesa: Mesa, pasta: Path) -> Bancada:
    _nascer_todos(mesa)
    return Bancada(mesa, pasta)


def _os_seis_fechados(mesa: Mesa) -> bool:
    return all(_fechado(no) for base, _ in OS_SEIS for no in _tudo_do_aparelho(mesa, base))


# --- 1. O ping da presença é a evidência do login ---------------------------------


def test_o_boot_sem_login_nunca_entrega(bancada: Bancada) -> None:
    """MORDIDA: troque o ``None`` do ``_sem_cliente_desde`` do ``Broker.__init__``
    por ``relogio()`` e o broker entrega antes do daemon (o login chega em +304 s)."""
    bancada.tique(GRACA * 20)
    assert bancada.st.entregue is False
    assert _os_seis_fechados(bancada.mesa)


def test_o_ping_da_presenca_entrega_os_seis_depois_da_graca(
    bancada: Bancada, pasta: Path
) -> None:
    """MORDIDA: o ``--ping`` sair sem conectar, e nada é entregue."""
    de_fora = _retrato_de_fora(bancada.mesa)
    assert bancada.ping(pasta, "--ping") == 0
    assert "peer_accepted" in bancada.eventos, "o --ping não chegou ao broker"
    bancada.tique(GRACA - 1)
    assert bancada.st.entregue is False
    assert _os_seis_fechados(bancada.mesa)
    bancada.tique(1.0)
    assert bancada.st.entregue is True
    for base, tipo in OS_SEIS:
        for no in _tudo_do_aparelho(bancada.mesa, base):
            assert _aberto_para_a_sessao(no), f"{tipo} {no.name} não voltou à sessão"
    assert _retrato_de_fora(bancada.mesa) == de_fora, "a entrega tocou o pad ou o externo"


def test_com_o_hefesto_de_pe_o_ping_nao_entrega(bancada: Bancada, pasta: Path) -> None:
    daemon, _ponta = socket.socketpair()
    assert bancada.broker.register_client(daemon) is not None
    assert bancada.ping(pasta, "--ping") == 0
    bancada.tique(GRACA * 3)
    assert bancada.st.entregue is False
    assert _os_seis_fechados(bancada.mesa)


def test_o_ping_sem_broker_diz_que_nao_chegou(pasta: Path, mesa: Mesa) -> None:
    b = Bancada(mesa, pasta)
    b.sock_path.unlink()
    assert b.ping(pasta, "--ping") != 0


# --- 2. A unit de presença: quando roda ------------------------------------------


def _diretivas(unit: Path, chave: str) -> list[str]:
    return [
        linha.split("=", 1)[1].strip()
        for linha in unit.read_text(encoding="utf-8").splitlines()
        if linha.startswith(f"{chave}=")
    ]


_SYSTEMCTL = """#!/bin/sh
printf '%s\\n' "$*" >> "{log}"
case "$*" in
  *is-enabled*) [ "$ESTADO_HABILITADO" = 1 ] ;;
  *is-failed*) [ "$ESTADO_FALHOU" = 1 ] ;;
  *) exit 3 ;;
esac
"""


@pytest.mark.parametrize(("habilitado", "falhou", "roda"), [
    (True, False, False),
    (False, False, True),
    (True, True, True),
])
def test_a_condicao_da_presenca(tmp_path: Path, habilitado: bool, falhou: bool,
                                roda: bool) -> None:
    """MORDIDA: inverter a condição (``is-enabled`` sem o ``!``)."""
    (condicao,) = _diretivas(UNIT_PRESENCA, "ExecCondition")
    falsos = tmp_path / "bin"
    falsos.mkdir()
    log = tmp_path / "systemctl.log"
    sc = falsos / "systemctl"
    sc.write_text(_SYSTEMCTL.format(log=log), encoding="utf-8")
    sc.chmod(0o755)
    env = {"PATH": f"{falsos}:/usr/bin:/bin", "ESTADO_HABILITADO": str(int(habilitado)),
           "ESTADO_FALHOU": str(int(falhou))}
    saida = subprocess.run(shlex.split(condicao), env=env, capture_output=True, timeout=30,
                           check=False)
    assert (saida.returncode == 0) is roda, (condicao, saida)
    perguntas = log.read_text(encoding="utf-8").splitlines()
    assert perguntas, "a condição não perguntou ao systemctl"
    unit_daemon = identidade.atual().unit_daemon
    for pergunta in perguntas:
        assert pergunta.split()[-1] == unit_daemon, pergunta
        assert "--user" in pergunta.split(), pergunta


def test_a_presenca_e_um_ping_de_uma_vez_no_login() -> None:
    assert _diretivas(UNIT_PRESENCA, "Type") == ["oneshot"]
    (inicio,) = _diretivas(UNIT_PRESENCA, "ExecStart")
    argv = shlex.split(inicio.lstrip("-"))
    assert argv[1:] == ["-m", "hefesto_dualsense4unix.integrations.hidraw_broker_client",
                        "--ping"], argv
    assert argv[0] == "__PYTHON__"
    assert _diretivas(UNIT_PRESENCA, "WantedBy") == ["default.target"]


def test_o_daemon_que_falha_chama_a_presenca() -> None:
    assert PRESENCA in _diretivas(UNIT_DAEMON, "OnFailure")


def test_o_ping_nao_retoma_o_esconderijo() -> None:
    assert "ping" not in hb.PEDIDOS_QUE_RETOMAM


# --- 3. A unit nova em toda rota --------------------------------------------------


def _texto(caminho: str) -> str:
    return (RAIZ / caminho).read_text(encoding="utf-8")


def test_o_install_copia_e_habilita_a_presenca() -> None:
    texto = _texto("install.sh")
    assert f"assets/{PRESENCA}" in texto
    assert 'enable --now "${PRESENCA_UNIT_NAME}"' in texto
    assert '__PYTHON__|${VENV_DIR}/bin/python' in texto


@pytest.mark.parametrize("caminho", ["uninstall.sh", "scripts/purge.sh"])
def test_o_uninstall_e_o_purge_levam_a_presenca(caminho: str) -> None:
    texto = _texto(caminho)
    assert f"disable --now {PRESENCA}" in texto, caminho
    assert f"systemd/user/{PRESENCA}" in texto, caminho


def test_o_deb_leva_a_presenca_com_o_python_dele() -> None:
    """MORDIDA: tirar a presença de ``UNITS_DE_PACOTE`` do renderizador único."""
    from hefesto_dualsense4unix.utils import units_de_usuario

    texto = _texto("scripts/build_deb.sh")
    assert PRESENCA in units_de_usuario.UNITS_DE_PACOTE
    assert "utils/units_de_usuario.py" in texto
    assert '--python "${FINAL_VENV}/bin/python"' in texto


def test_a_chave_nao_desliga_a_presenca() -> None:
    """O ``off`` desliga o Hefesto; a presença é o que devolve o controle depois."""
    assert PRESENCA not in _texto("scripts/hefesto-chave.sh")


# --- 4. O broker reiniciado com o Hefesto parado continua entregue ----------------


def test_a_marca_nasce_com_a_entrega_e_some_com_a_retomada(mesa: Mesa, tmp_path: Path) -> None:
    _nascer_todos(mesa)
    marca = tmp_path / "run" / "entregue"
    marca.parent.mkdir()
    st, _ = _estado(mesa, marca=marca)
    st.entregar_ao_linux()
    assert marca.is_file()
    st.retomar_o_esconderijo()
    assert not marca.exists()


class _Gravador:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __call__(self, nome: str) -> Any:
        def gravar(*_a: Any, **_k: Any) -> list[str]:
            self.chamadas.append(nome)
            return []
        return gravar


@pytest.fixture
def sem_maquina(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Gravador:
    """Nada do ``main`` alcança o ``/sys`` de verdade."""
    g = _Gravador()
    monkeypatch.setattr(hb, "fechar_todo_fisico", g("fechar"))
    monkeypatch.setattr(hb, "restore_all_physical", g("abrir"))
    monkeypatch.setattr(hb.PadUsbOps, "desmontar_todos", lambda _self: [])
    monkeypatch.setattr(hb, "MARCA_DA_ENTREGA_PATH", str(tmp_path / "entregue"))
    monkeypatch.setattr(hb, "_log", lambda *_a, **_k: None)
    monkeypatch.setenv(hb.ALLOWED_UID_ENV, str(UID))
    monkeypatch.setenv(hb.NO_NASCE_FECHADO_ENV, "1")
    return g


@pytest.mark.parametrize("com_marca", [False, True])
def test_o_broker_que_nasce_com_a_marca_nao_fecha(
    sem_maquina: _Gravador, tmp_path: Path, com_marca: bool
) -> None:
    if com_marca:
        (tmp_path / "entregue").write_text("", encoding="ascii")
    assert hb.main(["--fechar-tudo-e-sair"]) == 0
    assert hb._o_repouso_do_inicio(UID, no_nasce_fechado=True) is com_marca
    esperado = [] if com_marca else ["fechar", "fechar"]
    assert sem_maquina.chamadas == esperado


@pytest.mark.parametrize("com_marca", [False, True])
def test_o_broker_que_herda_a_entrega_retoma_quando_o_hefesto_volta(
    sem_maquina: _Gravador, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, com_marca: bool
) -> None:
    """MORDIDA: tirar o ``state.entregue = herdada`` do ``main``.

    O primeiro ``hide`` do Hefesto que volta só retoma (fecha o físico) com o
    estado ``entregue``: sem ele, o físico que a marca deixou aberto continua
    aberto com o Hefesto de pé, e o jogo vê o físico e o pad.
    """
    if com_marca:
        (tmp_path / "entregue").write_text("", encoding="ascii")
    vistos: list[BrokerState] = []

    class _BrokerQueGuarda:
        def __init__(self, state: BrokerState, _escuta: object, **_k: object) -> None:
            self._state = state
            self._graca_da_entrega_s = GRACA
            self.stopping = False

        def run(self) -> None:
            vistos.append(self._state)

    monkeypatch.setattr(hb, "Broker", _BrokerQueGuarda)
    monkeypatch.setattr(hb, "_sd_listen_socket", lambda: object())
    monkeypatch.setattr(hb, "_sd_notify", lambda _m: None)
    monkeypatch.setattr(hb.signal, "signal", lambda *_a: None)
    assert hb.main([]) == 0
    (state,) = vistos
    assert state.entregue is com_marca
    assert state._marca_da_entrega == hb.MARCA_DA_ENTREGA_PATH
    assert sem_maquina.chamadas == ([] if com_marca else ["fechar"])


def test_a_marca_e_um_arquivo_e_nao_um_link(sem_maquina: _Gravador, tmp_path: Path) -> None:
    (tmp_path / "alvo").write_text("", encoding="ascii")
    (tmp_path / "entregue").symlink_to(tmp_path / "alvo")
    assert hb._o_repouso_do_inicio(UID, no_nasce_fechado=True) is False
    assert sem_maquina.chamadas == ["fechar"]


def test_a_unit_do_broker_deixa_gravar_a_marca() -> None:
    gravaveis = " ".join(_diretivas(UNIT_BROKER, "ReadWritePaths")).split()
    assert "-/run/hefesto-hidraw-broker" in gravaveis
    assert Path(hb.MARCA_DA_ENTREGA_PATH).parent == Path(hb.DEFAULT_SOCKET_PATH).parent


# --- 5. O bloco do install, rodado com dublês ---------------------------------------


def _bloco_da_presenca() -> str:
    texto = _texto("install.sh")
    inicio = texto.index("# 7a'. A PRESENÇA")
    corpo = texto.index("\n", texto.index("# ----", inicio)) + 1
    fim = texto.index("\n# ----", corpo)
    return texto[corpo:fim]


@pytest.mark.parametrize("pular", [0, 1])
def test_o_install_veste_o_python_da_venv_e_habilita(tmp_path: Path, pular: int) -> None:
    """MORDIDA: tirar o ``sed`` do ``__PYTHON__`` (a unit chegaria com o marcador cru)."""
    falsos = tmp_path / "bin"
    falsos.mkdir()
    log = tmp_path / "systemctl.log"
    sc = falsos / "systemctl"
    sc.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\nexit 0\n', encoding="utf-8")
    sc.chmod(0o755)
    destino = tmp_path / "casa" / ".config" / "systemd" / "user"
    script = (
        "set -euo pipefail\n"
        'warn() { printf "WARN: %s\\n" "$*"; }\n'
        '_faria() { printf "FARIA: %s\\n" "$*"; }\n'
        f"SKIP_SYSTEMD={pular}\nDRY_RUN=0\n"
        f"ROOT_DIR='{RAIZ}'\nVENV_DIR='/opt/venv-de-mentira'\n"
        f"DAEMON_USER_UNIT_DIR='{destino}'\n"
        f"{_bloco_da_presenca()}\n"
    )
    saida = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30,
                           check=False, env={"PATH": f"{falsos}:/usr/bin:/bin",
                                             "HOME": str(tmp_path / "casa")})
    assert saida.returncode == 0, saida.stderr
    unit = destino / PRESENCA
    chamadas = log.read_text(encoding="utf-8") if log.exists() else ""
    if pular:
        assert not unit.exists() and chamadas == ""
        return
    texto = unit.read_text(encoding="utf-8")
    assert "__PYTHON__" not in texto
    assert "ExecStart=-/opt/venv-de-mentira/bin/python -m " in texto
    assert f"--user enable --now {PRESENCA}" in chamadas
