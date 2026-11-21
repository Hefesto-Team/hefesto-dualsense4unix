"""O-UNINSTALL-TIRA-A-COPIA-DO-DONO-QUE-O-INSTALL-POE-NO-BIN-01: o par do ``bin/`` do produto.

O install declara cada peça do ``~/.local/share/hefesto-dualsense4unix/bin/`` num alvo nomeado
(``*_TARGET``). O uninstall tem de tirar todas e deixar a pasta vazia sair. A régua lê os alvos do
install, nunca uma lista escrita aqui, e o trecho do uninstall roda num lar de mentira com guarda
que sai se o ``HOME`` for o de verdade.

A MORDIDA da sprint: o trecho do uninstall sem a remoção do dono dos arquivos de terceiro deixa o
``arquivo_de_terceiro.py`` e a pasta ``bin/``, e os dois testes reprovam nomeando o arquivo; a peça
nova posta ao lado de outro alvo (``${CAMADAS_TARGET%/*}/...``), sem alvo próprio, também reprova.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
BIN = ".local/share/hefesto-dualsense4unix/bin"
ALVO = re.compile(
    r'^readonly \w+_TARGET="\$\{HOME\}/\.local/share/hefesto-dualsense4unix/bin/([\w.-]+)"$',
    re.MULTILINE)


def _o_que_o_install_poe_no_bin() -> set[str]:
    return set(ALVO.findall(INSTALL.read_text(encoding="utf-8")))


def _o_trecho_do_bin_no_uninstall() -> str:
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.index('readonly CAMADAS_TARGET="')
    marca = f'rmdir "${{HOME}}/{BIN}"'
    fim = texto.index("\n", texto.index(marca, inicio))
    return texto[inicio:fim]


def test_o_install_declara_cada_peca_do_bin_num_alvo_nomeado() -> None:
    pecas = _o_que_o_install_poe_no_bin()
    assert len(pecas) >= 5
    assert "arquivo_de_terceiro.py" in pecas
    texto = INSTALL.read_text(encoding="utf-8")
    avulsas = re.findall(
        r'install -Dm\d+ [^\n]*(?:\\\n[^\n]*)?"\$\{HOME\}/' + re.escape(BIN) + "/",
        texto)
    assert not avulsas
    alvos_do_bin = set(re.findall(
        r'^readonly (\w+_TARGET)="\$\{HOME\}/' + re.escape(BIN) + "/", texto, re.MULTILINE))
    derivadas = [
        linha.strip() for linha in texto.splitlines()
        if any(f"${{{alvo}%/*}}/" in linha for alvo in alvos_do_bin)
    ]
    assert derivadas == [], f"peça do bin/ sem alvo nomeado, ao lado de outro alvo: {derivadas}"


def test_o_uninstall_nomeia_toda_peca_que_o_install_poe_no_bin() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    sem_volta = {p for p in _o_que_o_install_poe_no_bin() if f"/bin/{p}" not in texto}
    assert sem_volta == set(), f"o install põe no bin/ e o uninstall não tira: {sorted(sem_volta)}"


def test_o_trecho_do_uninstall_deixa_o_bin_vazio_e_o_tira(tmp_path: Path) -> None:
    lar = tmp_path / "lar"
    assert lar.resolve() != Path(os.path.expanduser("~")).resolve()
    pasta = lar / BIN
    pasta.mkdir(parents=True)
    for peca in sorted(_o_que_o_install_poe_no_bin()):
        (pasta / peca).write_text("peça\n", encoding="utf-8")
    roteiro = (
        'set -u\n'
        'case "${HOME}" in "' + str(lar) + '") ;; *) echo "HOME de verdade" >&2; exit 90 ;; esac\n'
        'log() { :; }\nROOT_DIR=/nao-existe\n'
        'ESTADOS_DO_HEFESTO=()\n' + _o_trecho_do_bin_no_uninstall() + "\n"
    )
    ambiente = {"HOME": str(lar), "PATH": "/usr/bin:/bin"}
    resultado = subprocess.run(
        ["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, resultado.stderr
    restou = sorted(p.name for p in pasta.iterdir()) if pasta.exists() else []
    assert restou == [], f"ficou no bin/: {restou}"
    assert not pasta.exists(), "o bin/ vazio devia ter saído"
