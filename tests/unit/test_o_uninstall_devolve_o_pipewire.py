"""O uninstall pergunta e devolve o PipeWire de antes (O-UNINSTALL-DEVOLVE-O-PIPEWIRE-DE-ANTES-01).

O passo 3f-bis do install grava ``pacote=versão`` de cada pacote que trocou e fixa a prioridade
do apt. O ``uninstall.sh`` lê o registro, devolve com ``--restore-pipewire`` ou com a resposta
«s», preserva com ``--yes`` e sem TTY, recusa com a Steam aberta e tira a trava do apt sempre.

Nada aqui troca pacote: a função do passo roda num bash com ``dpkg-query``, ``apt-get``,
``sudo``, ``pgrep`` e ``systemctl`` de mentira no PATH, a trava num arquivo do ``tmp_path`` e um
lar de mentira.
"""

from __future__ import annotations

import os
import pty
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_o_ensaio_do_uninstall_nao_escreve import PATH_DO_SISTEMA, _dublar, _retrato

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"
FONTE = UNINSTALL.read_text(encoding="utf-8")

PW_CASA = "1.6.9-0~hefesto24.04.1"
WP_CASA = "0.5.18-0~hefesto24.04.1"
PW_POP = "1.6.8-1pop1~1787688714~24.04~fdff050"
WP_POP = "0.5.12-2pop1~1766191027~24.04~d4bf441"

#: O que o install gravou: o que a máquina tinha antes, um ``pacote=versão`` por linha.
REGISTRO = (
    f"pipewire={PW_POP}\n"
    f"libpipewire-0.3-0t64:amd64={PW_POP}\n"
    f"pipewire-bin={PW_POP}\n"
    f"wireplumber={WP_POP}\n"
)

#: A máquina depois do install: tudo na versão da casa.
MAQUINA_DA_CASA = {
    "pipewire": PW_CASA,
    "libpipewire-0.3-0t64": PW_CASA,
    "pipewire-bin": PW_CASA,
    "wireplumber": WP_CASA,
}

DEVOLVE = (f"pipewire={PW_POP}", f"libpipewire-0.3-0t64:amd64={PW_POP}", f"wireplumber={WP_POP}")


def _funcao(nome: str) -> str:
    inicio = FONTE.index(f"{nome}() {{\n")
    return FONTE[inicio : FONTE.index("\n}\n", inicio) + 3]


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
    pref: Path

    def chamou(self, trecho: str) -> bool:
        return any(trecho in linha for linha in self.chamadas)

    def devolveu(self) -> bool:
        """O ``apt-get install`` de verdade (a simulação ``-s`` não conta)."""
        return any(
            linha.startswith("apt-get install ") and " -s " not in f"{linha} "
            for linha in self.chamadas
        )


