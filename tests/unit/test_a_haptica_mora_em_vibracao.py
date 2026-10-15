"""A háptica mora em Vibração — A-HAPTICA-MORA-EM-VIBRACAO-E-O-ICONE-DO-APP-VOLTA-01 (item 1).

Ela, 04/10/2026: «háptico deveria aparecer na seção de vibração». A háptica são os dois atuadores,
mesmo viajando como áudio por dentro. O dono é ``docs/data/pecas-do-dualsense.csv`` (a coluna
``regiao``). O mapa do controle deixou de desenhar os sensores e os motores (15/10/2026: a página
é a tela de configurar os botões), e quem desenha a háptica agora é a aba Vibração.

MORDIDA: voltar ``feat-haptica`` para ``audio`` no CSV reprova.
"""

from __future__ import annotations

import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"
MOTORES = ("feat-rumble-esquerdo", "feat-rumble-direito")


def _pecas() -> list[dict[str, str]]:
    linhas = [ln for ln in PECAS.read_text(encoding="utf-8").splitlines()
              if ln and not ln.startswith("#")]
    return list(csv.DictReader(linhas))


def test_o_dono_diz_que_a_haptica_e_vibracao_e_a_poe_antes_dos_motores() -> None:
    pecas = _pecas()
    por_id = {p["id"]: p for p in pecas}
    assert por_id["feat-haptica"]["regiao"] == "vibracao"
    ordem = [p["id"] for p in pecas if p["regiao"] == "vibracao"]
    assert ordem.index("feat-haptica") < min(ordem.index(m) for m in MOTORES), ordem
