"""As modificações rodam fora do serviço (AS-MODIFICACOES-RODAM-FORA-DO-DAEMON-01, ADR-021).

Tudo num lar de mentira (``HOME`` e ``XDG_*`` em pasta temporária), com o
barramento e a porta de verdade e os escritores do serviço por dublê. Nenhuma
prova fala com o serviço dela, com a rede de fora nem com o GitHub: os
repositórios são ``git init`` locais, abertos por ``file://``.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES, instalador
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    conferir_remocao,
    instalar,
    ler_estado,
    ler_registro,
    ligar,
    manifesto_instalado,
    remover,
)
from hefesto_dualsense4unix.mods.manifesto import (
    ManifestoRecusadoError,
    aceita_a_api,
    ler_manifesto,
)
from hefesto_dualsense4unix.mods.porta import (
    CODE_O_JOGO_ESCREVE,
    CODE_SEM_PERMISSAO,
    Porta,
    o_jogo_escreve_no_servico,
)
from hefesto_dualsense4unix.mods.supervisor import Supervisor, parar_o_grupo

UNIQ = "aa:bb:cc:00:00:01"
OUTRO = "aa:bb:cc:00:00:02"


# -- o lar de mentira ---------------------------------------------------------


#: Fora do ``/tmp``: a caixa monta um ``/tmp`` vazio, e uma casa de mentira
#: dentro dele sumiria da caixa por isso, com ou sem a cura que se quer provar.
_FORA_DO_TMP = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None


@pytest.fixture
def curto() -> Iterator[Path]:
    """Uma pasta de caminho curto: o socket Unix aceita até 107 bytes."""
    pasta = Path(tempfile.mkdtemp(prefix="hm", dir=_FORA_DO_TMP))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@pytest.fixture
def lar(curto: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    casa = curto / "casa"
    execucao = curto / "run"
    for pasta in (casa, execucao):
        pasta.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(casa / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(casa / ".local/state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(casa / ".cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(execucao))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    lugares = Lugares.do_xdg()
    for caminho in (lugares.codigo, lugares.dados, lugares.registro, lugares.estado):
        assert str(caminho).startswith(str(curto)), caminho
    return lugares


def _manifesto(mod_id: str = "exemplo", **mais: Any) -> dict[str, Any]:
    corpo: dict[str, Any] = {
        "id": mod_id,
        "nome": "Exemplo",
        "versao": "0.1.0",  # (noqa-acento): contrato ASCII
        "api": ">=1,<3",
        "licenca": "MIT",
        "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["ler:estado", "escrever:luz"],  # (noqa-acento): contrato ASCII
    }
    corpo.update(mais)
    return corpo


#: O filho de mentira: fala com a porta e faz o que o arquivo ``modo`` manda.
_O_FILHO = textwrap.dedent('''
    import json, os, signal, socket, sys, time
    modo = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modo")).read().strip()
    dados = os.environ.get("HEFESTO_MOD_DADOS", ".")
    def relatar(**k):
        with open(os.path.join(dados, "relato.json"), "w") as f:
            json.dump(k, f)
    if modo == "cai":
        print("falhei agora", flush=True)
        sys.exit(3)
    if modo == "teimoso":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        relatar(pid=os.getpid())
        while True:
            time.sleep(1)
    if modo == "neto":
        import subprocess
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)", sys.argv[1]])
    s = socket.socket(socket.AF_UNIX)
    s.connect(os.environ["HEFESTO_MOD_SOCKET"])
    s.sendall((json.dumps({"jsonrpc": "2.0", "id": 1, "method": "mod.ola",
                           "params": {"ficha": os.environ["HEFESTO_MOD_FICHA"]}}) + "\\n").encode())
    ola = json.loads(s.makefile().readline())
    caixa = {}
    if modo == "caixa":
        casa = os.environ["HOME"]
        # Na HOME vazia só aparece o caminho até o código e os dados da modificação.
        caixa["casa"] = sorted(os.listdir(casa))
        caixa["segredo_visivel"] = os.path.exists(os.path.join(casa, "segredo.txt"))
        caixa["config_visivel"] = os.path.exists(os.path.join(casa, ".config"))
        try:
            open("escrito-no-codigo", "w").write("x")
            caixa["codigo_gravavel"] = True
        except OSError:
            caixa["codigo_gravavel"] = False
        open(os.path.join(dados, "escrito-nos-dados"), "w").write("x")
        caixa["redes"] = sorted(n for _i, n in socket.if_nameindex())
        caixa["principal_visivel"] = os.path.exists(sys.argv[1])
    relatar(ola=ola, caixa=caixa, pid=os.getpid())
    while True:
        time.sleep(1)
''')


def _ligar_vendo(mod_id: str, lar: Lugares) -> None:
    """O gesto da linha de comando: mostra o manifesto instalado e liga com o que mostrou."""
    ligar(mod_id, permissoes_vistas=manifesto_instalado(mod_id, lugares=lar).permissoes,
          lugares=lar)


def _pasta_do_mod(base: Path, modo: str = "fica", **mais: Any) -> Path:
    pasta = base / f"fonte-{mais.get('mod_id', 'exemplo')}"
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = _manifesto(**mais)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text(_O_FILHO, encoding="utf-8")
    (pasta / "modo").write_text(modo, encoding="utf-8")
    return pasta


async def _ate(condicao: Any, prazo: float = 10.0, passo: float = 0.02) -> None:
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return
        await asyncio.sleep(passo)
    raise AssertionError("o prazo passou sem a condição")


def _supervisor(
    lar: Lugares, bus: EventBus | None = None, *, escritas: list[Any] | None = None, **mais: Any
) -> Supervisor:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        if escritas is not None:
            escritas.append((metodo, pedido))
        return {"status": "ok"}

    return Supervisor(
        bus or EventBus(),
        escritor=escritor,
        o_jogo_escreve=lambda uniq, canal: False,
        uniq_do_posto=lambda: UNIQ,
        lugares=lar,
        **mais,
    )


# -- o manifesto e a versão da porta -------------------------------------------


def test_o_manifesto_fora_da_faixa_da_api_e_recusado_com_a_frase(tmp_path: Path) -> None:
    (tmp_path / "hefesto-mod.json").write_text(
        json.dumps(_manifesto(api=">=3,<4")), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert recusa.value.frase == (
        f"«Exemplo» pede a porta >=3,<4, e este Hefesto fala a {API_DAS_MODIFICACOES}."
    )
    assert aceita_a_api(">=1,<3") and not aceita_a_api("<1") and aceita_a_api("2")


def test_o_manifesto_recusa_campo_desconhecido_e_permissao_inventada(tmp_path: Path) -> None:
    (tmp_path / "hefesto-mod.json").write_text(
        json.dumps(_manifesto(senha="x")), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError, match="«senha»"):
        ler_manifesto(tmp_path)
    (tmp_path / "hefesto-mod.json").write_text(
        json.dumps(_manifesto(permissoes=["escrever:tudo"])), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError, match="escrever:tudo"):
        ler_manifesto(tmp_path)


def test_a_modificacao_fora_da_api_nao_sobe_e_o_estado_diz_por_que(
    lar: Lugares, curto: Path
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    manifesto = lar.codigo / "exemplo" / "hefesto-mod.json"
    manifesto.write_text(json.dumps(_manifesto(api=">=7")), encoding="utf-8")

    async def corrida() -> None:
        supervisor = _supervisor(lar, procurar_bwrap=False)
        await supervisor.iniciar()
        try:
            estado = supervisor.estado_de("exemplo")
            assert estado is not None and estado.estado == "recusada"
            assert estado.motivo == "«Exemplo» pede a porta >=7, e este Hefesto fala a 2."
            assert ler_estado(lar.estado)["exemplo"]["motivo"] == estado.motivo
            assert not supervisor.porta.aberta
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_atualizacao_que_pede_permissao_nova_volta_a_pedir_o_sim(
    lar: Lugares, curto: Path
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    assert ler_registro(lar.registro)["exemplo"].ligada
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(versao="0.2.0")))
    mesma = instalar(str(pasta), lugares=lar)
    assert mesma.permissoes_novas == [] and mesma.entrada.ligada
    (pasta / "hefesto-mod.json").write_text(
        json.dumps(_manifesto(permissoes=["ler:estado", "escrever:luz", "rede:internet"])))
    nova = instalar(str(pasta), lugares=lar)
    assert nova.permissoes_novas == ["rede:internet"]
    entrada = ler_registro(lar.registro)["exemplo"]
    assert not entrada.ligada
    assert "rede:internet" not in entrada.permissoes_aceitas


# -- a porta -------------------------------------------------------------------


class _Cliente:
    """Um cliente da porta no mesmo processo (o PID do ``SO_PEERCRED`` é o nosso)."""

    def __init__(self, caminho: Path) -> None:
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.sock.setblocking(True)
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

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


async def _porta_viva(
    curto: Path,
    bus: EventBus,
    permissoes: list[str],
    *,
    o_jogo_escreve: Any = None,
    escritas: list[Any] | None = None,
) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        if escritas is not None:
            escritas.append((metodo, pedido))
        return {"status": "ok"}

    porta = Porta(
        curto / "mods.sock",
        bus,
        escritor=escritor,
        o_jogo_escreve=o_jogo_escreve or (lambda uniq, canal: False),
        uniq_do_posto=lambda: UNIQ,
    )
    await porta.iniciar()
    porta.registrar("ficha-certa", "exemplo", os.getpid(), permissoes)
    return porta


def test_a_porta_e_propria_e_so_do_usuario(curto: Path) -> None:
    async def corrida() -> None:
        porta = await _porta_viva(curto, EventBus(), [])
        try:
            assert (curto / "mods.sock").stat().st_mode & 0o777 == 0o600
        finally:
            await porta.parar()
        assert not (curto / "mods.sock").exists()

    asyncio.run(corrida())


def test_a_assinatura_sem_permissao_e_recusada_nomeando_a_permissao(curto: Path) -> None:
    async def corrida() -> None:
        bus = EventBus()
        porta = await _porta_viva(curto, bus, ["ler:estado"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            ola = await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-certa"})
            assert ola["result"]["api"] == API_DAS_MODIFICACOES
            recusa = await asyncio.to_thread(
                cliente.pedir, "eventos.assinar", {"topicos": ["botoes"]})
            assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
            assert recusa["error"]["message"] == "falta a permissão ler:botoes"
            assert bus.subscriber_count(EventTopic.BUTTON_DOWN) == 0
            aceita = await asyncio.to_thread(
                cliente.pedir, "eventos.assinar", {"topicos": ["estado"]})
            assert aceita["result"] == {"assinados": ["estado"]}
            assert bus.subscriber_count(EventTopic.STATE_UPDATE) == 1
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())


def test_a_ficha_errada_e_recusada_e_a_conexao_fecha(curto: Path) -> None:
    async def corrida() -> None:
        porta = await _porta_viva(curto, EventBus(), ["ler:estado"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            recusa = await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "inventada"})
            assert recusa["error"]["message"] == "ficha desconhecida"
            assert await asyncio.to_thread(cliente.arquivo.readline) == b""
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())


def test_o_processo_que_nao_e_o_criado_e_recusado_mesmo_com_a_ficha(curto: Path) -> None:
    async def corrida() -> None:
        porta = await _porta_viva(curto, EventBus(), [])
        porta.registrar("ficha-de-outro", "outra", 999_999_999, [])
        cliente = _Cliente(curto / "mods.sock")
        try:
            recusa = await asyncio.to_thread(
                cliente.pedir, "mod.ola", {"ficha": "ficha-de-outro"})
            assert recusa["error"]["message"] == "este processo não é o que o Hefesto abriu"
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())


def test_a_escrita_pede_o_uniq_a_permissao_e_cede_ao_jogo(curto: Path) -> None:
    escritas: list[Any] = []

    def o_jogo_escreve(uniq: str, canal: str) -> bool:
        return uniq == OUTRO and canal == "luz"

    async def corrida() -> None:
        porta = await _porta_viva(
            curto, EventBus(), ["escrever:luz"], o_jogo_escreve=o_jogo_escreve,
            escritas=escritas)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-certa"})
            sem_uniq = await asyncio.to_thread(
                cliente.pedir, "luz.set", {"rgb": [1, 2, 3]})
            assert "uniq" in sem_uniq["error"]["message"]
            sem_permissao = await asyncio.to_thread(
                cliente.pedir, "vibracao.set", {"uniq": UNIQ, "fraco": 10, "forte": 10})
            assert sem_permissao["error"] == {
                "code": CODE_SEM_PERMISSAO, "message": "falta a permissão escrever:vibracao"}
            do_jogo = await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": OUTRO, "rgb": [1, 2, 3]})
            assert do_jogo["error"]["code"] == CODE_O_JOGO_ESCREVE
            feita = await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": UNIQ, "rgb": [1, 2, 3], "brilho": 0.5})
            assert feita["result"] == {"status": "ok"}
        finally:
            cliente.fechar()
            await porta.parar()

    asyncio.run(corrida())
    assert escritas == [
        ("led.set", {"uniq": UNIQ, "rgb": [1, 2, 3], "brightness": 0.5}),
    ]


def test_o_jogo_escreve_le_a_camada_do_jogo_por_controle() -> None:
    from types import SimpleNamespace

    saida = SimpleNamespace(led=(255, 0, 0), trigger_left=None, trigger_right=None)
    controle = SimpleNamespace(
        primary_uniq="aabbcc000001",
        _game_output_by_uniq={"aabbcc000001": saida},
        _game_triggers_by_uniq={"aabbcc000002": {"left": b"\x01"}},
    )
    vpad_que_vibrou = SimpleNamespace(rumble_no_fisico_ha_s=0.3)
    vpad_quieto = SimpleNamespace(rumble_no_fisico_ha_s=None)
    jogadores = {"aa:bb:cc:00:00:02": SimpleNamespace(vpad=vpad_que_vibrou)}
    servico = SimpleNamespace(
        controller=controle,
        is_native_mode=lambda: False,
        _gamepad_device=vpad_quieto,
        _coop_manager=SimpleNamespace(_players=jogadores),
    )
    pergunta = o_jogo_escreve_no_servico(servico)
    assert pergunta(UNIQ, "luz") and not pergunta(OUTRO, "luz")
    assert pergunta(OUTRO, "gatilho") and not pergunta(UNIQ, "gatilho")
    assert pergunta(OUTRO, "vibracao") and not pergunta(UNIQ, "vibracao")
    servico.is_native_mode = lambda: True
    assert pergunta(UNIQ, "vibracao")


def test_o_assinante_que_nao_le_nao_atrasa_o_tique(curto: Path) -> None:
    """O tique publica o estado e espera o próximo; a modificação assinou e nunca lê.

    A fila do barramento descarta o mais antigo: o tique não espera por ela.
    Mordida: sem o descarte, a fila cheia segura o tique.
    """
    tique_s = 0.004
    tiques = 400
    carga = {"botoes": ["cross"] * 200, "eixos": list(range(400)), "uniq": UNIQ}

    async def corrida() -> tuple[float, int, int]:
        bus = EventBus(queue_maxsize=16)
        bus.bind_loop(asyncio.get_running_loop())
        porta = await _porta_viva(curto, bus, ["ler:estado"])
        cliente = _Cliente(curto / "mods.sock")
        cliente.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-certa"})
            await asyncio.to_thread(cliente.pedir, "eventos.assinar", {"topicos": ["estado"]})
            (fila,) = porta.assinaturas_de("exemplo")
            pior = 0.0
            cheia = 0
            for _ in range(tiques):
                inicio = time.perf_counter()
                bus.publish(EventTopic.STATE_UPDATE, carga)
                pior = max(pior, time.perf_counter() - inicio)
                cheia += fila.full()
                await asyncio.sleep(tique_s)
            return pior, fila.qsize(), cheia
        finally:
            cliente.fechar()
            await porta.parar()

    pior, tamanho, cheia = asyncio.run(corrida())
    # A modificação não leu nada: a fila encheu (senão a prova não prova nada)...
    assert cheia > tiques // 2, f"a fila nunca encheu ({cheia})"
    assert tamanho <= 16
    # ...e o tique nunca esperou por ela.
    # Publicar custa microssegundos; 10 ms é folga para a máquina carregada, e
    # ainda menos que um tique de 60 Hz (16,7 ms).
    assert pior < 0.010, f"o tique esperou {pior * 1000:.1f} ms pela modificação"


# -- o supervisor --------------------------------------------------------------


def _instalar_e_ligar(lar: Lugares, curto: Path, modo: str, **mais: Any) -> None:
    pasta = _pasta_do_mod(curto / "fontes", modo, **mais)
    instalar(str(pasta), lugares=lar)
    _ligar_vendo(mais.get("mod_id", "exemplo"), lar)


def _relato(lar: Lugares, mod_id: str = "exemplo") -> dict[str, Any] | None:
    try:
        dado: dict[str, Any] = json.loads(
            (lar.dados / mod_id / "relato.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dado


def test_o_filho_fala_pela_porta_com_a_ficha_e_sem_caixa_o_estado_diz(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "fica")

    async def corrida() -> None:
        supervisor = _supervisor(lar, procurar_bwrap=False)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            relato = _relato(lar)
            assert relato is not None and relato["ola"]["result"]["id"] == "exemplo"
            assert relato["pid"] == supervisor.pid_de("exemplo")
            estado = ler_estado(lar.estado)["exemplo"]
            assert estado["estado"] == "rodando" and estado["caixa"] == ""
            assert estado["motivo"] == "Roda sem caixa: o bwrap não está instalado."
            assert os.getpgid(relato["pid"]) == relato["pid"], "o filho tem grupo próprio"
        finally:
            await supervisor.parar()
        assert not lar.estado.exists()

    asyncio.run(corrida())


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="sem bwrap nesta máquina")
def test_com_bwrap_a_caixa_esconde_a_casa_a_rede_e_o_socket_principal(
    lar: Lugares, curto: Path
) -> None:
    assert not curto.is_relative_to("/tmp"), "no /tmp a caixa esconde tudo sozinha"
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    principal = ipc_socket_path()
    principal.parent.mkdir(parents=True, exist_ok=True)
    principal.write_text("socket principal de mentira", encoding="utf-8")
    (Path(os.environ["HOME"]) / "segredo.txt").write_text("x", encoding="utf-8")
    pasta = _pasta_do_mod(curto / "fontes", "caixa")
    manifesto = _manifesto()
    manifesto["processo"]["executar"] = ["python3", "mod.py", str(principal)]
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)

    async def corrida() -> dict[str, Any]:
        supervisor = _supervisor(lar)
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            assert ler_estado(lar.estado)["exemplo"]["caixa"] == "bwrap"
            relato = _relato(lar)
            assert relato is not None
            return relato
        finally:
            await supervisor.parar()

    relato = asyncio.run(corrida())
    assert relato["ola"]["result"]["id"] == "exemplo", relato
    assert relato["caixa"] == {
        "casa": [".local"],
        "segredo_visivel": False,
        "config_visivel": False,
        "codigo_gravavel": False,
        "redes": ["lo"],
        "principal_visivel": False,
    }
    assert (lar.dados / "exemplo" / "escrito-nos-dados").is_file()
    assert not (lar.codigo / "exemplo" / "escrito-no-codigo").exists()


def test_o_filho_que_cai_volta_tres_vezes_e_na_quarta_para_com_a_ultima_linha(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "cai")

    async def corrida() -> None:
        supervisor = _supervisor(lar, procurar_bwrap=False, esperas=(0.05, 0.1, 0.2))
        await supervisor.iniciar()
        try:
            await _ate(lambda: getattr(supervisor.estado_de("exemplo"), "estado", "")
                       == "parou")
            estado = ler_estado(lar.estado)["exemplo"]
            assert estado["quedas"] == 4
            assert estado["ultima_linha"] == "falhei agora"
            assert estado["motivo"] == "Caiu 4 vezes seguidas (código 3)."
            diario = (lar.dados / "exemplo" / "diario.log").read_text(encoding="utf-8")
            assert diario.count("falhei agora") == 4
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_o_filho_que_ignora_o_sigterm_morre_pelo_pid_dentro_do_prazo(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "teimoso")
    prazo = 0.5

    async def corrida() -> tuple[int, float]:
        supervisor = _supervisor(lar, procurar_bwrap=False, prazo_para_parar_s=prazo)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            relato = _relato(lar)
            assert relato is not None
            inicio = time.monotonic()
            await supervisor.parar()
            return relato["pid"], time.monotonic() - inicio
        finally:
            await supervisor.parar()

    pid, levou = asyncio.run(corrida())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert prazo <= levou < prazo + 2.0


def test_parar_o_grupo_manda_o_sigkill_no_fim_do_prazo() -> None:
    async def corrida() -> int | None:
        processo = await asyncio.create_subprocess_exec(
            sys.executable, "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "print('pronto', flush=True); time.sleep(60)",
            stdout=asyncio.subprocess.PIPE, start_new_session=True)
        assert processo.stdout is not None
        await processo.stdout.readline()
        codigo: int | None = await parar_o_grupo(processo, 0.3)
        return codigo

    assert asyncio.run(corrida()) == -9


def _com_a_marca(marca: str) -> list[int]:
    """Os PIDs (vistos daqui) cuja linha de comando leva ``marca``."""
    achados: list[int] = []
    for pasta in Path("/proc").iterdir():
        if not pasta.name.isdigit():
            continue
        try:
            linha = (pasta / "cmdline").read_bytes()
        except OSError:
            continue
        if marca.encode() in linha.split(b"\0"):
            achados.append(int(pasta.name))
    return achados


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="sem bwrap nesta máquina")
def test_na_caixa_o_que_a_modificacao_abriu_morre_com_ela(
    lar: Lugares, curto: Path
) -> None:
    """O ``--new-session`` do ``bwrap`` põe o filho fora do grupo do PID criado: sem
    o espaço de PID próprio, o neto que a modificação deixa de fundo sobrevive ao
    «parar». Mordida: tirar o ``--unshare-pid`` e ver o neto vivo."""
    marca = f"neto-da-modificacao-{os.getpid()}-{time.monotonic_ns()}"
    pasta = _pasta_do_mod(curto / "fontes", "neto")
    manifesto = _manifesto()
    manifesto["processo"]["executar"] = ["python3", "mod.py", marca]
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)

    async def corrida() -> tuple[list[int], list[int]]:
        supervisor = _supervisor(lar)
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None and bool(_com_a_marca(marca)))
            antes = _com_a_marca(marca)
        finally:
            await supervisor.parar()
        await asyncio.sleep(0.3)
        return antes, _com_a_marca(marca)

    try:
        antes, depois = asyncio.run(corrida())
    finally:
        for pid in _com_a_marca(marca):
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
    assert antes, "o neto nunca nasceu: a prova não prova nada"
    assert depois == [], f"o neto {depois} sobreviveu ao «parar»"


@pytest.mark.skipif(shutil.which("bwrap") is None, reason="sem bwrap nesta máquina")
def test_sem_xdg_runtime_dir_a_caixa_esconde_a_execucao_da_sessao(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem ``XDG_RUNTIME_DIR``, o socket principal não vai para a ``HOME``: o
    ``platformdirs`` resolve ``/run/user/<uid>``. A caixa esconde o avô da porta.
    Mordida: esconder só o ``XDG_RUNTIME_DIR`` do ambiente e ver o principal à mostra."""
    assert not curto.is_relative_to("/tmp"), "no /tmp a caixa esconde tudo sozinha"
    execucao = curto / "execucao-da-casa" / "hefesto-dualsense4unix"
    execucao.mkdir(parents=True)
    principal = execucao / "hefesto-dualsense4unix.sock"
    principal.write_text("socket principal de mentira", encoding="utf-8")
    pasta = _pasta_do_mod(curto / "fontes", "caixa")
    manifesto = _manifesto()
    manifesto["processo"]["executar"] = ["python3", "mod.py", str(principal)]
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    monkeypatch.delenv("XDG_RUNTIME_DIR")

    async def corrida() -> dict[str, Any]:
        supervisor = _supervisor(lar, porta=execucao / "mods.sock")
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            relato = _relato(lar)
            assert relato is not None
            return relato
        finally:
            await supervisor.parar()

    relato = asyncio.run(corrida())
    assert relato["ola"]["result"]["id"] == "exemplo", relato
    assert relato["caixa"]["principal_visivel"] is False


