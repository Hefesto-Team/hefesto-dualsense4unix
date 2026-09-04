#!/usr/bin/env python3
"""A LINHA FECHADA DA ABA 08 SEGUE O APARELHO — e a confissão segue a mesa dela.

**03/09/2026.** Três coisas desta aba decidiam o que mostrar pela POSIÇÃO NO
DESENHO, e não pelo que o daemon disse. As três foram medidas na mesa dela no
mesmo dia, com **um** controle na mesa, no cabo, com a ponte de microfone
DESLIGADA no `maquina.json`:

===========================  ==================================  ==============
o que a tela dizia           o que a máquina dizia               quem mandava
===========================  ==================================  ==============
"Microfone **Ligado**"       `microfone` não declarado           o mockup
"pelo cabo · Placa…" no P1   certo por coincidência: o P2 do     o mockup
e "pelo rádio · Pela         desenho dizia rádio, e a mesa
ponte" no P2                 dela não tem P2
"A luz não acende" ACESO     o lugar do P2 está vazio; o do      o mockup
no segundo lugar e apagado   P1 está no CABO, onde o botão
no primeiro                  recusa
"…não consegui conferir:     a bancada dela tem **UMA**          o mockup
**três coisas**"             lacuna (`especie`)
===========================  ==================================  ==============

AS TRÊS CURAS TÊM A MESMA FORMA, e é a desta casa: o valor ganha ENDEREÇO no
gerador e DONO no pacote. Nenhuma palavra nova foi escrita — `caminho_do_mic`
e a tabela do "por extenso" mudaram-se para o pacote, que agora é o dono único
chamado pelos dois lados (o gerador com a mesa da bancada, o pacote a cada
tique com o aparelho vivo), e a confissão passa a vir de
`mapa_da_mesa.confissao_do_desenho`, que já era o dono das frases.

**AS DUAS METADES SE PRECISAM** (a lição do `IDENTIDADE-VEM-DE-CIMA-01`): um
`data-campo` sem ninguém escrevendo nele troca um congelado por um vazio, e um
pacote que emite para um endereço que não existe escreve zero e some.

A MORDIDA — medida, e cada uma reprova SÓ o seu:

* comente `"luz-trava"` do `pacote()`  →  `test_a_trava_da_luz_segue_o_transporte`
  e `test_o_pacote_emite_o_que_a_bancada_enderecou` reprovam (2);
* tire o `data-campo="luz-trava"` do `aba08.py` e regenere  →
  `test_os_enderecos_novos_existem_na_bancada` reprova (1);
* comente `"mic-caminho"`  →  `test_o_caminho_do_mic_segue_o_transporte` e
  `test_o_pacote_emite_o_que_a_bancada_enderecou` reprovam (2);
* devolva o `caminho_do_mic` literal ao gerador  →
  `test_o_gerador_e_o_pacote_dizem_a_mesma_frase` reprova (1);
* faça `_confissao_do_mapa` devolver a conta da CENA em vez da bancada  →
  `test_a_confissao_conta_as_lacunas_da_bancada` reprova (1).
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"


def _pacote() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def _ctx() -> Any:
    """Uma mesa de dois: o primeiro no CABO, o segundo no RÁDIO.

    Os dois transportes na mesma prova é o que impede a régua de passar por
    acaso: um valor congelado acerta metade dos casos, e uma prova de um
    controle só não distingue "seguiu o aparelho" de "acertou por sorte".
    """
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


def _por_transporte(pac: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """As colunas indexadas pelo transporte — `{"USB": {...}, "BT": {...}}`."""
    return {str(c.get("via") or ""): c for c in pac["colunas"].values()}


# ---------------------------------------------------------------------------
# (a) A BANCADA — os endereços que a cura precisa existem no que vai renderizar
# ---------------------------------------------------------------------------
def test_os_enderecos_novos_existem_na_bancada() -> None:
    """Os cinco endereços desta leva, no arquivo que o produto vai renderizar.

    O ALVO ENTRA NA BUSCA, e não só o `data-campo`: o `luz-trava` sem
    `data-hef-alvo="classe"` viraria TEXTO — o botão passaria a se chamar
    "cabo" em vez de acender ou apagar. Endereço certo com alvo errado é um
    defeito que a tela mostra e a contagem de campos não vê.
    """
    html = BANCADA.read_text(encoding="utf-8")
    pac = _pacote()
    esperados = (
        # POR CONTROLE
        'data-campo="mic-existe"',
        'data-campo="mic-caminho" data-hef-alvo="html"',
        # A TRAVA MUDOU DE NÓ EM 04/09/2026, e não de dono: ela saiu do
        # `<button>` para um `<i class="ltrava">` irmão, porque o vocabulário é
        # UM `data-campo` por nó e o botão precisava do dele para a DICA. A
        # classe deixou de ser nomeada (`apagado`) e passou a ser o `on` padrão,
        # que é o que a folha lê pelo `~` — ver `.gc-corpo .ltrava.on ~ .btn`.
        f'data-campo="luz-trava" data-hef-alvo="classe" '
        f'data-hef-quando="{pac.LUZ_TRAVADA}"',
        # E A DICA DO BOTÃO — a metade que era do desenho e mentia quando o
        # controle trocava de transporte.
        'data-campo="luz-dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title"',
        # A CONFISSÃO DO DESENHO
        'data-campo="confissao-nada" data-hef-alvo="classe" '
        'data-hef-classe="sumido" data-hef-quando="sim"',
        'data-campo="confissao-dica" data-hef-alvo="atributo" '
        'data-hef-atributo="title"',
        'data-campo="confissao-conta"',
    )
    for endereco in esperados:
        assert endereco in html, (
            f"o endereço `{endereco}` não está na bancada da 08 — sem ele o "
            f"produto não tem onde escrever, e a tela volta ao desenho")


def test_o_resumo_do_mic_e_o_select_dividem_o_mesmo_endereco() -> None:
    """`mic-existe` está no `<b>` da linha fechada E no `<select>` do corpo.

    UM VALOR, DOIS TRAJES: o piloto distribui por `data-campo` e cada elemento
    o veste como sabe (`texto` no `<b>`, `valor` no `<select>`). Dois endereços
    para o mesmo fato é como duas grafias começam — e foi assim que a linha
    fechada ficou dizendo "Ligado" enquanto o campo do corpo dizia a verdade.
    """
    html = BANCADA.read_text(encoding="utf-8")
    # Um bloco por controle CONECTADO — o lugar vazio não desenha resumo.
    blocos = re.findall(r'<div class="gc-item gc-p\d"[^>]*>.*?(?=<div class="gc-item)',
                        html, flags=re.S)
    assert blocos, "não achei uma linha de controle conectado na bancada da 08"
    endereco = 'data-campo="mic-existe"'
    for bloco in blocos:
        assert bloco.count(endereco) == 2, (
            "a linha fechada e o `<select>` do corpo têm de dividir o mesmo "
            f"`mic-existe` — contei {bloco.count(endereco)}")


def test_todo_botao_da_luz_tem_a_trava() -> None:
    """NENHUM botão "A luz não acende" fica sem endereço de trava.

    A régua compara CONJUNTOS, e não uma contagem: no dia em que a mesa da cena
    ganhar um terceiro controle conectado, um botão a mais sem `data-campo`
    passaria por um `== 2` sem que ninguém visse.
    """
    html = BANCADA.read_text(encoding="utf-8")
    botoes = re.findall(r'<button[^>]*data-gesto="luz-nao-acende"[^>]*>', html)
    # A TRAVA É O IRMÃO ANTERIOR desde 04/09/2026 — ver o teste acima. O `~` do
    # CSS só alcança irmãos POSTERIORES, então o `<i>` colado antes do botão é a
    # única forma que faz o apagado acender; um `<i>` solto noutro canto passaria
    # por um `in html` e nunca pintaria nada.
    com_trava = re.findall(
        r'<i class="ltrava[^"]*" data-campo="luz-trava"[^>]*></i><button[^>]*'
        r'data-gesto="luz-nao-acende"', html)
    assert botoes and len(botoes) == len(com_trava), (
        f"a bancada da 08 tem {len(botoes)} botões da luz e {len(com_trava)} "
        f"com o interruptor da trava colado antes deles")


# ---------------------------------------------------------------------------
# (b) O PACOTE ESCREVE — a metade que impede a maquiagem
# ---------------------------------------------------------------------------
def test_o_pacote_emite_o_que_a_bancada_enderecou() -> None:
    """Todo `data-campo` POR CONTROLE da bancada tem quem o escreva.

    ELA PERGUNTA AOS DOIS LADOS: lê os endereços do arquivo e as chaves do
    `pacote()`. Uma lista digitada aqui envelheceria no dia em que a aba
    ganhasse um campo — e a régua reprovaria justamente quem o acrescentou.

    O QUE FICA DE FORA são os endereços que o piloto pinta por OUTRO caminho:
    `desenho` e `plastico` valem por controle e já têm dono; os de topo
    (`selo`, `achado`, a fita, o rodapé) não são de controle nenhum. Por isso a
    régua olha só o que está DENTRO de um `[data-controle]` e cruza com as
    chaves das `colunas`, que é o dicionário que o piloto distribui ali.
    """
    html = BANCADA.read_text(encoding="utf-8")
    linhas = re.findall(
        r'<div class="gc-item gc-p\d"(?! [^>]*\bfora\b)[^>]*>.*?(?=<div class="gc-item)',
        html, flags=re.S)
    assert linhas, "não achei uma linha de controle conectado na bancada da 08"
    na_tela = {c for bloco in linhas
               for c in re.findall(r'data-campo="([^"]+)"', bloco)}
    pac = _pacote().pacote(_ctx())
    emitidos = {k for coluna in pac["colunas"].values() for k in coluna}
    # OS CAMPOS DE MÁQUINA CONTAM — 04/09/2026, e é o piloto quem manda: o passo
    # 1 da pintura faz `achar(document, k)` para as chaves de topo, sem recorte
    # por `[data-controle]` (`hefesto_vivo.py:612`). Um valor que é UM por
    # máquina e mora dentro da linha do controle — o escopo do botão físico do
    # microfone, decisão D-12 dela — é pintado ali do mesmo jeito, e nas duas
    # linhas com o mesmo valor, que é a verdade dele.
    #
    # A RÉGUA NÃO AFROUXA: ela continua reprovando o endereço que NINGUÉM
    # escreve, que é o defeito que ela existe para pegar. O que ela deixa de
    # exigir é que todo campo da linha seja POR CONTROLE — e essa exigência era
    # sobre a arquitetura do pacote, não sobre a tela.
    emitidos |= {k for k, v in pac.items()
                 if not isinstance(v, (dict, list))}
    sem_dono = na_tela - emitidos
    assert not sem_dono, (
        f"a linha do controle na bancada da 08 tem endereço sem ninguém que o "
        f"escreva: {sorted(sem_dono)} — endereço mudo é congelado com outro nome")


def test_a_trava_da_luz_segue_o_transporte() -> None:
    """No cabo o botão apaga; no rádio ele acende. E a palavra é a do produto.

    O VALOR NÃO É DIGITADO AQUI: ele é lido de `LUZ_TRAVADA`/`LUZ_LIVRE`, que
    são as constantes que o gerador escreve no `data-hef-quando`. Digitar
    `"cabo"` na régua faria dela a terceira grafia do mesmo par.
    """
    pac = _pacote()
    colunas = _por_transporte(pac.pacote(_ctx()))
    assert colunas["USB"]["luz-trava"] == pac.LUZ_TRAVADA, (
        "o controle do CABO não travou o botão da luz — e o gesto vai recusar "
        "depois do clique com a frase do cabo, que é a metade que a tela deve "
        "dizer antes")
    assert colunas["BT"]["luz-trava"] == pac.LUZ_LIVRE, (
        "o controle do RÁDIO travou o botão que existe justamente para ele")


def test_a_trava_da_luz_concorda_com_a_recusa_do_gesto() -> None:
    """A tela e o gesto usam a MESMA regra — e a régua prova isso agindo.

    É a guarda contra a segunda verdade: se um dia o gesto passar a aceitar o
    cabo (ou a recusar o rádio) e a pintura não acompanhar, a tela ofereceria
    um botão aceso que recusa, ou apagaria um que funciona.
    """
    import pytest

    pac = _pacote()
    ctx = _ctx()
    for controle in ctx.conectados:
        via = str(controle.get("transport") or "")
        travado = pac.trava_da_luz(via) == pac.LUZ_TRAVADA
        clique = {"uniq": controle["uniq"], "controle": ""}
        if travado:
            with pytest.raises(RuntimeError):
                pac.luz_nao_acende(ctx, clique, object())
        # O RÁDIO NÃO É EXERCITADO AQUI, e é de propósito: chamá-lo pediria um
        # `Disconnect` de verdade no BlueZ desta máquina. O que esta régua trava
        # é o lado que a tela apaga — o outro é o `SEM_ECO` do piloto que mede.


def test_o_caminho_do_mic_segue_o_transporte() -> None:
    """A frase do caminho é a do rádio no rádio e a do cabo no cabo.

    E ELA PERGUNTA AO DONO (`caminho_do_microfone`) em vez de digitar as duas
    frases: o texto é do desenho dela e pode ser reescrito — o que esta régua
    trava é que o pacote não escolha pela POSIÇÃO.
    """
    pac = _pacote()
    colunas = _por_transporte(pac.pacote(_ctx()))
    assert colunas["USB"]["mic-caminho"] == pac.caminho_do_microfone("usb")
    assert colunas["BT"]["mic-caminho"] == pac.caminho_do_microfone("bt")
    assert (pac.caminho_do_microfone("usb")
            != pac.caminho_do_microfone("bt")), (
        "as duas frases do caminho do microfone viraram a mesma — a régua "
        "acima passaria a dar verde sobre um campo que não distingue nada")


def test_o_transporte_que_ninguem_leu_nao_promete_a_ponte() -> None:
    """Sem transporte lido, o caminho é o do CABO — nunca o da ponte.

    A ponte de rádio é o que CUSTA turno (a régua de Desempenho a mostra).
    Afirmá-la sem leitura poria na tela um preço que ninguém mediu.
    """
    pac = _pacote()
    assert pac.caminho_do_microfone("") == pac.caminho_do_microfone("usb")
    assert pac.trava_da_luz("") == pac.LUZ_TRAVADA


def test_o_gerador_e_o_pacote_dizem_a_mesma_frase() -> None:
    """O gerador não tem mais a frase do caminho do mic — ele a PEDE.

    Enquanto a frase morava nos dois, a linha fechada e a repintura podiam
    divergir sem ninguém ver. A régua lê o CORPO da função no fonte do gerador
    — e só ele: procurar a frase no arquivo inteiro reprovaria o COMENTÁRIO que
    conta esta história, que é a régua confundindo a palavra com o ato.
    """
    fonte = GERADOR.read_text(encoding="utf-8")
    corpo = re.search(r"^def caminho_do_mic\(.*?^(?=\S)", fonte,
                      flags=re.S | re.M)
    assert corpo, "o `caminho_do_mic` sumiu do gerador da 08"
    texto = corpo.group(0)
    assert "_pacote08.caminho_do_microfone" in texto, (
        "o `caminho_do_mic` do gerador deixou de PEDIR a frase ao pacote — "
        "a bancada e a repintura voltam a poder divergir sem ninguém ver")
    for metade in ("Pela ponte", "Placa do controle"):
        assert metade not in texto, (
            f"a frase `{metade}` voltou a ser digitada no gerador — ela é do "
            f"`a08_conexoes.caminho_do_microfone`, que os dois lados chamam")


# ---------------------------------------------------------------------------
# (c) A CONFISSÃO — ela é da mesa dela, não da cena
# ---------------------------------------------------------------------------
def _com_lacunas(monkeypatch: Any, quantas: int) -> dict[str, str]:
    """O que o pacote emite quando a bancada dela tem `quantas` lacunas."""
    from hefesto_dualsense4unix.app.widgets import mapa_da_mesa

    pac = _pacote()
    monkeypatch.setattr(pac, "_bancada", lambda: object())
    monkeypatch.setattr(
        mapa_da_mesa, "confissao_do_desenho",
        lambda _b: tuple(f"lacuna número {n}" for n in range(quantas)))
    return pac._confissao_do_mapa()


def test_a_confissao_conta_as_lacunas_da_bancada(monkeypatch: Any) -> None:
    """A conta por extenso é a de `confissao_do_desenho`, e não a da cena.

    A CENA TEM TRÊS. Se a régua desse verde com a bancada em uma lacuna
    dizendo "três coisas", ela estaria medindo o mockup — que é exatamente o
    defeito que esta leva fechou.
    """
    pac = _pacote()
    for quantas in (1, 2, 3):
        campos = _com_lacunas(monkeypatch, quantas)
        assert campos["confissao-conta"] == pac.palavra_da_conta(quantas), (
            f"com {quantas} lacuna(s) a tela diria "
            f"{campos['confissao-conta']!r}")
        assert campos["confissao-nada"] == "", (
            "há o que confessar e a linha se apagaria")
        # E OS ITENS CHEGAM, um por linha do `title`.
        assert campos["confissao-dica"].count("\n") == quantas, (
            f"a dica não trouxe as {quantas} lacunas: "
            f"{campos['confissao-dica']!r}")


def test_sem_lacuna_a_linha_da_confissao_some(monkeypatch: Any) -> None:
    """Zero lacuna apaga a linha — a mesma regra da janela do desenho.

    Sem o interruptor, a tela leria *"O que eu não consegui conferir neste
    desenho: nada."* — uma frase que ocupa a linha para não dizer nada.
    """
    campos = _com_lacunas(monkeypatch, 0)
    assert campos["confissao-nada"] == "sim", (
        "sem lacuna nenhuma a linha da confissão continuaria na tela")


def test_sem_censo_a_confissao_nao_emite_nada(monkeypatch: Any) -> None:
    """Barramento não lido: NÃO se emite — porque vazio vira travessão.

    O `escrever()` do piloto troca `""` por `—`, e a linha diria *"…neste
    desenho: —."*. Não emitir deixa o desenho como ele nasceu, que é o único
    estado honesto quando a leitura falhou.
    """
    pac = _pacote()
    monkeypatch.setattr(pac, "_bancada", lambda: None)
    assert pac._confissao_do_mapa() == {}


def test_a_palavra_da_conta_nunca_mente_por_extenso() -> None:
    """Fora da tabela, o número cru — nunca a última palavra que couber.

    A cena pode acender uma sexta lacuna no dia em que `mapa_da_mesa.CONFISSAO`
    crescer. Escrever "cinco coisas" sobre seis seria a tela afirmando uma
    contagem que ela não fez.
    """
    pac = _pacote()
    fora = max(pac.PALAVRA_DA_CONTA) + 1
    assert pac.palavra_da_conta(fora) == str(fora)
