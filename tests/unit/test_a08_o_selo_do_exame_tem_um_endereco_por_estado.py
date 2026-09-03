#!/usr/bin/env python3
"""A COR DA PÍLULA DO CHECK-UP É DO ACHADO, e não da posição no desenho.

**03/09/2026.** A régua do mockup acusava três ENDEREÇOS MORTOS na aba
Conexões — *"o pacote declara 'certo' e a tela continua em ''"* —, e por trás
deles havia um defeito que ninguém via na conta: com os **três achados `certo`**
que o exame devolve na mesa dela, a **segunda linha** mostrava a palavra
**CERTO** dentro da pílula **LARANJA**. A palavra vinha do produto; a cor, do
mockup, cravada por posição.

AS DUAS METADES DA CURA, e nenhuma vale sozinha:

    (a) O DESENHO TEM UM ENDEREÇO POR ESTADO   três `<i class="est">` invisíveis
        (`aba08.exame`)                        antes da pílula, e a folha de
                                               estilo lê a cor do IRMÃO (`~`)

    (b) O PACOTE FALA A LÍNGUA DO ELEMENTO     `_selos_por_estado`: um nó que
        (`a08_conexoes.pacote`)                pergunta *"é `problema`?"* só
                                               recebe `problema` ou o vazio

Sem (a), o pacote emite num endereço que não existe e o produto pinta zero.
Sem (b), o pacote responde a pergunta errada: emitir `certo` num elemento que
só sabe dizer `problema` é o que fazia a régua chamar de endereço morto o
que a tela mostrava CERTO.

**POR QUE UM ELEMENTO NÃO BASTAVA:** o alvo `classe` do
`hefesto_vivo.BOOTSTRAP` acende UMA classe por elemento, e o vocabulário de
endereço é UM `data-campo` por nó. Quatro estados não cabem num interruptor só.

O TERCEIRO CASO, e ele é da RÉGUA: o alvo `html` era comparado COM as tags de
um lado e SEM do outro. `p1·teto-explica` e `p2·teto-explica` saíam como
endereço morto com o produto pintando os dois a cada tique. É o terceiro alvo
da decisão 15 dela — *"a régua aprende os alvos que faltam (`largura`, `valor`,
`html`)"* —, e ele tinha ficado de fora.

A MORDIDA, medida:

* devolva o `"selo-estado": [i["estado"] for i in itens]` do pacote →
  `test_o_pacote_so_responde_a_pergunta_do_elemento` e
  `test_o_estado_cru_num_elemento_de_um_estado_so_e_endereco_morto` reprovam;
* apague o ramo `campo.alvo == "html"` da `regua_do_mockup` →
  `test_a_regua_le_o_html_declarado_como_a_tela_o_mostra` reprova;
* tire um `<i class="est">` do `aba08.exame` e regenere →
  `test_o_desenho_tem_um_interruptor_por_estado` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"


def _pacote():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _regua():  # type: ignore[no-untyped-def]
    from hefesto_dualsense4unix.interface import regua_do_mockup

    return regua_do_mockup


#: Os quatro estados do `exame_da_mesa.Item`, como o dono os nomeia.
def _estados() -> list[str]:
    from hefesto_dualsense4unix.gui.aba_conexoes import SELO_DO_ESTADO

    return list(SELO_DO_ESTADO)


# ---------------------------------------------------------------------------
# (b) O PACOTE FALA A LÍNGUA DO ELEMENTO
# ---------------------------------------------------------------------------
def test_o_pacote_so_responde_a_pergunta_do_elemento() -> None:
    """Cada lista traz o SEU estado ou o vazio — nunca o de outro endereço."""
    p = _pacote()
    itens = [{"estado": e} for e in _estados()]
    listas = p._selos_por_estado(itens)

    assert set(listas) == set(p.ENDERECO_DO_ESTADO.values()), (
        "faltou (ou sobrou) um endereço de estado no que o pacote emite")

    for estado, endereco in p.ENDERECO_DO_ESTADO.items():
        for i, valor in enumerate(listas[endereco]):
            esperado = estado if itens[i]["estado"] == estado else ""
            assert valor == esperado, (
                f"`{endereco}` pergunta se o estado é `{estado}` e recebeu "
                f"{valor!r} para a linha {i}, cujo estado é "
                f"{itens[i]['estado']!r}. Um elemento pergunta UMA coisa; "
                f"responder com o token de outra pergunta é o que fazia a "
                f"régua acusar endereço morto sobre a tela certa.")


def _ctx():  # type: ignore[no-untyped-def]
    """Uma mesa de dois — o bastante para `pacote()` correr inteiro."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # A FAIXA SINTÉTICA DA CASA — há dois portões de anonimato nesta árvore.
    p1, p2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
    mesa = [
        {"pref": "p1", "uniq": p1, "jogador": 1, "cor": "white",
         "nome": "White", "via": "USB", "transporte": "usb", "mascara": "DualSense"},
        {"pref": "p2", "uniq": p2, "jogador": 2, "cor": "galactic-purple",
         "nome": "Galactic Purple", "via": "BT", "transporte": "bt",
         "mascara": "DualSense"},
    ]
    conectados = [
        {"uniq": p1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": p2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=mesa,
                    conectados=conectados, estados={})


def test_o_pacote_liga_os_quatro_enderecos() -> None:
    """A METADE QUE FALTAVA NESTE ARQUIVO, e ela é a que morde.

    MEDIDO EM 03/09/2026, arrancando a cura: com o
    `"selo-estado": [i["estado"] for i in itens]` de volta no `pacote()`, a
    régua do mockup voltou a acusar os três endereços mortos — e **os testes
    deste arquivo continuaram os nove verdes**, porque todos chamavam
    `_selos_por_estado` DIRETO. Um teste que prova a peça e não a ligação dá
    verde sobre um fio solto; é o defeito de régua que esta casa mais paga.
    """
    p = _pacote()
    saiu = p.pacote(_ctx())
    for endereco in p.ENDERECO_DO_ESTADO.values():
        assert endereco in saiu, (
            f"o `pacote()` não emite `{endereco}` — o desenho tem o endereço e "
            f"ninguém escreve nele")
    estados = set(_estados())
    for estado, endereco in p.ENDERECO_DO_ESTADO.items():
        for valor in saiu[endereco]:
            assert valor in ("", estado), (
                f"`{endereco}` pergunta se o estado é `{estado}` e o "
                f"`pacote()` emitiu {valor!r}. Todo token de "
                f"{sorted(estados - {estado})} é resposta de outra pergunta, e "
                f"é o que fazia a régua acusar endereço morto.")


def test_um_achado_certo_nao_acende_o_vermelho_de_problema() -> None:
    """Os três `certo` da mesa dela deixam a pílula do `problema` APAGADA."""
    p = _pacote()
    listas = p._selos_por_estado([{"estado": "certo"}] * 3)
    assert listas["selo-estado"] == ["", "", ""], (
        "a pílula do `problema` recebeu um token que não é o dela")
    assert listas["selo-certo"] == ["certo"] * 3, (
        "o interruptor do `certo` não acendeu com três achados `certo`")


# ---------------------------------------------------------------------------
# A RÉGUA — a prova de que (b) muda o VEREDITO, e não só o texto emitido
# ---------------------------------------------------------------------------
def _pilula(quando: str, classe: str = "on", aceso: bool = False):  # type: ignore[no-untyped-def]
    r = _regua()
    return r._Campo(chave="selo-x", dono="", alvo="classe",
                    valor=(quando if aceso else ""), quando=quando)


def test_o_estado_cru_num_elemento_de_um_estado_so_e_endereco_morto() -> None:
    """O veredito com o token errado, e o veredito com o certo. Lado a lado."""
    r = _regua()
    campo = _pilula("problema")

    cru = r._classificar([campo], [""], {("", "selo-x"): ["certo"]}, [True])
    assert cru[0].classe == r.MOCKUP, (
        "emitir `certo` num elemento que só sabe dizer `problema` TEM de ser "
        "acusado — é a régua fazendo o trabalho dela")
    assert "ENDEREÇO MORTO" in cru[0].nota

    curado = r._classificar([campo], [""], {("", "selo-x"): [""]}, [True])
    assert curado[0].classe == r.PRODUTO, (
        "com o vazio — o `não` desta pergunta — o campo é do produto: o piloto "
        "esteve nele e a tela mostra exatamente o que ele escreveu")


def test_o_interruptor_aceso_e_produto() -> None:
    """E o `sim` também: o elemento do estado que casa acende, e isso é produto."""
    r = _regua()
    campo = _pilula("certo")
    fora = r._classificar([campo], ["certo"], {("", "selo-x"): ["certo"]}, [True])
    assert fora[0].classe == r.PRODUTO


# ---------------------------------------------------------------------------
# A RÉGUA APRENDE O `html` — o terceiro alvo da decisão 15 dela
# ---------------------------------------------------------------------------
def test_a_regua_le_o_html_declarado_como_a_tela_o_mostra() -> None:
    """Uma declaração com `<b>` chega à comparação SEM as tags, como o DOM."""
    r = _regua()
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html",
                     valor="hoje segue o global")
    assert r._declarado_neste_elemento(campo, "hoje <b>segue o global</b>") == (
        "hoje segue o global"), (
        "a régua lê o alvo `html` pelo TEXTO (ver `_campo` e o `LER_CAMPOS` do "
        "piloto). Comparar a declaração COM as tags contra a tela SEM elas "
        "acusa endereço morto sobre a pintura que acertou.")


