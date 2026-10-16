"""A-VIBRACAO-DO-CONTROLE-CHEGA-AOS-ACESSORIOS-PELO-BUTTPLUG-01 — o lado do Hefesto.

O que o jogo pede de vibração a cada controle sai no barramento (``jogo.vibracao``),
com o ``uniq`` e o número do jogador de CADA um, e uma modificação com a permissão
``ler:jogo.vibracao`` o recebe pela porta, junto com ``jogo.fechou``. O perfil
efetivo e as marcas dele saem em ``perfil.trocou`` (permissão ``ler:perfil.marcas``) e
chegam também a quem assina depois.

O backend, o ``apply_game_rumble``, o barramento, a porta e o ``AutoSwitcher`` de
leitura são os do produto. Os quatro handles são dublês que anotam o que os motores
receberam (os mesmos do funil da força), e o relógio da vibração é injetado.

AS MORDIDAS (executadas na implementação, uma a uma, com o md5 conferido na volta):

* publicar só o ``pedido`` (sem o ``efetivo``) → ``test_o_par_fixado_tambem_publica`` e
  ``test_o_evento_do_jogador_2_sai_com_o_uniq_dele`` reprovam;
* tirar a publicação do ramo do par fixado → ``test_o_par_fixado_tambem_publica`` reprova;
* a batida sem o período (repete a cada tique) → ``test_a_batida_repete_a_cada_250_ms``
  reprova;
* tirar o teto de 60 por segundo → ``test_o_teto_de_60_por_segundo_nao_perde_o_ultimo_valor``
  reprova;
* a batida que não para no zero → ``test_a_batida_para_quando_o_valor_volta_a_zero`` reprova;
* o ``perfil.trocou`` sem ``marcas`` → ``test_o_perfil_adulto_publica_as_marcas`` reprova;
* o leitor da janela sem o anunciador (`_anunciando` devolve o leitor puro) →
  `test_as_duas_rotas_de_subida_ligam_o_anunciador` reprova nas duas rotas;
* o barramento sem guardar o estado → ``test_a_conexao_tardia_recebe_o_perfil_de_agora``
  reprova.

As da conferência (13/10/2026), na mesma forma:

* o fim da sessão que só zera a linha com o ``efetivo`` diferente de zero (o zero que o teto
  atrasou se perde) → ``test_o_zero_que_o_teto_atrasou_chega_no_fim_da_sessao`` reprova;
* ``jogo.fechou`` publicado antes do zero de quem vibrava →
  ``test_quem_vibrava_recebe_o_zero_antes_do_jogo_fechou`` reprova;
* o anunciador que só compara o nome do perfil →
  ``test_a_marca_nova_no_perfil_ativo_vira_troca`` reprova;
* a tabela criada sem a trava da criação →
  ``test_dois_controles_que_comecam_juntos_ficam_os_dois_na_tabela`` reprova.
"""
from __future__ import annotations

import asyncio
import json
import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import vibracao_do_jogo as vj
from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AnunciadorDoJogo
from hefesto_dualsense4unix.daemon.subsystems.rumble import fixar_par
from hefesto_dualsense4unix.mods.manifesto import (
    TOPICOS_DE_LEITURA,
    permissao_valida,
)
from hefesto_dualsense4unix.mods.porta import CODE_SEM_PERMISSAO, Porta
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from tests.unit.test_a_forca_da_vibracao_de_cada_controle_sai_de_um_funil_so import (
    UNIQS,
    _Mesa,
)

PEDIDO = 200
NUMERO_DO_JOGADOR = {u: i + 1 for i, u in enumerate(UNIQS)}


