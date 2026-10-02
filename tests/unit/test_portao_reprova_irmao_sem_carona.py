"""O portão reprova script distribuído que chama irmão que ninguém distribuiu."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT_REL_PATH = "scripts/check_packaging_parity.sh"
DOCTOR_REL_PATH = "scripts/doctor.sh"

CABECALHO = "== irmão sem carona"

REPO_RAIZ = Path(__file__).resolve().parents[2]


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
def repo(tmp_path: Path) -> Path:
    """Repo fake mínimo: o portão, um `install.sh` vazio e a pasta `scripts/`."""
    src_script = REPO_RAIZ / SCRIPT_REL_PATH
    if not src_script.exists():
        pytest.skip(f"script {SCRIPT_REL_PATH} não encontrado no repo")

    (tmp_path / "scripts").mkdir()
    dst_script = tmp_path / SCRIPT_REL_PATH
    shutil.copy2(src_script, dst_script)
    dst_script.chmod(0o755)

    (tmp_path / "install.sh").write_text("# instalador de mentira\n", encoding="utf-8")
    (tmp_path / "uninstall.sh").write_text("# removedor de mentira\n", encoding="utf-8")
    _semeia_simbolico(tmp_path)
    return tmp_path


def escreve(repo: Path, rel: str, conteudo: str) -> None:
    alvo = repo / rel
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")


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


INSTALL_LITERAL = """#!/usr/bin/env bash
sudo install -Dm755 "${ROOT_DIR}/scripts/alfa.sh" /usr/local/lib/hefesto/alfa.sh
"""

INSTALL_LACO = """#!/usr/bin/env bash
for _s in alfa.sh; do
    sudo install -Dm755 "${ROOT_DIR}/scripts/${_s}" "/usr/local/lib/hefesto/${_s}"
