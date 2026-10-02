"""A-EXCLUSAO-MORA-NA-CAMADA-DO-JOGO-01 — as réguas.

A exclusão é de UM jogo, e ela agia (ou deixava de agir) numa camada que é de
vários jogos. Medido em 02/10/2026 num lar de mentira, na integração:

* **o Lutris Flatpak:** a caixa `net.lutris.Lutris` é uma só para todos os
  jogos dele; com um jogo excluído ela seguia com as 9 variáveis da ponte, e o
  jogo (Modo Nativo em foco) herdava o `SDL_GAMECONTROLLER_IGNORE_DEVICES` e o
  `PROTON_DISABLE_HIDRAW` — zero controles. A camada que só ele lê é o
  `system.env` do `.yml` dele, que o Lutris põe por cima da caixa;
* **o prefixo do Heroic dividido:** com A e B no mesmo `winePrefix` e só A
  excluído, a carona do device KS pulava o prefixo e B perdia a háptica;
* **o «Corrigir Vulkan» comparava o prefixo de fora da Steam pelo NOME da
  pasta**, e pulava também o de outra casa com o mesmo nome.

NENHUMA RÉGUA LÊ A PRÓPRIA SAÍDA: as do Lutris leem o `.yml` e a caixa pelo
disco (com o PyYAML, o leitor do Lutris), a do prefixo pela carona do KS de
verdade (`launch_env._device_ks_nos_lancadores`), a do Vulkan pelo
`curar_todos`, a do censo pela `classe_de_janela`, a dos formatos pelos
arquivos de cada formato.

TUDO NUM LAR DE MENTIRA: o `HOME` e os `XDG_*` de cada teste.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tomllib
from pathlib import Path

import pytest
import structlog
import yaml

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from tests.unit.test_a_cura_do_engasgo_alcanca_todos_os_prefixos import EPIC
from tests.unit.test_a_cura_do_engasgo_alcanca_todos_os_prefixos import (
    _registro as _registro_com_camadas,
)
from tests.unit.test_o_censo_responde_como_o_lancador_responde import plantar_o_registro

RAIZ = Path(__file__).resolve().parents[2]

#: A ponte que o daemon publica com a emulação ligada — as 9 variáveis.
_PONTE = {
    "SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0ce6",
    "SDL_JOYSTICK_HIDAPI": "0",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS": "0",
    "PROTON_DISABLE_HIDRAW": "0x054C/0x0CE6",
    "__GL_SHADER_DISK_CACHE": "1",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP": "1",
    "SDL_ACCELEROMETER_AS_JOYSTICK": "0",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE": "1",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO": "1",
}

#: O jogo da GOG no Lutris, e a linha dele no `umu-games.json` (a mesma forma
#: do arquivo dela: 314 jogos, `store`/`appid`/`umu_id`).
_GOG_APPID = "1441875624"
_UMU = "umu-70400"
_JANELA = "steam_app_70400"
_LUTRIS = "net.lutris.Lutris"

#: O «NÃO VEIO» DE CADA LEITOR, ESCRITO À MÃO A PARTIR DO FONTE DE CADA UM, e
#: nunca derivado do escritor (`cura_por_estrada.nao_veio`):
#:
#: * as `SDL_*` booleanas: `SDL_GetHintBoolean` devolve o padrão com o valor
#:   vazio, como ausente — medido em 02/10/2026 no SDL2 2.32.10 do runtime da
#:   Steam, por `ctypes`, sem iniciar subsistema;
#: * a lista `SDL_GAMECONTROLLER_IGNORE_DEVICES` vazia não ignora aparelho
#:   nenhum (lido no SDL2);
#: * as `PROTON_*`: o script do Proton lê as opções por `nonzero`
#:   (`len(s) > 0 and s != "0"`, GE-Proton10-34 `proton:167-168`): vazio é
#:   desligado, como a ausência.
_NAO_VEIO_DO_LEITOR = {
    "SDL_GAMECONTROLLER_IGNORE_DEVICES": "",
    "SDL_JOYSTICK_HIDAPI": "",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS": "",
    "SDL_ACCELEROMETER_AS_JOYSTICK": "",
    "PROTON_DISABLE_HIDRAW": "",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE": "",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO": "",
}
#: O leitor do par é o driver fechado da NVIDIA, e o efeito do `''` não está
#: medido: o par fica fora do `.yml` (decisão por delegação, a validar por ela).
_SEM_MEDIDA = {"__GL_SHADER_DISK_CACHE", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"}


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE.items()))
    return lar


def _md5(caminho: Path) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def _flatpak(lar: Path, app_id: str) -> None:
    meta = lar / ".local/share/flatpak/app" / app_id / "current" / "active"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "metadata").write_text(f"[Application]\nname={app_id}\n")


#: O `games` do `pga.db` com as 23 colunas do Lutris 0.5.22 dela.
_ESQUEMA = (
    "CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, sortname TEXT, slug TEXT, "
    "installer_slug TEXT, parent_slug TEXT, platform TEXT, runner TEXT, executable TEXT, "
    "directory TEXT, updated DATETIME, lastplayed INTEGER, installed INTEGER, "
    "installed_at INTEGER, year INTEGER, configpath TEXT, has_custom_banner INTEGER, "
    "has_custom_icon INTEGER, has_custom_coverart_big INTEGER, playtime REAL, "
    "service TEXT, service_id TEXT, discord_id TEXT)"
)

#: O `.yml` que o Lutris grava ao instalar um jogo da GOG pelo runner `wine`.
_YML_DO_JOGO = (
    "game:\n"
    "  exe: /casa/Games/recettear/drive_c/GOG Games/Recettear/recettear.exe\n"
    "  prefix: /casa/Games/recettear\n"
    "system:\n"
    "  env:\n"
    "    MANGOHUD: '1'\n"
    "wine:\n"
    "  version: ge-proton\n"
)


def _lutris(casa_config: Path, casa_dados: Path, *, yml: str = _YML_DO_JOGO) -> Path:
    """Um Lutris com o jogo da GOG instalado; devolve o `.yml` do jogo."""
    casa_dados.mkdir(parents=True, exist_ok=True)
    if casa_config != casa_dados:
        casa_config.parent.mkdir(parents=True, exist_ok=True)
        casa_config.symlink_to(casa_dados)
    (casa_dados / "games").mkdir(exist_ok=True)
    umu = casa_dados / "runtime/umu-games/umu-games.json"
    umu.parent.mkdir(parents=True, exist_ok=True)
    umu.write_text(json.dumps([
        {"name": "Outro", "store": "egs", "appid": "x1", "notes": None, "umu_id": "umu-1"},
        {"name": "Recettear", "store": "gog", "appid": _GOG_APPID, "notes": None,
         "umu_id": _UMU}]))
    con = sqlite3.connect(casa_dados / "pga.db")
    with con:
        con.execute(_ESQUEMA)
        con.execute(
            "INSERT INTO games (name, slug, runner, executable, directory, installed, "
            "configpath, service, service_id) VALUES (?,?,?,?,?,?,?,?,?)",
            ("Recettear", "recettear", "wine", "recettear.exe", "/casa/Games/recettear",
             1, "recettear-1759370000", "gog", _GOG_APPID))
    con.close()
    alvo = casa_dados / "games" / "recettear-1759370000.yml"
    alvo.write_text(yml)
    return alvo


def _lutris_flatpak(lar: Path, **k: str) -> Path:
    _flatpak(lar, _LUTRIS)
    raiz = lar / ".var/app" / _LUTRIS
    return _lutris(raiz / "config/lutris", raiz / "data/lutris", **k)


def _lutris_nativo(lar: Path) -> Path:
    alvo = _lutris(lar / ".local/share/lutris", lar / ".local/share/lutris")
    (lar / ".config").mkdir(exist_ok=True)
    (lar / ".config/lutris").symlink_to(lar / ".local/share/lutris")
    return alvo


def _caixa(lar: Path) -> Path:
    return lar / ".local/share/flatpak/overrides" / _LUTRIS


def _carona(lar: Path) -> tuple[str, ...]:
    return cpe.curar_todas_as_estradas(lar=lar, raiz_sistema=lar.parent / "sistema")


def _env_do_yml(alvo: Path) -> dict[str, object]:
    dado = yaml.safe_load(alvo.read_text())
    env = (dado.get("system") or {}).get("env") or {}
    assert isinstance(env, dict), dado
    return env


def _nossas_na_caixa(lar: Path) -> dict[str, str]:
    linhas = _caixa(lar).read_text().splitlines()
    return {k: v for k, _, v in (x.partition("=") for x in linhas) if k in _PONTE}


# ---------------------------------------------------------------------------
# 1 · O jogo do Lutris sai pela camada dele
# ---------------------------------------------------------------------------
def test_o_jogo_do_lutris_sai_pela_camada_dele(_lar: Path) -> None:
    """MORDIDA: tire a escrita do `.yml` do `adicionar` e a régua reprova pelo
    nome do jogo — a caixa cheia chega ao jogo excluído."""
    yml = _lutris_flatpak(_lar)
    assert "lutris" in _carona(_lar)
    assert len(_nossas_na_caixa(_lar)) == 9
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    env = _env_do_yml(yml)
    for chave in ("SDL_GAMECONTROLLER_IGNORE_DEVICES", "PROTON_DISABLE_HIDRAW"):
        assert chave in env, (
            f"Recettear (Lutris Flatpak, excluído) herda da caixa {chave}="
            f"{_PONTE[chave]}: o `.yml` dele não cobre a caixa ({env})")
    assert len(_nossas_na_caixa(_lar)) == 9, "a caixa é de todos os jogos, e foi tocada"
    assert env.get("MANGOHUD") == "1", "o que é dela no `.yml` ficou"


def test_a_carona_mantem_o_yml_do_excluido(_lar: Path) -> None:
    """A exclusão veio antes de a caixa ter o nosso: a carona seguinte cobre.

    MORDIDA: tire o `_manter_os_ymls` do `curar_todas_as_estradas`.
    """
    yml = _lutris_flatpak(_lar)
    antes = yml.read_text()
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    assert yml.read_text() == antes, "sem o nosso na caixa, não há o que cobrir"
    _carona(_lar)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in _env_do_yml(yml)
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert yml.read_text() == antes, "a volta exata, com o registro que a carona anotou"


# ---------------------------------------------------------------------------
# 2 · O valor de cada chave é o «não veio» do leitor dela
# ---------------------------------------------------------------------------
def test_o_valor_de_cada_chave_e_o_nao_veio_do_leitor(_lar: Path) -> None:
    """MORDIDA: `None` no lugar do valor (o Lutris pula a chave nula,
    `monitored_command.py:141-142`), ou `''` no par da NVIDIA."""
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    env = _env_do_yml(yml)
    nossas = {k: v for k, v in env.items() if k in _PONTE}
    assert set(nossas) == set(_NAO_VEIO_DO_LEITOR), (
        f"o `.yml` cobre {sorted(nossas)}; o leitor de cada uma da caixa "
        f"pede {sorted(_NAO_VEIO_DO_LEITOR)}")
    for chave, valor in nossas.items():
        assert valor is not None, f"{chave}: valor nulo — o Lutris pula a chave e vale a caixa"
        assert valor == _NAO_VEIO_DO_LEITOR[chave], (chave, valor)
    assert not _SEM_MEDIDA & set(env), f"o par da NVIDIA entrou sem medida: {env}"


def test_com_um_antes_dela_na_caixa_o_yml_leva_o_dela(_lar: Path) -> None:
    """Ela tinha o cache de shader DESLIGADO na caixa antes do Hefesto: o
    jogo excluído o vê desligado de novo."""
    yml = _lutris_flatpak(_lar)
    caixa = _caixa(_lar)
    caixa.parent.mkdir(parents=True, exist_ok=True)
    caixa.write_text("[Environment]\n__GL_SHADER_DISK_CACHE=0\n")
    _carona(_lar)
    assert _nossas_na_caixa(_lar)["__GL_SHADER_DISK_CACHE"] == "1"
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    env = _env_do_yml(yml)
    assert env.get("__GL_SHADER_DISK_CACHE") == "0", env
    assert "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP" not in env, env


# ---------------------------------------------------------------------------
# 3 · Tirar devolve
# ---------------------------------------------------------------------------
def test_tirar_devolve_o_yml_byte_a_byte(_lar: Path) -> None:
    """MORDIDA: o `tirar` sem a volta do `.yml`."""
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    md5 = _md5(yml)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    assert _md5(yml) != md5
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert _md5(yml) == md5, yml.read_text()


def test_com_uma_linha_dela_no_meio_so_os_nossos_saem(_lar: Path) -> None:
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    dado = yaml.safe_load(yml.read_text())
    dado["system"]["env"]["DXVK_HUD"] = "fps"
    dado["game"]["args"] = "-windowed"
    yml.write_text(yaml.safe_dump(dado, default_flow_style=False))
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    depois = yaml.safe_load(yml.read_text())
    assert depois["system"]["env"] == {"MANGOHUD": "1", "DXVK_HUD": "fps"}, depois
    assert depois["game"]["args"] == "-windowed"


# ---------------------------------------------------------------------------
# 4 · O prefixo dividido fica
# ---------------------------------------------------------------------------
def _heroic(lar: Path, jogos: dict[str, dict[str, object]], *, rel: str =
            ".var/app/com.heroicgameslauncher.hgl/config/heroic",
            moradores: dict[Path, list[str]] | None = None, base: int = 100) -> Path:
    """Uma casa do Heroic com estes jogos instalados (`app -> cópia`).

    O umu-id de cada jogo é `umu-<base + i>`, na ordem do dicionário. O
    instalado é o registro da loja, que o Heroic lê (02/10/2026,
    `plantar_o_registro`).
    """
    casa = lar / rel
    (casa / "store_cache").mkdir(parents=True)
    (casa / "GamesConfig").mkdir()
    (casa / "config.json").write_text(json.dumps({"defaultSettings": {
        "enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}}))
    (casa / "store_cache" / "umu.json").write_text(json.dumps(
        {f"legendary_{app}": f"umu-{base + i}" for i, app in enumerate(jogos)}))
    (casa / "store_cache" / "legendary_library.json").write_text(json.dumps({"library": [
        {"app_name": app, "title": app, "is_installed": True} for app in jogos]}))
    plantar_o_registro(casa, list(jogos))
    for app, copia in jogos.items():
        if copia:
            (casa / "GamesConfig" / f"{app}.json").write_text(json.dumps({app: copia}))
    for prefixo, apps in (moradores or {}).items():
        (prefixo / "installed_games").write_text(json.dumps(apps))
    return casa


def _prefixo(caminho: Path, texto: str = "WINE REGISTRY Version 2\n\n") -> Path:
    (caminho / "pfx").mkdir(parents=True)
    (caminho / "pfx" / "system.reg").write_text(texto)
    return caminho


def _janela(i: int) -> str:
    return f"steam_app_{100 + i}"


@pytest.mark.parametrize("como", ["pela-copia", "pelo-installed-games"])
def test_o_prefixo_dividido_fica_com_o_device_ks(
        _lar: Path, monkeypatch: pytest.MonkeyPatch, como: str) -> None:
    """MORDIDA: `prefixos_excluidos` de volta a «todo prefixo de cópia
    excluída» — reprova no caso de B, que não foi excluído."""
    from hefesto_dualsense4unix.daemon import launch_env

    dividido = _prefixo(_lar / "Games/Heroic/Prefixes/Dividido")
    a: dict[str, object] = {"winePrefix": str(dividido)}
    b: dict[str, object] = {"winePrefix": str(dividido)} if como == "pela-copia" else {}
    _heroic(_lar, {"A": a, "B": b},
            moradores={dividido: ["A", "B"]} if como != "pela-copia" else None)
    monkeypatch.setattr(ks, "controles_do_registro",
                        lambda *x, **k: [ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=42)])
    assert lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar) == "adicionado"
    assert lx.prefixos_excluidos() == frozenset(), (
        "A e B moram no mesmo prefixo e só A foi excluído: B perderia a háptica")
    assert launch_env._device_ks_nos_lancadores()["prefixos"] == 1
    assert "HEFESTOKS" in (dividido / "pfx" / "system.reg").read_text(), (
        "a carona do KS pulou o prefixo de B, que não foi excluído")
    assert lx.adicionar(_janela(1), lancador="heroic", nome="B", lar=_lar) == "adicionado"
    assert lx.prefixos_excluidos() == frozenset({dividido.resolve()}), (
        "com A e B excluídos, o prefixo sai")
    assert launch_env._device_ks_nos_lancadores()["prefixos"] == 0


def test_o_prefixo_de_um_jogo_so_continua_saindo(_lar: Path) -> None:
    """O controle: o caso que já funcionava (o padrão do Heroic) não muda."""
    so_dele = _prefixo(_lar / "Games/Heroic/Prefixes/A")
    _heroic(_lar, {"A": {"winePrefix": str(so_dele)}}, moradores={so_dele: ["A"]})
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    assert lx.prefixos_excluidos() == frozenset({so_dele.resolve()})


def test_o_prefixo_global_tem_por_morador_quem_nao_tem_o_seu(_lar: Path) -> None:
    """Quando o prefixo é o da lista global, mora nele todo jogo sem um próprio."""
    global_ = _prefixo(_lar / "Games/Heroic/Prefixes/default")
    casa = _heroic(_lar, {"A": {"winePrefix": str(global_)}, "C": {}})
    dado = json.loads((casa / "config.json").read_text())
    dado["defaultSettings"]["winePrefix"] = str(global_)
    (casa / "config.json").write_text(json.dumps(dado))
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    assert lx.prefixos_excluidos() == frozenset(), "C mora no prefixo global e não foi excluído"


# ---------------------------------------------------------------------------
# 4b · Mora no prefixo quem está instalado
#      (O-PREFIXO-DIVIDIDO-CONTA-SO-QUEM-ESTA-INSTALADO-01)
# ---------------------------------------------------------------------------
def _dividido_com_b_fora_do_disco(lar: Path, *, extra: tuple[str, ...] = ()) -> tuple[Path, Path]:
    """A e B no mesmo prefixo; B desinstalado pelo caminho padrão do Heroic.

    O Heroic 2.22.3 (lido no `app.asar` dela) só acrescenta ao
    `installed_games`, e a cópia `GamesConfig/B.json` fica sem «remover as
    configurações»: as duas seguem dizendo B. Quem diz que B saiu do disco é o
    registro da loja (B sai do `legendary/installed.json`, e a biblioteca o
    marca `is_installed` falso). ``extra``: mais `app_name` anotados no
    `installed_games`, que o censo não conhece.
    """
    dividido = _prefixo(lar / "Games/Heroic/Prefixes/Dividido")
    casa = _heroic(lar, {"A": {"winePrefix": str(dividido)},
                         "B": {"winePrefix": str(dividido)}},
                   moradores={dividido: ["A", "B", *extra]})
    biblioteca = casa / "store_cache" / "legendary_library.json"
    dado = json.loads(biblioteca.read_text())
    for jogo in dado["library"]:
        jogo["is_installed"] = jogo["app_name"] == "A"
    biblioteca.write_text(json.dumps(dado))
    registro = casa / "legendaryConfig/legendary/installed.json"
    instalados = json.loads(registro.read_text())
    del instalados["B"]
    registro.write_text(json.dumps(instalados))
    return dividido, casa


def _o_ks_no(prefixo: Path, monkeypatch: pytest.MonkeyPatch) -> bool:
    """A carona do device KS de verdade, e o que ficou no registro do prefixo."""
    from hefesto_dualsense4unix.daemon import launch_env

    monkeypatch.setattr(ks, "controles_do_registro",
                        lambda *x, **k: [ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=42)])
    launch_env._device_ks_nos_lancadores()
    return bool("HEFESTOKS" in (prefixo / "pfx" / "system.reg").read_text())


def test_o_morador_que_saiu_do_disco_nao_divide_o_prefixo(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B saiu do disco e A foi excluído: o prefixo sai do KS e das camadas.

    MORDIDA: tire o filtro do censo do `_moradores_e_o_censo` — o prefixo fica
    «dividido» por um jogo que não está mais no disco, e A, excluído, segue com
    o device KS.
    """
    dividido, _ = _dividido_com_b_fora_do_disco(_lar)
    assert lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar) == "adicionado"
    assert lx.prefixos_excluidos() == frozenset({dividido.resolve()}), (
        "B saiu do disco e o prefixo seguiu dividido: A, excluído, fica com o KS")
    assert not _o_ks_no(dividido, monkeypatch), "a carona do KS escreveu no prefixo de A"


