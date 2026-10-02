"""O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01 — o censo responde pelo lançador"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import jogos_locais as jl
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

HEROIC = ".var/app/com.heroicgameslauncher.hgl/config/heroic"
LUTRIS_ID = "net.lutris.Lutris"


def plantar_o_registro(casa: Path, jogos: Iterable[str] | Mapping[str, Mapping[str, object]],
                       loja: str = "legendary") -> Path:
    """Acrescenta estes jogos ao registro dos instalados da loja, na forma do"""
    extras = (({j: {} for j in jogos}) if not isinstance(jogos, Mapping)
              else {j: dict(v) for j, v in jogos.items()})
    if loja == "legendary":
        alvo = casa / "legendaryConfig/legendary/installed.json"
        atual = json.loads(alvo.read_text(encoding="utf-8")) if alvo.is_file() else {}
        for app, extra in extras.items():
            atual[app] = {"app_name": app, "is_dlc": False, "platform": "Windows", **extra}
    elif loja == "gog":
        alvo = casa / "gog_store/installed.json"
        atual = (json.loads(alvo.read_text(encoding="utf-8")) if alvo.is_file()
                 else {"installed": []})
        atual["installed"] += [{"appName": app, "platform": "windows", "is_dlc": False,
                                **extra} for app, extra in extras.items()]
    elif loja == "nile":
        alvo = casa / "nile_config/nile/installed.json"
        atual = json.loads(alvo.read_text(encoding="utf-8")) if alvo.is_file() else []
        atual += [{"id": app, "version": "1", **extra} for app, extra in extras.items()]
    else:  # pragma: no cover - erro de quem escreve a régua
        raise ValueError(loja)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(atual), encoding="utf-8")
    return alvo


def _escrever(caminho: Path, dado: object) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dado), encoding="utf-8")


@pytest.fixture
def maquina(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Uma máquina sem lançador nenhum: o `PATH` só com uma pasta de comandos"""
    lar = tmp_path / "lar"
    lar.mkdir()
    comandos = tmp_path / "bin"
    comandos.mkdir()
    sistema = tmp_path / "usr/share/applications"
    sistema.mkdir(parents=True)
    exports = lar / ".local/share/flatpak/exports/share/applications"
    exports.mkdir(parents=True)
    monkeypatch.setenv("PATH", str(comandos))
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [exports, sistema])
    raiz = tmp_path / "flatpak-do-sistema"
    raiz.mkdir()
    return {"lar": lar, "comandos": comandos, "sistema": sistema, "exports": exports,
            "raiz": raiz}


def _comando(maquina: dict[str, Path], nome: str) -> None:
    alvo = maquina["comandos"] / nome
    alvo.write_text("#!/bin/sh\n", encoding="utf-8")
    alvo.chmod(0o755)


def _flatpak_instalado(lar: Path, app_id: str) -> None:
    meta = lar / ".local/share/flatpak/app" / app_id / "current/active"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "metadata").write_text(f"[Application]\nname={app_id}\n", encoding="utf-8")


