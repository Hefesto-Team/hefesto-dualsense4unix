"""A háptica mora em Vibração — A-HAPTICA-MORA-EM-VIBRACAO-E-O-ICONE-DO-APP-VOLTA-01 (item 1).

Ela, 04/10/2026: «háptico deveria aparecer na seção de vibração». A háptica são os dois atuadores,
mesmo viajando como áudio por dentro. O dono é ``docs/data/pecas-do-dualsense.csv`` (a coluna
``regiao``); o mapa do controle nasce dele. Aqui se mede o dono e o desenho gerado.

MORDIDA: voltar ``feat-haptica`` para ``audio`` no CSV reprova os dois lados (o do dono na hora, o
do desenho depois de regerar o mapa).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PECAS = RAIZ / "docs/data/pecas-do-dualsense.csv"
DESENHO = RAIZ / "mockup/mapa-do-controle.html"
MOTORES = ("feat-rumble-esquerdo", "feat-rumble-direito")


def _pecas() -> list[dict[str, str]]:
    linhas = [ln for ln in PECAS.read_text(encoding="utf-8").splitlines()
              if ln and not ln.startswith("#")]
    return list(csv.DictReader(linhas))


def _grupo(html: str, titulo: str) -> list[str]:
    """Os `item-<id>` do grupo de um título, na ordem em que a página os desenha."""
    achado = re.search(
        rf'<div class="grupo-rot">{titulo}</div>(.*?)\n    </div>', html, re.S)
    assert achado, f"o grupo «{titulo}» não está no desenho"
    return re.findall(r'<div class="item item-([\w-]+)"', achado.group(1))


def test_o_dono_diz_que_a_haptica_e_vibracao_e_a_poe_antes_dos_motores() -> None:
    pecas = _pecas()
    por_id = {p["id"]: p for p in pecas}
    assert por_id["feat-haptica"]["regiao"] == "vibracao"
    ordem = [p["id"] for p in pecas if p["regiao"] == "vibracao"]
    assert ordem.index("feat-haptica") < min(ordem.index(m) for m in MOTORES), ordem


def test_o_desenho_do_mapa_poe_a_haptica_em_vibracao_antes_dos_dois_motores() -> None:
    html = DESENHO.read_text(encoding="utf-8")
    assert _grupo(html, "Vibração") == ["feat-haptica", *MOTORES]
    assert "feat-haptica" not in _grupo(html, "Áudio")


def test_a_haptica_continua_acendendo_quando_o_servico_diz_que_ela_toca() -> None:
    """A linha mudou de seção, não de dono: o campo que a acende no desenho segue nela."""
    html = DESENHO.read_text(encoding="utf-8")
    item = re.search(r'<div class="item item-feat-haptica"[^>]*>', html)
    assert item and "data-campo" in item.group(0), item
