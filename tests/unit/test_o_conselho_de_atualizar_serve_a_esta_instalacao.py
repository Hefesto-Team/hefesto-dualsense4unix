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

**E EM 20/09/2026 NASCEU A QUARTA** — `cli/cmd_tray.py:100`, o «Abrir painel»
quando o lançador não está no PATH. Ela veio com o tray de 19/09
(`TRAY-ORFAO-01`), escrita de dentro de um checkout, e a varredura abaixo a
pegou no dia seguinte: *régua nova não impede frase nova, só encurta o tempo
entre escrevê-la e vê-la*. Ela ganhou o par de comportamento das outras três.

**E AS SETE QUE A RÉGUA NÃO VIA — O-INSTALADOR-SEM-A-BARRA-01 (20/09/2026).**
A varredura procurava `./install.sh`, **com a barra**, e sete frases de tela
escreviam o nome SEM ela — onde a régua não alcançava:

| arquivo | quem lê |
|---|---|
| `app/actions/daemon_actions.py:2286` | a dica do «Reiniciar daemon» em cinza |
| `app/actions/daemon_actions.py:2390` | o recado de quem não tem `systemctl` |
| `app/widgets/controller_card.py:941` | a dica do canal do alto-falante sem a regra |
| `integrations/alto_falante_bt.py:302` | quem manda som ao controle sem a libopus |
| `integrations/alto_falante_bt.py:2211` | o laudo de por que o nó de som não sobe |
| `integrations/dualsense_bt_audio.py:581` | quem abre o microfone do rádio sem a libopus |
| `integrations/dualsense_bt_audio.py:1775` | o laudo de por que a ponte do rádio não sobe |

**A ORDEM IMPORTOU:** alargar a régua ANTES de trocar as sete deixaria a suíte
vermelha em sete pontos de uma vez. As sete foram primeiro; a régua depois.

**QUATRO DAS SETE SAÍRAM DESTA FAMÍLIA — A-LIBOPUS-TEM-NOME-EM-CADA-CASA-01
(20/09/2026).** As quatro linhas da libopus acima (as duas de
`alto_falante_bt.py` e as duas de `dualsense_bt_audio.py`) davam o gesto de
ATUALIZAR o Hefesto para instalar uma BIBLIOTECA — e `pacman -Syu` não
instala a libopus. Elas passaram a chamar `storm_doctor.gesto_de_instalar`,
cujo nome de pacote é lido do dono (`install.sh`), e o que esta régua cobra
delas inverteu-se: o conselho de atualizar não pode VOLTAR para dentro delas.
A proibição do nome do instalador segue valendo para as onze.

A `DICA_CANAL_SEM_A_REGRA` do `controller_card` **virou função** nessa troca
(`dica_canal_sem_a_regra()`): congelada no import, ela responderia pela
instalação de quem importou, e o par de comportamento não teria como mordê-la
— que é exatamente a segunda mordida do `80dcb8fa1`.

`./install.sh` só existe para quem clonou o repositório. Em cinco dos seis
formatos em que este produto é instalado — Flatpak, AppImage, Arch, Fedora,
Nix — o arquivo **não está na máquina**, e é justamente nesses formatos que a
pessoa vê estas frases com mais frequência, porque é neles que as coisas
faltam.

**A cura mudou de casa nesta frente.** As duas funções passaram de
`app/actions/daemon_actions.py` para `utils/repo_files.py`, porque
`integrations/storm_doctor.py` precisa delas e `integrations/` não pode
importar de `app/` — seria inverter a camada.

**Como ela morde.** Devolvendo qualquer uma das onze frases ao literal:

* `test_fora_do_checkout_ninguem_manda_rodar_install_sh` varre `src/` inteiro
  pela árvore sintática e reprova com `arquivo:linha` e o texto;
* `TestAsOnzeFrasesObedecemAInstalacao` monta uma instalação SEM `install.sh`
  no disco e cobra as onze de verdade — é a mordida de comportamento, e ela
  pega o que a varredura de texto não pega: uma frase que só mudou de lugar,
  ou um ajudante que passou a responder sempre a mesma coisa. Cada uma tem o
  par no checkout, porque **a cura não podia piorar o caso que já
  funcionava**.
