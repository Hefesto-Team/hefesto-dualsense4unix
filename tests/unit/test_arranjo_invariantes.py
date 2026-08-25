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
  5** movimentos, e o plano de ``O melhor no papel`` passa a mandar tirar o cabo
  do hub de uma entrada para pôr noutra igualzinha.

DUAS INVARIANTES DA SPRINT **NÃO** VALEM NO MOTOR QUE RODA
------------------------------------------------------------

Medido aqui, e cada teste abaixo nomeia o buraco em vez de escondê-lo:

* **ponto fixo** vale em três das quatro variantes; ``Sem usar o hub`` precisa de
  uma segunda volta para estabilizar;
* **mapa = receita** vale em ``O melhor no papel`` e ``Mexendo o mínimo``, e
  falha nas duas variantes que **proíbem a entrada de hoje**: o plano desenha o
  dongle saindo do hub, a receita não manda tirá-lo, porque o ganho é negativo.

Isto é registro de medição, não conserto: consertar mudaria o cálculo, e o
cálculo é o que o teste de equivalência trava. A decisão é de quem coordena.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from tests.unit import mesa_do_mockup as mock

MELHOR = motor.variante_por_id("melhor").opcoes
POUCOS = motor.variante_por_id("poucos").opcoes
SEM_EXT = motor.variante_por_id("sem-ext").opcoes
SO_PC = motor.variante_por_id("so-pc").opcoes


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
    sem_bonus = motor.planejar(mesa, motor.Opcoes(bonus_parado=0)).plano
    assert sem_bonus["3"] == "hub"
    assert sem_bonus.get("4") != "hub"


def test_arrancado_o_bonus_mexendo_o_minimo_manda_mexer_em_mais() -> None:
    """A MORDIDA: 4 movimentos viram 5, e o quinto é a webcam mudando à toa."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    com = movimentos(mesa, POUCOS)
    sem = movimentos(mesa, motor.Opcoes(bonus_parado=0, proibir=POUCOS.proibir))
    assert len(com) == 4, com
    assert len(sem) == 5, sem
    webcam = "Mova a webcam da entrada 6 para a 2  ·  melhora, não é urgente"
    assert webcam in sem
    assert webcam not in com


# ══ A REGRA 3: só melhora vira movimento ═════════════════════════════════


def test_ganho_negativo_nao_vira_ordem_de_servico() -> None:
    """Não se manda mexer à toa: quem perde nota fica onde está."""
    mesa = mock.mesa()
    plano = motor.planejar(mesa, SO_PC)
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    titulos = " || ".join(movimentos(mesa, SO_PC))
    perdedores = [
        a.id for a in mesa.aparelhos
        if motor.entrada_de_em(aloc, a.id)
        and plano.motivo[a.id].ganho <= 0
    ]
    assert perdedores, "o cenário deixou de exercitar ganho negativo"
    for quem in perdedores:
        para = motor.entrada_de_em(plano.plano, quem)
        assert f"para a {para}" not in titulos


def test_arrancado_o_filtro_a_receita_manda_mexer_a_toa() -> None:
    """A MORDIDA: sem o filtro, `Sem usar o hub` ganha dois movimentos de ganho negativo."""
    mesa = mock.mesa()
    plano = motor.planejar(mesa, SO_PC)
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    sem_filtro = [
        (a.id, plano.motivo[a.id].ganho)
        for a in mesa.aparelhos
        if (para := motor.entrada_de_em(plano.plano, a.id))
        and motor.entrada_de_em(aloc, a.id) != para
    ]
    assert len(movimentos(mesa, SO_PC)) == 4
    assert len(sem_filtro) == 6, sem_filtro
    inuteis = [x for x in sem_filtro if x[1] <= 0]
    assert [x[0] for x in inuteis] == ["bt-a", "bt-b"]


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
    o pico (554 continua 554): ZERO, que é a guarda do pico fazendo o trabalho.
    """
    equilibrados = (
        motor.Controle("Jogador 1", mic=True, onde="bt-a"),
        motor.Controle("Jogador 2", mic=True, onde="bt-a"),
        motor.Controle("Jogador 3", mic=True, onde="bt-b"),
        motor.Controle("Jogador 4", mic=True, onde="bt-b"),
    )
    plano = motor.plano_dos_controles(equilibrados, DOIS_ADAPTADORES)
    assert _quem_muda(equilibrados, plano) == []
    assert dict(plano.carga) == {"bt-a": 554, "bt-b": 554}

    juntos = tuple(motor.Controle(c.nome, mic=True, onde="bt-a") for c in equilibrados)
    plano = motor.plano_dos_controles(juntos, DOIS_ADAPTADORES)
    assert len(_quem_muda(juntos, plano)) == 2
    assert dict(plano.carga) == {"bt-a": 554, "bt-b": 554}

    tres = equilibrados[:3]
    plano = motor.plano_dos_controles(tres, DOIS_ADAPTADORES)
    assert _quem_muda(tres, plano) == [], "mover não baixaria o pico: 554 continuaria 554"
    assert dict(plano.carga) == {"bt-a": 554, "bt-b": 277}