class _Relogio:
    """O relógio da vibração: só anda quando o teste manda."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def monotonic(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


class _Escuta:
    """Uma fila do barramento esvaziada de uma vez."""

    def __init__(self, bus: EventBus, topico: str) -> None:
        self.fila = bus.subscribe(topico)

    def tudo(self) -> list[Any]:
        saida: list[Any] = []
        while not self.fila.empty():
            saida.append(self.fila.get_nowait())
        return saida


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(vj, "time", SimpleNamespace(monotonic=r.monotonic))
    return r


@pytest.fixture
def mesa(tmp_path: Path, relogio: _Relogio) -> _Mesa:
    m = _Mesa(tmp_path)
    m.daemon.bus = EventBus()
    m.daemon.identity_registry = SimpleNamespace(
        numero_da_lampada=lambda uniq, assign=True: NUMERO_DO_JOGADOR.get(uniq)
    )
    return m


def _vibracao(mesa: _Mesa) -> _Escuta:
    return _Escuta(mesa.daemon.bus, EventTopic.JOGO_VIBRACAO)


# 1. Cada controle, com o endereço e o número DELE.

def test_o_evento_do_jogador_2_sai_com_o_uniq_dele(mesa: _Mesa) -> None:
    escuta = _vibracao(mesa)

    efetivo = gp.apply_game_rumble(mesa.daemon, 120, 200, target_uniq=UNIQS[1])

    eventos = escuta.tudo()
    assert len(eventos) == 1
    evento = eventos[0]
    assert evento["uniq"] == UNIQS[1], "o evento saiu com o endereço de outro controle"
    assert evento["jogador"] == 2
    assert evento["pedido"] == [120, 200]
    assert evento["efetivo"] == list(efetivo or ())
    assert efetivo is not None and efetivo != (0, 0), "o dublê não mediu nada"
    assert isinstance(evento["t"], float)


def test_cada_jogador_diz_o_seu(mesa: _Mesa) -> None:
    escuta = _vibracao(mesa)

    for u in UNIQS:
        gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=u)

    assert [(e["uniq"], e["jogador"]) for e in escuta.tudo()] == [
        (u, NUMERO_DO_JOGADOR[u]) for u in UNIQS
    ]


def test_sem_endereco_cada_controle_diz_uma_vez_so(mesa: _Mesa) -> None:
    """A mesa que se escreve por controle recorre a cada um: o evento não sai dobrado."""
    escuta = _vibracao(mesa)

    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO)

    uniqs = [e["uniq"] for e in escuta.tudo()]
    assert len(uniqs) == len(set(uniqs)), f"controle repetido no barramento: {uniqs}"
    assert uniqs, "o pedido sem endereço não publicou nada"


# 2. O par fixado vence, e o evento sai mesmo assim.

def test_o_par_fixado_tambem_publica(mesa: _Mesa) -> None:
    fixar_par(mesa.config, UNIQS[0], 90, 90, None, so_este=True)
    escuta = _vibracao(mesa)

    efetivo = gp.apply_game_rumble(mesa.daemon, 150, 250, target_uniq=UNIQS[0])

    assert efetivo is None, "o par fixado devia vencer o jogo"
    eventos = escuta.tudo()
    assert len(eventos) == 1, "o par fixado venceu e o evento sumiu"
    assert eventos[0]["uniq"] == UNIQS[0]
    assert eventos[0]["pedido"] == [150, 250]
    assert eventos[0]["efetivo"] == [0, 0], "o jogo não chegou aos motores: o efetivo é zero"


# 3. A batida e o zero.

def test_a_batida_repete_a_cada_250_ms(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _vibracao(mesa)
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    assert len(escuta.tudo()) == 1

    for _ in range(14):  # 14 tiques de 16 ms: 224 ms, antes do período
        relogio.avancar(0.016)
        vj.bater_a_vibracao(mesa.daemon)
    assert escuta.tudo() == [], "a batida saiu antes dos 250 ms"

    relogio.avancar(0.030)  # 254 ms
    vj.bater_a_vibracao(mesa.daemon)
    batida = escuta.tudo()
    assert len(batida) == 1
    assert batida[0]["uniq"] == UNIQS[1] and batida[0]["efetivo"] != [0, 0]

    relogio.avancar(0.100)
    vj.bater_a_vibracao(mesa.daemon)
    assert escuta.tudo() == [], "duas batidas dentro do mesmo período"
    relogio.avancar(0.160)
    vj.bater_a_vibracao(mesa.daemon)
    assert len(escuta.tudo()) == 1


def test_a_batida_para_quando_o_valor_volta_a_zero(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _vibracao(mesa)
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    relogio.avancar(0.020)
    gp.apply_game_rumble(mesa.daemon, 0, 0, target_uniq=UNIQS[1])

    eventos = escuta.tudo()
    assert [e["efetivo"] for e in eventos][-1] == [0, 0], "o zero não chegou a quem escuta"

    for _ in range(40):  # mais de 600 ms de tiques
        relogio.avancar(0.016)
        vj.bater_a_vibracao(mesa.daemon)
    assert escuta.tudo() == [], "a batida seguiu depois do zero"


def test_o_controle_parado_nao_publica_zero_atoa(mesa: _Mesa) -> None:
    escuta = _vibracao(mesa)

    gp.apply_game_rumble(mesa.daemon, 0, 0, target_uniq=UNIQS[1])

    assert escuta.tudo() == []


# 4. O teto de 60 por segundo por controle.

def test_o_teto_de_60_por_segundo_nao_perde_o_ultimo_valor(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    escuta = _vibracao(mesa)
    gp.apply_game_rumble(mesa.daemon, 100, 100, target_uniq=UNIQS[1])
    for valor in (150, 200, 0):  # três mudanças no mesmo instante
        relogio.avancar(0.002)
        gp.apply_game_rumble(mesa.daemon, valor, valor, target_uniq=UNIQS[1])
    assert len(escuta.tudo()) == 1, "mais de um evento dentro de 1/60 s no mesmo controle"

    relogio.avancar(0.020)
    vj.bater_a_vibracao(mesa.daemon)
    pendente = escuta.tudo()
    assert len(pendente) == 1, "o valor que o teto atrasou nunca saiu"
    assert pendente[0]["efetivo"] == [0, 0], "o último valor (o zero) foi perdido"


def test_o_teto_e_de_cada_controle(mesa: _Mesa) -> None:
    escuta = _vibracao(mesa)

    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[0])
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])

    assert len(escuta.tudo()) == 2, "o teto de um controle segurou o evento do outro"


def test_o_fim_da_sessao_do_pad_zera_quem_ainda_vibrava(mesa: _Mesa, relogio: _Relogio) -> None:
    escuta = _vibracao(mesa)
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[2])
    escuta.tudo()
    relogio.avancar(0.1)

    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[2])

    zero = escuta.tudo()
    assert len(zero) == 1 and zero[0]["uniq"] == UNIQS[2] and zero[0]["efetivo"] == [0, 0]
    relogio.avancar(0.5)
    vj.bater_a_vibracao(mesa.daemon)
    assert escuta.tudo() == []


def test_o_zero_que_o_teto_atrasou_chega_no_fim_da_sessao(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    """O jogo para o motor logo depois de ligá-lo e fecha o pad antes do tique seguinte."""
    escuta = _vibracao(mesa)
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[2])
    relogio.avancar(0.002)
    gp.apply_game_rumble(mesa.daemon, 0, 0, target_uniq=UNIQS[2])  # o teto segura
    dito = escuta.tudo()
    assert len(dito) == 1 and dito[0]["efetivo"] != [0, 0], "o teto não segurou o zero"

    gp.end_game_output_session(mesa.daemon, target_uniq=UNIQS[2])

    eventos = escuta.tudo()
    assert eventos and eventos[-1]["efetivo"] == [0, 0], (
        "o zero que o teto atrasou se perdeu com o fim da sessão"
    )
    assert eventos[-1]["uniq"] == UNIQS[2]


# 5. O jogo que fecha, o perfil que muda.

def test_o_jogo_que_fecha_vira_evento_e_cala_a_batida(
    mesa: _Mesa, relogio: _Relogio
) -> None:
    bus = mesa.daemon.bus
    appid: list[int | None] = [730]

    class _Daemon(SimpleNamespace):
        @property
        def appid_em_cena(self) -> int | None:
            return appid[0]

    daemon = _Daemon(bus=bus, controller=mesa.backend, config=mesa.config,
                     identity_registry=mesa.daemon.identity_registry)
    anunciador = AnunciadorDoJogo(bus, mesa.store, daemon)
    fechou = _Escuta(bus, EventTopic.JOGO_FECHOU)
    vibracao = _Escuta(bus, EventTopic.JOGO_VIBRACAO)
    gp.apply_game_rumble(daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    vibracao.tudo()

    anunciador.ver()
    assert fechou.tudo() == [], "o jogo ainda está em cena"
    appid[0] = None
    anunciador.ver()

    dito = fechou.tudo()
    assert len(dito) == 1 and dito[0]["appid"] == 730
    zero = vibracao.tudo()
    assert zero and zero[-1]["efetivo"] == [0, 0], "quem vibrava não recebeu o zero"
    relogio.avancar(1.0)
    vj.bater_a_vibracao(daemon)
    assert vibracao.tudo() == [], "a batida seguiu com o jogo fechado"
    anunciador.ver()
    assert fechou.tudo() == [], "o mesmo jogo fechou duas vezes"


def test_quem_vibrava_recebe_o_zero_antes_do_jogo_fechou(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    bus = mesa.daemon.bus
    appid: list[int | None] = [730]

    class _Daemon(SimpleNamespace):
        @property
        def appid_em_cena(self) -> int | None:
            return appid[0]

    daemon = _Daemon(bus=bus, controller=mesa.backend, config=mesa.config,
                     identity_registry=mesa.daemon.identity_registry)
    anunciador = AnunciadorDoJogo(bus, mesa.store, daemon)
    gp.apply_game_rumble(daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    anunciador.ver()
    ordem: list[str] = []
    publicar = bus.publish

    def _anotando(topico: str, carga: Any) -> None:
        ordem.append(topico)
        publicar(topico, carga)

    monkeypatch.setattr(bus, "publish", _anotando)
    appid[0] = None
    anunciador.ver()

    assert EventTopic.JOGO_FECHOU in ordem
    assert ordem.index(EventTopic.JOGO_VIBRACAO) < ordem.index(EventTopic.JOGO_FECHOU), (
        f"o jogo fechou antes do zero de quem vibrava: {ordem}"
    )


def test_a_marca_nova_no_perfil_ativo_vira_troca(mesa: _Mesa) -> None:
    """A pessoa marca «Adulto» no jogo que já está aberto: o estado guardado não fica velho."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    save_profile(Profile(name="noite", match=MatchAny(), priority=5))
    mesa.store.set_active_profile("noite")
    escuta = _Escuta(mesa.daemon.bus, EventTopic.PERFIL_TROCOU)
    anunciador = AnunciadorDoJogo(mesa.daemon.bus, mesa.store, SimpleNamespace())
    anunciador.ver()

    arquivo = profiles_dir() / "noite.json"
    antes = arquivo.stat().st_mtime_ns
    save_profile(Profile(name="noite", match=MatchAny(), priority=5, marcas=["adulto"]))
    os.utime(arquivo, ns=(antes + 10**9, antes + 10**9))  # o relógio do disco andou
    anunciador.ver()
    anunciador.ver()

    assert [(e["perfil"], e["marcas"]) for e in escuta.tudo()] == [
        ("noite", []),
        ("noite", ["adulto"]),
    ], "a marca nova no perfil ativo não chegou a quem acompanha"


