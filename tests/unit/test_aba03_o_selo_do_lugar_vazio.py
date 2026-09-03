"""A régua da aba 03: o cabeçalho do lugar VAZIO tem de poder ser PROVADO.

O DEFEITO, medido em 03/09/2026 com a régua do mockup e os dois controles dela
na mesa (um no cabo, um por rádio)::

    03-gatilhos.html   62 campos   58 PRODUTO   4 MOCKUP    93%
        p3·chip-do-controle = 'P3 • Desconectado'
        p3·chip.plastico    = 'P3 • Desconectado'
        p4·chip-do-controle = 'P4 • Desconectado'
        p4·chip.plastico    = 'P4 • Desconectado'

Os quatro estavam sendo ESCRITOS pelo produto. O que faltava não era escrita —
era **prova**, e ela tem uma forma só nesta casa: o SELO da visita
(`data-hef-visto`), que o `escrever()` do piloto carimba no elemento em que
esteve. Sem selo, a régua do mockup só consegue dar por PRODUTO um campo cujo
valor MUDE; e o do lugar vazio não muda nunca — `P3 • Desconectado` é o mesmo
no desenho e no produto, porque os dois saem da MESMA função.

AS DUAS METADES DA CURA, e elas são de naturezas diferentes:

1. **O EMBRULHO VIRA CAMPO.** Ele saía por `blocos`, que pousa por seletor CSS
   e não carimba selo nenhum. Onde a página já marca a coluna
   `data-conectado="nao"`, emitir uma `colunas` não custa nada — e o campo é o
   único caminho que leva selo. O bloco fica para o lugar que a PÁGINA dá por
   conectado (o P2 com um controle só na mesa), onde emitir coluna custaria o
   `data-conectado="nao"` que segura o `pointer-events:none`.

2. **A COR SAI DE DENTRO DO CHIP.** Ela morava no `style` do `<span>`, isto é,
   DENTRO do `innerHTML` que o alvo `html` compara — e ali o `<span>` **nunca
   pode receber selo**: carimbá-lo poria `data-hef-visto="1"` dentro do HTML
   comparado, e a coluna repintaria a cada tique, para sempre (medido: 17
   tiques, 17 pinturas). Em 03/09/2026 o `--plastico` subiu para o EMBRULHO,
   com endereço (`a03_gatilhos.CAMPO_DO_PLASTICO`) e o alvo que o alcança —
   ele fica fora do HTML comparado, ganha selo, e a cor passa a vir do aparelho
   nos 28 modelos que ela mapeou. O `<span>` do chip ficou sem endereço nenhum:
   quem o reescreve é o pai.

O QUE ESTA RÉGUA MORDE:

* devolver o chip do lugar vazio para `blocos`  → `test_o_lugar_vazio_sai_por_campo`
* deixar de escrever o chip de ALGUM lugar sem
  aparelho (o P2 com um controle só)            → `test_nenhum_lugar_sem_aparelho_fica_sem_chip`
* pôr a cor de volta dentro do chip             → `test_a_cor_saiu_de_dentro_do_chip`
* o produto deixar a cor acesa num lugar vazio  → `test_o_lugar_vazio_apaga_a_cor`
* o pacote assinar a visita que não fez         → `test_o_pacote_nao_emite_o_selo`
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "03-gatilhos.html"

#: UM CONTROLE DE MENTIRA, com a forma que o daemon devolve. O MAC é da faixa
#: sintética da casa (`aa:bb:cc`): há dois portões de anonimato nesta árvore.
NO_CABO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "transport": "usb",
    "is_primary": True, "inputs": {"l2_raw": 0, "r2_raw": 0},
}
NO_RADIO = {
    "uniq": "aa:bb:cc:00:00:02", "player": 2, "transport": "bt",
    "is_primary": False, "inputs": {"l2_raw": 0, "r2_raw": 0},
}

#: A MESA DELA DE HOJE: um **White no cabo** e um **por rádio sem cor lida**.
MESA_DELA = [
    {"pref": "p1", "jogador": 1, "uniq": NO_CABO["uniq"], "nome": "White",
     "via": "USB", "cor": "white", "mascara": "DualSense", "alvo": True},
    {"pref": "p2", "jogador": 2, "uniq": NO_RADIO["uniq"], "nome": "Não sei",
     "via": "BT", "cor": "", "mascara": "DualSense", "alvo": False},
]

#: A MESA DE UM SÓ. É o caso em que o P2 fica sem dono e a PÁGINA continua
#: dando aquela coluna por conectada — o lugar que o `blocos` ainda cobre.
MESA_DE_UM = [MESA_DELA[0]]


@pytest.fixture(scope="module")
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return a03_gatilhos




def _pacote(a03, mesa, conectados):
    """O pacote inteiro para aquela mesa, com o perfil injetado pela porta."""
    from pacotes import Contexto, perfil

    guardado = perfil.ativo
    perfil.ativo = lambda _n: {  # type: ignore[assignment]
        "triggers": {"left": {"mode": "Rigid", "params": []},
                     "right": {"mode": "Rigid", "params": []}},
        "controllers": {}}
    try:
        return a03.pacote(Contexto(state={"active_profile": "régua"}, mesa=mesa,
                                   conectados=conectados, estados={}))
    finally:
        perfil.ativo = guardado  # type: ignore[assignment]


def _chip_de_bloco(a03, r, pref: str) -> str | None:
    """O chip que saiu por BLOCO naquele `pref`, ou `None` se não saiu."""
    return r["blocos"].get(a03.seletor_do_chip(pref))


# ---------------------------------------------------------------------------
# 1. O SELO — e ele só chega pelo caminho do CAMPO.
# ---------------------------------------------------------------------------

def test_o_lugar_vazio_sai_por_campo(a03):
    """O cabeçalho do P3 e do P4 sai em `colunas`, e NÃO em `blocos`.

    É a diferença entre escrever e PROVAR que escreveu. `hefesto_vivo.pintar`
    tem dois caminhos, e só um deles carimba o selo::

        blocos:  alvo.innerHTML = html          (nenhum selo)
        colunas: escrever(el, v) → el.dataset.hefVisto = '1'

    ARRANQUE a linha `vazia[CAMPO_DO_CHIP] = ...` do laço dos vazios em
    `pacote()` e esta régua reprova nomeando a coluna — o chip volta a sair só
    por bloco, e a régua do mockup volta a contar dois campos como desenho.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    vazios = sorted(a03._lugares_que_o_desenho_da_por_vazios())
    assert vazios, "a página não marca lugar vazio nenhum — a régua ficou cega"
    for pref in vazios:
        col = r["colunas"].get(pref) or {}
        assert a03.CAMPO_DO_CHIP in col, (
            f"o cabeçalho de {pref} não sai por `colunas`: {sorted(col)}. Só o "
            f"campo ganha o selo da visita, e sem selo a régua do mockup não "
            f"tem como separar 'o produto escreveu igual' de 'ninguém tocou'.")
        assert "Desconectado" in str(col[a03.CAMPO_DO_CHIP]), (
            f"{pref} recebeu {col[a03.CAMPO_DO_CHIP]!r} e não há controle nele")
        assert _chip_de_bloco(a03, r, pref) is None, (
            f"o cabeçalho de {pref} sai pelos DOIS caminhos. Duas escritas para "
            f"o mesmo elemento é o defeito de origem desta aba: elas divergem no "
            f"primeiro dia em que alguém mexer numa só.")


