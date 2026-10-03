"""As invariantes do motor do arranjo — e a mordida de cada regra."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Iterator
from typing import Any
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import radio_da_mesa as radio
from tests.unit import mesa_do_mockup as mock

MELHOR = motor.variante_por_id("melhor").opcoes
POUCOS = motor.variante_por_id("poucos").opcoes
SEM_EXT = motor.variante_por_id("sem-ext").opcoes
SO_PC = motor.variante_por_id("so-pc").opcoes

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


def test_dois_dongles_identicos_nao_trocam_de_lugar_entre_si() -> None:
    """Com a regra, a receita de 24/08 tem 5 movimentos e nenhum é troca de irmãos."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    assert len(movimentos(mesa)) == 5
    plano = motor.planejar(mesa).plano
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


def test_o_bonus_de_ficar_parado_so_desempata() -> None:
    """+1 mantém o hub na entrada em que está; sem ele, o plano o troca de lugar à toa."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    assert motor.planejar(mesa, MELHOR).plano["4"] == "hub"
    sem_bonus = motor.planejar(mesa, SEM_BONUS).plano
    assert sem_bonus["3"] == "hub"
    assert sem_bonus.get("4") != "hub"


def test_arrancado_o_bonus_mexendo_o_minimo_manda_mexer_em_mais() -> None:
    """A MORDIDA: 4 movimentos viram 6, e os dois a mais são trabalho puro."""
    mesa = mock.mesa(leitura=mock.LEITURA_ANTES)
    com = movimentos(mesa, POUCOS)
    sem = movimentos(mesa, motor.Opcoes(bonus_parado=0, proibir=POUCOS.proibir))
    assert len(com) == 4, com
    assert len(sem) == 6, sem
    webcam = "Mova a webcam da entrada 6 para a 2  ·  melhora, não é urgente"
    assert webcam in sem
    assert webcam not in com
    assert "Mova o cabo do hub da entrada 4 para a 3" in sem


def test_ganho_negativo_nao_vira_ordem_de_servico() -> None:
    """Não se manda mexer à toa — e agora o MAPA obedece à mesma regra."""
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
    """Duas entradas idênticas e um aparelho já numa delas — o empate puro."""
    faces = (motor.Face(nome="Duas iguais", regiao="pc", entradas=(
        motor.Entrada("1", usb=2, onde="pc"), motor.Entrada("2", usb=2, onde="pc"))),)
    return motor.Mesa(
        aparelhos=(motor.Aparelho("cam", "Webcam", "Logitech C920", "webcam"),),
        faces=faces, mapa={"2": "x-2"}, leitura={"cam": "x-2"},
    )


def test_arrancado_o_filtro_a_receita_manda_mexer_a_toa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA: sem o filtro, o mapa E a receita mandam mexer sem ganho nenhum."""
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
    """A MORDIDA na mesa REAL: os três movimentos forçados viram "não é urgente"."""
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


DOIS_ADAPTADORES = (
    motor.Adaptador("bt-a", "9", "entrada 9"),
    motor.Adaptador("bt-b", "15a", "entrada 15a"),
)


def _quem_muda(controles: tuple[motor.Controle, ...],
               plano: motor.PlanoDosControles) -> list[str]:
    return [c.nome for c in controles if plano.destino[c.nome] != c.onde]


def test_ninguem_troca_de_adaptador_sem_baixar_o_pico() -> None:
    """Trocar custa desfazer pareamento, apagar o cache SDP e parear de novo."""
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
    """A MORDIDA, e ela nomeia os três órfãos, um a um."""
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
    """Sair de um lugar bom sem ganho só se justifica com a frase que o explica."""
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
    """MEDIDO EM 25/08: a quarta variante NÃO é ponto fixo de primeira."""
    mesa = mock.mesa()
    primeira = _aplicar(mesa, motor.planejar(mesa, SO_PC))
    assert len(movimentos(primeira, SO_PC)) == 3
    segunda = _aplicar(primeira, motor.planejar(primeira, SO_PC))
    assert movimentos(segunda, SO_PC) == []


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


_FONTE_DO_MOTOR = Path(motor.__file__)

