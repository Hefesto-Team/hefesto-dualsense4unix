#!/usr/bin/env python3
"""O CHECK-UP RESPONDE EM UMA LINHA, e a mesa de rádio é a DELA.

**04/09/2026.** Duas frentes desta leva, e as duas fecham o mesmo tipo de
buraco — a tela mostrando cenário onde o produto já sabia responder.

**S-09 — a linha de veredito (decisão D-16 dela):** *"Uma linha de veredito no
topo."*, *"Na cor do pior achado."* O Check-up tinha cinco pílulas e nenhum
juízo: para saber se estava tudo certo era preciso ler as cinco e achar a pior,
e a segunda ordem de serviço desta bancada — que não cabe nas cinco — não
entrava nessa leitura de jeito nenhum. O pacote já emitia `achados` e `graves`
(as duas contagens de que a frase precisa) e a página não tinha onde recebê-las.

**A MESA DE RÁDIO — três coisas que a tela cravava do mockup:**

    a tabela de adaptadores     "Sala / TP-Link UB500 / Entrada 3" e "Sem nome /
                                Intel AX211 / Interno", sobre uma máquina com
                                TRÊS adaptadores `2357:0604`
    a régua de Desempenho       uma pista, sem nome, quando `ler_a_mesa()`
                                enumera os três e o BlueZ dá o nome de cada um
    a coluna "Onde" dos rádios  não existia — a linha do Check-up diz "dois
    vizinhos                    rádios em entradas vizinhas" e não diz QUAL

**A REGRA QUE ESTA LEVA CONFIRMOU:** as duas frases que o próprio código
escrevia como impossíveis — *"UMA PISTA POR ADAPTADOR espera uma fonte"* e *"o
apelido mora na declaração dela … as duas não casam hoje"* — descreviam o
caminho errado, não uma falta. `mesa_de_radio.ler_a_mesa().adaptadores` enumera,
e o `Dongle` do BlueZ carrega o endereço, o `hciN` e o nome no MESMO objeto.

AS MORDIDAS — ONZE, arrancadas de verdade em 04/09/2026, uma a uma, com o
desenho devolvido byte a byte idêntico no fim. Cada uma derrubou **um** teste, e
só ele:

===  ============================================  ==========================
 #   o que se arranca                              quem reprova
===  ============================================  ==========================
 1   `frase = topo.texto` incondicional em         `..._nao_diz_nada_a_mudar_
     `_veredito_do_exame`                          com_uma_linha_grave`
 2   `ordens=todas` no lugar de `ordens=novas`     `..._o_que_ela_calou_nao_
                                                   segura_a_cor`
 3   um `<i class="vst">` fora de                  `..._tem_um_interruptor_
     `aba08.veredito_do_checkup`, e regerar        por_estado_do_veredito`
 4   (caducou em 23/09/2026 — a régua de fatias    `..._uma_pista_por_
     saiu com a seção velha)                       adaptador` (e a irmã)
 5   (caducou em 23/09/2026 — a tabela saiu)       `..._a_tabela_dos_
                                                   adaptadores_tem_endereco`
 6   (caducou em 23/09/2026 — a coluna "Onde"      `..._a_coluna_onde_dos_
     saiu; o vizinho é selo)                       vizinhos_tem_endereco`
 7   (caducou em 13/09/2026 — o aviso da mesa      `..._nao_anexa_o_aviso_
     suja saiu da dica, FRASES-E-DICAS-02)         da_mesa_suja`
 8   (caducou em 13/09/2026 — a razão do           `..._a_razao_do_nascimento_
     nascimento saiu da dica, FRASES-E-DICAS-03)   nao_chega_a_dica`
 9   `"Custa +16,3 turnos"` digitado no lugar      `..._o_custo_do_mic_no_
     da frase derivada                             radio_nao_e_digitado`
10   o `<select data-gesto="mic-escopo">` de       `..._e_leitura_e_nao_
     volta no lugar da leitura                     escolha`
11   o `data-campo="mic-dica"` fora do `title`     `..._do_resumo_do_mic_
     do resumo                                     tem_endereco`
===  ============================================  ==========================
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


def _item(estado: str, chave: str = "", ordem: object = None):  # type: ignore[no-untyped-def]
    """Um `Item` do exame — o do PRODUTO, nunca um dublê de forma parecida."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item

    return Item(chave=chave or f"c-{estado}", rotulo="", estado=estado,
                porque="", ordem=ordem)


