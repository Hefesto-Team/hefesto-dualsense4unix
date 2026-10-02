"""A espera por leitura passa do descritor 1023, o teto do `select`."""
from __future__ import annotations

import contextlib
import os
import re
import resource
import select
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.utils.espera import prontos_para_ler
from tests.unit.test_o_pad_virtual_atende_a_vibracao_desde_que_nasce import (
    _UInputComoOPythonEvdev,
    evdev_de_mentira,  # noqa: F401 — a fixture do evdev de mentira
)
from tests.unit.test_vpad_ff_passthrough import _rumble_effect

RAIZ = Path(__file__).resolve().parents[2]

_ALTO = 1500


@pytest.fixture
def teto_alto() -> Iterator[None]:
    """O processo pode abrir o descritor `_ALTO` (o teto mole sobe e volta)."""
    mole, duro = resource.getrlimit(resource.RLIMIT_NOFILE)
    if duro != resource.RLIM_INFINITY and duro <= _ALTO + 16:
        pytest.skip(f"o teto duro de descritores ({duro}) não passa de {_ALTO}")
    if mole != resource.RLIM_INFINITY and mole <= _ALTO + 16:
        resource.setrlimit(resource.RLIMIT_NOFILE, (_ALTO + 16, duro))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (mole, duro))


def _para_o_alto(fd: int) -> int:
    alto = os.dup2(fd, _ALTO)
    os.close(fd)
    return alto


@pytest.mark.usefixtures("teto_alto")
def test_a_espera_acorda_com_o_descritor_acima_de_1023() -> None:
    leitura, escrita = os.pipe()
    alto = _para_o_alto(leitura)
    try:
        with pytest.raises(ValueError):
            select.select([alto], [], [], 0)
        assert prontos_para_ler([alto], 0) == []
        os.write(escrita, b"x")
        assert prontos_para_ler([alto], 1.0) == [alto]
    finally:
        for fd in (alto, escrita):
            with contextlib.suppress(OSError):
                os.close(fd)


def test_a_espera_responde_como_o_select_nos_casos_de_antes() -> None:
    with pytest.raises(ValueError):
        prontos_para_ler([-1], 0)
    leitura, escrita = os.pipe()
    os.close(leitura)
    try:
        with pytest.raises(OSError):
            prontos_para_ler([leitura], 0)
    finally:
        os.close(escrita)
    leitura, escrita = os.pipe()
    os.close(escrita)
    try:
        assert prontos_para_ler([leitura], 0) == [leitura], (
            "o fim de linha conta como pronto, como no select"
        )
    finally:
        os.close(leitura)


class _UInputNoDescritorAlto(_UInputComoOPythonEvdev):
    """O evdev de mentira com o fd do pad acima de 1023, como no CI."""

    def __init__(self, events: dict, **kwargs: object) -> None:
        super().__init__(events, **kwargs)
        self.fd = _para_o_alto(self.fd)


@pytest.mark.usefixtures("teto_alto")
def test_o_fio_da_vibracao_atende_com_o_descritor_alto(
    evdev_de_mentira: type[_UInputComoOPythonEvdev],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setattr(sys.modules["evdev"], "UInput", _UInputNoDescritorAlto)
    pad = UinputGamepad.for_flavor("xbox", rumble_sink=lambda _w, _s: None)
    assert pad.start() is True
    aparelho = evdev_de_mentira.instancias[0]
    try:
        assert aparelho.fd == _ALTO
        aparelho.o_jogo_manda_um_efeito(
            _rumble_effect(0, strong=0x8000, weak=0x4000), request_id=11
        )
        inicio = time.monotonic()
        while not aparelho.uploads_feitos and time.monotonic() - inicio < 1.0:
            time.sleep(0.002)
        assert aparelho.uploads_feitos, (
            "com o descritor acima de 1023 o fio da vibração saiu calado e o "
            "pedido ficou sem resposta: foi o CI de 27/09"
        )
    finally:
        pad.stop()


def test_nenhum_modulo_do_produto_espera_pelo_select() -> None:
    achados = [
        f"{caminho.relative_to(RAIZ)}:{numero}"
        for caminho in sorted((RAIZ / "src" / "hefesto_dualsense4unix").rglob("*.py"))
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\bselect\.select\(", linha) and not linha.lstrip().startswith("#")
    ]
    assert not achados, (
        f"o produto voltou a esperar pelo select.select em {achados}: acima do "
        "descritor 1023 ele levanta ValueError. Use utils.espera.prontos_para_ler."
    )
