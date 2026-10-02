"""O-CENSO-RESPONDE-COMO-O-LANCADOR-RESPONDE-01 — o censo responde pelo lançador
como o lançador responde (02/10/2026).

Quatro formas fixas que não eram a regra do lançador, medidas num lar de
mentira: o «instalado» do Heroic lido de um cache (o `*_install_info.json` e o
`is_installed` da biblioteca) no lugar do registro de cada loja; a primeira
casa que existe no lugar do programa instalado; as colunas de uma versão do
`pga.db`; e as casas nativas sem o XDG. Desde a costura dos Lançadores 3 a
primeira tirava o device KS de um prefixo em que moravam jogos que ela não
excluiu.

Todo dado é escrito na forma que o Heroic 2.22.3 e o Lutris 0.5.22 gravam (o
recorte está em `docs/process/estudos/2026-10-02-o-censo-responde-como-o-lancador-responde-01/`),
nunca lido da saída do censo. A máquina é de mentira também: o `PATH`, as
pastas de atalhos e a instalação do Flatpak do sistema são pastas do
`tmp_path`, e a resposta não depende de onde a régua roda (a suíte põe um
`lutris` e um `heroic` de mentira no `PATH`).

O ajudante :func:`plantar_o_registro` é o das réguas que plantavam
`is_installed: true` como a marca do instalado: elas passam a plantar o
registro, e a afirmação de cada uma não muda.
"""
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


# ---------------------------------------------------------------------------
# O ajudante: o registro de cada loja, na forma que o Heroic grava
# ---------------------------------------------------------------------------
def plantar_o_registro(casa: Path, jogos: Iterable[str] | Mapping[str, Mapping[str, object]],
                       loja: str = "legendary") -> Path:
    """Acrescenta estes jogos ao registro dos instalados da loja, na forma do
    Heroic 2.22.3 (`main.js` do `app.asar` dela, o `refreshInstalled` de cada
    loja): a Epic é o `installed.json` do legendary, um objeto pelo `app_name`;
    a GOG, ``{"installed": [{"appName": …}]}``; a Amazon, uma lista pelo `id`.

    ``jogos`` é a lista de chaves ou ``{chave: campos a mais}`` (o
    `install_path`, o `executable`, o `is_dlc` que o registro traz).
    """
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
    """Uma máquina sem lançador nenhum: o `PATH` só com uma pasta de comandos
    vazia, as pastas de atalhos do sistema vazias (uma delas a de exports do
    Flatpak do usuário), e a instalação do Flatpak do sistema vazia."""
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


# ---------------------------------------------------------------------------
# 1 · O instalado de cada loja é o registro dela
# ---------------------------------------------------------------------------
def test_o_registro_de_cada_loja_diz_o_instalado(tmp_path: Path) -> None:
    """A GOG com `is_installed: false` na biblioteca (o `refresh()` grava assim)
    e o jogo no `gog_store/installed.json`; a Epic no `installed.json` e fora do
    `install_info`; a Amazon pelo `id`. Os três são instalados.

    MORDIDA: o leitor de antes (a união do `install_info` com o `is_installed`
    da biblioteca) diz os três fora.
    """
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
    """A chave no `legendary_install_info.json` (o diálogo de instalar que ela
    abriu) e fora do registro não é instalado, e o `__timestamp` que o
    `CacheStore` grava junto não vira jogo.

    MORDIDA: devolver a leitura do `install_info` — o jogo do diálogo conta.
    """
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


# ---------------------------------------------------------------------------
# 2 · O prefixo dividido, de ponta a ponta
# ---------------------------------------------------------------------------
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
    """O lar do estudo: A (Epic, instalado), E (Epic, instalado depois da última
    releitura), G (GOG, instalado) e F (Epic, só o diálogo aberto); A, E e G no
    mesmo prefixo, e ela exclui A. Devolve ``(casa, prefixo)``."""
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
    """E e G moram no prefixo de A, instalados por outras vias que não a
    biblioteca: o prefixo FICA com o device KS e as camadas.

    MORDIDA: o censo de antes (o `install_info` e o `is_installed`) — E e G
    saem dos moradores, e o prefixo sai sem ela ter excluído nenhum dos dois.
    """
    casa, prefixo = _o_prefixo_do_estudo(_lar)

    assert lx._moradores(prefixo.resolve(), casa) == {
        "aaaa1111jogoa", "eeee2222jogoe", "1111111111"}
    assert prefixo.resolve() not in lx.prefixos_excluidos(_lar / ".config"), (
        "E e G, que ela não excluiu, perderam o device KS")