def test_o_desinstalado_que_volta_divide_de_novo(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B volta ao disco (o registro da loja o diz instalado, e a biblioteca
    ainda não foi relida): o prefixo volta a ser dividido, e B tem o device KS.

    MORDIDA: o «instalado» lido só do `is_installed` da biblioteca, sem o
    registro da loja — B segue «fora» e perde a háptica.
    """
    dividido, casa = _dividido_com_b_fora_do_disco(_lar)
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    assert lx.prefixos_excluidos() == frozenset({dividido.resolve()})
    plantar_o_registro(casa, ["B"])
    assert lx.prefixos_excluidos() == frozenset(), "B voltou ao disco e o prefixo seguiu fora"
    assert _o_ks_no(dividido, monkeypatch), "B voltou ao disco sem o device KS"


def test_quem_o_censo_nao_conhece_continua_morando(_lar: Path) -> None:
    """Um jogo «adicionado» à mão (o censo não o lista) segue morando.

    MORDIDA: o filtro por «está no censo e instalado» no lugar de «o censo
    diz não instalado» — o desconhecido sai, e o prefixo dele perde o KS.
    """
    dividido, _ = _dividido_com_b_fora_do_disco(_lar, extra=("sideload-a-mao",))
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    assert lx.prefixos_excluidos() == frozenset(), (
        "o jogo que o censo não conhece deixou de morar no prefixo")
    assert lx._moradores(dividido.resolve(), _lar / ".var/app/com.heroicgameslauncher.hgl"
                         "/config/heroic") == {"A", "sideload-a-mao"}


def test_sem_o_censo_nada_sai_e_o_diario_diz(_lar: Path) -> None:
    """A biblioteca da GOG está torta: o censo volta com erro, ninguém sai dos
    moradores (o comportamento de antes), e a linha diz `sem_censo=1`.

    MORDIDA: usar o censo com erro — B sai, e o prefixo também.
    """
    _, casa = _dividido_com_b_fora_do_disco(_lar)
    (casa / "store_cache" / "gog_library.json").write_text(json.dumps({"games": "torto"}))
    lx._DIVIDIDOS_DITOS.clear()
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    with structlog.testing.capture_logs() as diario:
        assert lx.prefixos_excluidos() == frozenset()
    linhas = [x for x in diario if x.get("event") == "exclusao_prefixo_dividido"]
    assert linhas and linhas[0].get("sem_censo") == 1, diario


def test_a_loja_sem_conta_nao_desliga_o_censo(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A loja em que ela nunca entrou não é biblioteca torta.

    O Heroic 2.22.3 grava `{}` na biblioteca da loja sem conta: lido no disco
    dela em 02/10/2026, só leitura, o `nile_library.json` (Amazon) é `{}`. O
    censo dizia «não traz `library` como lista», a lista de exclusão lia isso
    como «censo com erro», e a cura do morador que saiu do disco não valia em
    máquina nenhuma com uma loja sem conta — a dela inclusive.

    MORDIDA: o `{}` volta a ser erro no `censo_dos_lancadores._heroic` — o
    prefixo segue dividido por B, que saiu do disco, e A, excluído, fica com o
    device KS.
    """
    dividido, casa = _dividido_com_b_fora_do_disco(_lar)
    (casa / "store_cache" / "nile_library.json").write_text("{}")
    assert censo._heroic(casa).erros == [], "a loja sem conta virou erro do censo"
    assert lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar) == "adicionado"
    assert lx.prefixos_excluidos() == frozenset({dividido.resolve()}), (
        "com a Amazon sem conta, B (fora do disco) seguiu morando no prefixo de A")
    assert not _o_ks_no(dividido, monkeypatch), "a carona do KS escreveu no prefixo de A"