def test_nenhum_lugar_sem_aparelho_fica_sem_chip(a03):
    """Todo lugar sem aparelho recebe cabeçalho — por campo OU por bloco.

    COM UM CONTROLE SÓ, a página dá o P2 por CONECTADO: ele não está entre os
    `data-conectado="nao"` do arquivo, então emitir uma `colunas` para ele
    tiraria a coluna da conta `TODOS_OS_LUGARES - colunas` do piloto e levaria
    junto o `data-conectado="nao"` que segura o `pointer-events:none`. Lá o
    bloco continua sendo o caminho certo — e sem ele o cabeçalho do P2 ficaria
    dizendo `Starlight Blue` com ninguém ali.

    ARRANQUE a guarda `if pref not in colunas` (troque-a por `if False`) e o
    chip volta a sair duas vezes; troque-a por `if True` sem o campo e o P2 fica
    sem cabeçalho. Esta régua pega as duas metades.
    """
    r = _pacote(a03, MESA_DE_UM, [NO_CABO])
    ocupados = {str(m["pref"]) for m in MESA_DE_UM}
    for pref in sorted(a03._todos_os_lugares_da_pagina() - ocupados):
        por_campo = (r["colunas"].get(pref) or {}).get(a03.CAMPO_DO_CHIP)
        por_bloco = _chip_de_bloco(a03, r, pref)
        escritos = [x for x in (por_campo, por_bloco) if x is not None]
        assert len(escritos) == 1, (
            f"{pref} está sem aparelho e recebeu {len(escritos)} cabeçalho(s). "
            f"Zero deixa o nome de quem saiu na tela; dois são duas escritas "
            f"para o mesmo elemento.")
        assert "Desconectado" in str(escritos[0]), (
            f"{pref} recebeu {escritos[0]!r} e não há controle nele")


# ---------------------------------------------------------------------------
# 2. A COR — ela mora no EMBRULHO, que é o que o produto pode pintar.
# ---------------------------------------------------------------------------

