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
from collections.abc import Iterator
from pathlib import Path

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


def test_o_mockup_carrega_os_mesmos_numeros_que_o_python() -> None:
    """Corrigir nos DOIS foi a palavra dela, e esta linha é o que a mantém viva.

    A paridade de ``test_arranjo_da_mesa_bate_com_o_mockup.py`` já pegaria uma
    divergência de CÁLCULO. Esta pega a divergência de TEXTO: o mockup é o
    artefato que ela abre com duplo clique, e um número arredondado na legenda
    seria a segunda verdade voltando pela porta da tela.
    """
    mockup = _FONTE_DO_MOTOR.parents[3] / (
        "docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html")
    if not mockup.exists():  # pragma: no cover - árvore de agente sem os docs
        pytest.skip("o mockup não está nesta árvore")
    texto = mockup.read_text(encoding="utf-8")
    assert "var CUSTO_SEM_MIC = 260.4, CUSTO_COM_MIC = 276.7, SLOTS = 1600;" in texto
    assert ">276,7</b>/s" in texto
    assert ">260,4</b>/s" in texto
    assert ">277<" not in texto