def test_com_o_censo_torto_o_prefixo_global_segue_somando_quem_esta_instalado(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a biblioteca de uma loja torta, «nada sai» — e o que entrava continua entrando.

    O jogo instalado sem cópia própria mora no prefixo global, e quem o diz é o
    censo (`_moradores`, a terceira fonte, desde antes desta sprint). A sprint
    prometeu, para o censo com erro, «o comportamento de hoje»; a primeira
    versão parou de somar esse morador quando qualquer loja voltava com erro, e
    o prefixo global saía do device KS com C, que ela não excluiu, dentro.

    MORDIDA: a terceira fonte só com o censo sem erro — C deixa de morar, o
    prefixo sai, e C perde a háptica.
    """
    global_ = _prefixo(_lar / "Games/Heroic/Prefixes/default")
    casa = _heroic(_lar, {"A": {"winePrefix": str(global_)}, "C": {}})
    dado = json.loads((casa / "config.json").read_text())
    dado["defaultSettings"]["winePrefix"] = str(global_)
    (casa / "config.json").write_text(json.dumps(dado))
    (casa / "store_cache" / "gog_library.json").write_text(json.dumps({"games": "torto"}))
    assert censo._heroic(casa).erros, "a régua precisa do censo com erro"
    assert lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar) == "adicionado"
    assert lx.prefixos_excluidos() == frozenset(), (
        "C, instalado e sem cópia, deixou de morar no prefixo global")
    assert _o_ks_no(global_, monkeypatch), "C, que ela não excluiu, perdeu o device KS"


# ---------------------------------------------------------------------------
# 5 · O nome não basta
# ---------------------------------------------------------------------------
def _epic_ligada(raiz: Path) -> bool:
    camadas = cv.ler_camadas(raiz / "pfx" / "system.reg", prefixo=raiz)
    return next(c for c in camadas if c.caminho_windows == EPIC).ligada


def test_o_corrigir_vulkan_compara_o_prefixo_pelo_caminho(
        _lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dois prefixos com a mesma pasta em casas diferentes, um excluído.

    As duas casas são de dois Heroic instalados (o Flatpak e o nativo): com as
    duas no disco, o censo lê a do programa instalado (02/10/2026), e com os
    dois instalados lê as duas.

    MORDIDA: a comparação pelo nome (`p.appid not in fora`, com o nome da
    pasta vindo de `ids_dos_prefixos`)."""
    _flatpak(_lar, "com.heroicgameslauncher.hgl")
    comandos = tmp_path / "bin"
    comandos.mkdir()
    (comandos / "heroic").write_text("#!/bin/sh\n")
    (comandos / "heroic").chmod(0o755)
    monkeypatch.setenv("PATH", f"{comandos}{os.pathsep}{os.environ.get('PATH', '')}")
    reg = _registro_com_camadas((EPIC, "00000000"))
    um = _prefixo(_lar / "Games/Heroic/Prefixes/Dividido", reg)
    outro = _prefixo(_lar / "Outra/Prefixes/Dividido", reg)
    _heroic(_lar, {"A": {"winePrefix": str(um)}}, moradores={um: ["A"]})
    _heroic(_lar, {"C": {"winePrefix": str(outro)}}, rel=".config/heroic",
            moradores={outro: ["C"]}, base=200)
    lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=_lar)
    assert _epic_ligada(um) and _epic_ligada(outro)
    cv.curar_todos(_lar, excluir=lx.ids_dos_prefixos())
    assert _epic_ligada(um), "o botão desligou a camada do jogo excluído"
    assert not _epic_ligada(outro), (
        "o botão pulou o prefixo de C, de outra casa, só porque a pasta tem o mesmo nome")


