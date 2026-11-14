"""O jogo que oferece o `.exe` no Linux ganha o pino do Proton (O-SINFUL-SURVIVORS-ABRE-01)."""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp

PINO = "GE-Proton11-7-x86_64"
_TAB = "\t"

Lancamento = tuple[str, str | None]

SINFUL: list[Lancamento] = [
    ("Jogo.exe", None),
    ("Jogo_Linux_0.24.2.x86_64", "linux"),
]
NATIVO_COM_OSLIST: list[Lancamento] = [
    ("Outro.exe", "windows"),
    ("Outro", "linux"),
]
NATIVO_COM_SH: list[Lancamento] = [
    ("Terceiro.exe", "windows"),
    ("Terceiro.sh", "linux"),
    ("Terceiro.app", "macos"),
]
EXE_EM_PASTA: list[Lancamento] = [("Pasta\\Win64\\Jogo.EXE", ""), ("jogo.x86_64", "linux")]
BAT_NO_LINUX: list[Lancamento] = [("inicia.bat", "windows,linux")]


def _appinfo(apps: dict[str, tuple[str, list[Lancamento] | None]]) -> bytes:
    """Um `appcache/appinfo.vdf` v29 fabricado, com `common/oslist` e `config/launch`."""
    tabela: list[str] = []

    def chave(nome: str) -> bytes:
        if nome not in tabela:
            tabela.append(nome)
        return struct.pack("<I", tabela.index(nome))

    def texto(nome: str, valor: str) -> bytes:
        return b"\x01" + chave(nome) + valor.encode() + b"\0"

    corpo = b""
    for appid, (oslist, lancamentos) in apps.items():
        comum = texto("name", "Um Jogo") + texto("oslist", oslist)
        config = b""
        if lancamentos is not None:
            entradas = b""
            for i, (executavel, so) in enumerate(lancamentos):
                entrada = texto("executable", executavel)
                if so is not None:
                    entrada += b"\x00" + chave("config") + texto("oslist", so) + b"\x08"
                entradas += b"\x00" + chave(str(i)) + entrada + b"\x08"
            config = (
                b"\x00" + chave("config") + texto("installdir", "Jogo")
                + b"\x00" + chave("launch") + entradas + b"\x08" + b"\x08"
            )
        vdf = (
            b"\x00" + chave("appinfo")
            + b"\x02" + chave("appid") + struct.pack("<i", int(appid))
            + b"\x00" + chave("common") + comum + b"\x08"
            + config
            + b"\x08" + b"\x08"
        )
        cabecalho = struct.pack("<IIQ", 2, 0, 0) + b"\0" * 20 + struct.pack("<I", 1) + b"\0" * 20
        entrada_do_app = cabecalho + vdf
        corpo += struct.pack("<II", int(appid), len(entrada_do_app)) + entrada_do_app
    corpo += struct.pack("<I", 0)
    strings = struct.pack("<I", len(tabela)) + b"".join(s.encode() + b"\0" for s in tabela)
    return struct.pack("<IIq", 0x07564429, 1, 16 + len(corpo)) + corpo + strings