def test_o_registro_de_cada_loja_diz_o_instalado(tmp_path: Path) -> None:
    """A GOG com `is_installed: false` na biblioteca (o `refresh()` grava assim)"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/legendary_library.json", {"library": [
        {"app_name": "epic1", "title": "Da Epic", "is_installed": False, "install": {}}]})
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "1207658924", "title": "Da GOG", "is_installed": False,
         "install": {"is_dlc": False}}]})
    _escrever(casa / "store_cache/nile_library.json", {"library": [
        {"app_name": "amzn1.adg.product.x", "title": "Da Amazon", "is_installed": False}]})
    plantar_o_registro(casa, ["epic1"])
    plantar_o_registro(casa, ["1207658924"], loja="gog")
    plantar_o_registro(casa, ["amzn1.adg.product.x"], loja="nile")

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert {j.loja: j.instalado for j in b.jogos} == {
        "Epic": True, "GOG": True, "Amazon": True}, b.jogos
    assert b.erros == []
    assert b.resumo == "3 jogos na biblioteca · 3 instalados"


def test_o_dialogo_aberto_nao_instala(tmp_path: Path) -> None:
    """A chave no `legendary_install_info.json` (o diálogo de instalar que ela"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/legendary_library.json", {"library": [
        {"app_name": "baixado", "title": "Baixado", "is_installed": True},
        {"app_name": "so-o-dialogo", "title": "Só o diálogo", "is_installed": False}]})
    _escrever(casa / "store_cache/legendary_install_info.json", {
        "baixado": {"manifest": {}}, "so-o-dialogo": {"manifest": {}},
        "__timestamp": {"baixado": "x", "so-o-dialogo": "x"}})
    plantar_o_registro(casa, ["baixado"])

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert {j.chave: j.instalado for j in b.jogos} == {
        "baixado": True, "so-o-dialogo": False}
    assert b.resumo == "2 jogos na biblioteca · 1 instalado"


@pytest.fixture
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local/share"))
    lx._DIVIDIDOS_DITOS.clear()
    return lar


def _o_prefixo_do_estudo(lar: Path) -> tuple[Path, Path]:
    """O lar do estudo: A (Epic, instalado), E (Epic, instalado depois da última"""
    casa = lar / HEROIC
    prefixo = lar / "Games/Heroic/Prefixes/default/dividido"
    (prefixo / "pfx").mkdir(parents=True)
    _escrever(casa / "config.json", {"defaultSettings": {}})
    a, e, f, g = "aaaa1111jogoa", "eeee2222jogoe", "ffff3333jogof", "1111111111"
    for app in (a, e, g):
        _escrever(casa / "GamesConfig" / f"{app}.json", {app: {"winePrefix": str(prefixo)}})
    (prefixo / "installed_games").write_text(json.dumps([a, e, g]))
    _escrever(casa / "store_cache/legendary_library.json", {"library": [
        {"app_name": a, "title": "Jogo A", "is_installed": True, "install": {}},
        {"app_name": e, "title": "Jogo E", "is_installed": False, "install": {}},
        {"app_name": f, "title": "Jogo F", "is_installed": False, "install": {}}]})
    _escrever(casa / "store_cache/legendary_install_info.json",
              {a: {"manifest": {}}, f: {"manifest": {}}, "__timestamp": {a: "x", f: "x"}})
    plantar_o_registro(casa, {a: {"install_path": str(lar / "Games/A")},
                              e: {"install_path": str(lar / "Games/E")}})
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": g, "title": "Jogo G", "is_installed": False,
         "install": {"is_dlc": False}}]})
    plantar_o_registro(casa, {g: {"install_path": str(lar / "Games/G")}}, loja="gog")
    (casa / "store_cache/nile_library.json").write_text("{}")
    plantar_o_registro(casa, [], loja="nile")
    _escrever(lx.caminho(lar / ".config"), {"formato": 1, "jogos": [{
        "chave": "heroic_" + a, "lancador": "Heroic", "nome": "Jogo A", "quando": "",
        "heroic": [{"arquivo": str(casa / "GamesConfig" / f"{a}.json"), "app": a,
                    "prefixo": str(prefixo)}]}]})
    return casa, prefixo


def test_o_prefixo_dividido_fica_de_ponta_a_ponta(_lar: Path) -> None:
    """E e G moram no prefixo de A, instalados por outras vias que não a"""
    casa, prefixo = _o_prefixo_do_estudo(_lar)

    assert lx._moradores(prefixo.resolve(), casa) == {
        "aaaa1111jogoa", "eeee2222jogoe", "1111111111"}
    assert prefixo.resolve() not in lx.prefixos_excluidos(_lar / ".config"), (
        "E e G, que ela não excluiu, perderam o device KS")


