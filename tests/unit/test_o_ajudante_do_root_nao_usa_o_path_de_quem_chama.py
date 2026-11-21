"""O ajudante do root não acha comando nem o bash pelo PATH de quem chama.

O-AJUDANTE-DO-ROOT-NAO-ACHA-O-BASH-PELO-PATH-DE-QUEM-CHAMA-01 (20/11/2026). Todo script que o
install copia para ``/usr/local/lib/hefesto-dualsense4unix`` abre com caminho absoluto e, rodando
como root, fixa o PATH antes de qualquer comando; a regra do sudo de cada ajudante traz o
``Defaults`` do alias. O dublê roda o ajudante como root de um espaço de nomes de usuário
(``unshare -Ur``, sem privilégio nenhum) com ``bash``, ``id``, ``cat`` e companhia falsos na frente
do PATH: nenhum pode ser chamado.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o shebang ``env`` de volta reprova o caso do
dublê (o ``bash`` falso roda); o bloco do PATH tirado reprova o caso do dublê (o ``id`` falso
roda) e o da guarda estática; a regra sem o ``Defaults`` reprova o caso da regra. Os roteiros do
Bluetooth, o Wi-Fi USB e a ponte seguem com ``$(id -u)`` porque os testes deles fazem de conta que
são root com um ``id`` falso; o root de verdade já fixou o PATH antes do primeiro ``id``.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SEGURO = "/usr/sbin:/usr/bin:/sbin:/bin"
AJUDANTES = (
    "hefesto_atualizador_raiz", "hefesto_placa_acordada", "bt_ponte_privilegiada",
    "hefesto_acionador_raiz", "bt_active_mode", "bt_bonds_autorestore", "bt_bonds_restore",
    "bt_bonds_snapshot", "bt_crash_capture", "bt_health_watchdog", "bt_nosniff_now",
    "bt_rebind_orphans", "wifi_usb",
)
GUARDA_PELA_VARIAVEL = (
    "hefesto_atualizador_raiz", "hefesto_placa_acordada", "hefesto_acionador_raiz",
)
BROKER = RAIZ / "src" / "hefesto_dualsense4unix" / "broker" / "hidraw_broker.py"
REGRAS = (
    ("hefesto_atualizador_raiz", "HEFESTO_ATUALIZADOR"),
    ("hefesto_placa_acordada", "HEFESTO_PLACA"),
    ("bt_ponte_privilegiada", "HEFESTO_BT_PONTE"),
)
FALSOS = ("bash", "id", "cat", "sed", "mktemp", "install", "logger", "bluetoothctl", "btmgmt",
          "nvidia-smi", "stat", "readlink", "date", "grep")


def _script(nome: str) -> Path:
    return RAIZ / "scripts" / f"{nome}.sh"


def _antes_do_path_fixo(nome: str) -> list[str]:
    linhas = _script(nome).read_text(encoding="utf-8").splitlines()[1:]
    antes: list[str] = []
    for linha in linhas:
        if linha.strip().startswith("PATH=" + SEGURO):
            return antes
        if linha.strip() and not linha.lstrip().startswith("#"):
            antes.append(linha)
    raise AssertionError(f"{nome}: o PATH seguro nunca é fixado")


@pytest.mark.parametrize("nome", AJUDANTES)
def test_o_ajudante_abre_com_caminho_absoluto_e_fixa_o_path_antes_de_tudo(nome: str) -> None:
    """D-2011-O-AJUDANTE-DO-ROOT-FIXA-O-PROPRIO-PATH: caminho absoluto e PATH fixo antes de tudo."""
    texto = _script(nome).read_text(encoding="utf-8")
    assert texto.splitlines()[0] == "#!/bin/bash", nome
    if nome in GUARDA_PELA_VARIAVEL:
        assert "$(id -u)" not in texto, (
            f"{nome}: a guarda de root pergunta ao `id` do PATH; a variável EUID não depende dele")
    for linha in _antes_do_path_fixo(nome):
        assert (linha.startswith("set -") or linha.startswith('if [[ "${EUID}" -eq 0 ]]')
                or linha == "fi"), f"{nome}: comando antes de fixar o PATH: {linha!r}"


def test_o_broker_abre_com_o_python_do_sistema() -> None:
    assert BROKER.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/python3"


def test_o_pacote_nix_troca_o_shebang_que_o_broker_tem() -> None:
    """D-2011-O-AJUDANTE-DO-ROOT-FIXA-O-PROPRIO-PATH: o Nix reescreve o shebang que a fonte traz."""
    shebang = BROKER.read_text(encoding="utf-8").splitlines()[0]
    nix = (RAIZ / "packaging" / "nix" / "package.nix").read_text(encoding="utf-8")
    assert f'--replace-fail "{shebang}"' in nix


def test_o_duble_de_bin_so_vale_fora_do_root() -> None:
    ponte = _script("bt_ponte_privilegiada").read_text(encoding="utf-8")
    assert 'if [[ -n "${BIN_DE_TESTE}" && "${EUID}" -ne 0 ]]; then' in ponte
    wifi = _script("wifi_usb").read_text(encoding="utf-8")
    assert 'if [ -n "${HEFESTO_WIFI_BIN:-}" ] && [ "${EUID}" != 0 ]; then' in wifi


@pytest.mark.parametrize(("nome", "alias"), REGRAS)
def test_a_regra_do_sudo_traz_o_secure_path_do_alias(nome: str, alias: str) -> None:
    saida = subprocess.run(
        [str(_script(nome)), "regra-sudo", "fulana"], capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin"},
    ).stdout
    linha = f'Defaults!{alias} secure_path="{SEGURO}", env_reset'
    assert linha in saida.splitlines()
    assert saida.index(f"Cmnd_Alias {alias} =") < saida.index(linha) < saida.index("NOPASSWD")


@pytest.mark.skipif(not Path("/usr/sbin/visudo").exists(), reason="sem visudo")
@pytest.mark.parametrize(("nome", "alias"), REGRAS)
def test_o_visudo_aceita_a_regra_com_o_defaults(nome: str, alias: str, tmp_path: Path) -> None:
    saida = subprocess.run(
        [str(_script(nome)), "regra-sudo", "fulana"], capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin"},
    ).stdout
    regra = tmp_path / "regra"
    regra.write_text(saida, encoding="utf-8")
    rc = subprocess.run(["/usr/sbin/visudo", "-cf", str(regra)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr + rc.stdout


def _raiz_de_mentira_funciona() -> bool:
    if shutil.which("unshare") is None:
        return False
    rc = subprocess.run(["unshare", "-Ur", "/bin/true"], capture_output=True)
    return rc.returncode == 0


@pytest.mark.skipif(not _raiz_de_mentira_funciona(), reason="sem espaço de nomes de usuário")
@pytest.mark.parametrize(
    ("nome", "argv"),
    (("hefesto_atualizador_raiz", ["regra-sudo", "fulana"]),
     ("hefesto_placa_acordada", ["regra-sudo", "fulana"]),
     ("bt_ponte_privilegiada", ["regra-sudo", "fulana"]),
     ("hefesto_acionador_raiz", ["nada"])),
)
def test_como_root_nenhum_comando_do_path_de_quem_chama_roda(
        nome: str, argv: list[str], tmp_path: Path) -> None:
    """D-2011-O-AJUDANTE-DO-ROOT-FIXA-O-PROPRIO-PATH: como root, nada do PATH de fora roda."""
    falsos = tmp_path / "falsos"
    falsos.mkdir()
    marca = tmp_path / "chamado"
    for comando in FALSOS:
        alvo = falsos / comando
        alvo.write_text(f"#!/bin/sh\necho {comando} >> {marca}\nexit 0\n", encoding="utf-8")
        alvo.chmod(0o755)
    ambiente = {"PATH": f"{falsos}:/usr/bin:/bin", "HOME": str(tmp_path),
                "HEFESTO_BT_BIN": str(falsos), "HEFESTO_WIFI_BIN": str(falsos)}
    subprocess.run(
        ["unshare", "-Ur", str(_script(nome)), *argv], capture_output=True, text=True,
        env=ambiente, check=False, timeout=60)
    chamados = marca.read_text(encoding="utf-8").split() if marca.exists() else []
    assert chamados == [], f"{nome} rodou do PATH de quem chama: {chamados}"
    assert os.access(_script(nome), os.X_OK)


def test_a_lista_dos_ajudantes_e_a_que_o_install_copia() -> None:
    camada = (RAIZ / "scripts" / "lib" / "camada_de_maquina.sh").read_text(encoding="utf-8")
    for nome in AJUDANTES:
        assert re.search(rf"\b{nome}\.sh\b", camada), nome