_DE_ONDE_CADA_UMA_VEM: dict[str, set[str]] = {
    "CUSTO_SEM_MIC": {"HZ_INPUT_SEM_MIC", "SLOTS_POR_RELATORIO"},
    "CUSTO_COM_MIC": {"HZ_INPUT_COM_MIC", "HZ_AUDIO_COM_MIC", "SLOTS_POR_RELATORIO"},
    "SLOTS": {"SLOTS_POR_SEGUNDO"},
}


def nomes_que_alimentam(fonte: str, constante: str) -> set[str] | None:
    """Os nomes de que ``constante`` é feita — ou ``None`` se ela virou literal."""
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

    assert motor.CUSTO_SEM_MIC == radio.HZ_INPUT_SEM_MIC * radio.SLOTS_POR_RELATORIO
    assert motor.CUSTO_COM_MIC == (
        radio.HZ_INPUT_COM_MIC + radio.HZ_AUDIO_COM_MIC) * radio.SLOTS_POR_RELATORIO
    assert motor.SLOTS == radio.SLOTS_POR_SEGUNDO
    assert motor.CUSTO_SEM_MIC == 260.4
    assert motor.CUSTO_COM_MIC == 276.7


def test_a_regua_da_copia_sabe_recusar() -> None:
    """Régua que só sabe passar não é régua — esta reprova a cópia literal."""
    copiado = "CUSTO_SEM_MIC = 260\nCUSTO_COM_MIC = 277\nSLOTS = 1600\n"
    for constante in _DE_ONDE_CADA_UMA_VEM:
        assert nomes_que_alimentam(copiado, constante) == set()
    assert nomes_que_alimentam("SLOTS = 1600\n", "CUSTO_SEM_MIC") is None
    derivado = "CUSTO_SEM_MIC = HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO\n"
    assert nomes_que_alimentam(derivado, "CUSTO_SEM_MIC") == {
        "HZ_INPUT_SEM_MIC", "SLOTS_POR_RELATORIO"}


_ORIGEM_CONGELADA = "mockup/congelados/2026-08-24-mapa-das-portas.html"
_COPIA_DO_PRODUTO = ("src/hefesto_dualsense4unix/interface/paginas/mapa-das-portas.html")
_REFERENCIA_DO_DESENHO = "mockup/mapa-das-portas.html"

_CAMINHOS_DO_MOCKUP_DO_ARRANJO = (
    _ORIGEM_CONGELADA,
    _COPIA_DO_PRODUTO,
    _REFERENCIA_DO_DESENHO,
)

_CASAS_VERSIONADAS = (_ORIGEM_CONGELADA, _COPIA_DO_PRODUTO)


def _o_que_o_gerador_escreve() -> str:
    """A BANCADA como `pagina_do_mapa` a escreve, agora."""
    from hefesto_dualsense4unix.interface import pagina_do_mapa

    return pagina_do_mapa.pagina()


def _o_que_o_produto_recebe() -> str:
    """A cópia do PRODUTO como o gerador a responde: sem as edições que esperam."""
    from hefesto_dualsense4unix.interface import pagina_do_mapa

    return pagina_do_mapa.pagina(com_as_que_esperam=False)


def _edicoes() -> tuple[Any, ...]:
    from hefesto_dualsense4unix.interface import pagina_do_mapa

    return tuple(pagina_do_mapa.EDICOES)


def _esperando() -> tuple[Any, ...]:
    from hefesto_dualsense4unix.interface import pagina_do_mapa

    return tuple(pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA)


_DATA_NA_RAZAO = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

_PESO_DA_REGRA = re.compile(r"\{\s*n:\s*(-?\d+),\s*quando:")


_LINK_RELATIVO_DO_MOCKUP = re.compile(r'href="(?!https?:|//|#|mailto:)([^"#?]+\.html)"')


def test_o_mockup_carrega_os_mesmos_numeros_que_o_python() -> None:
    """O número da tela é o número medido — em TODA cópia que exista no disco."""
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
        assert ">277<" not in texto, f"{caminho}: o número arredondado voltou"
        assert "dualsense_bt_audio.py" in texto, (
            f"{caminho}: a legenda tem de citar onde o A/B foi medido")
    assert medidas >= len(_CASAS_VERSIONADAS), (
        f"só {medidas} cópia(s) do mockup foram medidas; as duas casas "
        f"versionadas {_CASAS_VERSIONADAS} viajam com o git e têm de estar aqui")


