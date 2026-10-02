#!/usr/bin/env python3
"""JOGOS-DOS-LANCADORES-01 — os jogos dos outros cinco chegam ao campo do jogo."""
from __future__ import annotations

import json
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import jogos_locais as jl
from tests.unit.test_o_censo_responde_como_o_lancador_responde import plantar_o_registro

HEROIC_ID = "com.heroicgameslauncher.hgl"


def _heroic(
    lar: pathlib.Path,
    itens: list[dict[str, Any]],
    umu: dict[str, str] | None = None,
) -> pathlib.Path:
    """Uma biblioteca da Epic de mentira, na árvore de flatpak que é a dela."""
    pasta = lar / ".var/app" / HEROIC_ID / "config/heroic"
    alvo = pasta / "store_cache/legendary_library.json"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"library": itens}), encoding="utf-8")
    plantar_o_registro(pasta, {
        str(i["app_name"]): {"is_dlc": bool((i.get("install") or {}).get("is_dlc"))}
        for i in itens if i.get("is_installed")})
    mapa = UMU_DO_DISCO_DELA if umu is None else umu
    (alvo.parent / "umu.json").write_text(json.dumps(mapa), encoding="utf-8")
    return pasta


UMU_DO_DISCO_DELA: dict[str, Any] = {
    "legendary_63a665088eb1480298f1e57943b225d8": "umu-1088850",
    "__timestamp": {"legendary_63a665088eb1480298f1e57943b225d8":
                    "Thu Sep 10 2026 00:17:23 GMT-0300"},
}

JANELA_DO_GOTG = "steam_app_1088850"


BAIXADO: dict[str, Any] = {
    "app_name": "63a665088eb1480298f1e57943b225d8",
    "title": "Marvel's Guardians of the Galaxy",
    "is_installed": True,
    "install": {"executable": "retail/gotg.exe",
                "install_path": "/casa/Games/Heroic/MarvelGOTG",
                "is_dlc": False},
}
A_ROUPA: dict[str, Any] = {
    "app_name": "9596620d263b40c083ddf1f0c662c8ff",
    "title": "Marvel's Guardians of the Galaxy: Social-Lord Outfit",
    "is_installed": True,
    "install": {"executable": "", "is_dlc": True},
}
SO_NA_CONTA: dict[str, Any] = {
    "app_name": "Catnip", "title": "Borderlands 3",
    "is_installed": False, "install": {"install_size": "0", "is_dlc": False},
}


def test_o_dlc_e_o_redistribuivel_saem_da_contagem(
    tmp_path: pathlib.Path,
) -> None:
    """`install.is_dlc` é quem manda — nunca uma lista de nomes."""
    _heroic(tmp_path, [BAIXADO, A_ROUPA, SO_NA_CONTA])

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.jogos] == [
        "Marvel's Guardians of the Galaxy", "Borderlands 3"]
    assert b.resumo == "2 jogos na biblioteca · 1 instalado"


def test_o_redistribuivel_da_gog_cai_pela_mesma_regua(
    tmp_path: pathlib.Path,
) -> None:
    """*Galaxy Common Redistributables* — `app_name: gog-redist`, `is_dlc: true`."""
    pasta = tmp_path / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "gog_library.json").write_text(json.dumps({"games": [
        {"app_name": "gog-redist", "title": "Galaxy Common Redistributables",
         "is_installed": True, "install": {"is_dlc": True}},
        {"app_name": "1421309312", "title": "Worms Revolution Gold Edition",
         "is_installed": False, "install": {"is_dlc": False}},
    ]}), encoding="utf-8")
    plantar_o_registro(pasta.parent, [], loja="gog")

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Worms Revolution Gold Edition"]


def test_a_chave_de_janela_vem_do_umu_e_nao_do_executavel(
    tmp_path: pathlib.Path,
) -> None:
    """**FATO SUBSTITUÍDO — 21/09/2026, e esta régua cravava o errado.**"""
    _heroic(tmp_path, [BAIXADO])

    jogo = censo.biblioteca_de("Heroic", lar=tmp_path).instalados[0]

    assert jogo.executavel == "retail/gotg.exe"
    assert jogo.umu_id == "umu-1088850"
    assert jogo.classe_de_janela == JANELA_DO_GOTG
    assert jogo.classe_de_janela != "gotg.exe", (
        "a derivação pelo executável voltou")
    assert jogo.caminho == pathlib.Path("/casa/Games/Heroic/MarvelGOTG")


