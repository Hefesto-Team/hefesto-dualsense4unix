"""O jogo GDK vibra pelo GameInput da casa (O-JOGO-GDK-VIBRA-PELO-GAMEINPUT-01).

O Proton acha o stub `gameinput.dll` dele antes do `WINEDLLPATH`; a peça xgameruntime carrega o
`gameinput.dll` do Hefesto pelo caminho inteiro, e a receita põe `gameinput=n,b` nos mesmos sinais
GDK da peça (nunca por appid). O GameInput só conta com as duas DLLs no sha do pino; sem ele, o par
da xgameruntime fica sozinho e o jogo abre como abria. O contrato da DLL (o QI v2, os motores, o
report 0x02 no cabo e o 0x31 no rádio) se mede no prefixo de teste por
`scripts/ensaios/o_contrato_da_peca_gameinput.py`; aqui fica o que o Python e o install decidem.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env
from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda
from tests.unit.test_o_jogo_que_pede_receita_de_ambiente import _lancar_par, _pasta_real

_RAIZ = Path(__file__).resolve().parents[2]
_FONTE = _RAIZ / "assets" / "gdk-runtime"
_XGR = b"MZ a xgameruntime de mentira"
_GI = b"MZ o gameinput de mentira"
_OS_DOIS = "xgameruntime=b;gameinput=n,b"
_PASTA = "@hefesto-wine"
_PAR = {"WINEDLLOVERRIDES": "xgameruntime=b", "WINEDLLPATH": _PASTA}
_TRIO = {"WINEDLLOVERRIDES": _OS_DOIS, "WINEDLLPATH": _PASTA}


def _jogo(biblioteca: Path, appid: str, *, sinal: str | None = "MicrosoftGame.config") -> Path:
    apps = biblioteca / "steamapps"
    raiz = apps / "common" / f"Jogo{appid}"
    exe_dir = raiz / "Binaries" / "Win64"
    exe_dir.mkdir(parents=True)
    (exe_dir / "Jogo-Win64-Shipping.exe").write_bytes(b"MZ" + b"\0" * 64)
    (apps / f"appmanifest_{appid}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"Jogo {appid}"\n'
        f'\t"installdir"\t\t"Jogo{appid}"\n}}\n',
        encoding="utf-8",
    )
    if sinal:
        (raiz / sinal).write_text("<Game/>", encoding="utf-8")
    return raiz


def _por(casa: Path, relativo: str, conteudo: bytes) -> Path:
    alvo = rda.pasta_da_peca(casa) / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_bytes(conteudo)
    return alvo


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Biblioteca Steam num HOME de mentira, com as duas peças no lugar e um pino de mentira que
    bate com as duas."""
    casa = tmp_path / "casa"
    biblioteca = casa / ".local" / "share" / "Steam"
    (biblioteca / "steamapps").mkdir(parents=True)
    assert not str(casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
    monkeypatch.setenv("HOME", str(casa))
    pino = tmp_path / "pino.txt"
    pino.write_text(
        f"sha256={hashlib.sha256(_XGR).hexdigest()}\n"
        f"gameinput_sha256={hashlib.sha256(_GI).hexdigest()}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rda, "PINO_DA_PECA", pino)
    _por(casa, "x86_64-windows/xgameruntime.dll", _XGR)
    _por(casa, "nativa/gameinput.dll", _GI)
    return biblioteca


def _casa(biblioteca: Path) -> Path:
    return biblioteca.parents[2]


# --- a tabela -------------------------------------------------------------------------------


def test_a_linha_do_gameinput_pede_n_b_nos_mesmos_sinais_da_peca_gdk() -> None:
    tabela = {r.id: r for r in rda.carregar_tabela()}
    gi, gdk = tabela["gdk-gameinput"], tabela["gdk-xgameruntime"]
    assert (gi.variavel, gi.valor, gi.peca) == (
        "WINEDLLOVERRIDES", "gameinput=n,b", rda.PECA_GAMEINPUT_DO_HEFESTO
    )
    assert gi.sinais == gdk.sinais, "o GameInput liga pelos sinais GDK, nunca por appid"
    linha = next(
        ln for ln in rda.TABELA.read_text(encoding="utf-8").splitlines()
        if ln.startswith("gdk-gameinput,")
    )
    assert not re.search(r"\b\d{5,}\b", linha), "appid embarcado na linha do GameInput"


# --- o disco do jogo ------------------------------------------------------------------------


def test_o_jogo_gdk_com_as_duas_pecas_recebe_os_dois_overrides(lar: Path) -> None:
    """Prova da D-2210-O-JOGO-GDK-VIBRA-PELO-GAMEINPUT-DA-CASA."""
    raiz = _jogo(lar, "710001")
    assert rda.ambiente_do_jogo(raiz) == _TRIO
    assert rda.pecas_que_faltam(raiz) == ()
    assert rda.ambientes_dos_jogos() == {"710001": _TRIO}


def test_o_outro_sinal_gdk_tambem_leva_o_gameinput(lar: Path) -> None:
    raiz = _jogo(lar, "710002", sinal="installscript-gamingrepair.vdf")
    assert rda.ambiente_do_jogo(raiz) == _TRIO


def test_o_jogo_que_nao_e_gdk_nao_recebe_nada(lar: Path) -> None:
    raiz = _jogo(lar, "710003", sinal=None)
    assert rda.ambiente_do_jogo(raiz) == {} and rda.pecas_que_faltam(raiz) == ()


@pytest.mark.parametrize("como", ["ausente", "outro-sha", "pino-sem-a-chave"])
def test_sem_o_gameinput_o_par_da_xgameruntime_fica_sozinho(
    lar: Path, tmp_path: Path, como: str
) -> None:
    """O pior caso é o de hoje: o jogo GDK abre com a peça, só sem vibrar, e nada falta."""
    dll = rda.pasta_da_peca(_casa(lar)) / "nativa" / "gameinput.dll"
    if como == "ausente":
        dll.unlink()
    elif como == "outro-sha":
        dll.write_bytes(b"MZ outro gameinput, de outra origem")
    else:
        sha = hashlib.sha256(_XGR).hexdigest()
        rda.PINO_DA_PECA.write_text(f"sha256={sha}\n", encoding="utf-8")
    raiz = _jogo(lar, "710004")
    assert rda.ambiente_do_jogo(raiz) == _PAR
    assert rda.pecas_que_faltam(raiz) == ()
    assert not rda.gameinput_do_hefesto_instalado()


def test_o_gameinput_sem_a_peca_gdk_nao_entra(lar: Path) -> None:
    """Sem a xgameruntime ninguém carrega o `gameinput.dll`: o `n,b` sozinho não serve a nada."""
    (rda.pasta_da_peca(_casa(lar)) / "x86_64-windows" / "xgameruntime.dll").unlink()
    raiz = _jogo(lar, "710005")
    assert rda.ambiente_do_jogo(raiz) == {}
    assert rda.pecas_que_faltam(raiz) == (rda.NOME_DA_PECA_DO_HEFESTO,)


# --- o arquivo do daemon e o wrapper --------------------------------------------------------


def _daemon_de_mentira() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
    )


def test_o_daemon_escreve_os_dois_overrides_numa_linha_so(
    lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    _jogo(lar, "710006")
    materialize_launch_env(_daemon_de_mentira())
    linhas = (pasta / "steam_app_710006.env").read_text(encoding="utf-8").splitlines()
    assert f"WINEDLLOVERRIDES={_OS_DOIS}" in linhas and f"WINEDLLPATH={_PASTA}" in linhas
    assert sum(ln.startswith("WINEDLLOVERRIDES=") for ln in linhas) == 1


def test_os_dois_overrides_atravessam_o_wrapper_ate_o_processo_do_jogo(tmp_path: Path) -> None:
    saida = _lancar_par(
        tmp_path, [f"WINEDLLOVERRIDES={_OS_DOIS}", f"WINEDLLPATH={_PASTA}"], com_peca=True
    )
    assert saida == (_OS_DOIS, _pasta_real(tmp_path))


# --- a peça C, o pino e o install falam da mesma pasta --------------------------------------


def test_a_peca_gdk_carrega_o_gameinput_da_pasta_que_o_python_confere() -> None:
    fonte = (_FONTE / "xgameruntime.c").read_text(encoding="utf-8")
    preload = fonte.split("static void preload_gameinput(void)", 1)[1].split("\n}\n", 1)[0]
    assert '"%s/nativa/gameinput.dll"' in preload
    assert 'GetEnvironmentVariableA("WINEDLLPATH"' in preload
    assert 'GetProcAddress(h, "HefestoPecaGameInput")' in preload, "sem conferir a identidade"
    init = fonte.split("InitializeApiImplEx2(UINT64 gdk", 1)[1].split("\n}\n", 1)[0]
    assert "preload_gameinput();" in init, "o preload tem de sair no init, fora do DllMain"
    gameinput = (_FONTE / "gameinput.c").read_text(encoding="utf-8")
    assert "HefestoPecaGameInput(void)" in gameinput
    assert rda.pasta_da_peca(Path("/c")) / "nativa" / "gameinput.dll" == Path(
        "/c/.local/share/hefesto-dualsense4unix/wine/nativa/gameinput.dll"
    )


def test_o_pino_e_o_construir_levam_o_gameinput() -> None:
    pino = dict(
        ln.split("=", 1) for ln in (_FONTE / "pino.txt").read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#") and "=" in ln
    )
    assert re.fullmatch(r"[0-9a-f]{64}", pino["gameinput_sha256"])
    assert pino["gameinput_url"].endswith("/releases/download/v{versao}/gameinput.dll")
    assert rda._sha256_do_pino(chave="gameinput_sha256") == pino["gameinput_sha256"]
    construir = (_FONTE / "construir.sh").read_text(encoding="utf-8")
    assert '-o "$saida/gameinput.dll" gameinput.c -lhid -lsetupapi' in construir
    assert '"$(pino gameinput_sha256)"' in construir, "o --conferir não olha o gameinput"


def test_o_install_poe_o_gameinput_em_nativa_so_com_o_sha_do_pino() -> None:
    install = (_RAIZ / "install.sh").read_text(encoding="utf-8")
    bloco = install.split("# 4b-5. A peça GDK", 1)[1].split("# 4c.", 1)[0]
    assert (
        'PECA_GAMEINPUT_TARGET="${HOME}/.local/share/hefesto-dualsense4unix/wine/nativa/gameinput.dll"'
        in bloco
    )
    assert 'gameinput_sha256 gameinput_url gameinput.dll "${PECA_GAMEINPUT_TARGET}"' in bloco
    assert "sudo" not in bloco


# --- o juiz dos bytes da régua --------------------------------------------------------------


def _regua() -> object:
    caminho = _RAIZ / "scripts" / "ensaios" / "o_contrato_da_peca_gameinput.py"
    spec = importlib.util.spec_from_file_location("o_contrato_da_peca_gameinput", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _usb(fraco: int, forte: int, flag0: int = 0x03) -> bytes:
    return bytes([0x02, flag0, 0x00, fraco, forte]) + bytes(43)


def _bt(fraco: int, forte: int, flag0: int = 0x03, crc_certo: bool = True) -> bytes:
    corpo = bytes([0x31, 0x00, 0x10, flag0, 0x00, fraco, forte]) + bytes(67)
    crc = zlib.crc32(b"\xa2" + corpo) ^ (0 if crc_certo else 1)
    return corpo + crc.to_bytes(4, "little")


def test_o_juiz_da_regua_aceita_o_report_certo_e_recusa_o_torto() -> None:
    regua = _regua()
    julgar = regua.julgar_bytes  # type: ignore[attr-defined]
    usb = _usb(0x80, 0xFF) * 2 + _usb(0, 0)
    bt = _bt(0xBF, 0x40) + _bt(0, 0)
    assert all(julgar(usb, bt).values())
    flag_errado = _usb(0x80, 0xFF, flag0=0x0F) + _usb(0, 0)
    assert not julgar(flag_errado, bt)["bytes_usb"], "o flag0 errado passou"
    crc_errado = _bt(0xBF, 0x40, crc_certo=False) + _bt(0, 0)
    assert not julgar(usb, crc_errado)["bytes_bt"], "o CRC errado passou"
    assert not julgar(_usb(0x80, 0xFF) + _usb(0, 0), bt)["reenvio"], "sem reenvio passou"
    assert not julgar(usb + _usb(0, 0), bt)["zero_no_fim"], "o zero repetido passou"


def test_sem_dualsense_a_peca_responde_como_o_gameinput_do_proton() -> None:
    """Prova da D-2210-SEM-DUALSENSE-O-GAMEINPUT-DA-CASA-RESPONDE-COMO-O-DO-PROTON."""
    # O pior caso é o de hoje: sem DualSense (modo Xbox, ou só pad de outra marca), o jogo GDK que
    # lê a entrada pelo GameInput tem de receber o E_NOTIMPL do Proton e cair na XInput.
    fonte = (_FONTE / "gameinput.c").read_text(encoding="utf-8")
    for nome in ("HRESULT WINAPI GameInputCreate(", "HRESULT WINAPI GameInputInitialize("):
        corpo = fonte.split(nome, 1)[1].split("\n}\n", 1)[0]
        assert "if (sem_dualsense()) return E_NOTIMPL;" in corpo, nome
    regua = _regua()
    julgar = regua.julgar_sem_aparelho  # type: ignore[attr-defined]
    carregada = '{"prova": "preload", "ok": true}'
    recusou = '{"prova": "qi_v2", "ok": false, "hr": "80004001"}'
    assert julgar([carregada, recusou])
    assert not julgar([carregada, '{"prova": "qi_v2", "ok": true, "hr": "00000000"}'])
    assert not julgar(['{"prova": "preload", "ok": false}', recusou]), "o stub do Proton passou"
    mordidas = regua.MORDIDAS  # type: ignore[attr-defined]
    assert {"sem-aparelho", "reenvio", "crc", "ordem"} <= set(mordidas)
    for arquivo, cura, _quebrado, _alvo in mordidas.values():
        assert (_FONTE / arquivo).read_text(encoding="utf-8").count(cura) == 1, cura
