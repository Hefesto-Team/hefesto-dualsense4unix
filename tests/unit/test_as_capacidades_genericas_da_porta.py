"""As capacidades genéricas da porta que a janela no arranjo C pede (22/10/2026).

Cada uma é aditiva (a API segue ``>=2,<3``) e nenhuma sabe que extensão a usa:

1. ``acessorios.estado.aparelhos[]`` como ``{nome, tipo, estado, bateria, forca}``;
2. a permissão ``publicar:acessorios.estado``, sem ``ler:acessorios.gesto`` (os gestos do PS
   ficam os de sempre);
3. ``acessorios.estado.conexoes[]`` como ``{id, tipo, transporte, estado, motivo}``;
4. a opção ``endereco``: o IP e a porta num campo só;
5. a opção ``por_botao``: ``{botão: forma}``, com as formas ``[[força, s], …]`` declaradas;
6. o tópico ``botoes`` de TODO controle: ``button.down {uniq, jogador, botao}``, cabo e BT;
7. o ``agora`` com as conexões e os aparelhos;
8. ``parar_tudo`` chega como ``extensao.parar``, sem ``ler:acessorios.gesto``.

A nona (a aba Conexões) é da interface e mora em ``test_a_janela_no_arranjo_c``.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems.poll import evdev_buttons_once
from hefesto_dualsense4unix.mods import opcoes
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError
from hefesto_dualsense4unix.mods.manifesto import (
    BOTOES_DO_POR_BOTAO,
    Manifesto,
    Opcao,
    endereco_valido,
)
from hefesto_dualsense4unix.mods.porta import (
    EVENTO_DO_PARAR,
    Porta,
    RecusaError,
    botoes_de_todo_controle_no_servico,
    estado_dos_acessorios,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    P1,
    _Extensao,
    curto,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    TRANSPORTES,
    UNIQS,
    config_isolado,
)
from tests.unit.test_os_atalhos_na_espera import (  # noqa: F401
    MATRIZ,
    kernel,
    montar_atalhos,
)

GESTO = "ler:acessorios.gesto"
CONEXOES = "conexoes"  # (noqa-acento)
ESTADO = "publicar:acessorios.estado"
APARELHO = {"nome": "Motor", "tipo": "vibrador", "estado": "ligado", "bateria": 80, "forca": 0.5}
CONEXAO = {"id": "cabo", "tipo": "Adaptador", "transporte": "usb", "estado": "procurando",
           "motivo": "Sem o adaptador no cabo"}


def _manifesto(**extra: Any) -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "api": ">=2,<3",
        "versao": "1.0",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["tema"], "tema": {}, **extra,
    })


async def _porta(pasta: pathlib.Path, bus: EventBus, permissoes: list[str]) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    porta = Porta(pasta / "mods.sock", bus, escritor=escritor,
                  o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1)
    await porta.iniciar()
    porta.registrar("ficha", "exemplo", os.getpid(), permissoes)
    return porta


async def _entrar(pasta: pathlib.Path, topicos: list[str] | None = None) -> _Extensao:
    ext = _Extensao(pasta / "mods.sock")
    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": "ficha"})
    if topicos:
        assinou = await asyncio.to_thread(ext.pedir, "eventos.assinar", {"topicos": topicos})
        assert "result" in assinou, assinou
    return ext


async def _esperar(condicao: Any) -> bool:
    for _ in range(100):
        if condicao():
            return True
        await asyncio.sleep(0.02)
    return False


def test_1_o_aparelho_e_um_objeto_e_o_texto_solto_e_so_o_nome() -> None:
    estado = estado_dos_acessorios("x", {"aparelhos": [APARELHO, "Outro"]})
    assert estado["aparelhos"] == [
        APARELHO, {"nome": "Outro", "tipo": None, "estado": "ligado", "bateria": None,
                   "forca": None}]
    for torto in ({**APARELHO, "bateria": 101}, {**APARELHO, "forca": 1.5},
                  {**APARELHO, "estado": "dormindo"}, {**APARELHO, "nome": " "}, 7):
        with pytest.raises(RecusaError):
            estado_dos_acessorios("x", {"aparelhos": [torto]})


def test_3_a_conexao_diz_o_transporte_o_estado_e_o_motivo() -> None:
    estado = estado_dos_acessorios("x", {CONEXOES: [CONEXAO, {**CONEXAO, "motivo": ""}]})
    assert estado[CONEXOES][0] == CONEXAO
    assert estado[CONEXOES][1]["motivo"] is None, "o motivo vazio é nenhum motivo"
    for torto in ({**CONEXAO, "transporte": "pombo"}, {**CONEXAO, "id": ""},
                  {**CONEXAO, "estado": "talvez"}, ["cabo"]):
        with pytest.raises(RecusaError):
            estado_dos_acessorios("x", {CONEXOES: [torto]})
    assert estado_dos_acessorios("x", {})[CONEXOES] == []


def test_2_o_estado_sem_o_gesto_se_guarda_e_nao_vai_ao_barramento(curto) -> None:  # noqa: F811
    async def corrida() -> None:
        bus = EventBus()
        porta = await _porta(curto, bus, [ESTADO])
        ext = await _entrar(curto)
        try:
            ok = await asyncio.to_thread(ext.pedir, "acessorios.estado", {
                "ligado": True, "aparelhos": [APARELHO], CONEXOES: [CONEXAO]})
            assert ok.get("result") == {"recebido": True}, ok
            assert porta.agora_de("exemplo")["aparelhos"] == [APARELHO]
            assert porta.agora_de("exemplo")[CONEXOES] == [CONEXAO]
            assert bus.ultimo(EventTopic.ACESSORIOS_ESTADO) is None, (
                "o estado de quem só mostra foi ao barramento e ligaria os gestos do PS")
        finally:
            ext.fechar()
        assert await _esperar(lambda: porta.agora_de("exemplo")["ligado"] is False)
        assert bus.ultimo(EventTopic.ACESSORIOS_ESTADO) is None, "a queda publicou o vazio"
        await porta.parar()

    asyncio.run(corrida())


def test_2_sem_nenhuma_das_duas_permissoes_o_estado_e_recusado(curto) -> None:  # noqa: F811
    async def corrida() -> dict[str, Any]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        ext = await _entrar(curto)
        try:
            return await asyncio.to_thread(ext.pedir, "acessorios.estado", {"ligado": True})
        finally:
            ext.fechar()
            await porta.parar()

    recusa = asyncio.run(corrida())
    assert recusa["error"]["message"] == (
        "falta a permissão publicar:acessorios.estado ou ler:acessorios.gesto")


def test_2_com_o_gesto_o_estado_segue_indo_ao_barramento(curto) -> None:  # noqa: F811
    async def corrida() -> Any:
        bus = EventBus()
        porta = await _porta(curto, bus, [GESTO])
        ext = await _entrar(curto)
        try:
            await asyncio.to_thread(ext.pedir, "acessorios.estado",
                                    {"ligado": True, "aparelhos": ["Motor"]})
            return bus.ultimo(EventTopic.ACESSORIOS_ESTADO)
        finally:
            ext.fechar()
            await porta.parar()

    estado = asyncio.run(corrida())
    assert estado is not None and estado["aparelhos"][0]["nome"] == "Motor"


def test_2_a_permissao_tem_a_frase_que_a_tela_mostra() -> None:
    from hefesto_dualsense4unix.mods.manifesto import o_que_a_permissao_deixa, permissao_valida

    assert permissao_valida(ESTADO)
    assert o_que_a_permissao_deixa(ESTADO) != ESTADO


def test_4_o_endereco_e_o_ip_e_a_porta_num_campo_so() -> None:
    opcao = Opcao(id="onde", rotulo="Onde", tipo="endereco", padrao="192.168.0.40:34567")
    assert opcoes.padrao_de(opcao) == "192.168.0.40:34567"
    assert opcoes.validar(opcao, " meu-pc.local:80 ") == "meu-pc.local:80"
    assert opcoes.validar(opcao, "[::1]:9") == "[::1]:9"
    assert opcoes.validar(opcao, "") == "", "o vazio é o endereço ainda não escolhido"
    for torto in ("192.168.0.40", "192.168.0.300:80", "a:0", "a:70000", "um nome:80", 80):
        with pytest.raises(InstalacaoRecusadaError):
            opcoes.validar(opcao, torto)
    assert endereco_valido("10.0.0.1:1") == ("10.0.0.1", 1)
    with pytest.raises(ValueError):
        Opcao(id="onde", rotulo="Onde", tipo="endereco", padrao="sem-porta")


FORMAS = {"Nenhum": [], "Curto": [[1.0, 0.2]], "Duplo": [[1.0, 0.1], [0.0, 0.1], [1.0, 0.1]]}


def test_5_o_por_botao_da_a_forma_de_cada_botao() -> None:
    opcao = Opcao(id="toques", rotulo="Toques", tipo="por_botao", formas=FORMAS,
                  padrao={"cross": "Curto"})
    padrao = opcoes.padrao_de(opcao)
    assert set(padrao) == set(BOTOES_DO_POR_BOTAO) and "ps" not in padrao
    assert padrao["cross"] == "Curto" and padrao["circle"] == "Nenhum", "a primeira forma"
    mudado = opcoes.validar(opcao, {"l1": "Duplo"})
    assert mudado["l1"] == "Duplo" and mudado["cross"] == "Curto", "o que falta é o padrão"
    for torto in ({"l1": "Longo"}, {"ps": "Curto"}, ["Curto"], {"l1": 3}):
        with pytest.raises(InstalacaoRecusadaError):
            opcoes.validar(opcao, torto)
    so_dois = Opcao(id="t", rotulo="T", tipo="por_botao", formas=FORMAS, botoes=["r1", "l1"])
    assert list(opcoes.padrao_de(so_dois)) == ["r1", "l1"]


@pytest.mark.parametrize("torto", [
    {"formas": {}},
    {"formas": {"Forte": [[2.0, 0.1]]}},
    {"formas": {"Lento": [[1.0, 0.0]]}},
    {"formas": FORMAS, "botoes": ["ps"]},
    {"formas": FORMAS, "padrao": {"cross": "Longo"}},  # (noqa-acento)
], ids=["sem-forma", "forca-fora", "passo-sem-tempo", "botao-da-casa", "padrao-sem-forma"])
def test_5_o_manifesto_recusa_o_por_botao_torto(torto: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        Opcao(id="t", rotulo="T", tipo="por_botao", **torto)


def test_5_formas_so_no_por_botao() -> None:
    with pytest.raises(ValueError):
        Opcao(id="t", rotulo="T", tipo="ligado", formas=FORMAS)


def test_7_o_agora_declara_as_conexoes_e_os_aparelhos_com_a_permissao_do_estado() -> None:
    manifesto = _manifesto(permissoes=[ESTADO], agora=[CONEXOES, "aparelhos"])
    assert manifesto.agora == [CONEXOES, "aparelhos"]
    assert _manifesto(permissoes=[GESTO], agora=[CONEXOES]).agora == [CONEXOES]
    with pytest.raises(ValueError):
        _manifesto(permissoes=["ler:botoes"], agora=[CONEXOES])


def test_8_o_parar_tudo_nao_pede_o_gesto() -> None:
    assert _manifesto(parar_tudo=True).parar_tudo is True


def test_8_o_parar_tudo_chega_como_extensao_parar_a_quem_nao_le_o_gesto(curto) -> None:  # noqa: F811
    """Prova da D-2210-O-PARAR-TUDO-E-UM-CAMPO-DO-MANIFESTO."""
    async def corrida() -> tuple[Any, Any]:
        bus = EventBus()
        porta = await _porta(curto, bus, [ESTADO])
        porta.registrar("ficha-gesto", "outra", os.getpid(), [GESTO])
        ext = await _entrar(curto)
        outra = _Extensao(curto / "mods.sock")
        await asyncio.to_thread(outra.pedir, "mod.ola", {"ficha": "ficha-gesto"})
        await asyncio.to_thread(outra.pedir, "eventos.assinar", {"topicos": ["acessorios.gesto"]})
        try:
            assert porta.parar_tudo("exemplo") is True
            chegou = await asyncio.to_thread(ext.esperar_evento, 2.0)
            vazou = await asyncio.to_thread(outra.esperar_evento, 0.4)
            return chegou, vazou
        finally:
            ext.fechar()
            outra.fechar()
            await porta.parar()

    chegou, vazou = asyncio.run(corrida())
    assert chegou is not None, "a extensão sem o gesto não recebeu o «Parar tudo»"
    assert chegou["params"]["topico"] == EVENTO_DO_PARAR == chegou["params"]["nome"]
    assert chegou["params"]["dados"] == {"mod": "exemplo"}
    assert vazou is None, f"o «Parar tudo» de uma extensão chegou à outra: {vazou}"


def test_8_quem_le_o_gesto_recebe_o_para_e_nao_o_evento(curto) -> None:  # noqa: F811
    async def corrida() -> list[Any]:
        porta = await _porta(curto, EventBus(), [GESTO])
        ext = await _entrar(curto, ["acessorios.gesto"])
        try:
            porta.parar_tudo("exemplo")
            chegaram = [await asyncio.to_thread(ext.esperar_evento, 1.0)]
            chegaram.append(await asyncio.to_thread(ext.esperar_evento, 0.4))
            return [c for c in chegaram if c is not None]
        finally:
            ext.fechar()
            await porta.parar()

    nomes = [c["params"]["nome"] for c in asyncio.run(corrida())]
    assert nomes == [EventTopic.ACESSORIOS_GESTO], nomes


def _drenar(ext: _Extensao) -> list[dict[str, Any]]:
    saida: list[dict[str, Any]] = []
    while (evento := ext.esperar_evento(0.3)) is not None:
        saida.append(evento["params"])
    return saida


@pytest.mark.usefixtures("config_isolado")
@MATRIZ
def test_6_o_aperto_de_cada_controle_chega_com_o_uniq_e_o_jogador_dele(
    curto, monkeypatch, kernel, quantos: int, transporte: str,  # noqa: F811
) -> None:
    """Cada controle da mesa aperta o ✕ e solta: a extensão recebe a borda com o dele.

    Prova da D-2210-O-TOQUE-DE-BOTAO-CHEGA-DE-TODO-CONTROLE.
    """
    bancada = montar_atalhos(monkeypatch, kernel, quantos, transporte)
    numeros = bancada.a_tela()

    def tique() -> None:
        bancada.tique()
        botoes = evdev_buttons_once(bancada.daemon)
        botoes_de_todo_controle_no_servico(bancada.daemon, botoes, botoes)

    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        bancada.daemon._mods_supervisor = SimpleNamespace(porta=porta)
        ext = await _entrar(curto, ["botoes"])
        try:
            tique()
            for uniq in UNIQS[:quantos]:
                bancada.mesa.apertados[uniq] = frozenset({"cross"})
                tique()
                del bancada.mesa.apertados[uniq]
                tique()
            return await asyncio.to_thread(_drenar, ext)
        finally:
            ext.fechar()
            await porta.parar()

    eventos = asyncio.run(corrida())
    for nome, apertado in ((EventTopic.BUTTON_DOWN, True), (EventTopic.BUTTON_UP, False)):
        visto = [(e["uniq"], e["dados"]["jogador"], e["dados"]["pressed"])
                 for e in eventos if e["nome"] == nome]
        esperado = [(uniq, numeros[uniq], apertado) for uniq in UNIQS[:quantos]]
        assert visto == esperado, f"{transporte} {nome}: {visto}"
    assert all(e["topico"] == "botoes" and e["dados"]["botao"] == "cross"
               and e["dados"]["button"] == "cross" for e in eventos)


def test_6_sem_quem_leia_os_botoes_o_tique_nao_le_controle_nenhum(curto, monkeypatch) -> None:  # noqa: F811
    lidos: list[Any] = []
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.poll.botoes_de_cada_controle",
                        lambda *a: lidos.append(a) or {})

    async def corrida() -> None:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        daemon = SimpleNamespace(_mods_supervisor=SimpleNamespace(porta=porta), controller=None)
        try:
            botoes_de_todo_controle_no_servico(daemon, frozenset({"cross"}), frozenset())
        finally:
            await porta.parar()

    asyncio.run(corrida())
    assert lidos == []


def test_6_o_controle_que_sai_solta_o_que_segurava(curto) -> None:  # noqa: F811
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        ext = await _entrar(curto, ["botoes"])
        try:
            porta.botoes_do_tique({"p2": frozenset()}, lambda u: 2)
            porta.botoes_do_tique({"p2": frozenset({"r1"})}, lambda u: 2)
            porta.botoes_do_tique({}, lambda u: None)
            return await asyncio.to_thread(_drenar, ext)
        finally:
            ext.fechar()
            await porta.parar()

    visto = [(e["nome"], e["uniq"], e["dados"]["botao"]) for e in asyncio.run(corrida())]
    assert visto == [(EventTopic.BUTTON_DOWN, "p2", "r1"), (EventTopic.BUTTON_UP, "p2", "r1")]


def test_6_o_leitor_que_chega_depois_nao_recebe_a_borda_de_um_aperto_velho(curto) -> None:  # noqa: F811
    """Sem leitor, o laço não chama a porta (``le_os_botoes``): o retrato do último tique fica.

    A extensão que reabre (a vigia depois do «Parar tudo», uma queda) não pode receber, no
    primeiro tique, o ``button.down`` de um botão que já estava apertado: seria um toque que
    ninguém deu. O primeiro tique dela só guarda.
    """
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus(), ["ler:botoes"])
        primeira = await _entrar(curto, ["botoes"])
        try:
            porta.botoes_do_tique({"p2": frozenset()}, lambda u: 2)
            porta.botoes_do_tique({"p2": frozenset({"r1"})}, lambda u: 2)
            assert [e["dados"]["botao"] for e in await asyncio.to_thread(_drenar, primeira)] \
                == ["r1"]
            primeira.fechar()
            assert await _esperar(lambda: not porta.le_os_botoes())
            porta.registrar("ficha-2", "exemplo", os.getpid(), ["ler:botoes"])
            segunda = _Extensao(curto / "mods.sock")
            await asyncio.to_thread(segunda.pedir, "mod.ola", {"ficha": "ficha-2"})
            await asyncio.to_thread(segunda.pedir, "eventos.assinar", {"topicos": ["botoes"]})
            try:
                porta.botoes_do_tique({"p2": frozenset({"cross"})}, lambda u: 2)
                return await asyncio.to_thread(_drenar, segunda)
            finally:
                segunda.fechar()
        finally:
            await porta.parar()

    assert asyncio.run(corrida()) == [], "a extensão nova recebeu a borda de um aperto velho"


@pytest.mark.asyncio
async def test_6_o_laco_do_servico_entrega_a_borda_do_posto_com_o_uniq(curto, monkeypatch) -> None:  # noqa: F811
    """O ``_poll_loop`` chama o tópico ``botoes`` a cada tique, com o estado do posto."""
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle.INPUT_GRACE_SEC", 0.0)
    monkeypatch.setattr("hefesto_dualsense4unix.daemon.lifecycle._a_fabrica_do_supervisor",
                        lambda: lambda daemon: None)
    estados = [ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
                               transport="bt", buttons_pressed=frozenset(b))
               for b in ((), (), ("square",), ("square",), (), ())]
    porta = await _porta(curto, EventBus(), ["ler:botoes"])
    ext = await _entrar(curto, ["botoes"])
    controle = FakeController(transport="bt", states=estados)
    daemon = Daemon(controller=controle, bus=EventBus(), store=StateStore(), config=DaemonConfig(
        poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False))
    daemon._mods_supervisor = SimpleNamespace(porta=porta, parar=_nada)
    rodando = asyncio.create_task(daemon.run())
    try:
        prazo = asyncio.get_running_loop().time() + 5.0
        while controle._idx < len(estados) and asyncio.get_running_loop().time() < prazo:
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.05)
    finally:
        daemon.stop()
        await rodando
    eventos = await asyncio.to_thread(_drenar, ext)
    ext.fechar()
    await porta.parar()
    visto = {(e["nome"], e["dados"]["botao"]) for e in eventos}
    assert (EventTopic.BUTTON_DOWN, "square") in visto, f"o laço não entregou o aperto: {eventos}"
    assert all(e["uniq"] == P1 for e in eventos), "sem o uniq, o posto entra pelo uniq_do_posto"


async def _nada() -> None:
    return None


def test_os_transportes_da_mesa_cobrem_cabo_e_radio() -> None:
    assert {"usb", "bt"} <= {via for vias in TRANSPORTES.values() for via in vias}
