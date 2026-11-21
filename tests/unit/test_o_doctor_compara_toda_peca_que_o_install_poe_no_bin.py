"""O-DOCTOR-COMPARA-TODA-PECA-QUE-O-INSTALL-POE-NO-BIN-01: o doctor vê a cópia velha de cada peça.

O install declara cada peça do ``~/.local/share/hefesto-dualsense4unix/bin/`` num alvo nomeado
(``*_TARGET``), com a fonte no ``*_SRC`` de mesmo prefixo. O ``check_copias_do_wrapper`` do doctor
compara todas com o checkout; a lista do doctor é lida do ``doctor.sh`` e cotejada com a do
install, nunca escrita aqui.

A MORDIDA: a lista do doctor sem uma peça do install (ou sem o ``cmp``) deixa a cópia velha dessa
peça passar sem aviso, e os testes reprovam nomeando a peça.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
BIN = ".local/share/hefesto-dualsense4unix/bin"
ALVO = re.compile(
    r'^readonly (\w+)_TARGET="\$\{HOME\}/\.local/share/hefesto-dualsense4unix/bin/([\w.-]+)"$',
    re.MULTILINE)
FONTE = re.compile(r'^readonly (\w+)_SRC="\$\{ROOT_DIR\}/([\w./-]+)"$', re.MULTILINE)


def _o_que_o_install_poe_no_bin() -> dict[str, str]:
    texto = INSTALL.read_text(encoding="utf-8")
    fontes = dict(FONTE.findall(texto))
    return {nome: fontes[prefixo] for prefixo, nome in ALVO.findall(texto)}


def _o_que_o_doctor_compara() -> dict[str, str]:
    texto = DOCTOR.read_text(encoding="utf-8")
    inicio = texto.index("check_copias_do_wrapper() {")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    return {
        nome: fonte
        for nome, fonte in re.findall(r'^\s+"([\w.-]+)\|([\w./-]+)\|', corpo, re.MULTILINE)
    }


def test_o_doctor_compara_toda_peca_que_o_install_poe_no_bin() -> None:
    install = _o_que_o_install_poe_no_bin()
    assert len(install) >= 6
    assert "arquivo_de_terceiro.py" in install
    doctor = _o_que_o_doctor_compara()
    assert set(install) - set(doctor) == set(), (
        f"o install põe no bin/ e o doctor não compara: {sorted(set(install) - set(doctor))}")
    assert set(doctor) - set(install) == set(), (
        f"o doctor compara o que o install não põe: {sorted(set(doctor) - set(install))}")
    assert {n: f for n, f in doctor.items() if install[n] != f} == {}


def _lar(tmp_path: Path, *, velha: str = "", sem: str = "") -> Path:
    lar = tmp_path / "lar"
    assert lar.resolve() != Path(os.path.expanduser("~")).resolve()
    pasta = lar / BIN
    pasta.mkdir(parents=True)
    for nome, fonte in _o_que_o_install_poe_no_bin().items():
        if nome == sem:
            continue
        dado = (RAIZ / fonte).read_bytes()
        if nome == velha:
            dado += "\n# a cópia de antes do git pull\n".encode()
        (pasta / nome).write_bytes(dado)
        (pasta / nome).chmod(0o644 if nome.endswith((".py", ".json")) else 0o755)
    return lar


def _doctor(lar: Path) -> str:
    roteiro = (
        f'case "${{HOME}}" in "{lar}") ;; *) echo "HOME de verdade" >&2; exit 90 ;; esac\n'
        f'source "{DOCTOR}"; check_copias_do_wrapper'
    )
    r = subprocess.run(
        ["bash", "-c", roteiro], capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(lar),
             "XDG_STATE_HOME": str(lar / "estado"), "XDG_RUNTIME_DIR": str(lar / "run")})
    assert r.returncode == 0, r.stderr
    return r.stdout + r.stderr


def test_o_doctor_acusa_a_copia_velha_de_cada_peca_do_bin(tmp_path: Path) -> None:
    for nome in _o_que_o_install_poe_no_bin():
        caso = tmp_path / nome
        caso.mkdir()
        saida = _doctor(_lar(caso, velha=nome))
        assert f"diferente deste checkout: {nome} —" in saida, saida


def test_o_doctor_com_todas_as_pecas_iguais_passa(tmp_path: Path) -> None:
    saida = _doctor(_lar(tmp_path))
    assert "[WARN]" not in saida
    assert "iguais a este checkout" in saida


def test_o_doctor_acusa_a_peca_que_nao_e_executavel_ausente(tmp_path: Path) -> None:
    for nome in ("arquivo_de_terceiro.py", "anticheat_conhecido.json"):
        caso = tmp_path / nome
        caso.mkdir()
        saida = _doctor(_lar(caso, sem=nome))
        assert f"[WARN] arquivo {nome} ausente" in saida, saida
        assert "iguais a este checkout" not in saida
