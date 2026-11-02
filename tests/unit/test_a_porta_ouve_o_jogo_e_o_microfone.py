"""A porta das extensões ouve o jogo e o microfone.

Sprint A-PORTA-DAS-EXTENSOES-OUVE-O-JOGO-E-O-MICROFONE-01. Três tópicos genéricos: `jogo.som` (o
estalo com o lado e a impressão de 24 bandas), `microfone.nivel` (o pico de cada controle, só com
assinante) e `jogo.identidade` (a chave, o executável e o buildid). Tudo por dublê: PCM sintético
de semente fixa, gravador de mentira, `/proc` e biblioteca da Steam numa pasta.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import math
import os
import random
import socket
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.events import TOPICOS_DE_ESTADO, EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import identidade_do_jogo as ij
from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as lm
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import nivel_do_microfone as nm
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from hefesto_dualsense4unix.mods.manifesto import TOPICOS_DE_LEITURA, permissao_valida
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta

TAXA = tj.TAXA
P1 = "aa:bb:cc:00:00:61"
P2 = "aa:bb:cc:00:00:62"


def _fundo(segundos: float, semente: int, nivel: float = 0.01) -> list[list[float]]:
    sorteio = random.Random(semente)
    quantos = int(segundos * TAXA)
    return [[sorteio.gauss(0, nivel), sorteio.gauss(0, nivel)] for _ in range(quantos)]


def _grave(
    quadros: list[list[float]], em_s: float, ganhos: tuple[float, float], fase: float
) -> None:
    inicio = int(em_s * TAXA)
    for k in range(int(0.03 * TAXA)):
        queda = math.exp(-k / (0.012 * TAXA))
        amostra = 0.8 * math.sin(2 * math.pi * 110 * k / TAXA + fase) * queda
        quadros[inicio + k][0] += amostra * ganhos[0]
        quadros[inicio + k][1] += amostra * ganhos[1]


def _agudo(
    quadros: list[list[float]], em_s: float, ganhos: tuple[float, float], semente: int
) -> None:
    sorteio = random.Random(semente)
    inicio = int(em_s * TAXA)
    anterior = 0.0
    for k in range(int(0.03 * TAXA)):
        ruido = sorteio.uniform(-1, 1)
        amostra = 0.6 * (ruido - anterior) * math.exp(-k / (0.012 * TAXA))
        anterior = ruido
        quadros[inicio + k][0] += amostra * ganhos[0]
        quadros[inicio + k][1] += amostra * ganhos[1]


def _pcm(quadros: list[list[float]]) -> bytes:
    planos = [max(-32767, min(32767, int(v * 32767))) for q in quadros for v in q]
    return struct.pack(f"<{len(planos)}h", *planos)


class _Gravador:
    def __init__(self, pcm: bytes) -> None:
        self.stdout = io.BytesIO(pcm)

    def poll(self) -> int | None:
        return None


def _ouvido(pcm: bytes, publicados: list[dict[str, Any]], assinado: bool) -> tj.OuvidoDoJogo:
    return tj.OuvidoDoJogo(
        lambda: True,
        achar_o_fluxo=lambda: tj.FluxoDoJogo(4, 504, "jogo", 200),
        montar_argv=lambda f: ["pw-record", f"--target={f.serial}"],
        abrir=lambda _argv: _Gravador(pcm),
        derrubar=lambda _proc, **_k: None,
        conferir_o_alvo=lambda _rotulo: "jogo",
        relogio=lambda: 10.0,
        publicar=publicados.append,
        assinado=lambda: assinado,
    )


def _ouvir_tudo(ouvido: tj.OuvidoDoJogo) -> None:
    ouvido.uma_volta()
    leitor = ouvido._leitor
    assert leitor is not None
    leitor.join(timeout=10.0)


def _bandas(pcm: bytes) -> list[float]:
    detector = tj.DetectorDeTransiente(imprimir=True)
    for i in range(0, len(pcm), tj.BYTES_POR_JANELA * 4):
        detector.ouvir(pcm[i:i + tj.BYTES_POR_JANELA * 4], i / (4 * TAXA))
    [(_estalo, bandas)] = detector.tirar_os_impressos()
    return bandas


def _distancia(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) / len(a))


def test_o_estalo_a_esquerda_chega_com_lado_negativo_e_24_bandas() -> None:
    quadros = _fundo(0.6, semente=3)
    _grave(quadros, 0.3, (1.0, 0.1), 0.0)
    publicados: list[dict[str, Any]] = []
    _ouvir_tudo(_ouvido(_pcm(quadros), publicados, assinado=True))
    assert len(publicados) == 1, publicados
    [carga] = publicados
    assert set(carga) == {"t", "evento", "lado", "energia", "canais", "bandas"}
    assert carga["evento"] == "estalo" and carga["canais"] == 2
    assert carga["lado"] < -0.5
    assert len(carga["bandas"]) == 24
    assert all(isinstance(b, float) for b in carga["bandas"])
    assert 0.0 < carga["energia"] <= 1.0
    json.dumps(carga)


def test_o_estalo_a_direita_chega_com_lado_positivo() -> None:
    quadros = _fundo(0.6, semente=4)
    _agudo(quadros, 0.3, (0.1, 1.0), 5)
    publicados: list[dict[str, Any]] = []
    _ouvir_tudo(_ouvido(_pcm(quadros), publicados, assinado=True))
    assert [c["lado"] > 0.5 for c in publicados] == [True]


def test_sem_assinante_nenhum_estalo_sai_e_nada_se_imprime() -> None:
    quadros = _fundo(0.6, semente=3)
    _grave(quadros, 0.3, (1.0, 0.1), 0.0)
    publicados: list[dict[str, Any]] = []
    ouvido = _ouvido(_pcm(quadros), publicados, assinado=False)
    _ouvir_tudo(ouvido)
    assert publicados == []
    assert not ouvido.detector.imprimir


def test_timbres_diferentes_dao_bandas_distantes_e_o_mesmo_timbre_bandas_proximas() -> None:
    graves = []
    for semente, fase in ((11, 0.0), (12, 1.3)):
        quadros = _fundo(0.5, semente=semente)
        _grave(quadros, 0.25, (1.0, 1.0), fase)
        graves.append(_bandas(_pcm(quadros)))
    quadros = _fundo(0.5, semente=13)
    _agudo(quadros, 0.25, (1.0, 1.0), 21)
    agudo = _bandas(_pcm(quadros))
    mesmo = _distancia(graves[0], graves[1])
    outro = min(_distancia(graves[0], agudo), _distancia(graves[1], agudo))
    assert outro > 4 * mesmo, (mesmo, outro)
    assert sum(graves[0][:6]) > sum(agudo[:6]) and sum(agudo[-6:]) > sum(graves[0][-6:])


def test_a_impressao_cabe_no_estalo() -> None:
    import time

    sorteio = random.Random(1)
    mono = [sorteio.uniform(-1, 1) for _ in range(tj.PONTOS_DA_IMPRESSAO)]
    inicio = time.process_time()
    for _ in range(20):
        tj.bandas_log_mel(mono)
    por_estalo = (time.process_time() - inicio) / 20
    assert por_estalo < 0.02, f"{por_estalo * 1000:.1f} ms por estalo"


class _Ouvido:
    def __init__(self) -> None:
        self.comecos = 0
        self.fila: list[tj.Transiente] = [tj.Transiente(1.0, "esquerdo", 0.5)]

    def comecar(self) -> None:
        self.comecos += 1

    def tirar(self) -> list[tj.Transiente]:
        achados, self.fila = self.fila, []
        return achados


def _daemon(bus: EventBus) -> Any:
    return SimpleNamespace(
        bus=bus, display_authority="game", store=SimpleNamespace(active_profile=None),
        controller=None)


def test_com_o_tato_vivo_sem_pedir_o_som_o_assinante_sozinho_acorda_o_ouvido() -> None:
    bus = EventBus()
    motor = tv.TatoVivo([])
    ouvido = _Ouvido()
    motor.ouvido = ouvido
    passo = tv.Passo(_daemon(bus), motor)
    passo(100.0)
    assert not passo.ouvido_quer() and ouvido.comecos == 0
    fila = bus.subscribe(EventTopic.JOGO_SOM)
    passo(101.0)
    assert passo.ouvido_quer() and ouvido.comecos == 1
    assert ouvido.fila == [], "o estalo que só a porta quer não fica preso na fila do tato"
    bus.unsubscribe(EventTopic.JOGO_SOM, fila)
    assert not passo.ouvido_quer()


def test_sem_jogo_o_assinante_nao_acorda_o_ouvido() -> None:
    bus = EventBus()
    daemon = _daemon(bus)
    daemon.display_authority = "daemon"
    motor = tv.TatoVivo([])
    motor.ouvido = _Ouvido()
    passo = tv.Passo(daemon, motor)
    bus.subscribe(EventTopic.JOGO_SOM)
    passo(100.0)
    assert not passo.ouvido_quer()


def test_o_pcm_que_so_a_porta_quer_nao_mexe_na_cena_do_tato() -> None:
    bus = EventBus()
    motor = tv.TatoVivo([])
    passo = tv.Passo(_daemon(bus), motor)
    antes = vars(motor.cena).copy()
    bus.subscribe(EventTopic.JOGO_SOM)
    passo.alimentar_o_corpo(b"\x7f" * 960)
    assert vars(motor.cena) == antes


def test_os_tres_topicos_pedem_permissao_e_a_identidade_e_estado() -> None:
    for topico in ("jogo.som", "microfone.nivel", "jogo.identidade"):
        assert topico in TOPICOS_DE_LEITURA
        assert permissao_valida(f"ler:{topico}")
    assert EventTopic.JOGO_IDENTIDADE in TOPICOS_DE_ESTADO
    assert EventTopic.JOGO_SOM not in TOPICOS_DE_ESTADO


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def evento(self) -> dict[str, Any]:
        recebido: dict[str, Any] = json.loads(self.arquivo.readline())
        return recebido

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


def test_a_extensao_de_mentira_assina_os_tres_e_sem_permissao_e_recusada() -> None:
    topicos = ["jogo.som", "microfone.nivel", "jogo.identidade"]

    async def corrida() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with tempfile.TemporaryDirectory(prefix="pj") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor,
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
            await porta.iniciar()
            porta.registrar("ficha-com", "com", os.getpid(), [f"ler:{t}" for t in topicos])
            porta.registrar("ficha-sem", "sem", os.getpid(), ["ler:bateria"])
            com = _Cliente(caminho)
            sem = _Cliente(caminho)
            try:
                await asyncio.to_thread(com.pedir, "mod.ola", {"ficha": "ficha-com"})
                await asyncio.to_thread(sem.pedir, "mod.ola", {"ficha": "ficha-sem"})
                recusas = [
                    await asyncio.to_thread(sem.pedir, "eventos.assinar", {"topicos": [t]})
                    for t in topicos
                ]
                assert bus.subscriber_count(EventTopic.MICROFONE_NIVEL) == 0
                aceito = await asyncio.to_thread(
                    com.pedir, "eventos.assinar", {"topicos": topicos})
                assert aceito["result"] == {"assinados": topicos}
                assert bus.subscriber_count(EventTopic.JOGO_SOM) == 1
                assert bus.subscriber_count(EventTopic.MICROFONE_NIVEL) == 1
                bus.publish(EventTopic.JOGO_SOM, {
                    "t": 1.0, "evento": "estalo", "lado": -0.8, "energia": 0.4, "canais": 2,
                    "bandas": [0.0] * 24})
                bus.publish(EventTopic.MICROFONE_NIVEL, {
                    "uniq": P2, "nivel": 0.3, "mudo": False, "do_jogo": True, "t": 2.0})
                bus.publish(EventTopic.JOGO_IDENTIDADE, {
                    "chave": "steam_app_9900010", "executavel": "a.exe", "buildid": "7",
                    "loja": "steam", "emulador": None})
                eventos = [
                    await asyncio.wait_for(asyncio.to_thread(com.evento), 3) for _ in range(3)]
            finally:
                com.fechar()
                sem.fechar()
                await porta.parar()
            return recusas, eventos

    recusas, eventos = asyncio.run(corrida())
    assert [r["error"]["code"] for r in recusas] == [CODE_SEM_PERMISSAO] * 3
    por_nome = {e["params"]["nome"]: e["params"] for e in eventos}
    assert set(por_nome) == {"jogo.som", "microfone.nivel", "jogo.identidade"}
    assert por_nome["jogo.som"]["dados"]["lado"] == -0.8
    assert por_nome["microfone.nivel"]["dados"]["uniq"] == P2
    assert "pid" not in por_nome["jogo.identidade"]["dados"]


def test_sem_assinante_o_microfone_do_radio_nao_abre_e_com_ele_abre() -> None:
    mesa = [P1, P2]
    transportes = {P1: "bt", P2: "usb"}
    mudos: dict[str, bool | None] = {P1: False, P2: True}
    assert lm._a_medir(mesa, {}, transportes, mudos) == []
    assert lm._a_medir(mesa, {}, transportes, mudos, assinado=True) == [P1]
    mudos[P1] = True
    assert lm._a_medir(mesa, {}, transportes, mudos, assinado=True) == []


def test_o_nivel_de_cada_controle_sai_pelo_uniq_e_o_mudo_e_zero() -> None:
    cargas = lm.niveis_do_microfone(
        [P1, P2], {P1: 0.42, P2: 0.9}, {P1: False, P2: True}, {P1: True}, 5.0)
    assert cargas == [
        {"uniq": P1, "nivel": 0.42, "mudo": False, "do_jogo": True, "t": 5.0},
        {"uniq": P2, "nivel": 0.0, "mudo": True, "do_jogo": None, "t": 5.0},
    ]


class _Fluxo:
    def __init__(self, picos: list[float]) -> None:
        self._r, escrita = os.pipe()
        os.write(escrita, b"".join(struct.pack("<f", p) for p in picos))
        os.close(escrita)
        self.fd = self._r

    def fechar(self) -> None:
        os.close(self._r)


def test_o_medidor_guarda_o_pico_e_zera_a_cada_pergunta() -> None:
    fluxos: list[_Fluxo] = []

    def abrir(_uniq: str, _fonte: str) -> Any:
        fluxo = _Fluxo([0.1, -0.7, 0.2, float("nan")])
        fluxos.append(fluxo)
        return SimpleNamespace(fd=fluxo.fd, vivo=lambda: True, parar=fluxo.fechar)

    medidor = nm.NivelDoMicrofone(abrir=abrir, agora=lambda: 1.0)
    try:
        medidor._canais[P1] = nm._Canal(P1, "fonte", abrir(P1, "fonte"), nm.Histerese())
        medidor._desejado = {P1: "fonte", P2: "outra"}
        medidor._comer(P1, 1.0)
        assert medidor.picos() == {P1: 0.7, P2: None}
        assert medidor.picos()[P1] == 0.0
    finally:
        medidor._canais.clear()
        for fluxo in fluxos:
            with contextlib.suppress(OSError):
                fluxo.fechar()


def test_o_jogo_le_a_fonte_pelo_pid_da_captura() -> None:
    saida = json.dumps([
        {"index": 1, "source": 7, "corked": False,
         "properties": {"application.process.id": "4242", "application.name": "jogo"}},
        {"index": 2, "source": 8, "corked": False,
         "properties": {"application.process.id": "99", "application.name": "outro"}},
        {"index": 3, "source": 9, "corked": True,
         "properties": {"application.process.id": "4242"}},
    ])
    nomes = {7: "fonte_p1", 8: "fonte_p2", 9: "fonte_p3"}
    assert nm.fontes_que_o_jogo_le(saida, nomes, {4242}) == frozenset({"fonte_p1"})


def _processo(raiz: Path, pid: int, argv: list[str], ambiente: dict[str, str]) -> None:
    pasta = raiz / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    (pasta / "environ").write_bytes(
        b"\0".join(f"{k}={v}".encode() for k, v in ambiente.items()) + b"\0")


def test_a_identidade_tem_chave_executavel_e_buildid_sem_pid(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    steamapps = tmp_path / "steamapps"
    steamapps.mkdir()
    (steamapps / "appmanifest_1234.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"1234"\n\t"buildid"\t\t"998877"\n}\n', encoding="utf-8")
    _processo(proc, 10, ["/usr/bin/reaper", "SteamLaunch"], {"SteamAppId": "1234"})
    _processo(proc, 11, ["C:\\windows\\system32\\services.exe"], {"SteamAppId": "1234"})
    _processo(proc, 12, ["Z:\\jogos\\Jogo\\Jogo-Win64.exe", "-dx12"], {"SteamAppId": "1234"})
    _processo(proc, 13, ["/usr/bin/outro"], {"SteamAppId": "12345"})
    carga = ij.identidade(1234, raiz_proc=proc, pastas=[steamapps])
    assert carga == {"chave": "steam_app_1234", "executavel": "Jogo-Win64.exe",
                     "buildid": "998877", "loja": "steam", "emulador": None}
    assert "pid" not in json.dumps(carga)
    fora = ij.identidade(None, raiz_proc=proc, pastas=[steamapps])
    assert fora["chave"] is None and fora["executavel"] is None


def test_o_emulador_se_reconhece_pelo_executavel(tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    _processo(
        proc, 20, ["/opt/retroarch/retroarch", "-L", "x.so"], {"STEAM_COMPAT_APP_ID": "9900020"})
    carga = ij.identidade(9900020, raiz_proc=proc, pastas=[])
    assert carga["emulador"] == "retroarch" and carga["executavel"] == "retroarch"


def test_a_identidade_so_se_republica_quando_muda() -> None:
    publicadas: list[dict[str, Any]] = []
    quem = ij.Identificador(publicadas.append)
    carga = {"chave": "steam_app_1", "executavel": "a.exe", "buildid": "1", "loja": "steam",
             "emulador": None}
    assert quem.precisa(1)
    assert quem.receber(1, carga)
    assert not quem.precisa(1)
    assert not quem.receber(1, dict(carga))
    assert quem.precisa(2)
    assert len(publicadas) == 1
