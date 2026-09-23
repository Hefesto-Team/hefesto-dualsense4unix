"""O D-Bus do BlueZ tem UM dono — BLUEZ-UM-DONO-01 (23/09/2026).

Medido no estudo de 23/09: nove leitores falavam com o BlueZ, cada um com o
próprio subprocesso, quatro desembrulhos, três prazos, e ninguém assinava o
``ObjectManager``. A guarda contra a suíte estava em um executor de cinco — e a
política D-Bus desta máquina deixa qualquer uid local chamar qualquer método do
``org.bluez``, inclusive a suíte.

O QUE ESTA RÉGUA COBRA:

1. **o contrato do barramento:** um ``PropertiesChanged(Discovering=true)``
   muda a leitura da varredura sem subprocesso nenhum;
2. **a guarda na borda:** sob a suíte, toda escrita no BlueZ de verdade recusa,
   e o ``busctl`` do sistema nem responde à leitura;
3. **a trava:** toda escrita espera o motor que está com a trava do rádio — a
   exceção declarada é o ``StopDiscovery``;
4. **o diário:** a escrita que muda o rádio deixa uma linha no diário comum;
5. **a régua de dono:** um ``busctl`` ou um nome ``org.bluez`` escrito em
   ``src/`` fora do ``bluez_dbus.py`` reprova;
6. **o lugar (D3):** o dongle que troca de porta é percebido e dito.
"""

from __future__ import annotations

import ast
import contextlib
import io
import os
import re
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio, varredura_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as reconexao
from tests.unit import bluez_de_mentira as bm

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
DONO = SRC / "integrations" / "bluez_dbus.py"


@pytest.fixture()
def barramento() -> bm.BarramentoDeMentira:
    return bm.BarramentoDeMentira()


@pytest.fixture()
def vivo(barramento: bm.BarramentoDeMentira) -> bd.DonoVivo:
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    return dono


