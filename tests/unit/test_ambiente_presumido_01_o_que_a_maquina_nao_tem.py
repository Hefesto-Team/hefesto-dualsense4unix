"""Testes da ONDA0-Z7 · O AMBIENTE PRESUMIDO 01 — o que a máquina não tem (Z7-D).

Cobre T-11 (o teclado na tela conhece mais que dois programas), T-12
(`osk_disponivel` ganha o primeiro leitor, num arquivo próprio) e T-13 (o
systemd de usuário deixa de ser presumido).
"""
from __future__ import annotations

from typing import ClassVar

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import ambiente_na_tela
from hefesto_dualsense4unix.daemon.subsystems import keyboard


# ---------------------------------------------------------------------------
# T-11 — o teclado na tela conhece mais que dois programas
# ---------------------------------------------------------------------------


class TestSqueekboardEMaliit:
    def test_squeekboard_entrou_nos_candidatos(self) -> None:
        assert keyboard._OSK_BIN_SQUEEKBOARD in keyboard._OSK_CANDIDATES
        assert keyboard._OSK_BIN_SQUEEKBOARD in keyboard._OSK_SPAWN_ARGS

    def test_maliit_entrou_nos_candidatos(self) -> None:
        assert keyboard._OSK_BIN_MALIIT in keyboard._OSK_CANDIDATES
        assert keyboard._OSK_BIN_MALIIT in keyboard._OSK_SPAWN_ARGS

    def test_squeekboard_vem_antes_do_onboard_em_sessao_wayland(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        monkeypatch.setenv("DISPLAY", ":1")
        candidatos = keyboard._osk_candidatos()
        assert candidatos.index(keyboard._OSK_BIN_SQUEEKBOARD) < candidatos.index(
            keyboard._OSK_BIN_X11
        )

    def test_maliit_vem_antes_do_onboard_em_sessao_wayland(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        monkeypatch.setenv("DISPLAY", ":1")
        candidatos = keyboard._osk_candidatos()
        assert candidatos.index(keyboard._OSK_BIN_MALIIT) < candidatos.index(
            keyboard._OSK_BIN_X11
        )

    def test_onboard_continua_primeiro_em_sessao_x11(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        monkeypatch.setenv("DISPLAY", ":0")
        assert keyboard._osk_candidatos()[0] == keyboard._OSK_BIN_X11

    def test_path_so_com_squeekboard_fica_disponivel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA de T-11: só squeekboard instalado -> disponível=True, e
        `_osk_candidatos()` o coloca primeiro em sessão Wayland."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.setattr(
            keyboard.shutil,
            "which",
            lambda n: "/usr/bin/squeekboard" if n == keyboard._OSK_BIN_SQUEEKBOARD else None,
        )
        assert keyboard.osk_disponivel_no_sistema() is True

        ctrl = keyboard._OSKController()
        assert ctrl._resolve() == keyboard._OSK_BIN_SQUEEKBOARD

    def test_arrancar_o_candidato_novo_faz_devolver_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida na direção contrária: um `_osk_candidatos()` que NÃO
        conhece squeekboard (o comportamento antes de T-11) devolve False
        mesmo com o binário instalado."""
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        monkeypatch.setattr(
            keyboard, "_osk_candidatos", lambda: (keyboard._OSK_BIN_WAYLAND, keyboard._OSK_BIN_X11)
        )
        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.setattr(
            keyboard.shutil,
            "which",
            lambda n: "/usr/bin/squeekboard" if n == keyboard._OSK_BIN_SQUEEKBOARD else None,
        )
        assert keyboard.osk_disponivel_no_sistema() is False

    def test_path_vazio_fica_indisponivel_nos_dois_mundos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(keyboard.shutil, "which", lambda _n: None)
        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
        assert keyboard.osk_disponivel_no_sistema() is False
        keyboard._OSK_SONDA[0] = (float("-inf"), False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        assert keyboard.osk_disponivel_no_sistema() is False


# ---------------------------------------------------------------------------
# T-12 — osk_disponivel ganha o primeiro leitor, num arquivo próprio
# ---------------------------------------------------------------------------


class TestDescreverTecladoNaTela:
    def test_ausente_do_payload_e_terceiro_estado(self) -> None:
        assert "não consegui ler" in ambiente_na_tela.descrever_teclado_na_tela({})

    def test_state_nao_e_dict_e_terceiro_estado(self) -> None:
        assert "não consegui ler" in ambiente_na_tela.descrever_teclado_na_tela(None)

    def test_disponivel_true(self) -> None:
        texto = ambiente_na_tela.descrever_teclado_na_tela({"osk_disponivel": True})
        assert "instalado" in texto

    def test_disponivel_false(self) -> None:
        texto = ambiente_na_tela.descrever_teclado_na_tela({"osk_disponivel": False})
        assert "nenhum programa" in texto.lower()

    def test_nenhuma_frase_menciona_transporte(self) -> None:
        """Regra de §7 da sprint: nada de cabo/rádio/Bluetooth/sem fio."""
        proibidas = ("cabo", "rádio", "radio", "bluetooth", "sem fio")
        for payload in ({}, {"osk_disponivel": True}, {"osk_disponivel": False}):
            texto = ambiente_na_tela.descrever_teclado_na_tela(payload).lower()
            for termo in proibidas:
                assert termo not in texto, f"{termo!r} vazou para {texto!r}"


class TestOQueEstaFraseNaoAlcancaNoStateFullDeVerdade:
    """MEDIDO em 26/08/2026 (LEVA-3-D): esta frase NÃO pode ser pendurada.

    A ordem da frente era pendurar `descrever_teclado_na_tela` na legenda do L3
    — o gancho que a lápide do `portao_a_casa_sabe_e_o_produto_nao_faz` nomeia.
    A medição derrubou a ordem, por DUAS razões independentes, e as duas estão
    travadas aqui para que a próxima pessoa não pague o mesmo caminho:

    1. **A frase lê a chave no NÍVEL ERRADO.** O daemon publica
       `osk_disponivel` DENTRO do bloco `keyboard_emulation`
       (`_keyboard_emulation_payload`), e esta função a procura no TOPO do
       `state`. Contra os dois `state_full` reais desta bancada — capturados
       com a máquina TENDO teclado na tela (`keyboard_emulation.osk_disponivel
       == True`) — ela responde *"não consegui ler — o Hefesto pode estar
       desligado"*. Pendurá-la seria pôr uma frase FALSA na tela dela;
    2. **o defeito que ela existia para curar já fechou, por outro caminho.**
       Em 25/08 (`e909b62`, N12) `mouse_actions._anotar_teclado_na_tela` passou
       a ler a chave do lugar certo e `input_actions.frase_do_teclado_na_tela`
       a transformar na frase da legenda do L3 — no gancho exato que a lápide
       nomeia. Pendurar esta função ao lado daquela poria DUAS frases sobre o
       mesmo fato na mesma legenda, uma delas errada.

    Este teste MORDE nos dois sentidos: se alguém consertar o nível da chave
    sem decidir o que fazer com a duplicata, ele reprova e obriga a decisão.
    """

    #: O `state_full` como o daemon o publica: a chave mora DENTRO do bloco.
    #: Não é dublê de conveniência — é a forma que
    #: `tests/fixtures/state_full_quatro_controles.json` traz, e a que
    #: `mouse_actions._anotar_teclado_na_tela` lê.
    PAYLOAD_REAL: ClassVar[dict[str, dict[str, bool]]] = {
        "keyboard_emulation": {"osk_disponivel": True}
    }

    def test_a_chave_nao_mora_no_topo_do_state_full(self) -> None:
        """A prova de que o payload acima é o de verdade, e não invenção minha."""
        import json
        from pathlib import Path

        fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "state_full_quatro_controles.json"
        )
        state = json.loads(fixture.read_text(encoding="utf-8"))
        assert "osk_disponivel" not in state, (
            "o daemon passou a publicar `osk_disponivel` no TOPO do state_full "
            "— se isso é verdade, `descrever_teclado_na_tela` finalmente "
            "alcança a chave e a decisão da duplicata (ver o docstring desta "
            "classe) tem de ser tomada"
        )
        assert state["keyboard_emulation"]["osk_disponivel"] is True

    def test_contra_o_payload_real_a_frase_diz_que_nao_conseguiu_ler(self) -> None:
        """A MORDIDA: a máquina TEM teclado na tela e a frase não vê.

        Consertado o nível da chave, este teste reprova — e é para reprovar:
        ele é o lembrete de que a frase corrigida vira a SEGUNDA frase sobre o
        mesmo fato na legenda do L3, e de que a casa não deixa duas versões
        vivas do mesmo fato.
        """
        texto = ambiente_na_tela.descrever_teclado_na_tela(self.PAYLOAD_REAL)
        assert "não consegui ler" in texto, (
            "`descrever_teclado_na_tela` passou a alcançar "
            "`keyboard_emulation.osk_disponivel`. Ela agora DIZ a verdade — e "
            "por isso passa a competir com "
            "`input_actions.frase_do_teclado_na_tela`, que ocupa o mesmo "
            "gancho desde 25/08. ESCOLHA uma das duas e apague a outra; a "
            f"frase de hoje é {texto!r}"
        )

    def test_o_gancho_do_l3_ja_tem_dono_e_nao_e_esta_funcao(self) -> None:
        """Quem fala do teclado na tela na legenda do L3 é a frente da Navegação."""
        from hefesto_dualsense4unix.app.actions import input_actions

        assert input_actions.frase_do_teclado_na_tela(True), (
            "a frase viva da legenda do L3 sumiu — se ela saiu de propósito, "
            "o gancho ficou vago e `descrever_teclado_na_tela` volta a ser "
            "candidata (depois de consertado o nível da chave)"
        )


class TestDescreverDisplayGrafico:
    def test_ausente_do_payload_e_terceiro_estado(self) -> None:
        assert "não consegui ler" in ambiente_na_tela.descrever_display_grafico({})

    def test_backend_nulo_e_nada_disponivel(self) -> None:
        texto = ambiente_na_tela.descrever_display_grafico(
            {"window_detect_backend": None}
        )
        assert "nenhum caminho" in texto.lower()

    def test_vendo_e_enxergando(self) -> None:
        texto = ambiente_na_tela.descrever_display_grafico(
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": True,
                "window_detect_reason": None,
            }
        )
        assert "enxergando" in texto.lower()

    def test_nao_vendo_cita_o_motivo(self) -> None:
        texto = ambiente_na_tela.descrever_display_grafico(
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": False,
                "window_detect_reason": "sem_conexao_x",
            }
        )
        assert "sem_conexao_x" in texto

    def test_nenhuma_frase_menciona_transporte(self) -> None:
        proibidas = ("cabo", "rádio", "radio", "bluetooth", "sem fio")
        casos = (
            {},
            {"window_detect_backend": None},
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": True,
                "window_detect_reason": None,
            },
            {
                "window_detect_backend": "xlib",
                "window_detect_seeing": False,
                "window_detect_reason": "sem_conexao_x",
            },
        )
        for payload in casos:
            texto = ambiente_na_tela.descrever_display_grafico(payload).lower()
            for termo in proibidas:
                assert termo not in texto, f"{termo!r} vazou para {texto!r}"


class TestDescreverSteamEncontrada:
    def test_ausente_do_payload_e_terceiro_estado(self) -> None:
        assert "não consegui ler" in ambiente_na_tela.descrever_steam_encontrada({})

    def test_layout_achado(self) -> None:
        texto = ambiente_na_tela.descrever_steam_encontrada(
            {"steam_layout_achado": "flatpak"}
        )
        assert "encontrada" in texto.lower()
        assert "flatpak" in texto.lower()

    def test_layout_ausente_mas_chave_presente(self) -> None:
        texto = ambiente_na_tela.descrever_steam_encontrada(
            {"steam_layout_achado": None}
        )
        assert "não encontrada" in texto.lower()

    def test_nenhuma_frase_menciona_transporte(self) -> None:
        proibidas = ("cabo", "rádio", "radio", "bluetooth", "sem fio")
        for payload in ({}, {"steam_layout_achado": "flatpak"}, {"steam_layout_achado": None}):
            texto = ambiente_na_tela.descrever_steam_encontrada(payload).lower()
            for termo in proibidas:
                assert termo not in texto, f"{termo!r} vazou para {texto!r}"


def _leitores_de_osk(raiz_app: Path) -> list[Path]:
    """Os arquivos de `app/` que mencionam a chave. DONO ÚNICO da varredura.

    O portão e a mordida faziam a mesma busca escrita duas vezes — e foi por
    isso que elas puderam divergir sem ninguém notar. Ver a nota de 25/08 na
    mordida abaixo.
    """
    return sorted(
        p
        for p in raiz_app.rglob("*.py")
        if "osk_disponivel" in p.read_text(encoding="utf-8")
    )


class TestOPortaoDeCompletudeDoOskDisponivel:
    """T-12: `osk_disponivel` deixa de ser chave órfã (item 8 do aceite §9.2).

    Nasce reprovando contra a árvore de 23/08 (medido, §3.6 da sprint: `grep
    -rn osk_disponivel app/ gui/` devolvia vazio); T-12 o faz passar.
    """

    def test_ha_leitor_de_osk_disponivel_em_app(self, repo_root: Path) -> None:
        alvo = repo_root / "src" / "hefesto_dualsense4unix" / "app"
        achados = _leitores_de_osk(alvo)
        assert achados, (
            "nenhum arquivo em app/ lê 'osk_disponivel' -- a chave publicada "
            "em daemon/ipc_handlers.py:2091 continua órfã (F2)"
        )
        assert any(p.name == "ambiente_na_tela.py" for p in achados)

    def test_arrancar_o_leitor_reprova_nomeando_a_chave(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        """A MORDIDA: sem leitor nenhum em `app/`, o portão acima reprova.

        NOTA DATADA (25/08/2026) — POR QUE ESTA MORDIDA MUDOU DE FORMA. Ela
        apagava UM arquivo (`actions/ambiente_na_tela.py`) e exigia que a
        varredura voltasse a VAZIO. Isso fossilizava uma premissa que era
        verdade em 24/08 e deixou de ser: *"`ambiente_na_tela.py` é o único
        leitor de `osk_disponivel` em `app/`"*.

        O que mudou, e é o CONTRÁRIO de uma regressão: em 25/08 a frente da
        Navegação (`e909b62`, TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01/N12) deu
        mais dois leitores à chave — `actions/mouse_actions.py`, que a lê do
        `state_full` vivo, e `actions/input_actions.py`, que a transforma na
        frase da legenda. A chave ficou MENOS órfã, e a mordida reprovava
        justamente por isso. Um teste que reprova quando o defeito é curado
        duas vezes não estava medindo o defeito.

        **A cura é no TESTE, e ela não afrouxa nada** — ao contrário: a régua
        antiga só falsificava a PRIMEIRA asserção do portão, e por um caminho
        que dependia de contar leitores. Esta falsifica as DUAS, sem
        depender de quantos leitores existam hoje:

        1. sem `ambiente_na_tela.py`, a segunda asserção do portão (a que
           nomeia o dono da frase) cai;
        2. com a chave arrancada de TODOS os leitores, a primeira cai.
        """
        import shutil as _shutil

        alvo = repo_root / "src" / "hefesto_dualsense4unix" / "app"
        copia = tmp_path / "app_sem_leitor_de_osk"
        _shutil.copytree(alvo, copia)

        # (1) o dono da frase sai: a asserção que o NOMEIA deixa de valer.
        (copia / "actions" / "ambiente_na_tela.py").unlink()
        sobraram = _leitores_de_osk(copia)
        assert not any(p.name == "ambiente_na_tela.py" for p in sobraram), (
            "a mordida não conseguiu arrancar o dono da frase -- "
            "`actions/ambiente_na_tela.py` mudou de lugar?"
        )

        # (2) e agora TODOS os outros: a asserção de existência cai também.
        for arquivo in sobraram:
            arquivo.write_text(
                arquivo.read_text(encoding="utf-8").replace(
                    "osk_disponivel", "chave_arrancada_pela_mordida"
                ),
                encoding="utf-8",
            )
        assert _leitores_de_osk(copia) == [], (
            "a mordida não reprovou -- sobrou leitor de 'osk_disponivel' em "
            "app/ depois de arrancar todos os que a varredura achou: "
            f"{[str(p.relative_to(copia)) for p in _leitores_de_osk(copia)]}"
        )


# ---------------------------------------------------------------------------
# T-13 — o systemd de usuário deixa de ser presumido
# ---------------------------------------------------------------------------


class TestUserUnitDirNaoCriaMaisNada:
    def test_so_responde_o_caminho(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA central: `user_unit_dir()` num `XDG_CONFIG_HOME` dublê
        NÃO cria nada."""
        from hefesto_dualsense4unix.daemon import service_install as si

        xdg = tmp_path / "config-novo"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert not xdg.exists()

        caminho = si.user_unit_dir()

        assert caminho == xdg / "systemd" / "user"
        assert not xdg.exists(), "user_unit_dir() criou o XDG_CONFIG_HOME sozinho"
        assert not caminho.exists(), "user_unit_dir() criou a pasta como efeito colateral"

    def test_install_e_quem_cria(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon import service_install as si

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setattr(si.ServiceInstaller, "_systemctl", lambda self, *a, **k: None)
        installer = si.ServiceInstaller()
        dst = installer.install()
        assert dst.exists()
        assert dst.parent.is_dir()


class TestStatusTextSemSystemd:
    @staticmethod
    def _plantar_unit_instalada(tmp_path: Path) -> None:
        """Unit COPIADA (arquivo existe) — para `detect_installed_unit()` não
        ser o motivo do atalho e o teste medir de verdade a conferência de
        `status_text` sobre `systemctl`, não o ramo "nem instalei"."""
        unit_dir = tmp_path / "config" / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        (unit_dir / "hefesto-dualsense4unix.service").write_text("stub")

    def test_systemctl_ausente_do_path_nao_propaga_excecao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA de T-13: `PATH` dublê sem `systemctl` -> `status_text()`
        contém o caminho sem systemd e NÃO contém a palavra 'systemctl' crua
        — mesmo com a unit JÁ instalada (senão o teste mediria só o atalho de
        'não instalei', que existia antes de T-13 e não prova nada novo)."""
        from hefesto_dualsense4unix.daemon import service_install as si

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        self._plantar_unit_instalada(tmp_path)
        monkeypatch.setattr(si.shutil, "which", lambda _n: None)
        installer = si.ServiceInstaller()

        texto = installer.status_text()

        assert "systemctl" not in texto
        assert "foreground" in texto

    def test_sem_instancia_de_usuario_tambem_cai_na_mensagem_amigavel(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`systemctl` existe no PATH mas não responde (stdout vazio, bus
        indisponível) -- mesmo tratamento do binário ausente, com a unit
        instalada pela mesma razão do teste acima."""
        from hefesto_dualsense4unix.daemon import service_install as si

        class _Vazio:
            stdout = ""
            stderr = "Failed to connect to bus: No such file or directory"
            returncode = 1

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        self._plantar_unit_instalada(tmp_path)
        monkeypatch.setattr(si.shutil, "which", lambda _n: "/usr/bin/systemctl")
        monkeypatch.setattr(si.subprocess, "run", lambda *a, **k: _Vazio())
        installer = si.ServiceInstaller()

        texto = installer.status_text()

        assert "Failed to connect to bus" not in texto
        assert "foreground" in texto

    def test_o_systemctl_por_baixo_ainda_sabe_explodir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida na direção contrária: chamar `_systemctl` DIRETO (sem
        passar por `status_text`, que agora tem a conferência na frente)
        ainda propaga `RuntimeError` quando o binário some do PATH de
        verdade — é exatamente o defeito que a conferência de `status_text`
        existe para o usuário nunca ver."""
        from hefesto_dualsense4unix.daemon import service_install as si

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("PATH", str(tmp_path / "path-vazio-sem-systemctl"))
        (tmp_path / "path-vazio-sem-systemctl").mkdir()
        installer = si.ServiceInstaller()

        with pytest.raises(RuntimeError, match="systemctl não encontrado"):
            installer._systemctl("status", si.SERVICE_NORMAL, capture=True, check=False)

        # E é justamente esse caminho que `status_text()` agora NUNCA percorre:
        assert "systemctl" not in installer.status_text()