def test_a_cor_saiu_de_dentro_do_chip(a03):
    """O `<span>` do chip não carrega cor nem endereço. Quem carrega é o pai.

    AS DUAS RÉGUAS PUXAVAM PARA LADOS OPOSTOS enquanto a cor morava no chip:

    * `check_a_cor_vem_do_aparelho.py` EXIGE que o `--plastico` esteja num
      elemento cujo alvo o alcance (`plastico` ou `html`) — e o do `<span>` era
      `texto`, que escreveria o hexadecimal como palavra na tela.
    * `regua_do_mockup` COBRA todo endereço que não vira PRODUTO — e um `<span>`
      dentro de um pai que se troca inteiro nunca recebe selo, porque carimbá-lo
      poria `data-hef-visto="1"` dentro do `innerHTML` comparado.

    Tirar a cor de dentro do chip resolve as duas de uma vez, e é a cura de
    03/09/2026. ARRANQUE-A de volta para o `<span>` e esta régua reprova.
    """
    com_cor = a03._cabeca_do_controle(1, "White", "USB", "#e4e0d8")
    assert 'style="--plastico:#e4e0d8"' in com_cor, (
        f"o cabeçalho COM cor não a veste: {com_cor!r}")
    chip = com_cor[com_cor.index('<span class="chip'):]
    assert "--plastico" not in chip, (
        f"a cor voltou para dentro do chip: {chip!r}. Ali o produto não pode "
        f"reescrevê-la sem repintar a coluna a cada tique.")
    assert "data-hef" not in chip and "data-campo" not in chip, (
        f"o `<span>` do chip ganhou endereço: {chip!r}. Ele é filho de um pai "
        f"que se troca inteiro — nunca vai receber selo, e a régua do mockup "
        f"vai cobrá-lo para sempre.")

    vazio = a03._cabeca_do_controle(3, "", "", "", conectado=False)
    assert "--plastico" not in vazio, (
        f"o cabeçalho do lugar vazio ganhou cor de plástico: {vazio!r}")
    assert f'data-campo="{a03.CAMPO_DO_PLASTICO}"' in vazio, (
        f"o cabeçalho do lugar vazio ficou SEM o endereço da cor: {vazio!r}. A "
        f"página é estática: sem ele, o dia em que um controle entrar no P3 a "
        f"cor não terá por onde chegar.")

    # E O CONECTADO SEM COR LIDA cai do mesmo lado do vazio: pelo rádio a cor
    # ainda não chega, e o cabeçalho sai sem `style` — a queda do `topo.html`
    # deixa a borda neutra em vez de vestir o plástico de outro controle.
    sem_leitura = a03._cabeca_do_controle(2, "", "BT", "")
    assert "--plastico" not in sem_leitura, (
        f"o cabeçalho do controle por rádio, sem cor lida, vestiu plástico: "
        f"{sem_leitura!r}")


def test_o_lugar_vazio_apaga_a_cor(a03):
    """O que o produto escreve num lugar vazio APAGA a borda de quem saiu.

    O `escrever()` do alvo `plastico` chama `removeProperty` no vazio e no
    travessão — é assim que a decisão dela vale nos dois sentidos: *"os demais 3
    e o 4 ficam lá com os espaços mas tudo com Desligado e Nenhum, fora a borda
    do P1 e P2."* Sem esta escrita, um controle que SAI do P1 deixaria a borda
    dele acesa num lugar sem aparelho.

    ARRANQUE a linha `vazia[CAMPO_DO_PLASTICO] = ""` do laço dos vazios e esta
    régua reprova nomeando a coluna.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    for pref in sorted(a03._lugares_que_o_desenho_da_por_vazios()):
        col = r["colunas"].get(pref) or {}
        assert col.get(a03.CAMPO_DO_PLASTICO) == "", (
            f"{pref} está vazio e a coluna não apaga a cor: "
            f"{col.get(a03.CAMPO_DO_PLASTICO)!r}")
        escrito = str(col[a03.CAMPO_DO_CHIP])
        assert "--plastico" not in escrito, (
            f"o que o produto escreve em {pref} traz cor de plástico: "
            f"{escrito!r}")


def test_o_pacote_nao_emite_o_selo(a03):
    """O selo é um fato do PILOTO. O pacote que o escrevesse assinaria a visita.

    Ele faria a conta fechar sem que ninguém tivesse pintado — que é a família
    exata do `77%` que esta casa publicou lendo código, e o oposto do que a
    régua do mockup existe para medir.
    """
    r = _pacote(a03, MESA_DELA, [NO_CABO, NO_RADIO])
    tudo = "".join(str(v) for col in r["colunas"].values() for v in col.values())
    tudo += "".join(str(v) for v in r["blocos"].values())
    assert "data-hef-visto" not in tudo, (
        "o pacote está emitindo o SELO do piloto. Quem escreve o selo declara "
        "que esteve no elemento; escrevê-lo aqui seria a aba assinando a visita "
        "que não fez — e a régua do mockup passaria a medir a si mesma.")
