#!/usr/bin/env python3
"""O-VITA3K-RECEBE-O-DUALSENSE-INTEIRO-01 — o perfil do Vita3K entra pela janela dele.

O cartão que o produto acha pelo `.desktop` só sabe o nome do arquivo. Sem a classe de janela
na linha «todos os jogos», o perfil criado pela aba nunca casa o Vita3K aberto.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import struct
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a07_lancadores`, que carrega o GTK")

from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07


@pytest.fixture
def lar(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar de mentira: nada do `~/.config` dela é lido."""
    for nome, sub in (("HOME", ""), ("XDG_DATA_HOME", "share"), ("XDG_CONFIG_HOME", "cfg"),
                      ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "st"),
                      ("XDG_DATA_DIRS", "vazio")):
        monkeypatch.setenv(nome, str(tmp_path / sub) if sub else str(tmp_path))
    a07._ESCOLHA.limpar()
    a07._ESCOLHA.modo = desenho.CRIAR_PERFIL
    return tmp_path


def _achados(monkeypatch: pytest.MonkeyPatch,
             achados: dict[str, str]) -> tuple[desenho.SemCenso, ...]:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.jogos_locais.lancadores_por_conteudo",
        lambda *a, **k: achados)
    return a07._achados_por_conteudo()


def test_lancador_desconhecido_nao_ganha_janela_inventada(
        lar: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem medida não há classe: o Bottles segue só com o nome do arquivo."""
    (cartao,) = _achados(monkeypatch, {"com.usebottles.bottles": "Bottles"})
    assert cartao.janelas == ()
    assert cartao.atalhos == ("com.usebottles.bottles",)


# ---------------------------------------------------------------------------
# Degraus 1 e 2: a sonda do jogador (`o_jogo_para_de_ver_o_giro.py --jogador`)
# ---------------------------------------------------------------------------

_ENSAIO = RAIZ / "scripts" / "ensaios" / "o_jogo_para_de_ver_o_giro.py"
_SERIAIS = {1: "02:fe:00:00:00:01", 2: "02:fe:00:00:00:02",
            3: "02:fe:00:00:00:03", 4: "02:fe:00:00:00:04"}
_GUID = "030000004c050000f20d000000000000"
_NOME = "DualSense Edge Wireless Controller"


def _ensaio() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ensaio_do_giro_vita3k", _ENSAIO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    try:
        spec.loader.exec_module(modulo)
    finally:
        sys.modules.pop(spec.name, None)
    return modulo


def _estado(tmp_path: pathlib.Path) -> dict[str, Any]:
    """O `state_full` de quatro vpads, com os nós de mentira em `tmp_path`."""
    lista = []
    for n, uniq in _SERIAIS.items():
        no = tmp_path / f"hidraw{n}"
        no.write_text("")
        lista.append({"player": n, "uniq": f"aa:bb:cc:00:00:0{n}", "vpad_uniq": uniq,
                      "hidraw": str(no), "hidraw_ino": no.stat().st_ino, "evdev": None,
                      "output_count": 0, "lightbar_replicas": 0, "player_led_replicas": 0,
                      "visto_ha_s": 0.1, "game_open": False})
    return {"rumble_ff": {"per_vpad": lista}}


class _Relogio:
    def __init__(self) -> None:
        self.t = 0.0

    def agora(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.t += s


class _JogoDeMentira:
    """O SDL3 de mentira: quatro gamepads com o MESMO nome e GUID, e serial distinto."""

    def __init__(self, estado: dict[str, Any], relogio: _Relogio, fase: float,
                 *, hidapi: bool = True, salto_ns: int = 0, accel: float = 9.8) -> None:
        self.accel = accel
        self.estado, self.relogio, self.fase = estado, relogio, fase
        self.hidapi, self.salto_ns = hidapi, salto_ns
        self.abertos: list[int] = []
        self._ns = 0
        self._saltou = False

    def enumerar(self) -> list[dict[str, Any]]:
        lista = self.estado["rumble_ff"]["per_vpad"]
        return [{"id": 100 + v["player"], "nome": _NOME, "guid": _GUID,
                 "caminho": v["hidraw"] if self.hidapi else f"/dev/input/event{v['player']}"}
                for v in lista]

    def abrir(self, identidade: int) -> int:
        self.abertos.append(identidade)
        return identidade

    def descrever(self, h: int) -> dict[str, Any]:
        v = self.estado["rumble_ff"]["per_vpad"][h - 101]
        # Como o driver PS5 do SDL3 o devolve: o feature 0x09 reescrito com hífen.
        serial = v["vpad_uniq"].replace(":", "-") if self.hidapi else v["vpad_uniq"]
        return {"nome": _NOME, "serial": serial, "caminho": v["hidraw"],
                "touchpads": 1 if self.hidapi else 0, "dedos": 2 if self.hidapi else 0,
                "tem_giro": True, "tem_accel": True}

    def ligar_sensores(self, h: int) -> None:
        pass

    def eventos(self) -> list[dict[str, Any]]:
        quem = self.abertos[-1]
        self._ns += 4_000_000
        if self.salto_ns and not self._saltou and self.relogio.t > 0.5:
            self._ns += self.salto_ns
            self._saltou = True
        saida = [{"tipo": 0x659, "which": quem, "sensor": s, "dados": d, "carimbo_ns": self._ns}
                 for s, d in ((2, (0.0, 0.0, 0.0)), (1, (0.0, self.accel, 0.0)))]
        if self.hidapi and self.relogio.t >= self.fase:
            saida += [{"tipo": 0x656, "which": quem, "touchpad": 0, "dedo": 0,
                       "x": 0.5, "y": 0.5, "pressao": 1.0},
                      {"tipo": 0x651, "which": quem, "botao": 20, "baixo": True}]
        return saida

    def fechar(self, h: int) -> None:
        pass


def _roda(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, *, jogador: int = 3,
          hidapi: bool = True, salto_ns: int = 0, escrita_em: int | None = None,
          escolha: Any = None, avisos: list[str] | None = None,
          accel: float = 9.8) -> tuple[dict[str, Any], _JogoDeMentira, ModuleType]:
    ensaio = _ensaio()
    estado = _estado(tmp_path)
    por_caminho = {v["hidraw"]: v["vpad_uniq"] for v in estado["rumble_ff"]["per_vpad"]}
    monkeypatch.setattr(ensaio, "uniq_do_no_aberto", lambda c, *a, **k: por_caminho.get(c))
    if escolha is not None:
        monkeypatch.setattr(ensaio, "escolher_o_id", escolha)
    pasta_fd = tmp_path / "fd"
    pasta_fd.mkdir()
    if hidapi:
        for n, v in enumerate(estado["rumble_ff"]["per_vpad"]):
            (pasta_fd / str(n + 3)).symlink_to(v["hidraw"])
    relogio = _Relogio()
    jogo = _JogoDeMentira(estado, relogio, 1.0, hidapi=hidapi, salto_ns=salto_ns,
                          accel=accel)
    vpad = ensaio.vpad_do_jogador(estado, f"P{jogador}")
    todos = {v["player"]: v for v in estado["rumble_ff"]["per_vpad"]}
    chamadas = {"n": 0}

    def fotografar() -> dict[int, dict[str, Any]]:
        chamadas["n"] += 1
        quadro: dict[int, dict[str, Any]] = ensaio.contadores_dos_vpads(estado)
        if escrita_em is not None and chamadas["n"] >= 3:
            quadro[escrita_em]["output_count"] = 7
        if chamadas["n"] >= 3:
            quadro[jogador]["output_count"] = 12
        return quadro

    medida = ensaio.sondar_o_jogador(
        jogo, vpad, todos, fotografar=fotografar, fase_segundos=1.0,
        dormir=relogio.dormir, agora=relogio.agora, pasta_fd=pasta_fd,
        avisar=lambda fase: (avisos if avisos is not None else []).append(
            f"{fase}@{relogio.t:.3f}"))
    return medida, jogo, ensaio


def _reprovados(ensaio: ModuleType, medida: dict[str, Any]) -> set[str]:
    return {i["item"] for i in ensaio.laudo(medida) if not i["ok"]}


def test_os_layouts_do_evento_do_sdl3_sao_os_medidos_no_joystick_virtual() -> None:
    """Toque, sensor (com o carimbo em ns no deslocamento 40) e botão, como o SDL3 3.4.x os põe."""
    ensaio = _ensaio()
    toque = struct.pack("<IIQIiifff", 0x656, 0, 1, 7, 0, 1, 0.25, 0.75, 1.0).ljust(128, b"\0")
    assert ensaio.ler_evento(toque) == {
        "tipo": 0x656, "which": 7, "touchpad": 0, "dedo": 1, "x": 0.25, "y": 0.75, "pressao": 1.0}
    sensor = bytearray(struct.pack("<IIQIi3f", 0x659, 0, 1, 7, 1, 0.0, 9.8, 0.0).ljust(128, b"\0"))
    struct.pack_into("<Q", sensor, 40, 123456789)
    lido = ensaio.ler_evento(bytes(sensor))
    assert lido is not None and lido["carimbo_ns"] == 123456789 and lido["sensor"] == 1
    botao = struct.pack("<IIQIBB", 0x651, 0, 1, 7, 20, 1).ljust(128, b"\0")
    assert ensaio.ler_evento(botao) == {"tipo": 0x651, "which": 7, "botao": 20, "baixo": True}
    assert ensaio.ler_evento(struct.pack("<I", 0x653).ljust(128, b"\0")) is None


def test_o_jogador_vira_o_vpad_pelo_numero_do_state_full(tmp_path: pathlib.Path) -> None:
    ensaio = _ensaio()
    estado = _estado(tmp_path)
    assert ensaio.vpad_do_jogador(estado, "P2")["vpad_uniq"] == _SERIAIS[2]
    assert ensaio.vpad_do_jogador({"rumble_ff": {"per_vpad": []}}, "P1") is None
    assert set(ensaio.contadores_dos_vpads(estado)) == {1, 2, 3, 4}


def test_o_serial_vem_do_hid_uniq_do_hidraw_e_do_uniq_do_evdev(tmp_path: pathlib.Path) -> None:
    ensaio = _ensaio()
    (tmp_path / "hidraw" / "hidraw5" / "device").mkdir(parents=True)
    (tmp_path / "hidraw" / "hidraw5" / "device" / "uevent").write_text(
        "HID_ID=0003:0000054C:00000DF2\nHID_UNIQ=02:fe:00:00:00:05\n")
    (tmp_path / "input" / "event9" / "device").mkdir(parents=True)
    (tmp_path / "input" / "event9" / "device" / "uniq").write_text("02:fe:00:00:00:09\n")
    f = ensaio.uniq_do_no_aberto
    assert f("/dev/hidraw5", tmp_path / "hidraw", tmp_path / "input") == "02:fe:00:00:00:05"
    assert f("/dev/input/event9", tmp_path / "hidraw", tmp_path / "input") == "02:fe:00:00:00:09"
    assert f("/dev/hidraw6", tmp_path / "hidraw", tmp_path / "input") is None
    assert f(None) is None


def test_a_sonda_abre_so_o_vpad_pedido_pelo_serial_e_mede_o_aceite(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # D-1610-A-SONDA-DO-JOGADOR-ESCOLHE-O-VPAD-PELO-SERIAL
    """Quatro gamepads de mesmo nome e GUID: abre o P3 pelo serial, e o laudo fecha verde."""
    medida, jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=3)
    assert jogo.abertos == [103]
    assert medida["escolhido"]["jogador"] == 3
    assert medida["escolhido"]["serial_confere"] and medida["escolhido"]["no_confere"]
    assert len(medida["vpads"]) == 4
    assert {i["item"]: i["ok"] for i in ensaio.laudo(medida)} == {
        "driver_ps5_no_vpad_escolhido": True, "guids_iguais_e_seriais_distintos": True,
        "hidraw_de_todo_vpad_aberto": True, "escrita_so_no_escolhido": True,
        "serial_e_no_conferem": True, "um_touchpad_de_dois_dedos": True,
        "giro_e_acelerometro": True, "gravidade_parado": True, "carimbo_sem_salto": True,
        "toque_e_clique_chegam": True}


def test_mordida_escolher_pelo_nome_abre_sempre_o_primeiro(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: a escolha por nome ou GUID cai no P1; a sonda tem de reprovar a identidade."""
    primeiro = lambda candidatos, _uniq: int(candidatos[0]["id"])  # noqa: E731
    medida, jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=3, escolha=primeiro)
    assert jogo.abertos == [101]
    assert "serial_e_no_conferem" in _reprovados(ensaio, medida)


