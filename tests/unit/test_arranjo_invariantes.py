"""As invariantes do motor do arranjo — e a mordida de cada regra.

Cada uma nasceu de um defeito real da noite de 24/08/2026, quando o motor ainda
era JavaScript. O teste de equivalência
(``test_arranjo_da_mesa_bate_com_o_mockup.py``) prova que o porte calcula igual;
este prova **por que o cálculo é assim**, e o que volta a quebrar se a regra sair.

AS DUAS QUE SALVAM A CREDIBILIDADE, MEDIDAS EM 25/08/2026
----------------------------------------------------------

* **intercambiável não troca com o irmão** — arrancada, a receita salta de
  **5 para 7** movimentos, e os dois a mais são dois UB500 idênticos trocando de
  lugar entre a entrada 9 e a 15a. Trabalho puro, ganho zero;
* **ficar parado vale bônus** — arrancado, ``Mexendo o mínimo`` salta de **4 para
  6** movimentos: a webcam muda de entrada à toa, e o cabo do hub sai de uma
  entrada para outra igualzinha.

A INVARIANTE ``mapa = receita`` FECHOU EM 25/08, E ESTE ARQUIVO É O PORTÃO DELA
--------------------------------------------------------------------------------

Até a manhã de 25/08 ela valia em ``O melhor no papel`` e ``Mexendo o mínimo`` e
FALHAVA nas duas variantes que proíbem a entrada de hoje: o plano desenhava o
dongle saindo do hub, a receita não mandava tirá-lo, e quem olhava a tela via o
aparelho noutro lugar **sem instrução nenhuma**. Havia um terceiro furo que
ninguém tinha visto, e ele aparecia sem variante nenhuma: com
``bonus_parado=0`` o mapa mandava o cabo do hub da entrada 4 para a 3 — o Wi-Fi
tinha tomado a 4 — e a receita calava.

A ``D-MAPA-SEM-RECEITA`` (25/08/2026) fechou os três com uma frase dela: *"se não
há ordem, o mapa não move nada. Uma verdade só na tela: o desenho mostra o que a
receita manda fazer."* Hoje ``planejar()`` e ``receita()`` perguntam à MESMA
função (``_receita_manda_mover``), e o §5 daqui arranca o passe para ver os três
furos voltarem.

O QUE **NÃO** VALE NO MOTOR QUE RODA, e está medido em vez de escondido
------------------------------------------------------------------------

**Ponto fixo** vale em três das quatro variantes; ``Sem usar o hub`` continua
precisando de uma segunda volta para estabilizar. Isso é registro de medição, e
o teste que o nomeia está no §6.
"""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import radio_da_mesa as radio
from tests.unit import mesa_do_mockup as mock

MELHOR = motor.variante_por_id("melhor").opcoes
POUCOS = motor.variante_por_id("poucos").opcoes
SEM_EXT = motor.variante_por_id("sem-ext").opcoes
SO_PC = motor.variante_por_id("so-pc").opcoes

#: a quinta opção, que não é variante: o bônus de ficar parado desligado. Ela
#: entra aqui porque é onde mora o terceiro furo de ``mapa = receita``.
SEM_BONUS = motor.Opcoes(bonus_parado=0)

TODAS = [("melhor", MELHOR), ("poucos", POUCOS), ("sem-ext", SEM_EXT),
         ("so-pc", SO_PC), ("sem-bonus", SEM_BONUS)]


def movimentos(mesa: motor.Mesa, op: motor.Opcoes | None = None) -> list[str]:
    """Os títulos da receita, sem a linha de fecho que não é movimento."""
    return [m.titulo for m in motor.receita(mesa, op) if not m.sem_numero]


@pytest.fixture
def sem_a_regra_do_irmao() -> Iterator[None]:
    """Arranca o passe dos intercambiáveis — a cura da MOTOR-2, linha 4."""
    guardado = motor._intercambiaveis_ficam
    motor._intercambiaveis_ficam = lambda *a, **k: None  # type: ignore[assignment]
    try:
        yield
    finally:
        motor._intercambiaveis_ficam = guardado  # type: ignore[assignment]


@pytest.fixture
def sem_a_cura_do_mapa() -> Iterator[None]:
    """Arranca o passe da ``D-MAPA-SEM-RECEITA`` — o mapa volta a mover calado."""
    guardado = motor._o_mapa_so_move_o_que_a_receita_manda
    motor._o_mapa_so_move_o_que_a_receita_manda = lambda *a, **k: None  # type: ignore[assignment]
    try:
        yield
    finally:
        motor._o_mapa_so_move_o_que_a_receita_manda = guardado  # type: ignore[assignment]


# ══ A REGRA 1: intercambiável não troca com o irmão ══════════════════════


def test_dois_dongles_identicos_nao_trocam_de_lugar_entre_si() -> None:
    """Com a regra, a receita de 24/08 tem 5 movimentos e nenhum é troca de irmãos."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    assert len(movimentos(mesa)) == 5
    plano = motor.planejar(mesa).plano
    # os dois UB500 que já estão em 9 e 15a continuam em 9 e 15a
    assert plano["9"] == "bt-a"
    assert plano["15a"] == "bt-b"


@pytest.mark.usefixtures("sem_a_regra_do_irmao")
def test_arrancada_a_regra_do_irmao_a_receita_salta_de_cinco_para_sete() -> None:
    """A MORDIDA: sem ela, dois UB500 idênticos trocam de lugar, sem ganho nenhum."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    saltou = movimentos(mesa)
    assert len(saltou) == 7, saltou
    assert "Mova o dongle Bluetooth da entrada 15a para a 9" in saltou
    assert any(t.startswith("Mova o dongle Bluetooth da entrada 9 para a 15a") for t in saltou)


# ══ A REGRA 2: ficar parado vale bônus ═══════════════════════════════════


def test_o_bonus_de_ficar_parado_so_desempata() -> None:
    """+1 mantém o hub na entrada em que está; sem ele, o plano o troca de lugar à toa."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    assert motor.planejar(mesa, MELHOR).plano["4"] == "hub"  # é onde ele já está
    sem_bonus = motor.planejar(mesa, SEM_BONUS).plano
    assert sem_bonus["3"] == "hub"
    assert sem_bonus.get("4") != "hub"


def test_arrancado_o_bonus_mexendo_o_minimo_manda_mexer_em_mais() -> None:
    """A MORDIDA: 4 movimentos viram 6, e os dois a mais são trabalho puro.

    Um deles — o cabo do hub saindo da 4 para a 3 — só APARECE na receita desde
    a ``D-MAPA-SEM-RECEITA``. Antes dela o mapa já desenhava essa troca e
    ninguém a mandava, o que a fazia parecer barata: 4 viravam 5.
    """
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    com = movimentos(mesa, POUCOS)
    sem = movimentos(mesa, motor.Opcoes(bonus_parado=0, proibir=POUCOS.proibir))
    assert len(com) == 4, com
    assert len(sem) == 6, sem
    webcam = "Mova a webcam da entrada 6 para a 2  ·  melhora, não é urgente"
    assert webcam in sem
    assert webcam not in com
    assert "Mova o cabo do hub da entrada 4 para a 3" in sem


# ══ A REGRA 3: só melhora vira movimento ═════════════════════════════════


def test_ganho_negativo_nao_vira_ordem_de_servico() -> None:
    """Não se manda mexer à toa — e agora o MAPA obedece à mesma regra.

    Quem perde nota fica onde está nos DOIS lugares: a receita não o cita, e o
    plano continua desenhando-o na entrada de hoje.
    """
    mesa = mock.mesa()
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    parados = 0
    for nome, op in TODAS:
        plano = motor.planejar(mesa, op)
        titulos = " || ".join(movimentos(mesa, op))
        for aparelho in mesa.aparelhos:
            de = motor.entrada_de_em(aloc, aparelho.id)
            if not de or plano.motivo[aparelho.id].ganho > 0:
                continue
            parados += 1
            assert motor.entrada_de_em(plano.plano, aparelho.id) == de, (nome, aparelho.id)
            assert f"da entrada {de} para" not in titulos, (nome, aparelho.id)
    assert parados, "o cenário deixou de exercitar ganho não-positivo"


def _mesa_do_empate() -> motor.Mesa:
    """Duas entradas idênticas e um aparelho já numa delas — o empate puro.

    A mesa dela não tem empate assim: as suas entradas diferem em face, em cor e
    em vizinho, e sempre há um critério que desempata. Esta existe para exercitar
    o único caminho que a mesa real não alcança — o do ganho **zero**, em que o
    aparelho pode voltar para onde estava porque a entrada de hoje continua
    livre. Sem ela, o passe da ``D-MAPA-SEM-RECEITA`` teria um ramo sem régua.
    """
    faces = (motor.Face(nome="Duas iguais", regiao="pc", entradas=(
        motor.Entrada("1", usb=2, onde="pc"), motor.Entrada("2", usb=2, onde="pc"))),)
    return motor.Mesa(
        aparelhos=(motor.Aparelho("cam", "Webcam", "Logitech C920", "webcam"),),
        faces=faces, mapa={"2": "x-2"}, leitura={"cam": "x-2"},
    )


def test_arrancado_o_filtro_a_receita_manda_mexer_a_toa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA: sem o filtro, o mapa E a receita mandam mexer sem ganho nenhum.

    Arrancar aqui é arrancar de verdade — ``_receita_manda_mover`` passa a dizer
    sim a tudo. E como o MAPA pergunta à MESMA função desde a
    ``D-MAPA-SEM-RECEITA``, os dois lados voltam a mexer juntos: o desenho tira a
    webcam da entrada 2 e a receita manda tirá-la, por um ganho de zero.
    """
    mesa, op = _mesa_do_empate(), SEM_BONUS
    plano = motor.planejar(mesa, op)
    assert plano.motivo["cam"].ganho == 0, "o cenário deixou de ser um empate"
    assert dict(plano.plano) == {"2": "cam"}
    assert movimentos(mesa, op) == []

    monkeypatch.setattr(
        motor, "_receita_manda_mover",
        lambda de, para, motivo: bool(para) and de != para,
    )
    assert dict(motor.planejar(mesa, op).plano) == {"1": "cam"}
    assert movimentos(mesa, op) == [
        "Mova a webcam da entrada 2 para a 1  ·  melhora, não é urgente"]


