"""Mover UM por vez — MOVER-UM-POR-VEZ-01 (23/09/2026).

A palavra dela é a especificação: *"moveriamos por exemplo 1 controle por vez.
Apagaria esse um controle, o user, aperta os botões do controle pra
sincronizar aquele controle e ele estaria no novo dispositivo. E não apagar
tudo."* <!-- noqa-acento: citação literal dela -->

O mundo é o ``radio_de_mentira``: três adaptadores e controles que guardam UM
host, com o ``DonoVivo`` de verdade por cima — a borda, a trava, o diário e o
agente próprio são os do produto. O dublê não é mais frouxo que o BlueZ: o
``Pair`` recusa objeto que não existe e bond que já existe, o ``Connect`` só dá
no host que o controle guarda, e a busca só acha quem está segurando PS + Create.

O QUE ESTA RÉGUA COBRA:

1. mover um controle esquece SÓ ele, escreve UMA lápide, e abre a janela SÓ no
   destino — **mordida:** um mover que esquece dois reprova;
2. a ordem é parear → conferir → esquecer, e um parear que falha não apaga nada;
3. a conexão velha no destino sai ANTES da janela (R6 revista);
4. o adaptador desligado é ligado, e o ``Pairable`` só vale durante a janela;
5. idempotência: o segundo mover não escreve nada;
6. a trava fica na mão durante o gesto inteiro, e o gesto da tela a espera no
   máximo 5 s;
7. a D8 (onde parear) e o «Equilibrar» (R12): UM movimento, e nada enquanto
   um está «esperando»;
8. o verbo ``esquecer`` da ponte não apaga o cache SDP do bond novo.
"""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, SALA, VARANDA, VERDE, VERMELHO

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> rm.RadioDeMentira:
    """A sala com o vermelho e o azul; o quarto e a varanda livres."""
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


def _ela_segura_ps_create(mundo: rm.RadioDeMentira, relogio: rm.Relogio, aparelho: str) -> None:
    """Dois segundos depois de a janela abrir, ela segura PS + Create."""
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(aparelho))


# ---------------------------------------------------------------------------
# 1. esquece só ele, uma lápide, a janela só no destino
# ---------------------------------------------------------------------------


def test_mover_um_controle_esquece_so_ele_e_abre_a_janela_so_no_destino(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A régua da sprint, com as três metades.

    MORDIDA: faça o ``_esquecer_as_origens`` esquecer também os vizinhos da
    origem (o «apagar tudo» que ela recusou) — o azul some da sala, aparece uma
    segunda lápide, e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.CHEGOU, "")
    assert feito.origens == (SALA,)
    # Esquece SÓ ele: o azul continua pareado e conectado na sala.
    assert mundo.objeto(SALA, AZUL) is not None
    assert mundo.objeto(SALA, AZUL)["Paired"] is True
    assert mundo.onde_esta(rm.uniq(AZUL)) == SALA
    assert mundo.objeto(SALA, VERMELHO) is None
    # UMA lápide, do par que saiu.
    assert mundo.lapides == [(SALA, VERMELHO)]
    removidos = [a[0] for _c, a in mundo.metodos("RemoveDevice")]
    assert removidos == [rm.no_de(SALA, VERMELHO)]
    # A janela abriu SÓ no destino.
    buscas = [c for c, _a in mundo.metodos("StartDiscovery")]
    assert buscas == [rm.HCIS[QUARTO]]
    # O controle chegou: host novo, confiável, conectado.
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert mundo.objeto(QUARTO, VERMELHO)["Trusted"] is True
    # O agente próprio atendeu (R5), não o piso.
    assert mundo.o_nosso_atendeu == [rm.no_de(QUARTO, VERMELHO)]
    assert mundo.o_padrao_atendeu == []
    # O diário diz o que a central fez.
    linhas = diario_do_radio.ler(caminhos=[diario])
    movidos = [e for e in linhas if e["o_que"] == cr.MOVEU_O_APARELHO]
    assert len(movidos) == 1
    assert movidos[0]["controle"] == VERMELHO
    assert movidos[0]["adaptador"] == QUARTO