def test_quem_nao_tem_chave_nao_e_oferecido_mesmo_instalado(
    tmp_path: pathlib.Path,
) -> None:
    """Duas ausências diferentes, e nenhuma das duas vira oferta."""
    _heroic(tmp_path, [BAIXADO, SO_NA_CONTA])
    gog = tmp_path / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
    (gog / "gog_library.json").write_text(json.dumps({"games": [
        {"app_name": "1421309312", "title": "Worms Revolution Gold Edition",
         "is_installed": True, "install": {"is_dlc": False}}]}),
        encoding="utf-8")
    plantar_o_registro(gog.parent, ["1421309312"], loja="gog")

    com_chave = censo.jogos_com_chave_de_janela(lar=tmp_path)

    assert [(lanc, j.classe_de_janela) for lanc, j in com_chave] == [
        ("Heroic", JANELA_DO_GOTG)]
    assert len(censo.biblioteca_de("Heroic", lar=tmp_path).jogos) == 3


def test_o_emulador_nao_finge_ter_uma_janela_por_rom(
    tmp_path: pathlib.Path,
) -> None:
    """As 7 ROMs do RetroArch dela são UM processo — não sete janelas."""
    pasta = tmp_path / ".var/app/org.libretro.RetroArch/config/retroarch"
    (pasta / "playlists").mkdir(parents=True, exist_ok=True)
    (pasta / "playlists/Nintendo - SNES.lpl").write_text(json.dumps({"items": [
        {"path": "/casa/roms/240pSuite.sfc", "label": "240pSuite"}]}),
        encoding="utf-8")

    b = censo.biblioteca_de("RetroArch", lar=tmp_path)

    assert len(b.instalados) == 1
    assert b.instalados[0].classe_de_janela == ""
    assert censo.jogos_com_chave_de_janela(lar=tmp_path) == []


def test_o_jogo_do_lancador_vira_oferta_com_a_wm_class_no_value(
    tmp_path: pathlib.Path,
) -> None:
    """A mesma divisão da Steam: `value` é o ENDEREÇO, `label` é o que ela lê."""
    _heroic(tmp_path, [BAIXADO, A_ROUPA, SO_NA_CONTA])

    ofertas = jl.jogos_dos_lancadores(lar=tmp_path)

    assert [(j.valor, j.rotulo, j.forma) for j in ofertas] == [
        ("steam_app_1088850", "Marvel's Guardians of the Galaxy (Heroic)", "janela")]


def test_o_que_o_campo_grava_casa_com_a_janela_de_verdade() -> None:
    """A PROVA QUE IMPORTA: a oferta vira regra, e a regra reconhece a janela.

    É o critério de pronto *"no perfil"* da sprint — **o MESMO campo**
    (`window_class`), nunca um campo novo. O caminho inteiro, sem tela:

        oferta  →  from_simple_choice(forma, valor)  →  MatchCriteria  →  matches

    **MORDIDA:** devolva ``"game"`` em `JogoLocal.forma` e a regra vira
    `process_name=["gotg.exe"]` — outro dado, que casa por acaso: esta linha
    reprova porque `matches` deixa de reconhecer a `wm_class`.
    """
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    jogo = jl.JogoLocal(appid="", nome="Marvel's Guardians of the Galaxy",
                        fonte="heroic", lancador="Heroic", chave="gotg.exe")

    regra = from_simple_choice(jogo.forma, jogo.valor)

    assert regra.window_class == ["gotg.exe"]
    assert regra.matches({"wm_class": "gotg.exe", "wm_name": "GOTG"})
    assert not regra.matches({"wm_class": "steam_app_1245620", "wm_name": ""})


def test_a_steam_desempata_quando_o_mesmo_jogo_vem_das_duas_origens() -> None:
    """Um jogo em duas lojas não pode virar duas linhas na sugestão."""
    steam = [jl.JogoLocal(appid="1245620", nome="ELDEN RING", fonte="steam")]
    dos_lancadores = [
        jl.JogoLocal(appid="", nome="Elden Ring", fonte="heroic",
                     lancador="Heroic", chave="eldenring.exe"),
        jl.JogoLocal(appid="", nome="Outro", fonte="heroic",
                     lancador="Heroic", chave="outro.exe"),
    ]

    ofertas = jl.ofertas_do_campo_do_jogo(steam, dos_lancadores)

    assert [j.valor for j in ofertas] == ["1245620", "outro.exe"]