def _ordem(chave: str, arranjo: str):  # type: ignore[no-untyped-def]
    """Uma `Ordem` do catálogo, com o mínimo que a dispensa endereça.

    A CLASSE É A DO PRODUTO, e não um dublê de forma parecida: `ordens_novas` e
    `ordens_caladas` leem `chave` e `arranjo`, e um objeto anônimo passaria neste
    teste e mentiria no dia em que a dispensa mudar de chave.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Linha, Ordem

    vazia = Linha(texto="", selo="medido_aqui")
    return Ordem(
        chave=chave,
        acao="Mova o adaptador",
        o_que_eu_vi=vazia,
        por_que_importa=vazia,
        ganho_esperado=vazia,
        arranjo=arranjo,
    )


# ---------------------------------------------------------------------------
# S-09 — A LINHA DE VEREDITO
# ---------------------------------------------------------------------------
def test_a_frase_do_veredito_e_a_do_dono() -> None:
    """A frase NÃO nasce no pacote: ela é de `ordens_da_mesa.cabecalho()`.

    Quatro frases, quatro cenas — e as quatro conferidas contra o dono, que é
    quem as escreve. Um literal no pacote seria a segunda grafia, e a primeira
    coisa que uma segunda grafia perde é o dia em que a outra muda.
    """
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("certo"), _item("certo")])
    esperado = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0)
    assert saiu["veredito"] == esperado.texto, (
        f"o veredito disse {saiu['veredito']!r} e o dono escreve "
        f"{esperado.texto!r} — alguém digitou a frase no pacote")


def test_a_cor_e_a_do_pior_achado() -> None:
    """Um `problema` entre cinco `certo` acende o vermelho, e só ele."""
    p = _pacote()
    itens = [_item("certo"), _item("problema"), _item("certo")]
    saiu = p._veredito_do_exame(itens)
    assert saiu["veredito-problema"] == "problema", (
        "a linha de veredito não acendeu no pior achado")
    for estado, endereco in p.ENDERECO_DO_VEREDITO.items():
        if estado == "problema":
            continue
        assert saiu[endereco] == "", (
            f"`{endereco}` acendeu junto com o `problema`. Um instante com dois "
            f"acesos deixa o que está QUEBRADO com a cor do que só podia estar "
            f"melhor, que é a confusão que ela mandou desfazer em 02/09.")


def test_o_veredito_nao_diz_nada_a_mudar_com_uma_linha_grave() -> None:
    """A MORDIDA da cicatriz `6c86e295`, e ela é a razão de a função existir.

    `ordens_da_mesa.cabecalho()` **não conhece `problema`**: sem ordem aberta
    ele responde "Nada a mudar", em verde. `exame_da_mesa.veredito()` sobre as
    linhas conhece — e é `secao_exame.o_mais_grave` quem os concilia. Um selo
    pintado só pelo segundo diria *"Nada a mudar"* em verde com a linha de
    pareamentos em vermelho, que é o defeito que esta casa pagou duas vezes em
    agosto.

    ARRANQUE A CURA: troque o `frase = topo.texto if estado == topo.estado else
    …` por `frase = topo.texto` e este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_exame import FRASE_DO_SELO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import cabecalho

    p = _pacote()
    saiu = p._veredito_do_exame([_item("problema"), _item("certo")])
    verde = cabecalho(ordens=[], conferidas=2, sem_resposta=0, dispensadas=0).texto
    assert saiu["veredito"] != verde, (
        f"com uma linha em `problema` o veredito escreveu {verde!r} — a frase "
        f"do cabeçalho, que não conhece `problema`. É a cicatriz 6c86e295 "
        f"voltando: o verde convivendo com o vermelho na mesma seção.")
    assert saiu["veredito"] == FRASE_DO_SELO["problema"], (
        "quando o estado das linhas vence o do cabeçalho, a frase tem de ser a "
        "do estado — e ela também tem dono (`secao_exame.FRASE_DO_SELO`)")


def test_o_que_ela_calou_nao_segura_a_cor() -> None:
    """A ordem DISPENSADA sai da conta — senão o ⊘ é botão morto.

    É a mesma regra do `_escrever_o_cabecalho` da janela estável: uma ordem
    dispensada prenderia o topo em laranja para sempre e o clique dela não
    faria nada visível.

    ARRANQUE A CURA: faça `_veredito_do_exame` passar `todas` no lugar de
    `novas` e este teste reprova.
    """
    p = _pacote()
    ordem = _ordem("vizinhanca", "arranjo-de-hoje")
    itens = [_item("certo"), _item("atencao", chave="o1", ordem=ordem)]  # (dado) noqa-acento

    antes = dict(p._DISPENSADAS)
    try:
        p._DISPENSADAS = {}
        com_ordem = p._veredito_do_exame(itens)
        p._DISPENSADAS = {"vizinhanca": "arranjo-de-hoje"}
        calada = p._veredito_do_exame(itens)
    finally:
        p._DISPENSADAS = antes

    assert com_ordem["veredito-atencao"] == "atencao", (  # noqa-acento: chave e valor de dado
        "com a ordem aberta o topo tinha de estar em `atencao`")  # noqa-acento: nome do estado
    assert calada["veredito-atencao"] == "", (
        "a ordem que ela dispensou continuou segurando o topo em laranja — o ⊘ "
        "grava e a tela não muda, que é a definição de botão morto")