# ---------------------------------------------------------------------------
# 6 · O Lutris oferece o jogo
# ---------------------------------------------------------------------------
def test_o_lutris_le_o_umu_id_do_jogo(_lar: Path) -> None:
    """MORDIDA: sem a leitura do umu no censo, volta o «não sei»."""
    _lutris_flatpak(_lar)
    jogos = censo.biblioteca_de("Lutris", _lar).jogos
    assert [(j.nome, j.classe_de_janela) for j in jogos] == [("Recettear", _JANELA)]
    assert ("Lutris", jogos[0]) in censo.jogos_com_chave_de_janela(_lar), (
        "o cartão do Lutris não oferece o jogo da GOG")


def test_o_umu_id_posto_por_ela_no_yml_manda(_lar: Path) -> None:
    _lutris_flatpak(_lar, yml=_YML_DO_JOGO.replace("    MANGOHUD: '1'\n",
                                                   "    UMU_ID: umu-999\n"))
    assert censo.biblioteca_de("Lutris", _lar).jogos[0].classe_de_janela == "steam_app_999"


def test_o_lutris_sem_proton_nao_vira_steam_app(_lar: Path) -> None:
    """Uma versão do Wine que não é Proton não passa pelo umu: «não sei»."""
    _lutris_flatpak(_lar, yml=_YML_DO_JOGO.replace("version: ge-proton",
                                                   "version: wine-ge-8-26-x86_64"))
    assert censo.biblioteca_de("Lutris", _lar).jogos[0].classe_de_janela == ""