def test_as_duas_casas_versionadas_do_mockup_nao_andam_sozinhas() -> None:
    """Corrigir nos DOIS foi a palavra dela, e agora é o gerador quem corrige."""
    raiz = _FONTE_DO_MOTOR.parents[3]
    bancada = _o_que_o_gerador_escreve()
    produto = _o_que_o_produto_recebe()
    no_produto = (raiz / _COPIA_DO_PRODUTO).read_text(encoding="utf-8")
    assert not (_esperando() and no_produto == bancada and bancada != produto), (
        "a cópia do produto já recebeu o desenho que espera a sessão dela — no "
        "mesmo commit do `--publicar mapa-das-portas.html`, junte as edições de "
        "`pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA` ao fim de `EDICOES` e "
        "deixe aquela tupla vazia")
    for caminho, esperado in ((_COPIA_DO_PRODUTO, produto), (_REFERENCIA_DO_DESENHO, bancada)):
        arquivo = raiz / caminho
        assert arquivo.exists(), (
            f"{caminho} não está nesta árvore — mas é versionado. Sem ele a "
            "igualdade passaria por vacuidade, que é o pior estado de um portão")
        assert arquivo.read_text(encoding="utf-8") == esperado, (
            f"{caminho} não é o que `interface/pagina_do_mapa.py` escreve.\n"
            "Esta página é GERADA desde 11/09/2026 — mexer no HTML à mão é a\n"
            "mão que a fez divergir treze vezes da origem congelada.\n"
            "FAÇA ASSIM:\n"
            "  1. escreva a mudança como uma `Edicao` em `pagina_do_mapa.EDICOES`,\n"
            "     com a data e o motivo;\n"
            "  2. `python3 -m hefesto_dualsense4unix.interface.pagina_do_mapa`;\n"
            "  3. `scripts/check_o_desenho_aprovado.py --publicar mapa-das-portas.html`.")


def test_toda_edicao_do_gerador_acha_o_seu_alvo_uma_vez() -> None:
    """Edição que erra o alvo é edição que não aconteceu — e cala."""
    raiz = _FONTE_DO_MOTOR.parents[3]
    origem = (raiz / _ORIGEM_CONGELADA).read_text(encoding="utf-8")
    produto = (raiz / _COPIA_DO_PRODUTO).read_text(encoding="utf-8")
    bancada = (raiz / _REFERENCIA_DO_DESENHO).read_text(encoding="utf-8")
    edicoes = _edicoes()
    assert edicoes, "nenhuma edição — a régua passaria por vacuidade"
    casas = [(edicoes, produto, "cópia do produto"),
             (edicoes + _esperando(), bancada, "bancada")]
    for lista, casa, nome_da_casa in casas:
        texto = origem
        vez: list[str] = []
        for edicao in lista:
            assert texto.count(edicao.antes) == 1, (
                f"edição {len(vez) + 1}: o pedaço aparece "
                f"{texto.count(edicao.antes)} vez(es) no texto da vez dela, e "
                f"tem de aparecer UMA.\n  motivo declarado: {edicao.porque}")
            texto = texto.replace(edicao.antes, edicao.depois, 1)
            vez.append(texto)
        assert texto == casa, f"a {nome_da_casa} não é o que as edições escrevem"
        for numero, edicao in enumerate(lista, 1):
            if not edicao.depois:
                assert edicao.antes not in casa, (
                    f"edição {numero} tira um pedaço que voltou à {nome_da_casa}")
                continue
            if casa.count(edicao.depois) == 1:
                continue
            consumida = any(
                edicao.depois in vez[j - 1] and edicao.depois not in vez[j]
                for j in range(numero, len(lista)))
            assert consumida, (
                f"edição {numero}: o que ela escreve aparece "
                f"{casa.count(edicao.depois)} vez(es) na {nome_da_casa}, e "
                "nenhuma edição de depois o consumiu. Ou a página não foi "
                "regerada, ou duas edições escrevem a mesma coisa.\n"
                f"  motivo declarado: {edicao.porque}")
    for numero, edicao in enumerate(edicoes + _esperando(), 1):
        assert _DATA_NA_RAZAO.search(edicao.porque), (
            f"edição {numero} não diz QUANDO foi decidida: {edicao.porque!r}. "
            "Uma razão sem data é uma razão que ninguém consegue conferir "
            "depois — e é a porta por onde uma mudança sem dono entra.")