def test_a_que_parou_fica_parada_ate_ligar_de_novo(lar: Lugares, curto: Path) -> None:
    """Outra linha do registro que muda não reabre a que parou na quarta queda.
    Mordida: reabrir toda vigia terminada e ver o diário passar de quatro quedas."""
    _instalar_e_ligar(lar, curto, "cai")
    diario = lar.dados / "exemplo" / "diario.log"

    def quedas_no_diario() -> int:
        return diario.read_text(encoding="utf-8").count("falhei agora")

    async def corrida() -> None:
        supervisor = _supervisor(lar, procurar_bwrap=False, esperas=(0.05, 0.1, 0.2))
        await supervisor.iniciar()
        try:
            await _ate(lambda: getattr(supervisor.estado_de("exemplo"), "estado", "")
                       == "parou")
            instalar(str(_pasta_do_mod(curto / "fontes", mod_id="outra")), lugares=lar)
            await supervisor.reconciliar()
            await asyncio.sleep(0.5)
            estado = supervisor.estado_de("exemplo")
            assert estado is not None and estado.estado == "parou"
            assert quedas_no_diario() == 4
            _ligar_vendo("exemplo", lar)
            await supervisor.reconciliar()
            await _ate(lambda: quedas_no_diario() == 8
                       and getattr(supervisor.estado_de("exemplo"), "estado", "") == "parou")
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_instancia_isolada_nao_abre_as_modificacoes(
    lar: Lugares, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O ``--fake`` divide a casa com o serviço de verdade: abrir as modificações
    dali trocaria a porta dele e abriria cada uma duas vezes."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.mods.supervisor import supervisor_do_servico
    from hefesto_dualsense4unix.utils.xdg_paths import FAKE_ENV_VAR, IPC_SOCKET_ENV_VAR

    servico = SimpleNamespace(bus=EventBus(), controller=None)
    monkeypatch.delenv(IPC_SOCKET_ENV_VAR, raising=False)
    monkeypatch.delenv(FAKE_ENV_VAR, raising=False)
    assert isinstance(supervisor_do_servico(servico), Supervisor)
    monkeypatch.setenv(FAKE_ENV_VAR, "1")
    assert supervisor_do_servico(servico) is None
    monkeypatch.delenv(FAKE_ENV_VAR)
    monkeypatch.setenv(IPC_SOCKET_ENV_VAR, "outra-instancia.sock")
    assert supervisor_do_servico(servico) is None


# -- o instalador: os três lugares e a origem ------------------------------------


def test_remover_para_o_processo_e_deixa_os_tres_lugares_vazios(
    lar: Lugares, curto: Path
) -> None:
    _instalar_e_ligar(lar, curto, "fica")

    async def corrida() -> list[str]:
        supervisor = _supervisor(lar, procurar_bwrap=False, intervalo_s=0.05)
        await supervisor.iniciar()
        try:
            await _ate(lambda: _relato(lar) is not None)
            relato = _relato(lar)
            assert relato is not None
            restos: list[str] = await asyncio.to_thread(
                remover, "exemplo", lugares=lar, prazo=5.0)
            with pytest.raises(ProcessLookupError):
                os.kill(relato["pid"], 0)
            return restos
        finally:
            await supervisor.parar()

    assert asyncio.run(corrida()) == []
    assert not (lar.codigo / "exemplo").exists()
    assert not (lar.dados / "exemplo").exists()
    assert "exemplo" not in ler_registro(lar.registro)
    assert conferir_remocao("exemplo", lugares=lar) == []


def test_a_conferencia_da_remocao_ve_a_pasta_de_dados_que_ficou(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_e_ligar(lar, curto, "fica")
    (lar.dados / "exemplo").mkdir(parents=True)
    (lar.dados / "exemplo" / "algo.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(instalador, "_apagar_os_dados", lambda lg, mod_id: None)
    assert remover("exemplo", lugares=lar, prazo=0.1) == [str(lar.dados / "exemplo")]


def test_remover_o_que_nao_esta_instalado_e_recusado(lar: Lugares) -> None:
    with pytest.raises(InstalacaoRecusadaError, match="não está instalada"):
        remover("nada", lugares=lar)


def _git(pasta: Path, *args: str) -> str:
    feito = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
         "-c", "user.name=Time", "-c", "user.email=time@exemplo.invalid", *args],
        cwd=pasta, capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
    )
    return feito.stdout.strip()


def _chave(pasta: Path, nome: str) -> tuple[Path, str]:
    privada = pasta / nome
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", nome, "-f",
                    str(privada)], check=True, capture_output=True)
    publica = (pasta / f"{nome}.pub").read_text(encoding="utf-8").split()
    return privada, f"time@hefesto {publica[0]} {publica[1]}"