def _dividido(lar: Path) -> tuple[Path, Path]:
    """A (excluído) e B no mesmo prefixo, os dois na biblioteca da Epic."""
    casa = lar / HEROIC
    prefixo = lar / "Games/Heroic/Prefixes/AB"
    (prefixo / "pfx").mkdir(parents=True)
    _escrever(casa / "config.json", {"defaultSettings": {}})
    (prefixo / "installed_games").write_text(json.dumps(["A", "B"]))
    _escrever(casa / "store_cache/legendary_library.json", {"library": [
        {"app_name": "A", "title": "A", "is_installed": True},
        {"app_name": "B", "title": "B", "is_installed": True}]})
    _escrever(lx.caminho(lar / ".config"), {"formato": 1, "jogos": [{
        "chave": "heroic_A", "lancador": "Heroic", "nome": "A", "quando": "",
        "heroic": [{"arquivo": str(casa / "GamesConfig/A.json"), "app": "A",
                    "prefixo": str(prefixo)}]}]})
    return casa, prefixo


def test_o_registro_ausente_sem_instalado_e_nenhum_instalado(tmp_path: Path) -> None:
    """Sem o registro e sem `is_installed` na biblioteca: ninguém daquela loja"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "g1", "title": "Só na conta", "is_installed": False}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert [(j.chave, j.instalado) for j in b.jogos] == [("g1", False)]
    assert b.erros == []


@pytest.mark.parametrize("forma", ["ausente-com-instalado", "torto", "forma-errada"])
def test_o_registro_que_nao_responde_nao_tira_ninguem(_lar: Path, forma: str) -> None:
    """O registro ausente com a biblioteca dizendo `is_installed: true`, o que"""
    casa, prefixo = _dividido(_lar)
    registro = casa / "legendaryConfig/legendary/installed.json"
    if forma == "torto":
        registro.parent.mkdir(parents=True)
        registro.write_text('{"A": {', encoding="utf-8")
    elif forma == "forma-errada":
        _escrever(registro, [["A", "Windows"]])

    b = censo._heroic(casa)

    assert b.erros, f"{forma}: o censo não disse que não leu o registro"
    assert lx._moradores(prefixo.resolve(), casa) == {"A", "B"}
    assert prefixo.resolve() not in lx.prefixos_excluidos(_lar / ".config"), (
        f"{forma}: B, que ela não excluiu, perdeu o device KS")


def test_a_dlc_instalada_depois_da_releitura_nao_e_jogo(tmp_path: Path) -> None:
    """A DLC no `installed.json` com `is_dlc: true`, e sem `install` na"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/legendary_library.json", {"library": [
        {"app_name": "jogo", "title": "O Jogo", "is_installed": False, "install": {}},
        {"app_name": "dlc", "title": "A Trilha", "is_installed": False, "install": {}}]})
    plantar_o_registro(casa, {
        "jogo": {"install_path": "/jogos/o-jogo", "executable": "bin/jogo.exe"},
        "dlc": {"install_path": "/jogos/o-jogo", "is_dlc": True}})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.resumo == "1 jogo na biblioteca · 1 instalado"
    assert [(j.caminho, j.executavel) for j in b.jogos] == [
        (Path("/jogos/o-jogo"), "bin/jogo.exe")]


