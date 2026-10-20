#!/usr/bin/env python3
"""LANCADORES-ZERO-01 — o censo lê a biblioteca dos cinco que não são a Steam."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from tests.unit.test_o_censo_responde_como_o_lancador_responde import plantar_o_registro

HEROIC_ID = "com.heroicgameslauncher.hgl"


def _flatpak(lar: pathlib.Path, app_id: str, sub: str) -> pathlib.Path:
    """A pasta de config de um flatpak — `~/.var/app/<id>/config/<sub>`."""
    p = lar / ".var/app" / app_id / "config" / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _escrever(caminho: pathlib.Path, dado: object) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dado), encoding="utf-8")


def test_lancador_nunca_aberto_diz_o_que_fazer(tmp_path: pathlib.Path) -> None:
    """*"Abra o Heroic uma vez e eu leio a biblioteca"* — §3 da sprint."""
    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.NUNCA_ABERTO
    assert "Abra Heroic" in b.resumo
    assert b.jogos == []


def test_quem_nao_e_lancador_nao_ganha_a_frase_da_biblioteca(
    tmp_path: pathlib.Path,
) -> None:
    """O «Flatpak» é o RUNTIME dos outros cinco — §5.4 da sprint."""
    b = censo.biblioteca_de("Flatpak", lar=tmp_path)

    assert b.estado == censo.SEM_BIBLIOTECA
    assert b.resumo == ""
    assert not censo.sabe_ler("Flatpak")


def test_o_heroic_le_as_tres_lojas(tmp_path: pathlib.Path) -> None:
    """Epic (legendary), GOG e Amazon (nile) num cartão só."""
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "a1", "title": "Um da Epic"}]})
    _escrever(p / "store_cache/gog_library.json",
              {"games": [{"app_name": "g1", "title": "Um da GOG"}]})
    _escrever(p / "store_cache/nile_library.json",
              {"library": [{"id": "n1", "product_title": "Um da Amazon"}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert {j.loja for j in b.jogos} == {"Epic", "GOG", "Amazon"}
    assert [j.nome for j in b.jogos if j.loja == "Amazon"] == ["Um da Amazon"]


def test_o_caso_dela_biblioteca_cheia_e_zero_instalados(
    tmp_path: pathlib.Path,
) -> None:
    """O disco do usuário em 09/09/2026: 37 na biblioteca, nenhum baixado."""
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": f"e{n}", "title": f"Epic {n}"}
                           for n in range(35)]})
    _escrever(p / "store_cache/gog_library.json",
              {"games": [{"app_name": f"g{n}", "title": f"GOG {n}"}
                         for n in range(2)]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert len(b.jogos) == 37
    assert b.instalados == []
    assert b.resumo == "37 jogos na biblioteca · 0 instalados"


def test_o_registro_e_quem_diz_o_instalado(tmp_path: pathlib.Path) -> None:
    """A biblioteca não sabe o que está no disco — o registro da loja sabe."""
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Baixado"},
                           {"app_name": "e2", "title": "Só na conta"}]})
    plantar_o_registro(p, {"e1": {"install_path": "/jogos/e1"}})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.instalados] == ["Baixado"]
    assert b.resumo == "2 jogos na biblioteca · 1 instalado"


def test_o_singular_e_o_plural_da_frase(tmp_path: pathlib.Path) -> None:
    """"1 jogo · 1 instalado" — a tela do usuário não diz "1 jogos"."""
    p = _flatpak(tmp_path, HEROIC_ID, "heroic")
    _escrever(p / "store_cache/legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Um só"}]})
    plantar_o_registro(p, ["e1"])

    assert censo.biblioteca_de("Heroic", lar=tmp_path).resumo == \
        "1 jogo na biblioteca · 1 instalado"


def test_biblioteca_vazia_nao_e_o_mesmo_que_nunca_aberto(
    tmp_path: pathlib.Path,
) -> None:
    """A pasta existe e a conta não tem jogo — são coisas diferentes."""
    _flatpak(tmp_path, HEROIC_ID, "heroic")

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert b.resumo == "A biblioteca está vazia."


@pytest.mark.parametrize("lancador,app_id,sub,arquivo", [
    ("Heroic", HEROIC_ID, "heroic", "store_cache/legendary_library.json"),
])
def test_json_truncado_nao_derruba_a_leitura(
    tmp_path: pathlib.Path, lancador: str, app_id: str, sub: str, arquivo: str,
) -> None:
    """Um `.json` pela metade não pode apagar a coluna inteira."""
    p = _flatpak(tmp_path, app_id, sub)
    alvo = p / arquivo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text('{"library": [', encoding="utf-8")

    b = censo.biblioteca_de(lancador, lar=tmp_path)

    assert b.estado in (censo.LIDO, censo.ILEGIVEL)
    assert b.jogos == []


def test_o_nativo_tambem_e_lido(tmp_path: pathlib.Path) -> None:
    """`~/.config/<sub>` — quem não usa flatpak tem biblioteca igual."""
    p = tmp_path / ".config/heroic/store_cache"
    _escrever(p / "legendary_library.json",
              {"library": [{"app_name": "e1", "title": "Nativo"}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert [j.nome for j in b.jogos] == ["Nativo"]