# ---------------------------------------------------------------------------
# 3 · O registro ausente e o torto
# ---------------------------------------------------------------------------
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
    """Sem o registro e sem `is_installed` na biblioteca: ninguém daquela loja
    é instalado, e a biblioteca segue lida, sem erro (o caso dela na GOG e na
    Amazon, que não têm jogo baixado).

    MORDIDA: o registro ausente lido como erro — o censo deixa de tirar
    morador em toda máquina com uma loja sem jogo.
    """
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "g1", "title": "Só na conta", "is_installed": False}]})

    b = censo.biblioteca_de("Heroic", lar=tmp_path)

    assert b.estado == censo.LIDO
    assert [(j.chave, j.instalado) for j in b.jogos] == [("g1", False)]
    assert b.erros == []


@pytest.mark.parametrize("forma", ["ausente-com-instalado", "torto", "forma-errada"])
def test_o_registro_que_nao_responde_nao_tira_ninguem(_lar: Path, forma: str) -> None:
    """O registro ausente com a biblioteca dizendo `is_installed: true`, o que
    não abre e o que não tem a forma do Heroic: o censo volta com erro, e a
    lista de exclusão não tira ninguém (B segue morando).

    MORDIDA: o torto (ou o ausente contraditório) lido como vazio — B sai dos
    moradores, e o prefixo de A sai do device KS com B dentro.
    """
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
    """A DLC no `installed.json` com `is_dlc: true`, e sem `install` na
    biblioteca (instalada depois da última releitura), não conta como jogo; o
    `install_path` e o `executable` do jogo vêm do registro.

    MORDIDA: o `dlc` lido só da biblioteca — o cartão diz um instalado a mais.
    """
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
    """Reescrever o `gog_store/installed.json` muda a `assinatura_das_bibliotecas`:
    sem isso, a aba Perfis seguiria com a resposta velha depois de uma
    instalação (a nota de `_FONTES`).

    MORDIDA: tirar os registros de `_FONTES["Heroic"]`.
    """
    casa = tmp_path / HEROIC
    _escrever(casa / "store_cache/gog_library.json", {"games": [
        {"app_name": "g1", "title": "G", "is_installed": False}]})
    plantar_o_registro(casa, [], loja="gog")
    antes = censo.assinatura_das_bibliotecas(tmp_path)

    plantar_o_registro(casa, ["g1"], loja="gog")

    assert censo.assinatura_das_bibliotecas(tmp_path) != antes, (
        "instalar um jogo da GOG não mudou a assinatura")
    assert censo.biblioteca_de("Heroic", lar=tmp_path).instalados


# ---------------------------------------------------------------------------
# 4 · As duas casas: vale a do programa instalado
# ---------------------------------------------------------------------------
def _banco(dados: Path, jogos: Iterable[str], *, sem: tuple[str, ...] = ()) -> None:
    """O `pga.db` com as 23 colunas do 0.5.22 (menos as de ``sem``), e um jogo
    nativo por slug, com o `.yml` dele."""
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
    """O Lutris nativo com dois jogos e a pasta do Flatpak com o banco vazio
    (ou com os jogos de ``na_caixa``)."""
    nativo = lar / ".local/share/lutris"
    flatpak = lar / ".var/app" / LUTRIS_ID / "data/lutris"
    _banco(nativo, ["jogo-um", "jogo-dois"])
    _banco(flatpak, na_caixa)
    return nativo, flatpak


@pytest.mark.parametrize("como", ["pelo-path", "pelo-atalho-do-sistema"])
def test_o_lutris_nativo_instalado_vence_a_sobra_do_flatpak(
        maquina: dict[str, Path], como: str) -> None:
    """O nativo instalado (o `lutris` no `PATH`, ou só o
    `net.lutris.Lutris.desktop` numa pasta de atalhos que não é a de exports
    do Flatpak, o caso do serviço), e a pasta do Flatpak de sobra: o cartão
    diz os dois jogos do nativo.

    MORDIDA: o Flatpak primeiro, sempre — «A biblioteca está vazia.»; e o
    nativo achado só pelo `PATH` — o caso do serviço volta ao «vazia».
    """
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
    """O `net.lutris.Lutris.desktop` só na pasta de exports do Flatpak, e o
    Flatpak instalado: vale o Flatpak (o mesmo nome nas duas instalações, e é
    a pasta que diz qual).

    MORDIDA: contar o atalho dos exports como o nativo — vale o nativo.
    """
    lar = maquina["lar"]
    _, flatpak = _misto(lar)
    (maquina["exports"] / f"{LUTRIS_ID}.desktop").write_text("[Desktop Entry]\n")
    _flatpak_instalado(lar, LUTRIS_ID)

    b = censo.biblioteca_de("Lutris", lar=lar, raiz_sistema=maquina["raiz"])

    assert (b.onde, b.resumo) == (flatpak, "A biblioteca está vazia.")