def test_a_assinatura_ve_o_registro(tmp_path: Path) -> None:
    """Reescrever o `gog_store/installed.json` muda a `assinatura_das_bibliotecas`:"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "g1", "title": "G", "is_installed": False}]})
    plantar_o_registro(casa, [], loja="gog")
    antes = censo.assinatura_das_bibliotecas(tmp_path)

    plantar_o_registro(casa, ["g1"], loja="gog")

    assert censo.assinatura_das_bibliotecas(tmp_path) != antes, (
        "instalar um jogo da GOG não mudou a assinatura")
    assert censo.biblioteca_de("Heroic", lar=tmp_path).instalados


def _banco(dados: Path, jogos: Iterable[str], *, sem: tuple[str, ...] = ()) -> None:
    """O `pga.db` com as 23 colunas do 0.5.22 (menos as de ``sem``), e um jogo"""
    from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import _ESQUEMA

    dados.mkdir(parents=True, exist_ok=True)
    colunas = _ESQUEMA[_ESQUEMA.index("(") + 1:_ESQUEMA.rindex(")")].split(", ")
    colunas = [c for c in colunas if c.split()[0] not in sem]
    con = sqlite3.connect(dados / "pga.db")
    with con:
        con.execute(f"CREATE TABLE games ({', '.join(colunas)})")
        for slug in jogos:
            con.execute("INSERT INTO games (name, slug, runner, installed, configpath) "
                        "VALUES (?,?,?,?,?)", (slug.title(), slug, "linux", 1, f"{slug}-1"))
            (dados / "games").mkdir(exist_ok=True)
            (dados / "games" / f"{slug}-1.yml").write_text("game: {}\n", encoding="utf-8")
    con.close()


def _misto(lar: Path, na_caixa: Iterable[str] = ()) -> tuple[Path, Path]:
    """O Lutris nativo com dois jogos e a pasta do Flatpak com o banco vazio"""
    nativo = lar / ".local/share/lutris"
    flatpak = lar / ".var/app" / LUTRIS_ID / "data/lutris"
    _banco(nativo, ["jogo-um", "jogo-dois"])
    _banco(flatpak, na_caixa)
    return nativo, flatpak


@pytest.mark.parametrize("como", ["pelo-path", "pelo-atalho-do-sistema"])
def test_o_lutris_nativo_instalado_vence_a_sobra_do_flatpak(
        maquina: dict[str, Path], como: str) -> None:
    """O nativo instalado (o `lutris` no `PATH`, ou só o"""
    lar = maquina["lar"]
    nativo, _ = _misto(lar)
    if como == "pelo-path":
        _comando(maquina, "lutris")
    else:
        (maquina["sistema"] / f"{LUTRIS_ID}.desktop").write_text("[Desktop Entry]\n")

    b = censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"])

    assert b.resumo == "2 jogos na biblioteca · 2 instalados", b
    assert b.onde == nativo


def test_o_atalho_so_nos_exports_e_o_flatpak(maquina: dict[str, Path]) -> None:
    """O `net.lutris.Lutris.desktop` só na pasta de exports do Flatpak, e o"""
    lar = maquina["lar"]
    _, flatpak = _misto(lar)
    (maquina["exports"] / f"{LUTRIS_ID}.desktop").write_text("[Desktop Entry]\n")
    _flatpak_instalado(lar, LUTRIS_ID)

    b = censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"])

    assert (b.onde, b.resumo) == (flatpak, "A biblioteca está vazia.")


def test_com_os_dois_instalados_as_casas_se_somam(maquina: dict[str, Path]) -> None:
    """Os dois Lutris instalados: o cartão soma as duas bibliotecas, e cada jogo"""
    lar = maquina["lar"]
    nativo, flatpak = _misto(lar, ["jogo-da-caixa"])
    _comando(maquina, "lutris")
    _flatpak_instalado(lar, LUTRIS_ID)

    b = censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"])

    assert {j.chave: j.configuracao for j in b.jogos} == {
        "jogo-um": nativo / "games/jogo-um-1.yml",
        "jogo-dois": nativo / "games/jogo-dois-1.yml",
        "jogo-da-caixa": flatpak / "games/jogo-da-caixa-1.yml"}


def test_sem_programa_instalado_vale_o_flatpak_primeiro(maquina: dict[str, Path]) -> None:
    """Nenhum dos dois instalado e as duas pastas no disco: a regra de antes."""
    lar = maquina["lar"]
    _, flatpak = _misto(lar)

    assert censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"]).onde == flatpak


def test_o_heroic_nativo_instalado_vence_a_sobra_do_flatpak(maquina: dict[str, Path]) -> None:
    """O mesmo cenário misto no Heroic: o nativo instalado e a casa do Flatpak"""
    lar = maquina["lar"]
    nativo = lar / ".config/heroic"
    _escrever(nativo / "store_cache/legendary_library.json", {"library": [
        {"app_name": "n1", "title": "Nativo", "is_installed": True}]})
    plantar_o_registro(nativo, ["n1"])
    _escrever(lar / HEROIC / "store_cache/legendary_library.json", {"library": []})
    _comando(maquina, "heroic")

    b = censo.biblioteca_de("Heroic", lar=lar, raiz_sistema=maquina["raiz"])

    assert (b.onde, b.resumo) == (nativo, "1 jogo na biblioteca · 1 instalado")
    assert censo.pastas_lidas("Heroic", lar, raiz_sistema=maquina["raiz"]) == (nativo,)


def test_o_banco_sem_as_colunas_novas_da_os_jogos(tmp_path: Path) -> None:
    """Um banco sem `service`, `service_id` e `discord_id` (que nenhum Lutris"""
    _banco(tmp_path / ".local/share/lutris", ["jogo-um", "jogo-dois"],
           sem=("service", "service_id", "discord_id"))

    b = censo.biblioteca_de("Lutris", lar=tmp_path)

    assert b.erros == []
    assert b.resumo == "2 jogos na biblioteca · 2 instalados"
    assert {j.appid_da_steam for j in b.jogos} == {""}


def test_o_banco_sem_slug_e_erro_e_nao_vazio(tmp_path: Path) -> None:
    """Sem o `name` ou o `slug` não há jogo: o censo diz o erro."""
    dados = tmp_path / ".local/share/lutris"
    dados.mkdir(parents=True)
    con = sqlite3.connect(dados / "pga.db")
    with con:
        con.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT)")
    con.close()

    assert censo.biblioteca_de("Lutris", lar=tmp_path).erros


def test_as_casas_nativas_seguem_o_xdg(tmp_path: Path) -> None:
    """Com o `XDG_CONFIG_HOME` e o `XDG_DATA_HOME` fora do padrão (e fora do"""
    lar, config, dados = tmp_path / "lar", tmp_path / "fora/cfg", tmp_path / "fora/dados"
    lutris = dados / "lutris"
    from tests.unit.test_o_censo_dos_lancadores_le_a_biblioteca import _banco_do_lutris

    _banco_do_lutris(lutris)
    (config / "lutris/games").mkdir(parents=True)
    (config / "lutris/games/jogo-x-1.yml").write_text(
        "wine:\n  version: GE-Proton9-1\n", encoding="utf-8")
    proton = lar / ".steam/steam/compatibilitytools.d/GE-Proton9-1/proton"
    proton.parent.mkdir(parents=True)
    proton.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    _escrever(config / "heroic/store_cache/legendary_library.json", {"library": [
        {"app_name": "a1", "title": "Jogo A", "is_installed": True}]})
    plantar_o_registro(config / "heroic", ["a1"])

    lt = censo.biblioteca_de("Lutris", lar=lar, xdg_config=config, xdg_data=dados)
    hr = censo.biblioteca_de("Heroic", lar=lar, xdg_config=config, xdg_data=dados)

    assert (lt.onde, [j.classe_de_janela for j in lt.jogos]) == (
        config / "lutris", ["steam_app_70400"]), lt
    assert (hr.onde, hr.resumo) == (config / "heroic", "1 jogo na biblioteca · 1 instalado")
    assert censo.biblioteca_de("Lutris", lar=lar).estado == censo.NUNCA_ABERTO, (
        "o lar de mentira sem XDG leu o XDG de outro lugar")


def test_o_lar_de_mentira_sem_xdg_le_o_dele(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O lar dado sem XDG fica com o `<lar>/.config`, mesmo com o ambiente"""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "outro"))
    _escrever(tmp_path / ".config/heroic/store_cache/legendary_library.json",
              {"library": [{"app_name": "a1", "title": "Nativo"}]})

    assert censo.biblioteca_de("Heroic", lar=tmp_path).onde == tmp_path / ".config/heroic"


def test_o_censo_a_carona_e_a_copia_avulsa_acham_a_mesma_casa(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o XDG desviado no ambiente (o lar de verdade, ``lar=None``), a carona"""
    lar, config, dados = tmp_path / "lar", tmp_path / "cfg", tmp_path / "dados"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_DATA_HOME", str(dados))
    casa = config / "heroic"
    do_heroic = tmp_path / "prefixos/do-heroic"
    (do_heroic / "pfx").mkdir(parents=True)
    (do_heroic / "pfx/system.reg").write_text("WINE REGISTRY Version 2\n")
    _escrever(casa / "config.json", {"defaultSettings": {}})
    _escrever(casa / "GamesConfig/a1.json", {"a1": {"winePrefix": str(do_heroic)}})
    do_lutris = dados / "lutris/jogo-x"
    (do_lutris / "pfx").mkdir(parents=True)
    (do_lutris / "pfx/system.reg").write_text("WINE REGISTRY Version 2\n")
    _banco(dados / "lutris", [])

    assert censo.pastas_lidas("Heroic") == (casa,)
    assert cpe._pasta_do_heroic(None) == casa
    assert cpe.estradas_possiveis(lar) == [(casa / "config.json", cpe.HEROIC_CONFIG)]
    assert censo.pastas_lidas("Lutris") == (dados / "lutris",)
    assert set(cv.prefixos_dos_lancadores()) == {do_heroic, do_lutris}, (
        "a cópia avulsa das camadas não achou as casas do XDG")
    assert not hasattr(cpe, "_PASTAS_DO_HEROIC"), "a cópia das casas do Heroic voltou à carona"


def test_a_copia_avulsa_com_lar_dado_fica_no_lar(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `camadas_vulkan` com um lar dado não lê o XDG do ambiente (o molde de"""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "outro"))
    prefixo = tmp_path / ".local/share/lutris/jogo-y"
    (prefixo / "pfx").mkdir(parents=True)
    (prefixo / "pfx/system.reg").write_text("WINE REGISTRY Version 2\n")

    assert cv.prefixos_dos_lancadores(tmp_path) == [prefixo]