def test_mordida_o_hidapi_desligado_reprova_toque_e_hidraw(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: com `SDL_JOYSTICK_HIDAPI=0` não há touchpad nem hidraw aberto: mede o evdev."""
    medida, _jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=3, hidapi=False)
    reprovados = _reprovados(ensaio, medida) if "erro" not in medida else {"erro"}
    assert reprovados & {"erro", "hidraw_de_todo_vpad_aberto", "um_touchpad_de_dois_dedos"}


def test_mordida_o_carimbo_que_salta_reprova(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: um salto de 1431 s entre dois `sensor_timestamp` passa do teto de 0,1 s."""
    medida, _jogo, ensaio = _roda(tmp_path, monkeypatch, salto_ns=1_431_000_000_000)
    assert _reprovados(ensaio, medida) == {"carimbo_sem_salto"}


def test_a_calibracao_errada_do_acelerometro_reprova_a_gravidade(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Aceleração em g (0,98) em vez de m/s² (9,8) é calibração que não escala: reprova."""
    medida, _jogo, ensaio = _roda(tmp_path, monkeypatch, accel=0.98)
    assert _reprovados(ensaio, medida) == {"gravidade_parado"}


def test_mordida_abrir_todos_escreve_nos_outros(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: contador de saída subindo em outro vpad reprova a escrita só no escolhido."""
    medida, _jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=3, escrita_em=1)
    assert _reprovados(ensaio, medida) == {"escrita_so_no_escolhido"}


def test_o_degrau_2_traz_os_contadores_antes_durante_e_depois(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    medida, _jogo, _mod = _roda(tmp_path, monkeypatch, jogador=2)
    c = medida["contadores"]
    assert set(c) == {"antes", "durante", "depois"}
    assert set(c["durante"]) == {"parado", "dedo"}
    assert set(c["antes"][2]) >= {"visto_ha_s", "lightbar_replicas", "player_led_replicas"}


def test_os_hidraw_abertos_se_casam_por_inode_e_nao_por_nome(tmp_path: pathlib.Path) -> None:
    ensaio = _ensaio()
    aberto, fechado = tmp_path / "hidraw1", tmp_path / "hidraw2"
    aberto.write_text("")
    fechado.write_text("")
    pasta = tmp_path / "fd"
    pasta.mkdir()
    (pasta / "7").symlink_to(aberto)
    assert ensaio.fds_abertos_dos_vpads({1: str(aberto), 2: str(fechado)}, pasta) == {
        1: True, 2: False}


def test_o_ambiente_da_sonda_do_jogador_liga_o_hidapi_e_nasce_sem_tela(
        monkeypatch: pytest.MonkeyPatch) -> None:
    ensaio = _ensaio()
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setenv("SDL_JOYSTICK_HIDAPI", "0")
    env = ensaio._ambiente_do_vpad(hidapi="1", dica="0")
    assert env["SDL_JOYSTICK_HIDAPI"] == "1"
    assert "DISPLAY" not in env and "WAYLAND_DISPLAY" not in env
    assert env["SDL_VIDEODRIVER"] == "dummy"
    assert ensaio._ambiente_do_vpad(hidapi="0", dica="0")["SDL_JOYSTICK_HIDAPI"] == "0"


def test_a_sonda_recusa_o_que_nao_vale(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """`--so-medir` não combina com o vpad; sem SDL3 não há o que medir; bancada tomada espera."""
    ensaio = _ensaio()
    lib3 = tmp_path / "libSDL3.so.0"
    lib3.write_bytes(b"")
    base = ["--jogador", "P1"]

    def roda(*extra: str) -> int:
        monkeypatch.setattr(sys, "argv", ["x", *base, *extra])
        return int(ensaio.main())

    assert roda("--so-medir", "--lib", str(lib3)) == 2
    assert roda() == 2
    lib2 = tmp_path / "libSDL2-2.0.so.0"
    lib2.write_bytes(b"")
    assert roda("--lib", str(lib2)) == 2
    lancados: list[list[str]] = []

    def run(comando: list[str], **_k: Any) -> SimpleNamespace:
        lancados.append(comando)
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(ensaio.subprocess, "run", run)
    assert roda("--lib", str(lib3)) == 2
    assert len(lancados) == 1 and lancados[0][-1] == "exigir"
    assert "bancada" in capsys.readouterr().out


def test_a_saida_leva_o_serial_mascarado_e_sem_chaves_de_juncao(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    medida, _jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=1)
    fora = json.dumps(ensaio._para_a_saida(medida))
    assert "_uniq_inteiro" not in fora and "_serial_inteiro" not in fora


def test_o_serial_do_sdl3_com_hifen_e_o_mesmo_do_uniq_com_dois_pontos() -> None:
    """O driver PS5 do SDL3 devolve o serial `02-fe-…`; o `vpad_uniq` do daemon é `02:fe:…`."""
    ensaio = _ensaio()
    assert ensaio.mesmo_serial("02-fe-00-00-00-03", "02:FE:00:00:00:03")
    assert not ensaio.mesmo_serial("02-fe-00-00-00-03", "02:fe:00:00:00:01")
    assert not ensaio.mesmo_serial("", "")
    assert not ensaio.mesmo_serial(None, "02:fe:00:00:00:01")


def test_mordida_o_serial_comparado_como_texto_reprova_o_vpad_certo(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: comparar o texto cru dá «não confere» no vpad certo, porque o SDL3 usa hífen."""
    ensaio_cru = _ensaio()
    monkeypatch.setattr(ensaio_cru, "mesmo_serial",
                        lambda a, b: (a or "").casefold() == (b or "").casefold())
    monkeypatch.setattr(sys.modules[__name__], "_ensaio", lambda: ensaio_cru)
    medida, jogo, ensaio = _roda(tmp_path, monkeypatch, jogador=3)
    assert jogo.abertos == [103]
    assert "serial_e_no_conferem" in _reprovados(ensaio, medida)


def test_quem_esta_na_bancada_e_avisado_no_comeco_de_cada_fase(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o aviso, ninguém sabe quando soltar o controle e quando pôr o dedo."""
    avisos: list[str] = []
    _roda(tmp_path, monkeypatch, jogador=2, avisos=avisos)
    assert [a.split("@")[0] for a in avisos] == ["parado", "dedo"]
    assert float(avisos[1].split("@")[1]) >= 1.0


def test_a_sonda_que_passa_do_prazo_reprova_e_leva_a_pilha(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    """Sonda que trava junto com o alvo nunca reprova: o prazo vence, e a pilha vai no laudo."""
    ensaio = _ensaio()
    lib3 = tmp_path / "libSDL3.so.0"
    lib3.write_bytes(b"")
    monkeypatch.setattr(ensaio.subprocess, "run",
                        lambda *_a, **_k: SimpleNamespace(returncode=0, stdout="", stderr=""))
    mortos: list[str] = []

    class _Travado:
        pid = 4242
        returncode = None

        def __init__(self, *_a: Any, **_k: Any) -> None:
            self.vezes = 0

        def communicate(self, timeout: float | None = None) -> tuple[str, None]:
            self.vezes += 1
            if self.vezes == 1:
                raise ensaio.subprocess.TimeoutExpired("sonda", timeout or 0)
            return "", None

        def kill(self) -> None:
            mortos.append("kill")

    monkeypatch.setattr(ensaio.subprocess, "Popen", _Travado)
    monkeypatch.setattr(ensaio, "_pilha_do_processo", lambda pid: [f"#0 travado em {pid}"])
    monkeypatch.setattr(sys, "argv", ["x", "--jogador", "P1", "--lib", str(lib3)])
    assert ensaio.main() == 3
    saida = capsys.readouterr().out
    assert "prazo" in saida and "travado em 4242" in saida
    assert mortos == ["kill"]
