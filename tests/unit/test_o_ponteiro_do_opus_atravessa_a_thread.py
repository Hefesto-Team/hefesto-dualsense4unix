"""O ponteiro do encoder Opus sobrevive a uma thread de trabalho."""
from __future__ import annotations

import ctypes
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    BYTES_POR_QUADRO_OPUS,
    CodificadorOpus,
    OpusIndisponivelError,
    _carregar_libopus_encoder,
)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def tem_libopus() -> bool:
    try:
        _carregar_libopus_encoder()
    except OpusIndisponivelError:
        pytest.skip("libopus não está nesta máquina")
    return True


def test_o_codificador_funciona_dentro_de_uma_thread(tem_libopus: bool) -> None:
    """O caso EXATO da ponte: encoder construído e usado numa thread."""
    fora: dict[str, object] = {}

    def na_thread() -> None:
        try:
            with CodificadorOpus() as cod:
                quadro = cod.codificar(b"\x00" * cod.bytes_de_pcm_por_quadro)
                fora["tamanho"] = len(quadro) if quadro else 0
        except BaseException as erro:
            fora["erro"] = f"{type(erro).__name__}: {erro}"

    t = threading.Thread(target=na_thread)
    t.start()
    t.join(timeout=15)

    assert not t.is_alive(), "a thread do codificador travou"
    assert "erro" not in fora, f"o codificador quebrou na thread: {fora.get('erro')}"
    assert fora.get("tamanho") == BYTES_POR_QUADRO_OPUS, (
        f"o quadro saiu com {fora.get('tamanho')} B em vez de "
        f"{BYTES_POR_QUADRO_OPUS} — o CBR não fechou dentro da thread"
    )


def test_o_ponteiro_de_uma_thread_NAO_cabe_em_32_bits(tem_libopus: bool) -> None:  # noqa: N802
    """A premissa do defeito, medida — e ela é o que torna a cura necessária."""
    lib = _carregar_libopus_encoder()
    erro = ctypes.c_int()
    ponteiros: dict[str, int] = {}

    def cria(rotulo: str) -> None:
        p = lib.opus_encoder_create(48000, 2, 2049, ctypes.byref(erro))
        ponteiros[rotulo] = p
        lib.opus_encoder_destroy(ctypes.c_void_p(p))

    cria("principal")
    t = threading.Thread(target=lambda: cria("trabalho"))
    t.start()
    t.join(timeout=15)

    da_thread = ponteiros.get("trabalho", 0)
    assert da_thread, "não consegui criar o encoder na thread"
    if da_thread == (da_thread & 0xFFFFFFFF):
        pytest.skip(
            f"nesta máquina a thread alocou em 0x{da_thread:x}, que cabe em 32 "
            "bits — o defeito não é exercitável aqui, e a cura continua certa"
        )
    assert da_thread != (da_thread & 0xFFFFFFFF), (
        "premissa do defeito: a arena per-thread do glibc fica acima de 4 GB"
    )


def test_toda_chamada_variadica_passa_pelo_dono(tem_libopus: bool) -> None:
    """`opus_encoder_ctl` só é chamada de UM lugar, e é o que envelopa."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "alto_falante_bt.py"
    ).read_text(encoding="utf-8")

    chamadas = [
        n
        for n, linha in enumerate(fonte.splitlines(), 1)
        if "opus_encoder_ctl(" in linha and not linha.lstrip().startswith("#")
    ]
    assert len(chamadas) == 1, (
        f"opus_encoder_ctl é chamada em {len(chamadas)} lugares (linhas "
        f"{chamadas}); tem de haver UM dono, `CodificadorOpus._ctl`, porque é "
        "ele que envelopa o ponteiro em `ctypes.c_void_p`"
    )
    trecho = fonte[: fonte.index("opus_encoder_ctl(", fonte.index("def _ctl"))]
    assert "def _ctl" in trecho, "a única chamada tem de estar dentro de `_ctl`"
    depois = fonte[fonte.index("def _ctl") :]
    assert "ctypes.c_void_p(self._enc)" in depois[:1200], (
        "o dono não envelopa o ponteiro — sem `ctypes.c_void_p` ele vai como C "
        "int de 32 bits e o processo cai numa thread de trabalho"
    )


def test_a_mordida_mata_o_processo_de_verdade(tem_libopus: bool) -> None:
    """A prova de que a cura é load-bearing: sem ela, SIGSEGV num subprocesso."""
    programa = (
        "import ctypes, threading, sys\n"
        f"sys.path.insert(0, {str(RAIZ / 'src')!r})\n"
        "import hefesto_dualsense4unix.integrations.alto_falante_bt as af\n"
        "lib = af._carregar_libopus_encoder()\n"
        "erro = ctypes.c_int()\n"
        "def alvo():\n"
        "    p = lib.opus_encoder_create(48000, 2, 2049, ctypes.byref(erro))\n"
        "    # A CURA ARRANCADA: o ponteiro cru, sem `ctypes.c_void_p`.\n"
        "    lib.opus_encoder_ctl(p, 4006, ctypes.c_int32(0))\n"
        "t = threading.Thread(target=alvo)\n"
        "t.start(); t.join()\n"
    )
    fim = subprocess.run(
        [sys.executable, "-c", programa], capture_output=True, timeout=60, check=False
    )
    if fim.returncode == 0:
        pytest.skip(
            "nesta máquina o ponteiro da thread coube em 32 bits — a mordida "
            "não é exercitável aqui (ver o teste da premissa acima)"
        )
    assert fim.returncode < 0 or b"Segmentation" in fim.stderr, (
        f"esperava o processo MORRER com a cura arrancada; ele saiu com "
        f"rc={fim.returncode}. Se a libopus mudou de comportamento, esta régua "
        "precisa ser remedida antes de ser afrouxada."
    )
