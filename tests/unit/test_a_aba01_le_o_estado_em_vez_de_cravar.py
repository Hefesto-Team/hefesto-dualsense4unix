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


#: DOIS ENDEREÇOS FORJADOS, na faixa que o portão de anonimato reserva para
#: fixture (`aa:bb:cc`). O registro de máscaras é POR APARELHO, então uma mesa
#: sem `uniq` não sabe responder de quem é a máscara.
UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"


def _com_mesa(state: dict[str, Any], por_aparelho: dict[str, str] | None = None,
              quantos: int = 1) -> Contexto:
    """Um contexto com mesa VIVA — a máscara passou a ser de cada cartão.

    A mesa sai de `mesa_viva.mesa_do_estado`, que é o dono do valor por
    aparelho: ela lê `gamepad_emulation.por_aparelho` e cai na máscara da
    sessão para quem não escolheu. Montá-la à mão aqui seria escrever a regra
    de herança uma segunda vez, e a de cá envelheceria sozinha.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    conectados = [
        {"uniq": u, "connected": True, "player_slot": i, "transport": t}
        for i, (u, t) in enumerate(((UNIQ_A, "usb"), (UNIQ_B, "bluetooth"))[:quantos],
                                   start=1)
    ]
    cheio = {**state, "controllers": conectados}
    if por_aparelho is not None:
        emul = dict(cheio.get("gamepad_emulation") or {})
        emul["por_aparelho"] = por_aparelho
        cheio["gamepad_emulation"] = emul
    mesa = mesa_viva.mesa_do_estado(cheio, {})
    return Contexto(state=cheio, mesa=mesa, conectados=conectados, estados={})


def _mascaras_dos_cartoes(ctx: Contexto) -> list[str]:
    """O que cada cartão recebeu, na ordem da mesa."""
    return [c["mascara-cartao"] for c in aba.pacote(ctx)["cartoes"].values()]


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
    """Quem não escolheu segue a sessão — e é o cartão que recebe, não a página.

    O chip **Xbox 360** aceso no cartão do P2 com o daemon em `dualsense` era o
    desenho falando pelo produto. Sem `por_aparelho` o valor é o da sessão, que
    é a herança do `external_mask` e o comportamento anterior ao campo existir.
    """
    assert _mascaras_dos_cartoes(_com_mesa(VIVO_NAVEGACAO)) == ["DualSense"]
    assert _mascaras_dos_cartoes(_com_mesa(VIVO_GAMEPAD_XBOX)) == ["Xbox 360"]


def test_dois_controles_duas_mascaras() -> None:
    """A DECISÃO DELA, 03/09/2026: *"É uma máscara por controle."*

    ESTE É O DEFEITO QUE A CURA MATOU, e ele era de PINTURA, não de leitura:
    `mesa_viva` já trazia a máscara de cada aparelho, mas o pacote emitia
    `mascara-cartao` como valor DE PÁGINA — e o piloto escreve valor de página
    em todo elemento com aquele `data-campo`. A máscara da SESSÃO ia para os
    três chips dos quatro cartões, e dois controles com escolhas diferentes
    acendiam o MESMO chip.

    A MORDIDA: devolva `"mascara-cartao"` a `DA_PAGINA` e emita-o uma vez em
    `_estado_da_tela` — este teste reprova com os dois cartões em `DualSense`,
    que é exatamente o que a tela dela mostrava.
    """
    ctx = _com_mesa(VIVO_GAMEPAD_XBOX,
                    por_aparelho={UNIQ_A: "dualsense", UNIQ_B: "xbox"},
                    quantos=2)
    assert _mascaras_dos_cartoes(ctx) == ["DualSense", "Xbox 360"], (
        "os dois cartões receberam a mesma máscara — o valor voltou a ser da "
        "página, e a escolha por aparelho parou de chegar à tela")
    assert "mascara-cartao" not in aba.pacote(ctx), (
        "`mascara-cartao` voltou ao nível de página: o piloto o escreveria em "
        "TODOS os chips de TODOS os cartões, que é o defeito curado em 03/09")


def test_nintendo_pro_nunca_acende() -> None:
    """Ele não é máscara do produto: o daemon recusa tudo o que não for os dois.

    O chip fica na tela por ordem dela; apagado é a verdade sobre ele. Se algum
    dia esta linha reprovar, é porque alguém traduziu uma máscara que o
    `ipc_handlers` recusa.
    """
    for state in (VIVO_NAVEGACAO, VIVO_GAMEPAD_XBOX, VIVO_NATIVO):
        assert "Nintendo Pro" not in _mascaras_dos_cartoes(_com_mesa(state))
    # E NEM QUANDO O REGISTRO PEDE: um valor que o produto não sabe montar não
    # acende chip nenhum. É a diferença entre "a mesa não falou" (herda a
    # sessão) e "a mesa falou um nome que a tela desenha e o daemon recusa".
    ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: "Nintendo Pro"})
    assert _mascaras_dos_cartoes(ctx) == [""], (
        "um rótulo que o produto não sabe montar acendeu um chip")


def test_o_daemon_calado_nao_acende_nada() -> None:
    """A armadilha desta aba: `mode_of_state({})` devolve **desktop**.

    Ele só devolve `None` para um NÃO-dicionário. Sem a guarda, um tique sem
    resposta acenderia **Ligado** e o chip **Navegação** sobre um estado que
    ninguém leu — a tela afirmando com o Hefesto fora do ar.
    """
    fora = aba.pacote(_ctx({}))
    assert fora["hef-posicao"] == ""
    assert fora["modo-aceso"] == ""
    # E NENHUM CARTÃO, logo nenhuma máscara: sem estado não há mesa, e o valor
    # que sobraria seria o do desenho. Ver `test_dois_controles_duas_mascaras`.
    assert fora["cartoes"] == {}


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


def test_a_mascara_do_cartao_tem_a_MESA_por_dona() -> None:  # noqa: N802
    """Quem responde pela máscara de um aparelho é `mesa_viva`, e não o pacote.

    A REGRA DE HERANÇA MORA NO REGISTRO (`external_mask.mascara_efetiva`) e
    chega à tela por `mesa_viva.mesa_do_estado`, que lê `por_aparelho` e cai na
    sessão para quem não escolheu. Se o pacote relesse o `state` por conta
    própria, seriam DUAS verdades sobre o mesmo fato — e a de cá envelheceria no
    dia em que a herança mudasse.

    A RÉGUA TROCA A MESA em vez de comparar textos: um valor digitado no pacote
    passaria em todos os outros testes deste arquivo.
    """
    ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: "dualsense"})
    assert _mascaras_dos_cartoes(ctx) == ["DualSense"], (
        "o cartão ignorou o que a mesa disse — o pacote voltou a ler o estado")

    # E COM A MESA MUDA, o caminho de trás: um contexto cuja mesa não tem a
    # chave `mascara` (a de uma régua, ou a de um daemon anterior ao
    # `por_aparelho`) cai na máscara da SESSÃO, que é o comportamento de antes
    # deste campo existir. Meia cura que muda comportamento é pior que nenhuma.
    sem_mascara = Contexto(
        state=ctx.state,
        mesa=[{k: v for k, v in m.items() if k != "mascara"} for m in ctx.mesa],
        conectados=ctx.conectados,
        estados={},
    )
    assert _mascaras_dos_cartoes(sem_mascara) == ["Xbox 360"], (
        "a mesa muda deixou de herdar a máscara da sessão")


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


#: O PRODUTO ESTÁ ATRÁS **SÓ POR ENDEREÇO**? É a outra espera, e ela não passa
#: pelo `DIVERGENCIAS.md` — declarar ali uma página que não mudou um pixel a
#: torna uma declaração ÓRFÃ, e o portão reprova.
#:
#: Um `data-campo`/`data-gesto` novo num elemento que já existia não muda nada
#: do que ela vê, então **não é decisão dela**: quem o leva ao produto é
#: `scripts/check_o_desenho_aprovado.py --publicar-enderecos`, ato de quem
#: coordena. Enquanto isso não roda, a bancada anda na frente por endereço.
#:
#: A PERGUNTA É FEITA AO DONO, e é o que separa esta espera de um caso apagado:
#: `so_mudou_endereco` é a função do próprio portão, e ela apaga os trinta
#: atributos de endereço antes de comparar. Três desfechos, e só um dispensa:
#:
#:   páginas IDÊNTICAS ......... não dispensa (o publicado é medido, e passa)
#:   diferem num PIXEL ......... não dispensa (a régua reprova, alto)
#:   diferem só em ENDEREÇO .... dispensa, dizendo o comando que fecha
#:
#: Ela **se rearma sozinha** no dia da publicação, em vez de virar um `skip`
#: que ninguém tira.
def _atras_so_por_endereco() -> bool:
    import importlib.util

    alvo = RAIZ / "scripts" / "check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("_desenho_aprovado", alvo)
    if spec is None or spec.loader is None:  # pragma: no cover - defesa
        return False
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    nome = "01-jogar.html"
    bancada, produto = onde.BANCADA / nome, onde.PUBLICADO / nome
    if not produto.exists() or bancada.read_bytes() == produto.read_bytes():
        return False
    return bool(modulo.so_mudou_endereco(nome))


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
    if publicado and _atras_so_por_endereco():
        pytest.skip("o produto está atrás da bancada SÓ POR ENDEREÇO — nenhum "
                    "pixel mudou. Fecha com: scripts/check_o_desenho_aprovado.py "
                    "--publicar-enderecos 01")
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    esperado = {
        "hef-posicao": len(aba01.INTERRUPTOR),
        "modo-aceso": len(aba01.MODOS),
        # OS QUATRO LUGARES, e não só os conectados — decisão dela de 03/09:
        # *"É uma máscara por controle. (…) Se isso não ocorre com os 4
        # controles em cada aba, então temos que construir isso e garantir
        # isso."* No produto a página é ESTÁTICA: o cartão do P3 REABRE quando
        # um terceiro controle chega, e sem endereço os chips dele ficariam
        # cegos à pintura para sempre.
        "mascara-cartao": len(monta.MASCARAS) * len(aba01.MESA),
        "aviso-vivo": aba.AVISOS_VIVOS,
        "pendente-ha": 1,
    }
    for campo, quantos in esperado.items():
        achei = corpo.count(f'data-campo="{campo}" data-hef-alvo="classe"')
        assert achei == quantos, (
            f"{'publicado' if publicado else 'bancada'}: o endereço {campo!r} "
            f"aparece {achei} vezes e deviam ser {quantos}")
    # E O CLIQUE ALCANÇA OS QUATRO — a outra metade, e ela não sai da mesma
    # contagem: `data-campo` é por onde a verdade chega, `data-gesto` é por onde
    # o dedo dela sai. Até 03/09 os chips do P3 e do P4 não tinham nenhum dos
    # dois, e o ramo do gesto que responde *"Não há controle no lugar P3"* era
    # código inalcançável.
    cliques = corpo.count('data-gesto="mascara"')
    assert cliques == len(monta.MASCARAS) * len(aba01.MESA), (
        f"{'publicado' if publicado else 'bancada'}: o clique da máscara "
        f"alcança {cliques} chips e a mesa tem {len(aba01.MESA)} lugares")


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