def test_a_ordem_e_parear_conferir_esquecer(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Pair no destino ANTES de qualquer esquecer na origem.

    MORDIDA: mova o ``_esquecer_as_origens`` para antes da janela — o
    ``RemoveDevice`` da sala aparece antes do ``Pair``, e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU

    linha = mundo.linha_do_tempo
    parear = linha.index(("Pair", QUARTO, VERMELHO))
    esquecer = linha.index(("RemoveDevice", SALA, VERMELHO))
    assert parear < esquecer
    assert linha.index(("StopDiscovery", QUARTO, "")) < esquecer


def test_o_parear_que_falha_nao_apaga_nada(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pair_falha = True
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_NAO_PAREOU)
    assert mundo.objeto(SALA, VERMELHO) is not None, "a conexão velha continua lá"
    assert mundo.lapides == []
    assert mundo.metodos("RemoveDevice") == []
    # Com o PS, ele volta para a sala: nada se perdeu.
    mundo.apertar_ps(VERMELHO)
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA
    linhas = diario_do_radio.ler(caminhos=[diario])
    da_central = {cr.MOVEU_O_APARELHO, cr.O_APARELHO_NAO_CHEGOU}
    assert [e["o_que"] for e in linhas if e["o_que"] in da_central] == [
        cr.O_APARELHO_NAO_CHEGOU
    ]


def test_sem_o_gesto_a_janela_fecha_e_nada_se_apaga(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)

    feito = central.mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)
    assert mundo.lapides == []
    assert mundo.propriedade_do_adaptador(QUARTO, "Discovering") is False
    assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA


# ---------------------------------------------------------------------------
# 3. a conexão velha no destino sai antes
# ---------------------------------------------------------------------------


def test_a_conexao_velha_no_destino_sai_antes_da_janela(
    diario: Path, dono: bd.DonoVivo, mundo: rm.RadioDeMentira, relogio: rm.Relogio
) -> None:
    """O vermelho tem um bond velho no quarto, de antes — o controle não o guarda mais.

    Com ele de pé o ``Pair`` responderia «já existe» sobre uma chave morta.

    MORDIDA: tire o bloco do «objeto velho no destino» — a janela lê o bond
    morto como «já pareado» antes de ela apertar nada, o ``Pair`` nunca
    acontece, o controle não chega, e esta régua reprova.
    """
    mundo.pareado(QUARTO, VERMELHO, host=False)
    # O DonoVivo só vê o que entrou por sinal ou pela foto: fotografa de novo.
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    feito = central.mover(VERMELHO, QUARTO)

    assert feito.estado == cr.CHEGOU
    linha = mundo.linha_do_tempo
    assert linha.index(("esquecer", QUARTO, VERMELHO)) < linha.index(
        ("StartDiscovery", QUARTO, "")
    )
    assert mundo.lapides == [(QUARTO, VERMELHO), (SALA, VERMELHO)]
    assert mundo.objeto(QUARTO, VERMELHO)["Paired"] is True


# ---------------------------------------------------------------------------
# 4. Powered e Pairable
# ---------------------------------------------------------------------------


