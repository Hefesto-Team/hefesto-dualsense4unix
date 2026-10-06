"""A central CONFERE o que aplicou — MOVER-UM-POR-VEZ-01 (23/09/2026).

O coração da sprint: *"o BlueZ disse que pareou"* não é *"o controle chegou"*.
Só o ``HID_PHYS`` no adaptador pretendido E o movimento chegando dizem
«chegou»; sem os dois o estado fica «esperando».

FATO SUBSTITUÍDO (25/09/2026, A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01): aqui se
lia *«e a origem NÃO se apaga»*. Desde a lista dela de 25/09 a origem sai ANTES
do gesto (a R1 dela ao pé da letra — ligado, o controle não entra em modo de
parear, e com a chave lá ele volta sozinho). O que o CONFERIR segura continua
sendo o «chegou»: sem os dois sinais, nunca «chegou», e o diário não diz
«moveu».

O mundo é o ``radio_de_mentira`` com o botão ``pair_mente``: o ``Pair``
responde que deu e o controle não muda de host — o «aplicar que falha» da
sprint, que o BlueZ não denuncia.

O QUE ESTA RÉGUA COBRA:

1. o aplicar que falha fica «esperando», e nada se apaga — **mordida:** sem o
   CONFERIR dá «chegou» e a régua reprova;
2. o «esperando» resolve pela vigia: o ``HID_PHYS`` confirma depois → «chegou»
   (e só então a origem sai); ele volta para a origem → «não chegou»; o prazo
   acaba → «não chegou»;
3. ``HID_PHYS`` sem movimento não é chegada;
4. o que não é controle (o fone) confere pelo ``Connected`` do destino;
5. sem BlueZ é «não sei», e nada se escreve; a webcam não se move; o
   movimento em «não sei» não apaga a conexão viva do destino; um erro no meio
   não deixa a central emperrada num «esperando»;
6. sem o agente próprio, o piso atende o ``Pair`` (decisão de produto);
7. os estados publicados são só os três;
8. o ``state_full`` não abre o dono nem espera a foto do rádio;
9. sob a suíte, a ponte root de verdade não roda.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, FONE, QUARTO, SALA, VERMELHO


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> rm.RadioDeMentira:
    radio = rm.RadioDeMentira()
    radio.pareado(SALA, VERMELHO)
    radio.pareado(SALA, AZUL)
    return radio


@pytest.fixture()
def dono(mundo: rm.RadioDeMentira) -> Iterator[bd.DonoVivo]:
    vivo = bd.DonoVivo(mundo)
    assert vivo.ligar()
    yield vivo
    vivo.fechar()


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


def _central(
    dono: bd.LeitorDoBluez, mundo: rm.RadioDeMentira, relogio: rm.Relogio, **extra: Any
) -> cr.CentralDoRadio:
    return cr.CentralDoRadio(
        dono=dono,
        onde_esta=mundo.onde_esta,
        movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
        **extra,
    )


def _aplicar_que_falha(
    mundo: rm.RadioDeMentira, relogio: rm.Relogio, central: cr.CentralDoRadio
) -> cr.Movimento:
    """O ``Pair`` diz que deu, e o controle não sai do lugar."""
    mundo.pair_mente = True
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    return central.mover(VERMELHO, QUARTO)


def _da_central(diario: Path) -> list[str]:
    alvo = {cr.MOVEU_O_APARELHO, cr.O_APARELHO_NAO_CHEGOU}
    return [e["o_que"] for e in diario_do_radio.ler(caminhos=[diario]) if e["o_que"] in alvo]


def test_o_aplicar_que_falha_fica_esperando_e_nao_diz_chegou(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A régua da sprint: *"injete um aplicar que falha, e a régua acusa"*."""
    central = _central(dono, mundo, relogio)

    feito = _aplicar_que_falha(mundo, relogio, central)

    assert mundo.objeto(QUARTO, VERMELHO)["Paired"] is True, "o BlueZ disse que deu"
    assert (feito.estado, feito.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)
    assert feito.passo == cr.PASSO_CONFERINDO
    assert feito.estado != cr.CHEGOU
    assert feito.origens_esquecidas is True
    assert mundo.lapides == [(SALA, VERMELHO)], "UMA lápide: a da origem, antes do gesto"
    assert _da_central(diario) == []


