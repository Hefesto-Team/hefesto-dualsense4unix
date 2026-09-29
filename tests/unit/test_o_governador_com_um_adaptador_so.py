"""O governador com um adaptador só — O-GOVERNADOR-COM-UM-ADAPTADOR-SO-01 (28/09/2026).

Duas coisas que a auditoria de 27/09 mediu no governador do rádio, as duas
numa máquina com um adaptador só:

* **«Não sei» não é «não há».** Com o medidor de ar no daemon e sem amostra
  (o daemon que reinicia com o jogo aberto), a terceira ponte subia além do
  limite sem pergunta, e o diário dizia «não há vaga em outro adaptador», um
  fato que ninguém mediu. Agora ela espera a primeira janela medida (a
  :class:`~hefesto_dualsense4unix.daemon.subsystems.governador_do_radio.Recusa`
  sem pergunta publicada), e o governador acorda a volta quando a medida
  chega. Passado o teto sem medida, vale a R4, e o diário diz «não sei».
* **Cede só quem não cabe, e cada um na sua vez.** Três pontes num adaptador
  que escoa duas cediam juntas e voltavam juntas: cada uma ficava com metade.
  Agora cabem as que a saída medida comporta, o resto cede, e a vez gira pela
  ordem da vaga, nunca pelo número do jogador.

Nada aqui abre socket de Bluetooth, lê o sysfs dela ou escreve no diário dela:
o medidor é um dublê que publica o que o real publica (o ``ArDoAdaptador``), e
o diário é uma lista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import diario_do_radio as diario
from tests.unit.test_o_governador_do_radio import (
    ADAPTADOR_A,
    ADAPTADOR_B,
    CONTROLE_1,
    CONTROLE_2,
    CONTROLE_3,
    _AdaptadorQueEscoaDuas,
    _Diario,
    _Relogio,
)

CONTROLE_4 = "aa:bb:cc:00:00:04"
QUATRO = (CONTROLE_1, CONTROLE_2, CONTROLE_3, CONTROLE_4)

#: Cinco minutos de janelas do governador.
CINCO_MINUTOS = int(300 / gov.PERIODO_S)
#: 93,75 quadros por segundo numa janela de 250 ms.
POR_JANELA = 93.75 * gov.PERIODO_S


# ---------------------------------------------------------------------------
# os dublês
# ---------------------------------------------------------------------------
@dataclass
class _MedidorDaMesa:
    """Os adaptadores que o kernel lista, com o ``motivo`` de cada um.

    ``None`` num adaptador é a primeira leitura (sem taxa, mas listado), como
    o ``MedidorDeAr`` real devolve na primeira foto; ``falha=True`` levanta,
    como um ioctl que o kernel não respondeu antes de listar.
    """

    motivos: dict[str, str] = field(default_factory=lambda: {ADAPTADOR_A: ""})
    falha: bool = False
    chamadas: int = 0

    def amostrar(self) -> dict[str, ar.ArDoAdaptador]:
        self.chamadas += 1
        if self.falha:
            raise OSError("o kernel não respondeu")
        return {
            endereco: ar.ArDoAdaptador(
                hci=i,
                endereco=endereco,
                janela_s=gov.PERIODO_S,
                motivo=motivo or ar.PRIMEIRA_LEITURA,
                conexoes=(),
            )
            for i, (endereco, motivo) in enumerate(self.motivos.items())
        }


class _Volta:
    """Quem o ``ao_autorizar`` acorda: o subsystem do som, de mentira."""

    def __init__(self) -> None:
        self.acordou: list[str] = []

    def __call__(self, uniq: str) -> None:
        self.acordou.append(uniq)


def _governador(medidor: Any, relogio: _Relogio, registro: _Diario) -> gov.GovernadorDoRadio:
    return gov.GovernadorDoRadio(
        medidor=medidor,
        adaptador_de=lambda _u: ADAPTADOR_A,
        registrar=registro,
        relogio=relogio,
    )


def _duas_de_pe(governador: gov.GovernadorDoRadio) -> None:
    for uniq in (CONTROLE_1, CONTROLE_2):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga) and not vaga.alem_do_limite
        vaga.subiu("som")


def _partes(
    ordem: tuple[str, ...],
    *,
    sem_escrita: tuple[str, ...] = (),
    medidor: _AdaptadorQueEscoaDuas | None = None,
) -> tuple[dict[str, float], list[gov.Vaga], gov.GovernadorDoRadio, _Diario]:
    """Cinco minutos de pontes num adaptador que escoa duas.

    Cada ponte com escrita pede ~23,4 quadros por janela; a que cede não
    escreve. Devolve, por controle, a parte do que pediu que foi para o ar.
    A ponte ``sem_escrita`` está de pé e não escreve nada (a bomba não escreve
    o silêncio).
    """
    relogio, registro = _Relogio(), _Diario()
    medidor = medidor or _AdaptadorQueEscoaDuas()
    governador = _governador(medidor, relogio, registro)
    governador.tique()  # a primeira amostra: o adaptador A existe
    vagas: list[gov.Vaga] = []
    for uniq in ordem:
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga), f"{uniq} não recebeu vaga: {vaga}"
        vaga.subiu("som")
        vagas.append(vaga)
    pedidas = dict.fromkeys(ordem, 0)
    no_ar = dict.fromkeys(ordem, 0)
    sobra = 0.0
    for _ in range(CINCO_MINUTOS):
        sobra += POR_JANELA
        por_ponte, sobra = int(sobra), sobra - int(sobra)
        escritas = 0
        for vaga in vagas:
            if vaga.uniq in sem_escrita:
                continue
            pedidas[vaga.uniq] += por_ponte
            if vaga.cedendo:
                continue
            for _ in range(por_ponte):
                vaga.contar_escrita()
            no_ar[vaga.uniq] += por_ponte
            escritas += por_ponte
        medidor.janela(escritas)
        relogio.agora += gov.PERIODO_S
        governador.tique()
    partes = {u: no_ar[u] / pedidas[u] for u in ordem if u not in sem_escrita}
    return partes, vagas, governador, registro


# ---------------------------------------------------------------------------
# 1. «não sei» não é «não há»
# ---------------------------------------------------------------------------
def test_sem_amostra_a_terceira_espera_a_medida_e_nao_sobe_alem_do_limite() -> None:
    """O daemon que reinicia com o jogo aberto: medidor no ar, nenhuma janela.

    A terceira ponte num adaptador com duas não sobe além do limite sem que
    ninguém tenha medido os outros adaptadores. Ela recebe uma ``Recusa`` sem
    pedido publicado (a tela não pergunta nada) e espera a medida.

    MORDIDA: tire a guarda do «não sei» em ``pedir_vaga`` e a primeira volta
    sobe além do limite, com o diário dizendo «não há vaga em outro adaptador».
    """
    relogio, registro = _Relogio(), _Diario()
    medidor = _MedidorDaMesa({ADAPTADOR_A: "", ADAPTADOR_B: ""})
    governador = _governador(medidor, relogio, registro)
    _duas_de_pe(governador)

    espera = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(espera, gov.Recusa), "sem medida a terceira subiu além do limite"
    assert espera.motivo == gov.MOTIVO_SEM_MEDIDA
    assert espera.vagas == ()
    assert governador.publicar()[ADAPTADOR_A]["pedidos"] == [], (
        "o «não sei» virou pergunta na tela"
    )
    assert registro.de(gov.ADAPTADOR_CHEIO) == []
    assert "vaga" not in espera.frase, "a frase afirmou vaga sem medida"

    # A primeira janela: A e B de pé. Agora a terceira tem para onde ir (R3).
    governador.tique()
    recusa = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(recusa, gov.Recusa)
    assert (recusa.motivo, recusa.vagas) == (gov.MOTIVO_CHEIO, (ADAPTADOR_B,))


def test_com_so_o_adaptador_dela_na_amostra_vale_a_r4_medida() -> None:
    """Uma janela medida com só o A: aí sim, «não há vaga em outro adaptador».

    MORDIDA: responda «não sei» mesmo com a amostra na mão e a terceira nunca
    sobe; escreva «não sei» no diário também aqui e a frase reprova.
    """
    relogio, registro = _Relogio(), _Diario()
    governador = _governador(_MedidorDaMesa({ADAPTADOR_A: ""}), relogio, registro)
    _duas_de_pe(governador)
    governador.tique()
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga) and vaga.alem_do_limite is True
    vaga.subiu("som")
    [subida] = [e for e in registro.de(diario.PONTE_SUBIU) if e["controle"] == CONTROLE_3]
    assert subida["por_que"] == "não há vaga em outro adaptador"


def test_a_primeira_janela_medida_acorda_quem_espera() -> None:
    """A medida chega e a volta do som acorda, em vez de esperar os 5 s dela.

    MORDIDA: tire do ``tique`` o aviso a quem espera a medida e a volta não
    acorda; a terceira fica muda até o ``RECONCILIA_S`` seguinte.
    """
    relogio, registro, volta = _Relogio(), _Diario(), _Volta()
    governador = _governador(_MedidorDaMesa({ADAPTADOR_A: ""}), relogio, registro)
    governador.ao_autorizar = volta
    _duas_de_pe(governador)
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert volta.acordou == []
    relogio.agora += gov.PERIODO_S
    governador.tique()
    assert volta.acordou == [CONTROLE_3], "a medida chegou e ninguém acordou a volta"
    governador.tique()
    assert volta.acordou == [CONTROLE_3], "acordou duas vezes pela mesma espera"


def test_outro_adaptador_que_nao_se_leu_e_nao_sei() -> None:
    """O adaptador cuja leitura falhou (``IOCTL_FALHOU``) não sai da conta
    como se não existisse: ele é «não sei», e a terceira espera.

    MORDIDA: conte o ``IOCTL_FALHOU`` como adaptador fora e a terceira sobe na
    hora, com o diário dizendo «não há».
    """
    relogio, registro = _Relogio(), _Diario()
    medidor = _MedidorDaMesa({ADAPTADOR_A: "", ADAPTADOR_B: ar.IOCTL_FALHOU})
    governador = _governador(medidor, relogio, registro)
    governador.tique()
    _duas_de_pe(governador)
    espera = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(espera, gov.Recusa) and espera.motivo == gov.MOTIVO_SEM_MEDIDA
    # O adaptador desligado é um fato medido: não é vaga, e não é «não sei».
    medidor.motivos[ADAPTADOR_B] = ar.ADAPTADOR_DESLIGADO
    governador.tique()
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga) and vaga.alem_do_limite is True


def test_sem_cabo_o_governador_sem_medidor_segue_como_antes() -> None:
    """Sem medidor (o modo falso) não há medida a esperar: a R4 é a de sempre."""
    relogio, registro = _Relogio(), _Diario()
    governador = _governador(None, relogio, registro)
    _duas_de_pe(governador)
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga) and vaga.alem_do_limite is True


# ---------------------------------------------------------------------------
# 2. o teto do «não sei»
# ---------------------------------------------------------------------------
def test_o_medidor_que_sempre_falha_cede_a_r4_no_teto_e_o_diario_diz_nao_sei() -> None:
    """Um medidor que nunca responde: passado o teto, a ponte sobe (R4), e o
    diário diz «não sei», nunca «não há».

    MORDIDAS: sem o teto a ponte nunca sobe; com o «não há» a frase reprova.
    """
    relogio, registro, volta = _Relogio(), _Diario(), _Volta()
    governador = _governador(_MedidorDaMesa(falha=True), relogio, registro)
    governador.ao_autorizar = volta
    _duas_de_pe(governador)
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)

    while relogio.agora - 100.0 < gov.TETO_DO_NAO_SEI_S:
        relogio.agora += gov.PERIODO_S
        governador.tique()
        if relogio.agora - 100.0 < gov.TETO_DO_NAO_SEI_S:
            assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert volta.acordou == [CONTROLE_3], "o teto passou e ninguém acordou a volta"
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga), "passado o teto, a ponte seguiu esperando"
    assert vaga.alem_do_limite is True and vaga.por_escolha_dela is False
    vaga.subiu("som")
    [subida] = [e for e in registro.de(diario.PONTE_SUBIU) if e["controle"] == CONTROLE_3]
    assert subida["por_que"] == "não sei se há vaga em outro adaptador"
    assert "não há" not in subida["por_que"]

    # A ponte que desce e sobe de novo, ainda sem medida, não espera outra vez.
    vaga.soltar("sem som")
    de_novo = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(de_novo, gov.Vaga), "cada volta do som esperou o teto de novo"


# ---------------------------------------------------------------------------
# 3 a 6. cede só quem não cabe, e cada um na sua vez
# ---------------------------------------------------------------------------
def _diferenca(partes: dict[str, float]) -> float:
    return max(partes.values()) - min(partes.values())


def test_tres_pontes_num_adaptador_que_escoa_duas_dividem_por_igual() -> None:
    """Três com escrita, capacidade para duas: cada uma põe no ar pelo menos
    60% do que pediu, com até 10 p.p. de diferença, e nenhuma cai.

    MORDIDA: devolva o ceder do adaptador inteiro no ``_as_bordas`` e cada uma
    fica em 50%.
    """
    partes, vagas, _g, registro = _partes((CONTROLE_1, CONTROLE_2, CONTROLE_3))
    assert min(partes.values()) >= 0.60, partes
    assert _diferenca(partes) <= 0.10, partes
    assert not any(v.derrubar for v in vagas), "a divisão virou queda"
    assert registro.de(gov.FILA_PARADA) == []
    assert len(registro.de(gov.CEDEU_NA_FONTE)) <= 6


def test_quatro_pontes_dividem_por_igual() -> None:
    """Quatro, capacidade para duas: metade para cada, sem ninguém a zero.

    Esta régua guarda a DIVISÃO, e não o ganho: com o ceder do adaptador
    inteiro também dava 50%.

    MORDIDA: a mesma da régua da ordem — as ``n`` primeiras escrevem e o resto
    cede — e as duas últimas ficam em zero.
    """
    partes, vagas, _g, _r = _partes(QUATRO)
    assert min(partes.values()) >= 0.45, partes
    assert _diferenca(partes) <= 0.10, partes
    assert not any(v.derrubar for v in vagas)


def test_a_ponte_sem_escrita_nao_toma_a_vez() -> None:
    """Três com escrita e uma de pé sem escrever: as três seguem com 60%, e
    com a MESMA parte que teriam sem a quarta de pé.

    MORDIDA: conte e gire por toda vaga de pé. Medido em 28/09: a conta da
    fila compensa em parte (a vez da calada é uma a menos cedendo, a fila
    cresce e cabe uma a menos na janela seguinte), e as três caem de 66,8%
    para 63%; a comparação com as três sozinhas é o que reprova.
    """
    ordem = (CONTROLE_1, CONTROLE_4, CONTROLE_2, CONTROLE_3)
    partes, _v, _g, _r = _partes(ordem, sem_escrita=(CONTROLE_4,))
    assert set(partes) == {CONTROLE_1, CONTROLE_2, CONTROLE_3}
    assert min(partes.values()) >= 0.60, partes
    assert _diferenca(partes) <= 0.10, partes
    sozinhas, _v, _g, _r = _partes((CONTROLE_1, CONTROLE_2, CONTROLE_3))
    for uniq, parte in partes.items():
        assert abs(parte - sozinhas[uniq]) <= 0.01, (
            f"a ponte sem escrita mudou a parte de {uniq}: {parte:.3f} contra {sozinhas[uniq]:.3f}"
        )


@pytest.mark.parametrize(
    "ordem",
    [(CONTROLE_1, CONTROLE_2, CONTROLE_3), (CONTROLE_3, CONTROLE_2, CONTROLE_1)],
    ids=["chegada", "invertida"],
)
def test_a_ordem_de_chegada_nao_escolhe_quem_perde(ordem: tuple[str, ...]) -> None:
    """A régua das três com a ordem de chegada invertida dá as mesmas partes.

    MORDIDA: «as ``n`` primeiras escrevem, o resto cede» e a última fica em
    zero.
    """
    partes, _v, _g, _r = _partes(ordem)
    assert min(partes.values()) >= 0.60, partes
    assert _diferenca(partes) <= 0.10, partes


def test_o_adaptador_parado_segue_cedendo_inteiro() -> None:
    """Quando não cabe nenhuma (o 2B), cede o adaptador inteiro, como antes, e
    o teto derruba as pontes."""
    _p, vagas, _g, registro = _partes(
        (CONTROLE_1, CONTROLE_2, CONTROLE_3), medidor=_AdaptadorQueEscoaDuas(capacidade=0)
    )
    assert all(v.derrubar for v in vagas), "o adaptador parado não caiu no teto"
    assert len(registro.de(gov.FILA_PARADA)) >= 1


# ---------------------------------------------------------------------------
# 7. o cabo
# ---------------------------------------------------------------------------
def test_a_vaga_do_cabo_nunca_cede_nem_entra_na_conta() -> None:
    """A vaga sem adaptador (o cabo, ou o controle sem casa) sobe sem conta e
    fica fora da vez: nunca cede, e nenhum estado de adaptador nasce para ela.

    MORDIDA: tire o ``if vaga.adaptador`` do agrupamento do tique e o «não sei»
    do vazio vira um estado de adaptador sem endereço.
    """
    relogio, registro = _Relogio(), _Diario()
    medidor = _AdaptadorQueEscoaDuas()
    onde = {CONTROLE_4: ""}
    governador = gov.GovernadorDoRadio(
        medidor=medidor,
        adaptador_de=lambda u: onde.get(u, ADAPTADOR_A),
        registrar=registro,
        relogio=relogio,
    )
    governador.tique()
    cabo = governador.pedir_vaga(CONTROLE_4, "som")
    assert isinstance(cabo, gov.Vaga) and cabo.adaptador == ""
    cabo.subiu("som")
    vagas = []
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_3):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu("som")
        vagas.append(vaga)
    sobra = 0.0
    for _ in range(400):
        sobra += POR_JANELA
        por_ponte, sobra = int(sobra), sobra - int(sobra)
        escritas = 0
        for vaga in [*vagas, cabo]:
            if vaga.cedendo:
                continue
            for _ in range(por_ponte):
                vaga.contar_escrita()
            if vaga.adaptador:
                escritas += por_ponte
        medidor.janela(escritas)
        relogio.agora += gov.PERIODO_S
        governador.tique()
        assert cabo.cedendo is False, "a vaga do cabo cedeu"
    assert "" not in governador._estados, "o cabo ganhou estado de adaptador"
    assert "" not in governador.publicar()
    assert any(v.cedendo for v in vagas) or registro.de(gov.CEDEU_NA_FONTE), (
        "o dublê não congestionou o A"
    )
