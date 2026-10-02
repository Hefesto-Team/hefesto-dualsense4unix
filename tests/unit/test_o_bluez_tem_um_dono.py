"""O D-Bus do BlueZ tem UM dono — BLUEZ-UM-DONO-01 (23/09/2026)."""

from __future__ import annotations

import ast
import contextlib
import io
import re
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
DONO = SRC / "integrations" / "bluez_dbus.py"


@pytest.fixture()
def sem_subprocesso(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Qualquer subprocesso aberto pelo dono vira uma anotação — e uma falha."""
    abertos: list[Any] = []

    def anotar(*args: Any, **kwargs: Any) -> Any:
        abertos.append(args)
        raise AssertionError("o dono abriu um subprocesso")

    monkeypatch.setattr(bd.subprocess, "run", anotar)
    return abertos


@pytest.fixture()
def trava_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "radio.lock"
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(caminho))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    return caminho


def _publicos(classe: type) -> set[str]:
    return {
        nome
        for nome in dir(classe)
        if not nome.startswith("_") and callable(getattr(classe, nome))
    }


def _sem_classificacao(*classes: type) -> set[str]:
    conhecidos = set(bd.ESCRITAS) | set(bd.LEITURAS) | set(bd.CICLO)
    return set().union(*(_publicos(c) for c in classes)) - conhecidos


def test_todo_metodo_publico_do_dono_e_leitura_escrita_ou_ciclo() -> None:
    """Um método público novo que escreve e não está em ``ESCRITAS`` escaparia"""
    assert _sem_classificacao(bd.LeitorDoBluez, bd.PeloBusctl, bd.DonoVivo) == set()

    class ComUmAMais(bd.DonoVivo):
        def religar_tudo(self) -> None:
            return None

    assert _sem_classificacao(ComUmAMais) == {"religar_tudo"}


def test_sob_a_suite_o_dono_do_processo_nunca_e_o_vivo_do_sistema() -> None:
    assert isinstance(bd.dono(), bd.PeloBusctl)
    assert bd.enderecos_pelo_kernel() is None
    assert bd.lugares_dos_adaptadores() == {}


def test_a_porta_de_fuga_e_declarada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bd.RADIO_DE_VERDADE_NA_SUITE, "1")
    assert bd.a_suite_esta_rodando() is False


def _segurar_a_trava(segundos: float, pronto: threading.Event, soltou: list[float]) -> None:
    with diario_do_radio.trava_do_radio("watchdog-de-mentira", prazo_s=1.0):
        pronto.set()
        time.sleep(segundos)
        soltou.append(time.monotonic())


@pytest.fixture()
def travas_pegas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Quem pegou a trava do rádio de verdade — o atalho reentrante não conta."""
    pegas: list[str] = []
    original = diario_do_radio.trava_do_radio

    @contextlib.contextmanager
    def contando(quem: str, **kwargs: Any) -> Iterator[float]:
        pegas.append(quem)
        with original(quem, **kwargs) as espera:
            yield espera

    monkeypatch.setattr(diario_do_radio, "trava_do_radio", contando)
    return pegas


class _ProcessoVivo:
    """A busca da ponte, de pé até alguém fechá-la."""

    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self._vivo = True

    def poll(self) -> int | None:
        return None if self._vivo else 0

    def terminate(self) -> None:
        self._vivo = False

    kill = terminate

    def wait(self, timeout: float | None = None) -> int:
        return 0


_FERRAMENTAS = frozenset({"busctl", "bluetoothctl", "gdbus", "dbus-send"})

_NOME_DO_BLUEZ = re.compile(r"org\.bluez(\.[A-Za-z0-9_]+)*")

_COMECA_FALANDO_COM_O_BLUEZ = re.compile(
    r"^(?:busctl|bluetoothctl|gdbus|dbus-send)(?:\s|$)|^org\.bluez(?:\.|$)"
)


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = no.body
            primeiro = corpo[0] if corpo else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                ids.add(id(primeiro.value))
    return ids


def segundos_donos(fonte: str) -> list[tuple[int, str]]:
    """Os literais que falam com o BlueZ num arquivo. Docstring e comentário não"""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str) or id(no) in docs:
            continue
        valor = no.value.strip()
        if (
            valor in _FERRAMENTAS
            or _NOME_DO_BLUEZ.fullmatch(valor)
            or _COMECA_FALANDO_COM_O_BLUEZ.match(valor)
        ):
            achados.append((no.lineno, valor))
    return achados


