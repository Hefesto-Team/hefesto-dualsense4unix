"""O jogo de fora adicionado à Steam recebe o atalho, entra no catálogo, no censo e no pino.

O-JOGO-DE-FORA-ADICIONADO-A-STEAM-RECEBE-O-ATALHO-01 (22/11/2026).
D-2211-JOGO-DE-FORA-SO-VAI-AO-PROTON-SE-E-DO-WINDOWS: o jogo de fora entra no pino só quando o
executável é de Windows; o nativo do Linux fica como está.
TUDO É DE MENTIRA: o lar é ``tmp_path``, o ``shortcuts.vdf`` é montado byte a byte aqui, com a
forma que a Steam grava (número com sinal, `tags` aninhado, campos que o Hefesto não conhece), a
Steam está fechada por dublê e a rede é barrada.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o leitor que devolve vazio
reprova o leitor, o catálogo, o censo e o apply; o apply sem a passada dos atalhos reprova o apply e
a idempotência; o strip sem a passada dos atalhos reprova o desfazer; a lista de jogos sem os de
fora e o pino que os trata como nativos reprovam o caso do pino; o censo sem os atalhos reprova o
censo.
"""
from __future__ import annotations

import os
import socket
import struct
import subprocess
import sys
import textwrap
import zlib
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import atalhos_da_steam as atalhos
from hefesto_dualsense4unix.integrations import jogos_locais
from hefesto_dualsense4unix.integrations import proton_pin as pp
from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sentinela
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from tests.unit.test_o_pino_chega_a_qualquer_computador import (
    PINO,
    _jogo,
    _pino_na,
    _steam_de_verdade,
)

CONTA = "1000"
JANELA = (-1234567890) & 0xFFFFFFFF
LINUX = (-1111111111) & 0xFFFFFFFF
SEM_NUMERO_EXE = '"/jogos/emulador/retro.exe"'
SEM_NUMERO_NOME = "Sem número"
SEM_NUMERO = zlib.crc32((SEM_NUMERO_EXE + SEM_NUMERO_NOME).encode()) | 0x80000000
OPT_OUT = (-1000000007) & 0xFFFFFFFF


def _cs(texto: bytes | str) -> bytes:
    return (texto.encode() if isinstance(texto, str) else texto) + b"\x00"


def _texto(chave: str, valor: bytes | str) -> bytes:
    return b"\x01" + _cs(chave) + _cs(valor)


def _inteiro(chave: str, valor: int) -> bytes:
    return b"\x02" + _cs(chave) + struct.pack("<I", valor)


def _entrada(indice: int, *, appid: int | None, nome: bytes | str, exe: str,
             opcoes: str | None, resto: bytes = b"") -> bytes:
    corpo = b""
    if appid is not None:
        corpo += b"\x02" + _cs("appid") + struct.pack("<I", appid)
    corpo += _texto("AppName", nome) + _texto("Exe", exe) + _texto("StartDir", "/jogos")
    corpo += _texto("icon", "") + _texto("ShortcutPath", "")
    if opcoes is not None:
        corpo += _texto("LaunchOptions", opcoes)
    corpo += _inteiro("IsHidden", 0) + _inteiro("LastPlayTime", 1_700_000_000)
    corpo += b"\x00" + _cs("tags") + _texto("0", "favorito") + b"\x08" + resto
    return b"\x00" + _cs(str(indice)) + corpo + b"\x08"


def _arquivo(*entradas: bytes) -> bytes:
    return b"\x00" + _cs("shortcuts") + b"".join(entradas) + b"\x08\x08"


def _jogos(opcoes_janela: str | None = "", opcoes_linux: str | None = "-fullscreen %command%",
           opcoes_opt_out: str | None = "") -> bytes:
    return _arquivo(
        _entrada(0, appid=JANELA, nome="Jogo do Açaí", exe='"/jogos/gog/jogo.exe"',
                 opcoes=opcoes_janela),
        _entrada(1, appid=LINUX, nome="Emulador Nativo", exe='"/usr/bin/retroarch"',
                 opcoes=opcoes_linux),
        _entrada(2, appid=OPT_OUT, nome=b"Antigo \xe9 fora do utf8", exe='"/jogos/x/velho.EXE"',
                 opcoes=opcoes_opt_out),
    )