# ---------------------------------------------------------------------------
# 7 · A dependência nova chega a todo formato
# ---------------------------------------------------------------------------
_FORMATOS = {
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml": "pip",
    "packaging/arch/PKGBUILD": "arch",
    "packaging/fedora/hefesto-dualsense4unix.spec": "fedora",
    "packaging/nix/package.nix": "nix",
}


def _nomes(dependencia: str) -> set[str]:
    nome = re.split(r"[<>=!~;\[ ]", dependencia, maxsplit=1)[0].strip().lower()
    nome = nome.replace("_", "-")
    return {nome, nome.removeprefix("python-"), nome.removeprefix("py")} - {""}


def _esta_no_formato(texto: str, formato: str, nomes: set[str], pip: str) -> bool:
    if re.search(rf'"{re.escape(pip)}\b', texto, re.IGNORECASE):
        return True
    for n in nomes:
        padrao = {"arch": rf"'python-{re.escape(n)}'",
                  "fedora": rf"\bpython3-{re.escape(n)}\b",
                  "nix": rf"^\s+{re.escape(n)}\s*$",
                  "pip": rf'"{re.escape(n)}\b'}[formato]
        if re.search(padrao, texto, re.IGNORECASE | re.MULTILINE):
            return True
    return False


def test_a_dependencia_de_execucao_chega_a_todo_formato() -> None:
    """MORDIDA: tire o `python-yaml` do `PKGBUILD`; reprova pelo arquivo."""
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    dependencias = projeto["project"]["dependencies"]
    assert any(_nomes(d) & {"pyyaml", "yaml"} for d in dependencias), (
        "o PyYAML não é dependência de execução: a camada do Lutris não tem leitor")
    faltam: list[str] = []
    for rel, formato in _FORMATOS.items():
        texto = (RAIZ / rel).read_text(encoding="utf-8")
        for dep in dependencias:
            pip = re.split(r"[<>=!~;\[ ]", dep, maxsplit=1)[0].strip()
            if not _esta_no_formato(texto, formato, _nomes(dep), pip):
                faltam.append(f"{rel}: {pip}")
    assert not faltam, f"dependência de execução fora do formato: {faltam}"