def test_o_redistribuivel_da_gog_sem_registro_nao_e_contradicao(tmp_path: Path) -> None:
    """A conta da GOG ligada e nenhum jogo baixado: o Heroic instala o"""
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "gog-redist", "title": "Galaxy Common Redistributables",
         "is_installed": True, "install": {"is_dlc": True}},
        {"app_name": "g1", "title": "Só na conta", "is_installed": False}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.erros == [], b.erros
    assert [(j.chave, j.instalado) for j in b.jogos] == [("g1", False)]


def test_os_dois_heroic_da_mesma_conta_nao_contam_em_dobro(maquina: dict[str, Path]) -> None:
    """Os dois Heroic instalados, logados na mesma conta: a biblioteca de cada"""
    lar = maquina["lar"]
    nativo, caixa = lar / ".config/heroic", lar / HEROIC
    for casa in (nativo, caixa):
        _escrever(casa / "store_cache/legendary_library.json", {"library": [
            {"app_name": "e1", "title": "Um"}, {"app_name": "e2", "title": "Dois"}]})
    plantar_o_registro(nativo, [])
    plantar_o_registro(caixa, ["e2"])
    _comando(maquina, "heroic")
    _flatpak_instalado(lar, "com.heroicgameslauncher.hgl")

    b = censo.biblioteca_de("Heroic", lar=lar, raiz_sistema=maquina["raiz"])

    assert b.resumo == "2 jogos na biblioteca · 1 instalado", b.resumo
    assert len(censo.bibliotecas_por_casa("Heroic", lar, raiz_sistema=maquina["raiz"])) == 2


