#!/usr/bin/env python3
"""A aba Jogar LÊ o que mostra — o interruptor, o chip, a máscara e os avisos.

POR QUE ESTA RÉGUA EXISTE, e o que ela mede foi fotografado em 02/09/2026 e
remedido no daemon dela em 03/09. Com ``native_mode false`` e
``gamepad_emulation.enabled false`` — logo ``mode_of_state`` = **desktop** — a
página publicada mostrava, ao mesmo tempo:

    interruptor      **Ligado**       (o `<input>` do arquivo nasce `checked`)
    fileira de modo  **Sony DualSense** aceso (`aba01.MODO_ACESO`, cravado)
    cartão do P2     **Xbox 360** aceso, com o daemon em `flavor=dualsense`
    coluna Atenção   selo verde **CERTO** sob o cabeçalho laranja "Atenção"
    conta            "3 avisos", com UM par `aviso-selo`/`aviso-texto` na página

Nenhuma dessas quatro coisas era atraso de tique: **não havia quem repintasse**.
A página tinha 11 `data-campo` e ZERO `data-hef-quando`, então nenhum ESTADO —
posição do interruptor, chip aceso, máscara acesa — chegava do daemon.

O QUE A RÉGUA COBRA, e cada item é uma forma de a cura morrer calada:

* o pacote **lê** os três estados (posição, chip, máscara) das funções do
  produto, e a régua troca essas funções para provar que ele as segue — uma
  régua que comparasse textos passaria com o pacote digitando o valor;
* **daemon calado não pinta nada.** É a armadilha desta aba: ``mode_of_state({})``
  devolve ``desktop``, então um pacote descuidado acende **Ligado** sobre um
  estado que ninguém leu;
* a coluna **Atenção** sai de ``painel.avisos_do_estado`` — as seis fontes puras
  da GTK — mais o opt-out antigo, e **não** dos achados `certo` do Check-up;
* o selo do exame é o do produto: a linha antiga montava
  ``{"selo": …, **i}`` e o ``**i`` sobrescrevia o selo pretendido;
* a página publica os endereços, na quantidade certa — um a menos deixa uma
  posição acesa para sempre;
* o ``ACHADO_DO_TIMEOUT`` fala do ``ponte.TETOS`` de hoje, e não dos 250 ms que
  a cura já tinha substituído.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import aba01, onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O DAEMON DELA EM 03/09/2026, nas chaves que esta aba lê. Ele está em
#: **desktop** — a Navegação —, que é o caso que a tela errava: o modo não é
#: nenhum dos dois lados óbvios do interruptor, e `hefesto_ligado` responde
#: **Ligado** porque o Hefesto está no meio entregando teclado e mouse.
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense",
                          "wrapper_used": None, "mascara_divergente": None},
    "paused": False,
    "controllers": [{"uniq": "aa", "connected": True, "player_slot": 1}],
}
VIVO_GAMEPAD_XBOX: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
    "paused": False,
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


# ---------------------------------------------------------------------------
# 1. O ESTADO CHEGA À TELA — os três endereços que faltavam
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("state", "posicao", "chip"),
    [
        (VIVO_NAVEGACAO, "ligado", "navegacao"),
        (VIVO_GAMEPAD_XBOX, "ligado", "xbox"),
        (VIVO_NATIVO, "desligado", ""),
    ],
)
def test_o_interruptor_e_o_chip_saem_do_daemon(
    state: dict[str, Any], posicao: str, chip: str
) -> None:
    """Os três casos que a tela cravada errava — e o do meio é o que mais dói.

    Com o daemon em `desktop` a GTK marcaria "Controlar o PC"; a página mostrava
    **Ligado** + **Sony DualSense**. O `Ligado` até está certo (o Hefesto está no
    meio), mas por acaso: nada o tinha lido.
    """
    fora = aba.pacote(_ctx(state))
    assert fora["hef-posicao"] == posicao, (
        f"a posição do interruptor saiu {fora['hef-posicao']!r} com o daemon em "
        f"{painel.modo_vivo(state)!r}")
    assert fora["modo-aceso"] == chip, (
        f"o chip aceso saiu {fora['modo-aceso']!r} e o daemon está em "
        f"{painel.modo_vivo(state)!r}")


def test_a_mascara_do_cartao_e_a_do_aparelho() -> None:
    """O chip **Xbox 360** aceso no cartão do P2 com o daemon em `dualsense`.

    Era o desenho falando pelo produto. A máscara é UMA para a máquina —
    `gamepad.emulation.set` não recebe `uniq` —, então o endereço é da MESA e
    todos os chips de todos os cartões decidem por si.
    """
    assert aba.pacote(_ctx(VIVO_NAVEGACAO))["mascara-cartao"] == "DualSense"
    assert aba.pacote(_ctx(VIVO_GAMEPAD_XBOX))["mascara-cartao"] == "Xbox 360"


def test_nintendo_pro_nunca_acende() -> None:
    """Ele não é máscara do produto: o daemon recusa tudo o que não for os dois.

    O chip fica na tela por ordem dela; apagado é a verdade sobre ele. Se algum
    dia esta linha reprovar, é porque alguém traduziu uma máscara que o
    `ipc_handlers` recusa.
    """
    for state in (VIVO_NAVEGACAO, VIVO_GAMEPAD_XBOX, VIVO_NATIVO):
        assert aba.pacote(_ctx(state))["mascara-cartao"] != "Nintendo Pro"


def test_o_daemon_calado_nao_acende_nada() -> None:
    """A armadilha desta aba: `mode_of_state({})` devolve **desktop**.

    Ele só devolve `None` para um NÃO-dicionário. Sem a guarda, um tique sem
    resposta acenderia **Ligado** e o chip **Navegação** sobre um estado que
    ninguém leu — a tela afirmando com o Hefesto fora do ar.
    """
    fora = aba.pacote(_ctx({}))
    assert fora["hef-posicao"] == ""
    assert fora["modo-aceso"] == ""
    assert fora["mascara-cartao"] == ""


def test_a_leitura_e_do_produto_e_nao_uma_copia(monkeypatch: Any) -> None:
    """Troca os dois leitores do produto e cobra que o pacote os siga.

    Uma tradução digitada aqui passaria nos casos acima com as funções
    originais intactas — e é por isso que a régua as TROCA, em vez de comparar
    valores. É a mesma forma da régua da faixa laranja.
    """
    from hefesto_dualsense4unix.app.actions import home_actions

    monkeypatch.setattr(painel, "hefesto_ligado", lambda _s: False)
    monkeypatch.setattr(painel, "modo_vivo", lambda _s: "gamepad")
    monkeypatch.setattr(home_actions, "mascara_do_aparelho", lambda _s: "xbox")
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["hef-posicao"] == "desligado", (
        "o pacote deixou de usar `painel.hefesto_ligado` — a posição virou cópia")
    assert fora["modo-aceso"] == "xbox", (
        "o pacote deixou de usar `painel.modo_vivo` + `mascara_do_aparelho`")
    assert fora["mascara-cartao"] == "Xbox 360"


# ---------------------------------------------------------------------------
# 2. A COLUNA ATENÇÃO — a ponte que faltava
# ---------------------------------------------------------------------------
def test_a_coluna_atencao_sai_das_fontes_da_gtk(monkeypatch: Any) -> None:
    """Troca `painel.avisos_do_estado` e cobra que os avisos venham de lá.

    As seis fontes de `painel.AVISOS_DA_TELA` já existiam em `home_actions` e
    quem as chamava era a BANCADA (`interface/jogar_vivo.py`). O produto
    mostrava, no lugar delas, o Check-up da aba Conexões — dois conjuntos
    disjuntos, e o da GTK era o que respondia pelas perguntas desta tela.
    """
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": "de outro dono", "fonte": "x"}])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert "PAUSA" in fora["aviso-selo"], (
        "o pacote deixou de chamar `painel.avisos_do_estado`")
    assert "de outro dono" in fora["aviso-texto"]


def test_uma_boa_noticia_nao_entra_na_coluna_atencao(monkeypatch: Any) -> None:
    """O `**i` que sobrescrevia o selo, e o que ele punha na tela dela.

    `_do_exame` montava ``{"selo": "RÁDIO" if grave else "AVISO", **i}`` e o
    ``**i`` vinha DEPOIS: quem chegava à tela era o selo do exame, que tem
    quatro estados e inclui o **CERTO**. Fotografado: o selo `CERTO` com
    "Economia de energia desligada" sob o cabeçalho laranja **Atenção**.
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [
        {"selo": "CERTO", "titulo": "Economia de energia desligada", "grave": False},
        {"selo": "AJUSTAR", "titulo": "Dois rádios em portas vizinhas", "grave": True},
    ])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert "CERTO" not in fora["aviso-selo"], (
        "uma boa notícia voltou a aparecer sob o cabeçalho 'Atenção'")
    assert fora["aviso-selo"] == ["AJUSTAR"], (
        f"o selo do exame não é mais o do produto: {fora['aviso-selo']!r}")
    assert fora["aviso-texto"] == ["Dois rádios em portas vizinhas"]