def test_a_regua_de_dono_morde_um_executor_novo() -> None:
    """MORDIDA embutida: um executor novo, escrito como os nove de antes, reprova."""
    novo = (
        "import subprocess\n"
        "def espiar(caminho):\n"
        "    '''Lê o org.bluez pelo busctl — isto é docstring e não conta.'''\n"
        "    return subprocess.run(['busctl', 'get-property', 'org.bluez', caminho,\n"
        "                           'org.bluez.Device1', 'Connected'])\n"
    )
    assert [v for _l, v in segundos_donos(novo)] == [
        "busctl", "org.bluez", "org.bluez.Device1"
    ]


def test_a_regua_de_dono_morde_a_linha_inteira_e_a_f_string() -> None:
    """As duas formas que o ``fullmatch`` deixava passar, achadas na conferência."""
    novo = (
        "import subprocess\n"
        "SEM_BLUEZ = 'o `org.bluez` não respondeu no barramento'\n"
        "def derrubar(caminho, interface):\n"
        "    subprocess.run(f'busctl call org.bluez {caminho} Disconnect', shell=True)\n"
        "    return f'org.bluez.{interface}'\n"
    )
    assert sorted(v for _l, v in segundos_donos(novo)) == ["busctl call org.bluez", "org.bluez."]


def test_ninguem_fala_com_o_bluez_fora_do_dono() -> None:
    """Um ``busctl`` ou um ``org.bluez`` em ``src/`` fora de ``bluez_dbus.py`` reprova."""
    fora: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == DONO:
            continue
        for linha, valor in segundos_donos(arquivo.read_text(encoding="utf-8")):
            fora.append(f"{arquivo.relative_to(RAIZ)}:{linha}: {valor!r}")
    assert fora == [], "segundo dono do BlueZ:\n" + "\n".join(fora)


def test_o_dono_tem_os_nomes_que_a_regua_procura() -> None:
    """Sem isto, a régua acima passaria sobre um dono que não os tem."""
    assert {v for _l, v in segundos_donos(DONO.read_text(encoding="utf-8"))} >= {
        "busctl", "org.bluez", "org.bluez.Adapter1", "org.bluez.Device1", "org.bluez.Agent1",
    }


class _KernelDeMentira:
    """O ``LeitorDoKernel`` do AR-MEDIDO-01, com o que o ioctl responderia."""

    class _Leitura:
        def __init__(self, endereco: str) -> None:
            self.endereco = endereco

    def __init__(self, enderecos: dict[int, str]) -> None:
        self._enderecos = enderecos

    def adaptadores(self) -> list[int]:
        return sorted(self._enderecos)

    def ler(self, numero: int) -> Any:
        return self._Leitura(self._enderecos[numero])


def test_o_lugar_e_o_caminho_pci_e_as_portas() -> None:
    assert bd.lugar_de("0000:0c:00.3", "1.1.4") == "pci-0000:0c:00.3-usb-0:1.1.4"
    assert bd.lugar_de("0000:0c:00.3", "") == "pci-0000:0c:00.3"
    assert bd.lugar_de("", "1.4") == ""


def test_dongle_trocado_na_mesma_porta_e_outra_frase() -> None:
    (mudanca,) = bd.perceber_as_mudancas({"p1": "aa:bb:cc:00:00:01"}, {"p1": "aa:bb:cc:00:00:02"})
    assert mudanca.tipo == "trocado"
    assert mudanca.frase == "O adaptador desta porta foi trocado."
    assert bd.perceber_as_mudancas({}, {"p1": "aa:bb:cc:00:00:01"}) == ()


@pytest.mark.parametrize(
    ("bruto", "valor"),
    [
        ('{"type":"s","data":"Nintendo MeowSystem"}', "Nintendo MeowSystem"),
        ('s "Nintendo MeowSystem"', "Nintendo MeowSystem"),
        ('{"type":"b","data":true}', True),
        ("b false", False),
        ("u 9480", 9480),
        ("", None),
        (None, None),
    ],
)
def test_o_desembrulho_nao_mutila_nome_com_espaco(bruto: str | None, valor: Any) -> None:
    assert bd.desembrulhar(bruto) == valor