def _correr(
    tmp_path: Path,
    *,
    registro: str | None = REGISTRO,
    maquina: dict[str, str] | None = None,
    pref: bool = True,
    flag: bool = False,
    auto_yes: bool = True,
    resposta: str | None = None,
    steam_aberta: bool = False,
    sudo_ok: bool = True,
    remv: tuple[str, ...] = (),
    simulacao_recusada: bool = False,
) -> Corrida:
    maquina = MAQUINA_DA_CASA if maquina is None else maquina
    lar = tmp_path / "lar"
    cache = lar / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport"
    cache.mkdir(parents=True)
    if registro is not None:
        (cache / "VERSOES-ANTERIORES.txt").write_text(registro, encoding="utf-8")
    trava = tmp_path / "preferences.d" / "hefesto-pipewire"
    trava.parent.mkdir()
    if pref:
        trava.write_text("Package: src:pipewire\nPin-Priority: 500\n", encoding="utf-8")
    diario = tmp_path / "chamadas.log"
    fakes = tmp_path / "fakes"
    casos = "\n".join(f'  {pkg}) echo "ii |{ver}" ;;' for pkg, ver in maquina.items())
    _exe(
        fakes,
        "dpkg-query",
        'pkg=""\nfor a in "$@"; do case "$a" in -*) ;; *) pkg="$a" ;; esac; done\n'
        f'case "${{pkg%%:*}}" in\n{casos}\n  *) exit 1 ;;\nesac\n',
    )
    remv_txt = "".join(f"Remv {p} [x]\\n" for p in remv)
    _exe(
        fakes,
        "apt-get",
        f'printf "apt-get %s\\n" "$*" >> "{diario}"\n'
        'for a in "$@"; do [[ "$a" == "-s" ]] && { '
        f'{"exit 100; " if simulacao_recusada else ""}'
        f'printf "Inst pipewire [x] (y)\\n{remv_txt}"; exit 0; }}; done\n'
        "exit 0\n",
    )
    _exe(
        fakes,
        "sudo",
        f'printf "sudo %s\\n" "$*" >> "{diario}"\n'
        f'if [[ "$1" == "-n" ]]; then exit {0 if sudo_ok else 1}; fi\n'
        'exec "$@"\n',
    )
    _exe(
        fakes,
        "pgrep",
        f'printf "pgrep %s\\n" "$*" >> "{diario}"\nexit {0 if steam_aberta else 1}\n',
    )
    _exe(fakes, "systemctl", f'printf "systemctl %s\\n" "$*" >> "{diario}"\nexit 0\n')

    script = (
        "set -euo pipefail\n"
        "log() { printf '[uninstall] %s\\n' \"$*\"; }\n"
        f"PIPEWIRE_PREF={trava}\n"
        + _funcao("devolver_o_pipewire")
        + "devolver_o_pipewire\n"
    )
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "AUTO_YES": "1" if auto_yes else "0",
        "DRY_RUN": "0",
        "RESTORE_PIPEWIRE": "1" if flag else "0",
    }
    if resposta is None:
        r = subprocess.run(
            [BASH, "-c", script], env=env, capture_output=True, text=True, timeout=60,
            check=False, stdin=subprocess.DEVNULL,
        )
        rc, saida = r.returncode, r.stdout + r.stderr
    else:
        mestre, escravo = pty.openpty()
        try:
            os.write(mestre, (resposta + "\n").encode())
            r = subprocess.run(
                [BASH, "-c", script], env=env, capture_output=True, text=True, timeout=60,
                check=False, stdin=escravo,
            )
        finally:
            os.close(mestre)
            os.close(escravo)
        rc, saida = r.returncode, r.stdout + r.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return Corrida(rc, saida, chamadas, trava)


# ---------------------------------------------------------------- devolver


def test_a_flag_devolve_sem_perguntar_com_as_versoes_do_arquivo(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True)
    assert c.rc == 0, c.saida
    assert c.devolveu(), c.chamadas
    install = next(x for x in c.chamadas if x.startswith("apt-get install -y"))
    assert "--allow-downgrades" in install
    for pacote in DEVOLVE:
        assert pacote in install
    assert f"pipewire-bin={PW_POP}" in install
    assert c.chamou("systemctl --user restart pipewire pipewire-pulse wireplumber")


def test_a_resposta_sim_devolve(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False, resposta="s")
    assert c.rc == 0, c.saida
    assert c.devolveu(), c.saida
    assert f"pipewire={PW_POP}" in "\n".join(c.chamadas)
    assert "REINICIA o som" in c.saida, "a pergunta tem de avisar que o som reinicia"
    assert not c.pref.exists()


def test_a_resposta_nao_preserva_e_diz_a_flag(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False, resposta="n")
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "--restore-pipewire" in c.saida


def test_enter_sem_resposta_preserva(tmp_path: Path) -> None:
    """O padrão da pergunta é «não»: trocar o PipeWire reinicia o som."""
    c = _correr(tmp_path, auto_yes=False, resposta="")
    assert not c.devolveu(), c.chamadas


@pytest.mark.parametrize("com_tty", [False, True], ids=["sem-tty", "com-tty"])
def test_yes_preserva_e_diz_a_flag_que_devolve(tmp_path: Path, com_tty: bool) -> None:
    """`--yes` não responde «sim» a esta pergunta: devolver reinicia o som."""
    c = _correr(tmp_path, auto_yes=True, resposta="s" if com_tty else None)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "--restore-pipewire" in c.saida
    assert f"pipewire={PW_POP}" in c.saida, "a fala diz o que a flag devolveria"


