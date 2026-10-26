"""O sistema pergunta ao udev pela biblioteca dele, e não lê o arquivo interno dele.

O banco do udev (`/run/udev/data/c<maj>:<min>`) é interno do systemd, que muda o
formato quando quer. A propriedade lida (`LIBINPUT_IGNORE_DEVICE`,
`USEC_INITIALIZED`) sumiria sem erro e o nó seria tratado como "sem marca". Quem
tem o contrato é a `libudev`: `core/banco_do_udev.py` a chama por `ctypes`
(stdlib), e o curador de áudio KS (copiado SOZINHO pelo install) tem a pergunta
dele, sem importar o pacote.

MORDIDAS (cada uma arrancada e vista reprovar):

- voltar a ler o arquivo do banco em qualquer `.py` de `src/` ou `scripts/`, ou em
  qualquer `.sh` de `scripts/` (o `sed` do `doctor.sh`, por exemplo) ->
  ``test_nenhum_modulo_le_o_arquivo_interno_do_udev`` reprova;
- fazer a pergunta devolver o valor cru, sem decodificar ->
  ``test_a_resposta_da_biblioteca_vira_texto``;
- deixar a falta da biblioteca levantar em vez de "não sei" ->
  ``test_sem_a_biblioteca_a_resposta_e_nao_sei``.
"""

from __future__ import annotations

import ast
import ctypes
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import banco_do_udev
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
O_ARQUIVO_INTERNO = "/run/udev/data"


class _Biblioteca:
    """A `libudev` de mentira: um nó que responde `props`, ou nenhum."""

    def __init__(self, props: dict[str, bytes] | None) -> None:
        self.props = props
        self.abertos: list[tuple[str, object]] = []
        self.soltos = 0
        for nome in (
            "udev_new", "udev_unref", "udev_device_new_from_devnum",
            "udev_device_new_from_syspath", "udev_device_get_property_value",
            "udev_device_unref",
        ):
            setattr(self, nome, self._funcao(getattr(self, "_" + nome)))

    @staticmethod
    def _funcao(corpo: Any) -> Any:
        def chama(*a: Any) -> Any:
            return corpo(*a)

        return chama

    def _udev_new(self) -> int:
        return 1

    def _udev_unref(self, _c: int) -> None:
        return None

    def _udev_device_new_from_devnum(self, _c: int, tipo: bytes, devnum: int) -> int | None:
        self.abertos.append(("devnum", (tipo, devnum)))
        return 7 if self.props is not None else None

    def _udev_device_new_from_syspath(self, _c: int, caminho: bytes) -> int | None:
        self.abertos.append(("syspath", caminho))
        return 7 if self.props is not None else None

    def _udev_device_get_property_value(self, _d: int, nome: bytes) -> bytes | None:
        return (self.props or {}).get(nome.decode())

    def _udev_device_unref(self, _d: int) -> None:
        self.soltos += 1