@pytest.fixture()
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "lar"
    casa.mkdir()
    monkeypatch.setenv("HOME", str(casa))
    for nome, rel in (("XDG_CONFIG_HOME", ".config"), ("XDG_CACHE_HOME", ".cache"),
                      ("XDG_DATA_HOME", ".local/share"), ("XDG_STATE_HOME", ".local/state")):
        monkeypatch.setenv(nome, str(casa / rel))
    for modulo in (slo, pp, sentinela):
        monkeypatch.setattr(modulo, "steam_running", lambda: False)
        monkeypatch.setattr(modulo, "steam_game_running", lambda: False)

    def _sem_rede(host: object, *_a: object, **_k: object) -> list[object]:
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", _sem_rede)
    return casa


def _conta(lar: Path, bruto: bytes | None = None) -> tuple[Path, Path]:
    raiz = lar / ".steam/steam"
    pasta = raiz / "userdata" / CONTA / "config"
    pasta.mkdir(parents=True, exist_ok=True)
    local = pasta / "localconfig.vdf"
    local.write_text(
        '"UserLocalConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
        '\t\t\t\t"apps"\n\t\t\t\t{\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n', encoding="utf-8")
    atalho = pasta / "shortcuts.vdf"
    atalho.write_bytes(_jogos() if bruto is None else bruto)
    return local, atalho


def test_o_leitor_traz_numero_sem_sinal_nome_exe_e_opcoes() -> None:
    achados = {a.appid: a for a in atalhos.atalhos_do_bruto(_jogos())}

    assert set(achados) == {str(JANELA), str(LINUX), str(OPT_OUT)}
    assert achados[str(JANELA)].nome == "Jogo do Açaí"
    assert achados[str(JANELA)].exe == '"/jogos/gog/jogo.exe"'
    assert achados[str(LINUX)].opcoes == "-fullscreen %command%"
    assert achados[str(JANELA)].e_do_windows
    assert achados[str(OPT_OUT)].e_do_windows
    assert not achados[str(LINUX)].e_do_windows


def test_a_entrada_sem_o_campo_do_numero_usa_o_que_a_steam_deriva() -> None:
    bruto = _arquivo(_entrada(0, appid=None, nome=SEM_NUMERO_NOME, exe=SEM_NUMERO_EXE, opcoes=""))

    assert [a.appid for a in atalhos.atalhos_do_bruto(bruto)] == [str(SEM_NUMERO)]


def test_o_arquivo_cortado_nao_se_le_e_nunca_levanta_pelo_caminho_do_disco(tmp_path: Path) -> None:
    bruto = _jogos()
    arquivo = tmp_path / "shortcuts.vdf"
    arquivo.write_bytes(bruto[:60])

    with pytest.raises(ValueError):
        atalhos.atalhos_do_bruto(bruto[:60])
    assert atalhos.atalhos_do_arquivo(arquivo) == []
    assert atalhos.atalhos_do_arquivo(tmp_path / "nao-existe.vdf") == []
    with pytest.raises(ValueError, match="shortcuts"):
        atalhos.atalhos_do_bruto(b"\x00outra\x00\x08")


def test_o_catalogo_e_o_nome_do_jogo_trazem_os_jogos_de_fora(lar: Path) -> None:
    _conta(lar)
    _steam_de_verdade(lar)
    _jogo(lar / ".steam/steam", "9949958", "Um Jogo da Loja")

    jogos = {j.appid: j.nome for j in jogos_locais.jogos_da_biblioteca_steam(lar)}

    assert jogos[str(JANELA)] == "Jogo do Açaí"
    assert jogos[str(LINUX)] == "Emulador Nativo"
    assert jogos["9949958"] == "Um Jogo da Loja"
    assert slo.nome_do_appid(str(JANELA), lar) == "Jogo do Açaí"
    assert slo.rotulo_do_jogo(str(JANELA), lar) == f"Jogo do Açaí (appid {JANELA})"