def test_sem_tty_e_sem_yes_tambem_preserva(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "--restore-pipewire" in c.saida


# ---------------------------------------------------------------- a trava do apt


@pytest.mark.parametrize(
    "caso",
    ["devolvendo", "preservando", "sem-registro", "steam-aberta", "resposta-nao"],
)
def test_a_trava_do_apt_sai_nos_dois_casos_e_na_recusa(tmp_path: Path, caso: str) -> None:
    """MORDIDA: tirar a remoção da trava deixa o arquivo, e este teste reprova."""
    parametros: dict[str, dict[str, Any]] = {
        "devolvendo": {"flag": True},
        "preservando": {},
        "sem-registro": {"registro": None},
        "steam-aberta": {"flag": True, "steam_aberta": True},
        "resposta-nao": {"auto_yes": False, "resposta": "n"},
    }
    c = _correr(tmp_path, **parametros[caso])
    assert c.rc == 0, c.saida
    assert not c.pref.exists(), f"a trava do Hefesto ficou ({caso}):\n{c.saida}"
    assert c.chamou(f"sudo rm -f {c.pref}")


def test_sem_sudo_a_trava_fica_e_a_fala_diz_o_comando(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, sudo_ok=False)
    assert c.rc == 0, c.saida
    assert c.pref.exists()
    assert not c.devolveu(), c.chamadas
    assert f"sudo rm -f {c.pref}" in c.saida
    assert "apt-get install --allow-downgrades" in c.saida, "diz como devolver à mão"


# ---------------------------------------------------------------- a Steam aberta


def test_com_a_steam_aberta_a_flag_recusa_e_diz_por_que(tmp_path: Path) -> None:
    """MORDIDA: tirar a recusa faz o apt trocar o PipeWire com a Steam aberta."""
    c = _correr(tmp_path, flag=True, steam_aberta=True)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert not c.chamou("systemctl"), "recusou e ainda reiniciou o som"
    assert "Steam" in c.saida and "NÃO foi devolvido" in c.saida
    assert "./uninstall.sh --restore-pipewire" in c.saida, "diz o que fazer depois"


def test_com_a_steam_aberta_a_pergunta_nem_e_feita(tmp_path: Path) -> None:
    c = _correr(tmp_path, auto_yes=False, resposta="s", steam_aberta=True)
    assert not c.devolveu(), c.chamadas
    assert "Devolver o PipeWire de antes?" not in c.saida
    assert "Steam" in c.saida


# ---------------------------------------------------------------- nada a fazer


def test_sem_registro_e_sem_trava_nao_faz_nada(tmp_path: Path) -> None:
    """O install nunca construiu o PipeWire: nem sudo, nem apt, nem pgrep."""
    c = _correr(tmp_path, registro=None, pref=False, flag=True)
    assert c.rc == 0, c.saida
    assert c.chamadas == [], c.chamadas
    assert "nada a devolver" in c.saida


def test_o_que_a_maquina_ja_tem_nas_versoes_do_registro_nao_e_trocado(tmp_path: Path) -> None:
    ja_de_antes = {"pipewire": PW_POP, "libpipewire-0.3-0t64": PW_POP, "wireplumber": WP_POP}
    c = _correr(tmp_path, maquina=ja_de_antes, flag=True)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "nada a devolver" in c.saida
    assert not c.pref.exists(), "a trava sai mesmo sem pacote a devolver"


def test_pacote_do_registro_que_nao_esta_instalado_fica_fora_da_lista(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, maquina={"pipewire": PW_CASA})
    install = next(x for x in c.chamadas if x.startswith("apt-get install -y"))
    assert f"pipewire={PW_POP}" in install
    assert "wireplumber=" not in install and "pipewire-bin=" not in install


def test_linha_vazia_ou_pela_metade_do_registro_nao_quebra(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, registro=f"\npipewire=\n=1.0\npipewire={PW_POP}\n")
    assert c.rc == 0, c.saida
    install = next(x for x in c.chamadas if x.startswith("apt-get install -y"))
    assert install.endswith(f"pipewire={PW_POP}"), install


# ---------------------------------------------------------------- o que o apt diria


def test_se_a_simulacao_tira_pacote_da_maquina_nada_e_trocado(tmp_path: Path) -> None:
    """MORDIDA: tirar a conferência do `Remv` troca o PipeWire levando pacote junto."""
    c = _correr(tmp_path, flag=True, remv=("steam-devices",))
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "steam-devices" in c.saida and "nada foi trocado" in c.saida


def test_se_o_apt_recusa_a_simulacao_nada_e_trocado(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, simulacao_recusada=True)
    assert c.rc == 0, c.saida
    assert not c.devolveu(), c.chamadas
    assert "apt-get install -s --allow-downgrades" in c.saida
    assert not c.pref.exists()


def test_sem_sudo_o_pipewire_nao_e_devolvido_e_a_fala_diz_como(tmp_path: Path) -> None:
    c = _correr(tmp_path, flag=True, sudo_ok=False)
    assert not c.devolveu()
    assert "sudo indisponível" in c.saida


# ---------------------------------------------------------------- a casa inteira


def test_a_flag_esta_no_roteiro_na_ajuda_e_no_preparo_do_sudo() -> None:
    assert re.search(r"--restore-pipewire\)\s*RESTORE_PIPEWIRE=1", FONTE)
    assert "RESTORE_PIPEWIRE=0" in FONTE
    assert re.search(
        r"\[\[ -e /etc/apt/preferences\.d/hefesto-pipewire \]\] && _NEEDS_SUDO=1", FONTE
    ), "o passo pede root: sem o preparo da credencial, ele cai em «sudo indisponível»"
    r = subprocess.run(
        [BASH, str(UNINSTALL), "--help"], capture_output=True, text=True, timeout=30,
        check=False, env={"PATH": PATH_DO_SISTEMA, "HOME": "/nonexistent"},
    )
    assert r.returncode == 0
    ajuda = r.stdout[r.stdout.index("--restore-pipewire") :][:500]
    assert "pergunta" in ajuda and "--yes" in ajuda and "Steam" in ajuda


def test_o_ensaio_com_a_flag_so_descreve_e_deixa_a_casa_igual(tmp_path: Path) -> None:
    """`--dry-run --restore-pipewire` num lar de mentira: nenhum binário que escreve é chamado."""
    lar = tmp_path / "lar"
    casa = lar / "casa"
    cache = casa / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport"
    cache.mkdir(parents=True)
    (cache / "VERSOES-ANTERIORES.txt").write_text(
        "pipewire=0.0.1-de-mentira\nwireplumber=0.0.1-de-mentira\n", encoding="utf-8"
    )
    xdg = {
        "XDG_CONFIG_HOME": lar / "config",
        "XDG_DATA_HOME": lar / "data",
        "XDG_STATE_HOME": lar / "state",
        "XDG_CACHE_HOME": lar / "cache",
        "XDG_RUNTIME_DIR": lar / "run",
    }
    for pasta in xdg.values():
        pasta.mkdir(parents=True)
    xdg["XDG_RUNTIME_DIR"].chmod(0o700)
    (tmp_path / "tmp").mkdir()
    diario = tmp_path / "dubles-chamados.log"
    _dublar(tmp_path / "dubles", diario)
    env = {
        "HOME": str(casa),
        "PATH": f"{tmp_path / 'dubles'}:{PATH_DO_SISTEMA}",
        "LANG": "C.UTF-8",
        "TMPDIR": str(tmp_path / "tmp"),
        **{k: str(v) for k, v in xdg.items()},
    }
    assert not env["HOME"].startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    flatpak = tmp_path / "dubles" / "flatpak"
    if flatpak.is_file():  # o `flatpak list` real cria o cache dele na primeira vez
        subprocess.run(
            [str(flatpak), "--user", "list"], env=env, capture_output=True, timeout=60,
            check=False,
        )
    antes = _retrato(lar)
    r = subprocess.run(
        [BASH, str(UNINSTALL), "--dry-run", "--restore-pipewire"], env=env,
        capture_output=True, text=True, timeout=240, check=False,
    )
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    chamados = diario.read_text(encoding="utf-8") if diario.exists() else ""
    assert chamados == "", "o ensaio chamou binário que escreve:\n" + chamados
    assert _retrato(lar) == antes, "o ensaio mudou a casa de mentira"
    trava_existe = Path("/etc/apt/preferences.d/hefesto-pipewire").exists()
    faria_a_trava = any(
        "FARIA:" in linha and "rm -f /etc/apt/preferences.d/hefesto-pipewire" in linha
        for linha in r.stdout.splitlines()
    )
    assert faria_a_trava == trava_existe, "o plano tem de dizer a trava quando ela existe"
    assert "PipeWire" in r.stdout, "o passo do PipeWire não falou no ensaio"
