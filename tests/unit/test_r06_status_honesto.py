"""R-06 item 3 (auditoria 23/07) — "configurada" ≠ "EFETIVA".

A allowlist do Steam Input ficou inerte por meses e ninguém percebeu porque as
duas perguntas viviam coladas numa frase só: o appid ESTAVA no arquivo, o guard
de VDF o respeitava, e mesmo assim o daemon seguia escondendo o hidraw do
controle físico — o jogo não via DualSense nenhum. Um status honesto precisa
medir a segunda pergunta, não deduzi-la da primeira.

- `broker.hidraw_broker.physical_nodes_exposure` mede: cada hidraw de DualSense
  FÍSICO está legível pelo uid da usuária agora? (varredura read-only, sem
  root, sem falar com o broker — quem chama roda como ela e é a permissão DO USUÁRIO
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