"""

from __future__ import annotations

import ast
import io
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from hefesto_dualsense4unix.app.actions import emulation_actions, mouse_actions
from hefesto_dualsense4unix.integrations import storm_doctor
from hefesto_dualsense4unix.utils import repo_files

SRC = Path(repo_files.__file__).resolve().parent.parent

#: O nome do instalador em qualquer forma — com a barra, sem ela, depois de um
#: `bash`, entre crases. O olhar-para-trás recusa o `uninstall.sh`, que é outro
#: arquivo e não é conselho nenhum.
#:
#: **A BARRA ERA O PONTO CEGO** (O-INSTALADOR-SEM-A-BARRA-01, 20/09/2026):
#: enquanto esta régua procurava `./install.sh` literal, sete frases de tela
#: escreviam `install.sh` e passavam intactas por ela — uma delas com o
#: ponto cego ANOTADO no código ao lado, desde 26/08.
NOME_DO_INSTALADOR = re.compile(r"(?<![A-Za-z0-9_])install\.sh")

#: Os dois lugares de `src/` onde o nome do instalador pode ser escrito em
#: CÓDIGO, e as duas únicas strings que podem escrevê-lo. Os dois no próprio
#: ajudante, que é a cura e não a doença:
#:
#: * a frase do ramo do checkout — quem TEM o arquivo merece a instrução exata;
#: * o nome do arquivo que `esta_instalacao_e_um_checkout()` procura no disco.
#:   Ele não é texto de tela: é o `stat` que DECIDE qual das duas frases sai, e
#:   sem ele não há como distinguir um checkout de um `.deb`.
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
    """As strings de CÓDIGO de um arquivo que cravam o instalador.

    É por árvore sintática, não por `grep`: comentário e docstring citam o
    nome do arquivo o tempo todo (esta própria régua cita), e confundi-los com
    texto de tela daria um alarme convincente e falso. Pedaços de f-string
    entram — é lá que a interpolação do ajudante convive com texto fixo.

    Desde 20/09/2026 ela pega o nome em QUALQUER forma, não só `./install.sh`:
    a barra era o ponto cego, e sete frases moravam dentro dele.
    """
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

    def test_a_regua_pega_o_nome_sem_a_barra(self, tmp_path: Path) -> None:
        """A mordida do alargamento de 20/09/2026.

        Era exatamente isto que passava: as sete frases escreviam o nome sem
        o `./`, e a varredura — que procurava o literal com a barra — dava
        VERDE sobre as sete. As três formas abaixo são as que existiam no
        produto, e a quarta linha é o que a régua NÃO pode confundir: o
        `uninstall.sh` é outro arquivo, e nenhuma frase o crava.
        """
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

    # --- o «Abrir painel» do tray ------------------------------------------

    @staticmethod
    def _frase_do_tray(monkeypatch: pytest.MonkeyPatch) -> str:
        """O ramo "o lançador não está no PATH" do «Abrir painel».

        O `Popen` de mentira levanta `FileNotFoundError` sem chamar processo
        nenhum — nenhuma janela nasce na tela de ninguém. E o `Console`
        próprio, largo, existe porque o `rich` quebra linha na largura do
        terminal: medir a saída do console herdado seria medir a LARGURA da
        máquina que roda a suíte, não o texto que a pessoa lê.
        """
        from hefesto_dualsense4unix.cli import cmd_tray

        def _sem_lancador(*_args: object, **_kwargs: object) -> None:
            raise FileNotFoundError(cmd_tray.LANCADOR_DO_PAINEL)

        monkeypatch.setattr(cmd_tray.subprocess, "Popen", _sem_lancador)
        tinta = io.StringIO()
        monkeypatch.setattr(cmd_tray, "console", Console(file=tinta, width=400))

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

    # --- as duas do `daemon_actions` ---------------------------------------
    #
    # ELAS NÃO PASSAM PELO `repo_files` DIRETO, e por isso têm fixture
    # própria: `daemon_actions` congela as bases no import
    # (`BASES_DE_INSTALACAO`) e manda a pergunta pela escada de SETE degraus
    # do `storm_doctor.gesto_de_atualizar` — a que NOMEIA o gesto do formato
    # (`flatpak update`, `pacman -Syu`, …). Monkeypatchar
    # `repo_files.bases_de_instalacao` não alcança nenhuma das duas.
    #
    # Fora do checkout a asserção é «não há o nome do instalador na frase», e
    # não um texto fixo: qual dos sete degraus sai depende da MÁQUINA que roda
    # a suíte, e uma régua que cobra o degrau mede a máquina, não o produto.
    # Dentro do checkout o degrau é único, e a asserção volta a ser exata.

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

    @staticmethod
    def _dica_do_botao_cinza(monkeypatch: pytest.MonkeyPatch) -> str:
        """A dica do «Reiniciar daemon» quando NENHUMA unit está instalada.

        Nada de `Gtk`: o botão é um dublê que só guarda o que lhe mandam
        escrever, e o `_get` do host o devolve. O `ServiceInstaller` é trocado
        por um que diz "não há unit" sem falar com o systemd — a régua não
        pode perguntar à máquina de quem roda a suíte se o produto está
        instalado nela.
        """
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        class _Botao:
            dica = ""

            def set_sensitive(self, _valor: bool) -> None:
                pass

            def set_tooltip_text(self, texto: str) -> None:
                _Botao.dica = texto

        class _SemUnit:
            def detect_installed_unit(self) -> None:
                return None

        monkeypatch.setattr(da, "ServiceInstaller", _SemUnit)

        class _Host(da.DaemonActionsMixin):
            def __init__(self) -> None:
                pass

            def _get(self, _widget_id: str) -> object:
                return _Botao()

        _Host()._sync_restart_daemon_button_sensitivity()
        return _Botao.dica

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

    @staticmethod
    def _recado_sem_systemctl() -> str:
        """O recado de «este computador não tem `systemctl`».

        `_on_service_restart_done` com `err_type="missing"` é o ramo, e o
        `_show_restart_error` sobrescrito recolhe o texto sem abrir diálogo
        nenhum na tela de ninguém.
        """
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        class _Host(da.DaemonActionsMixin):
            recado = ""

            def __init__(self) -> None:
                pass

            def _show_restart_error(self, message: str) -> None:
                _Host.recado = message

        _Host()._on_service_restart_done(-1, "", "missing")
        return _Host.recado

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

    # --- a dica do canal do alto-falante -----------------------------------
    #
    # ELA ERA CONSTANTE ATÉ 20/09/2026, e é por isso que este par existe: uma
    # `Final[str]` montada no import responde pela instalação de quem
    # importou. Virou função, e a função pergunta ao disco a cada leitura.

    @staticmethod
    def _dica_do_canal_sem_a_regra() -> str:
        from hefesto_dualsense4unix.app.widgets import controller_card

        return controller_card.dica_canal_sem_a_regra()

    def test_a_dica_do_canal_sem_a_regra(self, sem_checkout: None) -> None:
        dica = self._dica_do_canal_sem_a_regra()

        assert "NÃO está instalada nesta" in dica, dica
        assert "install.sh" not in dica, dica
        assert repo_files.FRASE_DE_ATUALIZAR[False] in dica, dica

    def test_a_dica_do_canal_no_checkout_nao_mudou(self, com_checkout: None) -> None:
        """A cura não podia piorar o caso que já funcionava."""
        dica = self._dica_do_canal_sem_a_regra()

        assert "./install.sh" in dica, dica

    # --- as quatro da libopus ----------------------------------------------
    #
    # Duas são a recusa de carregar a `.so` (o som pelo rádio e o microfone
    # pelo rádio), duas são o laudo de «por que isto não sobe». As quatro são
    # exercitadas de verdade: o soname de mentira faz o `ctypes.CDLL` falhar
    # sem tocar biblioteca nenhuma do sistema, e o handle global é zerado para
    # que uma libopus JÁ carregada por outro teste não esconda o ramo.

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
        """O que o DONO do nome manda fazer nesta instalação, agora.

        Perguntado ao `storm_doctor`, nunca digitado: o nome do pacote muda
        com a distribuição, e uma régua que o digita é mais uma cópia do dado.
        """
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
        """A-LIBOPUS-TEM-NOME-EM-CADA-CASA-01 (20/09/2026): estas duas saíram.

        Elas davam o gesto de ATUALIZAR o Hefesto para instalar uma
        biblioteca — e `pacman -Syu` não instala a libopus. Hoje chamam
        `storm_doctor.gesto_de_instalar`; quem mede o NOME do pacote é
        `tests/unit/test_o_nome_do_pacote_tem_um_dono_so.py`.

        O que esta régua guarda continua sendo o desta casa: o conselho de
        atualizar não pode voltar para dentro delas.
        """
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