@pytest.fixture()
def sem_subprocesso(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Qualquer subprocesso aberto pelo dono vira uma anotação — e uma falha."""
    abertos: list[Any] = []

    def anotar(*args: Any, **kwargs: Any) -> Any:
        abertos.append(args)
        raise AssertionError("o dono abriu um subprocesso")

    monkeypatch.setattr(bd.subprocess, "run", anotar)
    return abertos


@pytest.fixture()
def trava_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "radio.lock"
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(caminho))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    return caminho


# ---------------------------------------------------------------------------
# 1. o contrato do barramento
# ---------------------------------------------------------------------------


def test_o_sinal_muda_a_leitura_sem_subprocesso_novo(
    vivo: bd.DonoVivo,
    barramento: bm.BarramentoDeMentira,
    sem_subprocesso: list[Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova da sprint: ``Discovering=true`` chega por sinal e a varredura o lê.

    MORDIDA: faça o ``_aplicar`` do dono ignorar o ``mudou`` — a segunda
    leitura continua dizendo que ninguém varre.
    """
    monkeypatch.setattr(bd, "_DONO", vivo)

    antes = varredura_do_radio.quem_esta_varrendo()
    assert antes.sei and antes.varrendo == frozenset()

    barramento.emitir(
        bd.Sinal("mudou", caminho=bm.HCI, interface=bd.ADAPTADOR, mudadas={"Discovering": True})
    )
    depois = varredura_do_radio.quem_esta_varrendo()

    assert depois.varrendo == frozenset({bm.ADAPTADOR})
    assert sem_subprocesso == []


def test_o_aparelho_que_entra_e_o_que_sai_mudam_a_arvore(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira
) -> None:
    novo = bm.no_de("aa:bb:cc:00:00:44")
    barramento.emitir(
        bd.Sinal("entrou", caminho=novo, propriedades={bd.APARELHO: {"Paired": False}})
    )
    assert novo in (vivo.caminhos() or ())

    barramento.emitir(bd.Sinal("saiu", caminho=novo, interfaces_que_sairam=(bd.APARELHO,)))
    assert novo not in (vivo.caminhos() or ())


def test_o_sinal_que_chega_durante_a_foto_nao_se_perde(
    barramento: bm.BarramentoDeMentira,
) -> None:
    """A foto é do instante em que o BlueZ respondeu; o sinal que chega enquanto
    ela viaja é MAIS NOVO que ela.

    MORDIDA: aplique o sinal direto na foto em vez de pôr na fila — a foto o
    sobrescreve e a leitura volta ao valor velho.
    """
    dono = bd.DonoVivo(barramento)

    def no_meio() -> None:
        barramento.emitir(
            bd.Sinal("mudou", caminho=bm.HCI, interface=bd.ADAPTADOR,
                     mudadas={"Discovering": True})
        )

    barramento.durante_a_foto = no_meio
    assert dono.ligar()
    assert dono.propriedade(bm.HCI, bd.ADAPTADOR, "Discovering") is True


def test_o_bluetoothd_que_sai_vira_nao_sei_e_o_que_volta_refotografa(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ausência é resposta: sem ``bluetoothd`` a árvore é ``None``, nunca vazia."""
    monkeypatch.setattr(bd, "_DONO", vivo)
    barramento.bluez_de_pe = False
    barramento.emitir(bd.Sinal("dono", dono_novo=""))

    assert vivo.caminhos() is None
    assert not varredura_do_radio.quem_esta_varrendo().sei

    barramento.bluez_de_pe = True
    barramento.emitir(bd.Sinal("dono", dono_novo=":1.99"))
    assert bm.esperar(lambda: vivo.caminhos() is not None)


def test_a_foto_que_falhou_com_o_bluez_de_pe_e_tirada_de_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um ``GetManagedObjects`` que estourou o prazo não cega o dono para sempre.

    Achado na conferência: o único gatilho de foto nova era o
    ``NameOwnerChanged``. Um ``bluetoothd`` lento no instante em que o daemon
    ligava o dono — o regime das quedas de 22/09 — deixava a árvore em "não sei"
    até o próximo reinício do serviço, e todo leitor do produto respondia
    "não deu" com o BlueZ de pé.

    MORDIDA: tire o ``_em_segundo_plano(self._refotografar_se_o_bluez_esta_la)``
    de ``DonoVivo.caminhos`` — a árvore nunca volta.
    """
    monkeypatch.setattr(bd, "REFOTOGRAFAR_S", 0.0)
    barramento = bm.BarramentoDeMentira()
    barramento.fotos_que_falham = 1
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()

    assert dono.caminhos() is None, "sem foto é 'não sei', nunca a árvore vazia"
    assert bm.esperar(lambda: dono.caminhos() is not None)
    assert bm.HCI in (dono.caminhos() or ())


def test_sem_dono_do_org_bluez_a_foto_nao_e_pedida(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem ``bluetoothd`` no barramento, pedir a foto ATIVARIA o serviço
    (``org.bluez.service``): quem o parou de propósito o veria voltar sozinho.
    Quem refotografa, então, é o ``NameOwnerChanged``.

    MORDIDA: troque o ``if self._barramento.dono_do_nome(SERVICO):`` de
    ``_refotografar_se_o_bluez_esta_la`` por ``if True:`` — o dono pede a foto
    ao nome sem dono.
    """
    monkeypatch.setattr(bd, "REFOTOGRAFAR_S", 0.0)
    barramento = bm.BarramentoDeMentira()
    barramento.bluez_de_pe = False
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    assert barramento.fotos == 1

    for _ in range(3):
        assert dono.caminhos() is None
    time.sleep(0.2)
    assert barramento.fotos == 1


# ---------------------------------------------------------------------------
# 2. a guarda na borda
# ---------------------------------------------------------------------------

_ARGUMENTOS_DE_ESCRITA: dict[str, tuple[Any, ...]] = {
    "chamar": (bm.no_de(bm.CONTROLE), bd.APARELHO, "Connect"),
    "escrever_propriedade": (bm.HCI, bd.ADAPTADOR, "Alias", "s", "x"),
    "escrever_alias": (bm.HCI, "x"),
    "conectar": (bm.no_de(bm.CONTROLE),),
    "desconectar": (bm.no_de(bm.CONTROLE),),
    "remover_aparelho": (bm.no_de(bm.CONTROLE),),
    "confiar": (bm.no_de(bm.CONTROLE),),
    "parear": (bm.no_de(bm.CONTROLE),),
    "comecar_busca": (bm.HCI,),
    "parar_busca": (bm.HCI,),
}


def test_toda_escrita_tem_argumento_de_prova() -> None:
    """Uma escrita nova sem linha aqui é uma escrita que a guarda não mede."""
    assert set(_ARGUMENTOS_DE_ESCRITA) == set(bd.ESCRITAS)


def _publicos(classe: type) -> set[str]:
    return {
        nome
        for nome in dir(classe)
        if not nome.startswith("_") and callable(getattr(classe, nome))
    }


def _sem_classificacao(*classes: type) -> set[str]:
    conhecidos = set(bd.ESCRITAS) | set(bd.LEITURAS) | set(bd.CICLO)
    return set().union(*(_publicos(c) for c in classes)) - conhecidos


def test_todo_metodo_publico_do_dono_e_leitura_escrita_ou_ciclo() -> None:
    """Um método público novo que escreve e não está em ``ESCRITAS`` escaparia
    da guarda. MORDIDA embutida: uma subclasse com um método a mais reprova."""
    assert _sem_classificacao(bd.LeitorDoBluez, bd.PeloBusctl, bd.DonoVivo) == set()

    class ComUmAMais(bd.DonoVivo):
        def religar_tudo(self) -> None:  # o método que ninguém classificou
            return None

    assert _sem_classificacao(ComUmAMais) == {"religar_tudo"}


@pytest.mark.parametrize("nome", bd.ESCRITAS)
def test_sob_a_suite_toda_escrita_no_bluez_de_verdade_recusa(
    nome: str, sem_subprocesso: list[Any]
) -> None:
    """A borda: o BlueZ do SISTEMA (pelo Gio ou pelo ``busctl``) recusa tudo.

    MORDIDA: tire o ``_recusa()`` de ``_na_borda`` — as escritas chegam ao
    barramento de mentira marcado como sistema, e ao ``busctl`` de verdade.
    """
    sistema = bm.BarramentoDeMentira(e_do_sistema=True)
    vivo = bd.DonoVivo(sistema)
    assert vivo.ligar()
    for leitor in (vivo, bd.PeloBusctl()):
        escrita = getattr(leitor, nome)(*_ARGUMENTOS_DE_ESCRITA[nome])
        if nome in ("comecar_busca", "parar_busca") and isinstance(leitor, bd.PeloBusctl):
            # Pelo busctl a busca nem existe: um processo que sai a derruba.
            assert escrita.erro == bd.SEM_BARRAMENTO
            continue
        assert escrita.erro == bd.RECUSA_DA_SUITE, (nome, type(leitor).__name__, escrita)
    assert sistema.chamadas == [] and sistema.escritas == []
    assert sem_subprocesso == []


def test_a_guarda_recusa_o_sistema_e_nao_o_barramento_de_mentira(
    barramento: bm.BarramentoDeMentira, vivo: bd.DonoVivo, trava_de_mentira: Path
) -> None:
    """A guarda recusa o SISTEMA, não o dublê — senão nenhuma régua exercitaria a lógica."""
    assert vivo.desconectar(bm.no_de(bm.CONTROLE)).feita
    assert barramento.metodos() == ["Disconnect"]


def test_sob_a_suite_o_busctl_do_sistema_nao_responde_nem_a_leitura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma régua que lê o barramento DELA mede a máquina, não o produto.

    O ``busctl`` de mentira posto na frente do ``PATH`` responde; o do sistema
    não. MORDIDA: tire o ``_e_o_do_sistema`` de ``bd.busctl`` — sem o de
    mentira, a árvore da mesa dela volta.
    """
    if bd.shutil.which(bd.FERRAMENTA, path=bd._PATH_DO_SISTEMA) is not None:
        monkeypatch.setenv("PATH", bd._PATH_DO_SISTEMA)
        assert bd.busctl(["tree", bd.SERVICO, "--list"]) is None

    pasta = tmp_path / "bin"
    pasta.mkdir()
    falso = pasta / bd.FERRAMENTA
    falso.write_text("#!/usr/bin/env bash\necho /org/bluez/hci9\n", encoding="utf-8")
    falso.chmod(0o755)
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{bd._PATH_DO_SISTEMA}")
    assert bd.busctl(["tree", bd.SERVICO, "--list"]) == "/org/bluez/hci9\n"
    assert bd.busctl(["call", bd.SERVICO, bm.HCI, bd.ADAPTADOR, "StartDiscovery"]) is None


def test_o_busctl_so_escreve_de_dentro_da_borda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trava_de_mentira: Path
) -> None:
    """Um executor novo que chamasse ``bd.busctl(["call", …])`` direto pularia a
    trava e o diário — e a régua de dono não o via, porque ele não escreve
    ``busctl`` nem ``org.bluez``: usa as constantes do dono.

    A suíte já recusa toda escrita pelo ``busctl``; para medir a BORDA, a régua
    desliga a guarda da suíte e deixa NO ``PATH`` SÓ um ``busctl`` de mentira,
    que anota o que recebe. O do sistema não é alcançável daqui.

    MORDIDA: tire a conferência de ``_POR_FIO.na_borda`` de ``bd.busctl`` — a
    chamada direta chega ao ``busctl``.
    """
    pasta = tmp_path / "bin"
    pasta.mkdir()
    anotado = tmp_path / "chamadas.txt"
    falso = pasta / bd.FERRAMENTA
    falso.write_text(f"#!/bin/sh\necho \"$*\" >> '{anotado}'\n", encoding="utf-8")
    falso.chmod(0o755)
    monkeypatch.setenv("PATH", str(pasta))
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    no = bm.no_de(bm.CONTROLE)

    assert bd.busctl(["call", bd.SERVICO, no, bd.APARELHO, "Disconnect"]) is None
    assert not anotado.exists(), "a escrita direta saiu sem trava e sem diário"

    escrita = bd.PeloBusctl().desconectar(no, quem="régua")
    assert escrita.feita, escrita
    assert anotado.read_text(encoding="utf-8").split() == [
        "call", bd.SERVICO, no, bd.APARELHO, "Disconnect"
    ]


def test_sob_a_suite_o_dono_do_processo_nunca_e_o_vivo_do_sistema() -> None:
    assert isinstance(bd.dono(), bd.PeloBusctl)
    assert bd.enderecos_pelo_kernel() is None
    assert bd.lugares_dos_adaptadores() == {}


def test_sob_a_suite_o_gio_nao_abre_o_barramento_de_sistema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda do ``busctl`` cobria a leitura; a do Gio faltava.

    Achado na conferência: ``bd.dono()`` nunca liga o vivo sob a suíte, mas um
    ``BarramentoGio()`` construído por uma régua abria o barramento de sistema e
    tirava a foto da mesa dela. O fio é trocado por um que não conecta nada, para
    a mordida não alcançar o barramento de verdade.

    MORDIDA: tire a guarda do começo de ``BarramentoGio.abrir`` — o fio nasce.
    """
    nasceram: list[str] = []

    def viver_de_mentira(self: bd.BarramentoGio) -> None:
        nasceram.append("fio")
        self._pronto.set()

    monkeypatch.setattr(bd.BarramentoGio, "_viver", viver_de_mentira)
    barramento = bd.BarramentoGio()

    assert barramento.abrir(espera=0.5) is False
    assert "suíte" in barramento.erro
    assert nasceram == [] and barramento._fio is None


def test_a_porta_de_fuga_e_declarada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(bd.RADIO_DE_VERDADE_NA_SUITE, "1")
    assert bd.a_suite_esta_rodando() is False


# ---------------------------------------------------------------------------
# 3. a trava
# ---------------------------------------------------------------------------


def _segurar_a_trava(segundos: float, pronto: threading.Event, soltou: list[float]) -> None:
    with diario_do_radio.trava_do_radio("watchdog-de-mentira", prazo_s=1.0):
        pronto.set()
        time.sleep(segundos)
        soltou.append(time.monotonic())


def test_a_escrita_espera_o_motor_que_esta_com_a_trava(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira, trava_de_mentira: Path
) -> None:
    """O watchdog com a trava, e o nosso ``Disconnect`` só sai quando ele solta.

    MORDIDA: chame ``fazer()`` sem ``na_trava`` em ``_na_borda`` — a chamada
    sai ANTES de o outro motor soltar.
    """
    pronto = threading.Event()
    soltou: list[float] = []
    outro = threading.Thread(target=_segurar_a_trava, args=(0.4, pronto, soltou))
    outro.start()
    assert pronto.wait(2)
    escrita = vivo.desconectar(bm.no_de(bm.CONTROLE), quem="régua")
    outro.join()

    assert escrita.feita
    ((_c, _i, metodo, _a, quando),) = barramento.chamadas
    assert metodo == "Disconnect"
    assert quando >= soltou[0], "o Disconnect saiu com a trava na mão de outro motor"
    esperas = [e for e in diario_do_radio.ler() if e["o_que"] == diario_do_radio.ESPEROU_A_TRAVA]
    assert esperas and esperas[-1]["quem"] == "régua"


def test_trava_que_nao_vem_no_prazo_e_recusa_sem_tocar_no_bluez(
    vivo: bd.DonoVivo,
    barramento: bm.BarramentoDeMentira,
    trava_de_mentira: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.1)
    pronto = threading.Event()
    outro = threading.Thread(target=_segurar_a_trava, args=(0.6, pronto, []))
    outro.start()
    assert pronto.wait(2)
    escrita = vivo.conectar(bm.no_de(bm.CONTROLE))
    outro.join()

    assert escrita.erro == bd.TRAVA_OCUPADA and escrita.nem_tentou
    assert barramento.chamadas == []


def test_o_stop_discovery_solta_o_radio_sem_esperar_ninguem(
    vivo: bd.DonoVivo,
    barramento: bm.BarramentoDeMentira,
    trava_de_mentira: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A exceção declarada: parar a busca nunca espera a trava.

    MORDIDA: tire ``StopDiscovery`` de ``METODOS_SEM_TRAVA`` — a busca fica de
    pé enquanto o outro motor segura a trava, e a escrita volta recusada.
    """
    assert frozenset({"StopDiscovery"}) == bd.METODOS_SEM_TRAVA
    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.1)
    pronto = threading.Event()
    outro = threading.Thread(target=_segurar_a_trava, args=(0.6, pronto, []))
    outro.start()
    assert pronto.wait(2)
    escrita = vivo.parar_busca(bm.HCI)
    outro.join()

    assert escrita.feita
    assert barramento.metodos() == ["StopDiscovery"]


def test_a_trava_e_reentrante_no_mesmo_fio(
    vivo: bd.DonoVivo,
    barramento: bm.BarramentoDeMentira,
    trava_de_mentira: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O motor que segura o gesto inteiro passa pela borda a cada escrita.

    MORDIDA: tire o atalho do ``dentro`` de ``na_trava`` — a escrita espera o
    próprio fio até o prazo e volta recusada.
    """
    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.2)
    with bd.na_trava("gesto-inteiro"):
        assert vivo.desconectar(bm.no_de(bm.CONTROLE)).feita
        assert vivo.conectar(bm.no_de(bm.CONTROLE)).feita
    assert barramento.metodos() == ["Disconnect", "Connect"]


@pytest.fixture()
def travas_pegas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Quem pegou a trava do rádio de verdade — o atalho reentrante não conta."""
    pegas: list[str] = []
    original = diario_do_radio.trava_do_radio

    @contextlib.contextmanager
    def contando(quem: str, **kwargs: Any) -> Iterator[float]:
        pegas.append(quem)
        with original(quem, **kwargs) as espera:
            yield espera

    monkeypatch.setattr(diario_do_radio, "trava_do_radio", contando)
    return pegas


def test_o_reconectar_segura_uma_trava_so_do_disconnect_ao_connect(
    trava_de_mentira: Path, travas_pegas: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decisão de quem coordena: o «Reconectar controles» entra na trava — e o
    gesto INTEIRO, para o watchdog não dar o Connect dele entre os nossos dois.

    MORDIDA: tire o ``with bluez_dbus.na_trava(QUEM)`` de ``reconectar`` — a
    borda pega a trava duas vezes, uma por escrita, e há uma fresta entre elas.
    """
    barramento = bm.BarramentoDeMentira()
    barramento.mesa[bm.no_de(bm.CONTROLE)][bd.APARELHO]["Connected"] = True
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    monkeypatch.setattr(bd, "_DONO", dono)

    desfecho = reconexao.reconectar(bm.CONTROLE)

    assert desfecho.estado == reconexao.ESTADO_VOLTOU
    assert barramento.metodos() == ["Disconnect", "Connect"]
    assert travas_pegas == [reconexao.QUEM]


def test_o_parear_pelo_dono_segura_uma_trava_so_do_pair_ao_trusted(
    vivo: bd.DonoVivo,
    barramento: bm.BarramentoDeMentira,
    trava_de_mentira: Path,
    travas_pegas: list[str],
) -> None:
    """MORDIDA: tire o ``na_trava`` de ``DonoVivo.parear`` — duas pegas, e o
    registro do agente nunca pede a trava (ele não aparece aqui)."""
    assert vivo.parear(bm.no_de(bm.CONTROLE), quem=gp.QUEM).feita
    assert barramento.metodos() == ["RegisterAgent", "Pair"]
    assert travas_pegas == [gp.QUEM]


class _ProcessoVivo:
    """A busca da ponte, de pé até alguém fechá-la."""

    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO("")
        self._vivo = True

    def poll(self) -> int | None:
        return None if self._vivo else 0

    def terminate(self) -> None:
        self._vivo = False

    kill = terminate

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_o_parear_pela_ponte_espera_a_trava(
    trava_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O piso também entra na fila: a ponte root não pareia no meio de outro motor.

    MORDIDA: tire o ``na_trava`` do ``parear`` da ponte em ``JanelaDeBusca`` —
    a ponte é chamada com a trava na mão de outro motor.
    """
    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.1)
    corridas: list[Any] = []

    def correr(argumentos: Any) -> tuple[int, str]:
        corridas.append(argumentos)
        return 0, ""

    janela = gp.JanelaDeBusca(bm.ADAPTADOR, 5, abrir=lambda _a: _ProcessoVivo(), correr=correr)
    assert not janela.pelo_dono
    assert janela.abrir_a_janela() == ""
    pronto = threading.Event()
    outro = threading.Thread(target=_segurar_a_trava, args=(0.6, pronto, []))
    outro.start()
    assert pronto.wait(2)
    desfecho = janela.parear(bm.CONTROLE)
    outro.join()
    janela.fechar()

    assert desfecho.estado == gp.ESTADO_NAO_DEU
    assert corridas == []


# ---------------------------------------------------------------------------
# 4. o diário
# ---------------------------------------------------------------------------


def test_a_escrita_que_muda_o_radio_vai_ao_diario_e_o_nome_nao(
    vivo: bd.DonoVivo, trava_de_mentira: Path
) -> None:
    vivo.desconectar(bm.no_de(bm.CONTROLE), quem="reconectar")
    vivo.escrever_alias(bm.HCI, "Sofá")

    linhas = [e for e in diario_do_radio.ler() if e["o_que"] == bd.ESCREVEU_NO_BLUEZ]
    assert len(linhas) == 1, linhas
    (linha,) = linhas
    assert linha["quem"] == "reconectar"
    assert linha["chamada"] == "Disconnect"
    assert linha["controle"] == bm.CONTROLE
    assert linha["hci"] == "hci9"
    assert linha["depois"]["feita"] is True


# ---------------------------------------------------------------------------
# 5. a régua de dono
# ---------------------------------------------------------------------------

#: Os programas que falam com o BlueZ por linha de comando.
_FERRAMENTAS = frozenset({"busctl", "bluetoothctl", "gdbus", "dbus-send"})

#: Um nome D-Bus do BlueZ: o serviço ou uma interface dele.
_NOME_DO_BLUEZ = re.compile(r"org\.bluez(\.[A-Za-z0-9_]+)*")


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corpo = no.body
            primeiro = corpo[0] if corpo else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                ids.add(id(primeiro.value))
    return ids


def segundos_donos(fonte: str) -> list[tuple[int, str]]:
    """Os literais que falam com o BlueZ num arquivo. Docstring e comentário não
    contam — um aviso que descreve o padrão não é o padrão."""
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    achados: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str) or id(no) in docs:
            continue
        valor = no.value.strip()
        if valor in _FERRAMENTAS or _NOME_DO_BLUEZ.fullmatch(valor):
            achados.append((no.lineno, valor))
    return achados


def test_a_regua_de_dono_morde_um_executor_novo() -> None:
    """MORDIDA embutida: um executor novo, escrito como os nove de antes, reprova."""
    novo = (
        "import subprocess\n"
        "def espiar(caminho):\n"
        "    '''Lê o org.bluez pelo busctl — isto é docstring e não conta.'''\n"
        "    return subprocess.run(['busctl', 'get-property', 'org.bluez', caminho,\n"
        "                           'org.bluez.Device1', 'Connected'])\n"
    )
    assert [v for _l, v in segundos_donos(novo)] == [
        "busctl", "org.bluez", "org.bluez.Device1"
    ]


def test_ninguem_fala_com_o_bluez_fora_do_dono() -> None:
    """Um ``busctl`` ou um ``org.bluez`` em ``src/`` fora de ``bluez_dbus.py`` reprova.

    MORDIDA medida: devolver o ``["busctl", "tree", "org.bluez", "--list"]`` a
    ``conexao_zumbi.enderecos_que_o_bluez_conhece`` reprova esta régua.
    """
    fora: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == DONO:
            continue
        for linha, valor in segundos_donos(arquivo.read_text(encoding="utf-8")):
            fora.append(f"{arquivo.relative_to(RAIZ)}:{linha}: {valor!r}")
    assert fora == [], "segundo dono do BlueZ:\n" + "\n".join(fora)


def test_o_dono_tem_os_nomes_que_a_regua_procura() -> None:
    """Sem isto, a régua acima passaria sobre um dono que não os tem."""
    assert {v for _l, v in segundos_donos(DONO.read_text(encoding="utf-8"))} >= {
        "busctl", "org.bluez", "org.bluez.Adapter1", "org.bluez.Device1", "org.bluez.Agent1",
    }


# ---------------------------------------------------------------------------
# 6. o endereço e o lugar (D3)
# ---------------------------------------------------------------------------


class _KernelDeMentira:
    """O ``LeitorDoKernel`` do AR-MEDIDO-01, com o que o ioctl responderia."""

    class _Leitura:
        def __init__(self, endereco: str) -> None:
            self.endereco = endereco

    def __init__(self, enderecos: dict[int, str]) -> None:
        self._enderecos = enderecos

    def adaptadores(self) -> list[int]:
        return sorted(self._enderecos)

    def ler(self, numero: int) -> Any:
        return self._Leitura(self._enderecos[numero])


def test_o_endereco_do_adaptador_vem_do_kernel() -> None:
    """O texto é do terceiro, o número é do kernel — e o kernel ganha."""
    kernel = bd.enderecos_pelo_kernel(_KernelDeMentira({9: "aa:bb:cc:00:00:99"}))
    assert kernel == {"hci9": "aa:bb:cc:00:00:99"}

    barramento = bm.BarramentoDeMentira()
    dono = bd.DonoVivo(barramento, kernel=lambda: kernel)
    assert dono.ligar()
    assert dono.endereco_do_adaptador(bm.HCI) == "aa:bb:cc:00:00:99"

    sem_kernel = bd.DonoVivo(bm.BarramentoDeMentira())
    assert sem_kernel.ligar()
    assert sem_kernel.endereco_do_adaptador(bm.HCI) == bm.ADAPTADOR


def test_o_lugar_e_o_caminho_pci_e_as_portas() -> None:
    assert bd.lugar_de("0000:0c:00.3", "1.1.4") == "pci-0000:0c:00.3-usb-0:1.1.4"
    assert bd.lugar_de("0000:0c:00.3", "") == "pci-0000:0c:00.3"
    assert bd.lugar_de("", "1.4") == ""


def test_o_lugar_sai_no_adaptador_do_dono() -> None:
    dono = bd.DonoVivo(bm.BarramentoDeMentira(), lugares=lambda: {"hci9": "pci-x-usb-0:1.4"})
    assert dono.ligar()
    (adaptador,) = dono.adaptadores() or ()
    assert adaptador.lugar == "pci-x-usb-0:1.4"
    assert adaptador.endereco == bm.ADAPTADOR


def test_trocar_o_dongle_de_porta_e_percebido_e_dito(
    tmp_path: Path, trava_de_mentira: Path
) -> None:
    """D3: o nome segue o LUGAR. Mudar de porta é percebido e vai ao diário.

    MORDIDA: faça ``perceber_as_mudancas`` devolver ``()`` — a mudança passa calada.
    """
    lugares = {"hci9": "pci-0000:0c:00.3-usb-0:1.2"}
    dono = bd.DonoVivo(bm.BarramentoDeMentira(), lugares=lambda: dict(lugares))
    assert dono.ligar()
    memoria = tmp_path / "lugares.json"

    assert dono.conferir_os_lugares(memoria=memoria) == ()
    lugares["hci9"] = "pci-0000:0c:00.3-usb-0:1.4"
    (mudanca,) = dono.conferir_os_lugares(memoria=memoria)

    assert mudanca.tipo == "mudou_de_porta"
    assert mudanca.lugar_antigo == "pci-0000:0c:00.3-usb-0:1.2"
    linhas = [e for e in diario_do_radio.ler() if e["o_que"] == bd.MUDOU_DE_LUGAR]
    assert linhas and linhas[-1]["frase"] == "Este adaptador mudou de porta."
    assert dono.conferir_os_lugares(memoria=memoria) == (), "a mesma mudança dita duas vezes"


def test_dongle_trocado_na_mesma_porta_e_outra_frase() -> None:
    (mudanca,) = bd.perceber_as_mudancas({"p1": "aa:bb:cc:00:00:01"}, {"p1": "aa:bb:cc:00:00:02"})
    assert mudanca.tipo == "trocado"
    assert mudanca.frase == "O adaptador desta porta foi trocado."
    assert bd.perceber_as_mudancas({}, {"p1": "aa:bb:cc:00:00:01"}) == ()


# ---------------------------------------------------------------------------
# o desembrulho — um só
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bruto", "valor"),
    [
        ('{"type":"s","data":"Nintendo MeowSystem"}', "Nintendo MeowSystem"),
        ('s "Nintendo MeowSystem"', "Nintendo MeowSystem"),
        ('{"type":"b","data":true}', True),
        ("b false", False),
        ("u 9480", 9480),
        ("", None),
        (None, None),
    ],
)
def test_o_desembrulho_nao_mutila_nome_com_espaco(bruto: str | None, valor: Any) -> None:
    assert bd.desembrulhar(bruto) == valor
