"""AS-SOLUCOES-NOS-LANCADORES-01 — as réguas.

«Aplicar soluções nos lançadores» vale para todo lançador, e a aba Lançadores
diz, por lançador, onde o ambiente do Hefesto falta.

MEDIDO ANTES, no disco dela e só lendo (01/10/2026): a lista global do Heroic
tinha as 8 variáveis que a ponte publica, e a cópia do Guardiões
(`GamesConfig/<app>.json`, de 22/09) não tinha três —
`PROTON_ENABLE_MHWILDS_USB_AUDIO`, `PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE` e
`SDL_ACCELEROMETER_AS_JOYSTICK`. O Heroic monta `{...globais, ...do jogo}`, e
todo jogo instalado tem cópia (ele a grava ao instalar): a carona e o botão
escreviam numa lista que o único jogo instalado dela não lia mais.

TUDO AQUI MORA NUM LAR DE MENTIRA: o `HOME` e o `XDG_*` de cada teste, e a
ponte publicada numa pasta do teste. Nenhuma Steam, nenhum lançador de
verdade.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx

_APP = "63a665088eb1480298f1e57943b225d8"
_CHAVE = "steam_app_1088850"
_IGNORE = ("SDL_GAMECONTROLLER_IGNORE_DEVICES", "0x054c/0x0ce6")
_HIDRAW = ("PROTON_DISABLE_HIDRAW", "0x054c/0x0ce6")
_MHWILDS = ("PROTON_ENABLE_MHWILDS_USB_AUDIO", "1")
_SONY = ("PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE", "1")
_ACELEROMETRO = ("SDL_ACCELEROMETER_AS_JOYSTICK", "0")
_CACHE = ("__GL_SHADER_DISK_CACHE", "1")
#: O que a ponte publica agora — a forma do `default.env` dela em 01/10.
_PONTE = (_HIDRAW, _IGNORE, _MHWILDS, _SONY, _ACELEROMETRO, _CACHE)
#: A cópia de 22/09: sem as três de depois, e com o cache que ELA pôs no jogo.
_COPIA_VELHA = (_HIDRAW, _IGNORE, ("__GL_SHADER_DISK_CACHE", "0"), ("MANGOHUD", "1"))


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    return lar


def _lista(pares: tuple[tuple[str, str], ...]) -> list[dict[str, str]]:
    return [{"key": k, "value": v} for k, v in pares]


def _ponte(tmp_path: Path, pares: tuple[tuple[str, str], ...] = _PONTE) -> Path:
    amb = tmp_path / "launch_env"
    amb.mkdir(exist_ok=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in pares))
    return amb


def _heroic(*, copia: tuple[tuple[str, str], ...] | None = _COPIA_VELHA) -> Path:
    """O Heroic flatpak com o Guardiões instalado; devolve a cópia do jogo."""
    casa = Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/heroic"
    (casa / "store_cache").mkdir(parents=True)
    (casa / "config.json").write_text(json.dumps(
        {"defaultSettings": {"enviromentOptions": _lista(_COPIA_VELHA)}}))
    (casa / "store_cache" / "umu.json").write_text(json.dumps({f"legendary_{_APP}": "umu-1088850"}))
    (casa / "store_cache" / "legendary_library.json").write_text(json.dumps(
        {"library": [{"app_name": _APP, "title": "Guardiões", "is_installed": True,
                      "install": {"executable": "retail/gotg.exe"}}]}))
    arquivo = casa / "GamesConfig" / f"{_APP}.json"
    if copia is not None:
        arquivo.parent.mkdir(parents=True)
        arquivo.write_text(json.dumps(
            {_APP: {"enviromentOptions": _lista(copia), "winePrefix": "/x"},
             "version": "v0", "explicit": True}, indent=2))
    return arquivo


def _pares(arquivo: Path) -> dict[str, str]:
    jogo = json.loads(arquivo.read_text())[_APP]
    return {e["key"]: e["value"] for e in jogo["enviromentOptions"]}


def _carona(tmp_path: Path, amb: Path) -> tuple[str, ...]:
    return cpe.curar_todas_as_estradas(lar=Path.home(), pasta_do_ambiente=amb,
                                       raiz_sistema=tmp_path / "sistema")


# ---------------------------------------------------------------------------
# 1 · A cópia de cada jogo do Heroic recebe o ambiente de agora
# ---------------------------------------------------------------------------
def test_a_carona_leva_o_ambiente_a_copia_do_jogo(tmp_path: Path) -> None:
    """ARRANQUE o `_por_o_nosso_nas_copias` do `curar_todas_as_estradas` e
    este teste reprova: a háptica pelo áudio e o acelerômetro não chegam ao
    jogo instalado — o estado medido no disco dela."""
    copia = _heroic()
    _carona(tmp_path, _ponte(tmp_path))
    pares = _pares(copia)
    for chave, valor in (_MHWILDS, _SONY, _ACELEROMETRO, _IGNORE, _HIDRAW):
        assert pares.get(chave) == valor, (chave, pares)
    assert pares["__GL_SHADER_DISK_CACHE"] == "0", (
        "o cache de shader é escolha dela PARA AQUELE JOGO, e a carona o trocou")
    assert pares["MANGOHUD"] == "1"


def test_no_modo_nativo_o_ignore_sai_da_copia(tmp_path: Path) -> None:
    """O Modo Nativo não publica o `IGNORE`. A cópia perde o nosso como a
    global perde. ARRANQUE o registro da casa (`_entrada_da_copia(entrada)`)
    do `_por_o_nosso_nas_copias` e este teste reprova: o jogo do Heroic no
    Modo Nativo abriria com o físico escondido e sem o virtual."""
    copia = _heroic()
    _carona(tmp_path, _ponte(tmp_path))
    assert _IGNORE[0] in _pares(copia)
    _carona(tmp_path, _ponte(tmp_path, tuple(p for p in _PONTE if p != _IGNORE)))
    assert _IGNORE[0] not in _pares(copia)


def test_o_jogo_sem_lista_propria_segue_a_global(tmp_path: Path) -> None:
    """Uma cópia sem `enviromentOptions` (o `{}` que o Heroic grava ao abrir a
    tela do jogo) segue a global: a carona não lhe dá lista própria."""
    copia = _heroic(copia=None)
    copia.parent.mkdir(parents=True)
    copia.write_text(json.dumps({_APP: {}, "version": "v0", "explicit": True}))
    _carona(tmp_path, _ponte(tmp_path))
    assert json.loads(copia.read_text())[_APP] == {}


def test_o_uninstall_tira_da_copia_o_que_a_carona_pos(tmp_path: Path) -> None:
    """A escrita nas cópias continua reversível: o desfazer do uninstall a lê
    pelo registro da casa. Se a carona escrevesse um valor que o registro não
    conhece, ele ficaria na cópia depois do uninstall."""
    copia = _heroic()
    amb = _ponte(tmp_path)
    _carona(tmp_path, amb)
    cpe.desfazer_as_estradas([amb], Path.home())
    pares = _pares(copia)
    assert not {_MHWILDS[0], _SONY[0], _ACELEROMETRO[0], _IGNORE[0]} & set(pares), pares
    assert pares.get("MANGOHUD") == "1"


def test_a_copia_do_excluido_nem_e_reescrita(tmp_path: Path) -> None:
    """O jogo excluído não recebe nada — e a cópia dele nem é regravada.
    ARRANQUE o filtro das `excluidas` do `_por_o_nosso_nas_copias` e este
    teste reprova: a carona escreveria o nosso e a manutenção da exclusão o
    tiraria logo depois, duas escritas por transição num arquivo dela."""
    copia = _heroic()
    amb = _ponte(tmp_path)
    assert lx.adicionar(_CHAVE, lancador="heroic", nome="Guardiões") == "adicionado"
    antes = copia.stat().st_mtime_ns
    texto = copia.read_text()
    os.utime(copia, ns=(antes - 10**9, antes - 10**9))
    marcado = copia.stat().st_mtime_ns
    _carona(tmp_path, amb)
    assert copia.read_text() == texto
    assert copia.stat().st_mtime_ns == marcado, "a cópia do jogo excluído foi regravada"


# ---------------------------------------------------------------------------
# 2 · Onde falta, por lançador — o que a aba Lançadores mostra
# ---------------------------------------------------------------------------
def test_onde_falta_mede_a_copia_e_nao_so_a_global(tmp_path: Path) -> None:
    """ARRANQUE a leitura das cópias do `onde_falta_o_ambiente` e este teste
    reprova: a global completa diria «no lugar» sobre o jogo que não a lê."""
    _heroic()
    amb = _ponte(tmp_path)
    (Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/heroic/config.json").write_text(
        json.dumps({"defaultSettings": {"enviromentOptions": _lista(_PONTE)}}))
    falta = cpe.onde_falta_o_ambiente("heroic", ("com.heroicgameslauncher.hgl",),
                                      pasta_do_ambiente=amb,
                                      raiz_sistema=tmp_path / "sistema")
    assert falta == ("Guardiões",)
    _carona(tmp_path, amb)
    assert cpe.onde_falta_o_ambiente("heroic", ("com.heroicgameslauncher.hgl",),
                                     pasta_do_ambiente=amb,
                                     raiz_sistema=tmp_path / "sistema") == ()


def test_o_excluido_nao_conta_como_falta(tmp_path: Path) -> None:
    """O jogo excluído está sem o ambiente de propósito."""
    _heroic()
    amb = _ponte(tmp_path)
    _carona(tmp_path, amb)
    lx.adicionar(_CHAVE, lancador="heroic", nome="Guardiões")
    assert cpe.onde_falta_o_ambiente("heroic", ("com.heroicgameslauncher.hgl",),
                                     pasta_do_ambiente=amb,
                                     raiz_sistema=tmp_path / "sistema") == ()


def test_onde_falta_mede_a_caixa_do_emulador(tmp_path: Path) -> None:
    """A caixa do Flatpak sem uma variável da ponte acusa falta; a carona a
    cura, e a caixa excluída não conta. ARRANQUE o ramo das caixas do
    `onde_falta_o_ambiente` e este teste reprova: o cartão do RetroArch nunca
    diria «Sem o ambiente do Hefesto»."""
    ativo = Path.home() / ".local/share/flatpak/app/org.libretro.RetroArch/current/active"
    ativo.mkdir(parents=True)
    (ativo / "metadata").write_text("[Application]\nname=org.libretro.RetroArch\n")
    override = Path.home() / ".local/share/flatpak/overrides/org.libretro.RetroArch"
    override.parent.mkdir(parents=True)
    override.write_text("[Environment]\nSDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6\n")
    amb = _ponte(tmp_path, (_IGNORE, _ACELEROMETRO))
    caixa = ("org.libretro.RetroArch",)

    def falta() -> tuple[str, ...]:
        return cpe.onde_falta_o_ambiente("retroarch", caixa, pasta_do_ambiente=amb,
                                         raiz_sistema=tmp_path / "sistema")

    assert falta() == caixa
    _carona(tmp_path, amb)
    assert falta() == ()
    override.write_text("[Environment]\n")
    lx.adicionar("emulador:retroarch", lancador="retroarch", nome="RetroArch — todos os jogos",
                 janelas=("org.libretro.RetroArch", "retroarch", "com.libretro.RetroArch"))
    assert falta() == (), "a caixa excluída contou como falta"


def test_sem_a_ponte_nao_ha_o_que_cobrar(tmp_path: Path) -> None:
    """Sem o ambiente publicado (serviço nunca ligado) não há com o que
    comparar: nenhum cartão acusa falta — nem com a global do Heroic ilegível,
    que é o caso em que a conta diria «falta» a todo jogo sem cópia. ARRANQUE
    a guarda do ambiente do `onde_falta_o_ambiente` e este teste reprova."""
    copia = _heroic(copia=None)
    copia.parent.parent.joinpath("config.json").write_text("{ torto")
    assert cpe.onde_falta_o_ambiente("heroic", ("com.heroicgameslauncher.hgl",),
                                     pasta_do_ambiente=tmp_path / "vazia",
                                     raiz_sistema=tmp_path / "sistema") == ()


def test_o_cartao_diz_onde_o_ambiente_falta() -> None:
    """A forma da Steam quando o atalho falta: o contador abre o corpo, a
    linha vem embaixo e o selo diz `COM IMPEDIMENTO`. ARRANQUE a linha do
    `cartao_sem_censo` e este teste reprova."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho

    heroic = next(x for x in desenho.SEM_FONTE if x.chave == "heroic")
    retroarch = next(x for x in desenho.SEM_FONTE if x.chave == "retroarch")
    disco = desenho.DoDisco(sem_ambiente=(("heroic", ("Guardiões",)),
                                          ("retroarch", ("org.libretro.RetroArch",))))
    cartao = desenho.cartao_sem_censo(heroic, "/opt/heroic", disco)
    assert cartao.selo == "warn"
    assert "1 jogo sem o ambiente do Hefesto" in cartao.diz
    assert cartao.diz.startswith(desenho.contador_html(0))
    caixa = desenho.cartao_sem_censo(retroarch, "/opt/retroarch", disco)
    assert caixa.selo == "warn" and "Sem o ambiente do Hefesto" in caixa.diz
    no_lugar = desenho.cartao_sem_censo(heroic, "/opt/heroic", desenho.SEM_DISCO)
    assert no_lugar.selo == "localizado"
    assert "ambiente" not in no_lugar.diz


