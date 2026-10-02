"""O portão reprova artefato de sistema que nenhum caminho de instalação alcança."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"

CABECALHO = "== artefato de sistema sem dono"

ARTEFATO = "assets/systemd/hefesto-artefato-de-mentira.service"


def _semeia_simbolico(raiz: Path) -> None:
    """O par de simbólicos que a seção do applet exige (APPLET-MONOCROMÁTICO-01)."""
    desenho = '<svg viewBox="0 0 16 16"><title>fake</title></svg>\n'
    alvos = (
        raiz / "assets" / "simbolico" / "hefesto-dualsense4unix-symbolic.svg",
        raiz
        / "packaging"
        / "cosmic-applet"
        / "data"
        / "icons"
        / "hicolor"
        / "symbolic"
        / "apps"
        / "com.vitoriamaria.HefestoDualsense4Unix-symbolic.svg",
    )
    for alvo in alvos:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(desenho, encoding="utf-8")


@pytest.fixture
def repo_com_artefato(tmp_path: Path) -> Path:
    """Repo fake mínimo: o script, um `install.sh` e UM artefato de sistema."""
    repo_root = Path(__file__).resolve().parents[2]
    src_script = repo_root / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    (tmp_path / "assets" / "systemd").mkdir(parents=True)
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / ARTEFATO).write_text(
        "[Unit]\nDescription=artefato de mentira\n", encoding="utf-8"
    )
    (tmp_path / "install.sh").write_text("# instalador de mentira\n", encoding="utf-8")
    (tmp_path / "uninstall.sh").write_text("# removedor de mentira\n", encoding="utf-8")
    _semeia_simbolico(tmp_path)
    return tmp_path


def roda(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def secao(saida: str) -> str:
    """Recorta só o pedaço desta seção — o resto da saída não é assunto daqui."""
    partes = saida.split(CABECALHO, 1)
    assert len(partes) == 2, f"seção ausente na saída do script:\n{saida}"
    return partes[1].split("─", 1)[0]


def test_artefato_sem_nenhum_dono_reprova_nomeando_o_arquivo(
    repo_com_artefato: Path,
) -> None:
    """A MORDIDA: unit versionada que instalador nenhum alcança derruba o portão."""
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert f"[FAIL] {ARTEFATO}" in corpo, corpo
    assert "ESCREVA a instalação dele" in corpo, corpo
    assert "_ARTEFATO_SEM_DONO_HOJE" in corpo, corpo


def test_dono_pelo_nome_no_install_passa(repo_com_artefato: Path) -> None:
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "[ OK ] artefatos de sistema: 1 com dono" in secao(resultado.stdout)


def test_dono_pelo_diretorio_copiado_inteiro_passa(repo_com_artefato: Path) -> None:
    """Um `cp -r assets/systemd` serve todo arquivo de lá — e tem de contar."""
    (repo_com_artefato / "install.sh").write_text(
        'cp -r "${ROOT_DIR}/assets/systemd" "${STAGING}/etc/systemd/system/"\n',
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_dono_por_glob_do_diretorio_passa(repo_com_artefato: Path) -> None:
    """Idem para o laço por glob — o molde do `assets/[0-9][0-9]-*.rules`."""
    (repo_com_artefato / "install.sh").write_text(
        'for u in "${ROOT_DIR}/assets/systemd/"*.service; do\n'
        '    sudo install -Dm644 "${u}" "/etc/systemd/system/$(basename "${u}")"\n'
        "done\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_diretorio_citado_com_o_nome_vindo_de_variavel_nao_conta(
    repo_com_artefato: Path,
) -> None:
    """O VÁCUO que esta seção não pode ter, e que o primeiro desenho tinha."""
    (repo_com_artefato / "install.sh").write_text(
        "for u in hefesto-outra.service hefesto-terceira.service; do\n"
        '    sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${u}" \\\n'
        '        "/etc/systemd/system/${u}"\n'
        "done\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_citacao_so_em_comentario_nao_conta(repo_com_artefato: Path) -> None:
    """Só linha de CÓDIGO conta — a armadilha do `grep -qF FastConnectable`."""
    (repo_com_artefato / "install.sh").write_text(
        "# instala assets/systemd/hefesto-artefato-de-mentira.service\n"
        "# (o passo foi arrancado numa refatoração e este comentário sobrou)\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_dono_por_helper_de_scripts_que_o_install_chama_passa(
    repo_com_artefato: Path,
) -> None:
    """Caminho 3: quem instala é o helper, e o install só o chama.

    Caso real de `assets/wireplumber/5{1,2,3}-*.conf`, instalados por
    `scripts/fix_wireplumber_default_source.sh` (install.sh:1139 e :1143).
    """
    (repo_com_artefato / "scripts" / "instala_unit.sh").write_text(
        'sudo install -Dm644 "assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "install.sh").write_text(
        'bash "${ROOT_DIR}/scripts/instala_unit.sh"\n', encoding="utf-8"
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout


def test_helper_que_o_install_nao_chama_nao_conta(repo_com_artefato: Path) -> None:
    """Helper existente e nunca chamado não instala nada — é o mesmo defeito."""
    (repo_com_artefato / "scripts" / "instala_unit.sh").write_text(
        'sudo install -Dm644 "assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    assert f"[FAIL] {ARTEFATO}" in secao(resultado.stdout)


def test_arte_nao_e_artefato_de_sistema(repo_com_artefato: Path) -> None:
    """Um PNG/SVG solto não é cobrado aqui — o portão de ícones já o cobra."""
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "assets" / "sem-dono-nenhum.png").write_bytes(b"\x89PNG\r\n")
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "sem-dono-nenhum.png" not in resultado.stdout


def test_regra_udev_e_delegada_ao_laco_que_ja_existia(
    repo_com_artefato: Path,
) -> None:
    """Sem contar duas vezes: `.rules` e modprobe ficam com os laços genéricos."""
    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    (repo_com_artefato / "assets" / "89-orfa-de-mentira.rules").write_text(
        'ACTION=="add", SUBSYSTEM=="hidraw", MODE="0660"\n', encoding="utf-8"
    )
    resultado = roda(repo_com_artefato)
    corpo = secao(resultado.stdout)
    assert "89-orfa-de-mentira.rules" not in corpo, corpo
    assert "+1 nos laços de udev/modprobe acima" in corpo, corpo


def test_lacuna_declarada_cala_o_portao_e_nao_envelhece_calada(
    repo_com_artefato: Path,
) -> None:
    """Declarar é honesto — e a lápide reprova no dia em que a dívida é paga."""
    script = repo_com_artefato / SCRIPT_REL_PATH
    texto = script.read_text(encoding="utf-8")
    assert "_ARTEFATO_SEM_DONO_HOJE=()" in texto, "a lista mudou de forma"
    script.write_text(
        texto.replace(
            "_ARTEFATO_SEM_DONO_HOJE=()",
            f'_ARTEFATO_SEM_DONO_HOJE=(\n    "{ARTEFATO}:razão de mentira, 12/08/2026"\n)',
        ),
        encoding="utf-8",
    )

    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    assert "1 lacuna(s) declarada(s)" in secao(resultado.stdout)

    (repo_com_artefato / "install.sh").write_text(
        'sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-artefato-de-mentira.service" \\\n'
        "    /etc/systemd/system/hefesto-artefato-de-mentira.service\n",
        encoding="utf-8",
    )
    resultado = roda(repo_com_artefato)
    assert resultado.returncode != 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert "lacuna declarada que já não vale" in corpo, corpo
    assert "ganhou dono" in corpo, corpo


def test_checkout_sem_install_fica_silencioso(repo_com_artefato: Path) -> None:
    """Sem instalador não há quem julgar — a seção cala, e não acusa."""
    (repo_com_artefato / "install.sh").unlink()
    resultado = roda(repo_com_artefato)
    assert resultado.returncode == 0, resultado.stdout
    corpo = secao(resultado.stdout)
    assert "[FAIL]" not in corpo, corpo
    assert "sem install.sh neste checkout" in corpo, corpo


def test_no_repo_real_a_secao_esta_verde() -> None:
    """Na árvore de verdade, nenhum artefato de sistema está órfão."""
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / SCRIPT_REL_PATH).exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")
    resultado = subprocess.run(
        ["bash", SCRIPT_REL_PATH],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    corpo = secao(resultado.stdout)
    assert "[FAIL]" not in corpo, corpo
    assert "[ OK ] artefatos de sistema:" in corpo, corpo
