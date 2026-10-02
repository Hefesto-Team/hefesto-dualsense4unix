"""O xalia fica fora de todo jogo — AS-CORRECOES-AUTOMATICAS-DESLIGAM-O-XALIA-E-O-FOSSILIZE-01."""
from __future__ import annotations

import configparser
import json
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao
from hefesto_dualsense4unix.utils import memoria_dos_controles as m
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import (
    _JANELA,
    _PONTE,
    _env_do_yml,
    _flatpak,
    _heroic,
    _janela,
    _lutris_flatpak,
    _lutris_flatpak_pelo_wine,
)

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "assets" / "hefesto-launch.sh"


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    """Casa, config e estado de mentira, e o Game Mode mudo na frente do PATH."""
    casa = tmp_path / "casa"
    (casa / ".config").mkdir(parents=True)
    mudos = tmp_path / "mudos"
    mudos.mkdir()
    for nome in ("system76-power", "busctl", "dbus-send"):
        falso = mudos / nome
        falso.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        falso.chmod(0o755)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    return tmp_path


def _lancar(lar: Path, **extra: str) -> dict[str, str]:
    ambiente = {
        "HOME": str(lar / "casa"),
        "XDG_CONFIG_HOME": str(lar / "casa" / ".config"),
        "XDG_STATE_HOME": str(lar / "estado"),
        "XDG_RUNTIME_DIR": str(lar / "runtime"),
        "PATH": f"{lar / 'mudos'}:/usr/bin:/bin",
        **extra,
    }
    saida = subprocess.run(
        ["sh", str(LANCADOR), "/usr/bin/env"],
        env=ambiente, capture_output=True, text=True, timeout=60, check=False,
    )
    assert saida.returncode == 0, saida.stderr
    visto: dict[str, str] = {}
    for linha in saida.stdout.splitlines():
        chave, _, valor = linha.partition("=")
        visto[chave] = valor
    return visto


def test_todo_jogo_nasce_sem_o_xalia(lar: Path) -> None:
    """Sem daemon e sem escolha gravada: o jogo recebe `PROTON_USE_XALIA=0`."""
    visto = _lancar(lar, SteamAppId="3621330")
    assert visto.get("PROTON_USE_XALIA") == "0", (
        "o lançador não desligou o xalia, e o proton o liga sozinho: "
        f"{visto.get('PROTON_USE_XALIA')!r}")


def test_o_jogo_sem_appid_tambem(lar: Path) -> None:
    """Um jogo de fora da Steam, sem `SteamAppId`, recebe o mesmo."""
    assert _lancar(lar).get("PROTON_USE_XALIA") == "0"


def test_a_launch_option_dela_manda(lar: Path) -> None:
    """Quem já pôs `PROTON_USE_XALIA` no ambiente não é sobrescrito."""
    assert _lancar(lar, SteamAppId="3621330", PROTON_USE_XALIA="1")["PROTON_USE_XALIA"] == "1"


def test_o_jogo_da_lista_de_exclusao_abre_como_sem_o_hefesto(lar: Path) -> None:
    """A lista de exclusão vale antes de tudo: nenhuma env do Hefesto."""
    status = lista_de_exclusao.adicionar(
        "steam_app_3621330", lancador="steam", nome="Pro Jank Footy",
        config_home=lar / "casa" / ".config")
    assert status == "adicionado", status
    assert "PROTON_USE_XALIA" not in _lancar(lar, SteamAppId="3621330")


