"""Testes da ONDA0-Z7 · O AMBIENTE PRESUMIDO 01 — o que a máquina não tem (Z7-D).

Cobre T-11 (o teclado na tela conhece mais que dois programas), T-12
(`osk_disponivel` ganha o primeiro leitor, num arquivo próprio) e T-13 (o
systemd de usuário deixa de ser presumido).
"""
from __future__ import annotations

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


class TestOPortaoDeCompletudeDoOskDisponivel:
    """T-12: `osk_disponivel` deixa de ser chave órfã (item 8 do aceite §9.2).

    Nasce reprovando contra a árvore de 23/08 (medido, §3.6 da sprint: `grep
    -rn osk_disponivel app/ gui/` devolvia vazio); T-12 o faz passar.
    """

    def test_ha_leitor_de_osk_disponivel_em_app(self, repo_root: Path) -> None:
        alvo = repo_root / "src" / "hefesto_dualsense4unix" / "app"
        achados = [
            p
            for p in alvo.rglob("*.py")
            if "osk_disponivel" in p.read_text(encoding="utf-8")
        ]
        assert achados, (
            "nenhum arquivo em app/ lê 'osk_disponivel' -- a chave publicada "
            "em daemon/ipc_handlers.py:2009 continua órfã (F2)"
        )
        assert any(p.name == "ambiente_na_tela.py" for p in achados)

    def test_arrancar_o_leitor_reprova_nomeando_a_chave(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        """A MORDIDA: sem o arquivo (ou com a chave removida dele), a
        varredura volta a não achar leitor nenhum."""
        import shutil as _shutil

        alvo = repo_root / "src" / "hefesto_dualsense4unix" / "app"
        copia = tmp_path / "app_sem_ambiente_na_tela"
        _shutil.copytree(alvo, copia)
        (copia / "actions" / "ambiente_na_tela.py").unlink()

        achados = [
            p for p in copia.rglob("*.py") if "osk_disponivel" in p.read_text(encoding="utf-8")
        ]
        assert achados == [], (
            "a mordida não reprovou -- outro leitor de 'osk_disponivel' já "
            "existia em app/ antes de T-12, e a alegação de F2 estava errada"
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
