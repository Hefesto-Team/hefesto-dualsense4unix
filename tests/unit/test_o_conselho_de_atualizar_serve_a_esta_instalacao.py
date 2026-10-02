"""BG-INSTALL-01 (26/08/2026) — *o conselho impossível, nos três que sobraram*."""

from __future__ import annotations

import ast
import io
import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.mouse_actions`, que carrega o GTK")

from rich.console import Console

from hefesto_dualsense4unix.integrations import storm_doctor
from hefesto_dualsense4unix.utils import repo_files

SRC = Path(repo_files.__file__).resolve().parent.parent

NOME_DO_INSTALADOR = re.compile(r"(?<![A-Za-z0-9_])install\.sh")

O_QUE_PODE_ESCREVER_O_NOME: frozenset[tuple[Path, str]] = frozenset(
    {
        (Path(repo_files.__file__).resolve(), repo_files.FRASE_DE_ATUALIZAR[True]),
        (Path(repo_files.__file__).resolve(), "install.sh"),
    }
)


def _linhas_de_docstring(arvore: ast.AST) -> set[int]:
    """Docstring EXPLICA; código PINTA NA TELA. Só o segundo interessa."""
    linhas: set[int] = set()
    for no in ast.walk(arvore):
        if not isinstance(
            no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        corpo = getattr(no, "body", [])
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            alvo = corpo[0]
            linhas.update(range(alvo.lineno, (alvo.end_lineno or alvo.lineno) + 1))
    return linhas


def _frases_com_install_sh(caminho: Path) -> list[tuple[int, str]]:
    """As strings de CÓDIGO de um arquivo que cravam o instalador."""
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    docs = _linhas_de_docstring(arvore)
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        if not NOME_DO_INSTALADOR.search(no.value) or no.lineno in docs:
            continue
        if (caminho, no.value) in O_QUE_PODE_ESCREVER_O_NOME:
            continue
        achados.append((no.lineno, no.value))
    return achados


class TestNenhumaFraseDeTelaCravaOInstalador:
    def test_fora_do_checkout_ninguem_manda_rodar_install_sh(self) -> None:
        """A varredura de `src/` inteiro — a regra "sai de TODOS os lugares"."""
        suspeitas = [
            f"{caminho.relative_to(SRC)}:{linha}: {texto!r}"
            for caminho in sorted(SRC.rglob("*.py"))
            for linha, texto in _frases_com_install_sh(caminho)
        ]

        assert not suspeitas, (
            "frase de tela mandando rodar o instalador:\n  "
            + "\n  ".join(suspeitas)
            + "\n\nUse `utils.repo_files.como_atualizar_esta_instalacao()`. "
            "Em cinco dos seis formatos deste produto `./install.sh` não "
            "existe na máquina de quem está lendo a frase."
        )

    def test_a_regua_sabe_acusar(self, tmp_path: Path) -> None:
        """Régua que só sabe absolver não é régua."""
        falso = tmp_path / "mentira.py"
        falso.write_text(
            '"""Uma docstring que cita ./install.sh e não é tela."""\n'
            "# um comentário que cita ./install.sh\n"
            'MSG = "rode ./install.sh"\n',
            encoding="utf-8",
        )

        assert _frases_com_install_sh(falso) == [(3, "rode ./install.sh")]

    def test_a_regua_pega_o_nome_sem_a_barra(self, tmp_path: Path) -> None:
        """A mordida do alargamento de 20/09/2026."""
        falso = tmp_path / "sem_a_barra.py"
        falso.write_text(
            'DICA = "Rode o install.sh de novo"\n'
            'ERRO = "instale libopus0 — ver install.sh"\n'
            'TIP = "Rode o instalador (install.sh) uma vez."\n'
            'OUTRO = "rode o uninstall.sh para sair"\n'
            'NEM_ESTE = "scripts/install_profiles.sh"\n',
            encoding="utf-8",
        )

        assert _frases_com_install_sh(falso) == [
            (1, "Rode o install.sh de novo"),
            (2, "instale libopus0 — ver install.sh"),
            (3, "Rode o instalador (install.sh) uma vez."),
        ]


class TestAsOnzeFrasesObedecemAInstalacao:
    """A mordida de comportamento: uma instalação SEM `install.sh` no disco."""

    @pytest.fixture
    def sem_checkout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        pacote = tmp_path / "app-share"
        pacote.mkdir()
        monkeypatch.setattr(repo_files, "bases_de_instalacao", lambda: (pacote,))
        assert repo_files.esta_instalacao_e_um_checkout() is False

    @pytest.fixture
    def com_checkout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        clone = tmp_path / "clone"
        clone.mkdir()
        (clone / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        monkeypatch.setattr(repo_files, "bases_de_instalacao", lambda: (clone,))
        assert repo_files.esta_instalacao_e_um_checkout() is True


    def test_a_aba_mouse_sem_o_modulo(
        self, sem_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = self._pintar_a_aba_mouse(monkeypatch)

        assert "Falta um componente do mouse virtual" in markup, markup
        assert "install.sh" not in markup, markup
        assert repo_files.FRASE_DE_ATUALIZAR[False] in markup, markup

    def test_a_aba_mouse_no_checkout_nao_mudou(
        self, com_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = self._pintar_a_aba_mouse(monkeypatch)

        assert "./install.sh" in markup, markup


    @staticmethod
    def _laudo_do_quirk(tmp_path: Path) -> str:
        """O ramo "a cura do travamento não está instalada"."""
        tag, laudo = storm_doctor.check_snd_quirk(
            quirk_flags_text="", conf_path=tmp_path / "ausente.conf"
        )
        assert tag == storm_doctor.WARN, tag
        return laudo

    def test_o_laudo_do_quirk(self, sem_checkout: None, tmp_path: Path) -> None:
        laudo = self._laudo_do_quirk(tmp_path)

        assert "cura do travamento do USB AUSENTE" in laudo, laudo
        assert "install.sh" not in laudo, laudo
        assert repo_files.FRASE_DE_ATUALIZAR[False] in laudo, laudo

    def test_o_laudo_do_quirk_no_checkout_nao_mudou(
        self, com_checkout: None, tmp_path: Path
    ) -> None:
        laudo = self._laudo_do_quirk(tmp_path)

        assert "./install.sh" in laudo, laudo


    @staticmethod
    def _frase_do_tray(monkeypatch: pytest.MonkeyPatch) -> str:
        """O ramo "o lançador não está no PATH" do «Abrir painel»."""
        from hefesto_dualsense4unix.cli import cmd_tray

        def _sem_lancador(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(cmd_tray.LANCADOR_DO_PAINEL)

        monkeypatch.setattr(cmd_tray.subprocess, "Popen", _sem_lancador)
        tinta = io.StringIO()
        from hefesto_dualsense4unix.app.actions import atos_da_bandeja

        monkeypatch.setattr(atos_da_bandeja, "console", Console(file=tinta, width=400))

        cmd_tray._abrir_o_painel()
        return tinta.getvalue()

    def test_o_tray_sem_o_lancador_no_path(
        self, sem_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        frase = self._frase_do_tray(monkeypatch)

        assert "não achei" in frase, frase
        assert "install.sh" not in frase, frase
        assert repo_files.FRASE_DE_ATUALIZAR[False] in frase, frase

    def test_o_tray_no_checkout_nao_mudou(
        self, com_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        frase = self._frase_do_tray(monkeypatch)

        assert "./install.sh" in frase, frase


    @pytest.fixture
    def daemon_sem_checkout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        pacote = tmp_path / "app-share-daemon"
        pacote.mkdir()
        monkeypatch.setattr(da, "BASES_DE_INSTALACAO", (pacote,))
        assert da.esta_instalacao_e_um_checkout() is False

    @pytest.fixture
    def daemon_com_checkout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        clone = tmp_path / "clone-daemon"
        clone.mkdir()
        (clone / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        monkeypatch.setattr(da, "BASES_DE_INSTALACAO", (clone,))
        assert da.esta_instalacao_e_um_checkout() is True


    def test_a_dica_do_botao_cinza(
        self, daemon_sem_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dica = self._dica_do_botao_cinza(monkeypatch)

        assert "não foi instalado como serviço" in dica, dica
        assert "install.sh" not in dica, dica

    def test_a_dica_do_botao_cinza_no_checkout_nao_mudou(
        self, daemon_com_checkout: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        dica = self._dica_do_botao_cinza(monkeypatch)

        assert "./install.sh" in dica, dica


    def test_o_recado_sem_systemctl(self, daemon_sem_checkout: None) -> None:
        recado = self._recado_sem_systemctl()

        assert "gerenciador de serviços" in recado, recado
        assert "install.sh" not in recado, recado

    def test_o_recado_sem_systemctl_no_checkout_nao_mudou(
        self, daemon_com_checkout: None
    ) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        recado = self._recado_sem_systemctl()

        assert "./install.sh" in recado, recado


    def test_a_dica_do_canal_sem_a_regra(self, sem_checkout: None) -> None:
        dica = self._dica_do_canal_sem_a_regra()

        assert "NÃO está instalada nesta" in dica, dica
        assert "install.sh" not in dica, dica
        assert repo_files.FRASE_DE_ATUALIZAR[False] in dica, dica

    def test_a_dica_do_canal_no_checkout_nao_mudou(self, com_checkout: None) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        dica = self._dica_do_canal_sem_a_regra()

        assert "./install.sh" in dica, dica


    @staticmethod
    def _recusa_da_libopus(
        monkeypatch: pytest.MonkeyPatch, modulo: Any, handle: str
    ) -> str:
        monkeypatch.setattr(modulo, "_SONAMES_OPUS", ("libopus-que-nao-existe.so.0",))
        monkeypatch.setattr(modulo, handle, None)
        carregar = (
            modulo._carregar_libopus_encoder
            if handle == "_LIB_OPUS_ENC"
            else modulo._carregar_libopus
        )
        with pytest.raises(modulo.OpusIndisponivelError) as erro:
            carregar()
        return str(erro.value)

    @pytest.fixture
    def os_dois_de_som(self) -> tuple[tuple[Any, str], ...]:
        from hefesto_dualsense4unix.integrations import (
            alto_falante_bt,
            dualsense_bt_audio,
        )

        return (
            (alto_falante_bt, "_LIB_OPUS_ENC"),
            (dualsense_bt_audio, "_LIB_OPUS"),
        )

    @staticmethod
    def _gestos_de_instalar() -> set[str]:
        """O que o DONO do nome manda fazer nesta instalação, agora."""
        return {
            storm_doctor.gesto_de_instalar(chave)
            for chave in storm_doctor.PACOTE_POR_FORMATO
        }

    def test_a_recusa_da_libopus_manda_instalar_e_nao_atualizar(
        self,
        sem_checkout: None,
        monkeypatch: pytest.MonkeyPatch,
        os_dois_de_som: tuple[tuple[Any, str], ...],
    ) -> None:
        """A-LIBOPUS-TEM-NOME-EM-CADA-CASA-01 (20/09/2026): estas duas saíram."""
        gestos = self._gestos_de_instalar()
        for modulo, handle in os_dois_de_som:
            frase = self._recusa_da_libopus(monkeypatch, modulo, handle)

            assert "libopus não encontrada" in frase, frase
            assert "install.sh" not in frase, frase
            assert repo_files.FRASE_DE_ATUALIZAR[False] not in frase, frase
            assert any(gesto in frase for gesto in gestos), frase

    def test_a_recusa_da_libopus_no_checkout_tambem_manda_instalar(
        self,
        com_checkout: None,
        monkeypatch: pytest.MonkeyPatch,
        os_dois_de_som: tuple[tuple[Any, str], ...],
    ) -> None:
        """No checkout também: `./install.sh` atualiza o Hefesto, não a libopus."""
        gestos = self._gestos_de_instalar()
        for modulo, handle in os_dois_de_som:
            frase = self._recusa_da_libopus(monkeypatch, modulo, handle)

            assert "install.sh" not in frase, frase
            assert repo_files.FRASE_DE_ATUALIZAR[True] not in frase, frase
            assert any(gesto in frase for gesto in gestos), frase

    @staticmethod
    def _laudos_sem_a_libopus() -> tuple[str, str]:
        """A linha da libopus nos dois laudos de «por que isto não sobe»."""
        from hefesto_dualsense4unix.integrations import (
            alto_falante_bt,
            dualsense_bt_audio,
        )

        som = alto_falante_bt.Diagnostico(
            controles=["um"], libopus=None, pactl=True, null_sink=True, loopback=True
        )
        ponte = dualsense_bt_audio.Diagnostico(
            controles=[], libopus=None, pactl=True, pipe_source=True, broker=True
        )
        return (
            next(f for f in som.impedimentos if "libopus" in f),
            next(f for f in ponte.impedimentos if "libopus" in f),
        )

    def test_os_laudos_sem_a_libopus_mandam_instalar(self, sem_checkout: None) -> None:
        """Os dois laudos seguiram as duas recusas: instalam, não atualizam."""
        gestos = self._gestos_de_instalar()
        for laudo in self._laudos_sem_a_libopus():
            assert "libopus ausente" in laudo, laudo
            assert "install.sh" not in laudo, laudo
            assert repo_files.FRASE_DE_ATUALIZAR[False] not in laudo, laudo
            assert any(gesto in laudo for gesto in gestos), laudo

    def test_os_laudos_no_checkout_tambem_mandam_instalar(
        self, com_checkout: None
    ) -> None:
        """Quem TEM o instalador ao lado também precisa da biblioteca."""
        gestos = self._gestos_de_instalar()
        for laudo in self._laudos_sem_a_libopus():
            assert "install.sh" not in laudo, laudo
            assert repo_files.FRASE_DE_ATUALIZAR[True] not in laudo, laudo
            assert any(gesto in laudo for gesto in gestos), laudo


class TestOConselhoNaoTemDUASREDACOES:
    def test_o_texto_mora_num_lugar_so(self) -> None:
        """`daemon_actions` delega; não redige de novo."""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        fonte = Path(da.__file__).read_text(encoding="utf-8")

        for frase in repo_files.FRASE_DE_ATUALIZAR.values():
            assert frase not in fonte, (
                f"`daemon_actions` reescreveu a frase {frase!r}. Ela mora em "
                "`utils/repo_files.FRASE_DE_ATUALIZAR`, e é comparada palavra "
                "por palavra com a do `scripts/doctor.sh` por portão."
            )
