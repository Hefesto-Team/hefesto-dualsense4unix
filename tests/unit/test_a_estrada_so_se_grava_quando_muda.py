"""A-ESTRADA-SO-SE-GRAVA-QUANDO-MUDA-01 — as réguas.

A materialização roda a cada troca de cabo, rádio e install. Sem mudança, nenhum arquivo de
lançador é tocado: nem temporário, nem ``fsync``, nem ``replace``, nem ``mtime``.
MORDIDA: arranque a comparação de ``cura_por_estrada._escrever_atomico`` e estas reprovam.
"""
from __future__ import annotations

import hashlib
import os
import stat
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import (
    _PONTE,
    _flatpak,
    _heroic,
    _lutris_flatpak,
)

_CAIXAS = ("org.libretro.RetroArch", "org.DolphinEmu.dolphin-emu", "io.mgba.mGBA")
_JOGO_DO_HEROIC = {"A": {"enviromentOptions": [{"key": "MANGOHUD", "value": "1"}]}}


@pytest.fixture(autouse=True)
def _as_extensoes_de_caixa_ligadas(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.as_caixas_das_extensoes import ligar

    ligar(monkeypatch)


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um lar de mentira com todo lançador que tem estrada, e a ponte publicada."""
    lar = tmp_path / "lar"
    lar.mkdir()
    assert not str(lar).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    _publicar(_PONTE)
    _heroic(lar, _JOGO_DO_HEROIC)
    _lutris_flatpak(lar)
    for caixa in _CAIXAS:
        _flatpak(lar, caixa)
    return lar


def _pasta() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    return launch_env_dir(ensure=True)


def _publicar(ambiente: dict[str, str]) -> None:
    (_pasta() / "default.env").write_text("".join(f"{k}={v}\n" for k, v in ambiente.items()))


def _carona(lar: Path) -> tuple[str, ...]:
    return cpe.curar_todas_as_estradas(lar=lar, raiz_sistema=lar.parent / "sistema")


def _alvos(lar: Path) -> dict[str, Path]:
    """Cada arquivo de lançador que a carona mantém, e o registro da carona."""
    overrides = lar / ".local/share/flatpak/overrides"
    heroic = lar / ".var/app/com.heroicgameslauncher.hgl/config/heroic"
    return {
        "heroic": heroic / "config.json",
        "copia do jogo": heroic / "GamesConfig" / "A.json",
        "lutris": overrides / "net.lutris.Lutris",
        **{caixa: overrides / caixa for caixa in _CAIXAS},
        "registro": cpe.caminho_do_registro(_pasta()),
    }


def _foto_do_disco(lar: Path) -> dict[str, tuple[int, int]]:
    """(``mtime_ns``, inode) de todo arquivo do lar, fora a pasta do ambiente."""
    ambiente = _pasta()
    fora: dict[str, tuple[int, int]] = {}
    for caminho in lar.rglob("*"):
        if caminho.is_file() and ambiente not in caminho.parents:
            st = caminho.stat()
            fora[str(caminho)] = (st.st_mtime_ns, st.st_ino)
    return fora


class _Gravacoes:
    def __init__(self) -> None:
        self.fsyncs: list[str] = []
        self.trocas: Counter[str] = Counter()


@pytest.fixture
def gravacoes(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Gravacoes]:
    """Conta o ``fsync`` e o ``replace`` de verdade, no chão do Python."""
    conta = _Gravacoes()
    fsync, replace = os.fsync, Path.replace

    def _fsync(fd: int) -> None:
        conta.fsyncs.append(os.readlink(f"/proc/self/fd/{fd}"))
        fsync(fd)

    def _replace(self: Path, alvo: str | Path) -> Path:
        conta.trocas[str(alvo)] += 1
        return replace(self, alvo)

    monkeypatch.setattr(os, "fsync", _fsync)
    monkeypatch.setattr(Path, "replace", _replace)
    yield conta


def _os_arquivos_nasceram(lar: Path) -> None:
    """Zero com o alvo fora da mesa não é zero: todo arquivo existe e carrega a ponte."""
    for nome, alvo in _alvos(lar).items():
        assert alvo.is_file(), f"{nome} não nasceu: a régua mediria um lançador ausente"
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in _alvos(lar)["heroic"].read_text()
    for caixa in ("lutris", *_CAIXAS):
        assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" in _alvos(lar)[caixa].read_text()


def test_a_segunda_carona_nao_toca_em_arquivo_nenhum(casa: Path, gravacoes: _Gravacoes) -> None:
    assert set(_carona(casa)) >= {"heroic", "lutris", "retroarch", "dolphin", "mgba"}
    _os_arquivos_nasceram(casa)
    antes = _foto_do_disco(casa)
    gravacoes.fsyncs.clear()
    gravacoes.trocas.clear()

    assert set(_carona(casa)) >= {"heroic", "lutris", "retroarch", "dolphin", "mgba"}

    assert gravacoes.fsyncs == [], gravacoes.fsyncs
    assert not gravacoes.trocas, gravacoes.trocas
    assert _foto_do_disco(casa) == antes


def test_a_ordem_das_chaves_no_ambiente_nao_muda_o_texto(
    casa: Path, gravacoes: _Gravacoes,
) -> None:
    """A mesma entrada dá o mesmo texto, byte a byte: a ordem do ``default.env`` não conta."""
    _carona(casa)
    antes = _foto_do_disco(casa)
    gravacoes.fsyncs.clear()
    _publicar(dict(reversed(list(_PONTE.items()))))

    _carona(casa)

    assert gravacoes.fsyncs == [], gravacoes.fsyncs
    assert _foto_do_disco(casa) == antes


def test_valor_diferente_grava_uma_vez_e_depois_cala(
    casa: Path, gravacoes: _Gravacoes,
) -> None:
    _carona(casa)
    alvos = _alvos(casa)
    gravacoes.fsyncs.clear()
    gravacoes.trocas.clear()
    _publicar({**_PONTE, "SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0dff"})

    _carona(casa)

    for caixa in ("heroic", "lutris", *_CAIXAS):
        assert "0x054c/0x0dff" in alvos[caixa].read_text(), caixa
        assert gravacoes.trocas[str(alvos[caixa])] == 1, (caixa, gravacoes.trocas)
    gravacoes.fsyncs.clear()
    gravacoes.trocas.clear()
    _carona(casa)
    assert gravacoes.fsyncs == [], gravacoes.fsyncs
    assert not gravacoes.trocas, gravacoes.trocas


class TestOEscritorAtomico:
    def test_texto_igual_nao_faz_nada(self, tmp_path: Path, gravacoes: _Gravacoes) -> None:
        alvo = tmp_path / "pasta" / "alvo.json"
        cpe._escrever_atomico(alvo, "{}\n")
        st = alvo.stat()
        gravacoes.fsyncs.clear()
        gravacoes.trocas.clear()

        cpe._escrever_atomico(alvo, "{}\n")

        assert gravacoes.fsyncs == []
        assert not gravacoes.trocas
        assert (alvo.stat().st_mtime_ns, alvo.stat().st_ino) == (st.st_mtime_ns, st.st_ino)
        assert [p.name for p in alvo.parent.iterdir()] == ["alvo.json"]

    def test_texto_diferente_grava_e_guarda_o_modo(self, tmp_path: Path) -> None:
        alvo = tmp_path / "alvo"
        alvo.write_text("velho")
        alvo.chmod(0o640)

        cpe._escrever_atomico(alvo, "novo")

        assert alvo.read_text() == "novo"
        assert stat.S_IMODE(alvo.stat().st_mode) == 0o640

    def test_o_arquivo_que_nao_existe_nasce(self, tmp_path: Path) -> None:
        alvo = tmp_path / "nova" / "alvo"

        cpe._escrever_atomico(alvo, "novo")

        assert alvo.read_text() == "novo"

    def test_o_que_nao_e_utf8_se_substitui(self, tmp_path: Path) -> None:
        alvo = tmp_path / "alvo"
        alvo.write_bytes(b"\xff\xfe")

        cpe._escrever_atomico(alvo, "novo")

        assert alvo.read_text() == "novo"

    def test_o_alvo_que_nao_se_le_ainda_se_grava(self, tmp_path: Path) -> None:
        alvo = tmp_path / "alvo"
        alvo.write_text("velho")
        alvo.chmod(0o000)
        if os.access(alvo, os.R_OK):
            pytest.skip("o root lê tudo")

        cpe._escrever_atomico(alvo, "novo")

        alvo.chmod(0o600)
        assert alvo.read_text() == "novo"


_MESAS = {
    "4 cabos": ("cabo", "cabo", "cabo", "cabo"),
    "3 cabos e 1 rádio": ("cabo", "cabo", "cabo", "radio"),
    "2 e 2": ("radio", "cabo", "radio", "cabo"),
    "1 cabo e 3 rádios": ("radio", "radio", "cabo", "radio"),
    "4 rádios": ("radio", "radio", "radio", "radio"),
    "só o P3": ("radio",),
}
_MODOS = ("dualsense", "xbox", "navegacao", "nativo")


def _foto(modo: str, jogadores: int) -> launch_env._FotoDoLancamento:
    native = modo == "nativo"
    emulacao = modo in ("dualsense", "xbox")
    mascara = "xbox" if modo == "xbox" else "dualsense"
    backends = tuple(["uinput" if modo == "xbox" else "uhid"] * jogadores) if emulacao else ()
    vivo = launch_env.ModoAntecipado(native, emulacao, mascara, backends, "vivo", jogadores)
    return launch_env._FotoDoLancamento(
        ordem=0, native=native, enabled=emulacao, flavor=mascara, backends=backends,
        fisicos=jogadores, modo_vivo=vivo, em_cena=frozenset(), identidade=None,
        permite_uhid=True, vpads_previstos=jogadores,
        leitor=launch_env._OQueOFioLe(False), publicar=lambda _d: None,
        carimbar=lambda: None, foto_ms=0.0)


def _materializar(modo: str, jogadores: int) -> None:
    launch_env._a_parte_de_fora(_foto(modo, jogadores), launch_env._rodar_na_hora)


def _textos(alvos: dict[str, Path]) -> dict[str, str]:
    return {nome: hashlib.sha256(alvo.read_bytes()).hexdigest() for nome, alvo in alvos.items()}


@pytest.mark.parametrize("mesa", _MESAS)
@pytest.mark.parametrize("modo", _MODOS)
def test_os_quatro_plugando_gravam_so_o_que_mudou_de_fato(
    casa: Path, gravacoes: _Gravacoes, mesa: str, modo: str,
) -> None:
    """Na mesa de cada jogo, um controle sobe de cada vez: a cada degrau, cada arquivo grava
    no máximo uma vez, e grava só se o conteúdo dele mudou. O mesmo degrau de novo, nada."""
    _materializar(modo, 1)
    alvos = _alvos(casa)
    for nome, alvo in alvos.items():
        assert alvo.is_file(), f"{nome} não nasceu: a régua mediria um lançador ausente"
    for chegaram in range(1, len(_MESAS[mesa]) + 1):
        antes = _textos(alvos)
        gravacoes.trocas.clear()

        _materializar(modo, chegaram)

        depois = _textos(alvos)
        for nome, alvo in alvos.items():
            vezes = gravacoes.trocas[str(alvo)]
            assert vezes == (1 if antes[nome] != depois[nome] else 0), (nome, chegaram, vezes)
        foto = _foto_do_disco(casa)
        gravacoes.trocas.clear()

        _materializar(modo, chegaram)

        assert _foto_do_disco(casa) == foto, (mesa, modo, chegaram)
        assert not [a for a in gravacoes.trocas if a in {str(x) for x in alvos.values()}]


def test_a_ida_e_volta_do_modo_chega_ao_mesmo_byte(casa: Path) -> None:
    """Xbox e DualSense se alternando: cada troca grava, e a volta repete o mesmo byte."""
    _materializar("xbox", 2)
    _materializar("dualsense", 2)
    _materializar("xbox", 2)
    xbox = _textos(_alvos(casa))
    _materializar("dualsense", 2)
    dualsense = _textos(_alvos(casa))
    assert xbox["heroic"] != dualsense["heroic"], "a troca de modo não mudou a estrada"

    _materializar("xbox", 2)

    de_lancador = [k for k in xbox if k != "registro"]
    fim = _textos(_alvos(casa))
    assert [fim[k] for k in de_lancador] == [xbox[k] for k in de_lancador]