def test_nenhuma_edicao_mexe_nos_pesos_do_motor() -> None:
    """O que a página DECIDE é o que a origem decide — medido nos pesos."""
    raiz = _FONTE_DO_MOTOR.parents[3]
    origem = _PESO_DA_REGRA.findall((raiz / _ORIGEM_CONGELADA).read_text(encoding="utf-8"))
    produto = _PESO_DA_REGRA.findall((raiz / _COPIA_DO_PRODUTO).read_text(encoding="utf-8"))
    assert len(origem) >= 10, (
        f"li {len(origem)} pesos na origem congelada, e a tabela de regras tem "
        "mais que isso — o seletor ficou cego e a régua passaria por vacuidade")
    assert produto == origem, (
        "os pesos das regras do produto não são os da origem congelada. "
        "Alguma edição mexeu no que a página DECIDE, não no que ela diz — e o "
        f"ouro do `fumaca.js` não veria.\n  origem:  {origem}\n  produto: {produto}")


def test_a_regua_da_igualdade_sabe_recusar() -> None:
    """A MORDIDA: um byte fora do lugar derruba a comparação."""
    raiz = _FONTE_DO_MOTOR.parents[3]
    esperado = _o_que_o_produto_recebe()
    produto = (raiz / _COPIA_DO_PRODUTO).read_text(encoding="utf-8")
    bancada = (raiz / _REFERENCIA_DO_DESENHO).read_text(encoding="utf-8")
    assert produto == esperado

    assert produto.replace("</html>", "</html> ") != esperado

    from hefesto_dualsense4unix.interface import pagina_do_mapa

    inteiras = pagina_do_mapa.EDICOES
    for fora in range(len(inteiras)):
        pagina_do_mapa.EDICOES = inteiras[:fora] + inteiras[fora + 1:]
        try:
            sem_uma = pagina_do_mapa.pagina(com_as_que_esperam=False)
        except SystemExit:
            continue
        finally:
            pagina_do_mapa.EDICOES = inteiras
        assert sem_uma != produto, (
            f"arrancar a edição {fora + 1} não mudou a página — ela não faz nada, "
            f"e uma edição que não muda nada é um perdão morto: {inteiras[fora].porque}")

    esperando = pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA
    for fora in range(len(esperando)):
        pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA = esperando[:fora] + esperando[fora + 1:]
        try:
            sem_uma = pagina_do_mapa.pagina()
        finally:
            pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA = esperando
        assert sem_uma != bancada, (
            f"arrancar a edição que espera {fora + 1} não mudou a bancada — ela "
            f"não faz nada: {esperando[fora].porque}")


def test_a_palavra_que_ela_baniu_nao_esta_na_tela_do_mapa() -> None:
    """A palavra saiu da TELA, e é na tela que se mede — não numa lista de pares."""
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        texto_visivel_no_produto,
    )

    raiz = _FONTE_DO_MOTOR.parents[3]
    banida = re.compile(r"\bmesas?\b", re.I)
    na_origem = banida.findall(
        texto_visivel_no_produto((raiz / _ORIGEM_CONGELADA).read_text(encoding="utf-8")))
    assert na_origem, (
        "a origem congelada não diz mais a palavra — ou ela foi reescrita (e "
        "não podia ser), ou este leitor parou de ver o texto da tela. Nos dois "
        "casos a régua abaixo estaria medindo o nada")
    for caminho in (_COPIA_DO_PRODUTO, _REFERENCIA_DO_DESENHO):
        visivel = texto_visivel_no_produto((raiz / caminho).read_text(encoding="utf-8"))
        achados = banida.findall(visivel)
        assert not achados, (
            f"{caminho}: {len(achados)} ocorrência(s) da palavra que ela baniu "
            f"chegam aos olhos de quem abre — {sorted(set(achados))}")


def test_nenhum_botao_do_mockup_vai_a_lugar_nenhum() -> None:
    """Botão que aponta para arquivo que não existe ao lado não está entregue."""
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


_SUPERFICIE_DA_PRODUCAO = ("app", "interface", "gui")

