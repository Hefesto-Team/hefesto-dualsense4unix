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
    """*"Abra o Lutris uma vez e eu leio a biblioteca"* — §3 da sprint."""
    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert b.estado == censo.NUNCA_ABERTO
    assert "Abra Lutris" in b.resumo
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


def test_o_lutris_le_um_yml_por_jogo(tmp_path: pathlib.Path) -> None:
    """O nome do arquivo É o slug — e é a chave que a §4 vai usar."""
    p = _flatpak(tmp_path, "net.lutris.Lutris", "lutris")
    (p / "games").mkdir()
    (p / "games/hollow-knight.yml").write_text("game: {}\n", encoding="utf-8")
    (p / "games/celeste.yml").write_text("game: {}\n", encoding="utf-8")

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert sorted(j.chave for j in b.jogos) == ["celeste", "hollow-knight"]
    assert b.resumo == "2 jogos na biblioteca · 2 instalados"


def test_o_retroarch_le_as_playlists(tmp_path: pathlib.Path) -> None:
    """Uma `.lpl` por console, com as ROMs dentro."""
    p = _flatpak(tmp_path, "org.libretro.RetroArch", "retroarch")
    _escrever(p / "playlists/Nintendo - SNES.lpl",
              {"items": [{"path": "/roms/smw.sfc", "label": "Super Mario World"}]})

    b = censo.biblioteca_de("RetroArch", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Super Mario World"]
    assert b.jogos[0].loja == "Nintendo - SNES"


def test_o_dolphin_conta_pastas_e_nao_mente_que_sao_jogos(
    tmp_path: pathlib.Path,
) -> None:
    """O Dolphin guarda o cache num binário; em texto há só as pastas."""
    p = _flatpak(tmp_path, "org.DolphinEmu.dolphin-emu", "dolphin-emu")
    (p / "Dolphin.ini").write_text(
        "[General]\nISOPath0 = /jogos/gc\nISOPath1 = /jogos/wii\nISOPaths = 2\n",
        encoding="utf-8")

    b = censo.biblioteca_de("Dolphin", lar=tmp_path)

    assert sorted(j.chave for j in b.jogos) == ["/jogos/gc", "/jogos/wii"]
    assert b.instalados == []
    assert b.resumo == "2 jogos na biblioteca · 0 instalados"


@pytest.mark.parametrize("lancador,app_id,sub,arquivo", [
    ("Heroic", HEROIC_ID, "heroic", "store_cache/legendary_library.json"),
    ("RetroArch", "org.libretro.RetroArch", "retroarch", "playlists/x.lpl"),
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


_LUTRIS_ID = "net.lutris.Lutris"
_CASAS_DO_LUTRIS = {
    "nativo-so-dados": (None, ".local/share/lutris"),
    "flatpak-so-dados": (None, f".var/app/{_LUTRIS_ID}/data/lutris"),
    "nativo-com-config": (".config/lutris", ".local/share/lutris"),
    "flatpak-com-config": (f".var/app/{_LUTRIS_ID}/config/lutris",
                           f".var/app/{_LUTRIS_ID}/data/lutris"),
}


def _banco_do_lutris(dados: pathlib.Path, *, versao: str = "ge-proton") -> None:
    """O `pga.db` com as 23 colunas do 0.5.22 e um jogo da GOG pelo runner `wine`."""
    import sqlite3

    from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import _ESQUEMA

    dados.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(dados / "pga.db")
    with con:
        con.execute(_ESQUEMA)
        con.execute(
            "INSERT INTO games (name, slug, runner, executable, installed, configpath, "
            "service, service_id) VALUES (?,?,?,?,?,?,?,?)",
            ("Jogo X", "jogo-x", "wine", "/x/jogo.exe", 1, "jogo-x-1", "gog", "1441"))
    con.close()
    _escrever(dados / "runtime/umu-games/umu-games.json",
              [{"store": "gog", "appid": "1441", "umu_id": "umu-70400"}])


@pytest.mark.parametrize("casa", sorted(_CASAS_DO_LUTRIS))
def test_o_lutris_e_lido_pela_regra_dele(tmp_path: pathlib.Path, casa: str) -> None:
    """Só com a pasta de dados (o 0.5.22 não cria a `config/`), o censo lê."""
    config, dados = _CASAS_DO_LUTRIS[casa]
    if config is not None:
        (tmp_path / config).mkdir(parents=True)
    _banco_do_lutris(tmp_path / dados)

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert b.estado == censo.LIDO, f"{casa}: o censo diz {b.estado}"
    assert [(j.nome, j.classe_de_janela) for j in b.jogos] == [("Jogo X", "steam_app_70400")]
    assert b.onde == tmp_path / (config or dados)


def test_a_caixa_do_lutris_flatpak_tem_um_dono(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com só a `data/lutris` do Flatpak, a camada da exclusão e o censo acham"""
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    (tmp_path / "bin").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [])

    _banco_do_lutris(tmp_path / _CASAS_DO_LUTRIS["flatpak-so-dados"][1])
    _escrever(tmp_path / ".config/lutris/games/outro.yml", {})

    achada = cpe._pasta_do_lutris_flatpak(tmp_path)
    assert achada == tmp_path / _CASAS_DO_LUTRIS["flatpak-so-dados"][1]
    assert achada == censo._pasta_de_config("Lutris", tmp_path)
    assert not hasattr(cpe, "_PASTAS_DO_LUTRIS_FLATPAK"), "a cópia da regra voltou à carona"


def test_o_lar_do_nativo_so_com_dados_acha_o_proton(tmp_path: pathlib.Path) -> None:
    """Com `~/.local/share/lutris`, o lar é o `~`, e o Proton da Steam se acha"""
    dados = tmp_path / ".local/share/lutris"
    _banco_do_lutris(dados)
    (dados / "games").mkdir()
    (dados / "games/jogo-x-1.yml").write_text("wine:\n  version: GE-Proton9-1\n",
                                              encoding="utf-8")
    proton = tmp_path / ".steam/steam/compatibilitytools.d/GE-Proton9-1/proton"
    proton.parent.mkdir(parents=True)
    proton.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    jogos = censo.biblioteca_de("Lutris", lar=tmp_path).jogos

    assert [j.classe_de_janela for j in jogos] == ["steam_app_70400"], (
        "o Proton plantado no lar não foi achado: o lar do nativo saiu errado")


def test_a_config_ganha_da_pasta_de_dados(tmp_path: pathlib.Path) -> None:
    """Com as duas, os `.yml` dos jogos vêm da `config/` (`GAME_CONFIG_DIR`), e"""
    config = tmp_path / ".config/lutris"
    dados = tmp_path / ".local/share/lutris"
    _banco_do_lutris(dados)
    for pasta, umu in ((config, "umu-111"), (dados, "umu-222")):
        (pasta / "games").mkdir(parents=True)
        (pasta / "games/jogo-x-1.yml").write_text(
            f"system:\n  env:\n    UMU_ID: {umu}\n", encoding="utf-8")

    jogos = censo.biblioteca_de("Lutris", lar=tmp_path).jogos

    assert [(j.classe_de_janela, j.configuracao) for j in jogos] == [
        ("steam_app_111", config / "games/jogo-x-1.yml")]