def test_dois_controles_que_comecam_juntos_ficam_os_dois_na_tabela(mesa: _Mesa) -> None:
    """Cada pad virtual escreve na thread dele: a primeira vibração de dois ao mesmo tempo."""
    largada = threading.Barrier(len(UNIQS))

    class _Daemon(SimpleNamespace):
        def __setattr__(self, nome: str, valor: Any) -> None:
            if nome == "_vibracao_do_jogo_vista":
                time.sleep(0.02)  # alarga a janela entre olhar e gravar a tabela
            super().__setattr__(nome, valor)

    daemon = _Daemon(bus=mesa.daemon.bus, controller=mesa.backend, config=mesa.config,
                     identity_registry=mesa.daemon.identity_registry)

    def _vibrar(uniq: str) -> None:
        largada.wait()
        vj.dizer_a_vibracao(daemon, uniq, (PEDIDO, PEDIDO), (PEDIDO, PEDIDO))

    fios = [threading.Thread(target=_vibrar, args=(u,)) for u in UNIQS]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(5)

    vista = vj._vista_do(daemon, criar=False)
    assert vista is not None
    assert sorted(vista.linhas) == sorted(UNIQS), "um controle perdeu a batida na largada"


def test_o_perfil_adulto_publica_as_marcas(mesa: _Mesa) -> None:
    save_profile(Profile(name="noite", match=MatchAny(), priority=5, marcas=["adulto"]))
    save_profile(Profile(name="dia", match=MatchAny(), priority=5))
    mesa.store.set_active_profile("noite")
    escuta = _Escuta(mesa.daemon.bus, EventTopic.PERFIL_TROCOU)
    anunciador = AnunciadorDoJogo(mesa.daemon.bus, mesa.store, SimpleNamespace())

    anunciador.ver()
    mesa.store.set_active_profile("dia")
    anunciador.ver()
    anunciador.ver()

    eventos = escuta.tudo()
    assert [(e["perfil"], e["marcas"]) for e in eventos] == [("noite", ["adulto"]), ("dia", [])]


