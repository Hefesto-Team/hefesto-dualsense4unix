"""A3 (23/08/2026) — o "Aplicar" responde sobre o que foi declarado.

O DEFEITO, medido: quem declarava algo na aba Configurações e clicava
"Aplicar" nunca sabia o que tinha acontecido. `_gravar_declaracao_de_maquina`
empurrava a frase na statusbar e, na MESMA iteração do GTK, o
`_apply_draft_agora` empurrava o resultado da aplicação — e `_status_toast` faz
`pop`+`push` no contexto "footer". A frase da declaração era apagada antes de
receber um único quadro de tela; o que sobrava era "Perfil aplicado ao
controle." sobre um perfil que a pessoa não tocou.

POR QUE ESTE ARQUIVO USA UMA `Gtk.Statusbar` DE VERDADE, e é o ponto:
o `_FooterStub` de `test_aplicar_verdade_rodape.py` sobrescreve `_status_toast`
por uma lista que só CRESCE. Contra ele o defeito é invisível — as duas frases
estão lá. É por isso que ele passou por cima deste defeito, e é por isso que
aqui a barra é real e a afirmação é sobre o texto FINAL do rótulo.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a3 o aplicar responde no rodape")

from typing import Any

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig


FRASE_DAEMON_DESLIGADO = "não gravei o que você declarou"
FRASE_GRAVOU = "Configurações gravadas."
DECLARACAO = {"orcamento": {"teto": "equilibrado"}}


class _Rodape(FooterActionsMixin):
    """O rodapé com uma `Gtk.Statusbar` REAL — sem `_status_toast` de mentira."""

    def __init__(self) -> None:
        self.draft = DraftConfig.default()
        self.barra = Gtk.Statusbar()
        self._maquina_pendente: dict[str, Any] | None = dict(DECLARACAO)

    def _get(self, widget_id: str) -> Any:
        return self.barra if widget_id == "status_bar" else None

    def pegar_carona_no_gesto(self, _gesto: str) -> None:
        pass

    @property
    def texto_da_barra(self) -> str:
        rotulo = self.barra.get_message_area().get_children()[0]
        return str(rotulo.get_text())


def _rodar(
    monkeypatch: pytest.MonkeyPatch,
    *,
    declarou: tuple[bool, str | None],
    resultado: Any = None,
    erro: Exception | None = None,
) -> _Rodape:
    """Um clique no "Aplicar" inteiro, com o daemon respondendo o combinado."""
    rodape = _Rodape()
    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "machine_declare",
        lambda _payload: declarou,
    )

    def _fake_async(
        _method: str,
        _params: Any,
        on_success: Any = None,
        on_failure: Any = None,
        **_kw: Any,
    ) -> None:
        if erro is not None:
            on_failure(erro)
        else:
            on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _fake_async)
    rodape.on_apply_draft()
    return rodape


class TestARespostaChegaNaTela:
    def test_daemon_desligado_a_frase_sobrevive_ao_toast_da_aplicacao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE: era exatamente esta frase que sumia no mesmo tique."""
        rodape = _rodar(
            monkeypatch,
            declarou=(False, None),
            resultado={"status": "ok", "applied": ["leds"]},
        )
        assert FRASE_DAEMON_DESLIGADO in rodape.texto_da_barra, (
            "a statusbar guarda UMA mensagem por contexto: a declaração tem de "
            f"viajar junto com o resultado, e o rótulo diz {rodape.texto_da_barra!r}"
        )
        assert rodape._maquina_pendente == DECLARACAO, (
            "recusa não pode perder o que ela declarou"
        )

    def test_motivo_do_daemon_vence_a_frase_de_fabrica(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rodape = _rodar(
            monkeypatch,
            declarou=(False, "teto inválido"),
            resultado={"status": "ok", "applied": ["leds"]},
        )
        assert "teto inválido" in rodape.texto_da_barra

    def test_sucesso_o_rodape_diz_que_gravou(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rodape = _rodar(
            monkeypatch,
            declarou=(True, None),
            resultado={"status": "ok", "applied": ["leds"]},
        )
        assert FRASE_GRAVOU in rodape.texto_da_barra
        assert "aplicado" in rodape.texto_da_barra, (
            "a frase da declaração não pode COMER o resultado da aplicação"
        )
        assert rodape._maquina_pendente is None

    def test_erro_de_aplicacao_tambem_carrega_o_recado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O outro final do `_apply_draft_agora` — o `_on_err`."""
        rodape = _rodar(
            monkeypatch,
            declarou=(False, None),
            erro=RuntimeError("socket morto"),
        )
        texto = rodape.texto_da_barra
        assert FRASE_DAEMON_DESLIGADO in texto
        assert "socket morto" in texto

    def test_sem_declaracao_o_rodape_nao_inventa_frase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho feliz de quem nunca abriu a aba Configurações."""
        rodape = _Rodape()
        rodape._maquina_pendente = None
        monkeypatch.setattr(
            footer_actions.ipc_bridge,
            "machine_declare",
            lambda _p: pytest.fail("sem declaração não se manda IPC"),
        )
        monkeypatch.setattr(
            footer_actions.ipc_bridge,
            "call_async",
            lambda *_a, on_success=None, **_k: on_success({"status": "ok"}),
        )
        rodape.on_apply_draft()
        assert rodape.texto_da_barra.startswith("Perfil"), rodape.texto_da_barra

    def test_o_recado_nao_reaparece_no_aplicar_seguinte(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O recado é consumido: sem isso ele grudaria em todo clique."""
        rodape = _rodar(
            monkeypatch,
            declarou=(True, None),
            resultado={"status": "ok", "applied": ["leds"]},
        )
        rodape.on_apply_draft()
        assert FRASE_GRAVOU not in rodape.texto_da_barra


class TestAMarcaDeQueHaEscolhaPorAplicar:
    """A5, metade da tela: a mesma `_maquina_pendente` que o portão consulta."""

    def test_com_pendencia_a_marca_entra_na_linha(self) -> None:
        rodape = _Rodape()
        rodape._marcar_declaracao_por_aplicar()
        assert "por aplicar" in rodape.texto_da_barra

    def test_sem_pendencia_a_marca_nao_apaga_o_que_estava_escrito(self) -> None:
        rodape = _Rodape()
        rodape._maquina_pendente = None
        rodape._footer_toast("Perfil aplicado ao controle.")
        rodape._marcar_declaracao_por_aplicar()
        assert rodape.texto_da_barra == "Perfil aplicado ao controle."
