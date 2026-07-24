"""R-06 item 3 (auditoria 23/07) — "configurada" ≠ "EFETIVA".

A allowlist do Steam Input ficou inerte por meses e ninguém percebeu porque as
duas perguntas viviam coladas numa frase só: o appid ESTAVA no arquivo, o guard
de VDF o respeitava, e mesmo assim o daemon seguia escondendo o hidraw do
controle físico — o jogo não via DualSense nenhum. Um status honesto precisa
medir a segunda pergunta, não deduzi-la da primeira.

- `broker.hidraw_broker.physical_nodes_exposure` mede: cada hidraw de DualSense
  FÍSICO está legível pelo uid da usuária agora? (varredura read-only, sem
  root, sem falar com o broker — quem chama roda como ela e é a permissão DELA
  que decide);
- a aba Emulação passa a dizer as duas coisas na mesma linha.
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import emulation_actions as ea
from hefesto_dualsense4unix.broker import hidraw_broker as hb


class _OpsFalso:
    def __init__(self, expostos: set[str]) -> None:
        self._expostos = expostos

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return node in self._expostos


class TestExposicaoDoFisico:
    def test_lista_so_o_fisico_e_diz_quem_esta_exposto(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for base in ("hidraw0", "hidraw1", "hidraw9"):
            (tmp_path / base).mkdir()

        def _validator(node: str) -> str | None:
            # hidraw9 é o vpad/teclado: NUNCA entra na conta.
            base = node.rsplit("/", 1)[-1]
            return base if base in ("hidraw0", "hidraw1") else None

        estado = hb.physical_nodes_exposure(
            1000,
            dev_root="/dev",
            sys_class_hidraw=str(tmp_path),
            ops=_OpsFalso({"/dev/hidraw0"}),
            validator=_validator,
        )

        assert estado == {"/dev/hidraw0": True, "/dev/hidraw1": False}

    def test_sysfs_ilegivel_devolve_vazio(self, tmp_path: Any) -> None:
        assert hb.physical_nodes_exposure(
            1000, sys_class_hidraw=str(tmp_path / "nao-existe")
        ) == {}


class _LabelFalso:
    def __init__(self) -> None:
        self.markup = ""

    def set_markup(self, markup: str) -> None:
        self.markup = markup


class _Aba(ea.EmulationActionsMixin):
    """Só o que o refresh do status toca."""

    def __init__(self, label: _LabelFalso) -> None:
        self._label = label

    def _get(self, nome: str) -> Any:
        return self._label if nome == "emulation_steam_input_status_label" else None


class TestStatusDaAba:
    @staticmethod
    def _refresh(
        monkeypatch: pytest.MonkeyPatch,
        *,
        appids: list[int],
        exposicao: dict[str, bool],
        conflito: bool | None = False,
    ) -> str:
        monkeypatch.setattr(ea, "run_in_thread", lambda fn, on_success: on_success(fn()))
        monkeypatch.setattr(
            ea.EmulationActionsMixin, "_steam_input_is_on", staticmethod(lambda: conflito)
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.launch_env.steam_input_appids",
            lambda path=None: set(appids),
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.broker.hidraw_broker.physical_nodes_exposure",
            lambda uid, **k: exposicao,
        )
        label = _LabelFalso()
        _Aba(label)._refresh_steam_input_status()
        return label.markup

    def test_sem_allowlist_a_linha_nao_muda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = self._refresh(monkeypatch, appids=[], exposicao={"/dev/hidraw0": True})
        assert "desligado (ok)" in markup
        assert "exceção" not in markup

    def test_excecao_configurada_e_efetiva(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = self._refresh(
            monkeypatch, appids=[2111190], exposicao={"/dev/hidraw0": True}
        )
        assert "exceção per-app: 1 jogo(s)" in markup
        assert "controle liberado agora" in markup

    def test_excecao_configurada_mas_o_fisico_segue_escondido(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Era exatamente este estado — configurada e sem efeito — que a GUI
        não sabia contar."""
        markup = self._refresh(
            monkeypatch, appids=[2111190], exposicao={"/dev/hidraw0": False}
        )
        assert "exceção per-app: 1 jogo(s)" in markup
        assert "só valendo durante o jogo" in markup

    def test_sem_fisico_visivel_nao_afirma_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup = self._refresh(monkeypatch, appids=[2111190], exposicao={})
        assert "sem controle físico visível" in markup
