"""O uninstall devolve o portal da distribuição (07/11/2026).

O install troca o ``xdg-desktop-portal-cosmic`` pelo da casa, com o sufixo ``+0~hefesto1``, grava a
versão de antes e fixa o pino do apt; o uninstall não citava nenhum dos dois. Agora ele tira o pino
sempre e devolve o pacote na forma do PipeWire: ``--restore-portal``, a resposta «s» ou, com
``--yes`` e sem TTY, preserva e diz.

Nada aqui troca pacote: a função roda num bash com ``dpkg-query``, ``apt-get``, ``sudo`` e
``systemctl`` de mentira, o pino num arquivo do ``tmp_path`` e um lar de mentira. O ensaio usa o
próprio bloco ``--dry-run`` do ``uninstall.sh``.

MORDIDA: tirar a função, a chamada no fluxo, o pedido de sudo ou o ``rm`` do pino reprova.
"""
from __future__ import annotations

import os
import pty
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTE = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
BASE = (RAIZ / "assets" / "portal-cosmic-backport" / "BASELINE").read_text(encoding="utf-8")
BASH = shutil.which("bash") or "/bin/bash"

PACOTE = "xdg-desktop-portal-cosmic"
POP = "1.11.0~1792525517~24.04~f448ddf"
CASA = f"{POP}+0~hefesto1"
ALVO = f"{PACOTE}={POP}"


def _funcao(nome: str) -> str:
    inicio = FONTE.index(f"{nome}() {{\n")
    return FONTE[inicio : FONTE.index("\n}\n", inicio) + 3]


def _bloco_do_ensaio() -> str:
    inicio = FONTE.index('if [[ "${DRY_RUN}" -eq 1 ]]; then\n    exec 3>&1')
    return FONTE[inicio : FONTE.index("\nfi\n", inicio) + 4]


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


@dataclass
class Corrida:
    rc: int
    saida: str
    chamadas: list[str]
    pino: Path

    def devolveu(self) -> bool:
        return any(c.startswith("apt-get install ") and " -s " not in f"{c} "
                   for c in self.chamadas)


def _correr(
    tmp_path: Path,
    *,
    registro: bool = True,
    versao: str = CASA,
    pino: bool = True,
    flag: bool = False,
    auto_yes: bool = True,
    resposta: str | None = None,
    sudo_ok: bool = True,
    simulacao_recusada: bool = False,
    remv: str = "",
    ensaio: bool = False,
) -> Corrida:
    lar = tmp_path / "lar"
    cache = lar / ".cache" / "hefesto-dualsense4unix" / "portal-cosmic-backport"
    cache.mkdir(parents=True)
    if registro:
        (cache / "VERSOES-ANTERIORES.txt").write_text(f"{ALVO}\n", encoding="utf-8")
    trava = tmp_path / "hefesto-portal-cosmic"
    if pino:
        trava.write_text("Package: src:xdg-desktop-portal-cosmic\n", encoding="utf-8")
    diario = tmp_path / "chamadas.log"
    fakes = tmp_path / "fakes"
    _exe(fakes, "dpkg-query", f'echo "ii |{versao}"\n')
    _exe(fakes, "apt-get",
         f'printf "apt-get %s\\n" "$*" >> "{diario}"\n'
         'for a in "$@"; do [[ "$a" == "-s" ]] && { '
         f'{"exit 100; " if simulacao_recusada else ""}'
         f'printf "{remv}Inst x\\n"; exit 0; }}; done\nexit 0\n')
    _exe(fakes, "sudo",
         f'printf "sudo %s\\n" "$*" >> "{diario}"\n'
         f'if [[ "$1" == "-n" ]]; then exit {0 if sudo_ok else 1}; fi\n'
         'exec "$@"\n')
    _exe(fakes, "systemctl", f'printf "systemctl %s\\n" "$*" >> "{diario}"\nexit 0\n')
    script = (
        "set -euo pipefail\n"
        "log() { printf '[uninstall] %s\\n' \"$*\"; }\n"
        + (_bloco_do_ensaio() if ensaio else "")
        + f"PORTAL_PREF={trava}\n"
        "PORTAL_UNIDADE=org.freedesktop.impl.portal.desktop.cosmic.service\n"
        + _funcao("devolver_o_portal")
        + "devolver_o_portal\n"
    )
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "AUTO_YES": "1" if auto_yes else "0",
        "DRY_RUN": "1" if ensaio else "0",
        "RESTORE_PORTAL": "1" if flag else "0",
    }
    if resposta is None:
        r = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                           timeout=60, check=False, stdin=subprocess.DEVNULL)
    else:
        mestre, escravo = pty.openpty()
        try:
            os.write(mestre, (resposta + "\n").encode())
            r = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                               timeout=60, check=False, stdin=escravo)
        finally:
            os.close(mestre)
            os.close(escravo)
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return Corrida(r.returncode, r.stdout + r.stderr, chamadas, trava)


