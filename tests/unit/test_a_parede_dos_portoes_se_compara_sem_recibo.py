"""A parede do portão completo só se mede (e vira piso) na corrida que rodou todos os portões."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]


def _tempo() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "o_tempo_da_casa_sem_recibo", RAIZ / "scripts" / "o-tempo-da-casa.py"
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["o_tempo_da_casa_sem_recibo"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _saida(casa: Path, nome: str, linha: str, quando: int) -> None:
    pasta = casa / "fecho"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / nome
    arquivo.write_text(
        f"portões — árvore x\n         camadas rapido completo\n\n{linha}\nTODOS VERDES.\n",
        encoding="utf-8",
    )
    os.utime(arquivo, (quando, quando))


def test_o_piso_e_a_corrida_sem_recibo_mesmo_quando_a_com_recibo_e_a_mais_nova(
    tmp_path: Path,
) -> None:
    """0 lembrados e 50 s; 10 lembrados e 9 s, mais nova: a medida é a de 50 s."""
    _saida(
        tmp_path,
        "portoes-1.out",
        "tempo: 50 s de parede; 400 s de portão somados; 0 lembrado(s) sem rodar.",
        1_000_000,
    )
    _saida(
        tmp_path,
        "portoes-2.out",
        "tempo: 9 s de parede; 38 s de portão somados; 10 lembrado(s) sem rodar.",
        2_000_000,
    )

    censo = _tempo().censo_do_completo(tmp_path)

    assert censo.numero == 50, censo
    assert censo.por_item == {"portoes-1.out": 50}


def test_so_com_recibo_a_medida_diz_nao_medido_em_vez_de_comparar(tmp_path: Path) -> None:
    """Sem nenhuma corrida de 0 lembrados, o número some e o motivo diz quais lembraram."""
    _saida(
        tmp_path,
        "portoes-1.out",
        "tempo: 9 s de parede; 38 s de portão somados; 72 lembrado(s) sem rodar.",
        1_000_000,
    )

    censo = _tempo().censo_do_completo(tmp_path)

    assert censo.numero is None
    assert "portoes-1.out (72 lembrados)" in (censo.indisponivel or ""), censo


def test_a_linha_sem_a_conta_de_lembrados_nao_prova_que_rodou_tudo(tmp_path: Path) -> None:
    """A linha de antes da conta (`tempo: N s de parede; M s de portão somados.`) não é medida."""
    _saida(tmp_path, "portoes-1.out", "tempo: 30 s de parede; 400 s de portão somados.", 1_000_000)

    censo = _tempo().censo_do_completo(tmp_path)

    assert censo.numero is None
    assert "sem a conta" in (censo.indisponivel or ""), censo
