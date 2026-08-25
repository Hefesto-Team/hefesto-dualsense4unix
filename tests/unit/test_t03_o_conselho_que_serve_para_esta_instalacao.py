"""T-03/T-02(b) (SISTEMA-O-VIGIA-VIVO-01) — o conselho impossível.

As frases da aba Sistema **não mentiam**: quando um script falta, elas dizem
que falta. O defeito é outro, e mais difícil de ver — elas dão um **conselho
impossível**. Oito lugares mandavam *"rode `./install.sh`"* como única
instrução, e `./install.sh` só existe para quem clonou o repositório.

Medido em 23/08, por formato de pacote:

| formato | leva os scripts do cartão? | tem `./install.sh`? |
|---|---|---|
| checkout | sim | **sim** |
| .deb | sim | não |
| Flatpak / AppImage / Arch / Fedora / Nix | **não** | não |

Ou seja: em cinco dos seis formatos a pessoa via a frase COM MAIS
frequência — porque os scripts realmente faltavam — e a instrução que recebia
era a única que ela não tinha como cumprir.

T-02(b) é a outra metade do mesmo botão: `_find_repo_file` procurava em três
bases e **nenhuma delas era `/app/share`**, que é onde o Flatpak instala.
Mesmo com o manifesto passando a levar os scripts, a janela não os acharia.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import daemon_actions as da


class TestOGestoQueServeParaCadaInstalacao:
    def test_no_checkout_a_frase_nomeia_o_install_sh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Para ela, que roda do clone, o gesto certo continua sendo esse.

        A cura não podia piorar o caso que já funcionava: quem TEM o
        `install.sh` merece a instrução exata, não a genérica.
        """
        monkeypatch.setattr(da, "esta_instalacao_e_um_checkout", lambda: True)

        assert "./install.sh" in da.como_atualizar_esta_instalacao()

    def test_fora_do_checkout_a_frase_nao_cita_install_sh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida da T-03, na sua forma mais curta."""
        monkeypatch.setattr(da, "esta_instalacao_e_um_checkout", lambda: False)

        frase = da.como_atualizar_esta_instalacao()

        assert "install.sh" not in frase
        assert "atualize o Hefesto" in frase

    def test_a_deteccao_olha_para_um_arquivo_de_verdade(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Não é presunção: é a existência do arquivo no disco.

        Régua que sabe ACEITAR e RECUSAR — o mesmo diretório responde
        diferente antes e depois de o `install.sh` existir.
        """
        monkeypatch.setattr(
            da, "BASES_DE_INSTALACAO", (tmp_path, Path("/nao/existe"))
        )
        assert da.esta_instalacao_e_um_checkout() is False

        (tmp_path / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        assert da.esta_instalacao_e_um_checkout() is True


class TestNenhumaFraseDaTelaMandaAoLugarInexistente:
    """O portão da regra "sai de TODOS os lugares onde aparece"."""

    @pytest.mark.parametrize(
        "script_ok, wrapper_ok",
        [(False, False), (False, True), (True, False)],
    )
    def test_format_steam_ready_result_nao_cita_install_sh_fora_do_checkout(
        self, monkeypatch: pytest.MonkeyPatch, script_ok: bool, wrapper_ok: bool
    ) -> None:
        """Os três ramos de instalação incompleta que a sprint nomeia.

        `janela="ok"` NÃO é decoração: com qualquer outro valor,
        `format_steam_janela_recusa` corta a função no começo e devolve a
        recusa da janela — a frase de instalação incompleta nunca é
        alcançada, e o teste passaria sem exercitar nada. Foi o que aconteceu
        na primeira versão deste arquivo, e a mordida o revelou.
        """
        monkeypatch.setattr(da, "esta_instalacao_e_um_checkout", lambda: False)

        frase = da.format_steam_ready_result(
            janela="ok",
            dados={"script": (0, ""), "wrapper": {}},
            script_ok=script_ok,
            wrapper_ok=wrapper_ok,
        )

        assert "instalação" in frase, (
            f"o ramo de instalação incompleta não foi exercitado: {frase!r}"
        )
        assert "install.sh" not in frase, frase

    def test_nenhuma_frase_do_modulo_crava_install_sh(self) -> None:
        """O portão que impede a correção pela metade.

        A regra desta casa é que fato errado sai de todos os lugares, não só
        de onde foi notado — *"uma correção pela metade deixa as duas versões
        vivas, que é o defeito que a regra existe para matar"*.

        Ficam DE FORA, com motivo declarado:

        * `medir_guarda_do_steam_input` — a frase do vigia parado é da T-01,
          cuja hipótese (`enable --now` não re-arma) ainda **não foi medida**.
          Trocar o texto sem o veredito seria prometer um gesto que ninguém
          verificou;
        * as duas frases de PRIMEIRA instalação ("Rode o instalador uma vez")
          — o caso ali não é atualizar, e a redação alternativa é texto novo
          de tela, que é dela.
        """
        caminho = Path(da.__file__)
        fonte = caminho.read_text(encoding="utf-8")
        isentas = (
            "Conserto: rode `bash install.sh` de novo (sem sudo).",
            "instalador (install.sh) uma vez.",
        )

        # Docstring EXPLICA; código PINTA NA TELA. Só o segundo interessa —
        # e a diferença entre os dois não se descobre por indentação, se
        # descobre pela árvore sintática.
        linhas_de_docstring: set[int] = set()
        for no in ast.walk(ast.parse(fonte)):
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
                linhas_de_docstring.update(
                    range(alvo.lineno, (alvo.end_lineno or alvo.lineno) + 1)
                )

        suspeitas: list[str] = []
        for numero, linha in enumerate(fonte.splitlines(), start=1):
            if "install.sh" not in linha or numero in linhas_de_docstring:
                continue
            texto = linha.strip()
            if texto.startswith("#") or any(i in texto for i in isentas):
                continue
            # As únicas linhas de CÓDIGO que podem citar o nome: a que
            # PROCURA o arquivo, e o ramo do checkout — que é justamente
            # onde ele existe.
            permitidas = (
                "esta_instalacao_e_um_checkout",
                'BASES_DE_INSTALACAO[0] / "install.sh"',
                'return "rode ./install.sh para atualizar o Hefesto"',
            )
            if any(p in texto for p in permitidas):
                continue
            suspeitas.append(f"{numero}: {texto}")

        assert not suspeitas, (
            "frase de tela cravando `install.sh` fora do helper:\n  "
            + "\n  ".join(suspeitas)
            + "\n\nUse `como_atualizar_esta_instalacao()`. Em cinco dos seis "
            "formatos deste produto esse arquivo não existe na máquina."
        )


class TestOFlatpakEntrouNaListaDeBases:
    """T-02(b): `_find_repo_file` passa a conhecer `/app/share`."""

    def test_app_share_esta_entre_as_bases(self) -> None:
        caminhos = [str(b) for b in da.BASES_DE_INSTALACAO]

        assert "/app/share/hefesto-dualsense4unix" in caminhos

    def test_as_bases_de_sempre_continuam_la(self) -> None:
        """A base nova não pode ter empurrado nenhuma das antigas para fora.

        `parents[4]` em particular já custou um defeito próprio
        (BUG-GUI-REPO-ROOT-OFFBYONE-01: `parents[3]` apontava para `<repo>/src`
        e os botões viravam no-op SILENCIOSO, com toast de sucesso).
        """
        caminhos = [str(b) for b in da.BASES_DE_INSTALACAO]

        assert "/usr/share/hefesto-dualsense4unix" in caminhos
        assert "/usr/local/share/hefesto-dualsense4unix" in caminhos
        assert (Path(caminhos[0]) / "src" / "hefesto_dualsense4unix").is_dir(), (
            "a primeira base tem de ser a RAIZ do checkout, não o `src/`"
        )

    def test_find_repo_file_acha_em_qualquer_uma_das_bases(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A busca percorre a lista inteira — inclusive a base nova.

        Sem esta mordida, acrescentar `/app/share` seria decoração: o teste
        planta o script SÓ na segunda base e exige que a busca chegue lá.
        """
        falsa = tmp_path / "app-share"
        (falsa / "scripts").mkdir(parents=True)
        alvo = falsa / "scripts" / "disable_steam_input.sh"
        alvo.write_text("#!/bin/bash\n", encoding="utf-8")

        monkeypatch.setattr(
            da, "BASES_DE_INSTALACAO", (tmp_path / "vazia", falsa)
        )

        class _Host(da.DaemonActionsMixin):
            def __init__(self) -> None:
                pass

        achado = _Host()._find_repo_file("scripts/disable_steam_input.sh")

        assert achado == alvo
