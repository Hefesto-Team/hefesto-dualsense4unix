"""BG-05 — o Python procura onde o pacote põe.

O `doctor` roda `scripts/doctor.sh` e mais três scripts do repo. Para achá-los
ele perguntava *"em que diretório esta instalação pôs o share do Hefesto?"* com
uma lista LOCAL de três layouts — checkout, `/usr/share` e `/usr/local/share`.
O Flatpak instala em `/app/share/…` e não estava na lista, então o `doctor`
dizia "não encontrado" dentro de uma sandbox onde o arquivo existe.

Pior: a mesma pergunta tinha uma SEGUNDA resposta no código
(`app/actions/daemon_actions.py:495`, `BASES_DE_INSTALACAO`), e as duas já
haviam divergido — a segunda ganhou `/app/share` na T-02(b) de 25/08/2026 e a
do `cmd_doctor` ficou para trás. É a correção pela metade, que esta casa proíbe.

As mordidas deste arquivo:

- um **Flatpak de mentira** (`sys.prefix` apontando para um `/app` de brinquedo)
  em que a busca ACHA o script — arranque `/app/share` ou a linha de
  `sys.prefix` de `bases_de_instalacao()` e ele reprova;
- a **guarda do outro lado**: um diretório onde o script não está devolve
  ``None``, nunca um caminho inventado — régua que só sabe achar não é régua;
- e o portão contra a REINCIDÊNCIA: `cmd_doctor.py` não pode voltar a carregar
  uma lista de bases própria.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.utils import repo_files

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]


def _plantar(base: Path, relpath: str) -> Path:
    """Cria um arquivo de mentira em `base/relpath` e devolve o caminho."""
    alvo = base / relpath
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    return alvo


class TestOFlatpakDeMentira:
    """A sandbox do Flatpak: `sys.prefix == /app`, os arquivos em `/app/share`."""

    # Um nome que NÃO existe no checkout, de propósito: se a régua usasse o
    # nome de um script real, a primeira base (a raiz do repo) responderia e o
    # teste passaria com a cura arrancada.
    SCRIPT = "scripts/so-existe-dentro-do-flatpak.sh"

    def test_acha_o_script_dentro_da_sandbox(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Com o wheel sob `/app`, a busca cai em `/app/share/hefesto-…`."""
        app = tmp_path / "app"
        esperado = _plantar(app / "share" / "hefesto-dualsense4unix", self.SCRIPT)
        monkeypatch.setattr(sys, "prefix", str(app))

        achado = repo_files.encontrar_arquivo_do_repo(self.SCRIPT)

        assert achado == esperado, (
            "a busca não alcançou o layout do Flatpak — o `doctor` diria 'não "
            "veio nesta instalação' sobre um arquivo que ESTÁ na sandbox.\n"
            f"bases consultadas: {[str(b) for b in repo_files.bases_de_instalacao()]}"
        )

    def test_o_doctor_sh_da_sandbox_tambem_e_achado(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """O caminho que o `doctor` realmente percorre, não só o helper.

        `_find_doctor_sh` é quem decide entre rodar o exame de verdade e cair
        no ramo "só os checks do daemon". Aqui a raiz do checkout é apagada da
        lista (num Flatpak ela não existe) para que a única resposta possível
        seja a da sandbox.
        """
        app = tmp_path / "app"
        esperado = _plantar(app / "share" / "hefesto-dualsense4unix", "scripts/doctor.sh")
        monkeypatch.setattr(sys, "prefix", str(app))
        de_verdade = repo_files.bases_de_instalacao
        monkeypatch.setattr(
            repo_files,
            "bases_de_instalacao",
            lambda: tuple(b for b in de_verdade() if b != RAIZ_DO_REPO),
        )

        assert cmd_doctor._find_doctor_sh() == esperado


class TestAGuardaDoOutroLado:
    """Régua que só sabe achar não é régua."""

    def test_devolve_none_quando_o_script_nao_esta_em_lugar_nenhum(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Nenhuma base tem o arquivo → ``None``, e não um caminho inventado."""
        vazio = tmp_path / "prefixo-vazio"
        vazio.mkdir()
        monkeypatch.setattr(sys, "prefix", str(vazio))

        achado = repo_files.encontrar_arquivo_do_repo(
            "scripts/este-script-nunca-existiu.sh"
        )

        assert achado is None, (
            f"inventou um caminho: {achado!r} — quem chama entregaria isso ao "
            "bash e receberia 'No such file or directory' em vez do aviso."
        )

    def test_nao_devolve_diretorio_como_se_fosse_script(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Um DIRETÓRIO com o nome procurado não conta como achado.

        `Path.exists()` diria que sim; a régua usa `is_file()` justamente por
        isso — `bash <um diretório>` falha com uma mensagem que não ajuda
        ninguém.
        """
        app = tmp_path / "app"
        (app / "share" / "hefesto-dualsense4unix" / "scripts" / "doctor.sh").mkdir(
            parents=True
        )
        monkeypatch.setattr(sys, "prefix", str(app))
        monkeypatch.setattr(
            repo_files,
            "bases_de_instalacao",
            lambda: (app / "share" / "hefesto-dualsense4unix",),
        )

        assert repo_files.encontrar_arquivo_do_repo("scripts/doctor.sh") is None


class TestAListaDeBases:
    """O que precisa estar na lista, e por quê."""

    def test_o_flatpak_esta_na_lista_por_extenso(self) -> None:
        """`/app/share` escrito à mão, para o caso de o wheel ter outro prefixo."""
        caminhos = [str(b) for b in repo_files.bases_de_instalacao()]

        assert "/app/share/hefesto-dualsense4unix" in caminhos

    def test_as_bases_de_sempre_continuam_la(self) -> None:
        caminhos = [str(b) for b in repo_files.bases_de_instalacao()]

        assert "/usr/share/hefesto-dualsense4unix" in caminhos
        assert "/usr/local/share/hefesto-dualsense4unix" in caminhos

    def test_a_primeira_base_e_a_raiz_do_checkout_e_nao_o_src(self) -> None:
        """BUG-GUI-REPO-ROOT-OFFBYONE-01 cobrava `parents` errado com no-op mudo."""
        primeira = repo_files.bases_de_instalacao()[0]

        assert (primeira / "src" / "hefesto_dualsense4unix").is_dir(), (
            f"a primeira base é {primeira} — tem de ser a RAIZ do checkout. "
            "Contar `parents` errado devolve `<repo>/src`, onde `scripts/` "
            "nunca existiu, e o botão vira no-op SILENCIOSO."
        )

    def test_o_prefixo_do_interpretador_entra(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AppImage, venv e Nix instalam em `sys.prefix/share/…`."""
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "bundle"))
        caminhos = [str(b) for b in repo_files.bases_de_instalacao()]

        assert str(tmp_path / "bundle" / "share" / "hefesto-dualsense4unix") in caminhos

    def test_o_share_do_usuario_entra(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """`install.sh:3239` instala `storm_watch.sh` em `XDG_DATA_HOME`."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "dados"))
        caminhos = [str(b) for b in repo_files.bases_de_instalacao()]

        assert str(tmp_path / "dados" / "hefesto-dualsense4unix") in caminhos

    def test_sem_base_repetida(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Com `sys.prefix == /usr` (o `.deb` no Python do sistema) as bases 2 e 5
        são o MESMO diretório; olhar duas vezes não acrescenta nada."""
        monkeypatch.setattr(sys, "prefix", "/usr")
        caminhos = [str(b) for b in repo_files.bases_de_instalacao()]

        assert len(caminhos) == len(set(caminhos)), f"base repetida em {caminhos}"


class TestUmaRespostaSo:
    """O portão contra a reincidência: `cmd_doctor` não tem lista própria."""

    def test_o_cmd_doctor_nao_carrega_bases_proprias(self) -> None:
        fonte = (
            RAIZ_DO_REPO
            / "src"
            / "hefesto_dualsense4unix"
            / "cli"
            / "cmd_doctor.py"
        ).read_text(encoding="utf-8")

        reincidentes = [
            linha.strip()
            for linha in fonte.splitlines()
            if "share/hefesto-dualsense4unix" in linha
        ]

        assert not reincidentes, (
            "o `cmd_doctor` voltou a escrever caminhos de instalação por conta "
            "própria:\n  " + "\n  ".join(reincidentes) + "\n\nA lista tem UM "
            "dono — `utils/repo_files.bases_de_instalacao()`. Duas cópias já "
            "divergiram uma vez (T-02(b) curou uma e deixou a outra)."
        )

    def test_o_cmd_doctor_usa_o_dono_unico(self) -> None:
        assert cmd_doctor.encontrar_arquivo_do_repo is repo_files.encontrar_arquivo_do_repo


class TestOAvisoDizOndeProcurou:
    """Quando o script não vem, a tela diz o que houve — e onde se olhou."""

    def test_o_aviso_lista_os_diretorios_consultados(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "prefix", str(tmp_path / "vazio"))

        rc = cmd_doctor._run_script("scripts/este-script-nunca-existiu.sh")
        saida = capsys.readouterr().out

        assert rc == 0, "script ausente não é falha do doctor — é uma linha de aviso"
        assert "não veio nesta instalação" in saida
        assert str(tmp_path / "vazio" / "share" / "hefesto-dualsense4unix") in saida, (
            "o aviso não lista as bases consultadas — quem lê não distingue "
            "'não instalado' de 'o produto olhou no lugar errado'.\n" + saida
        )
        assert "procurei o share do Hefesto em:" in saida, (
            "o aviso não diz onde procurou — e foi exatamente essa a pergunta "
            "que o defeito desta frente deixou sem resposta.\n" + saida
        )
