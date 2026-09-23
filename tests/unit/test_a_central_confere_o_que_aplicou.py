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
5. sem BlueZ é «não sei», e nada se escreve; a webcam não se move;
6. sem o agente próprio, o piso atende o ``Pair`` (decisão de quem coordena);
7. os estados publicados são só os três.
"""

from __future__ import annotations

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