def test_arrancado_o_filtro_a_mesa_dela_perde_a_urgencia_dos_forcados(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA na mesa REAL: os três movimentos forçados viram "não é urgente".

    Sem o filtro o passe nunca corre, e com ele some a única coisa que
    distinguia *"tire o dongle daqui porque esta opção não usa esta entrada"* de
    *"se sobrar tempo, melhore isto"*. A receita não encolhe — ela **mente sobre
    a prioridade**, que é o defeito mais caro de uma ordem de serviço.
    """
    mesa = mock.mesa()
    com = movimentos(mesa, SO_PC)
    monkeypatch.setattr(
        motor, "_receita_manda_mover",
        lambda de, para, motivo: bool(para) and de != para,
    )
    sem = movimentos(mesa, SO_PC)
    assert len(com) == len(sem) == 6
    urgentes = [t for t in com if "não é urgente" not in t]
    assert len(urgentes) == 4, urgentes
    assert [t for t in sem if "não é urgente" not in t] == [
        t for t in urgentes if not t.startswith("Mova")]


# ══ A REGRA 4: ninguém troca de adaptador sem baixar o pico ══════════════

DOIS_ADAPTADORES = (
    motor.Adaptador("bt-a", "9", "entrada 9"),
    motor.Adaptador("bt-b", "15a", "entrada 15a"),
)


def _quem_muda(controles: tuple[motor.Controle, ...],
               plano: motor.PlanoDosControles) -> list[str]:
    return [c.nome for c in controles if plano.destino[c.nome] != c.onde]


def test_ninguem_troca_de_adaptador_sem_baixar_o_pico() -> None:
    """Trocar custa desfazer pareamento, apagar o cache SDP e parear de novo.

    Quatro controles equilibrados em dois adaptadores: ZERO movimentos. Os
    quatro no mesmo dongle: exatamente DOIS. E três em 2+1, onde mover não baixa
    o pico (553,4 continua 553,4): ZERO, que é a guarda do pico fazendo o
    trabalho.

    A carga sai em ``approx`` porque o número é FLOAT desde a
    ``D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO``: somar 276,7 quatro vezes e
    subtrair duas dá ``553.3999999999999``, e o JavaScript do mockup produz o
    MESMO ruído — arredondar aqui esconderia uma divergência real.
    """
    equilibrados = (
        motor.Controle("Jogador 1", mic=True, onde="bt-a"),
        motor.Controle("Jogador 2", mic=True, onde="bt-a"),
        motor.Controle("Jogador 3", mic=True, onde="bt-b"),
        motor.Controle("Jogador 4", mic=True, onde="bt-b"),
    )
    plano = motor.plano_dos_controles(equilibrados, DOIS_ADAPTADORES)
    assert _quem_muda(equilibrados, plano) == []
    assert dict(plano.carga) == pytest.approx({"bt-a": 553.4, "bt-b": 553.4})

    juntos = tuple(motor.Controle(c.nome, mic=True, onde="bt-a") for c in equilibrados)
    plano = motor.plano_dos_controles(juntos, DOIS_ADAPTADORES)
    assert len(_quem_muda(juntos, plano)) == 2
    assert dict(plano.carga) == pytest.approx({"bt-a": 553.4, "bt-b": 553.4})

    tres = equilibrados[:3]
    plano = motor.plano_dos_controles(tres, DOIS_ADAPTADORES)
    assert _quem_muda(tres, plano) == [], "mover não baixaria o pico: 553,4 continuaria 553,4"
    assert dict(plano.carga) == pytest.approx({"bt-a": 553.4, "bt-b": 276.7})


def test_sem_adaptador_nenhum_o_motor_diz_que_nao_cabe() -> None:
    """A mesa dela às 02h36 de 25/08: o hub saiu e levou os três dongles."""
    mesa = mock.mesa_sem_hub()
    assert motor.adaptadores_da_mesa(mesa) == ()
    plano = motor.plano_dos_controles(mock.CONTROLES, motor.adaptadores_da_mesa(mesa))
    assert plano.cabe is False
    assert plano.sobra == 0
    assert dict(plano.destino) == {}


# ══ 5. MAPA = RECEITA: uma verdade só na tela ════════════════════════════
#
# D-MAPA-SEM-RECEITA, 25/08/2026. As duas beiras perguntam à mesma função, e
# estes três testes são o portão disso.


@pytest.mark.parametrize("nome,op", TODAS)
def test_todo_aparelho_que_o_mapa_move_a_receita_manda_mover(
    nome: str, op: motor.Opcoes,
) -> None:
    """A invariante inteira, nas quatro variantes MAIS o bônus desligado."""
    mesa = mock.mesa()
    plano = motor.planejar(mesa, op)
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    titulos = " || ".join(movimentos(mesa, op))
    for aparelho in mesa.aparelhos:
        para = motor.entrada_de_em(plano.plano, aparelho.id)
        if not para or motor.entrada_de_em(aloc, aparelho.id) == para:
            continue
        assert f"a {para}" in titulos or f"entrada {para}" in titulos, (nome, aparelho.id)


@pytest.mark.usefixtures("sem_a_cura_do_mapa")
def test_arrancada_a_cura_o_mapa_move_tres_aparelhos_que_a_receita_nao_manda() -> None:
    """A MORDIDA, e ela nomeia os três órfãos, um a um.

    Sem o passe, o plano realoja quem a receita cala: os dois dongles que ``Sem
    usar o hub`` expulsa do hub (ganho -60 e -130), o que ``Sem o extensor``
    tira da ponta (-25), e o cabo do hub que o Wi-Fi desaloja quando o bônus de
    ficar parado está desligado (ganho 0).
    """
    mesa = mock.mesa()
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    orfaos: dict[str, list[str]] = {}
    for nome, op in TODAS:
        plano = motor.planejar(mesa, op)
        titulos = " || ".join(movimentos(mesa, op))
        for aparelho in mesa.aparelhos:
            para = motor.entrada_de_em(plano.plano, aparelho.id)
            de = motor.entrada_de_em(aloc, aparelho.id)
            if not para or de is None or de == para:
                continue
            if f"a {para}" not in titulos and f"entrada {para}" not in titulos:
                orfaos.setdefault(nome, []).append(f"{aparelho.id}: {de}->{para}")
    assert orfaos == {
        "sem-ext": ["bt-b: 15a->15"],
        "so-pc": ["bt-a: 9->5", "bt-b: 15a->7"],
        "sem-bonus": ["hub: 4->3"],
    }, orfaos


def test_a_variante_que_tira_a_entrada_de_hoje_diz_por_que_esta_tirando() -> None:
    """Sair de um lugar bom sem ganho só se justifica com a frase que o explica.

    É o único movimento da receita cujo porquê não vem da tabela de notas: a
    entrada de hoje saiu do tabuleiro, então não há *"ficar onde está"* para
    comparar. Sem esta linha a ordem de serviço mandaria mexer sem dizer por quê.
    """
    mesa = mock.mesa()
    achou = 0
    for nome, op in [("sem-ext", SEM_EXT), ("so-pc", SO_PC)]:
        for movimento in motor.receita(mesa, op):
            if not movimento.titulo.startswith("Mova"):
                continue
            porques = [ln.texto for ln in movimento.linhas]
            if any(t.startswith("Esta opção não usa a entrada") for t in porques):
                achou += 1
                assert movimento.essencial, (nome, movimento.titulo)
                assert movimento.ganho == math.inf, (nome, movimento.titulo)
    assert achou == 3, f"esperava um em Sem o extensor e dois em Sem usar o hub, vi {achou}"


# ══ 6. AS INVARIANTES DE ESTRUTURA ═══════════════════════════════════════


def _aplicar(mesa: motor.Mesa, plano: motor.Plano) -> motor.Mesa:
    """A mesa depois de ela mexer nos cabos: cada entrada do plano vira o caminho."""
    novo = {n: mesa.leitura[quem] for n, quem in plano.plano.items() if quem in mesa.leitura}
    return mock.mesa(mapa=novo, leitura=mesa.leitura, aparelhos=mesa.aparelhos)


@pytest.mark.parametrize("variante", ["melhor", "poucos", "sem-ext"])
def test_aplicar_o_plano_e_replanejar_da_zero_movimentos(variante: str) -> None:
    """Ponto fixo: o plano não pode se contradizer a cada clique."""
    op = motor.variante_por_id(variante).opcoes
    mesa = mock.mesa()
    depois = _aplicar(mesa, motor.planejar(mesa, op))
    assert movimentos(depois, op) == []


def test_sem_usar_o_hub_so_estabiliza_na_segunda_volta() -> None:
    """MEDIDO EM 25/08: a quarta variante NÃO é ponto fixo de primeira.

    A MOTOR-2 pede ponto fixo nas quatro. O motor que roda entrega em três, e
    `Sem usar o hub` precisa de uma volta a mais — as oito entradas do gabinete
    para oito aparelhos deixam a ordem de decisão mandar num arranjo diferente
    do que ela acabou de aplicar. Está registrado aqui para não se perder.
    """
    mesa = mock.mesa()
    primeira = _aplicar(mesa, motor.planejar(mesa, SO_PC))
    assert len(movimentos(primeira, SO_PC)) == 3
    segunda = _aplicar(primeira, motor.planejar(primeira, SO_PC))
    assert movimentos(segunda, SO_PC) == []


# ══ 7. MOTOR-3: o preço em PALAVRA, nunca em pontos ══════════════════════


def test_a_variante_declara_o_que_perde() -> None:
    """Toda variante cujo plano difere do melhor diz, em frase, o que se perde."""
    mesa = mock.mesa()
    melhor = motor.planejar(mesa, MELHOR).plano
    diferentes = 0
    for variante in motor.VARIANTES:
        plano = motor.planejar(mesa, variante.opcoes).plano
        if plano == melhor:
            continue
        diferentes += 1
        perdas = motor.consequencias(mesa, variante.opcoes)
        assert perdas, f"{variante.rotulo} muda o arranjo e não diz o que custa"
    assert diferentes >= 2, "o cenário deixou de exercitar variantes que divergem"


def test_o_que_se_perde_nunca_sai_em_pontos() -> None:
    """*"437 pontos pior"* não diz nada a ninguém. A nota existe e não vai à tela."""
    mesa = mock.mesa()
    for variante in motor.VARIANTES:
        nota = str(motor.qualidade(mesa, variante.opcoes))
        for frase in motor.consequencias(mesa, variante.opcoes):
            assert "ponto" not in frase.lower()
            assert nota not in frase
        for movimento in motor.receita(mesa, variante.opcoes):
            texto = movimento.titulo + " ".join(ln.texto for ln in movimento.linhas)
            assert "ponto" not in texto.lower()
            assert nota not in texto


def test_o_selo_de_cada_razao_e_um_dos_tres_graus() -> None:
    """O selo é a coluna `de_onde_sei`: é o que impede raciocínio de virar medição."""
    graus = {motor.SELO_MEDIDO, motor.SELO_DERIVADO, motor.SELO_ESPEC}
    mesa = mock.mesa()
    for variante in motor.VARIANTES:
        for movimento in motor.receita(mesa, variante.opcoes):
            assert {ln.selo for ln in movimento.linhas} <= graus
        for motivo in motor.planejar(mesa, variante.opcoes).motivo.values():
            assert {r.selo for r in motivo.razoes} <= graus


# ══ 8. A CONTA DO RÁDIO TEM UM DONO SÓ ═══════════════════════════════════
#
# D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO, 25/08/2026. Até esta data o §10 do motor
# guardava `260`, `277` e `1600` — literais copiados do mockup, ARREDONDADOS. O
# dono é `radio_da_mesa.py`, que tem portão contra `docs/data/mapa-controles.csv`;
# o motor estava FORA desse portão, então remedir o A/B corrigia o dono e deixava
# o motor mentindo com tudo verde.
#
# Comparar VALOR não bastaria como régua: no dia em que alguém copiasse o número
# certo de volta para cá, a igualdade continuaria verdadeira e a segunda verdade
# voltaria calada. Por isso a régua olha a FORMA da atribuição, por AST.

_FONTE_DO_MOTOR = Path(motor.__file__)

#: nome da constante -> os nomes do dono de que ela TEM de ser feita.
_DE_ONDE_CADA_UMA_VEM: dict[str, set[str]] = {
    "CUSTO_SEM_MIC": {"HZ_INPUT_SEM_MIC", "SLOTS_POR_RELATORIO"},
    "CUSTO_COM_MIC": {"HZ_INPUT_COM_MIC", "HZ_AUDIO_COM_MIC", "SLOTS_POR_RELATORIO"},
    "SLOTS": {"SLOTS_POR_SEGUNDO"},
}


def nomes_que_alimentam(fonte: str, constante: str) -> set[str] | None:
    """Os nomes de que ``constante`` é feita — ou ``None`` se ela virou literal.

    Devolve o conjunto VAZIO quando a atribuição existe e não usa nome nenhum
    que não seja literal; ``None`` quando a constante não é atribuída no módulo.
    """
    for no in ast.parse(fonte).body:
        if not isinstance(no, ast.Assign) or len(no.targets) != 1:
            continue
        alvo = no.targets[0]
        if not isinstance(alvo, ast.Name) or alvo.id != constante:
            continue
        return {x.id for x in ast.walk(no.value) if isinstance(x, ast.Name)}
    return None


def test_a_conta_do_radio_e_feita_do_dono_e_nao_copiada() -> None:
    """As três constantes do §10 saem de ``radio_da_mesa`` por NOME, não por número."""
    fonte = _FONTE_DO_MOTOR.read_text(encoding="utf-8")
    for constante, esperados in _DE_ONDE_CADA_UMA_VEM.items():
        veio_de = nomes_que_alimentam(fonte, constante)
        assert veio_de == esperados, f"{constante} deixou de vir do dono: {veio_de}"

    # e o valor, que é a outra metade: o dono manda, e o motor obedece
    assert motor.CUSTO_SEM_MIC == radio.HZ_INPUT_SEM_MIC * radio.SLOTS_POR_RELATORIO
    assert motor.CUSTO_COM_MIC == (
        radio.HZ_INPUT_COM_MIC + radio.HZ_AUDIO_COM_MIC) * radio.SLOTS_POR_RELATORIO
    assert motor.SLOTS == radio.SLOTS_POR_SEGUNDO
    # o arredondado que morava aqui: 260 e 277. Se voltar, não é mais o medido.
    assert motor.CUSTO_SEM_MIC == 260.4
    assert motor.CUSTO_COM_MIC == 276.7


def test_a_regua_da_copia_sabe_recusar() -> None:
    """Régua que só sabe passar não é régua — esta reprova a cópia literal.

    O dublê é a linha exata que existia até 25/08/2026.
    """
    copiado = "CUSTO_SEM_MIC = 260\nCUSTO_COM_MIC = 277\nSLOTS = 1600\n"
    for constante in _DE_ONDE_CADA_UMA_VEM:
        assert nomes_que_alimentam(copiado, constante) == set()
    assert nomes_que_alimentam("SLOTS = 1600\n", "CUSTO_SEM_MIC") is None
    derivado = "CUSTO_SEM_MIC = HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO\n"
    assert nomes_que_alimentam(derivado, "CUSTO_SEM_MIC") == {
        "HZ_INPUT_SEM_MIC", "SLOTS_POR_RELATORIO"}


#: **O MOCKUP DO ARRANJO EXISTE EM TRÊS CASAS, E ELAS NÃO TÊM O MESMO PAPEL.**
#:
#: FATO CORRIGIDO EM 31/08/2026. O comentário que morava aqui dizia que
#: ``novo-layout/`` "é onde os mockups moram", e mandava a régua medir aquela
#: cópia. Caducou no commit ``48b4e1a2`` — *"o produto lê de `layout/`;
#: `novo-layout/` volta a ser só referência"* —, e a palavra dela está escrita
#: no ``.gitignore``: *"não tava trackeado por um motivo ÓBVIO: é só pra
#: referência do desenvolvimento. Se fosse pra usar, ao menos copiasse todos os
#: html e criasse uma pasta chamada layout."* A régua ficou apontada para a casa
#: errada — a mesma migração pela metade que no mesmo dia deixou 13 reprovações
#: em ``test_o_gancho_induz_a_regua_de_tela.py``.
#:
#: O ACHADO DE 29/08 CONTINUA VALENDO, e é por isso que a régua não encolhe: ela
#: passava verde enquanto uma das cópias carregava
#: ``var CUSTO_SEM_MIC = 260, CUSTO_COM_MIC = 277`` e ``>277</b>/s`` — o literal
#: que a última linha do §11 proíbe — porque nomeava **um caminho** e a cópia
#: que se abre com duplo clique era outra. Aquela cópia também citava a fonte
#: errada da medição (``daemon/subsystems/bt_mic.py``, quando o A/B está em
#: ``integrations/dualsense_bt_audio.py:77``).
#:
#: AS TRÊS CASAS, medidas em 31/08/2026:
#:
#: * ``docs/.../2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`` — **a
#:   origem congelada**. O ``LEIA.md`` ao lado diz o que ela é: *"não é
#:   rascunho: é a especificação executável de quatro sprints, e a única
#:   descrição existente do motor de arranjo"*. ``arranjo_da_mesa.py:4`` e
#:   ``mesa_do_mockup.py:4`` citam ESTE caminho como fonte do porte, e o
#:   ``fumaca.js`` — a régua que RODA o miolo em 29 estados — só existe nesta
#:   pasta. Último commit dela: ``79759cd5``, 25/08. É a única casa sem irmãs
#:   ao lado: abre com duplo clique e não tem para onde navegar.
#: * ``src/hefesto_dualsense4unix/interface/paginas/mapa-das-portas.html`` — **a
#:   cópia do produto**, versionada e viva. É para ela que a ``08-conexoes.html``
#:   publicada aponta, e é a que a GUI carrega no ``WebKit2.WebView``. Não é
#:   gerada: ninguém em ``src/hefesto_dualsense4unix/interface/`` a escreve,
#:   então a igualdade abaixo é mantível.
#: * ``mockup/mapa-das-portas.html`` — **a referência do desenho**, a bancada.
#:
#: OS DOIS ENDEREÇOS MUDARAM, e a régua não tinha ido junto — corrigido em
#: 03/09/2026, junto com o mesmo defeito em `check_regua_de_tela.py`. Ela
#: apontava para ``layout/`` e ``novo-layout/``, e NENHUMA DAS DUAS EXISTE nesta
#: árvore: as páginas publicadas moraram para ``interface/paginas/`` e a bancada
#: para ``mockup/``. O sintoma era o pior que um portão tem — ele reprovava
#: dizendo *"o arquivo versionado não está aqui"*, que se lê como "alguém
#: apagou o produto" quando o que houve foi a régua perguntar no lugar errado.
#:
#: A BANCADA AGORA É VERSIONADA, e isto derruba metade da razão antiga (*"não
#: existe em árvore de agente"*). O que NÃO mudou é a razão que importa: ela
#: anda À FRENTE do produto por decisão dela, e cobrar igualdade contra ela
#: seria portão gritando falso no dia seguinte. Fica nos NÚMEROS, fora da
#: IGUALDADE — que é onde já estava, agora pela razão certa.
#:
#: O QUE A RÉGUA MEDE, E POR QUE ELA NÃO EXIGE MAIS QUE AS TRÊS SEJAM IGUAIS: os
#: NÚMEROS são cobrados de toda casa que exista no disco — custo zero, e é
#: exatamente o defeito de 29/08. A IGUALDADE fica só entre as duas casas
#: VERSIONADAS, porque só elas viajam com o git e só elas podem divergir sem
#: ninguém ver. Exigir igualdade com a referência congelada seria portão
#: gritando falso já no dia seguinte — ela não acompanha o ``layout/``, por
#: decisão dela —, e portão que grita falso é portão que se desliga.
_ORIGEM_CONGELADA = "docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html"
_COPIA_DO_PRODUTO = ("src/hefesto_dualsense4unix/interface/paginas/mapa-das-portas.html")
_REFERENCIA_DO_DESENHO = "mockup/mapa-das-portas.html"

#: Toda casa onde o mockup pode estar. Os NÚMEROS são cobrados de todas.
_CAMINHOS_DO_MOCKUP_DO_ARRANJO = (
    _ORIGEM_CONGELADA,
    _COPIA_DO_PRODUTO,
    _REFERENCIA_DO_DESENHO,
)

#: As duas casas versionadas — as que a igualdade compara. Nenhuma delas pode
#: faltar: as duas estão no ``git ls-files``, logo viajam para qualquer árvore.
#: Se uma sumir, o portão passaria por VACUIDADE, que é o pior estado de todos.
_CASAS_VERSIONADAS = (_ORIGEM_CONGELADA, _COPIA_DO_PRODUTO)


class _Divergencia(NamedTuple):
    """Um pedaço em que a cópia do produto PODE diferir da origem congelada.

    Nasceu do mesmo desconforto que o ``SERVE_UM_LADO_SO`` do
    ``test_install_serve_os_dois_lados_da_cerca.py``: uma lacuna sem dono vira
    paisagem. Aqui a lacuna não é "esta parte não é medida" — é "esta parte é
    medida como EXATAMENTE este bloco". Nada mais se esconde dentro dela, e
    mexer no botão obriga a redeclarar, com data nova.
    """

    na_origem: str
    no_produto: str
    porque: str


#: O botão de voltar, e por que ele NÃO pode ir para a origem congelada.
#:
#: Medido em 31/08/2026: a pasta da sprint tem três arquivos — ``fumaca.js``,
#: ``LEIA.md`` e o mockup. **Não há ``08-conexoes.html`` ali**, e o ``LEIA.md``
#: diz que aquele arquivo se abre com duplo clique, autocontido. Copiar o botão
#: para lá entregaria um botão que não vai a lugar nenhum — pior do que não ter
#: botão. As duas cópias, portanto, NÃO PODEM ser byte-idênticas, e a régua que
#: exigia isso estava pedindo o impossível.
_VOLTAR_NA_ORIGEM = '  <header class="topo">\n'
_VOLTAR_NO_PRODUTO = """\
  <header class="topo" style="position:relative;padding-left:132px">
    <!-- O BOTÃO DE VOLTAR — 30/08/2026, pergunta dela: "ok temos um botão pra vir
         pra cá. Mas e o botão pra voltar?". Não havia nenhum href de saída nesta
         página. O destino não é chute: `grep -l mapa-das-portas.html layout/*.html`
         devolve UMA aba, a Conexões. -->
    <a href="08-conexoes.html" title="Volta para a aba Conexões, que é de onde este mapa se abre."
       style="position:absolute;left:0;top:2px;display:inline-flex;align-items:center;gap:6px;
              padding:5px 11px;border-radius:7px;text-decoration:none;
              border:1px solid var(--border-forte);background:var(--panel);
              color:var(--texto-suave);font-size:12px">← Voltar</a>
"""

#: A PALAVRA "mesa" SAIU DA TELA — 05/09/2026, ordem dela, e esta é a segunda
#: razão pela qual as duas casas não podem ser iguais.
#:
#: Ela mandou, em duas partes: *"não é pra ter mesa em nada da interface"* e,
#: corrigindo a primeira leva, *"muda o termo pra objeto e sinônimos nesses
#: casos"*. A cópia do produto é TELA — ela a abre pelo link da aba Conexões —,
#: logo a palavra tinha de sair de lá.
#:
#: A ORIGEM CONGELADA NÃO PODE RECEBER A TROCA, e o motivo é medido, não de
#: gosto: ela é a **especificação executável do motor**. O
#: `tests/fixtures/motor_do_arranjo_do_mockup.js` EXTRAI o `<script>` dela e
#: roda 120 cenários em `node`; o JSON de ouro que sai daí é a prova de
#: equivalência do porte em Python, e
#: `test_o_ouro_ainda_e_o_que_o_mockup_diz_hoje` reprova se o ouro se afastar
#: dela. Reescrever o texto ali reescreveria o ouro — e apagaria o registro de
#: como o motor falava em 24/08/2026, que é o que aquela pasta datada é.
#:
#: A DUAS FRASES DO MOTOR (as de "altura da mesa") divergem TAMBÉM no Python, e
#: lá a divergência tem a sua própria declaração, com a sua própria mordida:
#: `DIVERGENCIA_DA_PALAVRA_MESA`, em
#: `tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`.
#:
#: **Nenhuma destas pode mudar mais do que a palavra** — o
#: `test_nenhuma_troca_de_palavra_mudou_a_frase` logo abaixo é quem exige isso,
#: e é o que impede esta lista de virar a porta dos fundos da igualdade.
_A_PALAVRA_QUE_SAIU: tuple[tuple[str, str], ...] = (
    # QUATRO PARES SAÍRAM DAQUI EM 11/09/2026, e a régua mandou: *"perdão morto,
    # APAGUE o par"*. Eles não morreram porque a palavra voltou — morreram
    # porque a PÁGINA foi reescrita. A PAGINAS-ESPECIAIS-B1 mudou as frases
    # inteiras por aprovação dela («Como está hoje» no lugar de «Como está o meu
    # arranjo», a lição do adaptador refeita), e um perdão que descreve uma
    # frase que não existe mais deixa a próxima pessoa procurando o que não há.
    # Conferido antes de sair: a palavra banida NÃO voltou à tela desta página —
    # o que sobra dela são nomes de classe CSS e um `data-modo`, que são
    # endereço de código e não texto que alguém lê.
    ("— o mapa da sua mesa", "— o mapa dos seus objetos"),
    ('porque: "entrada direta, mas na altura da mesa"',
     'porque: "entrada direta, mas na altura da escrivaninha"'),
    ("Bom quando desmontar a mesa custa caro.",
     "Bom quando desmontar o arranjo custa caro."),
    ('out.push("os dongles ficam na altura da mesa, não no alto do rack")',
     'out.push("os dongles ficam na altura da escrivaninha, não no alto do rack")'),
    ("pode não caber na sua mesa — escolha o que cabe.",
     "pode não caber na sua escrivaninha — escolha o que cabe."),
    ("</span> e a sua mesa fica no melhor arranjo que este hardware permite.",
     "</span> e o seu arranjo fica no melhor que este hardware permite."),
    ('">Ver como a mesa estava ', '">Ver como o arranjo estava '),
    ('"Esta mesa está no melhor arranjo que eu conheço."',
     '"Este arranjo é o melhor que eu conheço."'),
    ('"Esta é a mesa de agora — "', '"Este é o arranjo de agora — "'),
    (">Controles na mesa:</span>", ">Controles ligados:</span>"),
)

_PORQUE_A_PALAVRA_SAIU = (
    "05/09/2026 — a palavra “mesa” saiu da tela por ordem dela (*\"muda o termo "
    "pra objeto e sinônimos nesses casos\"*). A cópia do produto é tela; a "
    "origem congelada é a especificação executável de onde o `fumaca.js` "
    "extrai o motor para produzir o ouro de 120 cenários, e reescrevê-la "
    "reescreveria a prova de equivalência do porte."
)

#: A lista inteira das divergências justificadas: o botão de voltar (31/08/2026)
#: e as catorze trocas de palavra (05/09/2026).
_DIVERGENCIAS_DECLARADAS = (
    _Divergencia(
        na_origem=_VOLTAR_NA_ORIGEM,
        no_produto=_VOLTAR_NO_PRODUTO,
        porque=(
            "30/08/2026 — o botão de voltar, que ela pediu com estas palavras: "
            '"ok temos um botão pra vir pra cá. Mas e o botão pra voltar?". Ele '
            "aponta para `08-conexoes.html`, que existe ao lado da cópia do "
            "produto e NÃO existe na pasta da sprint (só `fumaca.js`, `LEIA.md` "
            "e o mockup). Levá-lo para a origem congelada criaria link quebrado."
        ),
    ),
    *(
        _Divergencia(na_origem=antes, no_produto=depois, porque=_PORQUE_A_PALAVRA_SAIU)
        for antes, depois in _A_PALAVRA_QUE_SAIU
    ),
)

#: Link relativo para outra página, que é o único tipo que este mockup usa.
#: Âncora, `http(s):` e `mailto:` ficam de fora porque não são arquivo no disco.
_LINK_RELATIVO_DO_MOCKUP = re.compile(r'href="(?!https?:|//|#|mailto:)([^"#?]+\.html)"')


def _descontar_o_declarado(produto: str) -> str:
    """A cópia do produto com cada divergência declarada trocada pela da origem.

    Separado do teste de propósito: assim a régua pode ser mordida sem tocar em
    arquivo nenhum — ver ``test_a_regua_da_igualdade_sabe_recusar``.
    """
    reduzido = produto
    for divergencia in _DIVERGENCIAS_DECLARADAS:
        reduzido = reduzido.replace(divergencia.no_produto, divergencia.na_origem, 1)
    return reduzido


def test_o_mockup_carrega_os_mesmos_numeros_que_o_python() -> None:
    """O número da tela é o número medido — em TODA cópia que exista no disco.

    A paridade de ``test_arranjo_da_mesa_bate_com_o_mockup.py`` já pegaria uma
    divergência de CÁLCULO. Esta pega a divergência de TEXTO: o mockup é o
    artefato que ela abre com duplo clique, e um número arredondado na legenda
    seria a segunda verdade voltando pela porta da tela.

    O nome deste teste passou a dizer o que ele faz. Até 31/08 ele carregava,
    além dos números, uma igualdade byte a byte que reprovava por uma razão
    completamente diferente — e foi ela, não um número, que ficou vermelha.
    """
    raiz = _FONTE_DO_MOTOR.parents[3]
    medidas = 0
    for caminho in _CAMINHOS_DO_MOCKUP_DO_ARRANJO:
        mockup = raiz / caminho
        if not mockup.exists():  # pragma: no cover - árvore sem o `novo-layout/`
            continue
        texto = mockup.read_text(encoding="utf-8")
        medidas += 1
        assert (
            "var CUSTO_SEM_MIC = 260.4, CUSTO_COM_MIC = 276.7, SLOTS = 1600;" in texto
        ), f"{caminho}: as constantes do motor não são as medidas"
        assert ">276,7</b>/s" in texto, f"{caminho}: a legenda não diz 276,7"
        assert ">260,4</b>/s" in texto, f"{caminho}: a legenda não diz 260,4"
        assert ">277<" not in texto, f"{caminho}: o número arredondado voltou"
        assert "dualsense_bt_audio.py" in texto, (
            f"{caminho}: a legenda tem de citar onde o A/B foi medido")
    assert medidas >= len(_CASAS_VERSIONADAS), (
        f"só {medidas} cópia(s) do mockup foram medidas; as duas casas "
        f"versionadas {_CASAS_VERSIONADAS} viajam com o git e têm de estar aqui")


def test_as_duas_casas_versionadas_do_mockup_nao_andam_sozinhas() -> None:
    """Corrigir nos DOIS foi a palavra dela, e esta linha é o que a mantém viva.

    A origem congelada é a especificação executável do motor; a cópia do produto
    é o que ela abre. Se as duas divergirem em silêncio, o ``fumaca.js`` e o
    porte em Python passam a descrever uma tela que não é a que ela vê — que é o
    defeito das duas versões vivas, escrito de outro jeito.

    A igualdade desconta as divergências DECLARADAS, e só elas. Cada uma tem de
    estar presente na cópia do produto, ausente da origem, e aparecer uma vez
    só: o que sobrar depois do desconto tem de bater byte a byte.
    """
    raiz = _FONTE_DO_MOTOR.parents[3]
    textos = {}
    for caminho in _CASAS_VERSIONADAS:
        arquivo = raiz / caminho
        assert arquivo.exists(), (
            f"{caminho} não está nesta árvore — mas é versionado. Sem ele a "
            "igualdade passaria por vacuidade, que é o pior estado de um portão")
        textos[caminho] = arquivo.read_text(encoding="utf-8")

    origem = textos[_ORIGEM_CONGELADA]
    produto = textos[_COPIA_DO_PRODUTO]

    for divergencia in _DIVERGENCIAS_DECLARADAS:
        assert produto.count(divergencia.no_produto) == 1, (
            "a divergência declarada não aparece exatamente uma vez em "
            f"{_COPIA_DO_PRODUTO} — declaração e arquivo se separaram.\n"
            f"  motivo declarado: {divergencia.porque}")
        assert divergencia.no_produto not in origem, (
            f"o pedaço declarado como exclusivo do produto apareceu em "
            f"{_ORIGEM_CONGELADA}. Se ele passou a valer lá, a declaração é que "
            "tem de sair — e o link tem de existir naquela pasta.\n"
            f"  motivo declarado: {divergencia.porque}")
        assert origem.count(divergencia.na_origem) == 1, (
            f"o pedaço que a origem tem no lugar da divergência sumiu de "
            f"{_ORIGEM_CONGELADA}; a declaração ficou velha.\n"
            f"  motivo declarado: {divergencia.porque}")

    assert _descontar_o_declarado(produto) == origem, (
        "as duas casas versionadas de mapa-das-portas.html divergiram fora do "
        "que está declarado — corrigir numa e não na outra é o defeito que esta "
        "régua mata.\n"
        f"  origem congelada: {_ORIGEM_CONGELADA}\n"
        f"  cópia do produto: {_COPIA_DO_PRODUTO}\n"
        "FAÇA UMA das duas:\n"
        "  1. LEVE a mesma correção para a outra casa; ou\n"
        "  2. DECLARE em `_DIVERGENCIAS_DECLARADAS`, com data e com o motivo de "
        "a outra casa não poder receber aquele pedaço.")


def test_nenhum_botao_do_mockup_vai_a_lugar_nenhum() -> None:
    """Botão que aponta para arquivo que não existe ao lado não está entregue.

    Esta é a MEDIÇÃO que sustenta a divergência declarada, em vez de uma
    opinião: o botão de voltar existe onde o ``08-conexoes.html`` existe, e a
    régua reprova no dia em que alguém o copiar para uma pasta sem destino —
    inclusive para a da sprint, que tem três arquivos e nenhuma aba.
    """
    raiz = _FONTE_DO_MOTOR.parents[3]
    links = 0
    for caminho in _CAMINHOS_DO_MOCKUP_DO_ARRANJO:
        mockup = raiz / caminho
        if not mockup.exists():  # pragma: no cover - árvore sem o `novo-layout/`
            continue
        for alvo in _LINK_RELATIVO_DO_MOCKUP.findall(mockup.read_text(encoding="utf-8")):
            links += 1
            assert (mockup.parent / alvo).exists(), (
                f"{caminho}: o botão aponta para `{alvo}`, que não existe ao "
                f"lado ({mockup.parent}). Um botão que não vai a lugar nenhum é "
                "pior do que não ter botão")
    assert links, "nenhum link relativo foi medido — a régua passaria por vacuidade"


def test_a_regua_da_igualdade_sabe_recusar() -> None:
    """Régua que só sabe passar não é régua — esta reprova o que não foi declarado.

    O dublê é do tamanho do problema: uma mudança de UMA letra fora do pedaço
    declarado tem de sobreviver ao desconto e derrubar a comparação.
    """
    origem = "a\n" + _VOLTAR_NA_ORIGEM + "b\n"
    produto = "a\n" + _VOLTAR_NO_PRODUTO + "b\n"
    assert _descontar_o_declarado(produto) == origem

    # o desconto NÃO pode engolir uma segunda verdade que viajou de carona
    contrabando = produto.replace("b\n", "B\n")
    assert _descontar_o_declarado(contrabando) != origem

    # e nem apagar o que ele não conhece: sem a divergência, nada muda
    assert _descontar_o_declarado(origem) == origem


def test_nenhuma_troca_de_palavra_e_porta_dos_fundos() -> None:
    """Cada par de `_A_PALAVRA_QUE_SAIU` tira a palavra, e nada além disso passa.

    Esta é a régua da régua. `_DIVERGENCIAS_DECLARADAS` é a única liberdade que
    a igualdade byte a byte tem, e uma lista de perdões que ninguém confere é a
    porta dos fundos: bastaria declarar `("<html", "<XXX")` para qualquer
    divergência atravessar calada.

    AS TRÊS EXIGÊNCIAS, e a primeira versão desta régua PROMETIA UMA QUARTA QUE
    É FALSA. Ela exigia que o resto da frase ficasse idêntico, e não fica: o
    português concorda com o substantivo, então *"o mapa da sua mesa"* vira *"o
    mapa dos seus objetos"* — artigo e possessivo mudam junto, obrigados. Uma
    régua que exige o impossível ou é apagada ou é afrouxada, e as duas saídas
    são piores do que exigir o que é verdade:

    1. o lado da origem DIZ a palavra e o do produto NÃO — é disso que a lista
       trata, e um par que não fale de "mesa" não tem o que fazer aqui;
    2. cada par é curto. É o que impede o perdão de engolir estrutura: um par
       de duas linhas troca uma frase, um par de duzentas esconde um `<div>`;
    3. cada par DISPARA nos dois arquivos. Perdão que não é usado é perdão
       morto — a frase já mudou de outro jeito, e a entrada tem de sair.
    """
    for antes, depois in _A_PALAVRA_QUE_SAIU:
        assert "mesa" in antes, f"par que não é sobre a palavra: {antes!r}"
        assert "mesa" not in depois, f"o par manteve a palavra: {depois!r}"
        assert len(antes) <= 90 and len(depois) <= 90, (
            "par longo demais para ser uma troca de palavra — um perdão desse "
            f"tamanho esconde estrutura:\n  origem:  {antes!r}\n  produto: {depois!r}"
        )

    raiz = _FONTE_DO_MOTOR.parents[3]
    origem, produto = (raiz / c for c in _CASAS_VERSIONADAS)
    if not (origem.exists() and produto.exists()):  # pragma: no cover
        return
    texto_origem = origem.read_text(encoding="utf-8")
    texto_produto = produto.read_text(encoding="utf-8")
    for antes, depois in _A_PALAVRA_QUE_SAIU:
        assert antes in texto_origem, (
            f"a origem congelada já não diz {antes!r} — perdão morto, APAGUE o par")
        assert depois in texto_produto, (
            f"a cópia do produto já não diz {depois!r} — perdão morto, APAGUE o par")


# ══ 9. A MOTOR-5: A ABA CONSOME, E NÃO RECALCULA ═════════════════════════
#
# A tarefa MOTOR-5 da sprint pede UMA coisa e o nome dela é régua: *"a aba não
# pode ter uma segunda cópia da regra — duas verdades sobre a mesma coisa é o
# defeito que esta leva inteira existe para matar"*. A mordida que ela descreve
# é literal: *"Varredura AST: nenhum arquivo define função que decida arranjo,
# nota de entrada ou destino de controle. Arrancada a cura (recolocando a conta
# na aba), o portão reprova nomeando arquivo e função."*
#
# A ROTA MUDOU EM 06/09/2026 e o alvo com ela. A sprint mandava olhar
# `app/actions/config/secao_mesa.py` e `secao_orcamento.py`, que são o motor da
# JANELA GTK; quem consome hoje é a aba `08` da interface nova —
# `interface/pacotes/a08_conexoes.py`, com o desenho de `interface/aba08.py`.
# A varredura passa nos TRÊS lugares (`app/`, `interface/`, `gui/`), porque uma
# régua apontada só para o consumidor de hoje envelhece no dia da próxima rota.
#
# COMO A SEGUNDA CÓPIA SE RECONHECE, e as duas metades medem coisas diferentes:
#
#   · pela PALAVRA — a frase de uma razão da tabela de notas, ou de um veredito
#     do `julgar`, digitada fora do motor. Quem copia a regra copia a frase
#     junto: foi assim que a `aba08.veredito` nasceu, e é assim que ela se
#     declara aqui em vez de passar calada;
#   · pelo NÚMERO — dois pesos distintos da tabela na mesma função, ao lado de
#     uma classe de aparelho do motor. É a forma de quem reescreveu a conta sem
#     copiar o texto.
#
# MEDIDO EM 06/09/2026, com a varredura recém-escrita: `app/`, `interface/` e
# `gui/` somam 1 acusação pela palavra (a `aba08.py`, declarada abaixo) e ZERO
# pelo número. O piso é esse.

#: A superfície que a régua varre — o que o produto RODA, e o que o desenha.
_SUPERFICIE_DA_PRODUCAO = ("app", "interface", "gui")

#: O tamanho mínimo de uma frase para valer como assinatura de cópia.
#:
#: MEDIDO, e é a razão de o número não ser zero: os vereditos do `julgar`
#: carregam códigos curtos (`"fora"`, `"serve"`, `"melhor"`, `"cheia"`,
#: `"ruim"`, `"melhor lugar"`, `"indisponível"`) que são palavra comum do
#: português. Com o corte em 3 caracteres a varredura acusava 31 arquivos — o
#: rodapé da interface e um desenho de analógico entre eles —, e nenhum tem uma
#: linha de arranjo dentro. Régua que acusa quem está certo ensina a próxima
#: pessoa a não acreditar nela — é o defeito do `strip_quirks_token`, e o corte
#: em 25 caracteres é o que a mantém falando só de frase de arranjo.
_ASSINATURA_MINIMA = 25

#: arquivo (relativo a `src/hefesto_dualsense4unix/`) -> por que a cópia FICA.
#: Perdão declarado é decisão; perdão calado é a segunda verdade de volta.
_A_COPIA_DECLARADA: dict[str, str] = {
    "interface/aba08.py": (
        "A CENA DE BANCADA, e ela não é a tela. O gerador da página `08` monta "
        "um gabinete de mentira para o desenho sair igual em qualquer máquina — "
        "o motor de verdade precisa de uma `Bancada`, que precisa do censo do "
        "/sys de quem roda o gerador. A cópia é GUARDADA: `_confere_no_produto` "
        "reprova a geração no dia em que o produto trocar qualquer uma destas "
        "frases, e é isso que a impede de virar segunda verdade. O que o produto "
        "PINTA vem do motor, por `mapa_da_mesa.veredito_do_quadrado`."
    ),
}


def _arquivos_da_producao() -> list[Path]:
    """Todo `.py` de `app/`, `interface/` e `gui/`, menos o próprio motor."""
    raiz = _FONTE_DO_MOTOR.parent.parent
    achados: list[Path] = []
    for pasta in _SUPERFICIE_DA_PRODUCAO:
        achados.extend(sorted((raiz / pasta).rglob("*.py")))
    return [p for p in achados if p.resolve() != _FONTE_DO_MOTOR.resolve()]


def frases_da_tabela_de_notas() -> set[str]:
    """As razões da tabela do §5 — lidas do motor, nunca digitadas aqui."""
    return {
        regra.texto
        for regras in motor.REGRAS.values()
        for regra in regras
        if len(regra.texto) >= _ASSINATURA_MINIMA
    }


def frases_do_julgamento(fonte: str) -> set[str]:
    """As frases que `julgar` põe num `Veredito`, colhidas por AST do fonte."""
    for no in ast.parse(fonte).body:
        if isinstance(no, ast.FunctionDef) and no.name == "julgar":
            return {
                arg.value
                for chamada in ast.walk(no)
                if isinstance(chamada, ast.Call)
                and isinstance(chamada.func, ast.Name)
                and chamada.func.id == "Veredito"
                for arg in chamada.args
                if isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and len(arg.value) >= _ASSINATURA_MINIMA
            }
    return set()


def quem_digita_a_regra(arquivos: Iterator[Path] | list[Path],
                        frases: set[str]) -> dict[str, list[str]]:
    """arquivo -> as frases do motor que ele digita. Vazio é o estado certo."""
    fora: dict[str, list[str]] = {}
    for caminho in arquivos:
        texto = caminho.read_text(encoding="utf-8")
        achadas = sorted(f for f in frases if f in texto)
        if achadas:
            fora[str(caminho)] = achadas
    return fora


def quem_recalcula_a_nota(fonte: str) -> list[tuple[str, list[int], list[str]]]:
    """As funções que reescrevem a tabela de notas: dois pesos e uma classe.

    A conjunção é o que separa a cópia do acaso: `40` sozinho é largura de
    widget, `"bt"` sozinho é chave de transporte. Os dois juntos, com um segundo
    peso ao lado, é a tabela do §5 de volta.
    """
    pesos = {abs(r.n) for regras in motor.REGRAS.values() for r in regras
             if abs(r.n) > 5}
    classes = set(motor.REGRAS)
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover — fonte quebrado é outro portão
        return []
    acusadas: list[tuple[str, list[int], list[str]]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        numeros: set[int] = set()
        palavras: set[str] = set()
        for peca in ast.walk(no):
            if not isinstance(peca, ast.Constant):
                continue
            valor = peca.value
            if isinstance(valor, bool):
                continue
            if isinstance(valor, int) and abs(valor) in pesos:
                numeros.add(abs(valor))
            elif isinstance(valor, str) and valor in classes:
                palavras.add(valor)
        if len(numeros) >= 2 and palavras:
            acusadas.append((no.name, sorted(numeros), sorted(palavras)))
    return acusadas


def test_nenhuma_frase_do_motor_e_digitada_na_producao() -> None:
    """A tela mostra o que o motor diz — ela não redigita a razão dele."""
    frases = frases_da_tabela_de_notas() | frases_do_julgamento(
        _FONTE_DO_MOTOR.read_text(encoding="utf-8"))
    assert len(frases) >= 20, (
        f"a colheita das frases do motor encolheu para {len(frases)} — a régua "
        "está medindo menos do que promete")

    raiz = _FONTE_DO_MOTOR.parent.parent
    achados = quem_digita_a_regra(_arquivos_da_producao(), frases)
    inesperados = {
        arquivo: copias for arquivo, copias in achados.items()
        if str(Path(arquivo).relative_to(raiz)) not in _A_COPIA_DECLARADA
    }
    assert not inesperados, (
        "uma segunda cópia da regra do arranjo apareceu na produção — a razão "
        "do motor está digitada onde ela devia ser CONSUMIDA:\n"
        + "\n".join(f"  {arquivo}\n    {copias}"
                    for arquivo, copias in sorted(inesperados.items())))


def test_nenhuma_funcao_da_producao_redecide_a_nota() -> None:
    """Ninguém em `app/`, `interface/` ou `gui/` reescreve a tabela do §5."""
    acusadas: list[str] = []
    for caminho in _arquivos_da_producao():
        for nome, pesos, classes in quem_recalcula_a_nota(
                caminho.read_text(encoding="utf-8")):
            acusadas.append(f"  {caminho}::{nome} — pesos {pesos}, classes {classes}")
    assert not acusadas, (
        "a conta do arranjo voltou para a aba — duas verdades sobre a mesma "
        "coisa:\n" + "\n".join(acusadas))


def test_a_varredura_da_segunda_copia_sabe_recusar() -> None:
    """Régua que só sabe passar não é régua: os dois dublês são acusados.

    O primeiro é a cópia pela PALAVRA — a frase do motor digitada num arquivo de
    tela. O segundo é a cópia pelo NÚMERO, que é a forma de quem reescreveu a
    conta sem copiar o texto: é a tabela do §5 de volta dentro de uma função de
    aba, exatamente o que a MOTOR-5 existe para impedir.
    """
    frase = sorted(frases_da_tabela_de_notas())[0]
    with_copia = Path(__file__).parent / "__dublê_inexistente__.py"
    assert quem_digita_a_regra([], {frase}) == {}, "a régua acusou o vazio"
    assert not with_copia.exists(), "o dublê é de mentira, e não vai ao disco"

    recalcula = (
        "def nota_da_entrada(entrada, classe):\n"
        "    if classe == 'bt' and entrada.onde == 'hub':\n"
        "        return 60\n"
        "    if classe == 'teclado':\n"
        "        return 100\n"
        "    return 0\n"
    )
    acusada = quem_recalcula_a_nota(recalcula)
    assert [nome for nome, _, _ in acusada] == ["nota_da_entrada"], acusada
    assert acusada[0][1] == [60, 100]
    assert acusada[0][2] == ["bt", "hub", "teclado"]

    # e quem só CHAMA o motor passa — é a forma que a MOTOR-5 pede
    consome = (
        "from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor\n"
        "def veredito_do_quadrado(bancada, numero, escolhido):\n"
        "    entrada = motor.por_num(bancada.mesa.faces, numero)\n"
        "    return motor.julgar(entrada, 'bt', bancada.mesa, escolhido)\n"
    )
    assert quem_recalcula_a_nota(consome) == []


def test_todo_perdao_da_varredura_esta_vivo() -> None:
    """Perdão que não dispara é perdão morto — e porta dos fundos aberta.

    Uma lista de isenções que ninguém confere deixa passar qualquer coisa: basta
    declarar um arquivo e a régua cala sobre ele para sempre. Aqui cada entrada
    tem de (a) existir no disco, (b) de fato digitar frase do motor e (c) trazer
    a razão escrita.
    """
    raiz = _FONTE_DO_MOTOR.parent.parent
    frases = frases_da_tabela_de_notas() | frases_do_julgamento(
        _FONTE_DO_MOTOR.read_text(encoding="utf-8"))
    for relativo, razao in _A_COPIA_DECLARADA.items():
        caminho = raiz / relativo
        assert caminho.exists(), f"perdão para arquivo que não existe: {relativo}"
        assert len(razao) >= 120, f"perdão sem razão escrita: {relativo}"
        achadas = quem_digita_a_regra([caminho], frases)
        assert achadas, (
            f"{relativo} já não digita frase nenhuma do motor — perdão morto, "
            "APAGUE a entrada")


# ══ 10. A MOTOR-6: A ENTRADA VAZIA DESENHA, E A CONFIRMAÇÃO ENSINA ═══════
#
# A §7 da sprint separou duas necessidades que viviam misturadas numa pergunta
# só, e a separação é a tarefa inteira:
#
#   para DESENHAR o gabinete .... basta saber QUANTAS entradas cada face tem.
#                                Zero caminhos.
#   para RECONHECER quem mudou .. é preciso o caminho, e só das entradas que
#                                de fato recebem alguma coisa.
#
# *"Entrada que nunca recebe nada nunca precisa de caminho, e desenha bem."* É
# o que estes testes cobram, e é a mordida que a §7.5 nomeia:
# `test_entrada_vazia_desenha_sem_caminho` e
# `test_a_confirmacao_da_ordem_liga_a_entrada`.
#
# MEDIDO PELO CAMINHO DO PRODUTO EM 06/09/2026, e não numa `Mesa` montada à mão:
# `mapa_das_portas.mesa_do_motor` sobre o gabinete DELA e a bancada de mentira de
# 25/08 desenha **16 entradas, 8 sem caminho nenhum**, e `candidatas` corta de 16
# para 4 de cada lado — os mesmos números da §7.2 da sprint.

_ENTRADAS_DESENHADAS = 16
_ENTRADAS_COM_CAMINHO = 8


def _bancada_do_gabinete_dela() -> object:
    """A `Bancada` do produto: o desenho DELA sobre a leitura de 25/08 às 02h30."""
    from hefesto_dualsense4unix.integrations import mapa_das_portas
    from tests.unit.test_mapa_a_bancada_de_mentira import (
        bancada_de_agora,
        mapa_dela,
    )

    return mapa_das_portas.mesa_do_motor(mapa_dela(), bancada_de_agora().censo())


def test_entrada_vazia_desenha_sem_caminho() -> None:
    """O gabinete desenha os buracos que ele TEM, não os que já foram ligados.

    A mordida da §7.5: face declarada e nenhuma ligação — o mapa desenha as
    entradas assim mesmo, e `candidatas` as devolve. Arrancada a cura, entrada
    sem caminho some do desenho e a pessoa vê um gabinete com menos buracos do
    que ele tem — que é o defeito que ela reportou em 24/08, com quatro dos
    cinco aparelhos movidos caindo fora do mapa.
    """
    mesa = _bancada_do_gabinete_dela().mesa  # type: ignore[attr-defined]
    desenhadas = motor.todas_as_entradas(mesa.faces)
    assert len(desenhadas) == _ENTRADAS_DESENHADAS, [e.n for e in desenhadas]
    assert len(mesa.mapa) == _ENTRADAS_COM_CAMINHO, mesa.mapa

    vazias = [e.n for e in desenhadas if e.n not in mesa.mapa]
    assert len(vazias) == _ENTRADAS_DESENHADAS - _ENTRADAS_COM_CAMINHO, vazias

    # e elas não somem: cada uma continua candidata do próprio lado do gabinete
    de_cada_lado = {
        "pc": [e.n for e in motor.candidatas(mesa, "pc")],
        "hub": [e.n for e in motor.candidatas(mesa, "hub")],
    }
    assert sorted(de_cada_lado["pc"] + de_cada_lado["hub"]) == sorted(vazias), (
        f"{len(vazias)} entradas vazias desenhadas e "
        f"{len(de_cada_lado['pc']) + len(de_cada_lado['hub'])} candidatas — "
        "uma entrada sumiu entre o desenho e a escolha")
    assert de_cada_lado["pc"] and de_cada_lado["hub"], de_cada_lado


def test_arrancado_o_desenho_das_vazias_o_gabinete_perde_os_buracos() -> None:
    """A cura arrancada: só o que já está ligado entra na face.

    É a linha exata que o produto NÃO tem — `mesa_do_motor` percorre os números
    da face, e não as chaves do mapa. Aqui ela é reposta de propósito, e o
    gabinete dela encolhe de 16 buracos para 8: as oito entradas em que ela pode
    pôr alguma coisa deixam de existir para o produto.
    """
    from hefesto_dualsense4unix.integrations import mapa_das_portas

    guardado = mapa_das_portas._entradas_da_fileira_da_face

    def so_as_ligadas(mapa: object, numeros: object) -> tuple[str, ...]:
        ligadas = {
            numero for numero, porta in mapa.portas.items()  # type: ignore[attr-defined]
            if porta.caminho
        }
        return tuple(n for n in guardado(mapa, numeros) if n in ligadas)  # type: ignore[arg-type]

    mapa_das_portas._entradas_da_fileira_da_face = so_as_ligadas  # type: ignore[assignment]
    try:
        mesa = _bancada_do_gabinete_dela().mesa  # type: ignore[attr-defined]
        desenhadas = motor.todas_as_entradas(mesa.faces)
        assert len(desenhadas) < _ENTRADAS_DESENHADAS, (
            "a régua passou com a cura arrancada — ela não mede o desenho")
        assert not motor.candidatas(mesa, "pc"), (
            "com o desenho podado ainda sobraram candidatas — a régua está "
            "medindo outra coisa")
    finally:
        mapa_das_portas._entradas_da_fileira_da_face = guardado  # type: ignore[assignment]


def test_a_contagem_da_face_nao_depende_da_ligacao_por_caminho() -> None:
    """§7.5: a CONTAGEM por face e a LIGAÇÃO por caminho são dois donos.

    Apagar todas as ligações não pode encolher o gabinete: o metal continua com
    os mesmos buracos. É a invariante que separa *"quantas entradas esta face
    tem"* de *"o que está em cada uma"*, e é ela que permite ao produto
    desenhar antes de saber qualquer caminho.
    """
    mesa = _bancada_do_gabinete_dela().mesa  # type: ignore[attr-defined]
    com = [e.n for e in motor.todas_as_entradas(mesa.faces)]

    sem_ligacao = motor.Mesa(
        aparelhos=mesa.aparelhos, faces=mesa.faces, mapa={}, leitura=mesa.leitura)
    assert [e.n for e in motor.todas_as_entradas(sem_ligacao.faces)] == com
    assert len(motor.candidatas(sem_ligacao, "pc")) + len(
        motor.candidatas(sem_ligacao, "hub")) == _ENTRADAS_DESENHADAS


# -- A confirmação da ordem, que É o gesto de ensinar (§7.3) ---------------
#
# O produto mandou *"mova o Wi-Fi para a entrada 3"*. Ela move e confirma. O
# gesto que ela escolheu (`D-GESTO-DO-MAPA`, clique-em-clique) é o mesmo ato:
# `LogicaDoMapa.colocar` grava `entrada -> caminho` **do que ela apontou**, e
# nunca do que o produto sugeriu.
#
# POR QUE PERGUNTAR EM VEZ DE PRESUMIR, e é o ponto inteiro: o produto não vê o
# soquete. Se ela puser noutra entrada e ele presumir a que sugeriu, o mapa
# aprende uma mentira — e mapa que mente é pior que mapa vazio.

#: A entrada que a ordem de serviço sugeriu. Vazia no mapa dela, na traseira.
_ENTRADA_SUGERIDA = "3"
#: A entrada em que ela REALMENTE pôs o aparelho. Também vazia, também traseira.
_ENTRADA_ONDE_ELA_POS = "7"
#: O caminho novo do Wi-Fi na leitura de 22h50 — nenhuma entrada o declara.
_CAMINHO_NOVO_DO_WIFI = "4-2"


def _mapa_declarado_do_mockup() -> object:
    """O gabinete do mockup na forma do `maquina.json` — 8 de 16 declaradas."""
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

    faces = [
        {"nome": face.nome,
         "portas": [e.n for e in face.entradas],
         "perto": face.perto, "alto": face.alto}
        for face in mock.FACES
    ]
    portas: dict[str, dict[str, object]] = {
        entrada.n: {} for face in mock.FACES for entrada in face.entradas
    }
    portas["15a"] = {"filha_de": "15"}
    for numero, caminho in mock.MAPA.items():
        portas.setdefault(numero, {})["caminho"] = caminho
    return MapaDaMesa(faces=faces, portas=portas)


def _confirmar(entrada: str) -> dict[str, str]:
    """O 'Já movi' dela, pelo gesto do produto — devolve `entrada -> caminho`.

    É `LogicaDoMapa`, a camada sem GTK que os seis botões do mapa acionam.
    Nenhum widget é criado: o `gi` deste módulo é carregado dentro da janela, e
    a janela não entra aqui.
    """
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa

    logica = LogicaDoMapa(_mapa_declarado_do_mockup())  # type: ignore[arg-type]
    logica.escolhido = _CAMINHO_NOVO_DO_WIFI
    assert logica.colocar(entrada), f"o produto recusou a entrada {entrada}"
    return {
        numero: str(valor["caminho"])
        for numero, valor in logica.portas.items()
        if valor.get("caminho")
    }


def test_a_confirmacao_da_ordem_liga_a_entrada() -> None:
    """O mapa ganha `N -> caminho novo` só quando ela diz que foi para o N.

    O cenário é o MEDIDO da §3: entre 20h15 e 22h50 de 24/08 o Wi-Fi saiu de
    `4-1.1.2` (entrada 11, declarada) para `4-2`, que entrada nenhuma declara.
    """
    mesa_agora = mock.mesa(leitura=mock.LEITURA_AGORA)
    mudou = {m.aparelho.id: m for m in motor.reexame(
        mesa_agora, mock.LEITURA_ANTES, mock.LEITURA_AGORA)}
    assert "wifi" in mudou, sorted(mudou)
    assert mudou["wifi"].agora == _CAMINHO_NOVO_DO_WIFI
    assert mudou["wifi"].entrada_agora is None, (
        "o motor deu uma entrada a um caminho que ninguém declarou — "
        "isso é presumir")

    # SEM RESPOSTA: nada se grava, e o produto tem o que perguntar
    perdidos = {s.aparelho.id: s for s in motor.sem_entrada(mesa_agora)}
    assert "wifi" in perdidos and perdidos["wifi"].regiao == "pc"
    livres = [e.n for e in motor.candidatas(mesa_agora, "pc")]
    assert _ENTRADA_SUGERIDA in livres and _ENTRADA_ONDE_ELA_POS in livres, livres
    assert len(livres) < len(motor.todas_as_entradas(mesa_agora.faces)), (
        "a dedução não cortou candidata nenhuma")

    # "SIM, na que você sugeriu"
    depois_do_sim = _confirmar(_ENTRADA_SUGERIDA)
    assert depois_do_sim[_ENTRADA_SUGERIDA] == _CAMINHO_NOVO_DO_WIFI
    assert _ENTRADA_ONDE_ELA_POS not in depois_do_sim
    aprendida = mock.mesa(mapa=depois_do_sim, leitura=mock.LEITURA_AGORA)
    assert motor.alocacao(aprendida.mapa, aprendida.leitura)[
        _ENTRADA_SUGERIDA] == "wifi"
    assert "wifi" not in {s.aparelho.id for s in motor.sem_entrada(aprendida)}

    # "NÃO, na 7" — o mapa aprende o que ELA disse, e a sugerida fica vazia
    depois_do_nao = _confirmar(_ENTRADA_ONDE_ELA_POS)
    novas = sorted(n for n in depois_do_nao if n not in mock.MAPA)
    assert depois_do_nao.get(_ENTRADA_ONDE_ELA_POS) == _CAMINHO_NOVO_DO_WIFI, (
        f"ela apontou a entrada {_ENTRADA_ONDE_ELA_POS} e o mapa aprendeu "
        f"{novas} — o produto presumiu em vez de gravar o que ela disse")
    assert _ENTRADA_SUGERIDA not in depois_do_nao, (
        f"o mapa gravou a entrada {_ENTRADA_SUGERIDA}, que o produto sugeriu, "
        "e ela disse outra — mapa que mente é pior que mapa vazio")


def test_presumir_a_entrada_sugerida_faz_o_mapa_mentir() -> None:
    """A mordida: gravar a sugerida sem perguntar, e ela ter posto noutra.

    É a cura arrancada da §7.3. O produto presume a `3`, ela pôs na `7`, e a
    partir daí o mapa responde a entrada ERRADA para o Wi-Fi — com a mesma cara
    de quem sabe. Nenhuma leitura futura o corrige: `4-2` passa a ser, para
    sempre, o caminho da entrada 3.
    """
    presumido = dict(mock.MAPA)
    presumido[_ENTRADA_SUGERIDA] = _CAMINHO_NOVO_DO_WIFI
    mentindo = mock.mesa(mapa=presumido, leitura=mock.LEITURA_AGORA)

    onde_o_mapa_diz = motor.entrada_de_em(
        motor.alocacao(mentindo.mapa, mentindo.leitura), "wifi")
    assert onde_o_mapa_diz == _ENTRADA_SUGERIDA
    assert onde_o_mapa_diz != _ENTRADA_ONDE_ELA_POS, (
        "o dublê não reproduziu a mentira — a régua não estaria medindo nada")

    # e o produto perde o único sinal de que não sabia: ele para de perguntar
    assert "wifi" not in {s.aparelho.id for s in motor.sem_entrada(mentindo)}
    assert _ENTRADA_SUGERIDA not in [
        e.n for e in motor.candidatas(mentindo, "pc")], (
        "a entrada presumida continuou candidata — a mentira nem sequer pegou")
