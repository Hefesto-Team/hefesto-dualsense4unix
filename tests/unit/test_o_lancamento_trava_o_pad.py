"""O pad que o lançamento deixa de pé é o que o jogo abre.

O R-04 só recusa recriar quando `display_authority == "game"`. Essa
autoridade chega segundos depois do `exec`, e não chega quando a janela não
tem classe. No vão, o perfil de fora do jogo reaplicava o caminho dele e o
jogo perdia o aparelho que acabara de abrir — trabalha, depois para.

A trava nasce no `arm_launch_profile`, antes do `exec`. O gesto dela
(`manual`, `gesto_de_perfil`) continua passando. Um lançamento novo solta a
trava anterior antes de vestir o pad dele, senão o arming se bloqueava.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp


def _daemon_sem_jogo() -> Any:
    """Autoridade de daemon: o R-04 antigo deixaria recriar."""
    return SimpleNamespace(display_authority="daemon", store=None)


def test_com_a_trava_o_automatico_nao_recria_antes_da_janela() -> None:
    daemon = _daemon_sem_jogo()
    daemon._pad_travado_pelo_lancamento = (4235410, 1000.0)

    assert gp._recriacao_bloqueada_por_jogo(
        daemon, origin="profile", motivo="troca_de_caminho:dualsense"
    ) is True


def test_o_gesto_dela_passa_com_a_trava() -> None:
    daemon = _daemon_sem_jogo()
    daemon._pad_travado_pelo_lancamento = (4235410, 1000.0)

    assert gp._recriacao_bloqueada_por_jogo(
        daemon, origin="manual", motivo="gesto"
    ) is False
    assert gp._recriacao_bloqueada_por_jogo(
        daemon, origin="gesto_de_perfil", motivo="gesto"
    ) is False


def test_sem_a_trava_e_sem_autoridade_o_automatico_recria() -> None:
    daemon = _daemon_sem_jogo()

    assert gp._recriacao_bloqueada_por_jogo(
        daemon, origin="profile", motivo="troca_de_caminho:dualsense"
    ) is False


def test_jogo_sem_perfil_trava_o_pad_que_ja_esta_de_pe(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem perfil não há modo a impor. O que há é o pad de pé, e é ele que
    o jogo vai abrir — a trava segura esse, sem aplicar modo nenhum.
    """
    (tmp_path / "last_run").write_text(
        "appid=2111190\nepoch=1000\npid=1\n", encoding="utf-8"
    )
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    daemon = SimpleNamespace()

    resultado = le.arm_launch_profile(daemon, base_dir=tmp_path, now=1001.0)

    assert resultado is not None
    assert resultado["armado"] is False
    assert resultado["motivo"] == "sem_perfil"
    assert daemon._pad_travado_pelo_lancamento == (2111190, 1000)


def test_o_lancamento_novo_solta_a_trava_antes_de_vestir(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Se a soltura viesse depois do apply, o arming do jogo novo seria
    bloqueado pela trava do jogo anterior.
    """
    (tmp_path / "last_run").write_text(
        "appid=2111190\nepoch=2000\npid=1\n", encoding="utf-8"
    )
    monkeypatch.setattr(le, "_steam_profiles", lambda _daemon: [])
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    daemon = SimpleNamespace(_pad_travado_pelo_lancamento=(111, 1.0))
    ordem: list[str] = []
    real = le._soltar_a_trava_do_lancamento

    def _solta(alvo: Any) -> None:
        ordem.append("solta")
        assert alvo._pad_travado_pelo_lancamento == (111, 1.0)
        real(alvo)

    monkeypatch.setattr(le, "_soltar_a_trava_do_lancamento", _solta)
    monkeypatch.setattr(
        le,
        "_travar_o_pad_que_o_jogo_vai_abrir",
        lambda *_a, **_k: ordem.append("trava"),
    )

    le.arm_launch_profile(daemon, base_dir=tmp_path, now=2001.0)

    assert ordem == ["solta", "trava"]
    assert daemon._pad_travado_pelo_lancamento is None