def test_a_vigia_pergunta_ao_dono_da_estrada(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A vigia da aba 07 mede pelo dono da estrada, só nos cartões ACHADOS.
    ARRANQUE o `_onde_falta_o_ambiente` do `_ler_do_disco` e a linha nunca
    chega ao cartão."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    perguntas: list[str] = []

    def _dono(chave: str, atalhos: tuple[str, ...], **_k: object) -> tuple[str, ...]:
        perguntas.append(chave)
        return ("Guardiões",) if chave == "heroic" else ()

    monkeypatch.setattr(cpe, "onde_falta_o_ambiente", _dono)
    fora = a07._onde_falta_o_ambiente((("heroic", "/opt/heroic"), ("lutris", "")), ())
    assert fora == (("heroic", ("Guardiões",)),)
    assert perguntas == ["heroic"], "um cartão NÃO ACHADO foi medido"
    fonte = Path(a07.__file__).read_text(encoding="utf-8")
    corpo = fonte[fonte.index("def _ler_do_disco("):]
    assert "_onde_falta_o_ambiente(onde_estao, declarados)" in corpo


# ---------------------------------------------------------------------------
# 3 · O botão da aba Sistema aplica em todos
# ---------------------------------------------------------------------------
def test_o_botao_da_sistema_aplica_nos_outros_mesmo_com_a_steam_recusando(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Com jogo aberto a Steam recusa, e os outros lançadores já receberam o
    deles: nada ali fecha programa nenhum. ARRANQUE a carona do
    `aplicar_aos_jogos` e este teste reprova."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    caronas: list[bool] = []
    monkeypatch.setattr(cpe, "curar_todas_as_estradas",
                        lambda *a, **k: caronas.append(True) or ("heroic", "retroarch"))
    monkeypatch.setattr(slo, "apply_wrapper_to_all_games", lambda: {}, raising=False)
    monkeypatch.setattr(slo, "with_steam_closed", lambda acao: ("jogo_aberto", None))
    a09._ARMADO.clear()
    ctx = Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[], estados={})
    a09.aplicar_aos_jogos(ctx, {"gesto": "aplicar-aos-jogos", "texto": "rótulo"}, None)
    assert caronas == [], "o PRIMEIRO clique já aplicou — o consentimento sumiu"
    with pytest.raises(RuntimeError):
        a09.aplicar_aos_jogos(ctx, {"gesto": "aplicar-aos-jogos", "texto": a09.CONFIRMA}, None)
    a09._ARMADO.clear()
    a09._PAINEL[0] = None
    assert caronas == [True]
    assert "O ambiente do Hefesto está em: Heroic, RetroArch." in capsys.readouterr().err