def test_o_apply_poe_o_atalho_nas_opcoes_do_jogo_de_fora_e_o_resto_passa_igual(
        lar: Path) -> None:
    local, atalho = _conta(lar)

    res = slo.apply_wrapper_to_all_games(
        home=lar, excluir=[str(OPT_OUT)], vdfs=[local])

    esperado = _jogos(
        opcoes_janela=slo.WRAPPER_LAUNCH,
        opcoes_linux=slo.com_o_atalho("-fullscreen %command%"),
    )
    assert atalho.read_bytes() == esperado
    assert res["errors"] == []
    aplicados = {a["appid"] for a in res["applied"] if a["vdf"] == str(atalho)}
    assert aplicados == {str(JANELA), str(LINUX)}
    assert {"vdf": str(atalho), "appid": str(OPT_OUT), "reason": "opt_out_da_usuaria"} \
        in res["skipped"]
    assert any(p.name.startswith("shortcuts.vdf.bak.hefesto-launch-")
               for p in atalho.parent.iterdir())


def test_o_apply_repetido_nao_escreve_de_novo(lar: Path) -> None:
    local, atalho = _conta(lar)
    slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])
    firmado = atalho.read_bytes()
    copias = sorted(p.name for p in atalho.parent.iterdir())

    res = slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])

    assert atalho.read_bytes() == firmado
    assert sorted(p.name for p in atalho.parent.iterdir()) == copias
    assert res["applied"] == []
    assert {s["reason"] for s in res["skipped"] if s["vdf"] == str(atalho)} == {"ja_tem_wrapper"}


def test_a_entrada_sem_o_campo_das_opcoes_ganha_o_campo_no_fim_do_dicionario(lar: Path) -> None:
    bruto = _arquivo(_entrada(0, appid=JANELA, nome="Sem Campo", exe='"/j/a.exe"', opcoes=None))
    local, atalho = _conta(lar, bruto)

    slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])

    novo = atalho.read_bytes()
    assert [a.opcoes for a in atalhos.atalhos_do_arquivo(atalho)] == [slo.WRAPPER_LAUNCH]
    campo = b"\x01LaunchOptions\x00" + slo.WRAPPER_LAUNCH.encode() + b"\x00"
    assert novo.replace(campo, b"", 1) == bruto


def test_a_steam_aberta_ou_o_jogo_aberto_nao_deixam_escrever_nos_atalhos(
        lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local, atalho = _conta(lar)
    antes = atalho.read_bytes()
    monkeypatch.setattr(slo, "steam_running", lambda: True)

    res = slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])

    assert atalho.read_bytes() == antes
    assert [e["reason"] for e in res["errors"]] == ["steam_aberta"]


def test_tirar_o_atalho_de_um_jogo_de_fora_so_toca_nele(lar: Path) -> None:
    local, atalho = _conta(lar)
    slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])

    res = slo.tirar_o_atalho_dos_jogos([str(LINUX)], home=lar, vdfs=[local])

    assert atalho.read_bytes() == _jogos(opcoes_janela=slo.WRAPPER_LAUNCH,
                                         opcoes_linux="-fullscreen %command%",
                                         opcoes_opt_out=slo.WRAPPER_LAUNCH)
    assert [r["appid"] for r in res["removed"] if r["vdf"] == str(atalho)] == [str(LINUX)]


def test_o_strip_do_desinstalar_devolve_os_jogos_de_fora_como_estavam(lar: Path) -> None:
    local, atalho = _conta(lar)
    original = atalho.read_bytes()
    slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])
    assert atalho.read_bytes() != original

    assert slo.process_atalhos(local) == 3
    assert atalho.read_bytes() == original


