#!/usr/bin/env python3
"""OS SETE DA ABA CONEXÕES: eles RECUSARAM, e a régua é que leu "mentiu".

**02/09/2026.** O mapa daquele dia listou dezesseis gestos que *"dizem aplicado
e não mudam nada"*, e sete deles são desta aba:

    escolher-aparelho · escolher-entrada · luz-nao-acende · nova-entrada ·
    nova-extensao · nova-face · tirar-daqui

**Nenhum dos sete disse "aplicado".** Medido com dublê da ponte, sem tocar o
daemon vivo: os sete LEVANTAM com o clique que o instrumento deu — o clique
automático não levava o argumento do próprio botão (`caminho`, `entrada`,
`face`, `uniq`), e cada um recusou com a frase que o desenho promete.

O QUE PRODUZIU A ACUSAÇÃO, e é defeito de RÉGUA, não de gesto:
`_depois_do_gesto`, em `interface/hefesto_vivo.py`, compara o estado do daemon
antes e depois do clique e **não pergunta se o gesto levantou**. Quando ele
levanta, o piloto imprime `[gesto falhou]` no stderr e `self.aplicados` não
recebe nada — mas a prova já foi guardada como "sem efeito". Um gesto que
RECUSOU DIZENDO cai na mesma lista de um que mentiu.

A CLASSIFICAÇÃO QUE ESTA RÉGUA TRAVA, e é o que ela existe para não deixar
regredir:

    monte              gestos                          o que a régua cobra
    (a) recusa certa   luz-nao-acende                  FORA do `SEM_ECO`
    (b) não ecoa       os SEIS do mapa do gabinete     DENTRO, com razão escrita
    (c) mentiu         nenhum                          —

**`luz-nao-acende` fora do `SEM_ECO` é o ponto mais fino daqui.** Ele é o único
dos sete com eco de verdade — derrubar um controle do rádio o tira da lista
`controllers` do `state_full`. Declará-lo sem eco cegaria a régua onde ela mais
enxerga: um `Disconnect` que não derrubasse nada passaria a contar como sucesso.

A MORDIDA: tire `escolher-entrada` do `SEM_ECO` do pacote, ou acrescente
`luz-nao-acende` a ele — os dois casos reprovam, cada um com a sua frase.
"""
from __future__ import annotations

import ast
import io
import pathlib
import sys
import tokenize
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "08-conexoes.html"

GABINETE = {
    "faces": [{"nome": "Traseira", "portas": ["1", "2"], "perto": False,
               "alto": False},
              {"nome": "Frontal", "portas": ["3"], "perto": True,
               "alto": False}],
    "portas": {"1": {"caminho": None},
               "2": {"caminho": "3-1.1.4"},
               "3": {"caminho": None}},
}

UNIQ_RADIO = "aabbcc000001"
UNIQ_CABO = "aabbcc000002"
#: que volta `player: None` — a assinatura é `is_primary`, não o transporte.
CONECTADOS = [
    {"uniq": UNIQ_RADIO, "index": 0, "transport": "bt", "connected": True,
     "player": 1, "player_slot": 1, "is_primary": True, "battery_pct": 95},
    {"uniq": UNIQ_CABO, "index": 1, "transport": "usb", "connected": True,
     "player": None, "player_slot": 2, "is_primary": False, "battery_pct": 95},
]

CEGO = {"controle": "p1", "texto": "Régua"}

DIRIGIDO: dict[str, dict[str, Any]] = {
    "escolher-aparelho": {"caminho": "3-1.1.4"},
    "escolher-entrada": {"entrada": "1"},
    "tirar-daqui": {"entrada": "2"},
    "nova-entrada": {"face": "0"},
    "nova-extensao": {"entrada": "2"},
    "nova-face": {"valor": "Lateral"},
    "luz-nao-acende": {"uniq": UNIQ_CABO},
}

DO_GABINETE = ("escolher-aparelho", "escolher-entrada", "tirar-daqui",
               "nova-entrada", "nova-extensao", "nova-face")