@pytest.fixture
def biblioteca(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Põe uma `libudev` de mentira no lugar da carregada (e devolve a original depois)."""

    def poe(props: dict[str, bytes] | None) -> _Biblioteca:
        falsa = _Biblioteca(props)
        monkeypatch.setattr(banco_do_udev, "_BIBLIOTECA", falsa)
        return falsa

    return poe


def test_a_resposta_da_biblioteca_vira_texto(biblioteca) -> None:  # type: ignore[no-untyped-def]
    falsa = biblioteca({"LIBINPUT_IGNORE_DEVICE": b"1", "USEC_INITIALIZED": b"42"})
    assert banco_do_udev.propriedade_do_devnum("c", 3456, "LIBINPUT_IGNORE_DEVICE") == "1"
    assert banco_do_udev.propriedade_do_syspath("/sys/x", "USEC_INITIALIZED") == "42"
    assert falsa.abertos == [("devnum", (b"c", 3456)), ("syspath", b"/sys/x")]
    assert falsa.soltos == 2, "cada pergunta solta o dispositivo que abriu"


def test_propriedade_ou_no_ausente_e_nao_sei(biblioteca) -> None:  # type: ignore[no-untyped-def]
    """Prova da D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV."""
    biblioteca({"OUTRA": b"1"})
    assert banco_do_udev.propriedade_do_devnum("c", 1, "LIBINPUT_IGNORE_DEVICE") is None
    biblioteca(None)
    assert banco_do_udev.propriedade_do_syspath("/sys/sumiu", "USEC_INITIALIZED") is None


def test_tipo_de_no_invalido_nao_chega_a_biblioteca(biblioteca) -> None:  # type: ignore[no-untyped-def]
    falsa = biblioteca({"X": b"1"})
    assert banco_do_udev.propriedade_do_devnum("l", 1, "X") is None
    assert falsa.abertos == []


def test_argumento_torto_e_nao_sei_conferido_na_porta(biblioteca) -> None:  # type: ignore[no-untyped-def]
    """O nome e o nó se conferem antes da biblioteca: nada aqui levanta, e não há
    ``except`` que engula o erro de quem chamou (a catraca da origem).

    MORDIDA: tirar a conferência do nome em ``propriedade_do_syspath`` faz o
    ``encode("ascii")`` levantar aqui, e o teste reprova.
    """
    falsa = biblioteca({"X": b"1"})
    assert banco_do_udev.propriedade_do_syspath("/sys/x", "PROPRIEDADE_Ç") is None
    assert banco_do_udev.propriedade_do_devnum("c", 1, "PROPRIEDADE_Ç") is None
    assert banco_do_udev.propriedade_do_devnum("c", -1, "X") is None
    assert banco_do_udev.propriedade_do_devnum("c", 1.5, "X") is None  # type: ignore[arg-type]
    assert banco_do_udev.propriedade_do_syspath("", "X") is None
    assert banco_do_udev.propriedade_do_syspath("/sys/a\0b", "X") is None
    assert falsa.abertos == []
    assert banco_do_udev.propriedade_do_syspath(Path("/sys/x"), "X") == "1"
    assert falsa.abertos == [("syspath", b"/sys/x")]


def test_sem_a_biblioteca_a_resposta_e_nao_sei(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV."""
    def falta(*_a: Any, **_k: Any) -> Any:
        raise OSError("libudev.so.1: não achei")

    monkeypatch.setattr(banco_do_udev, "_BIBLIOTECA", None)
    monkeypatch.setattr(ctypes, "CDLL", falta)
    assert banco_do_udev.propriedade_do_devnum("c", 1, "X") is None
    assert banco_do_udev.propriedade_do_syspath("/sys/x", "X") is None


def test_o_curador_de_audio_sem_a_biblioteca_nao_sabe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def falta(*_a: Any, **_k: Any) -> Any:
        raise OSError("libudev.so.1: não achei")

    monkeypatch.setattr(ctypes, "CDLL", falta)
    assert ks._usec_do_udev(tmp_path) is None


def test_o_curador_de_audio_pergunta_pelo_caminho_do_usb_device(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    falsa = _Biblioteca({"USEC_INITIALIZED": b"987654"})
    monkeypatch.setattr(ctypes, "CDLL", lambda *_a, **_k: falsa)
    assert ks._usec_do_udev(tmp_path) == 987654
    assert falsa.abertos == [("syspath", str(tmp_path).encode())]
    assert falsa.soltos == 1


RAIZ_DO_REPO = RAIZ.parents[1]

PODE_ESCREVER_O_CAMINHO: dict[str, str] = {}

_COMENTARIO_DO_SHELL = re.compile(r"(^|\s)#.*$")


def _codigo_python(arquivo: Path) -> str:
    """O texto das strings que EXECUTAM (sem docstring e sem comentário, que a AST não tem)."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    docs = {
        id(no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
    }
    return "\n".join(
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs
    )


def _codigo_shell(arquivo: Path) -> str:
    """O shell sem as linhas de comentário nem o rabo `# ...` delas."""
    linhas = arquivo.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(_COMENTARIO_DO_SHELL.sub("", linha) for linha in linhas)


def _todo_leitor_de_codigo() -> list[Path]:
    achados = sorted(
        [*(RAIZ_DO_REPO / "src").rglob("*.py"), *(RAIZ_DO_REPO / "scripts").rglob("*.py"),
         *(RAIZ_DO_REPO / "scripts").rglob("*.sh")]
    )
    return [a for a in achados if "__pycache__" not in a.parts]


def test_nenhum_modulo_le_o_arquivo_interno_do_udev() -> None:
    """Prova da D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV."""
    arquivos = _todo_leitor_de_codigo()
    assert len(arquivos) > 100, "a varredura não achou o código: o caminho da raiz mudou"
    achados: dict[str, str] = {}
    for arquivo in arquivos:
        rel = arquivo.relative_to(RAIZ_DO_REPO).as_posix()
        if rel in PODE_ESCREVER_O_CAMINHO:
            continue
        codigo = _codigo_shell(arquivo) if arquivo.suffix == ".sh" else _codigo_python(arquivo)
        if O_ARQUIVO_INTERNO in codigo:
            achados[rel] = O_ARQUIVO_INTERNO
    assert not achados, (
        f"voltaram a citar o arquivo do banco do udev (pergunte à libudev): {sorted(achados)}"
    )


def _ensaio_dos_endpoints() -> Any:
    caminho = RAIZ_DO_REPO / "scripts" / "ensaios" / "os_endpoints_de_haptica.py"
    espec = importlib.util.spec_from_file_location("ensaio_os_endpoints_de_haptica", caminho)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


def test_o_ensaio_dos_endpoints_pergunta_o_usec_a_biblioteca(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ensaio = _ensaio_dos_endpoints()
    perguntas: list[tuple[str, int, str]] = []

    def pergunta(tipo: str, devnum: int, nome: str) -> str | None:
        perguntas.append((tipo, devnum, nome))
        return "123456"

    monkeypatch.setattr(ensaio, "propriedade_do_devnum", pergunta)
    (tmp_path / "dev").write_text("189:5\n", encoding="utf-8")

    assert ensaio._usec(tmp_path) == 123456
    assert perguntas == [("c", os.makedev(189, 5), "USEC_INITIALIZED")]
    assert ensaio._usec(tmp_path / "sem-no") == 0


def test_o_ensaio_dos_endpoints_le_os_sinks_pelo_json(monkeypatch: pytest.MonkeyPatch) -> None:
    ensaio = _ensaio_dos_endpoints()
    chamadas: list[list[str]] = []
    nos = [
        {
            "index": 7,
            "name": "alsa_output.usb-Sony_HEFESTOAABBCC-00.HiFi__Speaker__sink",
            "sample_specification": "s16le 4ch 48000Hz",
            "properties": {
                "device.bus": "usb", "device.vendor.id": "054c", "device.product.id": "0ce6",
                "sysfs.path": "/devices/pci0000:00/usb1/1-1", "audio.channels": "4",
            },
        },
        {"index": 8, "name": "alsa_output.pci-0000_00_1f.3.analog-stereo", "properties": {}},
    ]

    def ler(argv: list[str]) -> str | None:
        chamadas.append(list(argv))
        return json.dumps(nos) if "--format=json" in argv else None

    monkeypatch.setattr(ensaio, "rodar_pactl", ler)

    achados = ensaio.nossos_sinks()

    assert [a["nome"] for a in achados] == [nos[0]["name"]]
    assert achados[0] | {} == {
        "nome": nos[0]["name"], "espec": "s16le 4ch 48000Hz", "bus": "usb", "vid": "054c",
        "pid": "0ce6", "sysfs": "/devices/pci0000:00/usb1/1-1", "canais": "4", "id": "7",
    }
    assert all("--format=json" in c for c in chamadas), chamadas
