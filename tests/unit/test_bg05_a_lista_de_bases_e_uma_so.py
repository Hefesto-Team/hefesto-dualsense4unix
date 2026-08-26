"""BG-BASES-01 (26/08/2026) — *cinco listas respondiam "onde estão os scripts"*.

O defeito, do lado de quem usa: **o arquivo está na máquina e o botão diz que
não está.** Quem instalou por Flatpak clica em "Verificar" ou em "Desligar
Steam Input" na aba Emulação e recebe *"Não encontrei o script…"* — com o
`disable_steam_input.sh` instalado em
`/app/share/hefesto-dualsense4unix/scripts/` pelo próprio manifesto. Quem
instalou por AppImage, Nix, venv ou `pip --user` clica em "Aplicar correções"
na aba Sistema e ouve o mesmo. Em todos os casos o produto olhou na lista
curta.

`utils/repo_files.py` nasceu em 25/08 para ser a resposta única e ficou com
**um** consumidor (`cli/cmd_doctor.py`). Esta régua cobra as outras quatro:

| resolvedor | tinha | e não conhecia |
|---|---|---|
| `daemon_actions…._find_repo_file` | 4 bases | `sys.prefix`, `share/` do usuário |
| `emulation_actions…._mic_script` | 3 bases | as duas acima e `/app/share` |
| `emulation_actions…._steam_input_script` | 3 bases | as mesmas três |
| `cli.cmd_mic._find_script` | 3 bases | as mesmas três |

**Como ela morde.** Devolvendo qualquer um dos quatro à lista à mão:

* `test_nenhum_resolvedor_a_mao_sobreviveu` reprova nomeando a **função** e o
  literal que voltou (`/usr/share/`, `/app/share/`, `parents[`);
* `test_os_quatro_resolvedores_obedecem_a_busca_unica` reprova porque o
  resolvedor ignora a lista de bases que o teste plantou e olha para a sua
  própria — é a mordida de comportamento, não de texto;
* `test_a_busca_unica_conhece_as_seis_bases` reprova **nomeando a base que
  falta**, que é a linha por onde cada formato de instalação entra.
"""

from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import emulation_actions
from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin
from hefesto_dualsense4unix.cli import cmd_mic
from hefesto_dualsense4unix.utils import repo_files

#: Os quatro resolvedores que a BG-BASES-01 converteu, e o arquivo relativo
#: que cada um procura. O caminho é dado aqui porque é ele que o teste planta
#: na base de mentira — sem isso a régua provaria só que a função existe.
RESOLVEDORES: tuple[tuple[str, Callable[..., Path | None], str], ...] = (
    (
        "daemon_actions.DaemonActionsMixin._find_repo_file",
        DaemonActionsMixin._find_repo_file,
        "scripts/install_snd_quirk.sh",
    ),
    (
        "emulation_actions.EmulationActionsMixin._mic_script",
        emulation_actions.EmulationActionsMixin._mic_script,
        "scripts/fix_wireplumber_default_source.sh",
    ),
    (
        "emulation_actions.EmulationActionsMixin._steam_input_script",
        emulation_actions.EmulationActionsMixin._steam_input_script,
        "scripts/disable_steam_input.sh",
    ),
    ("cmd_mic._find_script", cmd_mic._find_script, "scripts/fix_wireplumber_default_source.sh"),
)

#: Os pedaços de caminho que SÓ podem aparecer em `utils/repo_files.py`. Ver
#: um destes num resolvedor é ver a lista à mão de volta.
LITERAIS_DE_LISTA_A_MAO = (
    "/usr/share/",
    "/usr/local/share/",
    "/app/share/",
    "parents[",
)

#: Os módulos que perderam a lista própria. A varredura é do arquivo INTEIRO
#: (não só do corpo da função) porque a forma antiga era uma constante de
#: módulo — `BASES_DE_INSTALACAO` — e olhar só a função a deixaria voltar
#: pela porta dos fundos.
MODULOS_CONVERTIDOS = (
    "app/actions/daemon_actions.py",
    "app/actions/emulation_actions.py",
    "cli/cmd_mic.py",
)