def test_a_flag_devolve_com_a_versao_do_registro_e_tira_o_pino(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True)
    assert c.rc == 0, c.saida
    assert c.devolveu(), c.chamadas
    instalar = next(x for x in c.chamadas if x.startswith("apt-get install -y"))
    assert "--allow-downgrades" in instalar and ALVO in instalar
    assert any("try-restart --no-block" in x and BASE.split("PORTAL_UNIDADE=")[1].split()[0] in x
               for x in c.chamadas)
    assert not c.pino.exists()


def test_a_resposta_sim_devolve_e_avisa_o_compartilhamento(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False, resposta="s")
    assert c.devolveu(), c.saida
    assert "compartilhamento de tela aberto cai uma vez" in c.saida
    assert not c.pino.exists()


def test_enter_preserva_e_diz_a_flag_mas_o_pino_sai(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False, resposta="")
    assert not c.devolveu(), c.chamadas
    assert "--restore-portal" in c.saida
    assert not c.pino.exists()


def test_com_yes_e_sem_tty_preserva_e_diz_e_o_pino_sai(tmp_path: Path) -> None:
    c = _correr(tmp_path)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "preservado" in c.saida and "--restore-portal" in c.saida
    assert "o próximo apt upgrade volta o portal" in c.saida
    assert not c.pino.exists()


def test_sem_registro_so_o_pino_sai(tmp_path: Path) -> None:
    c = _correr(tmp_path, registro=False)
    assert c.rc == 0, c.saida
    assert "só o pino do apt sai" in c.saida
    assert not c.pino.exists()


def test_o_portal_que_nao_e_o_da_casa_fica(tmp_path: Path) -> None:
    c = _correr(tmp_path, versao=POP, flag=True)
    assert not c.devolveu(), c.chamadas
    assert not c.pino.exists()


def test_o_apt_que_recusa_nao_troca_nada(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, simulacao_recusada=True)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "nada foi trocado" in c.saida
    assert not c.pino.exists()


def test_o_apt_que_tiraria_outro_pacote_nao_troca_nada(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, remv="Remv outro\\n")
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "tiraria da máquina: outro" in c.saida
    assert not c.pino.exists()


def test_sem_sudo_nada_sai_e_diz_o_comando(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, sudo_ok=False)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert c.pino.exists()
    assert f"sudo rm -f {c.pino}" in c.saida and ALVO in c.saida


def test_o_ensaio_lista_as_duas_linhas_e_nao_toca_em_nada(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, ensaio=True)
    assert c.rc == 0, c.saida
    faria = [linha for linha in c.saida.splitlines() if "FARIA" in linha]
    assert any("apt-get install" in linha and ALVO in linha for linha in faria), c.saida
    assert any(f"rm -f {c.pino}" in linha for linha in faria), c.saida
    assert c.pino.exists()
    assert not c.devolveu(), c.chamadas


def test_o_ensaio_sem_a_flag_lista_o_pino_e_diz_que_preserva(tmp_path: Path) -> None:
    c = _correr(tmp_path, ensaio=True)
    assert c.rc == 0, c.saida
    assert "preservado" in c.saida
    assert any(f"rm -f {c.pino}" in linha for linha in c.saida.splitlines() if "FARIA" in linha)


def test_o_passo_roda_no_uninstall_e_o_sudo_e_pedido_antes() -> None:
    chamada = FONTE.index("\ndevolver_o_portal\n")
    assert FONTE.index("\ndevolver_o_pipewire\n") < chamada
    assert chamada < FONTE.index('"${HOME}/.cache/hefesto-dualsense4unix" \\\n')
    pedido = '[[ -e /etc/apt/preferences.d/hefesto-portal-cosmic ]] && _NEEDS_SUDO=1'
    assert pedido in FONTE and FONTE.index(pedido) < chamada


def test_a_ajuda_diz_a_flag() -> None:
    saida = subprocess.run([BASH, str(RAIZ / "uninstall.sh"), "--help"], capture_output=True,
                           text=True, timeout=30, check=False)
    assert "--restore-portal" in saida.stdout


def test_a_unidade_e_o_pacote_sao_os_do_install() -> None:
    assert f"PORTAL_PACOTE={PACOTE}" in BASE
    unidade = BASE.split("PORTAL_UNIDADE=")[1].split()[0]
    assert f"PORTAL_UNIDADE={unidade}\n" in FONTE
    assert "/etc/apt/preferences.d/hefesto-portal-cosmic" in FONTE