# ---------------------------------------------------------------------------
# 8 · O Lutris nativo fica como está
# ---------------------------------------------------------------------------
def test_o_lutris_nativo_fica_como_esta(_lar: Path) -> None:
    """O ambiente do Hefesto só chega ao jogo do Lutris pela caixa do Flatpak.

    O Flatpak está instalado e com a caixa cheia; o jogo é do nativo.
    MORDIDA: escrever nas duas casas (o `jogos_do_lutris_pela_janela` lendo
    também o nativo)."""
    _flatpak(_lar, _LUTRIS)
    _carona(_lar)
    assert len(_nossas_na_caixa(_lar)) == 9
    yml = _lutris_nativo(_lar)
    assert censo.biblioteca_de("Lutris", _lar).jogos[0].classe_de_janela == _JANELA
    md5 = _md5(yml)
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    assert _md5(yml) == md5, yml.read_text()


# ---------------------------------------------------------------------------
# 9 · A configuração em pasta própria (o Lutris de antes do 0.5.17)
# ---------------------------------------------------------------------------
def _lutris_com_a_configuracao_a_parte(casa_config: Path, casa_dados: Path) -> Path:
    """A forma de quem usa o Lutris desde antes do 0.5.17: a configuração é
    pasta própria (`games/`, `runners/`), e o `pga.db` e o `runtime/` moram nos
    dados (`settings.DATA_DIR` do 0.5.22, lido no fonte instalado nela)."""
    alvo = _lutris(casa_dados, casa_dados)
    (casa_config / "games").mkdir(parents=True)
    (casa_config / "runners").mkdir()
    (casa_config / "runners" / "wine.yml").write_text("wine:\n  version: ge-proton\n")
    movido = casa_config / "games" / alvo.name
    alvo.rename(movido)
    return movido