def test_a_conta_e_a_do_produto_e_conta_o_que_a_coluna_mostra(monkeypatch: Any) -> None:
    """`painel.texto_da_conta` sabe dizer "nenhum aviso"; o desenho não tem isso.

    E ela contava ERRADO: era o exame INTEIRO, incluindo os `certo` — a tela
    dizia "3 avisos" com duas boas notícias na conta.
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [
        {"selo": "CERTO", "titulo": "tudo bem", "grave": False}])
    assert aba.pacote(_ctx(VIVO_NAVEGACAO))["atencao-conta"] == "nenhum aviso"

    monkeypatch.setattr(painel, "texto_da_conta", lambda n: f"{n} de outro dono")
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": "a", "fonte": "x"}])
    assert aba.pacote(_ctx(VIVO_NAVEGACAO))["atencao-conta"] == "1 de outro dono", (
        "o pacote voltou a escrever a conta em vez de perguntar ao produto")


def test_a_linha_sem_aviso_nao_fica_com_travessao(monkeypatch: Any) -> None:
    """O acendedor da linha. Sem ele a coluna mostra seis linhas de `— —`.

    O piloto escreve `—` no lugar de um valor vazio, e o alvo `classe` sem
    `data-hef-quando` é booleano: a lista de `"1"` acende exatamente as que têm
    texto, e as outras ficam com `display:none`.
    """
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": "a", "fonte": "x"},
                    {"selo": "JOGO", "texto": "b", "fonte": "y"}])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["aviso-vivo"] == ["1", "1"], (
        f"o acendedor não acompanha a lista de avisos: {fora['aviso-vivo']!r}")
    assert len(fora["aviso-vivo"]) == len(fora["aviso-selo"])


def test_a_coluna_nao_estoura_o_que_a_pagina_publica(monkeypatch: Any) -> None:
    """Mais avisos que linhas: a lista corta, e a CONTA continua dizendo o total.

    Uma coluna que mostrasse 6 de 8 e escrevesse "6 avisos" esconderia dois sem
    dizer que os escondeu.
    """
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                    for i in range(aba.AVISOS_VIVOS + 2)])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert len(fora["aviso-selo"]) == aba.AVISOS_VIVOS
    assert fora["atencao-conta"] == painel.texto_da_conta(aba.AVISOS_VIVOS + 2)


def test_uma_fonte_que_quebra_nao_apaga_a_coluna(monkeypatch: Any) -> None:
    """O `except` largo do `_do_exame` já comeu meia coluna calado uma vez.

    A política é a de `painel.avisos_do_estado`: a que falhou vira um aviso com
    o selo `ERRO`. Silêncio é o pior dos dois desfechos — ele se lê como "não
    havia achado nenhum".
    """
    def explode() -> list[dict[str, Any]]:
        raise RuntimeError("o exame caiu")

    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", explode)
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert "ERRO" in fora["aviso-selo"], (
        "o exame quebrou e a coluna ficou vazia — o silêncio voltou")


# ---------------------------------------------------------------------------
# 3. A PÁGINA TEM ONDE ESCREVER — endereço que falta pinta em lugar nenhum
# ---------------------------------------------------------------------------
#: A ABA ESTÁ DECLARADA EM TRABALHO NA BANCADA? Enquanto estiver, o publicado
#: pode estar atrás do desenho de propósito — é o contrato do
#: `scripts/check_o_desenho_aprovado.py`, e a direção é `mockup/` → produto, por
#: decisão dela de 31/08. A régua abaixo então mede a BANCADA sempre e o
#: PUBLICADO só quando a divergência já foi fechada: ela **se rearma sozinha** no
#: dia em que a aba for publicada, em vez de virar um caso que alguém apaga.
def _em_trabalho() -> bool:
    arquivo = onde.BANCADA / "DIVERGENCIAS.md"
    if not arquivo.exists():
        return False
    corpo = arquivo.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    return "\n## 01-jogar.html" in f"\n{corpo}"


@pytest.mark.parametrize("publicado", [False, True])
def test_a_pagina_publica_os_enderecos_na_quantidade_certa(publicado: bool) -> None:
    """Um endereço a menos deixa uma posição acesa para sempre.

    A régua cobre a BANCADA e o PUBLICADO: o desenho pode andar na frente, mas
    nenhum dos dois pode ter meia fileira endereçada. O `querySelector` de um
    endereço que não existe não levanta — devolve `null`, e a pintura escreve
    zero.
    """
    if publicado and _em_trabalho():
        pytest.skip("01-jogar está declarada em trabalho no `mockup/DIVERGENCIAS.md`: "
                    "o produto recebe no `--publicar`, que é ato de quem coordena")
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    esperado = {
        "hef-posicao": len(aba01.INTERRUPTOR),
        "modo-aceso": len(aba01.MODOS),
        "mascara-cartao": len(monta.MASCARAS) * len(monta.CONECTADOS),
        "aviso-vivo": aba.AVISOS_VIVOS,
        "pendente-ha": 1,
    }
    for campo, quantos in esperado.items():
        achei = corpo.count(f'data-campo="{campo}" data-hef-alvo="classe"')
        assert achei == quantos, (
            f"{'publicado' if publicado else 'bancada'}: o endereço {campo!r} "
            f"aparece {achei} vezes e deviam ser {quantos}")


def test_todo_endereco_que_o_pacote_emite_existe_na_pagina() -> None:
    """A régua nos DOIS sentidos — sem ela, o pacote emite para o vazio.

    Foi assim que a `06-navegacao` publicou zero endereços em 01/09 sem ninguém
    ver, e assim que a Jogar pintava um valor de cinco: o pacote emitia
    `mascara` e a página tinha `identidade`.
    """
    corpo = onde.pagina("01-jogar.html", publicado=not _em_trabalho()).read_text(
        encoding="utf-8")
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    for campo in fora:
        if campo in {"cartoes", "cobertura", "sem_dono", "blocos"}:
            continue
        assert f'data-campo="{campo}"' in corpo, (
            f"o pacote emite {campo!r} e a página publicada não tem onde escrever")


def test_a_cena_da_coluna_atencao_continua_com_um_aviso() -> None:
    """As linhas novas são ENDEREÇO, e endereço não move pixel.

    A cena que ela aprovou tem um aviso. As outras cinco nascem sem a classe
    que as mostra, então a página aberta sozinha desenha exatamente o que ela
    viu — e é isso que separa "a aba ganhou vida" de "alguém mexeu no desenho".
    """
    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    assert corpo.count('class="aviso-item mostra"') == len(aba01.AVISOS)
    assert corpo.count('class="aviso-item"') == aba.AVISOS_VIVOS - len(aba01.AVISOS)


# ---------------------------------------------------------------------------
# 4. O FATO CADUCO — a folga de tempo que já tinha sido curada
# ---------------------------------------------------------------------------
def test_os_cinco_metodos_desta_aba_tem_a_folga_do_produto() -> None:
    """`ACHADO_DO_TIMEOUT` afirmava 250 ms; `ponte.TETOS` já dava 2,0 s.

    Quem lesse o texto antigo iria construir uma cura já construída. Esta régua
    tranca o fato dos dois lados: a tabela tem os cinco, e com o valor que o
    produto declara — se `mode_transition.MODE_IPC_TIMEOUT_S` mudar, ela avisa.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_IPC_TIMEOUT_S
    from pacotes import ponte

    for metodo in aba.METODOS:
        assert ponte.teto(metodo) == MODE_IPC_TIMEOUT_S, (
            f"{metodo} espera {ponte.teto(metodo)}s e o produto declara "
            f"{MODE_IPC_TIMEOUT_S}s para trocar de modo")
    assert "TETOS" in aba.ACHADO_DO_TIMEOUT and "2,0 s" in aba.ACHADO_DO_TIMEOUT, (
        f"o fato caduco voltou — o texto precisa nomear a tabela que já dá a "
        f"folga: {aba.ACHADO_DO_TIMEOUT!r}")