def test_a_conexao_tardia_recebe_o_perfil_de_agora(mesa: _Mesa) -> None:
    save_profile(Profile(name="noite", match=MatchAny(), priority=5, marcas=["adulto"]))
    mesa.store.set_active_profile("noite")
    bus = mesa.daemon.bus
    AnunciadorDoJogo(bus, mesa.store, SimpleNamespace()).ver()  # ninguém assinava ainda

    tardia = _Escuta(bus, EventTopic.PERFIL_TROCOU)

    assert [(e["perfil"], e["marcas"]) for e in tardia.tudo()] == [("noite", ["adulto"])]


def test_so_o_estado_e_guardado_o_evento_nao_se_repete(mesa: _Mesa) -> None:
    bus = mesa.daemon.bus
    gp.apply_game_rumble(mesa.daemon, PEDIDO, PEDIDO, target_uniq=UNIQS[1])
    bus.publish(EventTopic.JOGO_FECHOU, {"appid": 1})

    assert _vibracao(mesa).tudo() == []
    assert _Escuta(bus, EventTopic.JOGO_FECHOU).tudo() == []


def test_a_subida_liga_o_anunciador(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O leitor que o AutoSwitcher recebe da partida da lista deixa o anunciador olhar o serviço."""
    from hefesto_dualsense4unix.daemon.subsystems import autoswitch as sub
    from hefesto_dualsense4unix.profiles import autoswitch as perfis
    from hefesto_dualsense4unix.profiles import manager as gerente

    capturado: dict[str, Any] = {}

    class _Captura:
        def __init__(self, **kwargs: Any) -> None:
            capturado.update(kwargs)

        def disabled(self) -> bool:
            return True

    monkeypatch.setattr(sub, "_ensure_display_env", lambda: None)
    monkeypatch.setattr(sub, "_build_diag_window_reader", lambda store: lambda: {"wm_class": "x"})
    monkeypatch.setattr(perfis, "AutoSwitcher", _Captura)
    monkeypatch.setattr(gerente, "gerente_do_daemon", lambda *a, **k: object())
    mesa.store.set_active_profile("noite")
    daemon = mesa.daemon
    daemon.aplicar_a_exclusao = lambda **_: "aplicado"
    daemon.reverter_a_exclusao = lambda: "aplicado"
    escuta = _Escuta(daemon.bus, EventTopic.PERFIL_TROCOU)
    asyncio.run(sub.start_autoswitch(daemon))

    assert capturado["window_reader"]() == {"wm_class": "x"}

    assert [e["perfil"] for e in escuta.tudo()] == ["noite"], (
        "o leitor do autoswitch não deixou o anunciador olhar o serviço"
    )


# 6. A porta: a permissão e a entrega.

def test_as_permissoes_novas_existem_e_cada_uma_entrega_o_seu() -> None:
    assert permissao_valida("ler:jogo.vibracao") and permissao_valida("ler:perfil.marcas")
    assert TOPICOS_DE_LEITURA["jogo.vibracao"] == (
        EventTopic.JOGO_VIBRACAO,
        EventTopic.JOGO_FECHOU,
    )
    assert TOPICOS_DE_LEITURA["perfil.marcas"] == (EventTopic.PERFIL_TROCOU,)


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


def test_a_modificacao_recebe_a_vibracao_de_cada_jogador_pela_porta() -> None:
    async def corrida() -> None:
        with tempfile.TemporaryDirectory(prefix="vb") as pasta:
            curto = Path(pasta)
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(
                curto / "mods.sock", bus, escritor=escritor,
                o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: UNIQS[0],
            )
            await porta.iniciar()
            porta.registrar("ficha", "acessorios", os.getpid(), ["ler:jogo.vibracao"])
            cliente = _Cliente(curto / "mods.sock")
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
                recusa = await asyncio.to_thread(
                    cliente.pedir, "eventos.assinar", {"topicos": ["perfil.marcas"]})
                assert recusa["error"]["code"] == CODE_SEM_PERMISSAO
                assert recusa["error"]["message"] == "falta a permissão ler:perfil.marcas"
                aceita = await asyncio.to_thread(
                    cliente.pedir, "eventos.assinar", {"topicos": ["jogo.vibracao"]})
                assert aceita["result"] == {"assinados": ["jogo.vibracao"]}

                bus.publish(EventTopic.JOGO_VIBRACAO, {
                    "uniq": UNIQS[1], "jogador": 2, "pedido": [10, 20],
                    "efetivo": [10, 20], "t": 1.0,
                })
                bus.publish(EventTopic.JOGO_FECHOU, {"appid": 7, "t": 2.0})
                vibracao = await asyncio.wait_for(asyncio.to_thread(cliente.evento), 3)
                fechou = await asyncio.wait_for(asyncio.to_thread(cliente.evento), 3)
            finally:
                cliente.fechar()
                await porta.parar()
            assert vibracao["params"]["topico"] == "jogo.vibracao"
            assert vibracao["params"]["nome"] == EventTopic.JOGO_VIBRACAO
            assert vibracao["params"]["uniq"] == UNIQS[1], "o evento do jogador 2 saiu com o P1"
            assert vibracao["params"]["dados"]["jogador"] == 2
            assert fechou["params"]["nome"] == EventTopic.JOGO_FECHOU

    asyncio.run(corrida())
