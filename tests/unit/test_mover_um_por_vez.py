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


# ---------------------------------------------------------------------------
# 5. idempotência
# ---------------------------------------------------------------------------


def test_mover_duas_vezes_nao_move_duas(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """O segundo diff é vazio: nenhuma chamada e nenhuma escrita no rádio.

    MORDIDA: tire o atalho do «já está lá» — o segundo mover abre outra janela
    e esta régua reprova.
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
