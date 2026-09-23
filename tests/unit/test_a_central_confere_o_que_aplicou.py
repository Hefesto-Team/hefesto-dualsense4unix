"""A central CONFERE o que aplicou — MOVER-UM-POR-VEZ-01 (23/09/2026).

O coração da sprint: *"o BlueZ disse que pareou"* não é *"o controle chegou"*.
Só o ``HID_PHYS`` no adaptador pretendido E o movimento chegando dizem
«chegou»; sem os dois o estado fica «esperando», e a origem NÃO se apaga.

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
6. sem o agente próprio, o piso atende o ``Pair`` (decisão de quem coordena);
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


# ---------------------------------------------------------------------------
# 1. o aplicar que falha
# ---------------------------------------------------------------------------


def test_o_aplicar_que_falha_fica_esperando_e_nao_apaga_a_origem(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A régua da sprint: *"injete um aplicar que falha, e a régua acusa"*.

    MORDIDA: faça o ``_conferir`` devolver ``True`` sem perguntar — o mover diz
    «chegou», apaga a sala com o controle ainda lá, e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)

    feito = _aplicar_que_falha(mundo, relogio, central)

    assert mundo.objeto(QUARTO, VERMELHO)["Paired"] is True, "o BlueZ disse que deu"
    assert (feito.estado, feito.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)
    assert feito.passo == cr.PASSO_CONFERINDO
    assert feito.estado != cr.CHEGOU
    assert mundo.objeto(SALA, VERMELHO) is not None, "a origem não se apaga sem conferir"
    assert mundo.lapides == []
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

    # 2 s até o gesto, e a conferência inteira — nem um passo a mais.
    conferencia = relogio.agora - antes - 2.0
    assert cr.CONFERIR_S <= conferencia <= cr.CONFERIR_S + cr.PASSO_S


# ---------------------------------------------------------------------------
# 2. o «esperando» se resolve pela vigia
# ---------------------------------------------------------------------------


def test_o_hid_phys_que_confirma_depois_vira_chegou_e_so_entao_a_origem_sai(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    _aplicar_que_falha(mundo, relogio, central)
    central.vigiar()
    assert central.movimento_de(VERMELHO).estado == cr.ESPERANDO
    assert mundo.lapides == []

    # O controle pega o host novo e conecta no quarto.
    mundo.fisicos[VERMELHO].host = QUARTO
    mundo.apertar_ps(VERMELHO)
    central.vigiar()

    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.passo) == (cr.CHEGOU, cr.PASSO_FIM)
    assert mundo.lapides == [(SALA, VERMELHO)]
    assert mundo.objeto(SALA, VERMELHO) is None
    assert mundo.objeto(SALA, AZUL) is not None
    assert _da_central(diario) == [cr.MOVEU_O_APARELHO]


def test_o_controle_que_volta_para_a_origem_nao_chegou(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    _aplicar_que_falha(mundo, relogio, central)

    mundo.apertar_ps(VERMELHO)  # o host que ele guarda ainda é a sala
    central.vigiar()

    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_VOLTOU)
    assert mundo.lapides == []
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA
    assert _da_central(diario) == [cr.O_APARELHO_NAO_CHEGOU]


def test_o_esperando_que_passa_do_prazo_nao_chegou(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    feito = _aplicar_que_falha(mundo, relogio, central)

    # O prazo conta do COMEÇO do movimento, não do fim da conferência.
    relogio.agora = feito.comecou + cr.PRAZO_DO_PENDENTE_S - 1
    central.vigiar()
    assert central.movimento_de(VERMELHO).estado == cr.ESPERANDO

    relogio.agora += 2
    central.vigiar()
    feito = central.movimento_de(VERMELHO)
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_PRAZO)
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 3. HID_PHYS sem movimento
# ---------------------------------------------------------------------------


def test_hid_phys_sem_movimento_nao_e_chegada(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O nó está no quarto, e nenhum pacote de movimento chega: não é «chegou».

    MORDIDA: tire a pergunta do movimento do ``_chegou`` — o mover diz «chegou»
    com o controle mudo, e esta régua reprova.
    """
    mundo.fisicos[VERMELHO].hz = 0.0
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert feito.estado == cr.ESPERANDO
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 4. o fone confere pelo Connected
# ---------------------------------------------------------------------------


