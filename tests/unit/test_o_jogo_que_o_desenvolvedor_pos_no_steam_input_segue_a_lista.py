"""O-JOGO-QUE-LE-O-STEAM-INPUT-NAO-RECEBE-O-CONTROLE-DOBRADO-01 (31/10/2026).

O jogo cujo desenvolvedor declara o Steam Input (`config/steamconfigurator3rdpartynative`
no cache de apps da Steam, a máscara que o diário da Steam imprime como
«Opted-in Controller Mask for AppId N: 1000|máscara») recebe o controle virtual do
Hefesto por dois caminhos: a leitura direta e a API do Steam Input, que a Steam liga
sozinha sem configuração por jogo da conta e sem escrever `UseSteamControllerConfig`.
O `--desligar-fora-da-lista` só via a configuração por jogo, e deixava esse jogo de fora.

Este arquivo trava:

1. a leitura da máscara num cache de apps binário montado aqui, e a falha fechada;
2. o lar de mentira: o jogo declarado fora da lista ganha `"0"`, inclusive o instalado
   que a Steam ainda não abriu; o da lista e o sem máscara ficam como estão;
3. a segunda passada não escreve nem faz backup;
4. o cache ilegível não inventa alvo, e a configuração por jogo continua valendo;
5. o `--apply` do install conta o jogo fora da lista como trabalho: sem isso ele dizia
   «nada a fazer», não fechava a Steam e o `"0"` nunca chegava ao disco.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin
from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte

_CONTA = "10"
_DECLARADO_ABERTO = "3587610"
_DECLARADO_NUNCA_ABERTO = "2129530"
_DECLARADO_NA_LISTA = "2497900"
_SEM_MASCARA = "3628950"
_CONFIGURADO = "316790"
_FORA_DO_DISCO = "480"

_MAGIA_29 = 0x07564429


def _kv(chaves: list[str], mapa: dict[str, object]) -> bytes:
    """KeyValues binário da Steam com a tabela de chaves do formato 29."""
    saida = bytearray()
    for nome, valor in mapa.items():
        if nome not in chaves:
            chaves.append(nome)
        indice = struct.pack("<I", chaves.index(nome))
        if isinstance(valor, dict):
            saida += b"\x00" + indice + _kv(chaves, valor)
        elif isinstance(valor, int):
            saida += b"\x02" + indice + struct.pack("<i", valor)
        else:
            saida += b"\x01" + indice + str(valor).encode("utf-8") + b"\x00"
    return bytes(saida + b"\x08")


def _cache_de_apps(mascaras: dict[str, int | str | None]) -> bytes:
    """Um `appinfo.vdf` de formato 29 com um app por appid, a máscara quando há."""
    chaves: list[str] = []
    entradas = bytearray()
    for appid, mascara in mascaras.items():
        config: dict[str, object] = {"contenttype": "3"}
        if mascara is not None:
            config["steamconfigurator3rdpartynative"] = mascara
        corpo = b"\x00" * 60 + _kv(
            chaves, {"appinfo": {"appid": int(appid), "config": config}}
        )
        entradas += struct.pack("<II", int(appid), len(corpo)) + corpo
    entradas += struct.pack("<I", 0)
    tabela = struct.pack("<I", len(chaves)) + b"".join(
        c.encode("utf-8") + b"\x00" for c in chaves
    )
    deslocamento = 16 + len(entradas)
    return struct.pack("<IIq", _MAGIA_29, 1, deslocamento) + bytes(entradas) + tabela


def _vdf(viva: dict[str, str | None]) -> str:
    linhas = ['"UserLocalConfigStore"', "{", '\t"apps"', "\t{"]
    for appid, valor in viva.items():
        linhas += [f'\t\t"{appid}"', "\t\t{"]
        if valor is not None:
            linhas.append(f'\t\t\t"UseSteamControllerConfig"\t\t"{valor}"')
        linhas.append('\t\t\t"SteamControllerRumble"\t\t"-1"')
        linhas.append("\t\t}")
    linhas += ["\t}", '\t"SteamController_PSSupport"\t\t"0"', "}", ""]
    return "\n".join(linhas)


def _valores(texto: str) -> dict[str, str | None]:
    viva = ponte.arvore_viva(ponte.ler_arvores(texto))
    assert viva is not None, "o parser não achou a árvore viva"
    return {appid: par[0] for appid, par in viva.chaves.items()}


def _fotografia(raiz: Path) -> dict[str, str]:
    return {
        str(p.relative_to(raiz)): hashlib.md5(p.read_bytes()).hexdigest()
        for p in sorted(raiz.rglob("*"))
        if p.is_file()
    }


class TestAMascaraDoDesenvolvedor:
    @pytest.mark.parametrize(
        ("valor", "esperado"),
        [(15, 15), (65533, 65533), ("10", 10), (0, 0), ("0", 0), (None, 0),
         (True, 0), (-1, 0), ("abc", 0)],
    )
    def test_a_mascara_de_um_app(self, valor: object, esperado: int) -> None:
        config = {} if valor is None else {"steamconfigurator3rdpartynative": valor}
        assert proton_pin.mascara_do_desenvolvedor({"appinfo": {"config": config}}) == esperado

    def test_o_cache_diz_quem_o_desenvolvedor_pos_no_steam_input(
        self, tmp_path: Path
    ) -> None:
        cache = tmp_path / "appinfo.vdf"
        cache.write_bytes(_cache_de_apps({
            _DECLARADO_ABERTO: 15, _SEM_MASCARA: None, _FORA_DO_DISCO: 0,
            _DECLARADO_NA_LISTA: "65533",
        }))
        pedidos = {_DECLARADO_ABERTO, _SEM_MASCARA, _FORA_DO_DISCO, _DECLARADO_NA_LISTA, "99"}
        assert ponte.steam_input_do_desenvolvedor(cache, pedidos) == {
            _DECLARADO_ABERTO, _DECLARADO_NA_LISTA,
        }
        assert ponte.steam_input_do_desenvolvedor(cache, {_SEM_MASCARA}) == set()

    def test_cache_que_nao_existe_e_nenhum_declarado(self, tmp_path: Path) -> None:
        assert ponte.steam_input_do_desenvolvedor(tmp_path / "ausente", {"1"}) == set()

    @pytest.mark.parametrize(
        "bruto",
        [b"\x00\x01", struct.pack("<IIq", 0x12345678, 1, 16), None],
        ids=["curto", "magia-desconhecida", "entrada-cortada"],
    )
    def test_cache_que_nao_se_entende_levanta(
        self, tmp_path: Path, bruto: bytes | None
    ) -> None:
        cache = tmp_path / "appinfo.vdf"
        if bruto is None:
            inteiro = _cache_de_apps({_DECLARADO_ABERTO: 15})
            bruto = inteiro[:40]
        cache.write_bytes(bruto)
        with pytest.raises(ValueError):
            ponte.steam_input_do_desenvolvedor(cache, {_DECLARADO_ABERTO})

    def test_o_endereco_do_cache_e_o_da_mesma_raiz(self, tmp_path: Path) -> None:
        vdf = tmp_path / "raiz/userdata/77/config/localconfig.vdf"
        assert ponte.cache_de_apps_da_conta(vdf) == tmp_path / "raiz/appcache/appinfo.vdf"
        assert ponte.cache_de_apps_da_conta(tmp_path / "localconfig.vdf") is None


def _montar_lar(raiz: Path) -> dict[str, Path]:
    home = raiz / "home"
    steam = home / ".steam/steam"
    vdf = steam / f"userdata/{_CONTA}/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(
        _vdf({
            _DECLARADO_ABERTO: None, _DECLARADO_NA_LISTA: None,
            _SEM_MASCARA: None, _CONFIGURADO: None,
        }),
        encoding="utf-8",
    )
    cache = steam / "appcache/appinfo.vdf"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(_cache_de_apps({
        _DECLARADO_ABERTO: 15, _DECLARADO_NUNCA_ABERTO: 65535,
        _DECLARADO_NA_LISTA: 65533, _SEM_MASCARA: None, _FORA_DO_DISCO: 65535,
    }))
    steamapps = steam / "steamapps"
    for appid, nome in ((_DECLARADO_NUNCA_ABERTO, "Jogo Novo"), (_DECLARADO_ABERTO, "Jogo")):
        (steamapps / "common" / nome).mkdir(parents=True)
        (steamapps / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n'
            f'\t"installdir"\t\t"{nome}"\n}}\n',
            encoding="utf-8",
        )
    configs = steamapps / f"common/Steam Controller Configs/{_CONTA}/config"
    configs.mkdir(parents=True)
    (configs / _CONFIGURADO).mkdir()
    lista = home / ".config/hefesto-dualsense4unix/steam_input_apps.txt"
    lista.parent.mkdir(parents=True)
    lista.write_text(f"{_DECLARADO_NA_LISTA}\n", encoding="utf-8")
    return {"home": home, "vdf": vdf, "cache": cache}


class TestOLarDeMentira:
    @pytest.fixture()
    def lar(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
        casa = _montar_lar(tmp_path)
        monkeypatch.setenv("XDG_CONFIG_HOME", str(casa["home"] / ".config"))
        monkeypatch.setattr(ponte, "steam_running", lambda: False)
        monkeypatch.setattr(ponte, "steam_game_running", lambda: False)
        return casa

    def test_o_jogo_declarado_fora_da_lista_ganha_zero(self, lar: dict[str, Path]) -> None:
        """A MORDIDA: troque `configurados | declarados` por `configurados` e isto reprova."""
        status, detalhe = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_DESLIGADA, detalhe
        depois = _valores(lar["vdf"].read_text(encoding="utf-8"))
        assert depois == {
            _DECLARADO_ABERTO: "0",
            _DECLARADO_NUNCA_ABERTO: "0",
            _CONFIGURADO: "0",
        }
        assert _FORA_DO_DISCO not in repr(detalhe)

    def test_a_segunda_passada_nao_escreve(self, lar: dict[str, Path]) -> None:
        ponte.garantir_fora_da_lista_desligado(lar["home"])
        foto = _fotografia(lar["home"])

        status, _ = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_NADA
        assert _fotografia(lar["home"]) == foto

    def test_com_a_steam_aberta_adia_sem_tocar(
        self, lar: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ponte, "steam_running", lambda: True)
        foto = _fotografia(lar["home"])

        status, _ = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_ADIADA_STEAM
        assert _fotografia(lar["home"]) == foto

    def test_cache_ilegivel_nao_inventa_alvo(self, lar: dict[str, Path]) -> None:
        lar["cache"].write_bytes(b"\x29\x44\x56\x07\x01\x00\x00\x00\xff")

        status, detalhe = ponte.garantir_fora_da_lista_desligado(lar["home"])

        assert status == ponte.PONTE_DESLIGADA, detalhe
        assert ponte.CACHE_DE_APPS_ILEGIVEL in [d["desfecho"] for d in detalhe]
        assert _valores(lar["vdf"].read_text(encoding="utf-8")) == {_CONFIGURADO: "0"}


_RAIZ = Path(__file__).resolve().parents[2]
_GUARDA = _RAIZ / "scripts" / "disable_steam_input.sh"
_DONO_DA_PONTE = _RAIZ / "src" / "hefesto_dualsense4unix" / "integrations"
_BASH = shutil.which("bash") or "/bin/bash"

_PONTE_DO_ENSAIO = """\
import runpy
import sys

