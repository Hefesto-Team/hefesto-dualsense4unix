"""A-PERGUNTA-DO-APLICAR-DIZ-TODO-LANCADOR-01 — a pergunta diz o que o ato faz.

**O DEFEITO, medido em 02/10/2026 na integração:** o segundo clique do
«Aplicar soluções nos lançadores» (aba 09) escreve primeiro nos outros
lançadores (`cura_por_estrada.curar_todas_as_estradas`: o Heroic, o Lutris e
as caixas dos emuladores, sem fechar nada) e só depois fecha a Steam. A
pergunta do primeiro clique, o corpo do dono que o painel lê palavra por
palavra (`DaemonActionsMixin._STEAM_APPLY_CORPO`), falava só da Steam e
prometia *«Com um jogo aberto eu não mexo em nada»* — com um jogo aberto, a
carona já tinha escrito nos outros quando a Steam recusava.

AS RÉGUAS, e nenhuma digita a lista de lançadores: o que a pergunta
tem de nomear sai do que a carona ESCREVEU num lar de mentira.

1. a pergunta nomeia cada lançador que o ato escreve;
2. com um jogo aberto (a Steam recusa), a pergunta não promete «nada»;
3. o contrato de dono do gesto (`interface/sistema.GESTOS`) cita a carona e
   não diz «só a Steam»;
4. o backup só se promete onde ele existe;
5. a pergunta fala a língua da tela;
6. nos outros lançadores, a pergunta não promete «na hora»: o lançador aberto
   só lê o que a carona escreveu quando abrir de novo.

TUDO NUM LAR DE MENTIRA: o `HOME` e os `XDG_*` de cada teste. A Steam é dublê
no ponto em que o motor a fecharia (`with_steam_closed`), e o dublê sabe
recusar por jogo aberto.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.interface import sistema as aba_sistema
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

_PONTE = (
    ("SDL_GAMECONTROLLER_IGNORE_DEVICES", "0x054c/0x0ce6"),
    ("PROTON_DISABLE_HIDRAW", "0x054c/0x0ce6"),
    ("SDL_JOYSTICK_HIDAPI", "0"),
)

_JOGO_ABERTO = "jogo_aberto"


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(lar / ".cache"))
    a09._ARMADO.clear()
    a09._PAINEL[0] = None
    yield lar
    a09._ARMADO.clear()
    a09._PAINEL[0] = None


def _flatpak(lar: Path, app_id: str) -> None:
    """Um aplicativo Flatpak instalado do lado do usuário."""
    meta = lar / ".local/share/flatpak/app" / app_id / "current" / "active"
    meta.mkdir(parents=True)
    (meta / "metadata").write_text(f"[Application]\nname={app_id}\n")


def _montar(lar: Path) -> Path:
    """Um Heroic Flatpak com um jogo, um Lutris e um emulador Flatpak; a ponte."""
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE))
    casa = lar / ".var/app/com.heroicgameslauncher.hgl/config/heroic"
    (casa / "GamesConfig").mkdir(parents=True)
    (casa / "config.json").write_text(json.dumps(
        {"defaultSettings": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}}))
    copia = casa / "GamesConfig" / "jogo.json"
    copia.write_text(json.dumps(
        {"jogo": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}}, indent=2))
    _flatpak(lar, "net.lutris.Lutris")
    _flatpak(lar, "org.libretro.RetroArch")
    return copia


def _pergunta() -> str:
    """A pergunta que o primeiro clique põe no painel — pelo gesto de verdade."""
    carga = a09.aplicar_aos_jogos(
        Contexto(state={}, mesa=[], conectados=[], estados={}),
        {"gesto": "aplicar-aos-jogos", "texto": "o rótulo do desenho"}, None)
    painel = (carga.get("mesa") or {}).get(a09.REGISTRO)
    assert painel, f"o primeiro clique não escreveu no painel: {carga}"
    return " ".join(str(painel).split())


def _a_steam_recusa(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[bool]]:
    """Dubla a Steam no ponto em que o motor a fecharia: ela recusa por jogo aberto."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    visto: dict[str, list[bool]] = {"fechou": [], "aplicou": []}

    def _aplicar() -> dict[str, int]:
        visto["aplicou"].append(True)
        return {"applied": 0, "skipped": 0, "errors": 0}

    def _com_a_steam_fechada(acao: Any) -> tuple[str, Any]:
        visto["fechou"].append(True)
        return (_JOGO_ABERTO, None)

    monkeypatch.setattr(slo, "apply_wrapper_to_all_games", _aplicar, raising=False)
    monkeypatch.setattr(slo, "with_steam_closed", _com_a_steam_fechada)
    return visto


def _foto(lar: Path) -> dict[Path, str]:
    """O md5 de cada arquivo do lar, para saber o que o ato mudou."""
    return {p: hashlib.md5(p.read_bytes()).hexdigest()
            for p in lar.rglob("*") if p.is_file() and not p.is_symlink()}


def _o_que_mudou(antes: dict[Path, str], depois: dict[Path, str]) -> list[Path]:
    return sorted(p for p, h in depois.items() if antes.get(p) != h)


def _palavra_do_cartao(chave: str) -> str:
    """Como a pergunta chama o cartão que a carona escreveu."""
    if chave in a07._COM_BIBLIOTECA:
        return next(n for n in censo._ONDE if n.casefold() == chave)
    return "emuladores"


