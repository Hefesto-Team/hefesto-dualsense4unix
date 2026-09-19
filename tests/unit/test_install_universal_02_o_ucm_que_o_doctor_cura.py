"""INSTALL-UNIVERSAL (18/09/2026) — o UCM do DualSense no cabo, em qualquer máquina.

A vibração dos jogos da Sony pelo cabo depende do sink `…HiFi__Speaker__sink`,
que só nasce com a placa do controle aberta por UCM. O gancho do produto
(`scripts/install_ucm_dualsense.sh`) é lido pelo `ucm.conf` do SISTEMA. Quatro
buracos que só apareciam fora da bancada dela, e cada régua abaixo morde um:

1. o `alsa-ucm-conf` não era declarado no censo do install — no apt ele chega
   como `Recommends`, e numa instalação sem recomendações simplesmente falta —,
   nem nos pacotes (`debian/control`, `.spec`, `PKGBUILD`), que o censo não vê;
2. o doctor dizia "esta distro não usa UCM" (informação) com um DualSense
   plugado e sem o `ucm.conf` — a vibração sumia como se fosse escolha;
3. o `doctor --fix` não refazia o gancho, e um controlador USB que chega depois
   do install (uma dock) ficava sem ele para sempre;
4. numa distro imutável o `/usr` é só de leitura, e o install mandava rodar de
   novo um roteiro que ali nunca vai funcionar;
5. o `doctor --fix` jogava a resposta do roteiro fora e lia só o código de
   saída — e o roteiro sai 0 também quando NÃO grava (sem `ucm.conf`, com o
   `/usr` só de leitura…). O `--fix` dizia "[ OK ] conferido" exatamente nos
   casos que esta leva quer expor.

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
    _arvore_ucm,
    _cards,
    _ganchos,
    _mesa,
    _rodar,
    _sysfs,
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
    # O `--fix` não instala pacote: o conselho diz a ordem dos dois gestos.
    assert "Depois de instalar o pacote, rode scripts/doctor.sh --fix" in saida


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
    ucm = corpo.find("\n    fix_ucm_do_dualsense\n")
    wireplumber = corpo.find("fix_wireplumber_default_source.sh\" --install")
    assert ucm >= 0, "o --fix não chama o fix_ucm_do_dualsense"
    assert wireplumber >= 0
    assert ucm < wireplumber, "o gancho tem de estar no disco antes do restart do WirePlumber"
    assert 'bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh"' in _corpo("fix_ucm_do_dualsense")


def _sem_sudo(tmp_path: Path) -> Path:
    """Um `sudo` que recusa, na FRENTE do PATH: régua nenhuma daqui pede senha.

    As árvores UCM de mentira moram no tmp, que é gravável — o roteiro nem
    chega a chamar o `sudo`. Este dublê é a trava para o dia em que chegar.
    """
    binario = tmp_path / "bin-sem-sudo"
    binario.mkdir(exist_ok=True)
    falso = binario / "sudo"
    falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    falso.chmod(0o755)
    return binario


def _fix_ucm(
    tmp_path: Path, ucm: Path, sysfs: Path, *, caminho: str | None = None, doctor: Path = DOCTOR
) -> str:
    """Roda o `fix_ucm_do_dualsense` do doctor sobre a árvore e o sysfs de mentira."""
    base = caminho or os.environ.get("PATH", "/usr/bin:/bin")
    r = subprocess.run(
        ["bash", "-c", f'source "{doctor}"; fix_ucm_do_dualsense'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            "PATH": f"{_sem_sudo(tmp_path)}:{base}",
            "HOME": str(tmp_path / "home"),
            "HEFESTO_RAIZ_UCM": str(ucm),
            "HEFESTO_SYSFS": str(sysfs),
        },
    )
    return r.stdout + r.stderr


def test_o_fix_sem_ucm_conf_nao_diz_ok(tmp_path: Path) -> None:
    """A MORDIDA do furo 5: o roteiro sai 0 sem gravar, e o `--fix` dizia OK.

    Volte a ler só o código de saída (ou a saída para /dev/null) e esta régua
    reprova — é a máquina sem `alsa-ucm-conf`, exatamente a que a leva expõe.
    """
    sysfs, _ = _mesa(tmp_path)
    saida = _fix_ucm(tmp_path, tmp_path / "sem-ucm", sysfs)
    assert "[ OK ]" not in saida, saida
    assert "[WARN]" not in saida, "a falta do pacote é o check que acusa, com o DualSense no cabo"
    assert "perfil UCM do DualSense não gravado" in saida
    assert "ucm.conf ausente" in saida
    # O `[ucm] aviso:` do roteiro sai inteiro: dentro da linha do doctor ele
    # dizia "não gravado: aviso: …". MORDIDA: tire o `${fecho#aviso: }`.
    assert "aviso:" not in saida, saida


def test_o_fix_com_usr_so_de_leitura_nao_diz_ok(tmp_path: Path) -> None:
    sysfs, ucm = _mesa(tmp_path)
    saida = _fix_ucm(
        tmp_path, ucm, sysfs, caminho=_findmnt_de_mentira(tmp_path, "ro,relatime")
    )
    assert "[ OK ]" not in saida, saida
    assert "só de leitura" in saida
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}


def test_o_fix_com_ucm_conf_que_nao_le_conf_d_nao_diz_ok(tmp_path: Path) -> None:
    sysfs, _ = _mesa(tmp_path)
    outra = tmp_path / "outra"
    outra.mkdir()
    ucm = _arvore_ucm(outra, com_confd=False)
    saida = _fix_ucm(tmp_path, ucm, sysfs)
    assert "[ OK ]" not in saida, saida
    assert "não procura conf.d/" in saida


def test_o_fix_sem_controlador_que_caiba_no_corte_nao_diz_ok(tmp_path: Path) -> None:
    """Só um controlador de nome curto: o roteiro avisa, não grava, e sai 0."""
    _, ucm = _mesa(tmp_path)
    curto = _sysfs(tmp_path / "curto", {"platform/abc": ["usb7"]})
    saida = _fix_ucm(tmp_path, ucm, curto)
    assert "[ OK ]" not in saida, saida
    assert "nenhum controlador USB" in saida
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}


def test_o_fix_que_grava_diz_ok(tmp_path: Path) -> None:
    """O lado de cá da régua: com o gancho no disco, o OK de sempre."""
    sysfs, ucm = _mesa(tmp_path)
    saida = _fix_ucm(tmp_path, ucm, sysfs)
    assert "[ OK ] perfil UCM do DualSense conferido" in saida, saida
    assert len(_ganchos(ucm)) > 1


def test_o_fix_que_falha_e_aviso_com_o_motivo(tmp_path: Path) -> None:
    """O `install -D` que não consegue gravar: aviso com o código, não OK mudo."""
    sysfs, ucm = _mesa(tmp_path)
    (ucm / "USB-Audio").write_text("um arquivo onde devia haver pasta\n", encoding="utf-8")
    saida = _fix_ucm(tmp_path, ucm, sysfs)
    assert "[ OK ]" not in saida, saida
    assert "[WARN] install_ucm_dualsense.sh falhou (código" in saida


def test_o_fix_sem_o_roteiro_fica_calado(tmp_path: Path) -> None:
    """Pacote que leva o doctor sem o roteiro não pode virar "falhou" mudo.

    O `ROOT_DIR` é `readonly` e nasce do lugar do próprio doctor: a cópia
    solitária numa pasta `scripts/` sem o irmão é o layout desse pacote.
    """
    sysfs, ucm = _mesa(tmp_path)
    sozinho = tmp_path / "pacote" / "scripts" / "doctor.sh"
    sozinho.parent.mkdir(parents=True)
    shutil.copy2(DOCTOR, sozinho)
    saida = _fix_ucm(tmp_path, ucm, sysfs, doctor=sozinho)
    assert saida == ""
    assert _ganchos(ucm) == {"Alheio de outra placa.conf"}


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


def _nome_no_censo(familia: str) -> str:
    """O nome do pacote pela boca do DONO, o `_pkg_nome` do install.sh."""
    proc = _roda(f"_pkg_nome alsa-ucm {familia}")
    nome = proc.stdout.strip()
    assert nome, (familia, proc.stderr)
    return nome


def _campo_debian(nome: str) -> str:
    """Um campo do `debian/control` com as linhas de continuação juntadas."""
    texto = (RAIZ / "packaging" / "debian" / "control").read_text(encoding="utf-8")
    m = re.search(rf"^{nome}:(.*(?:\n[ \t].*)*)", texto, re.MULTILINE)
    assert m is not None, f"o campo {nome} sumiu do debian/control"
    return " ".join(m.group(1).split())


def test_os_pacotes_declaram_o_ucm_do_sistema_com_o_nome_do_censo() -> None:
    """O censo só roda no fluxo nativo: o `.deb`, o `.rpm` e o `PKGBUILD` não
    passavam por ele e não declaravam o UCM. O nome vem do `_pkg_nome`, e não
    digitado aqui — se a tabela mudar, os pacotes têm de mudar junto.

    A MORDIDA: tire o `alsa-ucm-conf` do `Recommends:` do `debian/control` (ou
    o `Recommends: alsa-ucm` do `.spec`, ou a linha do `optdepends` do
    `PKGBUILD`) e esta régua reprova, nomeando o formato.
    """
    faltam = []
    apt = _nome_no_censo("apt")
    recomendados = [p.strip() for p in _campo_debian("Recommends").split(",")]
    if not any(apt in (alt.strip() for alt in r.split("|")) for r in recomendados):
        faltam.append(f"packaging/debian/control (Recommends: {apt})")
    spec = (RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec").read_text(
        encoding="utf-8"
    )
    dnf = _nome_no_censo("dnf")
    if not re.search(rf"^Recommends:\s+{re.escape(dnf)}\s*$", spec, re.MULTILINE):
        faltam.append(f"packaging/fedora/hefesto-dualsense4unix.spec (Recommends: {dnf})")
    pkgbuild = (RAIZ / "packaging" / "arch" / "PKGBUILD").read_text(encoding="utf-8")
    pacman = _nome_no_censo("pacman")
    if not re.search(rf"^\s*'{re.escape(pacman)}:", pkgbuild, re.MULTILINE):
        faltam.append(f"packaging/arch/PKGBUILD (optdepends: {pacman})")
    assert not faltam, "o UCM do sistema não declarado em: " + "; ".join(faltam)


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
