"""INSTALL-UNIVERSAL (18/09/2026) — o UCM do DualSense no cabo, em qualquer máquina.

A vibração dos jogos da Sony pelo cabo depende do sink `…HiFi__Speaker__sink`,
que só nasce com a placa do controle aberta por UCM. O gancho do produto
(`scripts/install_ucm_dualsense.sh`) é lido pelo `ucm.conf` do SISTEMA. Quatro
buracos que só apareciam fora da bancada dela, e cada régua abaixo morde um:

1. o `alsa-ucm-conf` não era declarado no censo do install — no apt ele chega
   como `Recommends`, e numa instalação sem recomendações simplesmente falta;
2. o doctor dizia "esta distro não usa UCM" (informação) com um DualSense
   plugado e sem o `ucm.conf` — a vibração sumia como se fosse escolha;
3. o `doctor --fix` não refazia o gancho, e um controlador USB que chega depois
   do install (uma dock) ficava sem ele para sempre;
4. numa distro imutável o `/usr` é só de leitura, e o install mandava rodar de
   novo um roteiro que ali nunca vai funcionar.

**FORA DAQUI, e declarado:** o `Syntax 6` do `assets/ucm/DualSense-gancho.conf`.
O cético mediu que o `Syntax 6` pede libasound >= 1.2.7 e que o gancho só usa
o que o nível 4 já tem, mas baixar o número pede conferir com `alsaucm` um
DualSense NO CABO, e os controles da bancada estavam descarregados.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from tests.unit.test_haptica_nativa_01_o_ucm_do_dualsense import (
    NOME_MEDIDO,
    _cards,
    _ganchos,
    _mesa,
    _rodar,
)
from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    PRELUDO_DRIVER,
    _extrai_array,
    _roda,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _doctor_sem_ucm(tmp_path: Path, cards: Path) -> str:
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; check_ucm_do_dualsense'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_RAIZ_UCM": str(tmp_path / "sem-ucm"),
            "HEFESTO_PROC_CARDS": str(cards),
        },
    )
    return r.stdout + r.stderr


# ------------------------------------------------------------ 2. o doctor


def test_sem_ucm_conf_com_dualsense_no_cabo_e_aviso(tmp_path: Path) -> None:
    """A MORDIDA: volte ao `info` incondicional e esta régua reprova."""
    saida = _doctor_sem_ucm(tmp_path, _cards(tmp_path, NOME_MEDIDO))
    assert "[WARN] DualSense no cabo e sem" in saida
    assert "alsa-ucm-conf" in saida
    assert "esta distro não usa UCM" not in saida


def test_sem_ucm_conf_e_sem_dualsense_continua_informacao(tmp_path: Path) -> None:
    saida = _doctor_sem_ucm(tmp_path, _cards(tmp_path))
    assert "[WARN]" not in saida
    assert "esta distro não usa UCM" in saida


# ------------------------------------------------------ 3. o --fix refaz


def _corpo(nome: str) -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    m = re.search(rf"^{nome}\(\) \{{$.*?^\}}$", texto, re.MULTILINE | re.DOTALL)
    assert m is not None, f"{nome} sumiu do doctor"
    return "\n".join(
        linha for linha in m.group(0).splitlines() if not linha.lstrip().startswith("#")
    )


def test_o_fix_refaz_o_gancho_antes_de_reiniciar_o_wireplumber() -> None:
    """O restart do `fix_wireplumber_default_source.sh --install` é o que reabre
    a placa pelo gancho — o gancho tem de estar no disco ANTES dele. Arranque a
    chamada, ou ponha-a depois, e esta régua reprova.
    """
    corpo = _corpo("apply_fixes")
    ucm = corpo.find('bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh"')
    wireplumber = corpo.find("fix_wireplumber_default_source.sh\" --install")
    assert ucm >= 0, "o --fix não chama o install_ucm_dualsense.sh"
    assert wireplumber >= 0
    assert ucm < wireplumber, "o gancho tem de estar no disco antes do restart do WirePlumber"


def test_o_fix_guarda_a_existencia_do_roteiro() -> None:
    """Pacote que leva o doctor sem o roteiro não pode virar "falhou" mudo."""
    corpo = _corpo("apply_fixes")
    assert '[[ -f "${ROOT_DIR}/scripts/install_ucm_dualsense.sh" ]]' in corpo


# -------------------------------------------------- 1. o censo do install


def test_o_censo_declara_o_ucm_do_sistema_pelo_arquivo() -> None:
    tabela = _extrai_array("_DEPS_DE_SISTEMA")
    linha = [x for x in tabela.splitlines() if x.strip().startswith('"alsa-ucm|')]
    assert linha, "o alsa-ucm-conf saiu do censo do install"
    assert "|importante|arquivo:/usr/share/alsa/ucm2/ucm.conf|" in linha[0]


def test_o_nome_do_pacote_nas_tres_familias() -> None:
    esperado = {"apt": "alsa-ucm-conf", "dnf": "alsa-ucm", "pacman": "alsa-ucm-conf"}
    for familia, nome in esperado.items():
        proc = _roda(f"_pkg_nome alsa-ucm {familia}")
        assert proc.stdout.strip() == nome, (familia, proc.stdout, proc.stderr)


def test_a_checagem_por_arquivo_responde_pelo_efeito(tmp_path: Path) -> None:
    """A MORDIDA: sem o ramo `arquivo:`, o `*)` do `_dep_presente` responde
    "presente" para o que não conhece, e o pacote nunca seria pedido.
    """
    existe = tmp_path / "ucm.conf"
    existe.write_text("Syntax 4\n", encoding="utf-8")
    proc = _roda(
        f'_dep_presente "arquivo:{existe}" && printf "TEM\\n"; '
        f'_dep_presente "arquivo:{tmp_path}/nao-existe" || printf "FALTA\\n"',
        preludo=PRELUDO_DRIVER,
    )
    assert "TEM" in proc.stdout, proc.stdout + proc.stderr
    assert "FALTA" in proc.stdout, proc.stdout + proc.stderr


# ------------------------------------------------ 4. o /usr só de leitura


def _findmnt_de_mentira(tmp_path: Path, opcoes: str) -> str:
    """Um `findmnt` que responde as opções pedidas — o /usr imutável sem root."""
    binario = tmp_path / "bin-findmnt"
    binario.mkdir()
    falso = binario / "findmnt"
    falso.write_text(f"#!/bin/sh\nprintf '%s\\n' '{opcoes}'\n", encoding="utf-8")
    falso.chmod(0o755)
    return f"{binario}:{os.environ.get('PATH', '/usr/bin:/bin')}"


def _rodar_com_path(ucm: Path, sysfs: Path, caminho: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_ucm_dualsense.sh"),
         "--raiz-ucm", str(ucm), "--sysfs", str(sysfs)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PATH": caminho},
    )


def test_usr_so_de_leitura_nao_grava_e_sai_limpo(tmp_path: Path) -> None:
    """A MORDIDA: tire o `usr_so_leitura` e o roteiro volta a gravar (aqui, onde
    o tmp é gravável) — numa distro imutável, o `install -D` falharia.
    """
    sysfs, ucm = _mesa(tmp_path)
    r = _rodar_com_path(ucm, sysfs, _findmnt_de_mentira(tmp_path, "ro,relatime"))
    assert r.returncode == 0, r.stderr
    assert "só de leitura" in r.stdout
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}


def test_usr_gravavel_segue_como_antes(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    r = _rodar_com_path(ucm, sysfs, _findmnt_de_mentira(tmp_path, "rw,relatime"))
    assert r.returncode == 0, r.stderr
    assert len(_ganchos(ucm)) > 1


def test_sem_findmnt_a_resposta_e_nao_sei_e_o_roteiro_segue(tmp_path: Path) -> None:
    """O PATH sem `findmnt`: o roteiro grava como gravava antes desta leva."""
    sysfs, ucm = _mesa(tmp_path)
    magro = tmp_path / "magro"
    magro.mkdir()
    for ferramenta in ("bash", "basename", "dirname", "readlink", "sort", "grep",
                       "cmp", "install", "rm", "mkdir", "cat", "id"):
        real = shutil.which(ferramenta)
        if real:
            (magro / ferramenta).symlink_to(real)
    r = _rodar_com_path(ucm, sysfs, str(magro))
    assert r.returncode == 0, r.stderr
    assert len(_ganchos(ucm)) > 1


def test_o_roteiro_de_sempre_continua_verde(tmp_path: Path) -> None:
    """A árvore de mentira em tmp é gravável: o `findmnt` de verdade diz `rw`."""
    sysfs, ucm = _mesa(tmp_path)
    assert _rodar(ucm, sysfs).returncode == 0
    assert len(_ganchos(ucm)) > 1
