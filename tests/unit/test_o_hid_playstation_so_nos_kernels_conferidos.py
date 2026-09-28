"""O `hid-playstation` patchado só se constrói nos kernels conferidos — L6.

A `O-PRODUTO-EM-QUALQUER-MAQUINA-01` (28/09/2026) mediu o que o pino do `uhid`
já tinha medido do lado dele: o `hid-playstation.c` desta casa SUBSTITUI o de
fábrica, e construído contra um kernel cujo de fábrica é outro ele compila
limpo e devolve o arquivo errado. Até aqui a base era o v7.0.11 e o
`dkms.conf` construía para qualquer kernel; no 7.1.5-76070105, o que a máquina
roda, o módulo tirava as duas verificações de `num_touch_reports` do DualShock
4 que o stable acrescentou.

A régua é a irmã de ``test_o_uhid_patchado_so_nos_kernels_conferidos.py``, com
uma diferença medida: aqui o `srcversion` do de fábrica NÃO se reproduz fora
da árvore (repetido em 28/09 nos dois kernels, a conta está no
`patch/BASELINE`), então a prova da base é o commit do Pop que o pacote do
kernel nomeia, e não o `srcversion`. Ela cobra:

1. o pino existe, e a lista do `dkms.conf` é a MESMA do `KERNELS_VALIDADOS`,
   nos dois sentidos;
2. um kernel que ninguém conferiu fica de fora;
3. a base é o stable de CADA kernel pinado;
4. a série desfeita devolve o `SHA256_VANILLA_C`, e o `.c` da pasta é o
   `SHA256_PATCHED_C`;
5. a marca do 0003 está no `.c` e no `patch/0003`, só de leitura;
6. o `srcversion` do 0003 sem a marca é o MESMO no `BASELINE` e no daemon.

A MORDIDA, feita em 28/09/2026: tirar a linha ``BUILD_EXCLUSIVE_KERNEL`` do
``dkms.conf`` faz ``test_o_dkms_do_hid_playstation_tem_pino_de_kernel``
reprovar; pôr o 7.0.11 no pino sem pô-lo no ``KERNELS_VALIDADOS`` faz
``test_o_pino_nao_aceita_kernel_que_ninguem_conferiu`` reprovar; e trocar o
``0444`` da marca por ``0644`` faz ``test_a_marca_do_0003_e_so_de_leitura``
reprovar. Devolvido o arquivo, md5 conferido.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "assets" / "dkms" / "hid-playstation"
DKMS_CONF = PASTA / "dkms.conf"
BASELINE = PASTA / "patch" / "BASELINE"


def _baseline() -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        if chave.strip() == "PATCH":
            continue
        saida[chave.strip()] = valor.strip()
    return saida


def _serie() -> list[str]:
    return [
        linha.partition("=")[2].strip()
        for linha in BASELINE.read_text(encoding="utf-8").splitlines()
        if linha.startswith("PATCH=")
    ]


def _pino() -> re.Pattern[str]:
    casou = re.search(
        r'^BUILD_EXCLUSIVE_KERNEL="([^"]+)"$', DKMS_CONF.read_text(encoding="utf-8"), re.M
    )
    assert casou, "o dkms.conf do hid-playstation perdeu o BUILD_EXCLUSIVE_KERNEL"
    return re.compile(casou.group(1))


def test_o_dkms_do_hid_playstation_tem_pino_de_kernel() -> None:
    _pino()


def test_cada_kernel_validado_casa_o_pino() -> None:
    validados = _baseline()["KERNELS_VALIDADOS"].split()
    assert validados, "KERNELS_VALIDADOS vazio: o pino não teria dono"
    pino = _pino()
    for build in validados:
        assert pino.match(f"{build}-generic"), (
            f"{build} está em KERNELS_VALIDADOS e o dkms.conf não o constrói"
        )


def test_o_pino_nao_aceita_kernel_que_ninguem_conferiu() -> None:
    validados = set(_baseline()["KERNELS_VALIDADOS"].split())
    pino = _pino()
    # O 7.0.11-76070011 está AQUI de propósito: a base de agora é o stable
    # v7.1.5, e o de fábrica do 7.0.11 é outro arquivo (sem as duas
    # verificações do DualShock 4). Voltar a piná-lo pede refazer o ritual do
    # `BASELINE` — e mexer nesta linha é a prova de que alguém o refez.
    for build in (
        "7.2.0-76070200", "7.1.6-76070106", "6.17.9-76061709", "7.1.5-1", "7.0.11-76070011",
    ):
        assert build not in validados
        assert not pino.match(f"{build}-generic"), (
            f"o pino deixa passar {build}, que ninguém conferiu"
        )


def test_a_base_e_o_stable_de_cada_kernel_pinado() -> None:
    """O `.c` de base é o da versão EXATA de cada kernel pinado."""
    base = _baseline()
    versao_da_base = base["KERNEL_BASE"].removeprefix("v")
    for build in base["KERNELS_VALIDADOS"].split():
        assert build.split("-", 1)[0] == versao_da_base, (
            f"{build} está pinado sobre a base {base['KERNEL_BASE']}: o "
            "`hid-playstation.c` de fábrica dele é o do stable daquela versão"
        )
    assert base["KERNEL_TESTED"].removesuffix("-generic") in base["KERNELS_VALIDADOS"].split()


def test_o_c_da_pasta_e_o_patchado_do_baseline() -> None:
    fonte = (PASTA / "hid-playstation.c").read_bytes()
    assert hashlib.sha256(fonte).hexdigest() == _baseline()["SHA256_PATCHED_C"]


def test_a_serie_desfeita_devolve_o_de_fabrica(tmp_path: Path) -> None:
    if shutil.which("patch") is None:  # pragma: no cover - a máquina da casa tem
        pytest.skip("sem o patch(1) nesta máquina")
    copia = tmp_path / "hid-playstation.c"
    copia.write_bytes((PASTA / "hid-playstation.c").read_bytes())
    for nome in reversed(_serie()):
        resultado = subprocess.run(
            ["patch", "-R", "-p3", "-s", str(copia)],
            input=(PASTA / "patch" / nome).read_bytes(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        assert resultado.returncode == 0, (nome, resultado.stderr)
    assert hashlib.sha256(copia.read_bytes()).hexdigest() == _baseline()["SHA256_VANILLA_C"]


def test_a_marca_do_0003_e_so_de_leitura() -> None:
    """A marca não se escreve pelo sysfs, e o `.c` e o patch dizem a mesma coisa."""
    fonte = (PASTA / "hid-playstation.c").read_text(encoding="utf-8")
    remendo = next((PASTA / "patch").glob("0003-*.patch")).read_text(encoding="utf-8")
    assert "module_param(mic_frames_ignored, bool, 0444);" in fonte
    assert "+module_param(mic_frames_ignored, bool, 0444);" in remendo
    assert "static bool mic_frames_ignored = true;" in fonte
    # A guarda não lê a marca: o `if` do áudio é o de 10/09, inteiro.
    assert "if (data[1] & DS_INPUT_BT_FLAG_AUDIO)" in fonte


def test_o_srcversion_do_0003_sem_a_marca_e_o_mesmo_no_daemon() -> None:
    """Uma lista, dois lugares: o `BASELINE` mede, o daemon consulta."""
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic

    medido = set(_baseline()["SRCVERSION_DO_0003_SEM_A_MARCA"].split())
    assert all(re.fullmatch(r"[0-9A-F]{23}", v) for v in medido), medido
    assert medido == set(bt_mic.SRCVERSION_DO_0003_SEM_A_MARCA)