@pytest.fixture
def repositorio(curto: Path, lar: Lugares) -> tuple[Path, str]:
    """Um repositório local num caminho com o nome do time: o endereço não basta."""
    if shutil.which("ssh-keygen") is None:
        pytest.skip("sem ssh-keygen")
    origem = curto / "Hefesto-Team" / "hefesto-mod-exemplo"
    origem.mkdir(parents=True)
    _pasta_do_mod(origem.parent, "fica")
    for arquivo in (origem.parent / "fonte-exemplo").iterdir():
        shutil.move(str(arquivo), origem / arquivo.name)
    _git(origem, "init", "-q", "-b", "principal")
    _git(origem, "add", ".")
    _git(origem, "commit", "-q", "-m", "a primeira")
    privada, linha = _chave(curto, "chave-do-time")
    _git(origem, "-c", "gpg.format=ssh", "-c", f"user.signingkey={privada}",
         "tag", "-s", "v1", "-m", "assinada")
    _git(origem, "tag", "-a", "v1-sem-assinatura", "-m", "sem assinatura")
    _git(origem, "tag", "leve")
    return origem, linha


def test_a_tag_sem_assinatura_instala_como_comunidade(
    lar: Lugares, repositorio: tuple[Path, str]
) -> None:
    origem, chave_do_time = repositorio
    endereco = f"file://{origem}"
    for ref in ("v1-sem-assinatura", "leve", None):
        feito = instalar(endereco, ref=ref, lugares=lar, chaves=(chave_do_time,))
        assert feito.entrada.origem == "comunidade", ref
        assert feito.entrada.commit == _git(origem, "rev-parse", "HEAD")
        assert not (lar.codigo / "exemplo" / ".git").exists()