def test_a_conferencia_espera_os_dez_segundos_e_nao_mais(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    assert cr.CONFERIR_S == 10.0
    central = _central(dono, mundo, relogio)
    mundo.pair_mente = True
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    antes = relogio.agora

    central.mover(VERMELHO, QUARTO)

    conferencia = relogio.agora - antes - 2.0
    assert cr.CONFERIR_S <= conferencia <= cr.CONFERIR_S + cr.PASSO_S


def test_o_hid_phys_que_confirma_depois_vira_chegou_e_so_entao_a_origem_sai(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    _aplicar_que_falha(mundo, relogio, central)
    central.vigiar()
    assert central.movimento_de(VERMELHO).estado == cr.ESPERANDO
    assert mundo.lapides == [(SALA, VERMELHO)]

    mundo.fisicos[VERMELHO].host = QUARTO
    mundo.apertar_ps(VERMELHO)
    central.vigiar()

    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.passo) == (cr.CHEGOU, cr.PASSO_FIM)
    assert mundo.lapides == [(SALA, VERMELHO)]
    assert mundo.objeto(SALA, VERMELHO) is None
    assert mundo.objeto(SALA, AZUL) is not None
    assert _da_central(diario) == [cr.MOVEU_O_APARELHO]


def test_o_controle_nao_tem_como_voltar_para_a_origem(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O host que ele guarda ainda é a sala — e a sala não tem mais a chave."""
    central = _central(dono, mundo, relogio)
    _aplicar_que_falha(mundo, relogio, central)

    mundo.apertar_ps(VERMELHO)
    assert mundo.voltar_sozinho(VERMELHO) == ""
    central.vigiar()

    feito = central.movimento_de(VERMELHO)
    assert feito.estado == cr.ESPERANDO
    assert mundo.onde_esta(rm.uniq(VERMELHO)) != SALA
    assert _da_central(diario) == []


def test_o_esperando_que_passa_do_prazo_nao_chegou(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    feito = _aplicar_que_falha(mundo, relogio, central)

    relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S - 1
    central.vigiar()
    assert central.movimento_de(VERMELHO).estado == cr.ESPERANDO

    relogio.agora += 2
    central.vigiar()
    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert mundo.lapides == [(SALA, VERMELHO), (QUARTO, VERMELHO)]
    assert mundo.objeto(QUARTO, VERMELHO) is None


def test_hid_phys_sem_movimento_nao_e_chegada(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O nó está no quarto, e nenhum pacote de movimento chega: não é «chegou»."""
    mundo.fisicos[VERMELHO].hz = 0.0
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert feito.estado == cr.ESPERANDO
    assert mundo.lapides == [(SALA, VERMELHO)]


def test_o_fone_confere_pelo_connected_do_destino(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE)
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))

    feito = central.mover(FONE, QUARTO)

    assert feito.e_controle is False
    assert feito.estado == cr.CHEGOU
    assert mundo.objeto(QUARTO, FONE)["Connected"] is True
    assert mundo.lapides == [(SALA, FONE)]


def test_o_fone_pareado_que_nao_conecta_no_destino_fica_esperando(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O ``Pair`` do fone diz que deu, e o ``Connect`` no quarto falha: sem o"""
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE)
    dono._fotografar()
    mundo.pair_mente = True
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))

    feito = central.mover(FONE, QUARTO)

    assert mundo.objeto(QUARTO, FONE)["Paired"] is True, "o BlueZ disse que deu"
    assert mundo.objeto(QUARTO, FONE)["Connected"] is False
    assert (feito.estado, feito.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)
    assert mundo.lapides == [(SALA, FONE)]


def test_sem_bluez_e_nao_sei_e_nada_se_escreve(
    diario: Path, mundo: rm.RadioDeMentira, relogio: rm.Relogio
) -> None:
    mundo.bluez_de_pe = False
    vivo = bd.DonoVivo(mundo)
    assert vivo.ligar()
    central = _central(vivo, mundo, relogio)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_BLUEZ)
    assert mundo.chamadas == [] and mundo.escritas == []
    vivo.fechar()


def test_a_webcam_nao_se_move(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)

    nao_conhecido = central.mover("aa:bb:cc:00:00:9e", QUARTO)
    sem_forma = central.mover("/dev/video0", QUARTO)

    assert nao_conhecido.motivo == cr.MOTIVO_FORA_DO_RADIO
    assert sem_forma.motivo == cr.MOTIVO_FORA_DO_RADIO
    assert mundo.chamadas == [] and mundo.escritas == []


def test_destino_que_nao_esta_na_mesa_nao_abre_janela(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)

    feito = central.mover(VERMELHO, "aa:bb:cc:00:00:d4")

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_DESTINO)
    assert mundo.metodos("StartDiscovery") == []


def test_o_movimento_em_nao_sei_nao_apaga_a_conexao_viva_do_destino(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O kernel diz que ele JÁ está no destino, e o movimento ainda é «não sei»."""
    nao_sei = {"agora": False}

    def movimento(u: str) -> float | None:
        return None if nao_sei["agora"] else mundo.hz(u)

    central = cr.CentralDoRadio(
        dono=dono,
        onde_esta=mundo.onde_esta,
        movimento=movimento,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
    )
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU
    chamadas, escritas = len(mundo.chamadas), len(mundo.escritas)

    nao_sei["agora"] = True
    de_novo = central.mover(VERMELHO, QUARTO)

    assert mundo.objeto(QUARTO, VERMELHO) is not None, "a conexão viva do quarto saiu"
    assert mundo.objeto(QUARTO, VERMELHO)["Paired"] is True
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert mundo.lapides == [(SALA, VERMELHO)], "uma lápide a mais: o quarto foi esquecido"
    assert mundo.chamadas[chamadas:] == [] and mundo.escritas[escritas:] == []
    assert (de_novo.estado, de_novo.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)
    nao_sei["agora"] = False
    central.vigiar()
    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.motivo) == (cr.CHEGOU, cr.MOTIVO_JA_ESTAVA)
    assert _da_central(diario) == [cr.MOVEU_O_APARELHO], "nada se moveu na segunda vez"