_ASSINATURA_MINIMA = 25

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
    "interface/pagina_do_mapa.py": (
        "O GERADOR DA PÁGINA, e a frase está lá como ALVO de uma troca, não como "
        "regra. Ele escreve `mapa-das-portas.html` lendo a origem congelada e "
        "aplicando as `EDICOES`; uma delas troca a palavra que ela baniu dentro "
        "de uma razão do motor, e para trocar é preciso nomear o que se troca. "
        "A CÓPIA NÃO PODE ENVELHECER EM SILÊNCIO — que é o que esta varredura "
        "existe para impedir: o gerador exige que cada `antes` apareça UMA vez "
        "na origem e sai com `SystemExit` quando não aparece. No dia em que a "
        "origem disser outra coisa, o gerador PARA; nenhuma outra cópia desta "
        "casa tem essa garantia."
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
    """As funções que reescrevem a tabela de notas: dois pesos e uma classe."""
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
    """Régua que só sabe passar não é régua: os dois dublês são acusados."""
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

    consome = (
        "from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor\n"
        "def veredito_do_quadrado(bancada, numero, escolhido):\n"
        "    entrada = motor.por_num(bancada.mesa.faces, numero)\n"
        "    return motor.julgar(entrada, 'bt', bancada.mesa, escolhido)\n"
    )
    assert quem_recalcula_a_nota(consome) == []


def test_todo_perdao_da_varredura_esta_vivo() -> None:
    """Perdão que não dispara é perdão morto — e porta dos fundos aberta."""
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
    """O gabinete desenha os buracos que ele TEM, não os que já foram ligados."""
    mesa = _bancada_do_gabinete_dela().mesa  # type: ignore[attr-defined]
    desenhadas = motor.todas_as_entradas(mesa.faces)
    assert len(desenhadas) == _ENTRADAS_DESENHADAS, [e.n for e in desenhadas]
    assert len(mesa.mapa) == _ENTRADAS_COM_CAMINHO, mesa.mapa

    vazias = [e.n for e in desenhadas if e.n not in mesa.mapa]
    assert len(vazias) == _ENTRADAS_DESENHADAS - _ENTRADAS_COM_CAMINHO, vazias

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
    """A cura arrancada: só o que já está ligado entra na face."""
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
    """§7.5: a CONTAGEM por face e a LIGAÇÃO por caminho são dois donos."""
    mesa = _bancada_do_gabinete_dela().mesa  # type: ignore[attr-defined]
    com = [e.n for e in motor.todas_as_entradas(mesa.faces)]

    sem_ligacao = motor.Mesa(
        aparelhos=mesa.aparelhos, faces=mesa.faces, mapa={}, leitura=mesa.leitura)
    assert [e.n for e in motor.todas_as_entradas(sem_ligacao.faces)] == com
    assert len(motor.candidatas(sem_ligacao, "pc")) + len(
        motor.candidatas(sem_ligacao, "hub")) == _ENTRADAS_DESENHADAS


_ENTRADA_SUGERIDA = "3"
_ENTRADA_ONDE_ELA_POS = "7"
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
    """O 'Já movi' dela, pelo gesto do produto — devolve `entrada -> caminho`."""
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa

    logica = LogicaDoMapa(_mapa_declarado_do_mockup())  # type: ignore[arg-type]
    logica.escolhido = _CAMINHO_NOVO_DO_WIFI
    assert logica.colocar(entrada), f"o produto recusou a entrada {entrada}"
    return {
        numero: str(valor["caminho"])
        for numero, valor in logica.portas.items()
        if valor.get("caminho")
    }


def test_presumir_a_entrada_sugerida_faz_o_mapa_mentir() -> None:
    """A mordida: gravar a sugerida sem perguntar, e ela ter posto noutra."""
    presumido = dict(mock.MAPA)
    presumido[_ENTRADA_SUGERIDA] = _CAMINHO_NOVO_DO_WIFI
    mentindo = mock.mesa(mapa=presumido, leitura=mock.LEITURA_AGORA)

    onde_o_mapa_diz = motor.entrada_de_em(
        motor.alocacao(mentindo.mapa, mentindo.leitura), "wifi")
    assert onde_o_mapa_diz == _ENTRADA_SUGERIDA
    assert onde_o_mapa_diz != _ENTRADA_ONDE_ELA_POS, (
        "o dublê não reproduziu a mentira — a régua não estaria medindo nada")

    assert "wifi" not in {s.aparelho.id for s in motor.sem_entrada(mentindo)}
    assert _ENTRADA_SUGERIDA not in [
        e.n for e in motor.candidatas(mentindo, "pc")], (
        "a entrada presumida continuou candidata — a mentira nem sequer pegou")