done
"""

ALFA_CHAMA_BETA = """#!/usr/bin/env bash
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "${ROOT_DIR}/scripts/beta.sh" --apply
"""

BETA = "#!/usr/bin/env bash\nprintf 'beta\\n'\n"


class TestAMordidaDaSecao:
    """A falta reprova, e reprova NOMEANDO os dois lados."""

    def test_irmao_chamado_e_nao_copiado_derruba_o_portao(self, repo: Path) -> None:
        """A MORDIDA: era exatamente isto que passava batido no `doctor.sh`."""
        escreve(repo, "install.sh", INSTALL_LITERAL)
        escreve(repo, "scripts/alfa.sh", ALFA_CHAMA_BETA)
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode != 0, f"o portão passou com irmão sem carona:\n{r.stdout}"
        trecho = secao(r.stdout)
        assert "[FAIL]" in trecho, trecho
        assert "alfa.sh" in trecho and "beta.sh" in trecho, (
            "o [FAIL] tem de nomear quem chama E quem ficou para trás — sem os "
            f"dois nomes ninguém acha o defeito:\n{trecho}"
        )

    def test_o_laco_com_variavel_nao_cega_a_secao(self, repo: Path) -> None:
        """A forma que a árvore usa de verdade tem de ser vista igual."""
        escreve(repo, "install.sh", INSTALL_LACO)
        escreve(repo, "scripts/alfa.sh", ALFA_CHAMA_BETA)
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode != 0, f"o laço com variável passou batido:\n{r.stdout}"
        assert "alfa.sh" in secao(r.stdout)


class TestOsTresJeitosDeEstarCerto:
    """Carona, guarda e recado: qualquer UM basta, e nenhum pode ser acusado."""

    def test_irmao_copiado_pelo_mesmo_instalador_passa(self, repo: Path) -> None:
        escreve(
            repo,
            "install.sh",
            INSTALL_LITERAL
            + 'sudo install -Dm755 "${ROOT_DIR}/scripts/beta.sh" /usr/local/lib/hefesto/beta.sh\n',
        )
        escreve(repo, "scripts/alfa.sh", ALFA_CHAMA_BETA)
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode == 0, f"o portão acusou quem levou o irmão:\n{r.stdout}"
        assert "[FAIL]" not in secao(r.stdout)

    def test_guarda_de_existencia_com_o_nome_literal_passa(self, repo: Path) -> None:
        """O idioma que a casa já usava antes desta seção existir."""
        escreve(repo, "install.sh", INSTALL_LITERAL)
        escreve(
            repo,
            "scripts/alfa.sh",
            "#!/usr/bin/env bash\n"
            'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
            'if [[ -x "${ROOT_DIR}/scripts/beta.sh" ]]; then\n'
            '    bash "${ROOT_DIR}/scripts/beta.sh" --apply\n'
            "fi\n",
        )
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode == 0, f"o portão acusou quem escreveu a guarda:\n{r.stdout}"

    def test_recado_que_ensina_a_rodar_o_irmao_nao_e_chamada(self, repo: Path) -> None:
        """MEDIDO: sem este descarte, o portão acusava seis falsos só no doctor."""
        escreve(repo, "install.sh", INSTALL_LITERAL)
        escreve(
            repo,
            "scripts/alfa.sh",
            "#!/usr/bin/env bash\n"
            "warn() { printf '%s\\n' \"$*\"; }\n"
            'warn "sem cura automática — rode: sudo bash scripts/beta.sh"\n',
        )
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode == 0, f"o portão confundiu recado com chamada:\n{r.stdout}"

    def test_script_que_ninguem_distribui_nao_e_cobrado(self, repo: Path) -> None:
        """A âncora é a CHAMADA de quem foi copiado, não o arquivo em `scripts/`."""
        escreve(repo, "install.sh", "# instalador que não copia script nenhum\n")
        escreve(repo, "scripts/alfa.sh", ALFA_CHAMA_BETA)
        escreve(repo, "scripts/beta.sh", BETA)

        r = roda(repo)

        assert r.returncode == 0, f"o portão cobrou script de bancada:\n{r.stdout}"

    def test_nome_que_nao_existe_em_scripts_nao_e_irmao(self, repo: Path) -> None:
        """Comando de terceiro não é parentesco — cobrá-lo seria inventar defeito."""
        escreve(repo, "install.sh", INSTALL_LITERAL)
        escreve(
            repo,
            "scripts/alfa.sh",
            "#!/usr/bin/env bash\nbash /usr/lib/outro-projeto/coisa.sh\n",
        )

        r = roda(repo)

        assert r.returncode == 0, f"o portão inventou um irmão:\n{r.stdout}"


class TestOModuloPythonViajaComQuemOImporta:
    """A cláusula que guarda a decisão sobre `identidade_do_vpad.py`."""

    def test_import_de_modulo_irmao_e_cobrado_quando_o_script_e_distribuido(
        self, repo: Path
    ) -> None:
        """No dia em que um ensaio for distribuído, a régua tem de ir junto."""
        escreve(
            repo,
            "install.sh",
            '#!/usr/bin/env bash\nsudo install -Dm755 "${ROOT_DIR}/scripts/ensaio.py"'
            " /usr/local/lib/hefesto/ensaio.py\n",
        )
        escreve(
            repo,
            "scripts/ensaio.py",
            "#!/usr/bin/env python3\nimport sys\nimport regua\n\nprint(regua, sys)\n",
        )
        escreve(repo, "scripts/regua.py", "#!/usr/bin/env python3\nVALOR = 1\n")

        r = roda(repo)

        assert r.returncode != 0, f"o módulo irmão passou sem carona:\n{r.stdout}"
        trecho = secao(r.stdout)
        assert "ensaio.py" in trecho and "regua.py" in trecho, trecho

    def test_modulo_copiado_junto_passa(self, repo: Path) -> None:
        escreve(
            repo,
            "install.sh",
            '#!/usr/bin/env bash\nsudo install -Dm755 "${ROOT_DIR}/scripts/ensaio.py"'
            " /usr/local/lib/hefesto/ensaio.py\n"
            'sudo install -Dm755 "${ROOT_DIR}/scripts/regua.py" /usr/local/lib/hefesto/regua.py\n',
        )
        escreve(
            repo,
            "scripts/ensaio.py",
            "#!/usr/bin/env python3\nimport regua\n\nprint(regua)\n",
        )
        escreve(repo, "scripts/regua.py", "#!/usr/bin/env python3\nVALOR = 1\n")

        r = roda(repo)

        assert r.returncode == 0, f"o portão acusou quem levou o módulo:\n{r.stdout}"


class TestACuraNoDoctorRodaNoLayoutDoPacote:
    """A cura por EXECUÇÃO: quem reaplica udev é quem EXISTE neste layout."""

    @staticmethod
    def _layout(tmp_path: Path, *scripts: str) -> Path:
        """Um checkout de mentira com o doctor e só os scripts pedidos."""
        doctor = REPO_RAIZ / DOCTOR_REL_PATH
        if not doctor.exists():
            pytest.skip(f"script {DOCTOR_REL_PATH} não encontrado no repo")
        (tmp_path / "scripts").mkdir(exist_ok=True)
        shutil.copy2(doctor, tmp_path / DOCTOR_REL_PATH)
        for nome in scripts:
            (tmp_path / "scripts" / nome).write_text(
                "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
            )
        return tmp_path

    @staticmethod
    def _escolhido(raiz: Path) -> subprocess.CompletedProcess[str]:
        """Carrega o doctor SEM rodar o diagnóstico e pergunta quem ele escolheu."""
        return subprocess.run(
            [
                "bash",
                "-c",
                f'source "{raiz / DOCTOR_REL_PATH}" >/dev/null 2>&1; '
                "declare -F _dono_das_regras_udev >/dev/null || { printf 'AUSENTE'; exit 0; }; "
                "_dono_das_regras_udev || printf 'NENHUM'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_no_layout_do_pacote_escolhe_o_install_host_udev(
        self, tmp_path: Path
    ) -> None:
        """A MORDIDA da cura: é o .deb, e o `install_udev.sh` não está lá."""
        raiz = self._layout(tmp_path, "install-host-udev.sh")

        r = self._escolhido(raiz)

        assert r.stdout.strip().endswith("install-host-udev.sh"), (
            "no layout do .deb o doctor tem de cair no irmão que o pacote leva; "
            f"escolheu: {r.stdout.strip()!r}"
        )

    def test_no_checkout_escolhe_o_dono_nativo(self, tmp_path: Path) -> None:
        """Com os dois no disco, ganha o dono nativo do conjunto canônico."""
        raiz = self._layout(tmp_path, "install_udev.sh", "install-host-udev.sh")

        r = self._escolhido(raiz)

        assert r.stdout.strip().endswith("scripts/install_udev.sh"), r.stdout.strip()

    def test_sem_nenhum_dos_dois_nao_finge_que_aplicou(self, tmp_path: Path) -> None:
        """Ausência dos dois é recusa explícita, não escolha de um caminho morto."""
        raiz = self._layout(tmp_path)

        r = self._escolhido(raiz)

        assert r.stdout.strip() == "NENHUM", r.stdout.strip()