def _config_vdf(entradas: dict[str, str]) -> str:
    blocos = "".join(
        f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
        f'{_TAB * 6}"name"{_TAB * 2}"{nome}"\n'
        f'{_TAB * 6}"config"{_TAB * 2}""\n'
        f'{_TAB * 6}"priority"{_TAB * 2}"250"\n'
        f"{_TAB * 5}}}\n"
        for appid, nome in entradas.items()
    )
    return (
        '"InstallConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"CompatToolMapping"\n{_TAB * 4}{{\n{blocos}{_TAB * 4}}}\n'
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "lar"
    casa.mkdir()
    for var, sub in (("HOME", ""), ("XDG_CONFIG_HOME", ".config"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_STATE_HOME", ".local/state")):
        monkeypatch.setenv(var, str(casa / sub) if sub else str(casa))
    monkeypatch.setattr(pp, "steam_running", lambda: False)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    monkeypatch.setattr(pp, "baixar_a_ultima_do_ge",
                        lambda *_a, **_k: pp.Atualizacao("nao_consultado"))
    return casa


def _steam(lar: Path, apps: dict[str, tuple[str, list[Lancamento] | None]]) -> Path:
    raiz = lar / ".steam/steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir(parents=True)
    (raiz / "appcache").mkdir(parents=True)
    (raiz / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (raiz / "config" / "config.vdf").write_text(_config_vdf({"0": PINO}), encoding="utf-8")
    (raiz / "appcache" / "appinfo.vdf").write_bytes(_appinfo(apps))
    pino = raiz / "compatibilitytools.d" / PINO
    pino.mkdir(parents=True)
    (pino / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (pino / "version").write_text(f"1 {PINO}\n", encoding="utf-8")
    for appid in apps:
        (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"Um Jogo"\n}}\n',
            encoding="utf-8",
        )
    return raiz


MESA_DE_JOGOS: dict[str, tuple[str, list[Lancamento] | None]] = {
    "4540280": ("windows,linux", SINFUL),
    "9100005": ("windows,linux", NATIVO_COM_OSLIST),
    "9100006": ("windows,macos,linux", NATIVO_COM_SH),
    "9100001": ("windows,linux", EXE_EM_PASTA),
    "9100002": ("windows,linux", BAT_NO_LINUX),
    "9100003": ("windows,linux", None),
    "9100004": ("windows", [("Jogo.exe", None)]),
}


def test_o_appinfo_diz_o_que_a_steam_oferece_no_linux(tmp_path: Path) -> None:
    arquivo = tmp_path / "appinfo.vdf"
    arquivo.write_bytes(_appinfo(MESA_DE_JOGOS))
    lido = pp.executaveis_no_linux_do_appinfo(arquivo, [*MESA_DE_JOGOS, "777"])
    assert lido == {
        "4540280": ("Jogo.exe", "Jogo_Linux_0.24.2.x86_64"),
        "9100005": ("Outro",),
        "9100006": ("Terceiro.sh",),
        "9100001": ("Pasta\\Win64\\Jogo.EXE", "jogo.x86_64"),
        "9100002": ("inicia.bat",),
        "9100003": (),
        "9100004": ("Jogo.exe",),
    }


def test_cache_ilegivel_nao_inventa_executavel(tmp_path: Path) -> None:
    arquivo = tmp_path / "appinfo.vdf"
    arquivo.write_bytes(struct.pack("<II", 0x0756442A, 1) + b"\0" * 32)
    assert pp.executaveis_no_linux_do_appinfo(arquivo, ["1"]) is None


def test_quem_oferece_o_exe_no_linux_nao_e_nativo(lar: Path) -> None:
    """MORDIDA: devolva o `jogos_sem_entrada_nova` a olhar só o `common/oslist`."""
    _steam(lar, MESA_DE_JOGOS)
    nativos = pp.jogos_sem_entrada_nova(list(MESA_DE_JOGOS), home=lar)
    assert nativos == {"9100005", "9100006", "9100003"}


def test_o_sinful_ganha_o_pino_e_o_nativo_de_verdade_fica(lar: Path) -> None:
    """O botão, o install (`--lock --todos`) e o vigia (`--manter`) passam pela mesma classe."""
    raiz = _steam(lar, MESA_DE_JOGOS)
    r = pp.lock_proton_for_all_games(
        conf={"name": PINO, "url": "x", "sha256": "ab" * 32},
        home=lar, state_path=lar / "estado.json", todos=True,
    )
    assert r["status"] == "locked", r
    mapa = pp.extract_compat_tool_mapping(
        (raiz / "config" / "config.vdf").read_text(encoding="utf-8"))
    assert mapa.get("4540280") == PINO, mapa
    assert {a: mapa.get(a) for a in ("9100001", "9100002", "9100004")} == {
        "9100001": PINO, "9100002": PINO, "9100004": PINO}
    assert not {"9100005", "9100006", "9100003"} & set(mapa), mapa
