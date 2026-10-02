"""O-UNINSTALL-DEVOLVE-O-JOGO-EXCLUIDO-01 — as réguas.

**O DEFEITO, medido em 02/10/2026 num lar de mentira** (a carona, a exclusão
e o desfazer reais da integração): o jogo A do Heroic, que seguia a lista
global, foi excluído (a exclusão lhe deu uma lista própria, sem o que é nosso)
e o uninstall o deixou com a lista própria — ele não seguia mais a global
dela, e levava o cache de shader que a carona pôs na global. Com
`--purge-config` era pior: a lista de exclusão, onde mora a anotação de como
devolver A, saía do disco ANTES do desfazer dos lançadores.

AS CINCO RÉGUAS, cada uma lendo os arquivos do lançador pelo disco, nunca a
resposta do desfazer:

1. a volta segue a global;
2. o purge não apaga antes (o `uninstall.sh` de verdade, no lar de mentira);
3. um excluído de cada lançador, e nenhum rastro nosso nos quatro;
4. ela mexeu, ela fica;
5. sem PyYAML, o `.yml` não se escreve à mão.

E mais duas: o desfazer adiado com `--purge-config` termina depois (a lista vai
para o `launch_env`, ao lado do registro), e o espelho do caminho da lista.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from hefesto_dualsense4unix.utils import memoria_dos_controles as m
from tests.unit.test_o_uninstall_nao_deixa_rastro import (
    _SO_A_BIBLIOTECA_PADRAO,
    SISTEMA,
    UNINSTALL,
    _casa_de_mentira,
    _desinstalar,
    _instalar_flatpak,
    _instalar_pelos_donos,
)

RAIZ = Path(__file__).resolve().parents[2]
CURA = RAIZ / "src/hefesto_dualsense4unix/integrations/cura_por_estrada.py"

#: A ponte com a emulação ligada — as 9 variáveis (o `default.env` do daemon).
_PONTE = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6\nSDL_JOYSTICK_HIDAPI=0\n"
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0\nPROTON_DISABLE_HIDRAW=0x054C/0x0CE6\n"
    "__GL_SHADER_DISK_CACHE=1\n__GL_SHADER_DISK_CACHE_SKIP_CLEANUP=1\n"
    "SDL_ACCELEROMETER_AS_JOYSTICK=0\nPROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=1\n"
    "PROTON_ENABLE_MHWILDS_USB_AUDIO=1\n"
)
_HEROIC = ".var/app/com.heroicgameslauncher.hgl/config/heroic"
_LUTRIS = "net.lutris.Lutris"


def _nossas() -> set[str]:
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST

    return set(ENV_ALLOWLIST)


def _md5(caminho: Path) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def _heroic(lar: Path, jogos: dict[str, dict[str, object] | None]) -> Path:
    """O Heroic Flatpak com a global dela (`MANGOHUD`) e estes jogos instalados.

    `jogos`: `app -> cópia` (`None` = sem arquivo; `{}` = a cópia vazia que o
    Heroic grava ao abrir a tela do jogo). O umu-id é `umu-<100 + i>`.
    """
    casa = lar / _HEROIC
    (casa / "store_cache").mkdir(parents=True)
    (casa / "GamesConfig").mkdir()
    (casa / "config.json").write_text(json.dumps({"defaultSettings": {
        "enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}}, indent=2))
    (casa / "store_cache/umu.json").write_text(json.dumps(
        {f"legendary_{app}": f"umu-{100 + i}" for i, app in enumerate(jogos)}))
    (casa / "store_cache/legendary_library.json").write_text(json.dumps({"library": [
        {"app_name": app, "title": app, "is_installed": True} for app in jogos]}))
    for app, copia in jogos.items():
        if copia is not None:
            (casa / "GamesConfig" / f"{app}.json").write_text(
                json.dumps({app: copia}, indent=2))
    return casa


def _lista_propria(casa: Path, app: str) -> list[tuple[str, str]] | None:
    """A lista própria do jogo, ou `None` (sem arquivo, ou seguindo a global)."""
    arquivo = casa / "GamesConfig" / f"{app}.json"
    if not arquivo.is_file():
        return None
    jogo = json.loads(arquivo.read_text()).get(app) or {}
    lista = jogo.get("enviromentOptions")
    return None if lista is None else [(x["key"], x["value"]) for x in lista]


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "lar"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(casa / ".local/state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(casa / ".local/share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    (launch_env_dir(ensure=True) / "default.env").write_text(_PONTE)
    return casa


def _pasta() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    return launch_env_dir()


def _carona(lar: Path) -> tuple[str, ...]:
    return cpe.curar_todas_as_estradas(lar=lar, raiz_sistema=lar.parent / "sistema")


def _desfazer(lar: Path) -> tuple[list[cpe.Desfeito], bool]:
    return cpe.desfazer_as_estradas([_pasta()], lar, [lx.caminho()])


# ---------------------------------------------------------------------------
# 1 · A volta segue a global
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("copia", [None, {}], ids=["sem-arquivo", "copia-vazia"])
def test_a_volta_segue_a_global(lar: Path, copia: dict[str, object] | None) -> None:
    """MORDIDA: o desfazer sem a volta (`_devolver_os_excluidos` vazio); a régua
    mostra a lista que ficou em A."""
    casa = _heroic(lar, {"A": copia, "B": {"enviromentOptions": [
        {"key": "MANGOHUD", "value": "1"}]}})
    _carona(lar)
    assert lx.adicionar("steam_app_100", lancador="heroic", nome="A", lar=lar) == "adicionado"
    assert _lista_propria(casa, "A") is not None, "a exclusão não deu a A a lista própria"

    feitos, completo = _desfazer(lar)

    assert completo, [cpe.frase_do_desfeito(f) for f in feitos]
    ficou = _lista_propria(casa, "A")
    assert ficou is None, (
        f"A saiu do uninstall com a lista própria {ficou}: não segue mais a global dela")
    arquivo = casa / "GamesConfig" / "A.json"
    assert arquivo.exists() == (copia is not None), (
        "o arquivo que nasceu com a exclusão não saiu" if copia is None
        else "o arquivo do Heroic sumiu")
    global_ = json.loads((casa / "config.json").read_text())["defaultSettings"]
    assert global_["enviromentOptions"] == [{"key": "MANGOHUD", "value": "1"}]


# ---------------------------------------------------------------------------
# 4 · Ela mexeu, ela fica
# ---------------------------------------------------------------------------
def test_ela_mexeu_a_chave_dela_fica(lar: Path) -> None:
    """MORDIDA: a volta exata sem conferir o «depois» (a chave dela sumiria)."""
    casa = _heroic(lar, {"A": {}})
    _carona(lar)
    lx.adicionar("steam_app_100", lancador="heroic", nome="A", lar=lar)
    arquivo = casa / "GamesConfig" / "A.json"
    dado = json.loads(arquivo.read_text())
    dado["A"]["enviromentOptions"].append({"key": "DXVK_HUD", "value": "fps"})
    arquivo.write_text(json.dumps(dado, indent=2))

    _desfazer(lar)

    ficou = dict(_lista_propria(casa, "A") or [])
    assert ficou.get("DXVK_HUD") == "fps", f"a chave que ela pôs em A sumiu: {ficou}"
    assert ficou.get("MANGOHUD") == "1", ficou
    assert not set(ficou) & _nossas(), (
        f"A ficou com o que a carona ou a exclusão escreveram: {sorted(set(ficou) & _nossas())}")


# ---------------------------------------------------------------------------
# 5 · Sem PyYAML, o `.yml` não se escreve à mão
# ---------------------------------------------------------------------------
def _lutris(lar: Path, jogos: dict[str, str]) -> dict[str, Path]:
    """O Lutris Flatpak com estes jogos da GOG (`slug -> appid da GOG`).

    Devolve o `.yml` de cada um. O umu-id é `umu-<70000 + i>`.
    """
    import sqlite3

    _instalar_flatpak(lar, _LUTRIS)
    dados = lar / ".var/app" / _LUTRIS / "data/lutris"
    (dados / "games").mkdir(parents=True)
    (lar / ".var/app" / _LUTRIS / "config").mkdir(parents=True)
    (lar / ".var/app" / _LUTRIS / "config/lutris").symlink_to(dados)
    umu = dados / "runtime/umu-games/umu-games.json"
    umu.parent.mkdir(parents=True)
    umu.write_text(json.dumps([{"name": s, "store": "gog", "appid": a,
                                "umu_id": f"umu-{70000 + i}"}
                               for i, (s, a) in enumerate(jogos.items())]))
    con = sqlite3.connect(dados / "pga.db")
    with con:
        con.execute("CREATE TABLE games (name TEXT, slug TEXT, runner TEXT, executable TEXT, "
                    "directory TEXT, installed INTEGER, service TEXT, service_id TEXT, "
                    "configpath TEXT)")
        for slug, appid in jogos.items():
            con.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?)",
                        (slug, slug, "wine", f"{slug}.exe", f"/j/{slug}", 1, "gog",
                         appid, f"{slug}-1"))
    con.close()
    ymls: dict[str, Path] = {}
    for slug in jogos:
        alvo = dados / "games" / f"{slug}-1.yml"
        alvo.write_text(f"game:\n  exe: /j/{slug}/{slug}.exe\nsystem:\n  env:\n"
                        "    MANGOHUD: '1'\n")
        ymls[slug] = alvo
    return ymls


def test_sem_pyyaml_o_yml_volta_exato_ou_fica(lar: Path, tmp_path: Path) -> None:
    """O desfazer pelo `python3` do sistema, com o `yaml` recusado (só a
    biblioteca padrão importa): o `.yml` que ninguém mexeu volta byte a byte; o
    mexido fica intacto, e a saída diz o arquivo.

    MORDIDA: uma volta parcial que regrave o `.yml` sem o PyYAML (por texto);
    reprova pelo md5 do `.yml` mexido.
    """
    py = shutil.which("python3", path=SISTEMA)
    if py is None:
        pytest.skip("sem python3 no sistema")
    ymls = _lutris(lar, {"quieto": "11", "mexido": "22"})
    _carona(lar)
    originais = {s: _md5(y) for s, y in ymls.items()}
    for i in (0, 1):
        assert lx.adicionar(f"steam_app_{70000 + i}", lancador="lutris", nome=str(i),
                            lar=lar) == "adicionado"
    assert all(_md5(y) != originais[s] for s, y in ymls.items()), "a exclusão não escreveu"
    dado = yaml.safe_load(ymls["mexido"].read_text())
    dado["game"]["args"] = "-windowed"
    ymls["mexido"].write_text(yaml.safe_dump(dado, default_flow_style=False))
    mexido = _md5(ymls["mexido"])
    recusa = tmp_path / "so_a_biblioteca_padrao.py"
    recusa.write_text(_SO_A_BIBLIOTECA_PADRAO, encoding="utf-8")
    r = subprocess.run(
        [py, "-I", str(recusa), str(CURA), "--desfazer", "--lar", str(lar),
         "--pasta-do-ambiente", str(_pasta()), "--lista-de-exclusao", str(lx.caminho())],
        env={"HOME": str(lar), "PATH": SISTEMA, "LANG": "C.UTF-8",
             "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=60, check=False, cwd=str(tmp_path))
    assert _md5(ymls["quieto"]) == originais["quieto"], ymls["quieto"].read_text()
    assert _md5(ymls["mexido"]) == mexido, (
        "o `.yml` que ela mexeu foi regravado sem o PyYAML:\n" + ymls["mexido"].read_text())
    assert r.returncode == 1, r.stdout + r.stderr
    linha = next((x for x in r.stdout.splitlines() if ymls["mexido"].name in x), "")
    assert "fica para o desfazer de depois" in linha, r.stdout


# ---------------------------------------------------------------------------
# 2 e 3 · O uninstall.sh de verdade, no lar de mentira
# ---------------------------------------------------------------------------
def _excluir_um_de_cada(r: m.Raizes, monkeypatch: pytest.MonkeyPatch,
                        ) -> tuple[dict[str, Path], str]:
    """Depois dos donos e da carona do harness: A no Heroic, um jogo no Lutris
    Flatpak, o mGBA inteiro e um jogo da Steam na lista de exclusão.

    Devolve os arquivos e o texto do `.yml` do jogo do Lutris antes da exclusão.
    """
    monkeypatch.setenv("HOME", str(r.lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(r.config))
    monkeypatch.setenv("XDG_STATE_HOME", str(r.estado))
    casa = r.lar / _HEROIC
    (casa / "store_cache").mkdir(parents=True)
    (casa / "store_cache/umu.json").write_text(json.dumps({"legendary_A": "umu-100"}))
    (casa / "store_cache/legendary_library.json").write_text(json.dumps({"library": [
        {"app_name": "A", "title": "A", "is_installed": True}]}))
    dados = r.lar / ".var/app" / _LUTRIS / "data/lutris"
    yml = _lutris_no_harness(r.lar, dados)
    pasta = r.estado / m.SLUG / "launch_env"
    cpe.curar_todas_as_estradas(lar=r.lar, pasta_do_ambiente=pasta,
                                raiz_sistema=r.lar.parent / "flatpak-do-sistema")
    yml_original = yml.read_text()
    assert lx.adicionar("steam_app_100", lancador="heroic", nome="A", lar=r.lar) == "adicionado"
    assert lx.adicionar("steam_app_70000", lancador="lutris", nome="Q", lar=r.lar) == "adicionado"
    assert lx.adicionar("emulador:mgba", lancador="mgba", nome="mGBA — todos os jogos",
                        janelas=("io.mgba.mGBA",), lar=r.lar) == "adicionado"
    assert lx.adicionar("steam_app_200", lancador="steam", nome="S", lar=r.lar) == "adicionado"
    assert _lista_propria(casa, "A") is not None
    assert yml.read_text() != yml_original, "a exclusão não cobriu a caixa no `.yml`"
    return ({"casa": casa, "yml": yml,
             "mgba": r.lar / ".local/share/flatpak/overrides/io.mgba.mGBA",
             "lutris": r.lar / ".local/share/flatpak/overrides" / _LUTRIS, "pasta": pasta},
            yml_original)


def _lutris_no_harness(lar: Path, dados: Path) -> Path:
    """O Lutris do harness já tem a caixa (`_lutris` dele): acrescenta o jogo."""
    import sqlite3

    (dados / "games").mkdir(parents=True)
    (lar / ".var/app" / _LUTRIS / "config").mkdir(parents=True, exist_ok=True)
    (lar / ".var/app" / _LUTRIS / "config/lutris").symlink_to(dados)
    umu = dados / "runtime/umu-games/umu-games.json"
    umu.parent.mkdir(parents=True)
    umu.write_text(json.dumps([{"store": "gog", "appid": "11", "umu_id": "umu-70000"}]))
    con = sqlite3.connect(dados / "pga.db")
    with con:
        con.execute("CREATE TABLE games (name TEXT, slug TEXT, runner TEXT, executable TEXT, "
                    "directory TEXT, installed INTEGER, service TEXT, service_id TEXT, "
                    "configpath TEXT)")
        con.execute("INSERT INTO games VALUES ('Q','q','wine','q.exe','/j/q',1,'gog','11','q-1')")
    con.close()
    alvo = dados / "games" / "q-1.yml"
    alvo.write_text("game:\n  exe: /j/q/q.exe\n")
    return alvo


def test_o_purge_nao_apaga_antes_e_a_volta_segue_a_global(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `uninstall.sh` real, do começo ao fim, com `--purge-config`.

    MORDIDA: a ordem de antes (o bloco da configuração antes do desfazer dos
    lançadores); reprova pelo nome de A.
    """
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)
    alvos, yml_antes = _excluir_um_de_cada(r, monkeypatch)

    rodou, diario = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                                 xdg_fora=False)

    assert rodou.returncode == 0, rodou.stdout[-3000:] + rodou.stderr[-3000:]
    assert "RECUSADO" not in diario, diario
    ficou = _lista_propria(alvos["casa"], "A")
    assert ficou is None, (
        f"A saiu do uninstall com a lista própria {ficou}: o purge apagou a lista de "
        "exclusão antes do desfazer")
    assert not lx.caminho(r.config).exists(), "a configuração não saiu com --purge-config"
    assert list(r.config.glob(f"{m.SLUG}.backup-*/*/lista_de_exclusao.json")), (
        "a lista de exclusão não foi para o backup da configuração")
    # 3 · UM EXCLUÍDO DE CADA: nenhum arquivo dos quatro com o nosso.
    nossas = _nossas()
    for app in ("A",):
        sobrou = {k for k, _ in (_lista_propria(alvos["casa"], app) or [])} & nossas
        assert not sobrou, f"o jogo {app} do Heroic ficou com {sorted(sobrou)}"
    assert alvos["yml"].read_text() == yml_antes, alvos["yml"].read_text()
    for caixa in (alvos["lutris"], alvos["mgba"]):
        texto = caixa.read_text() if caixa.exists() else ""
        assert not {k for k in nossas if f"{k}=" in texto}, f"{caixa.name}: {texto}"
    assert not alvos["pasta"].exists(), "o launch_env ficou (com o steam_app da Steam)"
    vdf = next(r.lar.glob(".steam/steam/userdata/*/config/localconfig.vdf"))
    assert not {k for k in nossas if k in vdf.read_text()}, vdf.read_text()


