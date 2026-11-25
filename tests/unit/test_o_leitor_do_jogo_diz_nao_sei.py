"""O leitor do jogo diz «não sei», e quem pergunta só libera no «sem jogo» exato.

O-LEITOR-DO-JOGO-DIZ-NAO-SEI-E-QUEM-PERGUNTA-LE-O-SEM-JOGO-EXATO-01: o `--ha-jogo` saía com 1
para «sem jogo» e para a exceção que ninguém pegava, e o `disparo_do_udev.sh` e o `jogo_em_cena` do
install liam os dois como «sem jogo». O leitor devolve `SEM_JOGO` (10) só para «sem jogo»; a exceção
sai com `NAO_SEI` (3) e qualquer outra saída é jogo aberto para quem pergunta.

A MORDIDA: leia o 1 como «sem jogo» no dono ou no `jogo_em_cena`, ou tire o `try` do `main`, e a
régua reprova.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le

RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "scripts" / "disparo_do_udev.sh"
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
LEITOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "quem_o_jogo_le.py"

LEVANTA = 'def ha_jogo_aberto(*a, **k):\n    raise OSError("x")\n\n\n'
QUE_REENUMERAM = ("hidraw", "idVendor=054c", "subsystem-match=usb", "subsystem-match=input")
PID_ACIMA_DO_TETO_DO_KERNEL = "4999999"


def _proc(raiz: Path, *, jogo: bool) -> Path:
    proc = raiz / ("proc-com-jogo" if jogo else "proc-sem-jogo")
    (proc / PID_ACIMA_DO_TETO_DO_KERNEL).mkdir(parents=True)
    ambiente = b"HOME=/x\0"
    if jogo:
        ambiente += quem_o_jogo_le.ENV_DO_JOGO.encode() + b"=/compat/1234\0"
    (proc / PID_ACIMA_DO_TETO_DO_KERNEL / "environ").write_bytes(ambiente)
    (proc / "self").mkdir()
    return proc


def _udevadm_de_mentira(raiz: Path) -> tuple[dict[str, str], Path]:
    bin_ = raiz / "bin"
    bin_.mkdir(parents=True, exist_ok=True)
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    return {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}, diario


def _leitor_que_sai_com(pasta: Path, saida: int) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    leitor = pasta / "quem_o_jogo_le.py"
    leitor.write_text(f"import sys\nsys.exit({saida})\n", encoding="utf-8")
    return leitor


def _dono_ao_lado_de(pasta: Path) -> Path:
    dono = pasta / DONO.name
    dono.write_text(DONO.read_text(encoding="utf-8"), encoding="utf-8")
    dono.chmod(dono.stat().st_mode | stat.S_IEXEC)
    return dono


def _dispara(dono: Path, raiz: Path, proc: Path) -> tuple[list[str], str]:
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RAIZ_PROC"] = str(proc)
    saida = subprocess.run(
        ["bash", str(dono)], env=ambiente, capture_output=True, text=True, check=False
    )
    assert saida.returncode == 0, saida.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return chamadas, saida.stdout


def _reenumerou(chamadas: list[str]) -> bool:
    return any(alvo in c for c in chamadas for alvo in QUE_REENUMERAM) or "trigger" in chamadas


def test_o_main_separa_com_jogo_sem_jogo_e_nao_sei(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire o `try` do `main` e a exceção sobe em vez de sair com `NAO_SEI`."""
    com, sem = _proc(tmp_path, jogo=True), _proc(tmp_path, jogo=False)
    assert quem_o_jogo_le.main(["--ha-jogo", "--proc", str(com)]) == quem_o_jogo_le.COM_JOGO
    assert quem_o_jogo_le.main(["--ha-jogo", "--proc", str(sem)]) == quem_o_jogo_le.SEM_JOGO
    assert quem_o_jogo_le.main(["--ha-jogo", "--nada", "x"]) == quem_o_jogo_le.USO

    def levanta(*_a: object, **_k: object) -> bool:
        raise OSError("sem leitura")

    monkeypatch.setattr(quem_o_jogo_le, "ha_jogo_aberto", levanta)
    assert quem_o_jogo_le.main(["--ha-jogo", "--proc", str(sem)]) == quem_o_jogo_le.NAO_SEI
    saidas = {quem_o_jogo_le.COM_JOGO, quem_o_jogo_le.SEM_JOGO, quem_o_jogo_le.USO,
               quem_o_jogo_le.NAO_SEI}
    assert len(saidas) == 4
    assert 1 not in saidas


def test_o_leitor_que_levanta_sai_com_nao_sei_no_processo_de_verdade(tmp_path: Path) -> None:
    """A exceção do Python não sai mais com o 1 que o `SEM_JOGO` já teve."""
    texto = LEITOR.read_text(encoding="utf-8")
    corte = texto.index('if __name__ == "__main__"')
    pasta = tmp_path / "levanta"
    pasta.mkdir()
    falso = pasta / "quem_o_jogo_le.py"
    falso.write_text(
        texto[:corte] + LEVANTA + texto[corte:],
        encoding="utf-8",
    )
    feito = subprocess.run(["python3", "-I", str(falso), "--ha-jogo", "--proc", str(tmp_path)],
                           capture_output=True, check=False, timeout=30)
    assert feito.returncode == quem_o_jogo_le.NAO_SEI, feito.stderr


