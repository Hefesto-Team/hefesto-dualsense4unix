"""O sistema pergunta ao udev pela biblioteca dele, e não lê o arquivo interno dele.

O banco do udev (`/run/udev/data/c<maj>:<min>`) é interno do systemd, que muda o
formato quando quer. A propriedade lida (`LIBINPUT_IGNORE_DEVICE`,
`USEC_INITIALIZED`) sumiria sem erro e o nó seria tratado como "sem marca". Quem
tem o contrato é a `libudev`: `core/banco_do_udev.py` a chama por `ctypes`
(stdlib), e o curador de áudio KS (copiado SOZINHO pelo install) tem a pergunta
dele, sem importar o pacote.

MORDIDAS (cada uma arrancada e vista reprovar):

- voltar a ler o arquivo do banco em `core/evdev_reader.py` ->
  ``test_nenhum_modulo_le_o_arquivo_interno_do_udev`` reprova;
- fazer a pergunta devolver o valor cru, sem decodificar ->
  ``test_a_resposta_da_biblioteca_vira_texto``;
- deixar a falta da biblioteca levantar em vez de "não sei" ->
  ``test_sem_a_biblioteca_a_resposta_e_nao_sei``.
"""

from __future__ import annotations

import ast
import ctypes
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import banco_do_udev
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

RAIZ = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
O_ARQUIVO_INTERNO = "/run/udev/data"
QUEM_PERGUNTA = (
    "core/evdev_reader.py",
    "core/banco_do_udev.py",
    "integrations/audio_ks_dualsense.py",
    "integrations/sinal_da_barra.py",
)


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
    # A decisão D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV.
    biblioteca({"OUTRA": b"1"})
    assert banco_do_udev.propriedade_do_devnum("c", 1, "LIBINPUT_IGNORE_DEVICE") is None
    biblioteca(None)
    assert banco_do_udev.propriedade_do_syspath("/sys/sumiu", "USEC_INITIALIZED") is None


def test_tipo_de_no_invalido_nao_chega_a_biblioteca(biblioteca) -> None:  # type: ignore[no-untyped-def]
    falsa = biblioteca({"X": b"1"})
    assert banco_do_udev.propriedade_do_devnum("l", 1, "X") is None
    assert falsa.abertos == []


def test_sem_a_biblioteca_a_resposta_e_nao_sei(monkeypatch: pytest.MonkeyPatch) -> None:
    # A decisão D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV.
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


def _strings_de_codigo(arquivo: str) -> list[str]:
    arvore = ast.parse((RAIZ / arquivo).read_text(encoding="utf-8"))
    docs = {
        id(no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
    }
    return [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs
    ]


@pytest.mark.parametrize("arquivo", QUEM_PERGUNTA)
def test_nenhum_modulo_le_o_arquivo_interno_do_udev(arquivo: str) -> None:
    # A decisão D-0810-O-UDEV-SE-PERGUNTA-A-LIBUDEV.
    achados = [t for t in _strings_de_codigo(arquivo) if O_ARQUIVO_INTERNO in t]
    assert not achados, f"{arquivo} voltou a citar o arquivo do banco do udev: {achados}"
