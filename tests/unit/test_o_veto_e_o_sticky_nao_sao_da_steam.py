"""LANCADOR-AGNOSTICO-01 — o veto e o sticky param de ser da Steam."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

NOSSA = "Hefesto-Dualsense4Unix"


class TestOStickyNaoGuardaANossaJanela:
    """**A METADE QUE MORA ONDE O VALOR NASCE.**"""

    def test_a_nossa_classe_nao_derruba_a_anterior(self):
        """MORDIDA: devolva `self._window_detect_last_class = wm_class` para"""
        store = StateStore()
        store.record_window_detect_read("xlib", "steam_app_1088850")
        store.record_window_detect_read("xlib", NOSSA)
        assert store.window_detect_last_class == "steam_app_1088850", (
            "a nossa própria janela virou o sticky — é ela que o «Detectar» "
            "grava quando ela clica no botão")

    def test_a_leitura_crua_continua_dizendo_a_verdade(self):
        """O sticky filtra; a leitura CRUA não pode filtrar."""
        store = StateStore()
        store.record_window_detect_read("xlib", NOSSA)
        assert store.window_detect_current_class == NOSSA

    def test_olhar_para_nos_nao_declara_o_detector_cego(self):
        """**A ASSIMETRIA É O CUIDADO DESTA CURA.**"""
        store = StateStore()
        store.record_window_detect_read("xlib", NOSSA, now=100.0)
        assert store.window_detect_seeing(now=101.0) is True
        assert store.window_detect_useful_age(now=101.0) == pytest.approx(1.0)

    def test_a_saude_sobe_com_a_nossa_janela(self):
        """Ler a nossa janela É uma leitura boa: o backend está de pé."""
        store = StateStore()
        store.record_window_detect_read("xlib", NOSSA)
        assert store.window_detect_healthy is True

    def test_as_classes_cegas_continuam_fora(self):
        """O que já não entrava continua não entrando."""
        store = StateStore()
        store.record_window_detect_read("xlib", "unknown")
        store.record_window_detect_read("xlib", "")
        store.record_window_detect_read("xlib", None)
        assert store.window_detect_last_class is None

    def test_a_lista_da_nossa_janela_nao_e_digitada_aqui(self):
        """A régua consulta o MESMO dono que o produto (`OWN_GUI_WM_CLASSES`)."""
        assert NOSSA.casefold() in OWN_GUI_WM_CLASSES


class TestODetectarNaoGravaANossaPropriaJanela:
    """**A OUTRA METADE, no gesto — e sem ela a primeira não fecha.**"""

    def _ctx(self, **estado):
        from types import SimpleNamespace

        return SimpleNamespace(state=dict(estado))

    def test_o_recuo_pula_a_nossa_janela(self):
        from hefesto_dualsense4unix.interface.pacotes.a10_perfis import (
            _classe_de_outro_app,
        )

        ctx = self._ctx(window_detect_last_class=None,
                        window_detect_current_class=NOSSA)
        assert _classe_de_outro_app(ctx) == "", (
            "o «Detectar» gravaria a regra da janela do próprio Hefesto")

    def test_o_sticky_de_outro_app_vence_a_nossa_crua(self):
        """É o caso do clique do usuário: o foco está aqui, o jogo está atrás."""
        from hefesto_dualsense4unix.interface.pacotes.a10_perfis import (
            _classe_de_outro_app,
        )

        ctx = self._ctx(window_detect_last_class="steam_app_1088850",
                        window_detect_current_class=NOSSA)
        assert _classe_de_outro_app(ctx) == "steam_app_1088850"

    def test_a_crua_serve_quando_e_de_outro_app(self):
        from hefesto_dualsense4unix.interface.pacotes.a10_perfis import (
            _classe_de_outro_app,
        )

        ctx = self._ctx(window_detect_last_class=None,
                        window_detect_current_class="firefox")
        assert _classe_de_outro_app(ctx) == "firefox"

    def test_a_recusa_diz_o_que_esta_vendo(self):
        """*"Não achei janela"* sobre uma tela cheia de janelas se lê como"""
        fonte = Path(
            "src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py"
        ).read_text(encoding="utf-8")
        i = fonte.index("def detectar(")
        corpo = fonte[i : fonte.index("\n@gesto", i)]
        assert "estou vendo" in corpo, (
            "a recusa não nomeia a classe que o detector está vendo")


class TestOVetoDaR21AlcancaQualquerLancador:
    """**O NOME DIZIA A PERGUNTA CERTA E O CORPO RESPONDIA OUTRA.**"""

    def test_o_predicado_e_o_dono_da_pergunta(self):
        """MORDIDA: devolva o predicado da Steam. Esta régua reprova."""
        fonte = Path(
            "src/hefesto_dualsense4unix/profiles/manager.py"
        ).read_text(encoding="utf-8")
        assert "e_janela_de_jogo = e_endereco_de_jogo(wm_class)" in fonte
        assert (
            "e_janela_de_jogo = steam_appid_from_wm_class(wm_class) is not None"
            not in fonte
        )

    def test_a_classe_do_lancador_passa_a_ser_jogo(self):
        """O elo inteiro: o censo declara, o esquema sabe, o veto usa."""
        from hefesto_dualsense4unix.profiles.schema import (
            e_endereco_de_jogo,
            registrar_classes_de_jogo,
        )

        try:
            assert e_endereco_de_jogo("jogo-nativo-do-heroic") is False
            registrar_classes_de_jogo(["jogo-nativo-do-heroic"])
            assert e_endereco_de_jogo("jogo-nativo-do-heroic") is True
            assert e_endereco_de_jogo("steam_app_1088850") is True
        finally:
            registrar_classes_de_jogo([])


class TestOLutrisGanhaODegrauDoAppid:
    """**O `pga.db` DO USUÁRIO TEM ZERO JOGOS** — e é por isso que o que entra aqui"""

    def _banco(self, tmp_path: Path, linhas):
        banco = tmp_path / "pga.db"
        con = sqlite3.connect(banco)
        con.execute(
            "CREATE TABLE games (name TEXT, sortname TEXT, slug TEXT, "
            "installer_slug TEXT, parent_slug TEXT, platform TEXT, "
            "runner TEXT, executable TEXT, directory TEXT, installed INTEGER, "
            "service TEXT, service_id TEXT)")
        for linha in linhas:
            con.execute(
                "INSERT INTO games (name, slug, runner, executable, directory,"
                " installed, service, service_id) VALUES (?,?,?,?,?,?,?,?)",
                linha)
        con.commit()
        con.close()
        return banco

    def test_o_servico_da_steam_vira_a_classe_da_janela(self, tmp_path):
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            _lutris,
        )

        self._banco(tmp_path, [
            ("Stray", "stray", "wine", "stray.exe", "/jogos/stray", 1,
             "steam", "1332010"),
        ])
        jogo = _lutris(tmp_path).jogos[0]
        assert jogo.appid_da_steam == "1332010"
        assert jogo.classe_de_janela == "steam_app_1332010"

    def test_o_id_da_gog_nao_vira_chave_de_janela(self, tmp_path):
        """**O CASO QUE IMPEDE A CURA DE PASSAR DO PONTO.**"""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            _lutris,
        )

        self._banco(tmp_path, [
            ("Bloodlines", "bloodlines", "wine", "vamp.exe", "/j/v", 1,
             "gog", "1207659240"),
        ])
        jogo = _lutris(tmp_path).jogos[0]
        assert jogo.appid_da_steam == ""
        assert jogo.classe_de_janela == "", (
            "um id da GOG virou chave de janela — ela nunca vai casar")

    def test_o_exe_sem_servico_continua_dizendo_nao_sei(self, tmp_path):
        """O «não sei» é entrega: quem não tem chave tem o «Detectar»."""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            _lutris,
        )

        self._banco(tmp_path, [
            ("Um jogo", "um-jogo", "wine", "jogo.exe", "/j", 1, "", ""),
        ])
        assert _lutris(tmp_path).jogos[0].classe_de_janela == ""

    def test_o_nativo_linux_continua_caindo_no_basename(self, tmp_path):
        """O degrau 3 não foi tocado por esta cura."""
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
            _lutris,
        )

        self._banco(tmp_path, [
            ("Nativo", "nativo", "linux", "/opt/nativo/nativo", "/opt", 1,
             "", ""),
        ])
        assert _lutris(tmp_path).jogos[0].classe_de_janela == "nativo"