RAIZ_DO_PACOTE = Path(repo_files.__file__).resolve().parent.parent


def _linhas_de_docstring(arvore: ast.AST) -> set[int]:
    """As linhas que EXPLICAM, para não confundi-las com as que executam.

    Uma docstring pode citar `/usr/share` para dizer que a lista morreu — é
    exatamente o que as deste conserto fazem. A diferença entre explicar e
    executar não se descobre por indentação; descobre-se pela árvore.
    """
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


def _codigo_de(fonte: str) -> list[tuple[int, str]]:
    """As linhas de CÓDIGO de um fonte: sem docstring e sem comentário."""
    docs = _linhas_de_docstring(ast.parse(fonte))
    saida: list[tuple[int, str]] = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        if numero in docs:
            continue
        texto = linha.strip()
        if not texto or texto.startswith("#"):
            continue
        saida.append((numero, texto))
    return saida


class TestNenhumaListaAMaoSobreviveu:
    def test_nenhum_resolvedor_a_mao_sobreviveu(self) -> None:
        """Os quatro corpos, lidos no fonte de verdade por `inspect`."""
        faltas: list[str] = []
        for nome, funcao, _relpath in RESOLVEDORES:
            # `inspect.getsource` devolve o método indentado dentro da
            # classe, e `ast.parse` recusa isso — daí o `dedent`.
            fonte = textwrap.dedent(inspect.getsource(funcao))
            for numero, texto in _codigo_de(fonte):
                for literal in LITERAIS_DE_LISTA_A_MAO:
                    if literal in texto:
                        faltas.append(f"{nome} (+{numero}): {literal!r} em {texto}")
            if "encontrar_arquivo_do_repo" not in fonte:
                faltas.append(
                    f"{nome}: não chama `encontrar_arquivo_do_repo` — "
                    "voltou a resolver o caminho por conta própria"
                )

        assert not faltas, (
            "a lista de bases voltou a ser escrita à mão:\n  "
            + "\n  ".join(faltas)
            + "\n\nA resposta é uma só: `utils/repo_files."
            "encontrar_arquivo_do_repo()`. Lista curta é como o Flatpak "
            "voltou a dizer 'não encontrei o script' com o arquivo instalado."
        )

    @pytest.mark.parametrize("relativo", MODULOS_CONVERTIDOS)
    def test_o_modulo_inteiro_nao_guarda_uma_segunda_lista(
        self, relativo: str
    ) -> None:
        """A constante de módulo é a porta dos fundos, e ela fica fechada.

        `BASES_DE_INSTALACAO` continua existindo em `daemon_actions` — mas
        **derivada** (`= bases_de_instalacao()`), nunca escrita. Esta régua é o
        que separa as duas formas.
        """
        caminho = RAIZ_DO_PACOTE / relativo
        suspeitas = [
            f"{relativo}:{numero}: {texto}"
            for numero, texto in _codigo_de(caminho.read_text(encoding="utf-8"))
            for literal in LITERAIS_DE_LISTA_A_MAO
            if literal in texto
        ]

        assert not suspeitas, (
            "um caminho de instalação foi escrito à mão fora de "
            "`utils/repo_files.py`:\n  " + "\n  ".join(suspeitas)
        )


