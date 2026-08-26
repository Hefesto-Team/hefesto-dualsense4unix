"""BG-INSTALL-01 (26/08/2026) — *o conselho impossível, nos três que sobraram*.

A T-03 (25/08) tirou o `./install.sh` de OITO frases de `daemon_actions.py` e
escreveu a cura: `esta_instalacao_e_um_checkout()` +
`como_atualizar_esta_instalacao()`. Ela nasceu com **oito chamadores, todos
dentro do próprio arquivo** — e três frases de tela em OUTROS três arquivos
continuaram mandando rodar o instalador:

| arquivo | quem lê |
|---|---|
| `app/actions/emulation_actions.py:354` | quem clica em "Desligar Steam Input" sem o script |
| `app/actions/mouse_actions.py:605` | quem abre a aba Mouse sem o módulo `uinput` |
| `integrations/storm_doctor.py:334` | o laudo do travamento do USB, em toda instalação |

`./install.sh` só existe para quem clonou o repositório. Em cinco dos seis
formatos em que este produto é instalado — Flatpak, AppImage, Arch, Fedora,
Nix — o arquivo **não está na máquina**, e é justamente nesses formatos que a
pessoa vê estas frases com mais frequência, porque é neles que as coisas
faltam.

**A cura mudou de casa nesta frente.** As duas funções passaram de
`app/actions/daemon_actions.py` para `utils/repo_files.py`, porque
`integrations/storm_doctor.py` precisa delas e `integrations/` não pode
importar de `app/` — seria inverter a camada.

**Como ela morde.** Devolvendo qualquer uma das três frases ao literal:

* `test_fora_do_checkout_ninguem_manda_rodar_install_sh` varre `src/` inteiro
  pela árvore sintática e reprova com `arquivo:linha` e o texto;
* `TestAsTresFrasesObedecemAInstalacao` monta uma instalação SEM `install.sh`
  no disco e cobra as três de verdade — é a mordida de comportamento, e ela
  pega o que a varredura de texto não pega: uma frase que só mudou de lugar,
  ou um ajudante que passou a responder sempre a mesma coisa. Cada uma tem o
  par no checkout, porque **a cura não podia piorar o caso que já
  funcionava**.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import emulation_actions, mouse_actions
from hefesto_dualsense4unix.integrations import storm_doctor
from hefesto_dualsense4unix.utils import repo_files

SRC = Path(repo_files.__file__).resolve().parent.parent

#: O único lugar de `src/` onde `./install.sh` pode ser escrito, e a única
#: string que pode escrevê-lo: o ramo do checkout do próprio ajudante. Ele é a
#: cura, não a doença — quem tem o arquivo merece a instrução exata.
UNICA_FRASE_QUE_PODE = (
    Path(repo_files.__file__).resolve(),
    repo_files.FRASE_DE_ATUALIZAR[True],
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
    """As strings de CÓDIGO de um arquivo que cravam `./install.sh`.

    É por árvore sintática, não por `grep`: comentário e docstring citam o
    nome do arquivo o tempo todo (esta própria régua cita), e confundi-los com
    texto de tela daria um alarme convincente e falso. Pedaços de f-string
    entram — é lá que a interpolação do ajudante convive com texto fixo.
    """
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    docs = _linhas_de_docstring(arvore)
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        if "./install.sh" not in no.value or no.lineno in docs:
            continue
        if (caminho, no.value) == UNICA_FRASE_QUE_PODE:
            continue
        achados.append((no.lineno, no.value))
    return achados


class TestNenhumaFraseDeTelaCravaOInstalador:
    def test_fora_do_checkout_ninguem_manda_rodar_install_sh(self) -> None:
        """A varredura de `src/` inteiro — a regra "sai de TODOS os lugares".

        Não é só dos três arquivos desta frente de propósito: uma correção
        pela metade deixa as duas versões vivas, que é o defeito que a regra
        existe para matar.
        """
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
        """Régua que só sabe absolver não é régua.

        Um arquivo de mentira com a frase no código e a mesma frase numa
        docstring: a varredura tem de pegar UMA — a de código — e só ela.
        """
        falso = tmp_path / "mentira.py"
        falso.write_text(
            '"""Uma docstring que cita ./install.sh e não é tela."""\n'
            "# um comentário que cita ./install.sh\n"
            'MSG = "rode ./install.sh"\n',
            encoding="utf-8",
        )

        assert _frases_com_install_sh(falso) == [(3, "rode ./install.sh")]


class TestAsTresFrasesObedecemAInstalacao:
    """A mordida de comportamento: uma instalação SEM `install.sh` no disco.

    Não é presunção sobre o formato — é o mesmo diretório respondendo
    diferente antes e depois de o arquivo existir, que é a régua da própria
    cura.
    """

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

    # --- a aba Emulação -----------------------------------------------------

    def test_desligar_steam_input_sem_script(self, sem_checkout: None) -> None:
        frase = emulation_actions.format_steam_input_result(status="sem_script")

        assert "install.sh" not in frase, frase
        assert repo_files.FRASE_DE_ATUALIZAR[False] in frase, frase

    def test_desligar_steam_input_no_checkout_nao_mudou(
        self, com_checkout: None
    ) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        frase = emulation_actions.format_steam_input_result(status="sem_script")

        assert "./install.sh" in frase, frase

    # --- a aba Mouse --------------------------------------------------------

    @staticmethod
    def _pintar_a_aba_mouse(monkeypatch: pytest.MonkeyPatch) -> str:
        """Roda `_refresh_mouse_view` no ramo "falta o módulo `uinput`".

        `sys.modules["uinput"] = None` faz o `import uinput` levantar
        `ImportError` sem mexer no ambiente — é o ramo, e é o único que fala
        de instalação.
        """
        monkeypatch.setitem(sys.modules, "uinput", None)

        class _Label:
            markup = ""

            def set_markup(self, texto: str) -> None:
                _Label.markup = texto

        class _Host(mouse_actions.MouseActionsMixin):
            _mouse_virtual_no_ar = None

            def __init__(self) -> None:
                pass

            def _get(self, _widget_id: str) -> object:
                return _Label()

        _Host()._refresh_mouse_view()
        return _Label.markup

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

    # --- o laudo do travamento do USB --------------------------------------

    @staticmethod
    def _laudo_do_quirk(tmp_path: Path) -> str:
        """O ramo "a cura do travamento não está instalada".

        Sem sysfs e sem drop-in: os dois argumentos são injetados, então o
        laudo é o do WARN sem tocar a máquina de ninguém.
        """
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


class TestOConselhoNaoTemDUASREDACOES:
    def test_o_texto_mora_num_lugar_so(self) -> None:
        """`daemon_actions` delega; não redige de novo.

        Duas redações com o mesmo sentido é como duas verdades começam nesta
        casa — e uma delas envelhece sozinha.
        """
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        fonte = Path(da.__file__).read_text(encoding="utf-8")

        for frase in repo_files.FRASE_DE_ATUALIZAR.values():
            assert frase not in fonte, (
                f"`daemon_actions` reescreveu a frase {frase!r}. Ela mora em "
                "`utils/repo_files.FRASE_DE_ATUALIZAR`, e é comparada palavra "
                "por palavra com a do `scripts/doctor.sh` por portão."
            )