def test_o_veredito_chega_ao_pacote() -> None:
    """A LIGAÇÃO, e não só a peça.

    A lição está escrita no `test_a08_o_selo_do_exame_tem_um_endereco_por_estado`:
    um teste que prova a peça e não a ligação dá verde sobre um fio solto.
    """
    p = _pacote()
    saiu = p.pacote(_ctx())
    assert "veredito" in saiu, (
        "o `pacote()` não emite `veredito` — a linha do desenho fica com a "
        "frase da bancada para sempre")
    for endereco in p.ENDERECO_DO_VEREDITO.values():
        assert endereco in saiu, (
            f"o `pacote()` não emite `{endereco}`: o desenho tem o interruptor "
            f"e ninguém o acende")


def test_o_desenho_tem_um_interruptor_por_estado_do_veredito() -> None:
    """A outra metade: sem o endereço no HTML, o pacote escreve no vazio.

    ARRANQUE A CURA: tire um `<i class="vst">` de `aba08.veredito_do_checkup`,
    regenere, e este teste reprova.
    """
    p = _pacote()
    html = BANCADA.read_text()
    for endereco in p.ENDERECO_DO_VEREDITO.values():
        assert f'data-campo="{endereco}"' in html, (
            f"o desenho não tem `{endereco}` — o pacote emite e a tela não "
            f"recebe")
    assert 'data-campo="veredito"' in html, (
        "a linha de veredito não tem endereço para a frase")
    assert html.count('class="veredito"') == 1, (
        "a linha de veredito tem de ser UMA — ela responde pela seção inteira, "
        "e duas seriam duas respostas para a mesma pergunta")


def test_a_linha_de_veredito_mora_acima_das_duas_colunas() -> None:
    """*"Uma linha de veredito no topo"* — a palavra dela é TOPO.

    Dentro da coluna do exame ela responderia por metade da seção: a ordem de
    serviço vive na outra.
    """
    html = BANCADA.read_text()
    veredito = html.index('class="veredito"')
    colunas = html.index('class="duas-colunas"', html.index('id="cx8-2"'))
    assert veredito < colunas, (
        "a linha de veredito nasceu DENTRO das colunas — ela responde pelas "
        "duas, e pendurada em uma delas responde por metade da seção")


# ---------------------------------------------------------------------------
# A MESA DE RÁDIO SAIU DESTA RÉGUA — 23/09/2026, TRANSPLANTE-DA-SECAO-01.
#
# A tabela dos adaptadores, a régua de Desempenho e a coluna "Onde" dos vizinhos
# saíram da tela com a seção velha: «Rádio e Adaptadores» é o
# `mapa-do-radio.html` aprovado. O que elas prendiam continua preso, pela seção
# nova, em `test_a_secao_do_radio_transplantada.py` — um cartão por adaptador
# que o BlueZ enumera, o nome DELA no campo do cartão, e o vizinho como selo
# com o endereço `vid:pid` do gesto.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# O CONTEXTO VIVO — a mesa de dois que faz o `pacote()` correr inteiro
# ---------------------------------------------------------------------------
def _ctx():  # type: ignore[no-untyped-def]
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


