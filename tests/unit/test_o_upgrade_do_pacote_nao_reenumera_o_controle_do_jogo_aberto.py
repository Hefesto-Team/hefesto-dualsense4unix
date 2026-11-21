"""O upgrade do pacote não reenumera o controle do jogo aberto.

O-UPGRADE-DO-PACOTE-NAO-REENUMERA-O-CONTROLE-DO-JOGO-ABERTO-01: o `udevadm trigger` sem filtro do
`.install` do Arch, do `%post` do Fedora, o de usb do `postinst` do .deb e os do ajudante de host
reenumeravam o controle no meio do jogo. O disparo tem um dono, `scripts/disparo_do_udev.sh`, que
pergunta ao `quem_o_jogo_le.py` e, com jogo, só dispara o que não reenumera o controle.

A MORDIDA: devolva um `udevadm trigger` cru ao `post_install` do `.install`, tire o ramo do jogo
do dono ou deixe o pacote sem o `quem_o_jogo_le.py` ao lado do dono, e a régua reprova.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import quem_o_jogo_le

RAIZ = Path(__file__).resolve().parents[2]
DONO = RAIZ / "scripts" / "disparo_do_udev.sh"
LEITOR = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "quem_o_jogo_le.py"

INSTALL_DO_ARCH = RAIZ / "packaging/arch/hefesto-dualsense4unix.install"
PKGBUILD = RAIZ / "packaging/arch/PKGBUILD"
SPEC = RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec"
POSTINST = RAIZ / "packaging/debian/postinst"
POSTRM = RAIZ / "packaging/debian/postrm"
PRERM = RAIZ / "packaging/debian/prerm"
BUILD_DEB = RAIZ / "scripts/build_deb.sh"
FLATPAK = RAIZ / "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
AJUDANTE = RAIZ / "scripts/install-host-udev.sh"
NATIVO = RAIZ / "scripts/install_udev.sh"

QUE_REENUMERAM = ("hidraw", "idVendor=054c", "subsystem-match=usb", "subsystem-match=input")
QUE_NAO_REENUMERAM = ("subsystem-match=leds", "subsystem-match=misc", "subsystem-match=pci")


def _linhas_de_codigo(texto: str) -> list[str]:
    texto = texto.split("\n%changelog\n")[0]
    return [ln.strip() for ln in texto.splitlines() if not ln.strip().startswith("#")]


@pytest.mark.parametrize(
    "arquivo",
    [INSTALL_DO_ARCH, SPEC, POSTINST, POSTRM, PRERM, AJUDANTE, NATIVO, BUILD_DEB, FLATPAK],
    ids=lambda p: p.name,
)
def test_nenhum_scriptlet_dispara_o_udev_fora_do_dono(arquivo: Path) -> None:
    """MORDIDA: devolva `udevadm trigger` ao `post_install` do `.install`, e esta régua reprova."""
    codigo = _linhas_de_codigo(arquivo.read_text(encoding="utf-8"))
    culpadas = [ln for ln in codigo if "udevadm trigger" in ln]
    assert not culpadas, f"{arquivo.name} dispara o udev por conta própria: {culpadas}"


GESTO_QUE_INSTALA = {
    INSTALL_DO_ARCH: ("post_install() {", "\n}\n"),
    SPEC: ("\n%post\n", "\n%preun\n"),
    AJUDANTE: ("_build_install_cmd() {", "\n}\n"),
}


@pytest.mark.parametrize(
    "arquivo", [INSTALL_DO_ARCH, SPEC, POSTINST, AJUDANTE, NATIVO], ids=lambda p: p.name
)
def test_quem_instala_chama_o_dono(arquivo: Path) -> None:
    """MORDIDA: apague a chamada do dono do `post_install`, do `%post` ou do ajudante."""
    texto = arquivo.read_text(encoding="utf-8")
    if arquivo in GESTO_QUE_INSTALA:
        inicio, fim = GESTO_QUE_INSTALA[arquivo]
        texto = texto.split(inicio, 1)[1].split(fim, 1)[0]
    codigo = "\n".join(_linhas_de_codigo(texto))
    assert "disparo_do_udev.sh" in codigo or "${DISPARO_SH}" in codigo


@pytest.mark.parametrize(
    "arquivo", [PKGBUILD, SPEC, BUILD_DEB, FLATPAK], ids=lambda p: p.name
)
def test_todo_pacote_leva_o_dono_e_o_leitor_lado_a_lado(arquivo: Path) -> None:
    """O dono acha o `quem_o_jogo_le.py` ao lado de si: os dois vão na mesma pasta do pacote."""
    codigo = "\n".join(_linhas_de_codigo(arquivo.read_text(encoding="utf-8")))
    for nome in ("scripts/disparo_do_udev.sh", "integrations/quem_o_jogo_le.py"):
        assert nome in codigo, f"{arquivo.name} não leva {nome}"


def test_o_spec_lista_os_dois_arquivos_do_dono_nos_files() -> None:
    files = SPEC.read_text(encoding="utf-8").split("\n%files\n")[1]
    assert "%{_datadir}/%{app_id}/scripts/disparo_do_udev.sh" in files
    assert "%{_datadir}/%{app_id}/scripts/quem_o_jogo_le.py" in files


def _udevadm_de_mentira(raiz: Path) -> tuple[dict[str, str], Path]:
    bin_ = raiz / "bin"
    bin_.mkdir(parents=True, exist_ok=True)
    diario = raiz / "udevadm.txt"
    falso = bin_ / "udevadm"
    falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{diario}"\n', encoding="utf-8")
    falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
    ambiente = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}
    return ambiente, diario


def _proc(raiz: Path, *, jogo: bool) -> Path:
    proc = raiz / ("proc-com-jogo" if jogo else "proc-sem-jogo")
    (proc / "42").mkdir(parents=True)
    ambiente = b"HOME=/x\0"
    if jogo:
        ambiente += quem_o_jogo_le.ENV_DO_JOGO.encode() + b"=/compat/1234\0"
    (proc / "42" / "environ").write_bytes(ambiente)
    (proc / "self").mkdir()
    return proc


def _dispara(dono: Path, raiz: Path, proc: Path) -> tuple[list[str], str]:
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RAIZ_PROC"] = str(proc)
    saida = subprocess.run(
        ["bash", str(dono)], env=ambiente, capture_output=True, text=True, check=False
    )
    assert saida.returncode == 0, saida.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return chamadas, saida.stdout


def _alguma_casa(chamadas: list[str], alvos: tuple[str, ...]) -> bool:
    return any(alvo in c for c in chamadas for alvo in alvos)


def test_com_jogo_aberto_so_dispara_o_que_nao_reenumera_o_controle(tmp_path: Path) -> None:
    """MORDIDA: tire o ramo do jogo do dono e o hidraw, o usb e o input voltam a disparar."""
    chamadas, saida = _dispara(DONO, tmp_path, _proc(tmp_path, jogo=True))
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert all(c != "trigger" for c in chamadas)
    for alvo in QUE_NAO_REENUMERAM:
        assert any(alvo in c for c in chamadas), alvo
    assert "próximo plugue" in saida


def test_sem_jogo_dispara_o_que_o_instalador_disparava(tmp_path: Path) -> None:
    chamadas, saida = _dispara(DONO, tmp_path, _proc(tmp_path, jogo=False))
    for alvo in (*QUE_REENUMERAM, *QUE_NAO_REENUMERAM):
        assert any(alvo in c for c in chamadas), alvo
    assert "trigger" in chamadas
    assert "próximo plugue" not in saida


def _pasta_do_pacote(raiz: Path, *, com_leitor: bool) -> Path:
    pasta = raiz / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    pasta.mkdir(parents=True)
    shutil.copy2(DONO, pasta / DONO.name)
    if com_leitor:
        shutil.copy2(LEITOR, pasta / LEITOR.name)
    return pasta / DONO.name


@pytest.mark.parametrize("jogo", [True, False], ids=["com-jogo", "sem-jogo"])
def test_o_dono_instalado_acha_o_leitor_ao_lado(tmp_path: Path, jogo: bool) -> None:
    """MORDIDA: tire a pasta do próprio dono da busca do leitor e o upgrade sem jogo não dispara."""
    dono = _pasta_do_pacote(tmp_path, com_leitor=True)
    chamadas, saida = _dispara(dono, tmp_path, _proc(tmp_path, jogo=jogo))
    assert _alguma_casa(chamadas, QUE_REENUMERAM) == (not jogo)
    assert "não deu para saber" not in saida


def test_sem_o_leitor_o_dono_nao_reenumera_e_diz_que_nao_soube(tmp_path: Path) -> None:
    """MORDIDA: deixe o pacote sem o `quem_o_jogo_le.py` e o upgrade reenumera às cegas."""
    dono = _pasta_do_pacote(tmp_path, com_leitor=False)
    chamadas, saida = _dispara(dono, tmp_path, _proc(tmp_path, jogo=False))
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert "não deu para saber" in saida


def _corpo(arquivo: Path, inicio: str, fim: str) -> str:
    texto = arquivo.read_text(encoding="utf-8").split(inicio, 1)[1].split(fim, 1)[0]
    return "\n".join(_linhas_de_codigo(texto))


@pytest.mark.parametrize(
    ("arquivo", "pre", "pos"),
    [
        (INSTALL_DO_ARCH, ("pre_remove() {", "\n}\n"), ("post_remove() {", "\n}\n")),
        (SPEC, ("\n%preun\n", "\n%postun\n"), ("\n%postun\n", "\n%files\n")),
    ],
    ids=["arch", "fedora"],
)
def test_a_remocao_decide_antes_dos_arquivos_sairem_e_dispara_depois(
    arquivo: Path, pre: tuple[str, str], pos: tuple[str, str]
) -> None:
    """MORDIDA: tire a decisão do `pre_remove`/`%preun` e o gancho seguinte dispara sem veredito."""
    assert "disparo_do_udev.sh --preparar-a-remocao" in _corpo(arquivo, *pre)
    assert 'disparo_do_udev.sh" --apos-a-remocao' in _corpo(arquivo, *pos)
    assert "udevadm trigger" not in _corpo(arquivo, *pos)


def test_o_spec_so_decide_na_remocao_final_e_nao_no_upgrade() -> None:
    corpo = _corpo(SPEC, "\n%preun\n", "\n%postun\n")
    primeiras = corpo.splitlines()[:2]
    assert primeiras[0] == "if [ $1 -eq 0 ]; then"
    assert "--preparar-a-remocao" in primeiras[1]


def _a_remocao(
    raiz: Path,
    *,
    jogo: bool,
    com_leitor: bool = True,
    antes: bool = True,
    perde_o_veredito: bool = False,
) -> tuple[list[str], str]:
    pacote = raiz / "usr" / "share" / "hefesto-dualsense4unix" / "scripts"
    pacote.mkdir(parents=True)
    shutil.copy2(DONO, pacote / DONO.name)
    if com_leitor:
        shutil.copy2(LEITOR, pacote / LEITOR.name)
    run = raiz / "run" / "hefesto-dualsense4unix-remocao"
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RAIZ_PROC"] = str(_proc(raiz, jogo=jogo))
    ambiente["HEFESTO_RUN_DA_REMOCAO"] = str(run)
    if antes:
        feito = subprocess.run(
            ["bash", str(pacote / DONO.name), "--preparar-a-remocao"],
            env=ambiente, capture_output=True, text=True, check=False,
        )
        assert feito.returncode == 0, feito.stderr
        assert not diario.exists(), "decidir não dispara nada"
    if perde_o_veredito:
        (run / "veredito").unlink()
    shutil.rmtree(pacote.parent.parent.parent)
    assert not pacote.exists()
    saida = ""
    if (run / DONO.name).exists():
        feito = subprocess.run(
            ["bash", str(run / DONO.name), "--apos-a-remocao"],
            env=ambiente, capture_output=True, text=True, check=False,
        )
        assert feito.returncode == 0, feito.stderr
        saida = feito.stdout
        assert not run.exists(), "o veredito e a cópia não ficam no /run"
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return chamadas, saida


def test_remover_o_pacote_com_jogo_aberto_nao_reenumera_o_controle(tmp_path: Path) -> None:
    """MORDIDA: dispare o geral sem ler o veredito e o jogo perde o controle."""
    chamadas, saida = _a_remocao(tmp_path, jogo=True)
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert "trigger" not in chamadas
    assert "próximo plugue" in saida


def test_remover_o_pacote_sem_jogo_reenumera_como_antes(tmp_path: Path) -> None:
    chamadas, saida = _a_remocao(tmp_path, jogo=False)
    for alvo in QUE_REENUMERAM:
        assert any(alvo in c for c in chamadas), alvo
    assert "trigger" in chamadas
    assert "próximo plugue" not in saida


def test_remover_o_pacote_sem_o_leitor_nao_reenumera(tmp_path: Path) -> None:
    chamadas, saida = _a_remocao(tmp_path, jogo=False, com_leitor=False)
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert "trigger" not in chamadas
    assert "não deu para saber" in saida


def test_remover_o_pacote_sem_veredito_nao_dispara_nada(tmp_path: Path) -> None:
    """Sem a decisão do `pre_remove`, não há cópia do dono no /run e nada dispara."""
    chamadas, saida = _a_remocao(tmp_path, jogo=False, antes=False)
    assert chamadas == []
    assert saida == ""


def test_remover_o_pacote_com_o_veredito_perdido_nao_reenumera(tmp_path: Path) -> None:
    """MORDIDA: assuma «sem jogo» quando o veredito falta e o gancho reenumera às cegas."""
    chamadas, saida = _a_remocao(tmp_path, jogo=False, perde_o_veredito=True)
    assert not _alguma_casa(chamadas, QUE_REENUMERAM)
    assert "trigger" not in chamadas
    assert "não deu para saber" in saida


PASTA_DO_RUN = "/run/hefesto-dualsense4unix-remocao"
GANCHOS_DA_REMOCAO = {
    "arch": (INSTALL_DO_ARCH, "post_remove() {", "\n}\n", ["bash", "-c"]),
    "fedora": (SPEC, "\n%postun\n", "\n%files\n", ["sh", "-c"]),
}


def _stat_que_ve_o_root(raiz: Path) -> Path:
    """Um `stat` que mostra o dono deste usuário como root: o gancho roda como root."""
    bin_ = raiz / "bin-root"
    bin_.mkdir(parents=True, exist_ok=True)
    real = shutil.which("stat")
    assert real
    falso = bin_ / "stat"
    falso.write_text(
        f'#!/bin/sh\nsaida=$("{real}" "$@") || exit $?\n'
        f'printf "%s\\n" "$saida" | sed "s/^{os.getuid()} /0 /"\n',
        encoding="utf-8",
    )
    falso.chmod(0o755)
    return bin_


def _gancho_da_remocao(
    raiz: Path, formato: str, run: Path, *, como_root: bool
) -> tuple[list[str], bool]:
    """Roda o `post_remove`/`%postun` de verdade, com o /run e o udevadm de mentira."""
    arquivo, inicio, fim, interprete = GANCHOS_DA_REMOCAO[formato]
    corpo = arquivo.read_text(encoding="utf-8").split(inicio, 1)[1].split(fim, 1)[0]
    corpo = corpo.replace("%%", "%").replace(PASTA_DO_RUN, str(run))
    corpo = corpo.replace("/usr/sbin/udevadm", "udevadm")
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RUN_DA_REMOCAO"] = str(run)
    if como_root:
        ambiente["PATH"] = f"{_stat_que_ve_o_root(raiz)}:{ambiente['PATH']}"
    feito = subprocess.run(
        [*interprete, corpo, "gancho", "0"], env=ambiente, capture_output=True, text=True,
        check=False, timeout=60,
    )
    assert feito.returncode == 0, feito.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return [c for c in chamadas if not c.startswith("control")], (raiz / "executou").exists()


def _preparar(raiz: Path, run: Path, *, jogo: bool) -> None:
    pacote = raiz / "pacote"
    pacote.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DONO, pacote / DONO.name)
    shutil.copy2(LEITOR, pacote / LEITOR.name)
    ambiente, diario = _udevadm_de_mentira(raiz)
    ambiente["HEFESTO_RAIZ_PROC"] = str(_proc(raiz, jogo=jogo))
    ambiente["HEFESTO_RUN_DA_REMOCAO"] = str(run)
    feito = subprocess.run(
        ["bash", str(pacote / DONO.name), "--preparar-a-remocao"],
        env=ambiente, capture_output=True, text=True, check=False, timeout=60,
    )
    assert feito.returncode == 0, feito.stderr
    assert not diario.exists()


def _copia_alheia(pasta: Path, raiz: Path) -> Path:
    copia = pasta / DONO.name
    copia.write_text(f'#!/bin/sh\ntouch "{raiz}/executou"\n', encoding="utf-8")
    copia.chmod(0o700)
    return copia


@pytest.mark.parametrize("formato", list(GANCHOS_DA_REMOCAO))
@pytest.mark.parametrize("jogo", [True, False], ids=["com-jogo", "sem-jogo"])
def test_o_gancho_da_remocao_roda_a_copia_que_o_root_guardou(
    tmp_path: Path, formato: str, jogo: bool
) -> None:
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    _preparar(tmp_path, run, jogo=jogo)
    assert f"{run.stat().st_mode & 0o777:o}" == "700"
    assert f"{(run / DONO.name).stat().st_mode & 0o777:o}" == "700"
    chamadas, _ = _gancho_da_remocao(tmp_path, formato, run, como_root=True)
    assert _alguma_casa(chamadas, QUE_REENUMERAM) == (not jogo)
    assert not run.exists()


@pytest.mark.parametrize("formato", list(GANCHOS_DA_REMOCAO))
def test_o_gancho_recusa_a_pasta_que_nao_e_do_root(tmp_path: Path, formato: str) -> None:
    """MORDIDA: tire a conferência do dono do gancho e a pasta de outro usuário roda como root."""
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    run.mkdir(parents=True, mode=0o700)
    _copia_alheia(run, tmp_path)
    chamadas, executou = _gancho_da_remocao(tmp_path, formato, run, como_root=False)
    assert not executou
    assert chamadas == []


@pytest.mark.parametrize("formato", list(GANCHOS_DA_REMOCAO))
@pytest.mark.parametrize(
    ("modo_da_pasta", "modo_da_copia"),
    [(0o770, 0o700), (0o707, 0o700), (0o755, 0o700), (0o700, 0o720), (0o700, 0o702)],
    ids=["pasta-grupo", "pasta-outros", "pasta-legivel", "copia-grupo", "copia-outros"],
)
def test_o_gancho_recusa_escrita_de_grupo_ou_de_outros(
    tmp_path: Path, formato: str, modo_da_pasta: int, modo_da_copia: int
) -> None:
    """MORDIDA: tire a conferência do modo do gancho e a cópia que outro escreve roda como root."""
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    run.mkdir(parents=True)
    _copia_alheia(run, tmp_path).chmod(modo_da_copia)
    run.chmod(modo_da_pasta)
    chamadas, executou = _gancho_da_remocao(tmp_path, formato, run, como_root=True)
    assert not executou
    assert chamadas == []


@pytest.mark.parametrize("formato", list(GANCHOS_DA_REMOCAO))
@pytest.mark.parametrize("onde", ["pasta", "copia"])
def test_o_gancho_nao_segue_link(tmp_path: Path, formato: str, onde: str) -> None:
    """MORDIDA: o gancho que segue link roda a cópia que mora fora da pasta do root."""
    alheia = tmp_path / "alheia"
    alheia.mkdir(mode=0o700)
    alvo = _copia_alheia(alheia, tmp_path)
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    run.parent.mkdir(parents=True)
    if onde == "pasta":
        run.symlink_to(alheia)
    else:
        run.mkdir(mode=0o700)
        (run / DONO.name).symlink_to(alvo)
    chamadas, executou = _gancho_da_remocao(tmp_path, formato, run, como_root=True)
    assert not executou
    assert chamadas == []


def test_a_preparacao_nao_escreve_pelo_link_plantado(tmp_path: Path) -> None:
    """MORDIDA: crie a pasta com `mkdir -p` sem apagar o que estava e o veredito vai para o alvo."""
    alheia = tmp_path / "alheia"
    alheia.mkdir()
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    run.parent.mkdir(parents=True)
    run.symlink_to(alheia)
    _preparar(tmp_path, run, jogo=False)
    assert list(alheia.iterdir()) == []
    assert run.is_dir() and not run.is_symlink()
    assert f"{run.stat().st_mode & 0o777:o}" == "700"
    assert sorted(p.name for p in run.iterdir()) == [DONO.name, "veredito"]


def test_a_preparacao_troca_a_pasta_plantada_e_o_veredito_velho(tmp_path: Path) -> None:
    """MORDIDA: aproveite a pasta que já estava e a cópia alheia e o «sem jogo» velho ficam."""
    run = tmp_path / "run" / "hefesto-dualsense4unix-remocao"
    run.mkdir(parents=True, mode=0o777)
    run.chmod(0o777)
    (run / "veredito").write_text("10\n", encoding="utf-8")
    (run / "outro").write_text("x", encoding="utf-8")
    _preparar(tmp_path, run, jogo=True)
    assert f"{run.stat().st_mode & 0o777:o}" == "700"
    assert (run / "veredito").read_text(encoding="utf-8") == "0\n"
    assert not (run / "outro").exists()
    assert (run / DONO.name).read_bytes() == DONO.read_bytes()