def _dois_heroic(maquina: dict[str, Path], monkeypatch: pytest.MonkeyPatch
                 ) -> tuple[Path, Path, Path]:
    """Os dois Heroic instalados no lar de verdade de mentira (``HOME``), cada"""
    lar = maquina["lar"]
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local/state"))
    ponte = lar.parent / "launch_env"
    ponte.mkdir()
    (ponte / "default.env").write_text(
        "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6\n"
        "PROTON_DISABLE_HIDRAW=0x054c/0x0ce6\n")
    tudo = [{"key": k, "value": v} for k, v in cpe.ambiente_da_carona(ponte).items()]
    sem_o_hidraw = [p for p in tudo if p["key"] != "PROTON_DISABLE_HIDRAW"]
    nativo, caixa = lar / ".config/heroic", lar / HEROIC
    for casa, app, umu, globais in ((nativo, "nnnn", "umu-111", sem_o_hidraw),
                                    (caixa, "cccc", "umu-222", tudo)):
        _escrever(casa / "config.json", {"defaultSettings": {"enviromentOptions": globais}})
        _escrever(casa / "store_cache/legendary_library.json", {"library": [
            {"app_name": app, "title": f"Jogo {app[0].upper()}", "is_installed": True}]})
        _escrever(casa / "store_cache/umu.json", {f"legendary_{app}": umu})
        plantar_o_registro(casa, [app])
    _escrever(nativo / "GamesConfig/nnnn.json", {"nnnn": {"enviromentOptions": tudo}})
    _comando(maquina, "heroic")
    _flatpak_instalado(lar, "com.heroicgameslauncher.hgl")
    return nativo, caixa, ponte