DONO = {dono!r}
sys.path.insert(0, DONO)
import steam_launch_options as slo

_ler = slo.cmdline_de_pid


def _sem_o_jogo_da_maquina(pid):
    cmd = _ler(pid)
    return "" if slo._STEAM_LAUNCH_RE.search(cmd) else cmd


slo._cmdline_of = _sem_o_jogo_da_maquina
sys.argv[0] = DONO + "/steam_input_ponte.py"
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class TestOInstallContaOJogoForaDaLista:
    @pytest.fixture()
    def lar(self, tmp_path: Path) -> dict[str, Path]:
        casa = _montar_lar(tmp_path)
        lista = casa["home"] / ".config/hefesto-dualsense4unix/steam_input_apps.txt"
        lista.write_text("# vazia\n", encoding="utf-8")
        stubs = tmp_path / "stubs"
        stubs.mkdir()
        for nome, corpo in (("pgrep", "exit 1"), ("steam", "exit 0"), ("sleep", "exit 0")):
            alvo = stubs / nome
            alvo.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
            alvo.chmod(0o755)
        ponte_py = tmp_path / "ponte_do_ensaio.py"
        ponte_py.write_text(
            _PONTE_DO_ENSAIO.format(dono=str(_DONO_DA_PONTE)), encoding="utf-8"
        )
        return {**casa, "stubs": stubs, "ponte_py": ponte_py}

    def _roda(self, lar: dict[str, Path], modo: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["HOME"] = str(lar["home"])
        env["XDG_CONFIG_HOME"] = str(lar["home"] / ".config")
        env["PATH"] = f"{lar['stubs']}:/usr/bin:/bin"
        env["PONTE_PY"] = str(lar["ponte_py"])
        return subprocess.run(
            [_BASH, str(_GUARDA), modo],
            capture_output=True, text=True, check=False, env=env, timeout=120,
        )

    def test_o_apply_grava_o_zero_do_jogo_declarado(self, lar: dict[str, Path]) -> None:
        """A MORDIDA: arranque o `fora_da_lista_pendente` do `--apply` e isto reprova."""
        proc = self._roda(lar, "--apply")

        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "resultado=aplicado" in proc.stdout, proc.stdout
        assert f"fora da lista pendente: {_DECLARADO_ABERTO}" in proc.stdout
        depois = _valores(lar["vdf"].read_text(encoding="utf-8"))
        assert depois[_DECLARADO_ABERTO] == "0"
        assert depois[_DECLARADO_NUNCA_ABERTO] == "0"

    def test_o_status_pede_a_correcao(self, lar: dict[str, Path]) -> None:
        foto = _fotografia(lar["home"])

        proc = self._roda(lar, "--status")

        assert "resultado=precisa-corrigir" in proc.stdout, proc.stdout
        assert _fotografia(lar["home"]) == foto

    def test_a_segunda_passada_e_nada_a_fazer(self, lar: dict[str, Path]) -> None:
        self._roda(lar, "--apply")
        foto = _fotografia(lar["home"])

        proc = self._roda(lar, "--apply")

        assert "resultado=nada-a-fazer" in proc.stdout, proc.stdout
        assert "fora da lista pendente" not in proc.stdout
        assert _fotografia(lar["home"]) == foto