def test_o_rotulo_diz_o_nome_do_jogo_do_lancador() -> None:
    """Escolher a linha e o campo ficar mudo é a lista mentindo por omissão."""
    chaves = {"gotg.exe": "Marvel's Guardians of the Galaxy"}

    assert jl.frase_do_campo_do_jogo("gotg.exe", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    assert jl.frase_do_campo_do_jogo("gotg.exe", {}) is None
    assert jl.frase_do_campo_do_jogo("https://x/y", {}, chaves) == (
        jl.MSG_NAO_RECONHECI, True)


def test_a_busca_do_campo_acha_pelo_endereco_do_lancador() -> None:
    """Depois de escolher, o campo tem `gotg.exe` — e a lista tem de segurá-lo."""
    jogo = jl.JogoLocal(appid="", nome="Marvel's Guardians of the Galaxy",
                        fonte="heroic", lancador="Heroic", chave="gotg.exe")

    assert jl.casa_com_o_que_ela_digitou(jogo, "gotg")
    assert jl.casa_com_o_que_ela_digitou(jogo, "guardians")
    assert not jl.casa_com_o_que_ela_digitou(jogo, "elden")


def test_nenhum_lancador_instalado_e_lista_so_da_steam(
    tmp_path: pathlib.Path,
) -> None:
    """Máquina sem Heroic: a oferta é a de sempre, e nada quebra."""
    assert jl.jogos_dos_lancadores(lar=tmp_path) == []
    assert censo.jogos_com_chave_de_janela(lar=tmp_path) == []
    assert jl.jogos_com_janela(lar=tmp_path, pastas=[tmp_path]) == []


# (noqa-acento: citação literal dela, com a digitação dela)
LUTRIS_ID = "net.lutris.Lutris"

_ESQUEMA_LUTRIS = (
    "CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, sortname TEXT, "
    "slug TEXT, installer_slug TEXT, parent_slug TEXT, platform TEXT, "
    "runner TEXT, executable TEXT, directory TEXT, updated TEXT, "
    "lastplayed INTEGER, installed INTEGER, installed_at INTEGER, "
    "year INTEGER, configpath TEXT, has_custom_banner INTEGER, "
    "has_custom_icon INTEGER, has_custom_coverart_big INTEGER, "
    "playtime REAL, service TEXT, service_id TEXT, discord_id TEXT)"
)


def _lutris(lar: pathlib.Path, linhas: list[tuple[str, str, str, int]]) -> None:
    """Um `pga.db` de mentira na árvore de flatpak que é a dela."""
    import sqlite3

    pasta = lar / ".var/app" / LUTRIS_ID / "config/lutris"
    pasta.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(pasta / "pga.db")
    with con:
        con.execute(_ESQUEMA_LUTRIS)
        con.executemany(
            "INSERT INTO games (name, slug, executable, installed) "
            "VALUES (?, ?, ?, ?)", linhas)
    con.close()


def _atalho(pasta: pathlib.Path, arquivo: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / arquivo).write_text(corpo, encoding="utf-8")


def test_a_biblioteca_do_lutris_sai_do_banco_e_nao_da_pasta_vazia(
    tmp_path: pathlib.Path,
) -> None:
    """O LEITOR OLHAVA O ARQUIVO ERRADO, e o sintoma era a AUSÊNCIA de dado."""
    _lutris(tmp_path, [
        ("Celeste", "celeste", "/casa/Games/celeste/Celeste.bin.x86_64", 1),
        ("Hollow Knight", "hollow-knight", "/casa/Games/hk/hollow_knight.x86_64", 1),
        ("Só na conta", "so-na-conta", "", 0),
    ])

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert [j.nome for j in b.jogos] == ["Celeste", "Hollow Knight", "Só na conta"]
    assert b.resumo == "3 jogos na biblioteca · 2 instalados"
    assert [(lanc, j.classe_de_janela)
            for lanc, j in censo.jogos_com_chave_de_janela(lar=tmp_path)] == [
        ("Lutris", "Celeste.bin.x86_64"),
        ("Lutris", "hollow_knight.x86_64")]


def test_o_yml_de_configuracao_propria_nao_some_com_a_leitura_nova(
    tmp_path: pathlib.Path,
) -> None:
    """A leitura nova não pode ENCOLHER o que já funcionava."""
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste", 1)])
    games = tmp_path / ".var/app" / LUTRIS_ID / "config/lutris/games"
    games.mkdir(parents=True, exist_ok=True)
    (games / "celeste.yml").write_text("game: {}\n", encoding="utf-8")
    (games / "so-no-yml.yml").write_text("game: {}\n", encoding="utf-8")

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert [j.chave for j in b.jogos] == ["celeste", "so-no-yml"]


def test_o_jogo_direto_traz_a_etiqueta_do_proprio_atalho(
    tmp_path: pathlib.Path,
) -> None:
    """`StartupWMClass=` é a etiqueta — e não é invenção nossa, é a spec XDG."""
    _atalho(tmp_path, "celeste.desktop",
            "[Desktop Entry]\nType=Application\nName=Celeste\n"
            "Exec=/casa/celeste/Celeste\nCategories=Game;\n"
            "StartupWMClass=Celeste\n")
    _atalho(tmp_path, "meow-steam-4145130.desktop",
            "[Desktop Entry]\nType=Application\nName=ORPHEUS\n"
            "Exec=/usr/games/steam steam://rungameid/4145130\n"
            "Categories=Game;\nStartupWMClass=steam_app_4145130\n")
    _atalho(tmp_path, "com.heroicgameslauncher.hgl.desktop",
            "[Desktop Entry]\nType=Application\nName=Heroic Games Launcher\n"
            "Exec=/usr/bin/flatpak run com.heroicgameslauncher.hgl\n"
            "Categories=Game;PackageManager;\nStartupWMClass=heroic\n")
    _atalho(tmp_path, "org.libretro.RetroArch.desktop",
            "[Desktop Entry]\nType=Application\nName=RetroArch\n"
            "Exec=/usr/bin/flatpak run org.libretro.RetroArch\n"
            "Categories=Game;Emulator;\nStartupWMClass=retroarch\n")
    _atalho(tmp_path, "escondido.desktop",
            "[Desktop Entry]\nType=Application\nName=Escondido\n"
            "Exec=/bin/true\nCategories=Game;\nStartupWMClass=escondido\n"
            "NoDisplay=true\n")
    _atalho(tmp_path, "gedit.desktop",
            "[Desktop Entry]\nType=Application\nName=Editor\n"
            "Exec=/bin/true\nCategories=Utility;\nStartupWMClass=gedit\n")

    diretos = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    assert [(j.chave, j.nome) for j in diretos] == [
        ("Celeste", "Celeste"), ("retroarch", "RetroArch")]
    assert all(j.appid == "" for j in diretos)
    assert diretos[0].lancador == jl.LANCADOR_DIRETO


def test_o_detectar_acha_o_jogo_do_heroic_do_lutris_e_o_direto(
    tmp_path: pathlib.Path,
) -> None:
    """**A FALTA QUE ELA NOMEOU, medida nas três origens de uma vez.**"""
    _heroic(tmp_path, [BAIXADO])
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste.x86_64", 1)])
    _atalho(tmp_path, "super-zsnes.desktop",
            "[Desktop Entry]\nType=Application\nName=Super ZSNES\n"
            "Exec=/casa/zsnes/rodar.sh\nCategories=Game;Emulator;\n"
            "StartupWMClass=SUPERZSNES\n")

    jogos = jl.jogos_com_janela(lar=tmp_path, pastas=[tmp_path])
    achar = lambda c: jl.jogo_da_janela(c, jogos)  # noqa: E731

    assert achar("steam_app_1088850").nome == "Marvel's Guardians of the Galaxy"
    assert achar("steam_app_1088850").lancador == "Heroic"
    assert achar("Celeste.x86_64").lancador == "Lutris"
    assert achar("SUPERZSNES").lancador == jl.LANCADOR_DIRETO
    assert achar("STEAM_APP_1088850").nome == "Marvel's Guardians of the Galaxy"
    assert achar("steam_app_3357650") is None
    assert achar("unknown") is None
    assert achar("") is None
    assert achar(None) is None


def test_o_nome_da_janela_chega_ao_rotulo_sem_a_tela_ler_disco_duas_vezes(
    tmp_path: pathlib.Path,
) -> None:
    """A PONTA: `nomes_das_janelas` + `frase_do_campo_do_jogo` = o nome do jogo."""
    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])

    chaves = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])

    assert chaves == {"steam_app_1088850": "Marvel's Guardians of the Galaxy",
                      "1088850": "Marvel's Guardians of the Galaxy"}
    assert jl.frase_do_campo_do_jogo("steam_app_1088850", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    assert jl.frase_do_campo_do_jogo("STEAM_APP_1088850", {}, chaves) == (
        "Marvel's Guardians of the Galaxy", False)
    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) is chaves