_XALIA = "PROTON_USE_XALIA"
_RETROARCH = "org.libretro.RetroArch"


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O lar de mentira com a ponte publicada (as 9 variáveis da emulação ligada)."""
    lar = tmp_path / "lar"
    lar.mkdir()
    assert not str(lar).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE.items()))
    return lar


def _carona(lar: Path) -> tuple[str, ...]:
    return cpe.curar_todas_as_estradas(lar=lar, raiz_sistema=lar.parent / "sistema")


def _pasta() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    return launch_env_dir()


def _lista_global(casa_do_heroic: Path) -> dict[str, str]:
    dado = json.loads((casa_do_heroic / "config.json").read_text())
    lista = dado.get("defaultSettings", {}).get("enviromentOptions", [])
    return {x["key"]: x["value"] for x in lista}


def _lista_do_jogo(casa_do_heroic: Path, app: str) -> dict[str, str] | None:
    alvo = casa_do_heroic / "GamesConfig" / f"{app}.json"
    if not alvo.exists():
        return None
    jogo = json.loads(alvo.read_text()).get(app, {})
    lista = jogo.get("enviromentOptions")
    return None if lista is None else {x["key"]: x["value"] for x in lista}


def _override(lar: Path, app_id: str) -> dict[str, str]:
    alvo = lar / ".local/share/flatpak/overrides" / app_id
    if not alvo.exists():
        return {}
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    cfg.optionxform = str  # type: ignore[method-assign,assignment]
    cfg.read_string(alvo.read_text())
    return dict(cfg.items("Environment")) if cfg.has_section("Environment") else {}


def _trocar_o_nosso(arquivo: Path) -> None:
    """Ela troca o `0` do xalia por `1` em toda lista deste arquivo do Heroic."""
    dado = json.loads(arquivo.read_text())
    listas = [d.get("enviromentOptions", []) for d in dado.values() if isinstance(d, dict)]
    for lista in listas:
        for par in lista:
            if par.get("key") == _XALIA:
                par["value"] = "1"
    arquivo.write_text(json.dumps(dado, indent=2))


def _por_override(lar: Path, app_id: str, texto: str) -> None:
    alvo = lar / ".local/share/flatpak/overrides" / app_id
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto)


def test_a_carona_desliga_o_xalia_em_toda_estrada(casa: Path) -> None:
    """A global do Heroic, a cópia de um jogo, a caixa do Lutris e a de um emulador."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]},
                            "B": {}})
    _lutris_flatpak(casa)
    _flatpak(casa, _RETROARCH)
    assert {"heroic", "lutris", "retroarch"} <= set(_carona(casa))
    onde = {
        f"{heroic / 'config.json'} (a lista global do Heroic)": _lista_global(heroic),
        f"{heroic / 'GamesConfig' / 'A.json'} (a cópia do jogo A)":
            _lista_do_jogo(heroic, "A") or {},
        "a caixa do Lutris Flatpak": _override(casa, "net.lutris.Lutris"),
        "a caixa do RetroArch": _override(casa, _RETROARCH),
    }
    for arquivo, ambiente in onde.items():
        assert ambiente.get(_XALIA) == "0", (
            f"{arquivo} ficou sem {_XALIA}=0, e o Proton liga o xalia sozinho: "
            f"{ambiente.get(_XALIA)!r}")
    assert (_lista_do_jogo(heroic, "A") or {}).get("MANGOHUD") == "1", "o que é dela saiu"


def test_o_valor_da_carona_e_o_do_lancador_da_steam() -> None:
    """Um valor só para os dois caminhos: o `xalia_fora` do lançador e a carona."""
    texto = LANCADOR.read_text(encoding="utf-8")
    corpo = texto.split("xalia_fora() {", 1)[1].split("\n}", 1)[0]
    linha = next(x.strip() for x in corpo.splitlines() if x.strip().startswith('xf_envs="P'))
    nome, _, valor = linha.removeprefix('xf_envs="').rstrip('"').partition("=")
    assert dict(cpe.CORRECOES_DA_CARONA) == {nome: valor}


def test_o_que_ela_pos_manda(casa: Path) -> None:
    """Ela já pôs `PROTON_USE_XALIA`: a carona não escreve por cima, e não anota como nosso."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": _XALIA, "value": "1"}]}})
    dado = json.loads((heroic / "config.json").read_text())
    dado["defaultSettings"]["enviromentOptions"].append({"key": _XALIA, "value": "1"})
    (heroic / "config.json").write_text(json.dumps(dado))
    _lutris_flatpak(casa)
    _por_override(casa, "net.lutris.Lutris", f"[Environment]\n{_XALIA}=1\n")
    for _ in range(2):
        _carona(casa)
        assert _lista_global(heroic)[_XALIA] == "1"
        assert (_lista_do_jogo(heroic, "A") or {})[_XALIA] == "1"
        assert _override(casa, "net.lutris.Lutris")[_XALIA] == "1"
    registro = cpe.ler_registro(_pasta())
    for arquivo, entrada in registro.items():
        marca = entrada.chaves.get(_XALIA)
        assert marca is None or "1" not in marca.valores, (
            f"{arquivo}: o dela foi anotado como nosso")


def test_ela_muda_o_nosso_e_fica_o_dela(casa: Path) -> None:
    """Depois da carona ela troca o nosso `0` por `1`: a carona seguinte não volta ao `0`."""
    heroic = _heroic(casa, {"A": {}})
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "0"
    _trocar_o_nosso(heroic / "config.json")
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "1"
    cpe.desfazer_as_estradas([_pasta()], casa)
    assert _lista_global(heroic).get(_XALIA) == "1", "o desfazer tirou o valor dela"


def test_o_desfazer_tira_so_o_nosso(casa: Path) -> None:
    """O uninstall: sai o `0` nosso de cada arquivo; o que ela pôs fica."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]},
                            "C": {"enviromentOptions": [{"key": _XALIA, "value": "1"}]}})
    _lutris_flatpak(casa)
    _flatpak(casa, _RETROARCH)
    _por_override(casa, _RETROARCH, f"[Environment]\n{_XALIA}=1\n")
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "0"
    assert (_lista_do_jogo(heroic, "A") or {})[_XALIA] == "0"
    feitos, completo = cpe.desfazer_as_estradas([_pasta()], casa)
    assert completo, [f.erro for f in feitos if f.erro]
    assert _XALIA not in _lista_global(heroic), "a global do Heroic ficou com o nosso"
    assert _XALIA not in (_lista_do_jogo(heroic, "A") or {}), "a cópia de A ficou com o nosso"
    assert (_lista_do_jogo(heroic, "C") or {}).get(_XALIA) == "1", "a escolha dela em C saiu"
    assert _XALIA not in _override(casa, "net.lutris.Lutris"), "a caixa do Lutris ficou"
    assert _override(casa, _RETROARCH).get(_XALIA) == "1", "a escolha dela no RetroArch saiu"