def test_com_os_dois_heroic_a_carona_e_a_janela_seguem_a_casa_do_jogo(
        maquina: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """Os dois Heroic instalados: a carona tem uma estrada por casa, a cópia de"""
    nativo, caixa, ponte = _dois_heroic(maquina, monkeypatch)
    lar, atalhos = maquina["lar"], ("com.heroicgameslauncher.hgl",)

    estradas = cpe.estradas_do_cartao("heroic", atalhos, lar, maquina["raiz"])
    assert {e.arquivo for e in estradas} == {nativo / "config.json", caixa / "config.json"}
    assert cpe.jogos_do_heroic_pela_janela("steam_app_111", lar) == [
        nativo / "GamesConfig/nnnn.json"]
    assert cpe.jogos_do_heroic_pela_janela("steam_app_222", lar) == [
        caixa / "GamesConfig/cccc.json"]
    assert cpe.onde_falta_o_ambiente("heroic", atalhos, lar=lar, pasta_do_ambiente=ponte,
                                     raiz_sistema=maquina["raiz"]) == ()


def test_o_atalho_no_xdg_do_lar_acha_o_nativo(maquina: dict[str, Path]) -> None:
    """O `net.lutris.Lutris.desktop` só em `$XDG_DATA_HOME/applications` do lar"""
    lar = maquina["lar"]
    nativo, _ = _misto(lar)
    proprio = lar / ".local/share/applications"
    proprio.mkdir(parents=True)
    (proprio / f"{LUTRIS_ID}.desktop").write_text("[Desktop Entry]\n")

    b = censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"])

    assert (b.onde, b.resumo) == (nativo, "2 jogos na biblioteca · 2 instalados")


def test_a_carona_do_lutris_acha_o_proton_no_lar_de_quem_chama(tmp_path: Path) -> None:
    """O jogo do Lutris Flatpak com uma versão de Proton que mora no lar dado:"""
    from tests.unit.test_o_censo_dos_lancadores_le_a_biblioteca import _banco_do_lutris

    versao = "GE-Proton-da-regua-0210"
    dados = tmp_path / ".var/app" / LUTRIS_ID / "data/lutris"
    _banco_do_lutris(dados)
    yml = dados / "games/jogo-x-1.yml"
    yml.parent.mkdir(parents=True)
    yml.write_text(f"wine:\n  version: {versao}\n", encoding="utf-8")
    proton = tmp_path / ".steam/steam/compatibilitytools.d" / versao / "proton"
    proton.parent.mkdir(parents=True)
    proton.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    assert cpe._pelo_proton_por_yml(tmp_path) == {str(yml): True}