def test_a_tag_assinada_pela_chave_do_produto_instala_como_oficial(
    lar: Lugares, curto: Path, repositorio: tuple[Path, str]
) -> None:
    origem, chave_do_time = repositorio
    endereco = f"file://{origem}"
    feito = instalar(endereco, ref="v1", lugares=lar, chaves=(chave_do_time,))
    assert feito.entrada.origem == "oficial"
    _privada, chave_de_outro = _chave(curto, "chave-de-outro")
    feito = instalar(endereco, ref="v1", lugares=lar, chaves=(chave_de_outro,))
    assert feito.entrada.origem == "comunidade"
    feito = instalar(endereco, ref="v1", lugares=lar, chaves=())
    assert feito.entrada.origem == "comunidade"


def test_o_git_nunca_pergunta_senha(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vistos: list[dict[str, str]] = []
    original = subprocess.run

    def espiao(args: Any, **k: Any) -> Any:
        if isinstance(args, list) and args[:1] == ["git"]:
            vistos.append(dict(k.get("env") or {}))
        return original(args, **k)

    monkeypatch.setattr(subprocess, "run", espiao)
    with pytest.raises(InstalacaoRecusadaError, match="O git não baixou"):
        instalar(f"file://{curto}/nao-existe", lugares=lar)
    assert vistos and all(e.get("GIT_TERMINAL_PROMPT") == "0" for e in vistos)
    assert not list(lar.codigo.glob("exemplo"))
