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

NOTA DATADA — 13/09/2026 (RESTOS-DA-ONDA-DOIS-01). A segunda metade caducou em
duas etapas: a FRASES-E-DICAS-03 tirou a efetiva da tela, e sem ela nada vivo
lia o valor — a janela GTK desta linha saiu em 06/09 (`D-0609-GTK-LEVA-INTEIRA`),
e o cartão da Steam na aba 07 só o passava a `markup_status_steam_input`, que o
ignorava. A leitura da interface virou `_steam_input_excecoes` (só a lista) e
parou de varrer os hidraw. A primeira metade continua: quem mede o físico
exposto é `physical_nodes_exposure`, e o `doctor.sh` pergunta a ele.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("r06 status honesto")

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
    ) -> tuple[str, list[int]]:
        """O markup da linha e os `uid` com que alguém varreu os hidraw."""
        varridas: list[int] = []
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
            lambda uid, **k: varridas.append(uid) or exposicao,
        )
        label = _LabelFalso()
        _Aba(label)._refresh_steam_input_status()
        return label.markup, varridas

    def test_sem_allowlist_a_linha_nao_muda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup, varridas = self._refresh(
            monkeypatch, appids=[], exposicao={"/dev/hidraw0": True}
        )
        # PALAVRA-01: o rótulo era "desligado (ok)" — minúsculo no meio da
        # frase dela e com jargão ("per-app"). O que ela lê agora e o que
        # este teste trava é a frase em português.
        assert "Desligado — tudo certo" in markup
        assert "xceção" not in markup
        assert varridas == []

    # NOTA DATADA — 13/09/2026 (FRASES-E-DICAS-03). Os três casos abaixo
    # cobravam o estado da exceção NARRADO na linha, depois de um travessão. A
    # ordem dela de 13/09, no índice da terceira lista
    # (`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`),
    # deixa na tela só estado: a linha conta as exceções e cala o resto.
    #
    # NOTA DATADA — 13/09/2026 (RESTOS-DA-ONDA-DOIS-01). Eles cobravam também
    # que a leitura (`_steam_input_excecao_status`) distinguisse configurada de
    # efetiva, varrendo os hidraw. Nada vivo lia a efetiva, e a leitura virou
    # `_steam_input_excecoes`. Os três estados do físico ficam, e agora cobram
    # o contrário: a mesma contagem nos três, e nenhuma varredura.
    def test_excecao_configurada_e_efetiva(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup, varridas = self._refresh(
            monkeypatch, appids=[2111190], exposicao={"/dev/hidraw0": True}
        )
        assert markup.endswith("Exceção por jogo: 1 jogo(s)</span>"), markup
        assert "controle liberado agora" not in markup
        assert ea.EmulationActionsMixin._steam_input_excecoes() == [2111190]
        assert varridas == []

    def test_excecao_configurada_mas_o_fisico_segue_escondido(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Era exatamente este estado — configurada e sem efeito — que a GUI
        não sabia contar. A tela só conta, e a leitura não pergunta mais."""
        markup, varridas = self._refresh(
            monkeypatch, appids=[2111190], exposicao={"/dev/hidraw0": False}
        )
        assert markup.endswith("Exceção por jogo: 1 jogo(s)</span>"), markup
        assert "só valendo durante o jogo" not in markup
        assert varridas == []

    def test_sem_fisico_visivel_nao_afirma_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markup, varridas = self._refresh(monkeypatch, appids=[2111190], exposicao={})
        assert markup.endswith("Exceção por jogo: 1 jogo(s)</span>"), markup
        assert "sem controle físico visível" not in markup
        assert varridas == []