class TestAListaDeBases:
    def test_a_busca_unica_conhece_as_seis_bases(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """As seis, e cada uma é um formato de instalação MEDIDO.

        `sys.prefix` é trocado por um diretório de mentira para que a base 2
        seja distinguível das outras — com o `sys.prefix` real ela pode
        coincidir com `/usr` e o teste não veria a diferença entre "está lá"
        e "não está".
        """
        prefixo = tmp_path / "prefixo"
        casa = tmp_path / "casa"
        monkeypatch.setattr(sys, "prefix", str(prefixo))
        monkeypatch.setenv("XDG_DATA_HOME", str(casa))

        bases = [str(b) for b in repo_files.bases_de_instalacao()]
        nome = repo_files.NOME_NO_SHARE
        esperadas = {
            "a raiz do checkout": str(Path(repo_files.__file__).resolve().parents[3]),
            "o prefixo do wheel (AppImage, venv, Nix)": str(
                prefixo / "share" / nome
            ),
            "o Flatpak": f"/app/share/{nome}",
            "o share do usuário (pip --user)": str(casa / nome),
            "o pacote do sistema (.deb, Arch, Fedora)": f"/usr/share/{nome}",
            "a instalação manual em /usr/local": f"/usr/local/share/{nome}",
        }

        faltando = {
            porque: caminho
            for porque, caminho in esperadas.items()
            if caminho not in bases
        }
        assert not faltando, (
            "a busca única deixou de olhar para um formato de instalação:\n  "
            + "\n  ".join(f"{p}: {c}" for p, c in faltando.items())
            + f"\n\nolhou só para: {bases}"
        )

    def test_a_raiz_do_checkout_e_a_raiz_mesmo(self) -> None:
        """BUG-GUI-REPO-ROOT-OFFBYONE-01: contar um `parents` a menos aponta
        para `<repo>/src`, e aí os botões viram no-op SILENCIOSO — toast de
        sucesso, nada executado."""
        primeira = repo_files.bases_de_instalacao()[0]

        assert (primeira / "src" / "hefesto_dualsense4unix").is_dir(), (
            f"a primeira base é {primeira}, que não é a raiz do checkout"
        )


class TestOsQuatroObedecemABuscaUnica:
    """A mordida de COMPORTAMENTO — a que a régua de texto não pega.

    Cada resolvedor é chamado com uma lista de bases plantada: uma vazia e uma
    que TEM o arquivo. Quem ainda carrega a lista própria olha para o disco de
    verdade e devolve outra coisa (ou `None`).
    """

    @pytest.fixture
    def base_de_mentira(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> Path:
        vazia = tmp_path / "vazia"
        vazia.mkdir()
        plantada = tmp_path / "app-share"
        (plantada / "scripts").mkdir(parents=True)
        monkeypatch.setattr(
            repo_files, "bases_de_instalacao", lambda: (vazia, plantada)
        )
        return plantada

    @pytest.mark.parametrize(
        ("nome", "funcao", "relpath"),
        RESOLVEDORES,
        ids=[nome for nome, _f, _r in RESOLVEDORES],
    )
    def test_os_quatro_resolvedores_obedecem_a_busca_unica(
        self,
        base_de_mentira: Path,
        monkeypatch: pytest.MonkeyPatch,
        nome: str,
        funcao: Callable[..., Path | None],
        relpath: str,
    ) -> None:
        alvo = base_de_mentira / relpath
        alvo.write_text("#!/bin/bash\n", encoding="utf-8")

        if "_find_repo_file" in nome:
            # Este consulta `BASES_DE_INSTALACAO` do próprio módulo (nome que
            # sobrevive porque testes de 25/08 o monkeypatcham); a lista dele
            # também é derivada da busca única.
            from hefesto_dualsense4unix.app.actions import daemon_actions as da

            monkeypatch.setattr(
                da, "BASES_DE_INSTALACAO", repo_files.bases_de_instalacao()
            )

        achado = (
            funcao(object(), relpath) if "_find_repo_file" in nome
            else funcao(object()) if "Mixin" in nome
            else funcao()
        )

        assert achado == alvo, (
            f"{nome} não olhou para a lista de bases da busca única — "
            f"devolveu {achado!r} em vez de {alvo}. É este o desvio que faz o "
            "Flatpak dizer 'não encontrei o script' com o script instalado."
        )

    def test_o_resolvedor_sabe_recusar(self, base_de_mentira: Path) -> None:
        """Régua que só sabe aceitar não é régua.

        Sem NADA plantado, os três que consultam a busca única devolvem
        `None` — que é *"não veio nesta instalação"*, não *"quebrou"*. É o
        caminho de erro que o dublê que só sabe passar nunca exercita.
        """
        for nome, funcao, _relpath in RESOLVEDORES:
            if "_find_repo_file" in nome:
                continue  # consulta a lista do próprio módulo; coberto acima
            achado = funcao(object()) if "Mixin" in nome else funcao()
            assert achado is None, f"{nome} devolveu {achado!r} de um lugar vazio"