def test_o_jogo_excluido_do_heroic_nao_recebe(casa: Path) -> None:
    """A cópia do jogo excluído fica sem o nosso; o vizinho segue a global, com ele."""
    lx = lista_de_exclusao
    heroic = _heroic(casa, {"A": {}, "B": {}})
    _carona(casa)
    assert lx.adicionar(_janela(0), lancador="heroic", nome="A", lar=casa) == "adicionado"
    for _ in range(2):
        copia = _lista_do_jogo(heroic, "A")
        assert copia is not None, "a exclusão não deu a A uma lista própria"
        assert _XALIA not in copia, f"o jogo excluído A recebeu {_XALIA}={copia[_XALIA]}"
        assert _lista_do_jogo(heroic, "B") is None
        assert _lista_global(heroic)[_XALIA] == "0"
        _carona(casa)


def test_o_jogo_excluido_do_lutris_pelo_wine_herda_a_caixa(casa: Path) -> None:
    """O excluído pelo Wine sem Proton fica com o `0` da caixa, que é o padrão ali."""
    lx = lista_de_exclusao
    yml = _lutris_flatpak_pelo_wine(casa)
    _carona(casa)
    assert lx.adicionar(_JANELA, lancador="lutris", nome="Recettear", lar=casa) == "adicionado"
    env = _env_do_yml(yml)
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in env, "a exclusão do Lutris não cobriu a caixa"
    assert _XALIA not in env, f"o `.yml` do excluído levou {_XALIA}={env[_XALIA]!r}"
    assert _override(casa, "net.lutris.Lutris")[_XALIA] == "0"
    assert lx.tirar(_JANELA, lar=casa) == "removido"
    assert _XALIA not in _env_do_yml(yml)


def test_a_aba_lancadores_nao_cobra_o_que_ela_pos(casa: Path) -> None:
    """Com o valor dela no lugar do nosso, nada falta: o dela manda."""
    heroic = _heroic(casa, {"A": {}, "B": {"enviromentOptions": []}})
    atalhos = dict(cpe.cartoes_com_estrada())["heroic"]
    assert cpe.onde_falta_o_ambiente("heroic", atalhos, lar=casa) == ("A", "B")
    _carona(casa)
    assert cpe.onde_falta_o_ambiente("heroic", atalhos, lar=casa) == ()
    _trocar_o_nosso(heroic / "config.json")
    _trocar_o_nosso(heroic / "GamesConfig" / "B.json")
    assert _lista_global(heroic)[_XALIA] == "1"
    assert (_lista_do_jogo(heroic, "B") or {})[_XALIA] == "1"
    assert cpe.onde_falta_o_ambiente("heroic", atalhos, lar=casa) == ()


def test_o_limpa_nao_chama_de_rastro_o_xalia_dela(casa: Path) -> None:
    """O «limpa?» conhece a variável, e a conta como «pode ser sua»."""
    assert _XALIA in m.VARIAVEIS_DO_PRODUTO
    texto = json.dumps({"defaultSettings": {"enviromentOptions": [
        {"key": _XALIA, "value": "1"}]}})
    assert m.variaveis_do_produto_no_heroic(texto) == [_XALIA]
    assert _XALIA in m._VARIAVEIS_QUE_PODEM_SER_DELA


def _global_dela(heroic: Path, valor: str) -> None:
    """Ela põe `PROTON_USE_XALIA` na lista global do Heroic, à mão."""
    dado = json.loads((heroic / "config.json").read_text())
    dado["defaultSettings"]["enviromentOptions"].append({"key": _XALIA, "value": valor})
    (heroic / "config.json").write_text(json.dumps(dado))