# ---------------------------------------------------------------------------
# O BOTÃO "A luz não acende" — a dica que era do desenho
# ---------------------------------------------------------------------------
def test_a_dica_da_luz_segue_o_transporte() -> None:
    """As duas frases são do dono, e não a mesma congelada.

    O `title` do desenho era do transporte da CENA: o cartão da esquerda dizia
    *"Este controle está no cabo"* e o da direita explicava o rádio — e os dois
    continuavam dizendo isso quando o controle trocava de transporte. A cor já
    obedecia desde 03/09; a frase, não.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_NO_CABO,
        DICA_NO_RADIO,
    )

    p = _pacote()
    assert p.dica_da_luz("usb") == DICA_NO_CABO
    assert p.dica_da_luz("bt") == DICA_NO_RADIO
    assert p.dica_da_luz("") == DICA_NO_CABO, (
        "transporte vazio é TRAVA, pela mesma razão do gesto: `Disconnect` "
        "sobre um controle cujo transporte ninguém leu é um pedido no escuro")


def test_a_dica_da_luz_nao_anexa_o_aviso_da_mesa_suja(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A mesa suja NÃO muda a dica — FRASES-E-DICAS-02, 13/09/2026.

    CONTRATO QUE MUDOU: até esta data a dica ANEXAVA o aviso da mesa suja, com
    instrução. A ordem dela de 13/09 tira frase de aviso da tela em toda forma,
    `title` incluído (`docs/process/sprints/2026-09-13-A-TERCEIRA-LISTA-DELA-
    INDICE.md`, a mensagem de abertura). A dica fica com o que o botão faz.

    O DUBLÊ É A SONDA DE VERDADE respondendo SUSPEITA — outro programa
    segurando o nó. Se alguém religar a pergunta pela mesa DENTRO de
    `dica_da_luz`, as duas respostas deixam de ser iguais, com as palavras que
    forem.

    O ALCANCE DESTA, MEDIDO NA VALIDAÇÃO DE 13/09/2026: com o código de
    `249af1f6` devolvido inteiro, ela fica VERDE — ali a sonda morava no tique
    (`pacote()` perguntava e passava `mesa_suja` à função), e esta chamada
    direta nunca a aciona. Quem morde essa volta é
    `test_nenhuma_frase_de_aviso_chega_a_tela.
    test_a_dica_da_luz_nao_avisa_com_outro_programa_segurando_o_controle`, que
    passa pelo `pacote()`.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import DICA_NO_RADIO
    from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

    p = _pacote()
    limpa = p.dica_da_luz("bt")
    monkeypatch.setattr(sb, "limpo_para_conectar",
                        lambda *a, **k: (sb.CONFIANCA_SUSPEITA, "dublê", (4242,)))
    suja = p.dica_da_luz("bt")
    assert suja == limpa == DICA_NO_RADIO, (
        "a dica da luz mudou com outro programa segurando controle — o aviso da "
        f"mesa suja voltou a ser anexado: {suja!r}")


def test_a_razao_do_nascimento_nao_chega_a_dica() -> None:
    """A RAZÃO DO NASCIMENTO SAIU DA DICA — FRASES-E-DICAS-03, 13/09/2026.

    CONTRATO QUE MUDOU: até esta data a condenação escrevia a razão depois do
    que o botão faz. A ordem dela de 13/09
    (`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`) tira da
    tela frase de aviso em toda forma, `title` incluído: a dica fica com o que o
    botão faz, e o carimbo `nascimento` fica no `state_full`, para o diagnóstico.

    PASSA PELO TIQUE: os dois controles desta mesa chegam condenados no estado,
    e o `pacote()` escreve para cada um só a dica do dono.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_controles import (
        DICA_NO_CABO,
        DICA_NO_RADIO,
    )

    p = _pacote()
    porque = "Esta conexão nasceu com outro programa segurando o controle"
    ctx = _ctx()
    for controle in ctx.conectados:
        controle["nascimento"] = {"pede_reconexao": True, "porque": porque}
    dicas = [coluna.get("luz-dica", "") for coluna in p.pacote(ctx)["colunas"].values()]
    assert sorted(dicas) == sorted([DICA_NO_CABO, DICA_NO_RADIO]), (
        "com os dois controles condenados, a dica da luz deixou de ser só a do "
        f"dono — a razão do carimbo de nascimento voltou à tela: {dicas!r}")


def test_o_botao_da_luz_tem_a_dica_e_a_trava_em_nos_diferentes() -> None:
    """Um `data-campo` por nó — a classe no `<i>`, a dica no `<button>`.

    ARRANQUE A CURA: devolva o `data-campo="luz-trava"` ao próprio botão, e o
    `title` volta a ser o do desenho — o defeito que a dívida do gerador
    declarava com todas as letras.
    """
    html = BANCADA.read_text()
    botoes = re.findall(r'<button[^>]*data-gesto="luz-nao-acende"[^>]*>', html)
    assert botoes, "o botão 'A luz não acende' sumiu do desenho"
    for botao in botoes:
        assert 'data-campo="luz-dica"' in botao, (
            "o botão da luz não tem endereço para a dica — ela continua sendo "
            "a do desenho e mente quando o controle troca de transporte")
        assert 'data-hef-atributo="title"' in botao
        assert 'data-campo="luz-trava"' not in botao, (
            "a classe e a dica voltaram para o mesmo nó — o vocabulário é UM "
            "`data-campo` por nó, e uma das duas vai ficar sem endereço")
    # O `<i>` COLADO NO `<button>`: é assim que o `~` do CSS alcança a cor, e é
    # a única forma que prova a ORDEM dos dois. O `[^>]*></i><button` não deixa
    # nada entrar no meio.
    irmaos = re.findall(r'<i class="ltrava[^"]*"[^>]*></i><button[^>]*'
                        r'data-gesto="luz-nao-acende"', html)
    assert len(irmaos) == len(botoes), (
        f"{len(irmaos)} dos {len(botoes)} botões da luz têm o interruptor "
        f"colado ANTES deles — o `~` do CSS só alcança irmãos posteriores, e o "
        f"botão sem irmão anterior nunca apaga")
    for irmao in irmaos:
        assert 'data-campo="luz-trava"' in irmao, (
            "o interruptor da trava ficou sem endereço — a classe volta a ser a "
            "do desenho, cravada pela posição no mockup")