def test_sem_adaptador_nenhum_o_motor_diz_que_nao_cabe() -> None:
    """A mesa dela às 02h36 de 25/08: o hub saiu e levou os três dongles."""
    mesa = mock.mesa_sem_hub()
    assert motor.adaptadores_da_mesa(mesa) == ()
    plano = motor.plano_dos_controles(mock.CONTROLES, motor.adaptadores_da_mesa(mesa))
    assert plano.cabe is False
    assert plano.sobra == 0
    assert dict(plano.destino) == {}


# ══ AS INVARIANTES DE ESTRUTURA ══════════════════════════════════════════


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


@pytest.mark.parametrize("variante", ["melhor", "poucos"])
def test_todo_aparelho_que_o_mapa_move_a_receita_manda_mover(variante: str) -> None:
    """Mapa = receita: o mapa desenhava a mudança e a receita não a mandava."""
    op = motor.variante_por_id(variante).opcoes
    mesa = mock.mesa()
    plano = motor.planejar(mesa, op)
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    titulos = " || ".join(movimentos(mesa, op))
    for aparelho in mesa.aparelhos:
        para = motor.entrada_de_em(plano.plano, aparelho.id)
        if not para or motor.entrada_de_em(aloc, aparelho.id) == para:
            continue
        assert f"a {para}" in titulos or f"entrada {para}" in titulos


@pytest.mark.parametrize("variante", ["sem-ext", "so-pc"])
def test_a_variante_que_proibe_a_entrada_de_hoje_quebra_mapa_igual_receita(
    variante: str,
) -> None:
    """MEDIDO EM 25/08: o buraco que a MOTOR-2 diz não existir, e existe.

    Quando a variante PROÍBE a entrada em que o dongle está hoje, o planejador
    o realoja (o mapa desenha a mudança) e a receita não manda mexer, porque a
    nota da entrada nova é pior que a da atual — ganho negativo. Quem olha o
    mapa vê o dongle noutro lugar e não recebe ordem nenhuma.
    """
    op = motor.variante_por_id(variante).opcoes
    mesa = mock.mesa()
    plano = motor.planejar(mesa, op)
    aloc = motor.alocacao(mesa.mapa, mesa.leitura)
    titulos = " || ".join(movimentos(mesa, op))
    orfaos = [
        a.id for a in mesa.aparelhos
        if (para := motor.entrada_de_em(plano.plano, a.id))
        and motor.entrada_de_em(aloc, a.id) not in (None, para)
        and f"a {para}" not in titulos
    ]
    assert orfaos, "o buraco fechou — é boa notícia, e o texto acima precisa mudar"
    assert all(plano.motivo[quem].ganho < 0 for quem in orfaos)


# ══ MOTOR-3: o preço em PALAVRA, nunca em pontos ═════════════════════════


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