def test_com_a_global_dela_o_nosso_da_copia_sai_no_desfazer(casa: Path) -> None:
    """O `1` dela na global, e a cópia de A sem a chave: a carona põe o `0` na cópia."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}})
    _global_dela(heroic, "1")
    for _ in range(2):
        _carona(casa)
        assert (_lista_do_jogo(heroic, "A") or {}).get(_XALIA) == "0"
        assert _lista_global(heroic)[_XALIA] == "1"
    feitos, completo = cpe.desfazer_as_estradas([_pasta()], casa)
    assert completo, [f.erro for f in feitos if f.erro]
    assert _XALIA not in (_lista_do_jogo(heroic, "A") or {}), (
        "o uninstall deixou o nosso na cópia de A")
    assert _lista_global(heroic)[_XALIA] == "1", "o desfazer tirou o dela da global"


def test_ela_troca_a_global_e_o_nosso_da_copia_continua_nosso(casa: Path) -> None:
    """Ela troca o nosso `0` da global por `1`: a cópia de A segue com o nosso, e ele sai."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}})
    _carona(casa)
    _trocar_o_nosso(heroic / "config.json")
    for _ in range(2):
        _carona(casa)
    assert (_lista_do_jogo(heroic, "A") or {}).get(_XALIA) == "0"
    cpe.desfazer_as_estradas([_pasta()], casa)
    assert _XALIA not in (_lista_do_jogo(heroic, "A") or {}), (
        "o nosso da cópia de A virou dela e ficou depois do uninstall")
    assert _lista_global(heroic)[_XALIA] == "1"