def test_a_pergunta_nomeia_cada_lancador_que_a_carona_escreve(_lar: Path) -> None:
    """A lista sai da carona de verdade, no lar de mentira — nunca digitada."""
    _montar(_lar)
    escritos = cpe.curar_todas_as_estradas()
    assert {"heroic", "lutris"} <= set(escritos), (
        f"o lar de mentira não montou o que a régua precisa: {escritos}")
    assert set(escritos) - set(a07._COM_BIBLIOTECA), (
        f"nenhum emulador recebeu o ambiente no lar de mentira: {escritos}")
    pergunta = _pergunta()
    faltam = sorted({_palavra_do_cartao(c) for c in escritos}
                    - {p for p in map(_palavra_do_cartao, escritos) if p in pergunta})
    assert not faltam, (
        f"o ato escreve em {sorted(escritos)}, e a pergunta não nomeia {faltam}:\n"
        f"{pergunta}")


def test_com_jogo_aberto_a_pergunta_nao_promete_nada(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O ato inteiro, com a Steam recusando: os outros já receberam o deles."""
    copia = _montar(_lar)
    visto = _a_steam_recusa(monkeypatch)
    pergunta = _pergunta()
    antes = _foto(_lar)
    with pytest.raises(RuntimeError):
        a09.aplicar_aos_jogos(
            Contexto(state={}, mesa=[], conectados=[], estados={}),
            {"gesto": "aplicar-aos-jogos", "texto": a09.CONFIRMA}, None)
    assert visto["fechou"] == [True] and visto["aplicou"] == [], visto
    mudaram = _o_que_mudou(antes, _foto(_lar))
    global_ = copia.parent.parent / "config.json"
    assert global_ in mudaram, (
        f"a carona não escreveu no Heroic do lar de mentira: {mudaram}")
    assert "não mexo em nada" not in pergunta, (
        "com um jogo aberto a Steam recusou e a carona JÁ escreveu em "
        f"{[str(p.relative_to(_lar)) for p in mudaram]}; a pergunta prometia "
        f"«não mexo em nada»:\n{pergunta}")


def test_o_dono_do_gesto_cita_a_carona() -> None:
    """O contrato de dono que o gerador da aba cobra antes do `data-gesto`."""
    dono = aba_sistema.GESTOS["aplicar-aos-jogos"]
    assert "curar_todas_as_estradas" in dono, dono
    assert "só a Steam" not in dono, dono


def _nomes_dos_outros() -> tuple[str, ...]:
    return (*(n for n in censo._ONDE if n.casefold() in a07._COM_BIBLIOTECA),
            "emuladores")


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?])\s+", texto) if f.strip()]


def test_o_backup_so_se_promete_onde_ele_existe(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Depois do ato, procura um backup ao lado de cada arquivo que a carona"""
    _montar(_lar)
    _a_steam_recusa(monkeypatch)
    pergunta = _pergunta()
    antes = _foto(_lar)
    with pytest.raises(RuntimeError):
        a09.aplicar_aos_jogos(
            Contexto(state={}, mesa=[], conectados=[], estados={}),
            {"gesto": "aplicar-aos-jogos", "texto": a09.CONFIRMA}, None)
    depois = _foto(_lar)
    estado = Path(cpe.caminho_do_registro()).parent
    mudaram = [p for p in _o_que_mudou(antes, depois) if estado not in p.parents]
    assert mudaram, "a carona não mudou arquivo nenhum de lançador no lar de mentira"
    sem_backup = [p for p in mudaram
                  if not any(q.name.startswith(p.name) and "bak" in q.name
                             and q != p for q in p.parent.iterdir())]
    if not sem_backup:
        return
    nomes = _nomes_dos_outros()
    culpadas = [f for f in _frases(pergunta)
                if "backup" in f and any(n in f for n in nomes)]
    assert not culpadas, (
        f"a carona mudou {[str(p.relative_to(_lar)) for p in sem_backup]} sem "
        f"backup ao lado, e a pergunta promete backup a eles: {culpadas}")


def test_a_pergunta_do_painel_e_a_do_dono() -> None:
    """As duas pontas continuam uma só: o painel lê o corpo do dono."""
    corpo = " ".join(_daemon.DaemonActionsMixin._STEAM_APPLY_CORPO.split())
    assert corpo in " ".join(a09._pergunta_da_steam().split())


def test_a_pergunta_fala_a_lingua_da_tela() -> None:
    """A pergunta é texto de tela, e a tela fala português: o atalho do"""
    pergunta = " ".join(a09._pergunta_da_steam().split())
    em_ingles = [p for p in ("launcher", "uninstall") if p in pergunta.casefold()]
    assert not em_ingles, f"a pergunta diz {em_ingles} na tela:\n{pergunta}"


_LIDA_AO_ABRIR = {
    "heroic": "o Heroic lê o config.json ao abrir (GlobalConfigV0.getSettings)",
    "caixa": "a caixa do Flatpak vale no `flatpak run` do lançador",
}


def test_nos_outros_lancadores_a_pergunta_nao_promete_na_hora(_lar: Path) -> None:
    """A carona escreve agora, e o lançador aberto só lê ao abrir de novo."""
    _montar(_lar)
    escritos = cpe.curar_todas_as_estradas()
    estradas = {"heroic" if c == "heroic" else "caixa" for c in escritos}
    assert estradas == set(_LIDA_AO_ABRIR), (
        f"o lar de mentira não montou as duas estradas da carona: {escritos}")
    pergunta = _pergunta()
    culpadas = [f for f in _frases(pergunta)
                if "lançadores" in f and "vale" in f and "abrir" not in f]
    assert not culpadas, (
        "a carona escreve no Heroic e nas caixas do Flatpak, que o lançador lê só "
        f"ao abrir ({'; '.join(_LIDA_AO_ABRIR.values())}), e a pergunta promete "
        f"que vale antes disso: {culpadas}")