def test_o_teto_da_vibracao_nao_e_endereco_morto_quando_o_produto_o_pinta() -> None:
    """O caso medido em 03/09: o produto pinta o `?` e a régua o acusava."""
    r = _regua()
    texto = ("O teto da vibração deste controle. O global manda e o do controle "
             "sobrepõe: hoje este controle segue o global.")
    marcado = ("O teto da vibração <b>deste controle</b>. O global manda e o do "
               "controle sobrepõe: hoje este controle <b>segue o global</b>.")
    campo = r._Campo(chave="teto-explica", dono="p1", alvo="html", valor=texto)
    fora = r._classificar([campo], [texto], {("p1", "teto-explica"): marcado},
                          [True])
    assert fora[0].classe == r.PRODUTO, (
        f"o `?` do teto voltou a ser acusado: {fora[0].nota}")


def test_o_html_que_o_produto_nao_pintou_continua_acusado() -> None:
    """A cura do `html` NÃO pode cegar a régua: texto diferente segue acusado."""
    r = _regua()
    campo = r._Campo(chave="achado-explica", dono="", alvo="html",
                     valor="o desenho")
    fora = r._classificar([campo], ["o desenho"],
                          {("", "achado-explica"): "<b>o produto</b>"}, [True])
    assert fora[0].classe == r.MOCKUP, (
        "um endereço em que o produto declara UMA coisa e a tela mostra OUTRA "
        "continua sendo endereço morto — tirar as tags é normalizar a forma, "
        "nunca perdoar a diferença")