@pytest.mark.parametrize("casa", ["flatpak", "nativo"])
def test_com_a_configuracao_a_parte_o_lutris_le_o_banco_dos_dados(
        _lar: Path, casa: str) -> None:
    """Medido na conferência de 02/10/2026: com a configuração em pasta própria,
    o censo procurava o `pga.db` nela, caía nos `.yml` soltos sem o umu-id, e
    o jogo da GOG ficava no «não sei» — o cartão não o oferecia e a exclusão
    feita por outro cartão não achava o `.yml` dele.

    MORDIDA: o banco lido só da pasta de configuração (`pasta / "pga.db"`).
    """
    if casa == "flatpak":
        _flatpak(_lar, _LUTRIS)
        raiz = _lar / ".var/app" / _LUTRIS
        yml = _lutris_com_a_configuracao_a_parte(raiz / "config/lutris", raiz / "data/lutris")
    else:
        yml = _lutris_com_a_configuracao_a_parte(_lar / ".config/lutris",
                                                 _lar / ".local/share/lutris")
    jogos = censo.biblioteca_de("Lutris", _lar).jogos
    assert [(j.nome, j.classe_de_janela) for j in jogos] == [("Recettear", _JANELA)], jogos
    assert jogos[0].configuracao == yml
    if casa == "nativo":
        return
    _carona(_lar)
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar) == "adicionado"
    assert _env_do_yml(yml).get("SDL_GAMECONTROLLER_IGNORE_DEVICES") == "", (
        f"o jogo excluído herda da caixa o IGNORE: {yml.read_text()}")


def test_a_assinatura_ve_o_banco_dos_dados(_lar: Path) -> None:
    """Um jogo novo no `pga.db` dos dados muda a assinatura, mesmo com a
    configuração em pasta própria (o caderno da aba Perfis não congela)."""
    _flatpak(_lar, _LUTRIS)
    raiz = _lar / ".var/app" / _LUTRIS
    _lutris_com_a_configuracao_a_parte(raiz / "config/lutris", raiz / "data/lutris")
    antes = censo.assinatura_das_bibliotecas(_lar)
    con = sqlite3.connect(raiz / "data/lutris/pga.db")
    with con:
        con.execute("INSERT INTO games (name, slug, runner, installed) "
                    "VALUES ('Outro', 'outro', 'linux', 1)")
    con.close()
    assert censo.assinatura_das_bibliotecas(_lar) != antes


# ---------------------------------------------------------------------------
# 10 · O excluído do Lutris volta ao xalia do Proton
#      (O-JOGO-EXCLUIDO-DO-LUTRIS-VOLTA-AO-XALIA-DO-PROTON-01)
# ---------------------------------------------------------------------------
_XALIA = "PROTON_USE_XALIA"
_SO_SUPORTADAS = "XALIA_SUPPORTED_ONLY"
#: O recorte do script do GE-Proton 11-7 (`proton:2527-2533`), guardado como dado
#: de teste com a versão no nome. Nunca o Proton instalado na máquina do teste:
#: com ele, a régua mediria a máquina.
_RECORTE_DO_PROTON = RAIZ / "tests/fixtures/proton/GE-Proton11-7-o-padrao-do-xalia.txt"
_YML_PELO_WINE = _YML_DO_JOGO.replace("version: ge-proton", "version: wine-ge-8-26-x86_64")


def _lutris_flatpak_pelo_wine(lar: Path) -> Path:
    """O jogo da Steam no Lutris Flatpak, por um Wine que não é Proton.

    Sem o umu, o jogo só tem janela conhecida pelo degrau 2 (`service` da
    Steam, `steam_app_<N>`): é o jogo pelo Wine que a lista alcança.
    """
    yml = _lutris_flatpak(lar, yml=_YML_PELO_WINE)
    con = sqlite3.connect(lar / ".var/app" / _LUTRIS / "data/lutris/pga.db")
    with con:
        con.execute("UPDATE games SET service = 'steam', service_id = '70400'")
    con.close()
    return yml


def _padrao_do_script(compat_config: frozenset[str] = frozenset()) -> dict[str, str]:
    """O ambiente que o script do Proton monta quando a variável não vem."""

    class _Script:
        def __init__(self) -> None:
            self.env: dict[str, str] = {}
            self.compat_config = set(compat_config)

    script = _Script()
    exec(compile(_RECORTE_DO_PROTON.read_text(encoding="utf-8"),
                 str(_RECORTE_DO_PROTON), "exec"), {"self": script})
    return script.env