def test_o_fone_confere_pelo_connected_do_destino(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE)
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))

    feito = central.mover(FONE, QUARTO)

    assert feito.controle is False
    assert feito.estado == cr.CHEGOU
    assert mundo.objeto(QUARTO, FONE)["Connected"] is True
    assert mundo.lapides == [(SALA, FONE)]


def test_o_fone_pareado_que_nao_conecta_no_destino_fica_esperando(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O ``Pair`` do fone diz que deu, e o ``Connect`` no quarto falha: sem o
    ``Connected`` do destino, não é «chegou», e a sala não se apaga.

    MORDIDA: faça o ``_chegou`` do fone responder pelo objeto, sem o
    ``Connected`` — ele diz «chegou», a sala sai, e esta régua reprova.
    """
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE)
    dono._fotografar()
    mundo.pair_mente = True
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(FONE))

    feito = central.mover(FONE, QUARTO)

    assert mundo.objeto(QUARTO, FONE)["Paired"] is True, "o BlueZ disse que deu"
    assert mundo.objeto(QUARTO, FONE)["Connected"] is False
    assert (feito.estado, feito.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)
    assert mundo.objeto(SALA, FONE) is not None
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 5. não sei, e o que não é do rádio
# ---------------------------------------------------------------------------


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
    """O kernel diz que ele JÁ está no destino, e o movimento ainda é «não sei».

    O ``SensorHub`` responde ``None`` enquanto o nó de movimento não fecha uma
    janela — um controle que acabou de reconectar, ou que ninguém perguntou nos
    últimos 5 s (o TTL da demanda). O mover lia esse «não sei» como «não está
    lá», tratava a conexão VIVA do destino como a «velha» da R6, esquecia-a pela
    ponte (com lápide) e abria a janela pedindo PS + Create. Sem o gesto dela,
    o controle ficava sem bond em adaptador nenhum: a sala já tinha saído no
    primeiro mover.

    MORDIDA: tire o bloco «o kernel já o diz no destino» do ``_mover_na_trava``
    — o bond do quarto sai, uma segunda lápide aparece, e esta régua reprova.
    """
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
    # «Não sei» não é «chegou»: fica esperando, e a vigia resolve quando o número vem.
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
    """O ``mover`` promete nunca levantar. Uma exceção no meio deixava o
    movimento «esperando» para sempre: o «Equilibrar» nunca mais propunha nada
    e o mesmo pedido devolvia o movimento morto até o daemon reiniciar.

    MORDIDA: tire o ``except`` do ``mover`` — a exceção sobe e esta régua reprova.
    """
    quebrado = {"sim": True}
    central = _central(dono, mundo, relogio)
    central._onde_esta = _onde_esta_que_quebra(mundo, quebrado)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_FALHOU)
    assert central.em_curso is False, "a central ficou emperrada num «esperando» morto"
    assert mundo.lapides == [] and mundo.objeto(SALA, VERMELHO) is not None
    # E o próximo pedido anda.
    quebrado["sim"] = False
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU


def test_um_erro_na_vigia_nao_segura_o_esperando_alem_do_prazo(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A vigia roda num fio: uma exceção ali matava o fio e o «esperando» nunca
    mais chegava ao prazo.

    MORDIDA: tire o ``except`` da ``vigiar`` — a exceção sobe e esta régua reprova.
    """
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
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 6. sem o agente próprio, o piso
# ---------------------------------------------------------------------------


def test_sem_o_agente_proprio_o_piso_atende_o_pair(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O agente próprio não exportou: o ``hefesto-bt-agent`` (o padrão) atende.

    MORDIDA: devolva o ``SEM_AGENTE`` no ``DonoVivo.parear`` — o mover acaba
    «não chegou» com o piso de pé, e esta régua reprova.
    """
    mundo.exportar_da = False
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert feito.estado == cr.CHEGOU
    assert mundo.o_padrao_atendeu == [rm.no_de(QUARTO, VERMELHO)]
    assert mundo.o_nosso_atendeu == []
    assert mundo.objeto(QUARTO, VERMELHO)["Trusted"] is True


# ---------------------------------------------------------------------------
# 7. o que se publica
# ---------------------------------------------------------------------------


def test_o_publicado_so_tem_os_tres_estados_e_nenhum_texto_de_tela(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    _aplicar_que_falha(mundo, relogio, central)
    central.mover("aa:bb:cc:00:00:9e", QUARTO)

    publicado = central.publicar()

    assert publicado["em_curso"] is True
    assert publicado["proposta"] is None
    estados = {m["estado"] for m in publicado["movimentos"]}
    assert estados <= set(cr.ESTADOS)
    assert estados == {cr.ESPERANDO, cr.NAO_CHEGOU}
    for movimento in publicado["movimentos"]:
        assert set(movimento) == {
            "aparelho", "destino", "estado", "passo", "motivo", "origens", "controle", "quando"
        }


# ---------------------------------------------------------------------------
# 8. o state_full não espera o rádio
# ---------------------------------------------------------------------------


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
    """O primeiro ``dono()`` paga o Gio de forma síncrona: o tique não o paga.

    MORDIDA: tire o ``if self._ligada`` do ``publicar`` — o tique abre o dono,
    e esta régua reprova.
    """

    def nao_abra() -> bd.LeitorDoBluez:
        raise AssertionError("o state_full abriu o dono do BlueZ")

    monkeypatch.setattr(bd, "dono", nao_abra)
    central = cr.CentralDoRadio()

    assert central.publicar([]) == {"movimentos": [], "em_curso": False, "proposta": None}


def test_pelo_caminho_de_reserva_o_tique_nao_espera_a_foto(diario: Path) -> None:
    """Sem o dono vivo, a foto dos adaptadores se refaz num fio; o tique segue.

    MORDIDA: faça o ``_adaptadores`` sempre esperar — o ``publicar`` fica preso
    na foto lenta, e esta régua reprova pelo relógio.
    """
    lento = _LeitorLento()
    central = cr.CentralDoRadio(dono=lento, sysfs={"listar": lambda _p: [], "raiz": "/x"})
    antes = time.monotonic()

    central.publicar([])

    assert time.monotonic() - antes < 1.0, "o tique esperou a foto do rádio"
    lento.solta.set()
    assert _esperar(lambda: central._adaptadores_em_cache is not None)
    assert lento.fotos == 1


def _esperar(condicao: Any, teto: float = 3.0) -> bool:
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


# ---------------------------------------------------------------------------
# 9. sob a suíte, a ponte de verdade não roda
# ---------------------------------------------------------------------------
#
# As duas saídas da central para a ponte root são `sudo -n` contra a ponte
# INSTALADA, e o sudoers dela dispensa senha para `esquecer` e `descobrir`. Os
# dublês abaixo só GRAVAM o pedido: nem com a guarda arrancada nada roda.


def test_sob_a_suite_o_esquecer_nao_chama_a_ponte_de_verdade(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: tire a guarda da suíte do ``esquecer_pela_ponte`` — o pedido
    chega ao executor e esta régua reprova."""
    pedidos: list[list[str]] = []

    def correr(argumentos: Any) -> tuple[int, str]:
        pedidos.append(list(argumentos))
        return 0, ""

    monkeypatch.setattr(cr, "_correr_a_ponte", correr)

    fez, motivo = cr.esquecer_pela_ponte(SALA, VERMELHO)

    assert fez is False and "suíte" in motivo
    assert pedidos == []


def test_sob_a_suite_a_janela_pela_ponte_nao_chama_sudo(
    diario: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem o dono vivo, a janela da central é a da ponte (``sudo … descobrir``).

    MORDIDA: tire a guarda do ``_janela_de_busca`` — o ``sudo`` chega ao
    executor e esta régua reprova.
    """
    from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp

    pedidos: list[list[str]] = []

    def abrir(argumentos: Any) -> Any:
        pedidos.append(list(argumentos))
        raise OSError("dublê: nada roda")

    monkeypatch.setattr(gp, "_abrir_de_verdade", abrir)
    leitor = bd.pelo_executor(lambda _argumentos: None)
    assert leitor.atende_o_proprio_pareamento is False
    assert cr.CentralDoRadio()._abrir_janela is cr._janela_de_busca

    janela = cr._janela_de_busca(QUARTO, 30, leitor)

    assert janela.abrir_a_janela(), "a janela da ponte abriu sob a suíte"
    assert pedidos == []