# ---------------------------------------------------------------------------
# (a) O DESENHO — e ele é o que alcança a tela dela
# ---------------------------------------------------------------------------
def test_o_desenho_tem_um_interruptor_por_estado() -> None:
    """Toda linha do exame sabe mostrar os QUATRO estados, e um só de cada vez."""
    p = _pacote()
    html = BANCADA.read_text(encoding="utf-8")
    linhas = re.findall(r'<div class="exame" data-campo="exame">.*?</div>',
                        html, re.S)
    assert linhas, "a bancada da 08 não tem uma linha de exame"

    for i, linha in enumerate(linhas):
        for estado, endereco in p.ENDERECO_DO_ESTADO.items():
            marca = f'data-campo="{endereco}"'
            assert marca in linha, (
                f"a linha {i} do exame não tem onde mostrar o estado "
                f"`{estado}`: falta `{marca}`")
            tag = re.search(rf"<[a-z]+[^>]*{re.escape(marca)}[^>]*>", linha)
            assert tag and f'data-hef-quando="{estado}"' in tag.group(0), (
                f"o endereço `{endereco}` da linha {i} não pergunta pelo "
                f"estado `{estado}`")
            assert tag and 'data-hef-alvo="classe"' in tag.group(0), (
                f"o endereço `{endereco}` da linha {i} não usa o alvo `classe`")
        # UM ACESO POR LINHA, no máximo: o desenho mostra UM estado.
        acesos = len(re.findall(r'<i class="est [a-z-]+ on"', linha))
        assert acesos <= 1, (
            f"a linha {i} do exame nasce com {acesos} interruptores acesos")


def test_a_folha_de_estilo_le_a_cor_do_irmao() -> None:
    """As regras que fazem o interruptor invisível pintar a pílula ao lado."""
    html = BANCADA.read_text(encoding="utf-8")
    for regra in (".exame .est{display:none}",
                  ".exame .est-ok.on ~ .selo{",
                  ".exame .est-warn.on ~ .selo{",
                  ".exame .est-info.on ~ .selo{",
                  ".exame .est.on ~ .selo.grave{"):
        assert regra in html, (
            f"sumiu do desenho a regra `{regra}` — sem ela o interruptor acende "
            f"e a pílula não muda de cor, que é endereço sem efeito")
