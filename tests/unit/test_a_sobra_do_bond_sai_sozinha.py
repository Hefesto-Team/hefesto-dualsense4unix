"""A sobra do bond sai sozinha — A-SOBRA-DO-BOND-SAI-SOZINHA-01 (25/09/2026).

O defeito, medido na mesa dela: o P2 com chave de pareamento em dois
adaptadores desde 19/09, sobra de um mover feito pela metade. O ``doctor``
acusava todo dia (e acusava onze vizinhos de busca junto, a outra metade desta
sprint, em ``test_o_doctor_ve_o_bond_dobrado.py``), a memória dizia «a limpeza
é dela», e ninguém limpava. A pergunta dela: *«A interface do app não deveria
corrigir isso automaticamente?»*

A decisão (de quem coordena, que ela delega): o controle guarda UM host, e
quando o kernel o diz conectado pelo rádio num adaptador (``HID_PHYS``), ele
mesmo respondeu qual chave vale. A outra é sobra, e a central do rádio a
esquece como esquece a origem de um mover — ``RemoveDevice`` mais o verbo
``esquecer`` da ponte, com lápide —, UMA por volta, dentro da trava.

O mundo é o ``radio_de_mentira`` (controles que guardam UM host, com o
``DonoVivo`` de verdade por cima), e o ``HID_PHYS`` da matriz passa pelo leitor
de verdade (``radio_da_mesa.adaptador_por_uniq``) sobre um ``/sys`` de mentira,
com o vpad de cada máscara no meio.

O QUE ESTA RÉGUA COBRA:

1. conectado num adaptador, a chave do outro sai, com lápide e linha no diário;
2. desligado ou no cabo, nada sai — ele ainda não disse qual chave vale;
3. objeto de busca não é chave, e aparelho que não é controle não se toca;
4. uma por volta, idempotente, e nunca com um movimento «esperando»;
5. a mesa inteira: de 1 a 4 jogadores, no rádio, no cabo e misto, nas três máscaras;
6. o daemon liga a faxina, e o ``fechar()`` a para.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import adaptador_por_uniq
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO

CONTROLES = (VERMELHO, AZUL, VERDE, ROXO)
ADAPTADORES = (SALA, QUARTO, VARANDA)
#: A classe de um teclado (periférico, menor «teclado»): tem ``HID_PHYS``
#: como o controle, e pode guardar mais de um host.
CLASSE_DE_TECLADO = 0x002540


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> rm.RadioDeMentira:
    return rm.RadioDeMentira()


@pytest.fixture()
def ligar(mundo: rm.RadioDeMentira) -> Iterator[Callable[[], bd.DonoVivo]]:
    """O dono do BlueZ, aberto DEPOIS de a mesa estar montada: o ``DonoVivo``
    tira a foto no ``ligar()`` e depois só segue os sinais, e o ``pareado`` do
    rádio de mentira escreve na mesa sem sinal."""
    abertos: list[bd.DonoVivo] = []

    def abrir() -> bd.DonoVivo:
        vivo = bd.DonoVivo(mundo)
        assert vivo.ligar()
        abertos.append(vivo)
        return vivo

    yield abrir
    for vivo in abertos:
        vivo.fechar()


def _central(
    dono: bd.LeitorDoBluez,
    mundo: rm.RadioDeMentira,
    *,
    onde_esta: Callable[[str], str] | None = None,
    **extra: Any,
) -> cr.CentralDoRadio:
    relogio = rm.Relogio()
    return cr.CentralDoRadio(
        dono=dono,
        onde_esta=onde_esta or mundo.onde_esta,
        movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
        **extra,
    )


def _dobrado(
    mundo: rm.RadioDeMentira, controle: str, casa: str, velha: str, *, conectado: bool = True
) -> None:
    """O controle guarda ``casa``; a chave em ``velha`` é a sobra."""
    mundo.pareado(casa, controle, conectado=conectado)
    mundo.pareado(velha, controle, host=False)


# ---------------------------------------------------------------------------
# 1. conectado num adaptador, a chave do outro sai
# ---------------------------------------------------------------------------


def test_conectado_na_sala_a_chave_do_quarto_sai(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """O caso da mesa dela, com as três metades: o esquecer, a lápide, o diário.

    MORDIDA: tire o ``central.comecar_a_faxina()`` do arranque — a régua do
    daemon (§6) reprova; troque o ``sai != agora`` por ``sai == agora`` no
    ``sobras`` — a chave que o controle USA sai, e esta régua reprova.
    """
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    dono = ligar()
    central = _central(dono, mundo)

    assert central.sobras(dono) == ((QUARTO, VERMELHO, SALA),)
    assert central.esquecer_as_sobras() == (QUARTO, VERMELHO)

    assert mundo.objeto(QUARTO, VERMELHO) is None
    assert mundo.lapides == [(QUARTO, VERMELHO)]
    # A casa dele fica intacta, e ele segue conectado nela.
    casa = mundo.objeto(SALA, VERMELHO)
    assert casa is not None and casa["Paired"] is True
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA
    # Nada de janela, nada de parear: a faxina só esquece.
    assert mundo.metodos("StartDiscovery") == []
    assert mundo.metodos("Pair") == []
    linhas = [
        e for e in diario_do_radio.ler(caminhos=[diario]) if e["o_que"] == cr.ESQUECEU_A_SOBRA
    ]
    assert len(linhas) == 1
    assert (linhas[0]["controle"], linhas[0]["adaptador"]) == (VERMELHO, QUARTO)
    assert linhas[0]["depois"]["adaptador"] == SALA
    # Sem recado (R8): a linha não leva a frase que o sino da aba mostraria.
    assert "frase" not in linhas[0]
    # Nenhum movimento publicado: a tela não ganha um «chegou» que ela não pediu.
    assert central.movimentos() == ()


def test_a_segunda_volta_nao_escreve_nada(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    dono = ligar()
    central = _central(dono, mundo)

    assert central.esquecer_as_sobras() == (QUARTO, VERMELHO)
    removidos = len(mundo.metodos("RemoveDevice"))
    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == [(QUARTO, VERMELHO)]
    assert len(mundo.metodos("RemoveDevice")) == removidos


# ---------------------------------------------------------------------------
# 2. desligado ou no cabo, nada sai
# ---------------------------------------------------------------------------


def test_desligado_ele_ainda_nao_disse_qual_chave_vale(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """MORDIDA: trate o ``HID_PHYS`` vazio como «pode apagar qualquer uma» — as
    duas chaves de um controle desligado somem, e esta régua reprova."""
    _dobrado(mundo, VERMELHO, SALA, QUARTO, conectado=False)
    dono = ligar()
    central = _central(dono, mundo)

    assert central.sobras(dono) == ()
    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == []
    assert mundo.metodos("RemoveDevice") == []


def test_conectado_onde_o_bluez_nao_mostra_chave_nao_se_mexe(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """O kernel o diz na varanda, e as chaves estão na sala e no quarto: é estado
    que a central não entende, e ela não apaga nenhuma das duas."""
    _dobrado(mundo, VERMELHO, SALA, QUARTO, conectado=False)
    dono = ligar()
    central = _central(dono, mundo, onde_esta=lambda u: VARANDA if u == rm.uniq(VERMELHO) else "")

    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 3. objeto de busca não é chave; o que não é controle não se toca
# ---------------------------------------------------------------------------


def test_o_objeto_de_busca_nao_e_chave(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """O defeito do doctor, do lado do produto: o BlueZ guarda um objeto para todo
    aparelho que uma busca achou.

    MORDIDA: tire o ``objeto.pareado is not True`` do ``sobras`` — o objeto de
    busca do quarto sai pela ponte, com lápide, e esta régua reprova.
    """
    mundo.pareado(SALA, VERMELHO)
    mundo.mesa[rm.no_de(QUARTO, VERMELHO)] = {
        bd.APARELHO: {
            "Address": VERMELHO.upper(),
            "Alias": "controle de mentira",
            "Paired": False,
            "Bonded": False,
            "Trusted": False,
            "Connected": False,
            "Class": rm.CLASSE_DE_CONTROLE,
        }
    }
    dono = ligar()
    central = _central(dono, mundo)

    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == []
    assert mundo.metodos("RemoveDevice") == []


def test_o_teclado_de_varios_hosts_nao_se_toca(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """Teclado tem ``HID_PHYS`` como o controle, e pode querer as duas chaves.

    MORDIDA: tire o ``e_controle`` do ``sobras`` — a chave do teclado no quarto
    sai, e esta régua reprova.
    """
    mundo.pareado(SALA, ROXO, classe=CLASSE_DE_TECLADO)
    mundo.pareado(QUARTO, ROXO, classe=CLASSE_DE_TECLADO, host=False)
    dono = ligar()
    central = _central(dono, mundo, onde_esta=lambda u: SALA if u == rm.uniq(ROXO) else "")

    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 4. uma por volta, e nunca com um movimento «esperando»
# ---------------------------------------------------------------------------


def test_uma_por_volta(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """MORDIDA: faça o ``esquecer_as_sobras`` esquecer a lista inteira — a
    primeira volta escreve duas lápides, e esta régua reprova."""
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    _dobrado(mundo, AZUL, QUARTO, VARANDA)
    dono = ligar()
    central = _central(dono, mundo)

    primeira = central.esquecer_as_sobras()
    assert len(mundo.lapides) == 1
    segunda = central.esquecer_as_sobras()
    assert len(mundo.lapides) == 2
    assert {primeira, segunda} == {(QUARTO, VERMELHO), (VARANDA, AZUL)}
    assert central.esquecer_as_sobras() is None


def test_com_um_movimento_esperando_a_faxina_espera(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    """O mover esquece a própria origem; dois motores na mesma chave, não.

    MORDIDA: tire o ``_ocupada()`` do começo e o de dentro da trava — a faxina
    apaga no meio do mover, e esta régua reprova.
    """
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    dono = ligar()
    central = _central(dono, mundo)
    central._guardar(cr.Movimento(AZUL, VARANDA, cr.ESPERANDO, cr.PASSO_CONFERINDO))

    assert central.esquecer_as_sobras() is None
    assert mundo.lapides == []


def test_com_a_trava_na_mao_de_outro_tenta_na_proxima(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    dono = ligar()
    central = _central(dono, mundo, prazo_da_trava_s=0.2)
    segurando = threading.Event()
    soltar = threading.Event()

    def outro_motor() -> None:
        with diario_do_radio.trava_do_radio("bt-watchdog", prazo_s=1.0):
            segurando.set()
            soltar.wait(5.0)

    fio = threading.Thread(target=outro_motor, daemon=True)
    fio.start()
    assert segurando.wait(5.0)
    try:
        assert central.esquecer_as_sobras() is None
        assert mundo.lapides == []
    finally:
        soltar.set()
        fio.join(5.0)
    assert central.esquecer_as_sobras() == (QUARTO, VERMELHO)


# ---------------------------------------------------------------------------
# 5. a mesa inteira: de 1 a 4 jogadores, rádio, cabo e misto, as três máscaras
# ---------------------------------------------------------------------------


def _no_do_sys(mac: str, phys: str) -> str:
    return f"HID_NAME=DualSense Wireless Controller\nHID_PHYS={phys}\nHID_UNIQ={mac}\n"


def _sys_da_mesa(
    planos: list[tuple[str, str, bool]], mascara: str, *, vpad_primeiro: bool
) -> tuple[Callable[[str], list[str]], Callable[[str], str]]:
    """Um ``/sys/class/hidraw`` com o físico de cada um e o vpad da máscara.

    No rádio o ``HID_PHYS`` é o endereço do adaptador; no cabo é o caminho USB
    (a regra de honestidade do ``adaptador_por_uniq``). Na máscara DualSense o
    vpad é hidraw também, com ``HID_PHYS=hefesto-vpad`` — e o pior caso é ele
    carimbar o MESMO ``uniq`` do físico, por isso ele vem com o endereço dele,
    antes ou depois do físico. No Xbox o vpad é uinput (sem hidraw); no nativo
    não há vpad.
    """
    nos: dict[str, str] = {}
    n = 0
    for controle, casa, pelo_radio in planos:
        fisico = _no_do_sys(controle, casa if pelo_radio else "usb-0000:0c:00.3-1/input3")
        vpad = _no_do_sys(controle, "hefesto-vpad") if mascara == "dualsense" else None
        for texto in [vpad, fisico] if vpad_primeiro else [fisico, vpad]:
            if texto is not None:
                nos[f"hidraw{n}"] = texto
                n += 1

    def ler(caminho: str) -> str:
        return nos.get(Path(caminho).parent.parent.name, "")

    return (lambda _raiz: list(nos)), ler


@pytest.mark.parametrize("vpad_primeiro", [False, True], ids=["fisico-antes", "vpad-antes"])
@pytest.mark.parametrize("mascara", ["nativo", "dualsense", "xbox"])
@pytest.mark.parametrize("transporte", ["radio", "cabo", "misto"])
@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_a_mesa_inteira(
    diario: Path, jogadores: int, transporte: str, mascara: str, vpad_primeiro: bool
) -> None:
    """Cada jogador guarda um adaptador e tem a chave velha no seguinte.

    Só sai a sobra de quem está conectado pelo rádio; a de quem está no cabo
    espera. A máscara entra pelo ``/sys``: o vpad da máscara DualSense é hidraw
    e não pode esconder o ``HID_PHYS`` do físico, venha antes ou depois dele.
    """
    mundo = rm.RadioDeMentira()
    planos: list[tuple[str, str, bool]] = []
    for i in range(jogadores):
        controle, casa, velha = CONTROLES[i], ADAPTADORES[i % 3], ADAPTADORES[(i + 1) % 3]
        pelo_radio = transporte == "radio" or (transporte == "misto" and i % 2 == 0)
        _dobrado(mundo, controle, casa, velha, conectado=pelo_radio)
        planos.append((controle, casa, pelo_radio))
    listar, ler = _sys_da_mesa(planos, mascara, vpad_primeiro=vpad_primeiro)

    def onde_esta(uniq: str) -> str:
        lido = adaptador_por_uniq([uniq], raiz="/sys/class/hidraw", listar=listar, ler=ler)
        return str(lido[uniq])

    vivo = bd.DonoVivo(mundo)
    assert vivo.ligar()
    try:
        central = _central(vivo, mundo, onde_esta=onde_esta)
        esquecidas = []
        for _volta in range(2 * jogadores + 1):
            feito = central.esquecer_as_sobras()
            if feito is None:
                break
            esquecidas.append(feito)
    finally:
        vivo.fechar()

    esperadas = sorted(
        (ADAPTADORES[(i + 1) % 3], CONTROLES[i])
        for i, (_c, _casa, pelo_radio) in enumerate(planos)
        if pelo_radio
    )
    assert sorted(esquecidas) == esperadas
    assert sorted(mundo.lapides) == esperadas
    for i, (controle, casa, pelo_radio) in enumerate(planos):
        assert mundo.objeto(casa, controle) is not None, "a chave que ele usa saiu"
        sobra = mundo.objeto(ADAPTADORES[(i + 1) % 3], controle)
        assert (sobra is None) == pelo_radio, (
            f"jogador {i + 1} ({'rádio' if pelo_radio else 'cabo'}, máscara {mascara}): "
            "a sobra de quem está no rádio sai, e a de quem está no cabo espera"
        )


# ---------------------------------------------------------------------------
# 6. o daemon liga a faxina, e o fechar() a para
# ---------------------------------------------------------------------------


def test_a_faxina_roda_sozinha_e_para_no_fechar(
    diario: Path, mundo: rm.RadioDeMentira, ligar: Callable[[], bd.DonoVivo]
) -> None:
    _dobrado(mundo, VERMELHO, SALA, QUARTO)
    dono = ligar()
    central = _central(dono, mundo)

    central.comecar_a_faxina(intervalo_s=0.01)
    central.comecar_a_faxina(intervalo_s=0.01)  # idempotente: um fio só
    fim = time.monotonic() + 5.0
    while not mundo.lapides and time.monotonic() < fim:
        time.sleep(0.01)
    faxinas = [f for f in threading.enumerate() if f.name == "hefesto-central-faxina"]
    central.fechar(espera=2.0)

    assert mundo.lapides == [(QUARTO, VERMELHO)]
    assert len(faxinas) == 1
    assert not any(f.is_alive() for f in faxinas), "o fechar() não parou a faxina"


def test_o_daemon_liga_a_faxina(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tire o ``central.comecar_a_faxina()`` do ``_start_central_do_radio``
    — a central sobe sem faxina, a sobra fica para sempre, e esta régua reprova."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    chamadas: list[str] = []

    class _CentralQueAnota:
        def __init__(self, **_kw: Any) -> None:
            chamadas.append("nasceu")

        def ligar(self) -> bool:
            chamadas.append("ligar")
            return True

        def comecar_a_faxina(self, *_a: Any, **_kw: Any) -> None:
            chamadas.append("faxina")

    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_FAKE", raising=False)
    monkeypatch.setattr(cr, "CentralDoRadio", _CentralQueAnota)
    daemon = Daemon(
        controller=FakeController(transport="bt"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )

    asyncio.run(daemon._start_central_do_radio())

    assert chamadas == ["nasceu", "ligar", "faxina"]