def test_o_jogo_excluido_com_a_global_dela_sai_sem_o_nosso(casa: Path) -> None:
    """Com o `1` dela na global, o jogo excluído do Heroic não leva o `0` que a carona pôs."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]},
                            "B": {}})
    _global_dela(heroic, "1")
    _carona(casa)
    assert lista_de_exclusao.adicionar(
        _janela(0), lancador="heroic", nome="A", lar=casa) == "adicionado"
    copia = _lista_do_jogo(heroic, "A") or {}
    assert _XALIA not in copia, f"o jogo excluído A recebeu {_XALIA}={copia.get(_XALIA)}"
    assert copia.get("MANGOHUD") == "1"


def _tirar_da_global(heroic: Path) -> None:
    """Ela tira `PROTON_USE_XALIA` da lista global do Heroic, à mão."""
    dado = json.loads((heroic / "config.json").read_text())
    dado["defaultSettings"]["enviromentOptions"] = [
        x for x in dado["defaultSettings"]["enviromentOptions"] if x["key"] != _XALIA]
    (heroic / "config.json").write_text(json.dumps(dado))


def test_o_zero_que_ela_tinha_antes_do_hefesto_fica(casa: Path) -> None:
    """O `0` dela na global, de antes do Hefesto, continua lá depois do uninstall."""
    heroic = _heroic(casa, {})
    _global_dela(heroic, "0")
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "0"
    cpe.desfazer_as_estradas([_pasta()], casa)
    assert _lista_global(heroic).get(_XALIA) == "0", "o uninstall tirou o 0 que era dela"


def test_o_um_que_ela_tirou_nao_volta_no_desfazer(casa: Path) -> None:
    """Ela tinha `1`, tirou, e a carona pôs o `0`: o desfazer tira o `0` e não devolve o `1`."""
    heroic = _heroic(casa, {})
    _global_dela(heroic, "1")
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "1"
    _tirar_da_global(heroic)
    _carona(casa)
    assert _lista_global(heroic)[_XALIA] == "0"
    cpe.desfazer_as_estradas([_pasta()], casa)
    assert _XALIA not in _lista_global(heroic), "o desfazer devolveu o 1 que ela já tinha tirado"


def test_o_zero_dela_copiado_para_o_jogo_fica_no_uninstall(casa: Path) -> None:
    """O `0` dela na global antes do Hefesto, e o Heroic o copiou para o jogo A."""
    heroic = _heroic(casa, {"A": {"enviromentOptions": [
        {"key": "MANGOHUD", "value": "1"}, {"key": _XALIA, "value": "0"}]}})
    _global_dela(heroic, "0")
    for _ in range(2):
        _carona(casa)
        assert (_lista_do_jogo(heroic, "A") or {}).get(_XALIA) == "0"
    feitos, completo = cpe.desfazer_as_estradas([_pasta()], casa)
    assert completo, [f.erro for f in feitos if f.erro]
    assert _lista_global(heroic).get(_XALIA) == "0", "o uninstall tirou o 0 dela da global"
    copia = _lista_do_jogo(heroic, "A") or {}
    assert copia.get(_XALIA) == "0", (
        f"o uninstall tirou da cópia de A o 0 que ela tinha antes do Hefesto: {copia}")
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in copia, "o nosso ficou na cópia de A"


def test_o_excluido_que_segue_a_global_dela_fica_com_o_zero_dela(casa: Path) -> None:
    """O `0` dela na global antes do Hefesto, e o jogo A excluído segue a global."""
    heroic = _heroic(casa, {"A": {}, "B": {}})
    _global_dela(heroic, "0")
    _carona(casa)
    assert lista_de_exclusao.adicionar(
        _janela(0), lancador="heroic", nome="A", lar=casa) == "adicionado"
    for _ in range(2):
        copia = _lista_do_jogo(heroic, "A")
        assert copia is not None, "a exclusão não deu a A uma lista própria"
        assert copia.get(_XALIA) == "0", f"o jogo excluído A perdeu o 0 dela: {copia}"
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in copia, "o excluído levou o nosso"
        _carona(casa)


def test_o_recibo_do_uninstall_nao_diz_que_ela_mudou_o_que_ja_era_dela(casa: Path) -> None:
    """O `1` dela na global antes do Hefesto fica, e o recibo não diz «mudou depois»."""
    heroic = _heroic(casa, {})
    _global_dela(heroic, "1")
    _carona(casa)
    feitos, _ = cpe.desfazer_as_estradas([_pasta()], casa)
    assert _lista_global(heroic)[_XALIA] == "1"
    recibo = " ".join(cpe.frase_do_desfeito(f) for f in feitos)
    assert "mudou depois do Hefesto" not in recibo, recibo


def test_o_recibo_do_uninstall_diz_quando_ela_trocou_o_nosso(casa: Path) -> None:
    """Ela troca o nosso `0` por `1` depois da carona: o recibo diz que ficou o dela."""
    heroic = _heroic(casa, {})
    _carona(casa)
    _trocar_o_nosso(heroic / "config.json")
    feitos, _ = cpe.desfazer_as_estradas([_pasta()], casa)
    assert _lista_global(heroic)[_XALIA] == "1"
    recibo = " ".join(cpe.frase_do_desfeito(f) for f in feitos)
    assert f"mudou depois do Hefesto: {_XALIA}" in recibo, recibo


@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_o_xalia_chega_em_todo_modo_e_de_um_a_quatro(casa: Path, jogadores: int) -> None:
    """DualSense, Xbox, Navegação e Nativo, de um a quatro jogadores: o `0` fica em todos.

    O `default.env` de cada modo sai do dono (`launch_env.compose_env`), e a
    carona roda a cada troca. O `IGNORE` segue o modo; o xalia não depende dele.
    MORDIDA: em `ambiente_da_carona`, junte as correções só quando a ponte traz
    o `SDL_GAMECONTROLLER_IGNORE_DEVICES`, e esta reprova na Navegação.
    """
    from hefesto_dualsense4unix.daemon import launch_env

    heroic = _heroic(casa, {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}})
    _lutris_flatpak(casa)
    _flatpak(casa, _RETROARCH)
    gamepad = {"native_mode": False, "emulation_enabled": True, "fisicos": jogadores}
    modos = {
        "DualSense": {**gamepad, "flavor": "dualsense", "backends": ["uhid"] * jogadores},
        "Xbox": {**gamepad, "flavor": "xbox", "backends": ["uinput"] * jogadores},
        "Navegação": {"native_mode": False, "emulation_enabled": False, "flavor": "dualsense",
                      "backends": [], "fisicos": jogadores},
        "Nativo": {"native_mode": True, "emulation_enabled": False, "flavor": "dualsense",
                   "backends": [], "fisicos": jogadores},
    }
    for modo, estado in modos.items():
        env = launch_env.compose_env(**estado)
        (_pasta() / "default.env").write_text("".join(f"{k}={v}\n" for k, v in env.items()))
        _carona(casa)
        onde = {"a global do Heroic": _lista_global(heroic),
                "a cópia de A": _lista_do_jogo(heroic, "A") or {},
                "a caixa do Lutris": _override(casa, "net.lutris.Lutris"),
                "a caixa do RetroArch": _override(casa, _RETROARCH)}
        for nome, ambiente in onde.items():
            assert ambiente.get(_XALIA) == "0", (
                f"{modo}, {jogadores} jogador(es): {nome} {ambiente}")
