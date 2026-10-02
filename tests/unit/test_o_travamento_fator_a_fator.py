"""As réguas do I-1 da O-TRAVAMENTO-SE-SEPARA-UM-FATOR-POR-VEZ-01.

`scripts/ensaios/o_travamento_fator_a_fator.py` mede uma janela por vez com
todos os fatores do travamento na mesma linha. Cada régua abaixo cobra uma das
oito da sprint, sem aparelho, sem daemon e sem ``/proc`` de verdade: as portas
do instrumento (o ``state_full``, o medidor de ar, a varredura, a raiz do
``/proc`` e os diários) são dublês, e o ``/proc`` de mentira é uma pasta.

A nona régua é a do achado de 02/10: com o laço do serviço parado o soquete
aceita e não responde, e o instrumento não pode parar junto. A janela em que o
daemon não respondeu sai «-», fora do veredito, com o motivo.

AS MORDIDAS (feitas em 02/10/2026, uma por vez, com o md5 conferido na volta):

1. ``_numero`` lendo ``None`` como 0,0: o azul de leitor perdido vira colapso.
2. ``resumir`` chaveando pelo ``passo``: a janela «base» com a Steam dela cai
   no grupo da base.
3. a Steam sem olhar o ``HOME``: duas dela; sem a lista ``excluir``: três.
4. o controle chaveado pela posição: os números trocam de controle; pelo
   modelo: os dois «White» viram um.
5. o adaptador escrito pelo endereço, e a interface do Wi-Fi pelo nome: as
   formas do endereço aparecem na linha.
6. o diário contado sem a hora da linha: as três linhas em toda janela.
7. sem a marca, a janela discordante conta o colapso; comparando com a entrada
   do daemon, nada se marca; sem o piso de 50/s, o 02:37 sai do veredito.
8. sem a condição, o colapso da janela que varria conta; o «não sei» do
   ``Discovering`` lido como zero põe a janela no veredito.
9. sem prazo nenhum, a pergunta ao soquete mudo fica presa e a régua reprova
   em 2 s (sem pendurar a suíte); o daemon mudo no veredito reprova; e o
   ``state_full`` pedido por outro nome devolve sempre «não respondeu», o que
   a 9b reprova.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco
from hefesto_dualsense4unix.integrations.varredura_do_radio import MESA_TODA_MUDA, Varredura

_RAIZ = Path(__file__).resolve().parents[2]
_INSTRUMENTO = _RAIZ / "scripts" / "ensaios" / "o_travamento_fator_a_fator.py"
_CHECAGEM = _RAIZ / "scripts" / "check_endereco_de_radio.py"


def _carregar(caminho: Path, nome: str) -> Any:
    """Carrega um script pelo caminho — ``scripts/`` não é pacote."""
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def inst() -> Any:
    return _carregar(_INSTRUMENTO, "_regua_o_travamento_fator_a_fator")


VERMELHO = "aabbccd4e7a1"
AZUL = "aabbccd4e7a3"
BRANCO = "aabbccd4e7a2"
WHITE_A = "aabbccd4e7b1"
WHITE_B = "aabbccd4e7b2"
ADAPTADOR_1 = "aa:bb:cc:e3:f2:01"
ADAPTADOR_2 = "aa:bb:cc:e3:f2:02"
T0 = 1_790_000_000.0


def _controle(uniq: str, mov: float | None, *, voz: float | None = 0.0,
              adaptador: str | None = ADAPTADOR_1, modelo: str = "Cosmic Red",
              connected: bool = True, transporte: str = "bt", jogador: int = 1,
              extra: dict[str, Any] | None = None) -> dict[str, Any]:
    entrada = {
        "uniq": uniq, "connected": connected, "transport": transporte,
        "adaptador": adaptador, "hz_movimento": mov, "hz_voz": voz,
        "modelo": modelo, "player": jogador, "battery_pct": 80,
        "audio": {"mic_mudo": False, "mic_mudo_desejado": False},
    }
    entrada.update(extra or {})
    return entrada


def _estado(*controles: dict[str, Any], radio_ar: dict[str, Any] | None = None,
            appid: int | None = None, tique: int = 0) -> dict[str, Any]:
    return {
        "controllers": list(controles),
        "radio_ar": radio_ar or {},
        "jogo_steam": {"lido": True, "appid": appid},
        "counters": {"poll.tick": tique},
    }


def _amostra(inst: Any, estado: dict[str, Any] | None, n: int, *,
             ar: dict[str, dict[str, float | None]] | None = None, varrendo: int | None = 0,
             processos: dict[str, int] | None = None) -> Any:
    return inst.Amostra(instante=T0 + n, estado=estado, ar=ar or {}, varrendo=varrendo,
                        processos=processos or {}, memoria=None)


def _janela(inst: Any, amostras: list[Any], rotulos: Any = None, contexto: Any = None,
            inicio: float = T0, fim: float = T0 + 10) -> dict[str, Any]:
    linha: dict[str, Any] = inst.linha_da_janela(
        amostras, inicio, fim, rotulos or inst.Rotulos(), contexto or inst.ContextoDaJanela())
    return linha


def _dez(inst: Any, estado: dict[str, Any] | None, **kw: Any) -> list[Any]:
    return [_amostra(inst, estado, n, **kw) for n in range(10)]


def test_1_nao_sei_nao_e_colapso(inst: Any) -> None:
    rotulos = inst.Rotulos()
    antes = _estado(_controle(VERMELHO, 198), _controle(AZUL, 34, modelo="Starlight Blue"),
                    _controle(BRANCO, 600, modelo="White", adaptador=ADAPTADOR_2))
    _janela(inst, _dez(inst, antes), rotulos)
    # 02:18: o branco desligado (some do state_full), o azul de leitor perdido
    depois = _estado(_controle(VERMELHO, 550),
                     _controle(AZUL, None, modelo="Starlight Blue"))
    linha = _janela(inst, _dez(inst, depois), rotulos)
    assert linha["controles"]["White 1"]["movimento"] is None
    assert linha["controles"]["White 1"]["conectado"] is False
    assert linha["controles"]["Starlight Blue 1"]["movimento"] is None
    assert linha["colapso"] == []

    meio = [_amostra(inst, None, n) for n in range(4)]
    meio += [_amostra(inst, _estado(_controle(VERMELHO, 500)), n) for n in range(4, 10)]
    linha = _janela(inst, meio, rotulos)
    assert linha["controles"]["Cosmic Red 1"]["segundos"] == 6
    assert linha["controles"]["Cosmic Red 1"]["movimento"]["mediana"] == 500.0
    assert linha["daemon"] == {"respostas": 6, "sem_resposta": 4, "tiques": 0.0}
    assert linha["colapso"] == []

    zero = _janela(inst, _dez(inst, _estado(_controle(VERMELHO, 0.0))), rotulos)
    assert zero["colapso"] == ["Cosmic Red 1"]


def test_2_o_fator_sai_do_que_a_janela_mediu(inst: Any) -> None:
    rotulos = inst.Rotulos()
    estado = _estado(_controle(VERMELHO, 300))
    sem = _janela(inst, _dez(inst, estado), rotulos,
                  inst.ContextoDaJanela(passo="base"))
    com = _janela(inst, _dez(inst, estado, processos={"steam_dela": 1}), rotulos,
                  inst.ContextoDaJanela(passo="base"))
    assert com["fatores"]["steam_dela"] == 1
    grupos = inst.resumir([sem, com])
    assert len(grupos) == 2, "a janela «base» com a Steam dela caiu no grupo da base"
    da_steam = [g for g in grupos if g["fatores"]["steam_dela"] == 1]
    assert len(da_steam) == 1 and da_steam[0]["janelas"] == 1
    assert da_steam[0]["passos"] == ["base"]
    # DualSense (``uhid``) são dois grupos, pelo pad que o estado disse.
    xbox = _janela(inst, _dez(inst, _estado(_controle(VERMELHO, 300,
                                                       extra={"vpad_backend": "uinput"}))),
                   rotulos, inst.ContextoDaJanela(passo="base"))
    sony = _janela(inst, _dez(inst, _estado(_controle(VERMELHO, 300,
                                                       extra={"vpad_backend": "uhid"}))),
                   rotulos, inst.ContextoDaJanela(passo="base"))
    pelos_pads = {tuple(g["fatores"]["pads"]): g["janelas"] for g in inst.resumir([xbox, sony])}
    assert pelos_pads == {("uinput",): 1, ("uhid",): 1}, pelos_pads


def _processo(raiz: Path, pid: int, argv: list[str], home: str) -> None:
    pasta = raiz / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (pasta / "environ").write_bytes(f"PATH=/usr/bin\0HOME={home}\0".encode())


def test_3_a_steam_do_teste_pelo_home(inst: Any, tmp_path: Path) -> None:
    raiz = tmp_path / "proc"
    dela = "/home/ela"
    _processo(raiz, 100, ["/home/ela/.local/share/Steam/ubuntu12_32/steam", "-srt-logger-opened"],
              dela)
    _processo(raiz, 200, ["/tmp/pytest-of-ela/pytest-3/lar0/Steam/ubuntu12_32/steam"],
              "/tmp/pytest-of-ela/pytest-3/lar0")
    _processo(raiz, 300, ["python3", "o_travamento_fator_a_fator.py", "janela", "--passo",
                          "steam"], dela)
    _processo(raiz, 299, ["bash", "-c", "python3 o_travamento_fator_a_fator.py janela"], dela)
    _processo(raiz, 400, ["C:\\windows\\system32\\winedevice.exe"], dela)
    _processo(raiz, 500, ["python", "-m", "pytest", "tests/unit"], dela)
    contagem = inst.processos_da_mesa(str(raiz), dela, {300, 299})
    assert contagem["steam_dela"] == 1
    assert contagem["steam_de_teste"] == 1
    assert contagem["steam_outra"] == 0
    assert contagem["winedevice"] == 1
    assert contagem["pytest"] == 1


def test_4_o_controle_pela_posse(inst: Any) -> None:
    rotulos = inst.Rotulos()
    a = _controle(WHITE_A, 500, modelo="White")
    b = _controle(WHITE_B, 300, modelo="White", adaptador=ADAPTADOR_2, jogador=2)
    uma = _janela(inst, _dez(inst, _estado(a, b)), rotulos)
    outra = _janela(inst, _dez(inst, _estado(b, a)), rotulos)
    assert sorted(uma["controles"]) == ["White 1", "White 2"]
    for linha in (uma, outra):
        assert linha["controles"]["White 1"]["movimento"]["mediana"] == 500.0
        assert linha["controles"]["White 2"]["movimento"]["mediana"] == 300.0
        assert linha["controles"]["White 2"]["adaptador"] == 2


def test_5_nenhum_endereco_na_saida(inst: Any, tmp_path: Path) -> None:
    checagem = _carregar(_CHECAGEM, "_regua_check_endereco_de_radio")
    uniq = "aabbccd4e7f9"
    adaptador = "aa:bb:cc:e3:f2:c1"
    interface = "wlxaabbcc4c5d6e"
    serial = "AABBCCF5E6D8"
    no_de_som = "hefesto_mic_d4e7f9"
    proc = tmp_path / "proc"
    (proc / "net").mkdir(parents=True)
    linha_dev = f"{interface}: 1000 10 0 0 0 0 0 0 2000 20 0 0 0 0 0 0\n"
    (proc / "net" / "dev").write_text("Inter-| Receive\n face |bytes\n" + linha_dev)
    antes = inst.bytes_do_wifi(str(proc))
    (proc / "net" / "dev").write_text(
        "Inter-| Receive\n face |bytes\n"
        f"{interface}: 6000 10 0 0 0 0 0 0 9000 20 0 0 0 0 0 0\n")
    contexto = inst.ContextoDaJanela(
        passo="base", wifi_antes=antes, wifi_depois=inst.bytes_do_wifi(str(proc)),
        bandas={interface: "5"})
    estado = _estado(
        _controle(uniq, 300, voz=100, adaptador=adaptador,
                  extra={"serial": serial, "canal_fonte": no_de_som,
                         "audio": {"mic_mudo": False, "canal_fonte": no_de_som}}),
        radio_ar={adaptador: {"entrada_por_s": 400, "canais_evitados": [1, 2, 3]}})
    amostras = _dez(inst, estado, ar={adaptador: {"entrada": 400.0, "saida": 0.0}})
    linha = _janela(inst, amostras, contexto=contexto)

    def sem_endereco(saida: str, onde: str) -> None:
        baixa = saida.lower()
        for endereco in (uniq, adaptador, interface[3:]):
            vazou = {f for f in formas_do_endereco(endereco) if f.lower() in baixa}
            assert not vazou, f"a forma {sorted(vazou)} do endereço saiu {onde}"
        assert serial.lower() not in baixa
        assert no_de_som.lower() not in baixa
        assert interface.lower() not in baixa
        assert not checagem.acusa_serial(saida)

    sem_endereco(json.dumps(linha, ensure_ascii=False), "na linha")
    grupos = inst.resumir([linha])
    sem_endereco(inst.resumo_em_texto(grupos), "no resumo")
    sem_endereco(json.dumps(grupos, ensure_ascii=False), "no resumo em JSON")
    assert linha["fatores"]["wifi"] == {"wifi 1": {"banda": "5", "bytes_por_s": 1200.0}}
    assert list(linha["adaptadores"]) == ["1"]


def _linha_do_diario(epoch: float, texto: str) -> str:
    hora = datetime.fromtimestamp(epoch).astimezone().isoformat(timespec="microseconds")
    return f"{hora} MesaDeMentira {texto}"


def test_6_a_linha_do_diario_entra_na_janela_dela(inst: Any) -> None:
    t = T0 + 100
    kernel = "\n".join([
        _linha_do_diario(t - 3600, "kernel: hid_playstation: boot"),
        _linha_do_diario(t, "kernel: NVRM: nvAssertOkFailedNoLog: NV_ERR_NO_MEMORY"),
        _linha_do_diario(t + 15, "kernel: playstation 0005:054C:0CE6.0001: "
                                 "DualSense input CRC's check failed"),
    ])
    sistema = _linha_do_diario(t + 25, "systemd[1]: Starting hefesto-bt-health-watchdog.service"
                                        " - Hefesto — watchdog...")
    estado = _estado(_controle(VERMELHO, 300))
    contas = []
    for inicio in (t - 2, t + 8, t + 18):
        contexto = inst.ContextoDaJanela(kernel=kernel, sistema=sistema)
        linha = _janela(inst, _dez(inst, estado), contexto=contexto, inicio=inicio,
                        fim=inicio + 10)
        contas.append((linha["kernel"]["nvrm"], linha["kernel"]["crc"],
                       linha["fatores"]["vigia_do_radio"]))
    assert contas == [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    sem_diario = _janela(inst, _dez(inst, estado), contexto=inst.ContextoDaJanela())
    assert sem_diario["kernel"] is None
    assert sem_diario["fatores"]["vigia_do_radio"] is None


def test_7_as_reguas_que_discordam_aparecem_e_so_elas(inst: Any) -> None:
    rotulos = inst.Rotulos()
    par = _estado(_controle(VERMELHO, 200, voz=70),
                  _controle(AZUL, 30, voz=0, modelo="Starlight Blue", jogador=3),
                  radio_ar={ADAPTADOR_1: {"entrada_por_s": 300, "canais_evitados": []}})
    discorda = _janela(inst, _dez(inst, par, ar={ADAPTADOR_1: {"entrada": 500.0}}), rotulos)
    assert discorda["adaptadores"]["1"]["discordam"] is True
    assert discorda["veredito"] is False
    assert discorda["fora_do_veredito"] == ["as réguas discordam no adaptador 1"]
    sozinho = _estado(_controle(VERMELHO, 13.5, voz=22.4),
                      radio_ar={ADAPTADOR_1: {"entrada_por_s": 20,
                                              "canais_evitados": list(range(54))}})
    colapso = _janela(inst, _dez(inst, sozinho, ar={ADAPTADOR_1: {"entrada": 20.0}}), rotulos)
    assert colapso["adaptadores"]["1"]["discordam"] is False
    assert colapso["veredito"] is True
    assert colapso["colapso"] == ["Cosmic Red 1"]
    assert colapso["adaptadores"]["1"]["afh"] == 54.0
    grupos = {len(g["fatores"]["arranjo"][0][1]): g for g in inst.resumir([discorda, colapso])}
    assert grupos[2]["com_colapso"] == 0 and grupos[2]["no_veredito"] == 0
    assert grupos[2]["fora_do_veredito"] == {"as réguas discordam no adaptador 1": 1}
    assert grupos[1]["com_colapso"] == 1


def test_8_as_condicoes_tiram_a_janela_com_o_motivo(inst: Any) -> None:
    rotulos = inst.Rotulos()
    caido = _estado(_controle(VERMELHO, 13.5))
    casos: dict[str, dict[str, Any]] = {
        "um adaptador varria": {"varrendo": 1},
        "um pytest vivo": {"processos": {"pytest": 1}},
        "a Steam de teste viva": {"processos": {"steam_de_teste": 1}},
        "não sei se algum adaptador varria": {
            "varrendo": inst.varrendo_de(Varredura(motivo=MESA_TODA_MUDA))},
    }
    linhas = []
    for motivo, kw in casos.items():
        linha = _janela(inst, _dez(inst, caido, **kw), rotulos)
        assert linha["veredito"] is False, motivo
        assert motivo in linha["fora_do_veredito"]
        linhas.append(linha)
    assert inst.varrendo_de(Varredura(mudos=frozenset({ADAPTADOR_2}))) is None
    assert inst.varrendo_de(Varredura()) == 0
    (grupo,) = inst.resumir(linhas)
    assert grupo["no_veredito"] == 0 and grupo["com_colapso"] == 0
    assert grupo["controles"] == {}
    assert sum(grupo["fora_do_veredito"].values()) == 4


def test_9_o_daemon_mudo_sai_da_janela_e_nao_para_o_instrumento(inst: Any) -> None:
    rotulos = inst.Rotulos()
    _janela(inst, _dez(inst, _estado(_controle(VERMELHO, 300), tique=100)), rotulos)
    mudo = _janela(inst, _dez(inst, None), rotulos)
    assert mudo["daemon"] == {"respostas": 0, "sem_resposta": 10, "tiques": None}
    assert mudo["controles"]["Cosmic Red 1"]["movimento"] is None
    assert mudo["colapso"] == []
    assert mudo["fora_do_veredito"] == ["o daemon não respondeu na janela"]

    # O soquete que aceita e não responde (o laço parado): o state_full volta
    pasta = Path(tempfile.mkdtemp(prefix="tff-"))
    caminho = pasta / "s.sock"
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(caminho))
    servidor.listen(8)
    presos: list[socket.socket] = []

    def aceitar() -> None:
        with servidor:
            servidor.settimeout(5.0)
            try:
                conexao, _ = servidor.accept()
                presos.append(conexao)
            except OSError:
                return

    fio = threading.Thread(target=aceitar, daemon=True)
    fio.start()
    lido: list[Any] = []
    pergunta = threading.Thread(
        target=lambda: lido.append(inst.estado_pelo_ipc(0.3, caminho)), daemon=True)
    comeco = time.monotonic()
    pergunta.start()
    pergunta.join(2.0)
    passou = time.monotonic() - comeco
    preso = pergunta.is_alive()
    for conexao in presos:
        conexao.close()
    pergunta.join(2.0)
    caminho.unlink(missing_ok=True)
    pasta.rmdir()
    assert not preso, f"o state_full de um daemon parado prendeu o instrumento {passou:.1f} s"
    assert lido == [None]


def test_9b_o_daemon_que_responde_chega_inteiro(inst: Any) -> None:
    """A outra metade da nona: o ``None`` tem de ser do daemon mudo, e não da porta.

    Sem esta, uma porta que sempre devolve ``None`` (o método com outro nome, o
    cliente chamado errado) passaria na nona, e na bancada TODA janela sairia
    «o daemon não respondeu» — o instrumento respondendo sobre a própria porta,
    e não sobre o daemon. O dublê fala o protocolo do soquete (uma linha de
    JSON-RPC de cada lado) e só responde ao ``daemon.state_full``.
    """
    pasta = Path(tempfile.mkdtemp(prefix="tfr-"))
    caminho = pasta / "s.sock"
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(caminho))
    servidor.listen(8)
    estado = _estado(_controle(VERMELHO, 300), tique=7)

    def responder() -> None:
        with servidor:
            servidor.settimeout(5.0)
            try:
                conexao, _ = servidor.accept()
            except OSError:
                return
            with conexao:
                pedido = json.loads(conexao.makefile("rb").readline())
                if pedido.get("method") == "daemon.state_full":
                    corpo = {"jsonrpc": "2.0", "id": pedido["id"], "result": estado}
                else:
                    corpo = {"jsonrpc": "2.0", "id": pedido["id"],
                             "error": {"code": -32601, "message": "método desconhecido"}}
                conexao.sendall(json.dumps(corpo).encode() + b"\n")

    fio = threading.Thread(target=responder, daemon=True)
    fio.start()
    resposta = inst.estado_pelo_ipc(0.8, caminho)
    fio.join(5.0)
    caminho.unlink(missing_ok=True)
    pasta.rmdir()
    assert resposta == estado, "o daemon respondeu, e o instrumento leu «não respondeu»"


def test_o_laco_da_janela_fecha_uma_linha_por_janela(inst: Any, tmp_path: Path) -> None:
    relogio = [T0]
    respostas = iter([_estado(_controle(VERMELHO, 300), tique=n) for n in range(5)] + [None] * 5)

    def dormir(s: float) -> None:
        relogio[0] += s

    portas = inst.Portas(
        estado=lambda: next(respostas),
        ar=lambda: {},
        varredura=lambda: Varredura(),
        raiz_proc=str(tmp_path),
        home_dela="/home/ela",
        excluir=frozenset(),
        banda_do_wifi=lambda _i: None,
        diario_do_kernel=lambda _a, _b: "",
        diario_do_sistema=lambda _a, _b: "",
        relogio=lambda: relogio[0],
        monotonico=lambda: relogio[0],
        dormir=dormir,
    )
    linhas: list[dict[str, Any]] = []
    feitas = inst.medir(portas, segundos=5, janelas=2, passo="base", escrever=linhas.append)
    assert feitas == 2
    assert [ln["daemon"]["respostas"] for ln in linhas] == [5, 0]
    assert linhas[0]["daemon"]["tiques"] == 4.0
    assert linhas[0]["veredito"] is True
    assert linhas[1]["fora_do_veredito"] == ["o daemon não respondeu na janela"]
    assert linhas[0]["kernel"] == {"nvrm": 0, "crc": 0, "start_frame": 0, "fila_cheia": 0}