def test_o_censo_conta_o_jogo_de_fora_sem_o_atalho_e_depois_com_ele(lar: Path) -> None:
    local, atalho = _conta(lar)
    registro = lar / "visto.json"

    antes = sentinela.censo_do_wrapper(lar, [local], registro=registro, recusados=[], anotar=False)

    assert {j.appid for j in antes.faltantes} == {str(JANELA), str(LINUX), str(OPT_OUT)}
    assert {j.appid: j.vdf for j in antes.faltantes}[str(JANELA)] == str(atalho)
    assert "Jogo do Açaí" in {j.appid: j.rotulo for j in antes.faltantes}[str(JANELA)]
    assert antes.com_wrapper == []

    slo.apply_wrapper_to_all_games(home=lar, vdfs=[local])
    depois = sentinela.censo_do_wrapper(lar, [local], registro=registro, recusados=[],
                                        anotar=False)

    assert depois.faltantes == []
    assert sorted(depois.com_wrapper) == sorted([str(JANELA), str(LINUX), str(OPT_OUT)])


def test_o_pino_alcanca_o_jogo_de_fora_do_windows_e_deixa_o_nativo(lar: Path) -> None:
    """D-2211-JOGO-DE-FORA-SO-VAI-AO-PROTON-SE-E-DO-WINDOWS."""
    _conta(lar)
    raiz = _steam_de_verdade(lar)
    _pino_na(raiz)
    _jogo(raiz, "9949958")
    vdf = raiz / "config" / "config.vdf"

    assert pp.list_installed_appids(lar) == sorted(
        {"9949958", str(JANELA), str(OPT_OUT)}, key=int)

    conf = {"name": PINO, "url": "https://exemplo.invalido/x.tar.gz", "sha256": "0" * 64}
    pp.lock_proton_for_all_games(conf=conf, home=lar, config_vdf=vdf,
                                 state_path=lar / "lock.json", todos=True,
                                 compat_dir=raiz / "compatibilitytools.d")

    mapa = pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
    assert mapa.get(str(JANELA)) == PINO
    assert mapa.get(str(OPT_OUT)) == PINO
    assert str(LINUX) not in mapa


def test_o_avulso_sem_a_estrutura_do_produto_ainda_poe_o_atalho_no_jogo_de_fora(
        tmp_path: Path) -> None:
    """O install roda o `steam_launch_options.py` solto, e o Python de fora não tem `structlog`."""
    integracoes = Path(slo.__file__).resolve().parent
    entrada = tmp_path / "entrada.vdf"
    entrada.write_bytes(_jogos())
    saida = tmp_path / "saida.vdf"
    codigo = textwrap.dedent(f"""
        import importlib.abc, sys
        class Barra(importlib.abc.MetaPathFinder):
            def find_spec(self, nome, caminho=None, alvo=None):
                if nome.split(".")[0] == "structlog":
                    raise ModuleNotFoundError(nome)
        sys.meta_path.insert(0, Barra())
        sys.path.insert(0, {str(integracoes)!r})
        import steam_launch_options as s
        assert "hefesto_dualsense4unix.daemon.launch_env" not in sys.modules
        novo, aplicados, _ = s.apply_wrapper_atalhos_bruto(open({str(entrada)!r}, "rb").read())
        open({str(saida)!r}, "wb").write(novo)
        print(",".join(aplicados))
    """)

    r = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, text=True,
                       cwd=tmp_path, check=False,
                       env={"HOME": str(tmp_path), "PATH": os.environ.get("PATH", "/usr/bin:/bin")})

    assert r.returncode == 0, r.stderr
    assert set(r.stdout.strip().split(",")) == {str(JANELA), str(LINUX), str(OPT_OUT)}
    primeiro = next(iter(atalhos.atalhos_do_bruto(saida.read_bytes())))
    assert primeiro.opcoes == slo.WRAPPER_LAUNCH