def test_o_desfazer_adiado_leva_a_lista_e_termina_depois(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o desfazer adiado e `--purge-config`, a lista vai para o
    `launch_env`, ao lado do registro, e o comando do ADIADO devolve A depois.

    MORDIDA: o purge sem guardar a lista (o `cp` do bloco da configuração);
    o desfazer de depois não sabe devolver A."""
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    _instalar_pelos_donos(r, repo, heroic_nativo=False, com_venv=True)
    alvos, _ = _excluir_um_de_cada(r, monkeypatch)
    inteiro = (alvos["casa"] / "config.json").read_text()
    (alvos["casa"] / "config.json").write_text(inteiro[: len(inteiro) // 2])

    rodou, _ = _desinstalar(tmp_path, r, repo, UNINSTALL.read_text(encoding="utf-8"),
                            xdg_fora=False)

    assert rodou.returncode == 0, rodou.stderr[-3000:]
    guardada = alvos["pasta"] / "lista_de_exclusao-1.json"
    assert "ADIADO" in rodou.stdout and f"--lista-de-exclusao {guardada}" in rodou.stdout, (
        rodou.stdout[-3000:])
    assert guardada.is_file(), sorted(os.listdir(alvos["pasta"]))
    assert not lx.caminho(r.config).exists()

    (alvos["casa"] / "config.json").write_text(inteiro)  # ela abriu o Heroic
    py = shutil.which("python3", path=SISTEMA)
    assert py, "sem python3 no sistema"
    depois = subprocess.run(
        [py, "-I", str(CURA), "--desfazer", "--lista-de-exclusao", str(guardada)],
        env={"HOME": str(r.lar), "PATH": SISTEMA, "LANG": "C.UTF-8",
             "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=60, check=False, cwd=str(tmp_path))

    assert depois.returncode == 0, depois.stdout + depois.stderr
    assert _lista_propria(alvos["casa"], "A") is None, "o desfazer de depois não devolveu A"
    assert not (r.estado / m.SLUG).exists(), (
        f"a pasta de estado ficou: {sorted(os.listdir(r.estado / m.SLUG))}")


def test_o_caminho_da_lista_e_um_so() -> None:
    """O desfazer repete o caminho da lista porque roda sem o pacote; os dois
    não podem se afastar."""
    assert cpe.RELPATH_DA_LISTA == lx.RELPATH
