"""O-DESLIGADO-DE-ONTEM-01 — o produto inerte por uma decisão de ontem, em silêncio."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_desligado_de_ontem_01: importa código da janela GTK")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import aviso_de_opt_out_antigo

_INERTE: dict[str, Any] = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": False},
}


def test_o_caso_dela_ganha_o_aviso() -> None:
    """A cura. Morde ao fazer a função devolver `None` sempre."""
    texto = aviso_de_opt_out_antigo(_INERTE, opt_out=True, conectados=1)
    assert texto is not None
    assert "sessão anterior" in texto, "tem de dizer que a decisão é ANTIGA"
    assert "giroscópio" in texto, "tem de nomear o que para de funcionar"
    assert "Jogar pelo Hefesto" in texto and "Conexão Nativa" in texto, (
        "aviso sem saída é beco: as duas saídas são os rótulos da própria aba"
    )


def test_a_frase_nao_chama_a_escolha_dela_de_erro() -> None:
    """Ela desligou de propósito, e isso é um direito, não um defeito."""
    texto = (aviso_de_opt_out_antigo(_INERTE, opt_out=True, conectados=1) or "").lower()
    for proibido in ("erro", "errado", "problema", "falha", "incorreto", "esqueceu"):
        assert proibido not in texto


@pytest.mark.parametrize(
    ("estado", "opt_out", "conectados", "porque"),
    [
        (_INERTE, False, 1, "sem opt-out não há decisão antiga a explicar"),
        (
            {"native_mode": False, "gamepad_emulation": {"enabled": True}},
            True,
            1,
            "a emulação está ligada agora — o gesto novo já venceu",
        ),
        (
            {"native_mode": True, "gamepad_emulation": {"enabled": False}},
            True,
            1,
            "Conexão Nativa é escolha ATUAL dela, e ali o jogo fala direto",
        ),
        (_INERTE, True, 0, "sem controle na mesa não há nada a atravessar"),
        (None, True, 1, "sem daemon a aba já diz que está desligado"),
    ],
)
def test_o_aviso_cala_quando_nao_ha_o_que_dizer(
    estado: Any, opt_out: bool, conectados: int, porque: str
) -> None:
    """Cinco silêncios, cada um com a razão."""
    assert aviso_de_opt_out_antigo(estado, opt_out=opt_out, conectados=conectados) is None, porque


def test_o_aviso_some_no_instante_em_que_ela_troca_de_modo() -> None:
    """É aviso de ESTADO, não pedido repetido."""
    ligado = {"native_mode": False, "gamepad_emulation": {"enabled": True}}
    assert aviso_de_opt_out_antigo(ligado, opt_out=True, conectados=1) is None


def test_estado_sem_a_chave_do_gamepad_ainda_avisa() -> None:
    """Daemon antigo, ou payload sem a seção: a ausência não é "ligado"."""
    assert aviso_de_opt_out_antigo({"native_mode": False}, opt_out=True, conectados=1)