class PonteDeMentira:
    """Guarda o que foi pedido à ponte. Responde a qualquer nome, de propósito."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return True
        return registrar


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture(autouse=True)
def gabinete_de_bancada(a08, monkeypatch):
    """Um rascunho novo por caso, e NUNCA o `maquina.json` de quem roda."""
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

    monkeypatch.setattr(a08, "_LOGICA",
                        LogicaDoMapa(MapaDaMesa.model_validate(GABINETE)),
                        raising=False)


@pytest.fixture(autouse=True)
def o_radio_nunca_e_tocado(monkeypatch):
    """`desconectar` vira dublê — e esta trava nasceu de um susto MEDIDO.

    Rodando a MORDIDA desta régua (arrancar a recusa do cabo do
    `luz_nao_acende`), o caso chegou ao `gesto_de_reconexao.desconectar` de
    verdade e o log da suíte imprimiu `reconexao_ja_estava_fora` com o endereço
    do controle DELA. Naquele instante nada caiu — o do cabo não estava no rádio
    —, mas o caminho estava aberto: a mesma régua, com o controle do rádio na
    lista, teria mandado um `Disconnect` no BlueZ da máquina de quem a roda.

    **Um teste unitário não fala com o rádio de ninguém.** O dublê devolve o
    desfecho de sucesso, que é o pior caso para a régua: se o gesto passar a
    aceitar o clique do cabo, ele vai parecer que funcionou — e é exatamente o
    que `test_nenhum_dos_sete_e_o_monte_c` tem de pegar.
    """
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao

    def de_mentira(uniq: str, **_):
        return gesto_de_reconexao.Resultado(
            estado=gesto_de_reconexao.ESTADO_DESCONECTOU,
            porque="caiu do rádio (dublê da régua)",
            endereco=gesto_de_reconexao.mascarar(uniq))

    monkeypatch.setattr(gesto_de_reconexao, "desconectar", de_mentira)


def _gesto(pac, nome: str):
    fn = pac.gesto_da_pagina(PAGINA, nome)
    assert fn is not None, f"{PAGINA}:{nome} perdeu o dono"
    return fn


def _ctx(pac):
    return pac.Contexto(state={"active_profile": "regua"}, mesa=[],
                        conectados=CONECTADOS, estados={})


def _onde_a_razao_mora(caminho: pathlib.Path) -> str:
    """A prosa que EXPLICA o `SEM_ECO`, e só ela — não o arquivo inteiro."""
    texto = caminho.read_text(encoding="utf-8")
    linhas = texto.splitlines()

    fim = next(i for i, linha in enumerate(linhas)
               if linha.startswith("SEM_ECO"))
    inicio = fim
    while inicio > 0 and (linhas[inicio - 1].startswith("#")
                          or not linhas[inicio - 1].strip()):
        inicio -= 1
    pedacos = linhas[inicio:fim]

    for no in ast.walk(ast.parse(texto)):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            doc = ast.get_docstring(no)
            if doc:
                pedacos.append(doc)
    for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
        if tok.type == tokenize.COMMENT and inicio < tok.start[0] <= fim:
            pedacos.append(tok.string)
    return "\n".join(pedacos)


@pytest.mark.parametrize("nome", [*DO_GABINETE, "luz-nao-acende"])
def test_o_clique_sem_o_argumento_do_botao_recusa_dizendo(pac, nome) -> None:
    """A prova de que a acusação de 02/09 mediu recusa, não mentira."""
    p = PonteDeMentira()
    with pytest.raises((ValueError, RuntimeError)) as caiu:
        _gesto(pac, nome)(_ctx(pac), dict(CEGO), p)

    frase = str(caiu.value).strip()
    assert len(frase) >= 20, (
        f"{nome} recusou com {frase!r} — recusar DIZENDO é regra desta casa, e "
        f"uma frase de menos de vinte letras não diz o que fazer em seguida.")
    assert p.chamadas == [], (
        f"{nome} recusou o clique E AINDA ASSIM falou com o daemon "
        f"({[c[0] for c in p.chamadas]}). Recusa que grava é o pior dos dois "
        f"mundos: a tela diz que não deu, e o disco mudou.")


def test_escolher_aparelho_guarda_na_mao_e_nao_fala_com_o_daemon(pac, a08) -> None:
    """O primeiro tempo do gesto de dois: guardar é tudo o que ele faz.

    É por isso que a razão dele no `SEM_ECO` é DIFERENTE da dos outros cinco:
    eles não ecoam porque o `state_full` não publica o mapa; este não ecoa
    porque não chama a ponte de forma nenhuma.
    """
    p = PonteDeMentira()
    _gesto(pac, "escolher-aparelho")(
        _ctx(pac), {**CEGO, **DIRIGIDO["escolher-aparelho"]}, p)

    assert a08._LOGICA.escolhido == "3-1.1.4", (
        "o aparelho não ficou na mão — sem isso o segundo tempo não tem o que "
        "pôr na entrada, e o gesto de dois tempos vira dois cliques mudos.")
    assert p.chamadas == [], (
        "escolher passou a gravar. Escolher é estado de TELA: gravar aqui "
        "poria no `maquina.json` dela uma escolha que ela ainda não confirmou.")


@pytest.mark.parametrize("nome", ["tirar-daqui", "nova-entrada",
                                  "nova-extensao", "nova-face"])
def test_os_quatro_que_gravam_mandam_o_gabinete_inteiro(pac, nome) -> None:
    """Cada um chama `machine_declare` UMA vez, com o mapa INTEIRO dentro.

    O inteiro, e não um pedaço: as faces são uma LISTA e `fundir_declaracao`
    troca lista inteira em vez de fundir. Meia lista apagaria do disco as faces
    que ela já tinha.
    """
    p = PonteDeMentira()
    _gesto(pac, nome)(_ctx(pac), {**CEGO, **DIRIGIDO[nome]}, p)

    assert [c[0] for c in p.chamadas] == ["machine_declare"], (
        f"{nome} chamou {[c[0] for c in p.chamadas]}. Ele grava o desenho do "
        f"gabinete, e o caminho é um só.")
    documento = p.chamadas[0][1][0]
    assert set(documento) == {"mapa"}, (
        f"{nome} declarou {sorted(documento)} — o mapa não escreve noutra "
        f"seção do `maquina.json`.")
    assert documento["mapa"]["faces"], (
        f"{nome} mandou o mapa SEM FACES. `fundir_declaracao` troca a lista "
        f"inteira: isto apagaria do disco o gabinete que ela desenhou.")


def test_o_gesto_de_dois_tempos_grava_no_segundo(pac) -> None:
    """Escolher não grava; pôr grava — e o que vai é o aparelho escolhido."""
    p = PonteDeMentira()
    _gesto(pac, "escolher-aparelho")(
        _ctx(pac), {**CEGO, "caminho": "3-1.1.4"}, p)
    assert p.chamadas == [], "o primeiro tempo gravou"

    _gesto(pac, "escolher-entrada")(_ctx(pac), {**CEGO, "entrada": "1"}, p)
    assert [c[0] for c in p.chamadas] == ["machine_declare"]
    portas = p.chamadas[0][1][0]["mapa"]["portas"]
    assert portas["1"]["caminho"] == "3-1.1.4", (
        "o segundo tempo não pôs o aparelho na entrada clicada.")
    assert not portas["2"]["caminho"], (
        "um aparelho está em UM lugar: pôr na 1 tem de tirar da 2, no mesmo "
        "gesto. Sem isso o mesmo dongle apareceria em duas entradas.")


def test_escolher_entrada_sem_o_primeiro_tempo_recusa_dizendo(pac) -> None:
    """Clicar a entrada sem ter escolhido o aparelho não tem o que fazer."""
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as caiu:
        _gesto(pac, "escolher-entrada")(_ctx(pac), {**CEGO, "entrada": "1"}, p)
    assert "dois tempos" in str(caiu.value), (
        f"a recusa virou {str(caiu.value)!r} e parou de ensinar o gesto.")
    assert p.chamadas == []


def test_a_luz_no_cabo_recusa_dizendo_e_nao_derruba_nada(pac) -> None:
    """No cabo a barra de luz não depende de reconexão nenhuma."""
    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as caiu:
        _gesto(pac, "luz-nao-acende")(
            _ctx(pac), {**CEGO, "uniq": UNIQ_CABO}, p)

    frase = str(caiu.value)
    assert "cabo" in frase, (
        f"a recusa virou {frase!r} e parou de dizer POR QUE não dá. Quem lê "
        f"precisa saber que a cura é do rádio.")
    assert p.chamadas == [], "recusou e mesmo assim falou com o daemon"


def test_a_luz_nao_e_sem_eco_porque_derrubar_do_radio(a08) -> None:
    """O único dos sete com eco de verdade — e declará-lo cegaria a régua.

    Derrubar um controle do rádio o tira da lista `controllers` do `state_full`.
    Pôr `luz-nao-acende` em `SEM_ECO` faria um `Disconnect` que não derrubou
    nada passar a contar como sucesso, e é justamente o desfecho que
    `gesto_de_reconexao.Resultado.nao_deu` existe para acusar.
    """
    assert "luz-nao-acende" not in a08.SEM_ECO, (
        "`luz-nao-acende` entrou no `SEM_ECO`. Ele NÃO é sem eco: derrubar do "
        "rádio muda a lista de controles do `state_full`. Se o gesto passou a "
        "não ter efeito, o defeito é dele — não da régua que o mede.")


@pytest.mark.parametrize("nome", DO_GABINETE)
def test_os_seis_do_gabinete_estao_declarados_sem_eco(a08, nome) -> None:
    """Medido em 02/09: o `state_full` não publica `mapa` nem `maquina`.

    As chaves de topo do daemon vivo eram 47, e nenhuma delas é o desenho do
    gabinete. O caminho é `machine_declare` → `_handle_machine_declare` →
    `maquina.json`, e ali ele para. Sem esta declaração, a régua do piloto
    acusa os seis a cada rodada e a lista de defeitos nunca esvazia.
    """
    assert nome in a08.SEM_ECO, (
        f"{nome} saiu do `SEM_ECO`. Ele grava no `maquina.json` e o daemon não "
        f"republica isso — a régua do piloto vai chamá-lo de mudo para sempre.")


def test_todo_sem_eco_desta_aba_tem_razao_escrita(a08) -> None:
    """`SEM_ECO` sem razão escrita é lápide para esconder defeito."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/"
             "a08_conexoes.py")
    prosa = _onde_a_razao_mora(fonte)
    mudos = [nome for nome in a08.SEM_ECO if nome not in prosa]
    assert mudos == [], (
        f"estes gestos estão em `SEM_ECO` e ninguém escreveu por quê: {mudos}. "
        f"Uma declaração sem razão é indistinguível de um defeito escondido — "
        f"a próxima pessoa não tem como saber se o daemon não ecoa ou se o "
        f"gesto parou de funcionar.")


def test_nenhum_dos_sete_e_o_monte_c(pac, a08) -> None:
    """O fecho da classificação: nenhum dos sete MENTIU, e isso é verificável."""
    mentirosos = []
    for nome in (*DO_GABINETE, "luz-nao-acende"):
        p = PonteDeMentira()
        try:
            _gesto(pac, nome)(_ctx(pac), {**CEGO, **DIRIGIDO[nome]}, p)
        except (ValueError, RuntimeError):
            continue
        if not p.chamadas and nome not in a08.SEM_ECO:
            mentirosos.append(nome)
    assert mentirosos == [], (
        f"{mentirosos} aceitaram o clique, não falaram com o daemon e não estão "
        f"declarados em `SEM_ECO`. Isto é o 'responde calado': a tela diz "
        f"aplicado e nada aconteceu.")