def test_com_os_dois_instalados_as_casas_se_somam(maquina: dict[str, Path]) -> None:
    """Os dois Lutris instalados: o cartão soma as duas bibliotecas, e cada jogo
    aponta o `.yml` da própria casa.

    MORDIDA: uma casa só — o cartão perde os jogos de uma delas.
    """
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
    """O mesmo cenário misto no Heroic: o nativo instalado e a casa do Flatpak
    de sobra — lê-se o nativo, e a carona escreve nele.

    MORDIDA: o Flatpak primeiro, sempre.
    """
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


# ---------------------------------------------------------------------------
# 5 · As colunas que faltam
# ---------------------------------------------------------------------------
def test_o_banco_sem_as_colunas_novas_da_os_jogos(tmp_path: Path) -> None:
    """Um banco sem `service`, `service_id` e `discord_id` (que nenhum Lutris
    novo abriu) dá os dois jogos, com o degrau 2 da chave de janela vazio.

    MORDIDA: a lista fixa de colunas — «no such column: service», e o cartão
    diz «A biblioteca está vazia.».
    """
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


# ---------------------------------------------------------------------------
# 6 · O XDG
# ---------------------------------------------------------------------------
def test_as_casas_nativas_seguem_o_xdg(tmp_path: Path) -> None:
    """Com o `XDG_CONFIG_HOME` e o `XDG_DATA_HOME` fora do padrão (e fora do
    lar), o Lutris e o Heroic nativos são lidos; o `pga.db` vem do
    `$XDG_DATA_HOME/lutris` com a configuração em `$XDG_CONFIG_HOME/lutris`; e
    o Proton do jogo se acha no lar, não em `/`.

    MORDIDA: as casas fixas (`<lar>/.config` e `<lar>/.local/share`) — «Abra
    Lutris uma vez…» e «Abra Heroic uma vez…» com os dois cheios.
    """
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
    """O lar dado sem XDG fica com o `<lar>/.config`, mesmo com o ambiente
    apontando o XDG para outro lugar (a suíte o isola em `tmp_path/.xdg/`).

    MORDIDA: ler o XDG do ambiente com um lar explícito — a régua lê a casa
    errada e passa vazia.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "outro"))
    _escrever(tmp_path / ".config/heroic/store_cache/legendary_library.json",
              {"library": [{"app_name": "a1", "title": "Nativo"}]})

    assert censo.biblioteca_de("Heroic", lar=tmp_path).onde == tmp_path / ".config/heroic"


# ---------------------------------------------------------------------------
# 7 · Uma regra só para as casas
# ---------------------------------------------------------------------------
def test_o_censo_a_carona_e_a_copia_avulsa_acham_a_mesma_casa(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o XDG desviado no ambiente (o lar de verdade, ``lar=None``), a carona
    (`cura_por_estrada._pasta_do_heroic` e a rede do desfazer), o censo e a
    cópia avulsa do `camadas_vulkan` acham a mesma casa do Heroic e a mesma
    raiz do Lutris.

    MORDIDA: devolver a cópia `_PASTAS_DO_HEROIC` à carona (a carona não acha o
    Heroic nativo), ou as raízes fixas ao `camadas_vulkan` (os prefixos somem).
    """
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
    """O `camadas_vulkan` com um lar dado não lê o XDG do ambiente (o molde de
    `a_steam_instalou_as_camadas`), como o censo."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "outro"))
    prefixo = tmp_path / ".local/share/lutris/jogo-y"
    (prefixo / "pfx").mkdir(parents=True)
    (prefixo / "pfx/system.reg").write_text("WINE REGISTRY Version 2\n")

    assert cv.prefixos_dos_lancadores(tmp_path) == [prefixo]