def test_o_adaptador_desligado_liga_e_o_pairable_so_vale_na_janela(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.mesa[rm.HCIS[QUARTO]][bd.ADAPTADOR]["Powered"] = False
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU

    assert mundo.escritas_no(QUARTO, "Powered") == [True]
    assert mundo.escritas_no(QUARTO, "Pairable") == [True, False]
    assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False
    # Nenhum outro adaptador foi tocado.
    assert mundo.escritas_no(SALA, "Pairable") == []
    assert mundo.escritas_no(VARANDA, "Pairable") == []


def test_o_pairable_que_ja_estava_ligado_fica_ligado(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.mesa[rm.HCIS[QUARTO]][bd.ADAPTADOR]["Pairable"] = True
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU
    assert mundo.escritas_no(QUARTO, "Pairable") == []


def test_o_pairable_em_nao_sei_nao_e_desfeito(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Sem saber o ``Pairable`` de antes, devolver ``False`` poderia fechar o que
    já estava aberto: quem não sabe não desfaz.

    MORDIDA: tire o ``antes is None`` do ``_preparar_o_adaptador`` — o ``False``
    é escrito na saída e esta régua reprova.
    """
    del mundo.mesa[rm.HCIS[QUARTO]][bd.ADAPTADOR]["Pairable"]
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU
    assert mundo.escritas_no(QUARTO, "Pairable") == [True]


# ---------------------------------------------------------------------------
# 5. idempotência
# ---------------------------------------------------------------------------


def test_mover_duas_vezes_nao_move_duas(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O segundo diff é vazio: nenhuma chamada e nenhuma escrita no rádio.

    MORDIDA: tire o atalho do «já está lá» E o bloco «o kernel já o diz no
    destino» do ``_mover_na_trava`` — o segundo mover abre outra janela e esta
    régua reprova. Tirar só o atalho não morde AQUI (o controle tem ``HID_PHYS``,
    e o bloco do kernel o segura); quem morde o atalho sozinho é a régua do fone,
    ``test_o_fone_ja_conectado_no_destino_nao_se_move_de_novo``.
    """
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU
    chamadas, escritas = len(mundo.chamadas), len(mundo.escritas)

    de_novo = central.mover(VERMELHO, QUARTO)

    assert (de_novo.estado, de_novo.motivo) == (cr.CHEGOU, cr.MOTIVO_JA_ESTAVA)
    assert mundo.chamadas[chamadas:] == []
    assert mundo.escritas[escritas:] == []
    assert mundo.lapides == [(SALA, VERMELHO)]


def test_ja_no_destino_com_bond_sobrando_so_esquece_a_sobra(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Ele já está no quarto, e a sala ainda guarda um bond dele: sai só a sobra."""
    mundo.pareado(QUARTO, VERDE)
    mundo.pareado(SALA, VERDE, host=False)
    dono._fotografar()
    central = _central(dono, mundo, relogio)

    feito = central.mover(VERDE, QUARTO)

    assert feito.estado == cr.CHEGOU
    assert mundo.metodos("StartDiscovery") == []
    assert mundo.lapides == [(SALA, VERDE)]


def test_o_segundo_toque_com_o_primeiro_esperando_nao_desfaz_o_pareamento(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O primeiro mover pareou no quarto e ficou «esperando» a conferência — a
    trava já está livre. Ela toca de novo: é o MESMO movimento, sem escrita.

    Sem isto o segundo mover leria o bond recém-feito no quarto como a «conexão
    velha» da R6, o esqueceria com lápide e abriria outra janela.

    MORDIDA: faça o ``_o_mesmo_em_curso`` devolver sempre ``None`` — o quarto é
    esquecido e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)
    mundo.pair_mente = True
    _ela_segura_ps_create(mundo, relogio, VERMELHO)
    primeiro = central.mover(VERMELHO, QUARTO)
    assert (primeiro.estado, primeiro.passo) == (cr.ESPERANDO, cr.PASSO_CONFERINDO)
    chamadas, escritas = len(mundo.chamadas), len(mundo.escritas)

    de_novo = central.mover(VERMELHO, QUARTO)

    assert de_novo == primeiro
    assert mundo.chamadas[chamadas:] == [] and mundo.escritas[escritas:] == []
    assert mundo.lapides == []
    assert mundo.objeto(QUARTO, VERMELHO)["Paired"] is True


def test_o_fone_ja_conectado_no_destino_nao_se_move_de_novo(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O fone não tem ``HID_PHYS``: quem diz que ele já está lá é o ``Connected``.

    MORDIDA: tire o atalho do «já está lá» — o bond do fone no quarto é
    esquecido, outra janela abre e esta régua reprova.
    """
    mundo.pareado(QUARTO, rm.FONE, classe=rm.CLASSE_DE_FONE)
    dono._fotografar()
    central = _central(dono, mundo, relogio)

    feito = central.mover(rm.FONE, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.CHEGOU, cr.MOTIVO_JA_ESTAVA)
    assert mundo.chamadas == [] and mundo.escritas == []
    assert mundo.lapides == []


# ---------------------------------------------------------------------------
# 6. a trava
# ---------------------------------------------------------------------------


def test_a_trava_fica_na_mao_durante_o_gesto_inteiro(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Enquanto ela segura PS + Create, nenhum outro motor escreve no rádio.

    MORDIDA: tire o ``na_trava`` do :meth:`CentralDoRadio.mover` — o outro
    motor pega a trava no meio do gesto e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)
    tentativas: list[str] = []

    def outro_motor() -> None:
        resultado: list[str] = []

        def tentar() -> None:
            try:
                with diario_do_radio.trava_do_radio("vigia", prazo_s=0.0):
                    resultado.append("pegou")
            except diario_do_radio.TravaOcupadaError:
                resultado.append("esperou")

        # Outro processo seria outro descritor: outro fio com a trava própria.
        fio = threading.Thread(target=tentar)
        fio.start()
        fio.join(timeout=5)
        tentativas.extend(resultado)

    relogio.durante = outro_motor
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU
    relogio.durante = None

    assert tentativas, "a régua não chegou a tentar"
    assert set(tentativas) == {"esperou"}


def test_o_gesto_espera_a_trava_no_prazo_e_recusa_sem_tocar_nada(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Outro motor com a trava: o gesto recusa (o botão treme) e nada muda.

    O prazo da tela é 5 s por decisão de quem coordena; aqui ele encolhe para a
    régua não dormir, e a constante é conferida à parte.
    """
    assert cr.PRAZO_DA_TRAVA_DO_GESTO_S == 5.0
    assert cr.CentralDoRadio()._prazo_da_trava_s == 5.0
    central = _central(dono, mundo, relogio, prazo_da_trava_s=0.2)

    with diario_do_radio.trava_do_radio("vigia"):
        feito = central.comecar_a_mover(VERMELHO, QUARTO)

    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_OCUPADO)
    assert central.movimento_de(VERMELHO) is None, "a recusa não fica guardada"
    assert mundo.chamadas == []
    assert mundo.escritas == []
    central.fechar()


def test_o_gesto_da_tela_volta_logo_e_o_movimento_segue_no_fio(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """``comecar_a_mover`` devolve «esperando» sem esperar o gesto dela."""
    central = _central(dono, mundo, relogio)
    segurar = threading.Event()
    relogio.durante = lambda: segurar.wait(5)

    primeiro = central.comecar_a_mover(VERMELHO, QUARTO)
    assert primeiro.estado == cr.ESPERANDO
    # O mesmo pedido de novo devolve o MESMO movimento, sem abrir outro.
    assert central.comecar_a_mover(VERMELHO, QUARTO).aparelho == VERMELHO
    assert central.propor() is None, "com um movimento em curso, nada se propõe"

    relogio.durante = None
    mundo.segurar_ps_create(VERMELHO)
    segurar.set()
    central.fechar(espera=5.0)
    assert [c for c, _a in mundo.metodos("StartDiscovery")] == [rm.HCIS[QUARTO]]


# ---------------------------------------------------------------------------
# 7. a D8 e o «Equilibrar»
# ---------------------------------------------------------------------------


def _controle(u: str, adaptador: str, ponte: str | None = None) -> dict[str, Any]:
    return {
        "uniq": rm.uniq(u),
        "transport": "bt",
        "connected": True,
        "adaptador": adaptador,
        "ponte_do_radio": ponte,
    }


def test_a_d8_escolhe_mais_vaga_depois_menos_controles_e_quem_varre_por_ultimo(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    # Sala: duas pontes (cheia). Quarto: uma ponte. Varanda: vazia, mas varrendo.
    mundo._mudar(rm.HCIS[VARANDA], bd.ADAPTADOR, "Discovering", True)
    controles = [
        _controle(VERMELHO, SALA, "som"),
        _controle(AZUL, SALA, "haptica"),
        _controle(VERDE, QUARTO, "som"),
    ]
    assert central.escolher_destino(controles=controles) == QUARTO

    # Sem varredura, a varanda (vaga 2) ganha.
    mundo._mudar(rm.HCIS[VARANDA], bd.ADAPTADOR, "Discovering", False)
    relogio.agora += 10  # a foto dos adaptadores vale 2 s
    assert central.escolher_destino(controles=controles) == VARANDA

    # Empate na vaga: ganha o de menos controles.
    sem_ponte = [
        _controle(VERMELHO, SALA, "som"),
        _controle(AZUL, SALA, "haptica"),
        _controle(VERDE, QUARTO),
        _controle(rm.ROXO, QUARTO),
        _controle("aa:bb:cc:00:00:05", VARANDA),
    ]
    assert central.escolher_destino(controles=sem_ponte) == VARANDA


def test_mover_sem_destino_usa_a_d8_e_nunca_o_adaptador_de_agora(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    central.conhecer([_controle(VERMELHO, SALA), _controle(AZUL, SALA)])
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    feito = central.mover(VERMELHO)

    assert feito.estado == cr.CHEGOU
    assert feito.destino in (QUARTO, VARANDA)
    assert feito.destino != SALA


def test_a_d8_nunca_escolhe_o_adaptador_em_que_ele_ja_esta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A sala é a de MAIS vaga (o vermelho sozinho, sem ponte) — e é onde ele
    está. O mover sem destino não pode cair nela: seria um «já estava» mudo no
    lugar de um movimento.

    MORDIDA: tire o ``exceto`` do ``ordem_dos_destinos`` — a D8 devolve a sala e
    esta régua reprova. (A régua de cima não morde: lá a sala é a mais cheia.)
    """
    central = _central(dono, mundo, relogio)
    mesa = [
        _controle(VERMELHO, SALA),
        _controle(VERDE, QUARTO, "som"),
        _controle(AZUL, VARANDA, "som"),
        _controle(rm.ROXO, VARANDA, "haptica"),
    ]

    assert central.escolher_destino(controles=mesa) == SALA, "sem alvo, a sala ganha"
    assert central.escolher_destino(VERMELHO, controles=mesa) == QUARTO


def test_o_conectar_pareia_o_controle_novo_no_destino_da_d8(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O «Conectar» sem destino: a D8 escolhe, e o controle que aparece é o dela.

    A sala tem duas pontes; a varanda, um controle sem ponte; o quarto, nada —
    ganha o quarto (mesma vaga que a varanda, menos controles). O fone da
    vizinha em modo de pareamento aparece na mesma janela e fica de fora: não é
    controle pela classe.
    """
    mundo.pareado(VARANDA, rm.ROXO)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    mundo.fisicos[rm.FONE] = rm.Fisico(rm.FONE, rm.CLASSE_DE_FONE, pareando=True)
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    central.conhecer([
        _controle(VERMELHO, SALA, "som"),
        _controle(AZUL, SALA, "som"),
        _controle(rm.ROXO, VARANDA),
    ])
    _ela_segura_ps_create(mundo, relogio, VERDE)

    feito = central.conectar()

    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, VERDE, QUARTO)
    assert feito.origens == ()
    assert [c for c, _a in mundo.metodos("StartDiscovery")] == [rm.HCIS[QUARTO]]
    assert [c for c, _a in mundo.metodos("Pair")] == [rm.no_de(QUARTO, VERDE)]
    assert mundo.lapides == []
    assert [m.aparelho for m in central.movimentos()] == [VERDE], "a chave vira o endereço"


def test_o_conectar_de_quem_morava_em_outro_adaptador_e_um_mover(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
    assert feito.origens == (SALA,)
    assert mundo.lapides == [(SALA, VERMELHO)]
    assert mundo.objeto(SALA, AZUL) is not None


def test_o_conectar_ignora_o_que_o_destino_ja_conhecia(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Uma sobra de busca antiga no quarto não é quem ela está segurando.

    MORDIDA: tire o ``endereco not in antes`` — o ``Pair`` vai para a sobra,
    que não está pareando, e esta régua reprova.
    """
    sobra = rm.Fisico("aa:bb:cc:00:00:5a", rm.CLASSE_DE_CONTROLE)
    mundo.fisicos[sobra.endereco] = sobra
    mundo._achar(QUARTO, sobra)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERDE)

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERDE)


def test_o_conectar_sem_ninguem_na_janela_nao_chegou(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.motivo, feito.aparelho) == (
        cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO, cr.CONECTANDO
    )
    assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False
    assert mundo.metodos("Pair") == []


def test_o_equilibrar_propoe_um_e_so_depois_do_chegou_o_proximo(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Quatro pontes na sala (comporta 2): UMA ordem; depois do «chegou», a próxima.

    MORDIDA: tire o ``if self.em_curso: return None`` do ``propor`` — com o
    movimento «esperando», a régua recebe uma segunda ordem e reprova.
    """
    mundo.pareado(SALA, VERDE)
    mundo.pareado(SALA, rm.ROXO)
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    quatro = [
        _controle(VERMELHO, SALA, "som"),
        _controle(AZUL, SALA, "som"),
        _controle(VERDE, SALA, "haptica"),
        _controle(rm.ROXO, SALA, "som"),
    ]

    ordem = central.propor(quatro)
    assert ordem is not None
    assert ordem.origem == SALA and ordem.controle == rm.uniq(rm.ROXO)
    assert (ordem.pontes_na_origem_depois, ordem.pontes_no_destino_depois) == (3, 1)

    # Enquanto o roxo está «esperando», nada se propõe.
    mundo.pair_mente = True
    _ela_segura_ps_create(mundo, relogio, rm.ROXO)
    assert central.mover(rm.ROXO, ordem.destino).estado == cr.ESPERANDO
    assert central.propor(quatro) is None

    # O HID_PHYS confirma, a vigia esquece a origem, e a próxima ordem nasce.
    mundo.pair_mente = False
    mundo.fisicos[rm.ROXO].host = ordem.destino
    mundo.apertar_ps(rm.ROXO)
    central.vigiar()
    assert central.movimento_de(rm.ROXO).estado == cr.CHEGOU
    depois = [*quatro[:3], _controle(rm.ROXO, ordem.destino, "som")]
    proxima = central.propor(depois)
    assert proxima is not None
    assert proxima.controle == rm.uniq(VERDE)
    assert (proxima.pontes_na_origem_depois, proxima.pontes_no_destino_depois) == (2, 1)
    assert proxima.destino != ordem.destino, "o destino com mais vaga ganha"


def test_duas_mais_duas_nao_propoe_nada(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    central = _central(dono, mundo, relogio)
    mesa = [
        _controle(VERMELHO, SALA, "som"),
        _controle(AZUL, SALA, "som"),
        _controle(VERDE, QUARTO, "haptica"),
        _controle(rm.ROXO, QUARTO, "som"),
    ]
    assert central.propor(mesa) is None
    publicado = central.publicar(mesa)
    assert publicado == {"movimentos": [], "em_curso": False, "proposta": None}


# ---------------------------------------------------------------------------
# 8. a ponte não apaga o cache SDP do bond novo
# ---------------------------------------------------------------------------

_INFO_COM_CHAVE = "[General]\nName=controle\n\n[LinkKey]\nKey=00\nType=4\nPINLength=0\n"


def _ambiente_da_ponte(tmp_path: Path) -> dict[str, str]:
    env = {c: v for c, v in os.environ.items() if c not in ("SUDO_UID", "SUDO_USER")}
    env.update(
        HEFESTO_BT_LIB=str(tmp_path / "bluetooth"),
        HEFESTO_BT_LOG_DEST="none",
        HEFESTO_BT_LAPIDES=str(tmp_path / ".lapides"),
        HEFESTO_RADIO_DIARIO_ROOT=str(tmp_path / "diario-root.jsonl"),
        HEFESTO_SYS_BLUETOOTH=str(tmp_path / "sys-bluetooth"),
    )
    return env


def test_o_esquecer_da_origem_guarda_o_cache_sdp_do_bond_novo(tmp_path: Path) -> None:
    """Quando o esquecer roda, o controle JÁ tem bond novo no destino (a ordem
    nova), e o registro SDP daquele pareamento é o que o bluetoothd relê.

    MORDIDA: tire o ``_bond_com_chave`` do laço do cache — o cache do quarto
    some, e esta régua reprova.
    """
    # O BlueZ grava as pastas em MAIÚSCULAS, e a ponte as lê assim.
    lib = tmp_path / "bluetooth"
    sala, quarto, varanda, vermelho = (m.upper() for m in (SALA, QUARTO, VARANDA, VERMELHO))
    for adaptador in (sala, quarto):
        (lib / adaptador / vermelho).mkdir(parents=True)
        (lib / adaptador / vermelho / "info").write_text(_INFO_COM_CHAVE, encoding="utf-8")
        (lib / adaptador / "cache").mkdir()
        (lib / adaptador / "cache" / vermelho).write_text("[ServiceRecords]\n", encoding="utf-8")
    # A varanda só tem sobra de scan: cache sem bond.
    (lib / varanda / "cache").mkdir(parents=True)
    (lib / varanda / "cache" / vermelho).write_text("[ServiceRecords]\n", encoding="utf-8")

    resultado = subprocess.run(
        ["bash", str(PONTE), "esquecer", SALA, VERMELHO],
        capture_output=True,
        text=True,
        timeout=60,
        env=_ambiente_da_ponte(tmp_path),
    )

    assert resultado.returncode == 0, resultado.stderr
    assert not (lib / sala / vermelho).exists()
    assert not (lib / sala / "cache" / vermelho).exists()
    assert (lib / quarto / vermelho / "info").exists()
    assert (lib / quarto / "cache" / vermelho).exists(), "o SDP do bond novo sobrevive"
    assert not (lib / varanda / "cache" / vermelho).exists(), "a sobra de scan sai"
    [lapide] = (tmp_path / ".lapides").read_text(encoding="utf-8").splitlines()
    assert lapide.split()[1:] == [sala, vermelho]


# ---------------------------------------------------------------------------
# 9. o IPC e o arranque: o parear é pelo daemon
# ---------------------------------------------------------------------------


def _handlers(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo

    return _Handlers(daemon)


def _esperar(condicao: Any, teto: float = 5.0) -> bool:
    import time

    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


@pytest.mark.asyncio
async def test_o_ipc_radio_mover_move_pela_central(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """``radio.mover`` com o ``uniq`` que o «Equilibrar» publica: volta
    «esperando» na hora, e o movimento segue no fio da central.

    MORDIDA: faça o handler responder ``ok`` sem chamar a central — o vermelho
    não sai da sala, e esta régua reprova.
    """
    from types import SimpleNamespace

    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERMELHO)
    handlers = _handlers(SimpleNamespace(_central_do_radio=central))

    pedido = {"aparelho": rm.uniq(VERMELHO), "destino": QUARTO}
    resposta = await handlers._handle_radio_mover(pedido)

    assert resposta["status"] == "ok"
    assert resposta["movimento"]["aparelho"] == VERMELHO
    assert resposta["movimento"]["estado"] in (cr.ESPERANDO, cr.CHEGOU)
    assert _esperar(lambda: central.movimento_de(VERMELHO).estado == cr.CHEGOU)
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    central.fechar()


@pytest.mark.asyncio
async def test_o_ipc_sem_aparelho_e_o_conectar(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    from types import SimpleNamespace

    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    central = _central(dono, mundo, relogio)
    _ela_segura_ps_create(mundo, relogio, VERDE)
    handlers = _handlers(SimpleNamespace(_central_do_radio=central))

    resposta = await handlers._handle_radio_mover({"destino": QUARTO})

    assert resposta["status"] == "ok"
    assert _esperar(lambda: (central.movimento_de(VERDE) or cr.Movimento("", "", "", "")).estado
                    == cr.CHEGOU)
    central.fechar()


@pytest.mark.asyncio
async def test_o_ipc_ocupado_e_a_recusa_e_o_parametro_torto_levanta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    from types import SimpleNamespace

    central = _central(dono, mundo, relogio, prazo_da_trava_s=0.2)
    handlers = _handlers(SimpleNamespace(_central_do_radio=central))

    with diario_do_radio.trava_do_radio("vigia"):
        resposta = await handlers._handle_radio_mover({"aparelho": VERMELHO, "destino": QUARTO})
    assert resposta["status"] == "ocupado"
    assert mundo.chamadas == []

    with pytest.raises(ValueError):
        await handlers._handle_radio_mover({"aparelho": 5})
    with pytest.raises(ValueError):
        await handlers._handle_radio_mover({"aparelho": VERMELHO, "destino": ["x"]})
    sem = _handlers(SimpleNamespace(_central_do_radio=None))
    assert await sem._handle_radio_mover({"aparelho": VERMELHO}) == {"status": "sem_central"}
    central.fechar()


def test_radio_mover_e_o_ultimo_metodo_da_tabela() -> None:
    """Método IPC novo vai no FIM da tabela — regra da leva."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py").read_text(encoding="utf-8")
    ultimo = fonte.index('"radio.mover": self._handle_radio_mover,')
    fecha = fonte.index("\n        }\n", ultimo)
    assert fonte[ultimo:fecha].count('": self._handle_') == 1, "radio.mover não é o último"


@pytest.mark.asyncio
async def test_o_state_full_publica_a_central(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """``state_full["radio_central"]`` sai do dono (a central), num suppress próprio.

    MORDIDA: tire o bloco ``radio_central`` do ``_enriquecer_e_medir_o_ar`` — a
    chave some e esta régua reprova.
    """
    import time

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(transport="bt"))
    daemon.controller.describe_controllers = lambda: []  # type: ignore[attr-defined]
    daemon._central_do_radio = _central(dono, mundo, relogio)

    class _Estado(type(_handlers(daemon))):  # type: ignore[misc]
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo
            self.store = alvo.store
            self.controller = alvo.controller

    handlers = _Estado(daemon)
    handlers._afh_lido_em = time.monotonic()
    payload = await handlers._handle_daemon_state_full({})

    assert payload["radio_central"] == {"movimentos": [], "em_curso": False, "proposta": None}


@pytest.mark.asyncio
async def test_o_daemon_abre_o_dono_no_arranque_fora_do_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O dono do BlueZ abre no arranque, num fio — nunca no laço, nunca na tela.

    MORDIDA: tire o ``_start_central_do_radio`` do ``run()`` — esta régua
    reprova pelo fonte; chame o ``ligar`` direto no laço — reprova pelo fio.
    """
    import inspect

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    fios: list[str] = []
    monkeypatch.setattr(
        cr.CentralDoRadio, "ligar", lambda self: fios.append(threading.current_thread().name)
    )
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_FAKE", raising=False)
    daemon = Daemon(controller=FakeController(transport="bt"))

    await daemon._start_central_do_radio()

    assert isinstance(daemon._central_do_radio, cr.CentralDoRadio)
    assert fios and fios[0] != threading.main_thread().name
    assert '"central_do_radio", self._start_central_do_radio' in inspect.getsource(Daemon.run)

    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    falso = Daemon(controller=FakeController(transport="bt"))
    await falso._start_central_do_radio()
    assert falso._central_do_radio is None, "o daemon de fumaça não pareia nada"


def test_o_movimento_da_central_vem_do_sensor_hub_do_ipc() -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.testing import FakeController

    perguntas: list[str] = []

    def hz(uniq: str) -> float:
        perguntas.append(uniq)
        return 248.0

    hub = SimpleNamespace(hz_do_movimento=hz)
    daemon = Daemon(controller=FakeController(transport="bt"))
    assert daemon._movimento_para_a_central("aabbcc000001") is None
    daemon._ipc_server = SimpleNamespace(_garantir_sensor_hub=lambda: hub)
    assert daemon._movimento_para_a_central("aabbcc000001") == 248.0
    assert perguntas == ["aabbcc000001"]


# ---------------------------------------------------------------------------
# 10. o alias do `bt_active_mode.sh` vai dentro da trava
# ---------------------------------------------------------------------------
#
# Decisão de quem coordena (23/09): o script que prefixa «Nintendo» renomeia
# DENTRO da trava comum. A bancada é a do N-IGUAL-A-UM-01 — três adaptadores de
# mentira, `busctl` e `id` dublês —, e o dublê do `busctl` pergunta à trava, no
# instante do `set-property`, se ela está presa.


def _bancada_com_trava(tmp_path: Path) -> tuple[Any, Path, Path]:
    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import Bancada

    banca = Bancada(tmp_path)
    trava = tmp_path / "run" / "radio.lock"
    trava.parent.mkdir()
    real = banca.fakes / "busctl-real"
    (banca.fakes / "busctl").rename(real)
    no_instante = tmp_path / "trava-no-set-property.txt"
    (banca.fakes / "busctl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "set-property" ]]; then\n'
        f"    if flock -n '{trava}' true; then echo livre; else echo presa; fi >> '{no_instante}'\n"
        "fi\n"
        f"exec '{real}' \"$@\"\n",
        encoding="utf-8",
    )
    (banca.fakes / "busctl").chmod(0o755)
    return banca, trava, no_instante


def _ambiente_do_script(banca: Any, trava: Path, **extra: str) -> dict[str, str]:
    return {
        "PATH": ":".join([str(banca.fakes), "/usr/bin", "/bin"]),
        "HOME": str(banca.tmp),
        "LANG": os.environ.get("LANG", "pt_BR.UTF-8"),
        "HEFESTO_SYS_BLUETOOTH": str(banca.sys_bt),
        "HEFESTO_BT_LIB": str(banca.lib),
        "HEFESTO_BT_LOG_DEST": str(banca.log),
        "HEFESTO_RADIO_TRAVA": str(trava),
        **extra,
    }


ATIVO = RAIZ / "scripts" / "bt_active_mode.sh"


def test_o_alias_e_escrito_com_a_trava_na_mao(tmp_path: Path) -> None:
    """MORDIDA: tire o ``_na_trava`` do laço do alias — o ``set-property`` roda
    com a trava livre, e esta régua reprova."""
    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import (
        HOSPEDEIRO_DO_PRO,
    )

    banca, trava, no_instante = _bancada_com_trava(tmp_path)

    feito = subprocess.run(
        ["bash", str(ATIVO), "--quiet"], capture_output=True, text=True, timeout=60,
        env=_ambiente_do_script(banca, trava),
    )

    assert feito.returncode == 0, feito.stderr
    assert HOSPEDEIRO_DO_PRO in banca.aliases_escritos()
    assert no_instante.read_text(encoding="utf-8").split() == ["presa"]


def test_com_outro_motor_na_trava_o_alias_espera_o_prazo_e_desiste(tmp_path: Path) -> None:
    import fcntl

    banca, trava, _no_instante = _bancada_com_trava(tmp_path)
    with open(trava, "a+") as outro_motor:
        fcntl.flock(outro_motor, fcntl.LOCK_EX)
        feito = subprocess.run(
            ["bash", str(ATIVO), "--quiet"], capture_output=True, text=True, timeout=60,
            env=_ambiente_do_script(banca, trava, HEFESTO_RADIO_TRAVA_PRAZO_S="1"),
        )

    assert feito.returncode == 0, feito.stderr
    assert banca.aliases_escritos() == {}, "escreveu por cima de outro motor"
    assert "outro motor segura a trava do rádio" in banca.log.read_text(encoding="utf-8")


def test_a_trava_herdada_do_watchdog_nao_espera_o_proprio_pai(tmp_path: Path) -> None:
    """O watchdog chama o script com o tique inteiro na trava, e o descritor vem
    junto. Sem reconhecê-lo, o filho esperaria o pai o prazo inteiro e o alias
    nunca sairia de dentro do tique.

    MORDIDA: tire o laço do ``/proc/$$/fd`` — o filho espera o prazo, desiste,
    e esta régua reprova.
    """
    import time

    from tests.unit.test_o_prefixo_vai_no_adaptador_que_hospeda_nintendo import (
        HOSPEDEIRO_DO_PRO,
    )

    banca, trava, no_instante = _bancada_com_trava(tmp_path)
    tique = (
        f"exec {{fd}}<>'{trava}' && flock -n \"$fd\" || exit 9\n"
        f"bash '{ATIVO}' --quiet\n"
    )
    antes = time.monotonic()
    feito = subprocess.run(
        ["bash", "-c", tique], capture_output=True, text=True, timeout=60,
        env=_ambiente_do_script(banca, trava, HEFESTO_RADIO_TRAVA_PRAZO_S="3"),
    )

    assert feito.returncode == 0, feito.stderr
    assert time.monotonic() - antes < 3.0, "o filho esperou o próprio pai"
    assert HOSPEDEIRO_DO_PRO in banca.aliases_escritos()
    assert no_instante.read_text(encoding="utf-8").split() == ["presa"]
