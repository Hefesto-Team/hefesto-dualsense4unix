"""PONTE-NA-TELA-01 — a aba Início não pode esconder a divergência nem a ponte.

Os dois defeitos de tela medidos na noite de 18→19/08/2026, com DON'T SCREAM
aberto:

1. ela escolheu "Xbox 360" em "O jogo vê o controle como:", e a janela seguiu
   dizendo que estava tudo certo enquanto o aparelho continuava DualSense — o
   gate R-04 do daemon havia RECUSADO a troca. O rodapé chegou a anunciar
   desfecho de sucesso sobre a recusa, porque `set_gamepad_emulation` devolve o
   mesmo ``True`` para "apliquei", "já estava" e "recusei";
2. a janela não dizia por ONDE o jogo recebia o controle. Sob a exceção de
   Steam Input o vpad é suspenso, ``gamepad_emulation.enabled`` cai para False e
   `mode_of_state` chama isso de "Controlar o PC" — a aba mostrava modo desktop
   com o jogo jogando pelo espelho da Steam.

Tudo hermético: as funções puras não tocam GTK, e os testes de render usam o
mesmo dublê de widget do `test_home_render_state`.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_ponte_e_divergencia: importa código da janela GTK")

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        if name not in self.classes:
            self.classes.append(name)

    def remove_class(self, name: str) -> None:
        if name in self.classes:
            self.classes.remove(name)


class _FakeWidget:
    def __init__(self, label: str | None = None, **_kwargs: object) -> None:
        self.label = label
        self.markup: str | None = None
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()
        self.sensitive = True
        self.visible = True
        self.active_id: str | None = None

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, _value: float) -> None:
        pass

    def set_margin_end(self, _value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.markup = markup
        self.label = markup

    def set_text(self, text: str) -> None:
        self.label = text

    def set_label(self, text: str) -> None:
        self.label = text

    def get_label(self) -> str:
        return str(self.label or "")

    def get_text(self) -> str:
        return str(self.label or "")

    def set_sensitive(self, value: bool) -> None:
        self.sensitive = value

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_no_show_all(self, _value: bool) -> None:
        pass

    def set_active(self, _value: bool) -> None:
        pass

    def set_active_id(self, value: str) -> None:
        self.active_id = value

    def pack_start(self, child: _FakeWidget, *_args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


_UM_CONTROLE: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
}


def _estado(
    *,
    flavor: str = "dualsense",
    enabled: bool = True,
    jogo_aberto: bool = False,
    mesa: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    estado: dict[str, Any] = {
        "gamepad_emulation": {"enabled": enabled, "flavor": flavor},
        "native_mode": False,
        "controllers": [dict(_UM_CONTROLE)] if mesa is None else mesa,
    }
    if jogo_aberto:
        estado["game_signal"] = {"authority": "game"}
    estado.update(extra)
    return estado


class TestTextoDaDivergencia:
    def test_com_jogo_aberto_diz_as_duas_mascaras_e_o_caminho(self) -> None:
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=True
        )

        assert frase is not None
        assert "Xbox 360" in frase
        assert "DualSense (botões PlayStation)" in frase
        assert "abrir de novo" in frase

    def test_sem_jogo_aberto_a_frase_e_outra(self) -> None:
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=False
        )

        assert frase is not None
        assert "não chegou ao aparelho" in frase

    def test_a_cor_vem_por_markup_e_nao_por_classe_de_css(self) -> None:
        """A armadilha que a foto offscreen pegou nesta leva."""
        frase = home_actions.texto_da_divergencia(
            "xbox", "dualsense", jogo_aberto=True
        )

        assert frase is not None
        assert '<span foreground="#ffb86c">' in frase

    def test_iguais_nao_e_divergencia(self) -> None:
        assert (
            home_actions.texto_da_divergencia("xbox", "xbox", jogo_aberto=True)
            is None
        )

    @pytest.mark.parametrize(
        ("escolhida", "no_aparelho"),
        [(None, "xbox"), ("xbox", None), ("", "xbox"), ("xbox", "")],
    )
    def test_meia_informacao_nunca_acusa(
        self, escolhida: object, no_aparelho: object
    ) -> None:
        """Sem as duas pontas não há divergência a afirmar (nada de alarme falso)."""
        assert (
            home_actions.texto_da_divergencia(
                escolhida, no_aparelho, jogo_aberto=True
            )
            is None
        )


class TestMascaraDoAparelho:
    def test_backend_uhid_significa_dualsense_vivo(self) -> None:
        """`virtual_pad._try_uhid` recusa o uhid para Xbox — uhid é DualSense."""
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["backend"] = "uhid"

        assert home_actions.mascara_viva(estado) == "dualsense"
        assert home_actions.mascara_do_aparelho(estado) == "dualsense"

    def test_backend_uinput_e_ambiguo_e_cai_no_flavor_do_payload(self) -> None:
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["backend"] = "uinput"

        assert home_actions.mascara_viva(estado) is None
        assert home_actions.mascara_do_aparelho(estado) == "xbox"

    def test_campo_explicito_do_daemon_vence(self) -> None:
        estado = _estado(flavor="xbox")
        estado["gamepad_emulation"]["flavor_vivo"] = "dualsense"

        assert home_actions.mascara_do_aparelho(estado) == "dualsense"


class TestTextoDaPonte:
    def test_a_excecao_de_steam_input_nao_produz_frase_propria(self) -> None:
        """NOTA DATADA — 25/08/2026 (INÍCIO NÃO MENTE-01, I6, ramo 2)."""
        estado = _estado(
            enabled=False,
            steam_input={"excecao_ativa": True, "vpad_suspenso": True},
        )

        frase = home_actions.texto_da_ponte(estado)

        assert "Steam Input" not in frase
        assert "nenhuma" in frase

    def test_nativo(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(native_mode=True))

        assert "direto (Sony)" in frase

    def test_gamepad_diz_a_mascara_que_o_jogo_ve(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(flavor="xbox"))

        assert "pelo Hefesto" in frase
        assert "Xbox 360" in frase

    def test_desktop_diz_nenhuma_e_aponta_o_botao(self) -> None:
        frase = home_actions.texto_da_ponte(_estado(enabled=False))

        assert "nenhuma" in frase
        assert "Jogar pelo Hefesto" in frase

    def test_offline_nao_sabe(self) -> None:
        frase = home_actions.texto_da_ponte(None)

        assert "não sei" in frase
        assert "desligado" in frase

    def test_todas_as_frases_tem_o_prefixo(self) -> None:
        for estado in (
            None,
            _estado(),
            _estado(enabled=False),
            _estado(native_mode=True),
            _estado(
                enabled=False,
                steam_input={"excecao_ativa": True, "vpad_suspenso": True},
            ),
        ):
            assert home_actions.texto_da_ponte(estado).startswith(
                home_actions.PONTE_PREFIXO
            )