def test_a_dica_da_luz_chega_ao_pacote() -> None:
    """A ligação — uma dica por controle, no `colunas`."""
    p = _pacote()
    saiu = p.pacote(_ctx())
    for uniq, coluna in saiu["colunas"].items():
        assert coluna.get("luz-dica"), (
            f"o controle {uniq[:4]}… saiu sem `luz-dica` — o botão fica com o "
            f"`title` do desenho")


# ---------------------------------------------------------------------------
# O MICROFONE — o escopo virou leitura (D-12) e o custo virou derivado
# ---------------------------------------------------------------------------
# `test_o_escopo_do_botao_do_mic_e_leitura_e_nao_escolha` SAIU — o controle «Microfone e botões» saiu da linha do controle em 25/09/2026, por pedido dela (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01): o mic é da aba Jogar/Controles, e a linha mostra só o selo «Mic ✓» (tests/unit/test_a_08_o_checkup_absorve_a_gestao.py).


def test_o_escopo_le_o_valor_da_maquina() -> None:
    """As duas falas são as do `<select>` que saiu — nem uma palavra nova.

    E a ausência devolve VAZIO, nunca o padrão do `DaemonConfig`: um daemon que
    não respondeu não é um daemon que respondeu `True`.
    """
    p = _pacote()
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": True}) == (
        p.FALA_DO_BOTAO_DO_MIC[True])
    assert p.escopo_do_botao_do_mic({"mic_button_toggles_system": False}) == (
        p.FALA_DO_BOTAO_DO_MIC[False])
    assert p.escopo_do_botao_do_mic({}) == "", (
        "sem resposta do daemon a tela afirmou um dos dois — o travessão do "
        "piloto é a resposta honesta")
    assert p.pacote(_ctx())["mic-escopo"] == "", (
        "o `_ctx()` não publica a chave, e o pacote inventou um valor")


def test_o_custo_do_mic_no_radio_nao_e_digitado(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A MORDIDA do número: mude a constante do medidor e a frase acompanha.

    Os 16,3 do desenho conferiam com `radio_da_mesa` HOJE — eles eram a segunda
    grafia. `frase_da_capacidade_do_mic` deriva os quatro números das constantes
    do medidor, *"que é o mesmo lugar de onde a barra de Rádio em uso tira os
    dela"*.
    """
    from hefesto_dualsense4unix.integrations import radio_da_mesa as rm

    p = _pacote()
    antes = p.dica_do_microfone("bt")
    monkeypatch.setattr(rm, "HZ_AUDIO_COM_MIC", rm.HZ_AUDIO_COM_MIC * 3)
    depois = p.dica_do_microfone("bt")
    assert antes != depois, (
        "a frase do custo do microfone não seguiu a constante do medidor — ela "
        "está digitada, e no dia em que alguém remedir o A/B a janela estável "
        "acompanha e o HTML não")


def test_o_mic_pelo_cabo_nao_cobra_turno_de_radio() -> None:
    """Pelo cabo não há conta a fazer — e "0 turnos" seria um número sem conta."""
    p = _pacote()
    cabo = p.dica_do_microfone("usb")
    assert p._MIC_NAO_CUSTA_RADIO in cabo
    assert "turnos de rádio" not in cabo.replace(p._MIC_NAO_CUSTA_RADIO, ""), (
        "a frase do cabo trouxe a conta do rádio junto")


# `test_o_titulo_do_resumo_do_mic_tem_endereco` SAIU — o controle «Microfone e botões» saiu da linha do controle em 25/09/2026, por pedido dela (A-08-O-CHECKUP-ABSORVE-A-GESTAO-01): o mic é da aba Jogar/Controles, e a linha mostra só o selo «Mic ✓» (tests/unit/test_a_08_o_checkup_absorve_a_gestao.py).