def _onde_esta_que_quebra(mundo: rm.RadioDeMentira, quebrado: dict[str, bool]) -> Any:
    def onde_esta(u: str) -> str:
        if quebrado["sim"]:
            raise RuntimeError("o sysfs sumiu sob a mão")
        return mundo.onde_esta(u)

    return onde_esta


def test_um_erro_no_meio_do_mover_nao_emperra_a_central(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O ``mover`` promete nunca levantar. Uma exceção no meio deixava o"""
    quebrado = {"sim": True}
    central = _central(dono, mundo, relogio)
    central._onde_esta = _onde_esta_que_quebra(mundo, quebrado)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_FALHOU)
    assert central.em_curso is False, "a central ficou emperrada num «esperando» morto"
    assert mundo.lapides == [] and mundo.objeto(SALA, VERMELHO) is not None
    quebrado["sim"] = False
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU


def test_um_erro_na_vigia_nao_segura_o_esperando_alem_do_prazo(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A vigia roda num fio: uma exceção ali matava o fio e o «esperando» nunca"""
    quebrado = {"sim": False}
    central = _central(dono, mundo, relogio)
    central._onde_esta = _onde_esta_que_quebra(mundo, quebrado)
    feito = _aplicar_que_falha(mundo, relogio, central)
    assert feito.estado == cr.ESPERANDO

    quebrado["sim"] = True
    relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S + 1
    central.vigiar()

    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert mundo.lapides == [(SALA, VERMELHO)]


def test_sem_o_agente_proprio_o_piso_atende_o_pair(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O agente próprio não exportou: o ``hefesto-bt-agent`` (o padrão) atende."""
    mundo.exportar_da = False
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert feito.estado == cr.CHEGOU
    assert mundo.o_padrao_atendeu == [rm.no_de(QUARTO, VERMELHO)]
    assert mundo.o_nosso_atendeu == []
    assert mundo.objeto(QUARTO, VERMELHO)["Trusted"] is True


def test_o_publicado_so_tem_os_tres_estados_e_nenhum_texto_de_tela(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    central.mover("aa:bb:cc:00:00:9e", QUARTO)
    _aplicar_que_falha(mundo, relogio, central)

    publicado = central.publicar()

    assert publicado["em_curso"] is True
    assert publicado["proposta"] is None
    estados = {m["estado"] for m in publicado["movimentos"]}
    assert estados <= set(cr.ESTADOS)
    assert estados == {cr.ESPERANDO, cr.NAO_CHEGOU}
    for movimento in publicado["movimentos"]:
        assert set(movimento) == {
            "aparelho", "destino", "estado", "passo", "motivo", "origens", "e_controle",
            "classe", "modalias", "icone", "nome", "quando",
        }


# 8. o state_full não espera o rádio


class _LeitorLento(bd.LeitorDoBluez):
    """O caminho de reserva (``busctl``): cada foto custa subprocessos."""

    def __init__(self) -> None:
        self.solta = threading.Event()
        self.fotos = 0

    def pode_perguntar(self) -> bool:
        return True

    def adaptadores(self) -> tuple[bd.AdaptadorDoBluez, ...] | None:
        self.fotos += 1
        self.solta.wait(5)
        return (bd.AdaptadorDoBluez("/org/bluez/hci8", "hci8", QUARTO),)


def test_o_publicar_nao_abre_o_dono_antes_de_ligar(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O primeiro ``dono()`` paga o Gio de forma síncrona: o tique não o paga."""
    pedidos: list[str] = []

    def nao_abra() -> bd.LeitorDoBluez:
        pedidos.append(threading.current_thread().name)
        return _LeitorLento()

    monkeypatch.setattr(bd, "dono", nao_abra)
    central = cr.CentralDoRadio()

    assert central.publicar([]) == {"movimentos": [], "em_curso": False, "proposta": None,
                                    "busca": None, "pedindo": []}
    assert not _esperar(lambda: bool(pedidos), teto=0.3), "o state_full abriu o dono do BlueZ"


def test_pelo_caminho_de_reserva_o_tique_nao_espera_a_foto(diario: Path) -> None:
    """Sem o dono vivo, a foto dos adaptadores se refaz num fio; o tique segue."""
    lento = _LeitorLento()
    central = cr.CentralDoRadio(dono=lento, sysfs={"listar": lambda _p: [], "raiz": "/x"})
    antes = time.monotonic()

    central.publicar([])

    assert time.monotonic() - antes < 1.0, "o tique esperou a foto do rádio"
    lento.solta.set()
    assert _esperar(lambda: central._adaptadores_em_cache is not None)
    assert lento.fotos == 1


def test_depois_de_ligar_o_tique_nao_reabre_o_dono(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O dono do arranque morreu (o barramento caiu): o ``state_full`` não o reabre.

    O ``bluez_dbus.dono()`` sem dono vivo tenta o Gio de novo, de forma
    síncrona — até ~5 s num barramento mudo —, e o ``state_full`` roda no laço
    do daemon a 10 Hz. Depois do ``ligar`` o tique chamava o ``dono()`` direto;
    agora ele usa o último dono que a central viu, se ainda pergunta, e senão
    refaz a foto num fio.

    MORDIDA: faça o tique pegar o dono pelo ``_dono()`` — o ``dono()`` roda no
    fio de quem publica e esta régua reprova.
    """
    fios: list[str] = []
    lento = _LeitorLento()
    lento.solta.set()

    def dono_que_abre() -> bd.LeitorDoBluez:
        fios.append(threading.current_thread().name)
        return lento

    monkeypatch.setattr(bd, "dono", dono_que_abre)
    central = cr.CentralDoRadio(sysfs={"listar": lambda _p: [], "raiz": "/x"})
    central._ligada = True

    central.publicar([])

    assert threading.current_thread().name not in fios, "o tique abriu o dono"
    assert _esperar(lambda: central._adaptadores_em_cache is not None)
    assert fios, "a foto não se refez no fio"


def _esperar(condicao: Any, teto: float = 3.0) -> bool:
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


def test_sob_a_suite_o_esquecer_nao_chama_a_ponte_de_verdade(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire a guarda da suíte do ``esquecer_pela_ponte`` — o pedido"""
    pedidos: list[Any] = []

    def correr(pedido: Any) -> tuple[int, str]:
        pedidos.append(pedido)
        return 0, ""

    monkeypatch.setattr(cr, "_correr_a_ponte", correr)

    fez, motivo = cr.esquecer_pela_ponte(SALA, VERMELHO)

    assert fez is False and "suíte" in motivo
    assert pedidos == []


def test_sob_a_suite_a_janela_pela_ponte_nao_chama_sudo(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem o dono vivo, a janela da central é a da ponte (``sudo … descobrir``)."""
    from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp

    pedidos: list[Any] = []

    def abrir(pedido: Any) -> Any:
        pedidos.append(pedido)
        raise OSError("dublê: nada roda")

    monkeypatch.setattr(gp, "_abrir_de_verdade", abrir)
    leitor = bd.pelo_executor(lambda _argumentos: None)
    assert leitor.atende_o_proprio_pareamento is False
    assert cr.CentralDoRadio()._abrir_janela is cr._janela_de_busca

    janela = cr._janela_de_busca(QUARTO, 30, leitor)

    assert janela.abrir_a_janela(), "a janela da ponte abriu sob a suíte"
    assert pedidos == []