@pytest.mark.parametrize("saida", [0, 1, 2, 3, 4, 127, 139], ids=lambda c: f"saida-{c}")
def test_o_dono_so_reenumera_no_sem_jogo_exato(tmp_path: Path, saida: int) -> None:
    """MORDIDA: leia o 1 como «sem jogo» no `case` do dono e `saida-1` reenumera o controle."""
    pasta = tmp_path / "pacote"
    _leitor_que_sai_com(pasta, saida)
    dono = _dono_ao_lado_de(pasta)
    chamadas, _ = _dispara(dono, tmp_path, _proc(tmp_path, jogo=False))
    assert not _reenumerou(chamadas), chamadas


def test_o_dono_reenumera_no_sem_jogo_exato(tmp_path: Path) -> None:
    pasta = tmp_path / "pacote"
    _leitor_que_sai_com(pasta, quem_o_jogo_le.SEM_JOGO)
    dono = _dono_ao_lado_de(pasta)
    chamadas, _ = _dispara(dono, tmp_path, _proc(tmp_path, jogo=False))
    for alvo in QUE_REENUMERAM:
        assert any(alvo in c for c in chamadas), alvo
    assert "trigger" in chamadas


def test_o_dono_com_o_leitor_de_verdade_nos_tres_casos(tmp_path: Path) -> None:
    """Com jogo, sem jogo e leitor que levanta, o leitor real e o dono juntos."""
    texto = LEITOR.read_text(encoding="utf-8")
    corte = texto.index('if __name__ == "__main__"')
    casos = {
        "com-jogo": (texto, True, False),
        "sem-jogo": (texto, False, True),
        "levanta": (
            texto[:corte] + LEVANTA + texto[corte:],
            False, False,
        ),
    }
    for nome, (fonte, jogo, reenumera) in casos.items():
        pasta = tmp_path / nome / "pacote"
        pasta.mkdir(parents=True)
        (pasta / "quem_o_jogo_le.py").write_text(fonte, encoding="utf-8")
        dono = _dono_ao_lado_de(pasta)
        chamadas, _ = _dispara(dono, tmp_path / nome, _proc(tmp_path / nome, jogo=jogo))
        assert _reenumerou(chamadas) == reenumera, nome


def _jogo_em_cena_com(raiz: Path, saida: int) -> bool:
    arvore = raiz / "arvore"
    destino = arvore / "src/hefesto_dualsense4unix/integrations"
    _leitor_que_sai_com(destino, saida)
    texto = CAMADA.read_text(encoding="utf-8")
    inicio = texto.index("jogo_em_cena() {")
    funcao = texto[inicio:texto.index("\n}\n", inicio) + 3]
    feito = subprocess.run(
        ["bash", "-c", f'ROOT_DIR="{arvore}"\n{funcao}\njogo_em_cena'],
        capture_output=True, check=False, timeout=30,
    )
    return feito.returncode == 0


@pytest.mark.parametrize("saida", [0, 1, 2, 3, 127, 139], ids=lambda c: f"saida-{c}")
def test_o_jogo_em_cena_do_install_trata_o_nao_sei_como_jogo(tmp_path: Path, saida: int) -> None:
    """MORDIDA: leia o 1 no `jogo_em_cena` e o install troca o broker sem saber do jogo."""
    assert _jogo_em_cena_com(tmp_path, saida) is True


def test_o_jogo_em_cena_do_install_so_libera_no_sem_jogo_exato(tmp_path: Path) -> None:
    assert _jogo_em_cena_com(tmp_path, quem_o_jogo_le.SEM_JOGO) is False


def _raizes_que_nao_se_leem(raiz: Path) -> dict[str, Path]:
    fechada = raiz / "proc-fechado"
    (fechada / PID_ACIMA_DO_TETO_DO_KERNEL).mkdir(parents=True)
    fechada.chmod(0)
    return {"ausente": raiz / "proc-que-nao-existe", "fechada": fechada}


@pytest.mark.skipif(os.geteuid() == 0, reason="o root lê a pasta fechada")
def test_o_proc_que_nao_se_le_e_nao_sei_e_nao_sem_jogo(tmp_path: Path) -> None:
    """MORDIDA: liste a raiz pelo `_entradas`, que engole o erro, e o ilegível vira `SEM_JOGO`."""
    raizes = _raizes_que_nao_se_leem(tmp_path)
    try:
        for nome, raiz in raizes.items():
            assert quem_o_jogo_le.ha_jogo_aberto(str(raiz)) is True, nome
            assert quem_o_jogo_le.main(["--ha-jogo", "--proc", str(raiz)]) == (
                quem_o_jogo_le.NAO_SEI
            ), nome
            feito = subprocess.run(
                ["python3", "-I", str(LEITOR), "--ha-jogo", "--proc", str(raiz)],
                capture_output=True, check=False, timeout=30,
            )
            assert feito.returncode == quem_o_jogo_le.NAO_SEI, (nome, feito.stderr)
    finally:
        raizes["fechada"].chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="o root lê a pasta fechada")
def test_o_dono_com_o_proc_que_nao_se_le_nao_reenumera(tmp_path: Path) -> None:
    """O leitor real e o dono: o `/proc` ausente ou fechado não dispara nada que reenumera."""
    raizes = _raizes_que_nao_se_leem(tmp_path)
    try:
        for nome, raiz in raizes.items():
            pasta = tmp_path / nome / "pacote"
            pasta.mkdir(parents=True)
            (pasta / LEITOR.name).write_text(LEITOR.read_text(encoding="utf-8"), encoding="utf-8")
            dono = _dono_ao_lado_de(pasta)
            chamadas, saida = _dispara(dono, tmp_path / nome, raiz)
            assert not _reenumerou(chamadas), (nome, chamadas)
            assert "não deu para saber" in saida, nome
    finally:
        raizes["fechada"].chmod(0o755)