def test_o_rotulo_nunca_derruba_a_aba_por_causa_de_um_disco_torto(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isto é PINTURA sobre o disco dela — e o contrato é não levantar NUNCA."""
    def _explode(*_a: object, **_k: object) -> list[Any]:
        raise OSError("um `pga.db` com byte torto")

    jl._NOMES_DAS_JANELAS = None
    monkeypatch.setattr(jl, "jogos_com_janela", _explode)

    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) == {}


def test_o_caderno_releu_o_disco_quando_ela_instalou_o_segundo_jogo(
    tmp_path: pathlib.Path,
) -> None:
    """**A TRAVA MEDIDA CONTRA A PRÓPRIA SAÍDA, e ela atravessou 17 réguas.**"""
    jl._NOMES_DAS_JANELAS = None
    _heroic(tmp_path, [BAIXADO])

    antes = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])
    assert antes == {"steam_app_1088850": "Marvel's Guardians of the Galaxy",
                     "1088850": "Marvel's Guardians of the Galaxy"}
    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) is antes

    segundo = dict(BAIXADO, app_name="outro", title="Hades II",
                   install={"executable": "bin/hades2.exe", "is_dlc": False})
    _heroic(tmp_path, [BAIXADO, segundo], umu=dict(
        UMU_DO_DISCO_DELA, legendary_outro="umu-1145350"))

    depois = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])

    assert depois is not antes
    assert depois == {"steam_app_1088850": "Marvel's Guardians of the Galaxy",
                      "1088850": "Marvel's Guardians of the Galaxy",
                      "steam_app_1145350": "Hades II",
                      "1145350": "Hades II"}
    assert jl.frase_do_campo_do_jogo("steam_app_1145350", {}, depois) == (
        "Hades II", False)


def test_o_caderno_releu_quando_o_lutris_ganhou_uma_linha_no_banco(
    tmp_path: pathlib.Path,
) -> None:
    """O `pga.db` é um ARQUIVO dentro da pasta — a pasta não muda de `mtime`."""
    jl._NOMES_DAS_JANELAS = None
    _lutris(tmp_path, [("Celeste", "celeste", "/casa/celeste/Celeste.x86_64", 1)])

    antes = jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path])
    assert antes == {"celeste.x86_64": "Celeste"}

    import sqlite3
    pasta = tmp_path / ".var/app" / LUTRIS_ID / "config/lutris"
    antes_da_pasta = pasta.stat().st_mtime_ns
    con = sqlite3.connect(pasta / "pga.db")
    con.execute("PRAGMA journal_mode=MEMORY")
    with con:
        con.execute("INSERT INTO games (name, slug, executable, installed) "
                    "VALUES (?, ?, ?, ?)",
                    ("Hollow Knight", "hk", "/casa/hk/hollow_knight.x86_64", 1))
    con.close()
    assert pasta.stat().st_mtime_ns == antes_da_pasta

    assert jl.nomes_das_janelas(lar=tmp_path, pastas=[tmp_path]) == {
        "celeste.x86_64": "Celeste",
        "hollow_knight.x86_64": "Hollow Knight"}


def test_o_cliente_de_loja_nao_entra_na_lista_de_jogos_e_o_emulador_entra(
    tmp_path: pathlib.Path,
) -> None:
    """**O QUE A TERCEIRA ORIGEM ACHA NO DISCO DELA HOJE É ZERO JOGO.**"""
    _atalho(tmp_path, "io.github.dummerle.rare.desktop",
            "[Desktop Entry]\nType=Application\nName=Rare\n"
            "Exec=/usr/bin/flatpak run io.github.dummerle.rare\n"
            "Categories=Game;\nStartupWMClass=rare\n"
            "Comment=Open source alternative for Epic Games Launcher\n")
    _atalho(tmp_path, "super-zsnes.desktop",
            "[Desktop Entry]\nType=Application\nName=Super ZSNES\n"
            "Exec=/casa/zsnes/rodar.sh\nCategories=Game;Emulator;\n"
            "StartupWMClass=SUPERZSNES\n")

    diretos = jl.jogos_diretos_dos_atalhos(pastas=[tmp_path])

    assert [j.chave for j in diretos] == ["SUPERZSNES"]
    assert diretos[0].lancador == jl.LANCADOR_DIRETO


def test_a_aba_perfis_responde_o_nome_do_jogo_do_heroic(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A PONTA, e ela é a queixa dela — medida nas funções REAIS da aba.**"""
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    jl._NOMES_DAS_JANELAS = None
    #: `identidade_de_janela`: sem umu-id e sem appid, um binário que NÃO é
    nativo = dict(BAIXADO, app_name="nativo", title="Celeste",
                  install={"executable": "Celeste.x86_64", "is_dlc": False})
    _heroic(tmp_path, [BAIXADO, nativo])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: de_verdade(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: assinar(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {"3357650": "PRAGMATA"})

    assert a10._jogo_reconhecido("steam_app_1088850") == (
        "Marvel's Guardians of the Galaxy", False)
    assert a10._jogo_reconhecido("3357650") == ("PRAGMATA", False)

    prof = SimpleNamespace(name="Perfil",
                           match=from_simple_choice("janela", "steam_app_1088850"))
    assert a10._agora_vale_em(prof, "steam_app_1088850").endswith(
        "· Marvel's Guardians of the Galaxy")

    html = a10._html_dos_jogos()
    assert ('<option value="steam_app_1088850" '
            'label="Marvel\'s Guardians of the Galaxy"></option>') in html
    assert '<option value="3357650" label="PRAGMATA · 3357650">' in html

    # `steam_game`; e `from_simple_choice("steam_game", "1088850")` produz
    assert a10._forma_do_que_ela_escolheu("steam_app_1088850") == "steam_game"
    assert a10._forma_do_que_ela_escolheu("Celeste.x86_64") == "janela"
    assert a10._forma_do_que_ela_escolheu("3357650") == "steam_game"
    assert a10._forma_do_que_ela_escolheu("Cyberpunk2077.exe") == "game"
    assert (from_simple_choice("steam_game", "1088850").window_class
            == from_simple_choice("janela", "steam_app_1088850").window_class
            == ["steam_app_1088850"])


def test_o_botao_detectar_nomeia_o_jogo_do_heroic_que_acabou_de_gravar(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**O GESTO INTEIRO, pelo botão — e é a foto dela, com o outro desfecho.**"""
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis as a10
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    jl._NOMES_DAS_JANELAS = None
    #: `identidade_de_janela`: sem umu-id e sem appid, um binário que NÃO é
    nativo = dict(BAIXADO, app_name="nativo", title="Celeste",
                  install={"executable": "Celeste.x86_64", "is_dlc": False})
    _heroic(tmp_path, [BAIXADO, nativo])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: de_verdade(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: assinar(
        lar=tmp_path, pastas=[tmp_path]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {})
    monkeypatch.setattr(a10, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10, "_ESCOLHIDO", "", raising=False)

    todos = [Profile(name="Perfil", match=MatchAny(), priority=100)]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(loader, "load_profile", lambda *a, **k: todos[0])
    monkeypatch.setattr(loader, "save_profile", lambda p, *a, **k: todos.__setitem__(0, p))

    class _Ponte:
        def profile_switch(self, nome: str) -> bool:
            return True

        def profile_reaplicar(self, nome: str) -> bool:
            return True

        def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
            return True

    ctx = Contexto(state={"active_profile": "Perfil",
                          "window_detect_last_class": "steam_app_1088850"},
                   mesa=[], conectados=[], estados={})

    fora = a10.detectar(ctx, {}, _Ponte())

    assert list(todos[0].match.window_class) == ["steam_app_1088850"]
    assert fora["mesa"]["editor.jogo"] == "1088850"
    frase = str(fora.get("relato") or "")
    assert frase.endswith("· Marvel's Guardians of the Galaxy"), frase