def _o_xalia_do(yml: Path) -> dict[str, object]:
    env = _env_do_yml(yml)
    return {k: env[k] for k in (_XALIA, _SO_SUPORTADAS) if k in env}


def test_o_jogo_pelo_proton_ganha_o_par(_lar: Path) -> None:
    """O jogo do Lutris Flatpak pela versão padrão (`ge-proton`, pelo umu e pelo
    script do Proton): a camada põe o par, e o diário diz qual jogo.

    MORDIDA: o xalia de volta ao «fica fora» de antes (sem o padrão por jogo
    em `pares_da_camada_do_lutris`) — sem o par, o jogo excluído fica com o `0`
    da caixa, e o excluído da Steam e o do Heroic não.
    """
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    with structlog.testing.capture_logs() as diario:
        assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear",
                            lar=_lar) == "adicionado"
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}, yml.read_text()
    linhas = [x for x in diario if x.get("event") == "camada_do_lutris_xalia"]
    assert linhas and linhas[0]["par"] == 1 and linhas[0]["jogo"] == yml.stem, diario


def test_o_par_e_o_padrao_do_script_do_proton(_lar: Path) -> None:
    """O par que a camada põe é o que o script do GE-Proton 11-7 poria sozinho
    para um appid fora do `noxalia` — lido no recorte, não no escritor.

    MORDIDA: `XALIA_SUPPORTED_ONLY=0` no par — o xalia subiria em toda janela.
    """
    padrao = _padrao_do_script()
    assert padrao == {_XALIA: "1", _SO_SUPORTADAS: "1"}, padrao
    assert _padrao_do_script(frozenset({"noxalia"})) == {_XALIA: "0"}
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    assert _o_xalia_do(yml) == padrao


def test_o_jogo_pelo_wine_fica_com_o_da_caixa(_lar: Path) -> None:
    """Uma versão do Wine que não é Proton não passa pelo script: sem a
    variável, o `explorer.exe` não sobe o xalia, e o `0` da caixa é o padrão.

    MORDIDA: o par para todo jogo (sem perguntar ao censo `pelo_proton`).
    """
    yml = _lutris_flatpak_pelo_wine(_lar)
    assert not censo.biblioteca_de("Lutris", _lar).jogos[0].pelo_proton
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    env = _env_do_yml(yml)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in env, "a exclusão não cobriu a caixa"
    assert _o_xalia_do(yml) == {}, yml.read_text()


def test_o_par_segue_o_wine_do_jogo(_lar: Path) -> None:
    """Ela troca o Wine do jogo excluído (Proton → Wine) e a carona passa: o
    par sai; e volta quando ela troca de novo.

    MORDIDA: o «só acrescenta» de antes no `_manter_o_yml` — o par fica.
    """
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}

    def trocar(versao: str) -> None:
        dado = yaml.safe_load(yml.read_text())
        dado["wine"]["version"] = versao
        yml.write_text(yaml.safe_dump(dado, default_flow_style=False))

    trocar("wine-ge-8-26-x86_64")
    _carona(_lar)
    assert _o_xalia_do(yml) == {}, f"o par ficou no jogo pelo Wine:\n{yml.read_text()}"
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in _env_do_yml(yml)
    trocar("ge-proton")
    _carona(_lar)
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert _o_xalia_do(yml) == {}


def test_tirar_da_lista_tira_as_duas(_lar: Path) -> None:
    """Ela mexe no `.yml` depois da exclusão (a volta passa a ser pelos pares):
    o «Tirar da lista» tira as duas chaves do par, e o que é dela fica.

    MORDIDA: o registro sem o `XALIA_SUPPORTED_ONLY` — a chave fica no arquivo.
    """
    yml = _lutris_flatpak(_lar)
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    dado = yaml.safe_load(yml.read_text())
    dado["system"]["env"]["DXVK_HUD"] = "fps"
    yml.write_text(yaml.safe_dump(dado, default_flow_style=False))
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert _env_do_yml(yml) == {"MANGOHUD": "1", "DXVK_HUD": "fps"}, yml.read_text()


@pytest.mark.parametrize("onde", ["no-yml", "na-caixa"])
def test_o_xalia_que_ela_pos_manda(_lar: Path, onde: str) -> None:
    """Com o `PROTON_USE_XALIA` posto por ela (no `.yml` do jogo, ou na caixa),
    a camada não põe o par, nem a metade dele: o `1` dela não ganha o
    `XALIA_SUPPORTED_ONLY` nosso.

    MORDIDA: o par sem o «junto ou nada» do `_com_o_nosso_no_yml` — o `.yml`
    dela ganha a metade que faltava.
    """
    if onde == "no-yml":
        yml = _lutris_flatpak(_lar, yml=_YML_DO_JOGO.replace(
            "    MANGOHUD: '1'\n", "    MANGOHUD: '1'\n    PROTON_USE_XALIA: '1'\n"))
    else:
        yml = _lutris_flatpak(_lar)
        _caixa(_lar).parent.mkdir(parents=True, exist_ok=True)
        _caixa(_lar).write_text(f"[Environment]\n{_XALIA}=1\n")
    _carona(_lar)
    lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=_lar)
    _carona(_lar)
    esperado = {_XALIA: "1"} if onde == "no-yml" else {}
    assert _o_xalia_do(yml) == esperado, yml.read_text()
    if onde == "na-caixa":
        assert _nossas_na_caixa(_lar) and f"{_XALIA}=1" in _caixa(_lar).read_text()
