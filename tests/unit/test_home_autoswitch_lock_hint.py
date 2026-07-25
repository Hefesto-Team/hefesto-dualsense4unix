"""UX-05 (auditoria 24/07) — o cadeado tinha EFEITO visível e CAUSA invisível.

`autoswitch_locked` só existia na GUI como o marcador de um checkbox
(`_render_home`, `set_active`). Na máquina dela a flag estava ligada desde
24/07 20:42 e o que ela via era outra coisa: "o modo jogo não ativa", "os
perfis não mudam". Ninguém relê uma caixinha de 16 px depois de marcá-la.

A frase é gerada por uma função PURA (mesmo desenho de `vpad_degradation_text`
e `wrapper_banner_text`) e diz as DUAS metades da política LOCK-CEDE-01 —
o que congelou e o que continua entrando —, porque as duas surpreendem quem só
vê o efeito.
"""
from __future__ import annotations

import inspect

from hefesto_dualsense4unix.app.actions.home_actions import (
    HomeActionsMixin,
    autoswitch_lock_text,
)


class TestDecisaoPura:
    def test_destravado_nao_diz_nada(self) -> None:
        assert autoswitch_lock_text({"autoswitch_locked": False}) == ""

    def test_campo_ausente_nao_diz_nada(self) -> None:
        assert autoswitch_lock_text({"connected": True}) == ""

    def test_offline_nao_diz_nada(self) -> None:
        # Offline não é "destravado", é "não sei" — e a aba apaga a frase.
        assert autoswitch_lock_text(None) == ""

    def test_travado_explica_a_causa(self) -> None:
        texto = autoswitch_lock_text({"autoswitch_locked": True})
        assert "não troca sozinho" in texto

    def test_travado_nomeia_o_perfil_que_ficou(self) -> None:
        """'o perfil não troca sozinho' sem dizer QUAL perfil é meia
        informação — é o perfil que ela precisa reconhecer na aba Perfis."""
        texto = autoswitch_lock_text(
            {"autoswitch_locked": True, "active_profile": "vitoria"}
        )
        assert "vitoria" in texto

    def test_travado_sem_perfil_ativo_nao_inventa_nome(self) -> None:
        texto = autoswitch_lock_text(
            {"autoswitch_locked": True, "active_profile": None}
        )
        assert "não troca sozinho" in texto
        assert "None" not in texto

    def test_diz_que_o_jogo_com_perfil_proprio_ainda_entra(self) -> None:
        """LOCK-CEDE-01: sem esta metade, "o modo jogo ligou sozinho mesmo com
        o cadeado" volta a ser um mistério sem causa visível."""
        texto = autoswitch_lock_text({"autoswitch_locked": True})
        assert "perfil próprio" in texto

    def test_payload_torto_nao_vira_frase(self) -> None:
        for torto in (0, "", [], {}):
            assert autoswitch_lock_text({"autoswitch_locked": torto}) == ""


class TestFiacaoNaAbaInicio:
    def test_render_home_consome_a_funcao_pura(self) -> None:
        src = inspect.getsource(HomeActionsMixin._render_home)
        assert "autoswitch_lock_text(state)" in src
        assert "_home_autoswitch_lock_hint" in src

    def test_offline_apaga_a_frase(self) -> None:
        """Estado morto nunca deixa uma afirmação viva na tela."""
        src = inspect.getsource(HomeActionsMixin._render_home)
        offline = src.split("assert state is not None", 1)[0]
        assert "_home_autoswitch_lock_hint" in offline

    def test_widget_nasce_invisivel_e_imune_ao_show_all(self) -> None:
        """Mesmo desenho dos banners de vpad/wrapper — sem `no_show_all` o
        `show_all()` do build desfaria o que o `_render_home` mandou."""
        src = inspect.getsource(HomeActionsMixin)
        bloco = src.split("lock_hint = Gtk.Label", 1)[1].split(
            "self._home_autoswitch_lock_hint", 1
        )[0]
        assert "set_no_show_all(True)" in bloco
        assert "set_visible(False)" in bloco


class TestEstadoDoDaemonCarregaOCampo:
    def test_state_full_e_status_expoem_autoswitch_locked(self) -> None:
        """A frase depende do campo chegar nos DOIS payloads que a GUI lê."""
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        for metodo in (
            IpcHandlersMixin._handle_daemon_status,
            IpcHandlersMixin._handle_daemon_state_full,
        ):
            src = inspect.getsource(metodo)
            assert '"autoswitch_locked"' in src, metodo.__name__
            assert '"active_profile"' in src, metodo.__name__
