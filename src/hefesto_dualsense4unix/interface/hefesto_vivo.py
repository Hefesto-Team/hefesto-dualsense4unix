#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as dez abas, tudo pintado pelo despachante."""
from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any

import argparse
import contextlib
import dataclasses
import os
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
# A RAIZ É `parents[2]`, e o `[1]` custou dois instrumentos calados.
RAIZ = AQUI.parents[2]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

# `portao_a_casa_sabe_e_o_produto_nao_faz` chegava a **zero** módulos da interface
# A JANELA PEDE A PÁGINA ANTES DAS DEZ ABAS — O-APP-RESPONDE-NA-HORA-01, cura 3
# a página. Medido no lar de mentira: os dois custam ~0,3 s, e importados no
from hefesto_dualsense4unix.interface import (  # noqa: E402
    monta,
    onde,
    regua_do_mockup,
)

if __name__ != "__main__":
    from hefesto_dualsense4unix.interface import mesa_viva, pacotes
    from hefesto_dualsense4unix.interface.pacotes import ponte

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402
from hefesto_dualsense4unix.interface.janela import JanelaDaAba  # noqa: E402

#: A PRIMEIRA PÁGINA é a Jogar, que é a primeira da tira. Não é escolha de
#: gosto: é a aba que o `.desktop` dela abre.
PRIMEIRA = "01-jogar.html"

#: O tique da pintura. **100 ms — o mesmo da janela GTK**
#: (`app/constants.LIVE_POLL_INTERVAL_MS`) e o mesmo do `controles_vivos`
#: (`controles_vivos.TIQUE_MS`). As três leituras ao vivo do produto batem.
#:
#: FATO ERRADO, SUBSTITUÍDO EM 04/09/2026: esta linha dizia `500` e o comentário
#: justificava o número afirmando que *"500 ms é o mesmo do `controles_vivos`"*.
#: Não era: o `controles_vivos.py:119` sempre teve `TIQUE_MS = 100`. O número
#: errado tinha consequência medida — ela relatou *"delay absurdo em controles"*
#: olhando a aba 02, onde meio segundo de atraso separa o dedo do desenho.
#:
#: O CUSTO FOI MEDIDO ANTES DE BAIXAR, com o daemon dela vivo e dois DualSense
#:
TIQUE_MS = 100


#: Fato errado se substitui, e sai de todos os lugares onde aparece: os três

#: que caducou não foi o número: foi o CANAL cuja vida ele contava.
#: SEM DEPÓSITO NÃO HÁ PRAZO: a piscada se apaga sozinha no JS, e nenhum relógio

#: palavra: é o piloto FALAR quando não tem o que dizer.** Quem responde agora é
#: a piscada (`MS_DA_PISCADA`), e a palavra do GTK segue viva no dono dela.
#: gesto que devolva `{"recado": "…"}` manda a própria frase, e ela vai ao diário

#: (`hef-recusou`) quando ele levantou ou não tinha dono. O relógio é um só
#: **E O TEXTO DESTE COMENTÁRIO É PARTE DO PROBLEMA**, o que se descobriu na
MS_DA_PISCADA = 1500

#: recarregada é o que ela vê.

#: O CONTRATO TEM DUAS PONTAS: o pacote devolve `{"armou": True, …}` (o lado da
CHAVE_DO_CLIQUE_QUE_SO_ARMOU = "armou"

#: O QUE A GUARDA DE CARGA ACEITA. Os pilotos de uma aba só passavam o nome
#: Aqui as DEZ são legítimas, então o esperado é o que as dez compartilham:
#:
#:     Hefesto — aba JOGAR (mockup 26/08/2026)
#:     Hefesto — aba GATILHOS (mockup 26/08/2026)
#:
#: A guarda casa por SUBSTRING, e `"Jogar"` não casa com `"aba JOGAR"` — foi o
#: que matou a primeira execução deste piloto. Continua servindo para o que ela
#: existe: uma página que NÃO é do mockup (um erro de carga, um `about:blank`)
TITULO_DE_QUALQUER_ABA = "Hefesto — aba "


def _a_pagina_pedida(pedido: str) -> str:
    """Resolve o que veio no ``--abre`` para o nome de arquivo da página.

    ACEITA AS TRÊS FORMAS QUE ALGUÉM DIGITA, e a razão é medida: o `--abre`
    dizia só *"abrir direto numa aba"* e passava a string CRUA ao
    `onde.pagina`. `--abre 10` virava `paginas/10`, o WebKit carregava a
    página de erro dele, o piloto seguia o passeio e o relatório saía com as
    dez abas zeradas — **rc=0 sobre uma foto que dizia "No such file"**.

    * ``"10"``            → ``"10-perfis.html"``
    * ``"10-perfis"``     → ``"10-perfis.html"``
    * ``"10-perfis.html"`` → ele mesmo

    O que não casar com nenhuma página volta INTACTO — quem reprova é o
    `_ir`, que confere a existência do arquivo. Adivinhar aqui esconderia o
    erro de digitação dela dentro de uma aba que ela não pediu.
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return pedido
    nomes = [caminho.name for caminho in onde.paginas(publicado=True)]
    if pedido in nomes:
        return pedido
    for nome in nomes:
        if nome == f"{pedido}.html" or nome.split("-", 1)[0] == pedido:
            return nome
    return pedido


#: `a04_iluminacao.banco_de_luzes` — *"nenhum `data-controle` nasce aqui"* —, e
#: A LISTA É DE PERMITIDOS, e o dono dos assentos é `pacotes.TODOS_OS_LUGARES`.
#: `test_o_seletor_do_dono_pergunta_ao_dono` exige que os três digam o mesmo.
#:
#: Ele se monta em `_ligar_as_abas`, porque os assentos moram nos pacotes e a
#: janela do produto só os importa depois de pedir a página.
SELETOR_DO_DONO: str

#: O QUE UM GESTO **VIVO** NÃO PODE DEVOLVER — a quarta porta é de LEITURA.
#:
#: As três primeiras são o mesmo fato de forma diferente: um `input` dispara a
#: cada TECLA, e o que estas chaves fazem custa caro dez vezes por segundo.
#:
#: * `blocos` e `fita` TROCAM HTML INTEIRO — `innerHTML` no container, `outerHTML`
#:   no nó. É o defeito que a `A-TELA-SAMBA-01` mediu em 06/09/2026: quem clicou
#:   fica com o `mousedown` num nó que já não existe. Aqui seria pior, porque o
#:   nó arrancado é o campo em que ela está DIGITANDO;
#: * `recado` e `recados` eram o canal de AVISO na tela. **Desde 13/09/2026
#:   nenhum dos dois chega a ela** (TELA-CALADA-01 e FRASES-E-DICAS-01): o
#:   `recado` vai ao diário e o `recados` ninguém mais pinta. A recusa fica pelo
#:   custo que sobrou — uma linha de diário por tecla afogaria quem depura, e um
#:   gesto vivo que devolve frase é defeito de quem o ligou.
#:
#: O QUE SOBRA É A CARGA DE PINTURA — `mesa`, `colunas`, `alvo`. É o vocabulário
#: que o `_deu_certo` já usa, e nenhum segundo nasce aqui.
CHAVES_QUE_O_VIVO_RECUSA = ("blocos", "fita", "recado", "recados")

#: O BOOTSTRAP: uma função de pintura, genérica, para as dez.
#:
#: Ela NÃO sabe nada de nenhuma aba — recebe endereço e valor e escreve. Toda a
#: inteligência está do lado Python, nos pacotes, que são puros e testáveis sem
#: abrir janela. Foi assim que 143 valores puderam ser medidos antes de existir
#: esta janela.
#:
#: O CONTADOR É O QUE IMPEDE O VERDE SOBRE NADA. `pintar()` devolve quantos
#: valores escreveu, e o piloto imprime. Uma aba que devolve 0 com pacote não
#: vazio é endereço que não existe na página — e é o defeito que fez a
#: `06-navegacao` publicar zero endereços em 01/09 sem ninguém ver.
BOOTSTRAP = r"""
(function(){
  window.__hef = window.__hef || {};
  // O QUE CONTA COMO LIGADO, e vale só para o alvo `classe`. A lista é a mesma
  // dos dois lados — `regua_do_mockup._ligado` repete estas nove palavras — e
  // é ela que faz o `True` do Python e o `true` do JS quererem dizer a mesma
  // coisa neste alvo. O travessão entra porque é o que o `escrever` põe no
  // lugar de um valor vazio: um lugar VAZIO da mesa apaga a classe.
  function ligado(t){
    const b = String(t).trim().toLowerCase();
    return !(b === '' || b === '—' || b === '0' || b === 'false'
             || b === 'nao' || b === 'não' || b === 'off'  // (noqa-acento) valores
             || b === 'none' || b === 'null');
  }
  // O QUE O ALVO `atributo` PODE ESCREVER, e a lista é curta de propósito.
  //
  // O NOME VEM DA PÁGINA (do `data-hef-atributo` que o gerador escreve), não do
  // daemon — então isto não é guarda contra invasor, é guarda contra ERRO DE
  // GERADOR. Sem ela, um `data-hef-atributo="style"` apagaria, no mesmo tique, o
  // `--plastico` e a `width` que os outros alvos acabaram de pintar no MESMO
  // elemento; um `class` apagaria o alvo `classe`; um `id` quebraria os `url(#…)`
  // que o `monta.svg` prefixa por controle.
  //
  // E A RAZÃO MAIS DURA É O SELO: `escrever()` carimba `data-hef-visto`, e é ele
  // que decide um INDECIDÍVEL na régua do mockup. Um alvo capaz de escrever
  // `data-hef-visto` é um alvo capaz de FORJAR a medição desta casa — por isso
  // todo o prefixo `data-hef` está fora, e não só o selo.
  //
  // Os cinco nomeados são o vocabulário de ENDEREÇO do próprio piloto (`achar()`,
  // os donos de bloco e o ouvinte de gesto): o alvo não pode reescrever a placa
  // da porta por onde ele mesmo entrou.
  //
  // `data-*` e `aria-*` é o que SOBRA, e chega para quase tudo que a lei pede: o
  // `data-colorway` do SVG, o `data-modelo`, e o `aria-label` que um leitor de
  // tela anuncia. Uma lista de proibidos, em vez desta de permitidos, teria de
  // crescer toda vez que o HTML crescer.
  //
  // O `title` É A ÚNICA EXCEÇÃO, e ela é NOMEADA — 03/09/2026. O `fim.html`, que
  // é um só para as dez páginas, pede `data-hef-alvo="atributo"
  // data-hef-atributo="title"` nos botões Salvar e Exportar, para a dica dizer o
  // NOME do perfil ativo em vez de congelar um exemplo (`7db1e0e6`). Aquele
  // commit deu por certo que este alvo "sabe escrever num `title`" — e a guarda o
  // recusava CALADA: as 20 páginas (dez publicadas, dez da bancada) pediam um
  // atributo que nunca pintava, e o único barulho veio do portão
  // `test_todo_data_hef_atributo_publicado_e_escrevivel`.
  //
  // ELE PODE ENTRAR, e as três razões da lista curta não o alcançam: `title` não
  // é `data-hef` (não forja o selo), não é vocabulário de endereço (não move a
  // placa da porta) e não é `style`/`class`/`id` (não desfaz o que outro alvo
  // acabou de pintar no mesmo elemento). É texto de dica, e nada mais.
  //
  // E ELE MUDA UMA DECISÃO DE OUTRA ABA: a dica da linha por controle da
  // `10-perfis` foi REMOVIDA em 03/09 por não haver canal de pintura
  // (`test_aba10_a_dica_da_linha_nao_e_do_mockup`, §4). O canal existe agora —
  // aquela dica pode voltar VIVA, com o modelo e a conta do aparelho.
  const ATRIBUTO_DE_ENDERECO = ['data-campo', 'data-papel', 'data-controle',
                                'data-uniq', 'data-gesto'];
  const ATRIBUTO_A_MAIS = ['title'];
  function atributo_escrevivel(n){
    if(ATRIBUTO_A_MAIS.indexOf(n) >= 0) return true;
    return /^(data|aria)-[a-z0-9]+(-[a-z0-9]+)*$/.test(n)
           && n.indexOf('data-hef') !== 0
           && ATRIBUTO_DE_ENDERECO.indexOf(n) < 0;
  }
  window.__hef.atributoEscrevivel = atributo_escrevivel;
  function escrever(el, v){
    if(!el) return 0;
    const vazio = (v === null || v === undefined || v === '');
    // O TRAVESSÃO NÃO ENTRA NUM CAMPO QUE A PESSOA DIGITA — 11/09/2026.
    //
    // O `—` existe para MOSTRAR AUSÊNCIA num lugar de leitura (um slot vazio da
    // mesa, uma coluna sem dado). Num campo de digitar ele é LIXO: ela abre a
    // busca e acha um travessão escrito lá, que ela tem de apagar antes de
    // procurar. Medido na aba Perfis: `perfis.procura` sai `""` em todo tique,
    // e o campo da lupa nascia com `—` no PRIMEIRO tique em repouso — antes de
    // ela clicar, e de volta a cada fechamento. A guarda `sob_o_dedo` só
    // protege enquanto o campo TEM foco, e o travessão entra antes disso.
    //
    // O ALVO É `data-hef-vivo`, que é a QUARTA PORTA (`:1406`) — o gesto que LÊ
    // e não grava, ou seja, exatamente os campos que a PESSOA dirige. São UM na
    // casa inteira hoje (`procurar`, na 10-perfis), então o alcance é o defeito
    // e nada mais; e no dia em que houver um segundo ele já nasce curado.
    //
    // É A MESMA DISCIPLINA DO `<select>` E DO `<input type=range>` logo abaixo,
    // e a razão é a que aquelas duas guardas já escrevem: uma aba não pode ter
    // de lembrar-se disto — quem esquecer publica o defeito sem erro e sem
    // aviso.
    const digitavel = !!(el.dataset && el.dataset.hefVivo !== undefined
                         && String(el.dataset.hefVivo).trim() !== '');
    const t = vazio ? (digitavel ? '' : '—') : String(v);
    // O ALVO PADRÃO É O TEXTO. `data-hef-alvo` desvia para um atributo quando a
    // tela precisa de outra coisa — a largura de uma barra, o `value` de um
    // campo. Sem isso, pintar uma barra escreveria o número DENTRO dela.
    const alvo = el.dataset.hefAlvo || 'texto';
    // O SELO DA VISITA, e ele é O QUE DECIDE UM INDECIDÍVEL. A régua do mockup
    // lê a TELA e por isso não consegue separar "o produto pintou o mesmo valor
    // que o desenho cravou" de "ninguém tocou aqui" — eram 74 campos em 330.
    // Este selo é o único fato que a tela não mostra: o piloto ESTEVE neste
    // elemento com um valor. Ele é escrito a cada visita, mesmo quando nada
    // muda, porque é justamente a visita SEM mudança que não deixa rastro.
    //
    // ELE NÃO É "LER O CÓDIGO". A casa já se enganou lendo o fonte e publicando
    // 77% onde a tela mostrava 36%. O selo não afirma que um endereço existe no
    // pacote: ele registra que o valor emitido CHEGOU a um elemento desta
    // página — que é exatamente o degrau que faltava entre o `declarado` e o
    // `vivo`. Endereço morto continua sem selo, e continua acusado.
    //
    // E ELE SÓ ESCREVE UMA VEZ — A-TELA-SAMBA-01, 06/09/2026, e é a MAIOR
    // parcela do samba que ela relatou. `el.dataset.hefVisto = '1'` num
    // elemento que já traz `'1'` **é uma mutação de DOM**: a especificação manda
    // enfileirar um `MutationRecord` em toda troca de atributo, e não só quando
    // o valor difere. Medido com `--conta-mutacoes 100`, mesa parada:
    //
    //     01-jogar     7.100 mutações em 100 tiques — 6.700 são este selo
    //     03-gatilhos  6.400 mutações em 100 tiques — 4.700 são este selo
    //
    // O SELO NÃO PERDE NADA COM ISSO, e é o que separa esta cura de uma
    // regressão: o valor dele nunca muda — é `'1'` ou é ausência. A visita SEM
    // mudança continua deixando rastro, porque o rastro é o atributo ESTAR lá,
    // não o ato de reescrevê-lo. Quem nasce sem selo (um nó recriado por uma
    // troca de bloco) ganha o dele no tique seguinte, como sempre ganhou.
    if(el.dataset.hefVisto !== '1'){ el.dataset.hefVisto = '1'; }
    // ESCREVE E DEPOIS RELÊ, como o `cor`, o `plastico` e o `atributo` — e a
    // razão aqui é a MESMA que aqueles três já pagaram: **o CSSOM normaliza**.
    //
    // MEDIDO NESTE MOTOR em 11/09/2026 (F3-CALIBRAR), com a página de
    // calibração e a bancada PARADA::
    //
    //     escreve "5.0%"   →  el.style.width devolve "5%"     (o `.0` some)
    //     escreve "22.0%"  →  el.style.width devolve "22%"
    //     escreve "0.4%"   →  el.style.width devolve "0.4%"    (casa)
    //
    // Com a comparação ANTES da escrita, os dois primeiros nunca casam: o
    // piloto reescrevia a mesma largura e somava +1 **a cada tique, para
    // sempre**, em toda barra cuja largura desse número redondo. E o pior é
    // que ISSO NÃO É SAMBA — o DOM não muta, porque a declaração serializada é
    // a mesma: `--conta-mutacoes 40` dava ZERO com 69 valores por tique. O
    // contador de pinturas é O instrumento com que esta casa prova que um
    // endereço existe, e ele estava inflado sem que a régua do samba pudesse
    // ver.
    //
    // QUEM PAGA: todo eixo de `mesa_viva._barra_bipolar`, que emite
    // `f"{largura:.1f}"` — as barras de giro e acelerômetro da `02-controles`,
    // as da calibração, e qualquer barra futura com uma casa decimal. A cura
    // aqui cobre TODOS os chamadores; curá-la num pacote cobriria um.
    //
    // E ELA TAMBÉM CURA O VALOR INVÁLIDO: uma largura que o CSSOM RECUSA (o
    // travessão de um lugar sem dono, `—%`) não muda nada e agora conta 0, em
    // vez de contar uma pintura que não aconteceu a cada tique.
    if(alvo === 'largura'){
      const antes = el.style.width;
      el.style.width = t + '%';
      return el.style.width === antes ? 0 : 1;
    }
    // O ALVO `altura` — O DÉCIMO PRIMEIRO, e ele é o gêmeo vertical do
    // `largura`. Nasceu em 05/09/2026 para as ONDAS SONORAS da aba 02: as
    // barrinhas do microfone e do alto-falante crescem em `height`, e dos dez
    // alvos que havia nenhum escrevia essa propriedade.
    //
    // POR QUE NÃO O `html` NO CONTÊINER, que era a alternativa e não custava
    // motor nenhum: a régua do mockup lê o alvo `html` **pelo texto visível**
    // (`regua_do_mockup._Leitor`, ramo `alvo in ("fundo", "html")`), e o texto
    // de catorze `<i>` vazios é vazio nos DOIS lados — desenho e produto. As
    // 56 barrinhas ficariam INDECIDÍVEIS para sempre, que é justamente o balde
    // que esta casa passou 02/09 tentando esvaziar. Com `altura` a régua lê
    // `style.height` e decide, exatamente como já decide as barras horizontais.
    //
    // E o `innerHTML` recriaria 56 nós a dez vezes por segundo; este alvo
    // escreve estilo e devolve 0 quando nada mudou, que é o que mantém o
    // contador de pinturas honesto.
    // NÃO SE PINTA O QUE ESTÁ SOB O DEDO DELA — 09/09/2026, e a queixa é dela:
    // *"o slicer do brilho tá super estranho"*, *"oscila, aplica e não aplica"*.
    //
    // O DEFEITO, medido: o trilho do brilho carrega `data-campo="brilho-pct"`
    // com alvo `valor`, e o tique repinta `el.value` dez vezes por segundo com
    // o número que está NO DISCO. Enquanto ela arrasta, o polegar dela vai para
    // 60 e o tique seguinte o devolve para 82 — a cada 100 ms. O gesto só grava
    // no `change`, ou seja no SOLTAR, então o que ela vê durante o arraste é o
    // trilho brigando com o próprio dedo. "Aplica e não aplica" descreve isso
    // com precisão: aplica no soltar, e não aplica no caminho.
    //
    // A CURA É NO MOTOR, e não em cada aba lembrar-se dela — é o mesmo cuidado
    // que a guarda do `<select>` e a do `<input type=range>` sem número já
    // tomam logo abaixo, pela mesma razão: uma aba não pode ter de saber disso.
    //
    // DOIS TESTES, e os dois são necessários: `activeElement` pega o foco (o
    // arraste dá foco, e as setas do teclado também), e `:active` pega o botão
    // do mouse pressionado sobre o elemento. Um sem o outro deixa metade dos
    // caminhos passando.
    //
    // O QUE ISSO CUSTA, declarado: enquanto o foco estiver no controle, um
    // valor que mude POR FORA (o daemon, outro cliente) não aparece ali. É o
    // mal menor — e é o que qualquer campo de formulário faz. Sem o foco, o
    // tique seguinte repinta.
    //
    // ELE NÃO AFETA MEDIÇÃO AUTOMÁTICA: sem ninguém tocando a tela o
    // `activeElement` é o `<body>` e nada casa, então a contagem de pinturas do
    // passeio e das réguas continua a mesma.
    function sob_o_dedo(el){
      try{
        if(el === document.activeElement) return true;
        return !!(el.matches && el.matches(':active'));
      }catch(e){ return false; }
    }
    // O GÊMEO VERTICAL DO `largura`, e ele vai junto pela mesma medição — ver
    // o bloco daquele alvo. Cobrir um e deixar o outro é a correção pela metade
    // que esta casa persegue: a normalização do CSSOM não distingue eixo, e a
    // primeira barra de altura com uma casa decimal repetiria o defeito inteiro.
    if(alvo === 'altura'){
      const antes = el.style.height;
      el.style.height = t + '%';
      return el.style.height === antes ? 0 : 1;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){
      if(sob_o_dedo(el)) return 0;
      // UM <select> SÓ ACEITA O QUE ELE OFERECE, e escrever nele qualquer outra
      // coisa deixa `selectedIndex = -1` e `value = ''` — o campo RENDERIZA EM
      // BRANCO e, como `el.value` nunca volta igual ao que se escreveu, o
      // contador conta uma pintura NOVA a cada tique, para sempre. Um contador
      // que mente é pior que um campo parado, e ele é O instrumento com que esta
      // casa prova que um endereço existe.
      //
      // MEDIDO em 01/09/2026: o lugar VAZIO da mesa (P2, com um controle só)
      // recebe o travessão de `dict.fromkeys(chaves, "—")`, e o `<select>` do
      // teto da vibração ficava em branco somando +1 por tique. A cura é aqui, e
      // não em cada aba lembrar-se dela — é o mesmo cuidado que
      // `interface.conexoes.teto_que_vale` já tomava do lado Python.
      if(el.tagName === 'SELECT'){
        const tem = Array.prototype.some.call(el.options,
                                              function(o){ return o.value === t || o.text === t; });
        if(!tem) return 0;
      }
      // E UM <input type=range> SÓ ACEITA NÚMERO, com um desfecho PIOR que o do
      // `<select>` acima: ele não devolve vazio, ele SANEIA. Escrever o
      // travessão de um valor vazio faz o navegador trocar o `value` pelo meio
      // da escala, o polegar SALTA para um número que ninguém pediu, e como
      // `el.value` nunca volta igual ao que se escreveu o contador soma uma
      // pintura NOVA a cada tique, para sempre — que é o contador com que esta
      // casa prova que um endereço existe.
      //
      // MEDIDO NESTE MOTOR em 05/09/2026, na barra da Navegação (1..12):
      //
      //     sem esta guarda   pintar({"vel-cursor": null})  →  value "7", +1
      //                       de novo, no tique seguinte    →  value "7", +1 …
      //     com esta guarda                                 →  value "6",  0
      //
      // O CASO NÃO É HIPOTÉTICO: `a06_navegacao` emite as duas velocidades como
      // `rato.get("speed")`, e sem o bloco `mouse_emulation` no estado isso é
      // `None`. É o mesmo chão do `<select>` do teto da vibração, medido em
      // 01/09/2026, e a cura é aqui pela mesma razão: uma aba não pode ter de
      // lembrar-se dela — as três barras da Vibração ganham a mesma rede.
      //
      // ZERO É NÚMERO, e por isso a guarda é `isFinite` sobre `Number(t)` e não
      // um teste de vazio — um trilho cujo piso é 0 (as barras de motor da aba
      // Vibração) tem de aceitar o zero que o produto mandou.
      if(el.tagName === 'INPUT' && String(el.type).toLowerCase() === 'range'
         && !isFinite(Number(t))) return 0;
      if(el.value !== t){ el.value = t; return 1; }
      return 0;
    }
    // O ALVO `marcado` — O DÉCIMO, e o único que escreve `el.checked`.
    //
    // A DECISÃO DELA, 04/09/2026: opção **a**, *décimo alvo `marcado`*. O
    // acordeão do alto-falante da aba 02 é um `<input type="checkbox">` em CSS
    // puro, e o estado da saída não tinha como chegar nele: dos nove alvos, o
    // `valor` escreve `el.value` (que num checkbox é a string `"on"`, e não o
    // estado) e nenhum toca a propriedade que decide se ele está marcado.
    //
    // A LÍNGUA É `sim`, e é a mesma do alvo `classe` booleano — que é quem já
    // responde `sim` na leitura de volta (ver `LER_CAMPOS`). Uma segunda palavra
    // para o mesmo "ligado" seria a terceira maneira de dizer a mesma coisa.
    // Vazio, travessão e qualquer outra palavra DESMARCAM: o lugar sem dono da
    // mesa leva `—` (`pacotes.TRAVESSAO`), e um acordeão que abrisse sozinho num
    // lugar vazio seria a tela afirmando o que não é.
    //
    // IDEMPOTENTE COMO OS OUTROS NOVE: compara antes de mexer e devolve 0
    // quando nada mudou. Um alvo que devolve 1 sempre infla a contagem de
    // pinturas de toda aba que o use — e ela é O instrumento com que esta casa
    // prova que um endereço existe.
    //
    // ELE VALE PARA TODO CHECKBOX E RADIO das dez abas. A metade que falta é o
    // ENDEREÇO — o `data-hef-alvo="marcado"` no elemento —, e essa é da frente
    // da aba que o publicar: atributo invisível, zero pixel.
    if(alvo === 'marcado'){
      const querido = (t === 'sim');
      if(sob_o_dedo(el)) return 0;
      if(el.checked === querido) return 0;
      el.checked = querido;
      return 1;
    }
    // O ALVO `html` EXISTE PARA UM BLOCO COM MARCAÇÃO — a dica do `?` do teto
    // da vibração (`aba08.teto_dica`) traz `<b>` e `<code>` no desenho dela, e o
    // `textContent` do ramo padrão escreveria os marcadores como texto literal
    // na tela. Acrescentado em 01/09/2026.
    //
    // POR QUE NÃO O `blocos:` QUE JÁ EXISTE: aquele troca UM elemento por
    // `document.querySelector`, e o `?` do teto é um POR CONTROLE. É o mesmo
    // degrau, um tamanho menor — o endereço é `data-campo`, distribuído.
    //
    // E ELE LEMBRA O QUE ESCREVEU — A-TELA-SAMBA-01, 06/09/2026, pela MESMA
    // razão dos blocos (ver o laço `p.blocos` mais abaixo) e com o mesmo
    // mecanismo dos alvos `cor` e `plastico`. `innerHTML` de volta é a
    // SERIALIZAÇÃO do navegador, não o texto que entrou: a indentação some, o
    // atributo é reescrito com aspas duplas, a entidade vira caractere. Onde
    // uma dessas diferenças existir, `el.innerHTML !== t` é verdade para
    // sempre — e o miolo é recriado dez vezes por segundo com o mesmo desenho.
    // Medido com `--conta-mutacoes 40`, mesa parada: `luz` e `players` na
    // `04-iluminacao` (24 nós por tique) e `adaptadores-tabela` na
    // `08-conexoes`.
    if(alvo === 'html'){
      // O TRAVESSÃO TAMBÉM NÃO ENTRA NUM BLOCO DE HTML — 11/09/2026, e é a
      // irmã da guarda do campo digitável logo acima. O `—` marca VALOR
      // AUSENTE num lugar de leitura: uma coluna sem dado, um slot vazio da
      // mesa. Um alvo `html` não recebe um valor — recebe um PEDAÇO DE PÁGINA
      // já montado, e um pedaço de página vazio é ausência de página, não um
      // valor desconhecido a anunciar.
      //
      // MEDIDO NA ABA LANÇADORES, no mesmo dia em que ela mandou calar os
      // cinco cartões achados: com a frase vazia, os cinco passaram a mostrar
      // um `—` solto no lugar do parágrafo — um travessão anunciando a
      // ausência de uma frase que ela acabara de mandar tirar.
      const h = (v === null || v === undefined || v === '') ? '' : t;
      if(el.__hefHtml === h) return 0;
      if(el.innerHTML !== h){ el.innerHTML = h; el.__hefHtml = h; return 1; }
      el.__hefHtml = h;
      return 0;
    }
    // O ALVO `classe` — o ESTADO, que na tela dela é uma classe e não uma
    // palavra. Ele destrava cinco coisas que a página já desenha e o produto
    // não alcançava: qual dos quatro degraus da Vibração está aceso, o rótulo
    // `Máx` do teto, qual botão de jogador acende na Iluminação, o clique do
    // analógico e a coluna "Ajuste próprio" da Perfis.
    //
    // A SEMÂNTICA, e ela é a que os CINCO pilotos de aba já usavam — só que
    // escrita cinco vezes e nunca no piloto único:
    //
    //     cls(b, 'on', b.dataset.rota === d.alto.rota)      controles_vivos:427
    //     cls(chip, 'on', chip.dataset.mascara === d.mascara)  jogar_vivo:297
    //     cls(b, 'on', p.autostart === true)                  sistema_viva:284
    //
    // Cada elemento do grupo diz QUEM ELE É em `data-hef-quando`, e a classe
    // acende no que casar com o valor pintado. `data-hef-classe` nomeia a
    // classe (`on` por omissão).
    //
    // LIGAR UM DESLIGA AS IRMÃS, e não por lista de irmãs: os quatro degraus
    // compartilham o MESMO `data-campo`, então o `achar()` os visita todos com
    // o mesmo valor e cada um decide por si. Um segundo clique não pode deixar
    // dois acesos porque não há caminho no código em que dois casem — é a
    // diferença entre apagar o vizinho e nunca ter acendido dois.
    //
    // SEM `data-hef-quando` O ALVO É BOOLEANO — o elemento acende por si, que é
    // o caso do rótulo `Máx` e da coluna "Ajuste próprio".
    //
    // IDEMPOTENTE: compara antes de mexer e devolve 0 quando nada mudou. O
    // `cls()` dos pilotos velhos devolvia 1 SEMPRE, e um alvo assim infla a
    // contagem de pinturas de toda aba que o use — que é o instrumento com que
    // esta casa prova que um endereço existe.
    // E ELE VESTE UM ATRIBUTO JUNTO, quando o elemento pedir — 04/09/2026, e a
    // dívida foi achada pela frente da FOLHA no dia em que ela construiu o botão
    // cinza (S-03): *"nenhum alvo do `hefesto_vivo.py` escreve atributo E classe
    // no mesmo elemento, e o `aria-disabled` do botão cinza precisa disso"*.
    //
    // O PROBLEMA É REAL E É DE FORMA: `data-hef-alvo` é UM por elemento, e um
    // botão que fica cinza precisa das duas metades ao mesmo tempo — a classe,
    // que é o que a folha pinta, e o `aria-disabled`, que é o que um leitor de
    // tela anuncia. Sem as duas, ou o botão fica cinza sem dizer por quê a quem
    // não vê, ou diz e não fica cinza.
    //
    // POR QUE NÃO UM ALVO COMPOSTO, nem um segundo `data-campo`: alvo composto
    // quebraria tudo que LÊ o alvo por igualdade (o `LER_CAMPOS` aqui embaixo,
    // o `regua_do_mockup._campo`, os `campo.alvo == "…"`), e o comentário do
    // alvo `atributo` já paga essa lição. Dois endereços para o mesmo fato seria
    // pior: dois campos que podem DIVERGIR na tela, e a casa persegue o oposto.
    //
    // A VERDADE É UMA SÓ e ela mora na classe; o atributo é DERIVADO dela, na
    // língua do ARIA (`true`/`false`, que é o que a especificação exige — um
    // `aria-disabled` ausente e um `aria-disabled="false"` NÃO são a mesma coisa
    // para um leitor de tela). O nome vem do MESMO `data-hef-atributo` que o alvo
    // `atributo` já usa, e passa pela MESMA guarda: `aria-*` entra, `data-hef` e
    // o vocabulário de endereço não.
    //
    // A LEITURA DE VOLTA CONTINUA LENDO A CLASSE, de propósito: um endereço, uma
    // leitura. O atributo não é um segundo campo a medir — é a mesma verdade
    // dita para quem não enxerga a cor.
    if(alvo === 'classe'){
      const c = el.dataset.hefClasse || 'on';
      const quando = el.dataset.hefQuando;
      const aceso = (quando === undefined || quando === '') ? ligado(t) : (t === quando);
      let n = 0;
      const junto = (el.dataset.hefAtributo || '').trim().toLowerCase();
      if(junto && atributo_escrevivel(junto)){
        const querido = aceso ? 'true' : 'false';
        if(el.getAttribute(junto) !== querido){
          el.setAttribute(junto, querido);
          n += 1;
        }
      }
      if(el.classList.contains(c) === aceso) return n;
      el.classList.toggle(c, aceso);
      return n + 1;
    }
    // O ALVO `cor` — o `color` do elemento, e ele é o par que faltava do
    // `fundo`. O clique do analógico é COR na GTK
    // (`interface/cartao_do_controle.py`, "accent do CONTROLE quando
    // pressionados") e era cor no piloto velho desta aba
    // (`interface/controles_vivos.py:327`,
    // `{color: s.on ? 'var(--plastico)' : ''}`). Sem este alvo, o pacote da
    // aba Controles teve de escrever `[L3]` em TEXTO e deixou a razão escrita
    // em `a02_controles.py:63` — *"enquanto o piloto não tiver o alvo, o texto
    // é o canal honesto"*. Agora tem.
    //
    // ESCREVE E DEPOIS COMPARA, ao contrário dos outros alvos, e é a única
    // forma de ser idempotente aqui: o CSSOM NORMALIZA na atribuição
    // (`#6272a4` volta `rgb(98, 114, 164)` — medido no WebKit desta máquina em
    // 02/09/2026), então comparar o que se vai escrever com o que está escrito
    // acusaria mudança em TODO tique. De quebra, uma cor inválida é recusada
    // pelo CSSOM sem mexer no valor antigo, e isto devolve 0 — em vez de somar
    // uma pintura que não aconteceu.
    //
    // VAZIO APAGA a cor de linha, devolvendo o elemento à folha de estilo. É o
    // que o piloto velho fazia com `''`, e é o que faz um analógico solto
    // voltar à cor de sempre em vez de ficar aceso para sempre.
    //
    // E ESCREVER O MESMO VALOR AQUI NÃO É MUTAÇÃO — MEDIDO em 06/09/2026, na
    // A-TELA-SAMBA-01, e o resultado DERRUBOU a hipótese da sprint.
    //
    // Ela dizia que este ramo era um dos três culpados do samba, por escrever
    // antes de comparar. Escrever antes de comparar ele escreve; o que não
    // acontece é a mutação: o CSSOM só reescreve o atributo `style` quando a
    // DECLARAÇÃO muda, e atribuir a mesma cor não muda declaração nenhuma.
    // Com o observador ligado por 100 tiques e a mesa parada, este ramo não
    // produziu **uma** mutação em nenhuma das dez abas — o que a tabela acusava
    // nos elementos de cor era o SELO da visita, que é outro ramo e foi curado.
    //
    // Por isso a forma FICA como estava. Uma memória de elemento aqui — a que
    // os alvos `html` e os blocos ganharam, onde ela cura de verdade — passaria
    // por cura e não curaria nada, e a régua que a guardasse ficaria verde com
    // ela arrancada. `test_a_cor_e_o_plastico_repetidos_nao_mutam` guarda o
    // CONTRATO (o dia em que alguém trocar o CSSOM por um `setAttribute`
    // direto no `style`, ela reprova), e o docstring dela diz isso.
    if(alvo === 'cor'){
      const antes = el.style.color;
      el.style.color = vazio ? '' : t;
      return el.style.color === antes ? 0 : 1;
    }
    // O ALVO `plastico` — A COR DO APARELHO COMO VARIÁVEL, e é o que a lei de
    // 03/09/2026 pede com todas as letras: *"se identificou o controle como
    // modelo White a cor do card em volta tem que ser branco"*.
    //
    // POR QUE NÃO O `cor` NEM O `fundo`: `--plastico` não pinta UM elemento —
    // ele governa a borda da moldura E o halo do lado que treme, que é um
    // descendente. Escrever `color` obrigaria toda a coluna a herdar o tom do
    // plástico, e `background` pintaria o retângulo inteiro. Uma variável de
    // CSS é exatamente o mecanismo que o desenho já usa (`var(--plastico)` nas
    // dez páginas): o que faltava era o produto poder escrevê-la.
    //
    // VAZIO E TRAVESSÃO APAGAM — e os dois entram porque chegam por caminhos
    // diferentes: `""` é a cor que o aparelho não respondeu (pelo rádio o mapa
    // diz que ela não se lê), e `—` é o que o molde escreve num lugar sem dono
    // (`pacotes.TRAVESSAO`). Apagar devolve a borda ao tom neutro da folha de
    // estilo (`var(--plastico, …)`) em vez de deixar a cor do MOCKUP na tela —
    // regra dela: campo sem informação não mostra nada. Escrever `—` numa
    // variável usada em `border` deixaria a declaração inválida no cálculo e a
    // borda sumiria de vez.
    //
    // ESCREVE E DEPOIS COMPARA, como o `cor`: uma propriedade personalizada
    // aceita qualquer texto, então só a releitura diz se algo mudou — e é isso
    // que impede o contador de somar uma pintura que não aconteceu.
    //
    // E ELE TAMBÉM NÃO MUTA AO REPETIR — ver a nota do alvo `cor` logo acima,
    // que é a mesma medição de 06/09/2026 e a mesma hipótese derrubada:
    // `setProperty` com o mesmo valor e `removeProperty` do que já não está lá
    // não reescrevem o atributo `style`, e o observador não conta nada.
    if(alvo === 'plastico'){
      const antes = el.style.getPropertyValue('--plastico');
      if(vazio || t === '—'){ el.style.removeProperty('--plastico'); }
      else { el.style.setProperty('--plastico', t); }
      return el.style.getPropertyValue('--plastico') === antes ? 0 : 1;
    }
    // O ALVO `posicao` — ONDE O PONTINHO ESTÁ, e ele não reescreve folha
    // nenhuma. A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01, 25/09/2026.
    //
    // O valor é `x,y` em por cento, e o alvo escreve só `--hef-x` e `--hef-y`
    // no próprio elemento. Quem os usa é a regra da página,
    // `left:var(--hef-x,50.2%);top:var(--hef-y,50.2%)`. Antes, a posição era
    // uma folha endereçada trocada inteira a cada tique: o WebKit refazia o
    // estilo das 1.955 peças da 02 e repintava a janela toda, dez vezes por
    // segundo (37,7% de um núcleo contra 1,13% por aqui, na banca).
    //
    // O VAZIO E O TRAVESSÃO TIRAM AS DUAS VARIÁVEIS, e o pontinho volta ao
    // REPOUSO do `var()`. É o que o lugar vazio mostrava pelo piso da folha, e
    // `--hef-x:—` invalidaria a regra. Apagar o que já não está lá conta 0.
    if(alvo === 'posicao'){
      const ax = el.style.getPropertyValue('--hef-x').trim();
      const ay = el.style.getPropertyValue('--hef-y').trim();
      const xy = (vazio || t === '—') ? [] : t.split(',');
      if(xy.length !== 2){
        if(!ax && !ay) return 0;
        el.style.removeProperty('--hef-x');
        el.style.removeProperty('--hef-y');
        return 1;
      }
      const x = xy[0].trim() + '%';
      const y = xy[1].trim() + '%';
      let mudou = 0;
      if(ax !== x){ el.style.setProperty('--hef-x', x); mudou = 1; }
      if(ay !== y){ el.style.setProperty('--hef-y', y); mudou = 1; }
      return mudou;
    }
    // O ALVO `atributo` — UM ATRIBUTO DA TAG, e é o que faltava para o desenho
    // do controle seguir o aparelho. A lei dela, 03/09/2026: *"os svgs do
    // dualsense (…) mudam de acordo com o controle identificado no canto
    // superior. É white no p1, mas (…) os svgs não são os que o meu mapa
    // cataloga. Isso tá errado."*
    //
    // O SVG ESCOLHE A COR POR ATRIBUTO: o `monta.svg()` grava
    // `<svg data-colorway="cosmic-red">` e a folha embutida pinta as dez zonas
    // com `svg[data-colorway="…"] .z-casca{fill:var(--z-casca)}`. Havia 181
    // `data-colorway` nas dez páginas publicadas e NENHUM alcançável: dos oito
    // alvos do `escrever()`, nenhum escrevia atributo. A aba 08 desistiu com a
    // razão escrita no próprio HTML publicado (`08-conexoes.html:1033`) —
    // *"a cura certa é um alvo de atributo no piloto"*. É este.
    //
    // O NOME VEM DE `data-hef-atributo`, E NÃO DE UM `data-hef-alvo`
    // COMPOSTO. `atributo:data-colorway` no `data-hef-alvo` seria mais curto de
    // escrever e quebraria tudo que LÊ o alvo: `regua_do_mockup._campo`, o
    // `LER_CAMPOS` aqui embaixo e cada `campo.alvo == "…"` comparam o alvo por
    // IGUALDADE, e um alvo composto viraria 181 palavras diferentes onde hoje
    // há oito. O par alvo/parâmetro em atributos separados é o que o alvo
    // `classe` já faz com `data-hef-classe` e `data-hef-quando` — a casa tem a
    // forma, e inventar uma segunda seria a terceira maneira de dizer o mesmo.
    //
    // VAZIO E TRAVESSÃO APAGAM O ATRIBUTO, e a razão foi MEDIDA antes de
    // escolhida. Sem `data-colorway` nenhuma regra da folha casa, e o desenho
    // cai nos `fill` crus do `ds_limpo.svg`: 62 formas em `#3a3f4b` — um cinza
    // neutro, com o contorno intacto. Não é um SVG quebrado nem invisível: é o
    // controle SEM identidade, que é exatamente o que a regra dela pede quando
    // não há informação. Deixar o atributo faria o contrário — manteria na tela
    // o colorway do MOCKUP sobre um aparelho que é outro, que é o defeito que
    // este alvo nasceu para curar.
    //
    // ESCREVE E DEPOIS RELÊ, como o `cor` e o `plastico`: um atributo aceita
    // qualquer texto, então só a releitura diz se algo mudou. `getAttribute`
    // devolve `null` quando não há atributo, e `null === null` conta 0 — que é o
    // que impede o contador de somar uma pintura que não aconteceu ao apagar o
    // que já estava apagado.
    //
    // ELE É NECESSÁRIO E NÃO É SUFICIENTE, e quem for ligar uma aba precisa
    // saber: `monta._so_o_colorway` guarda na folha de cada SVG **só as regras
    // do modelo pedido** — 3.082 bytes dos 45.452 dos 28. Escrever aqui um
    // colorway que não está embutido dá o MESMO cinza do atributo apagado. Ou o
    // `monta.svg()` deixa de podar, ou a página publica a folha inteira uma vez.
    if(alvo === 'atributo'){
      const nome = (el.dataset.hefAtributo || '').trim().toLowerCase();
      // NOME RECUSADO NÃO PINTA E NÃO MENTE. O selo já foi carimbado acima, mas
      // a tela continua mostrando o valor velho e o pacote continua declarando
      // outro — então a régua do mockup acusa este endereço, que é o barulho
      // certo para um `data-hef-atributo` mal escrito.
      if(!atributo_escrevivel(nome)) return 0;
      // A DICA QUE ESTÁ SOB O PONTEIRO NÃO MORA MAIS NO `title` — TOOLTIP-C1,
      // 11/09/2026. A camada da dica (`DICA_DA_CASA`) guarda o texto em
      // `data-hef-dica` enquanto o ponteiro está em cima, justamente para o
      // popup do sistema não aparecer junto. Escrever `title` aqui
      // ressuscitaria esse popup NO MEIO da dica aberta — os dois na tela, um
      // por cima do outro.
      //
      // ENTÃO O ALVO SEGUE O TEXTO até onde ele está, e avisa a camada para a
      // dica aberta trocar de frase no mesmo tique. Fora da hover não há
      // `data-hef-dica` e este ramo não existe: o `title` é escrito como
      // sempre foi.
      //
      // O VAZIO APAGA DOS DOIS LADOS, como o ramo de baixo: uma dica sem texto
      // é dica que não existe, e deixar um travessão ali seria a tela
      // explicando um botão com um traço.
      if(nome === 'title' && el.hasAttribute('data-hef-dica')){
        const dica = (vazio || t === '—') ? '' : t;
        if(el.getAttribute('data-hef-dica') === dica) return 0;
        if(dica === ''){ el.removeAttribute('data-hef-dica'); }
        else { el.setAttribute('data-hef-dica', dica); }
        if(window.__hefDica) window.__hefDica.trocar(el, dica);
        return 1;
      }
      const antes = el.getAttribute(nome);
      // COMPARA ANTES DE ESCREVER — A-TELA-SAMBA-01, 06/09/2026, e é a cura do
      // *"algo ativa o tooltip mas ele se desativa"* que ela escreveu com o
      // produto aberto.
      //
      // O RAMO ESCREVIA E DEPOIS RELIA, e o comentário acima explica por quê:
      // um atributo aceita qualquer texto, então só a releitura diria se algo
      // mudou. **A premissa é falsa para um atributo comum**: `setAttribute`
      // não normaliza nada, e `getAttribute` devolve exatamente a string que
      // entrou — logo comparar ANTES dá a mesma resposta sem tocar no DOM.
      //
      // E TOCAR NO DOM ERA O DEFEITO INTEIRO. `setAttribute` com o mesmo valor
      // enfileira um `MutationRecord` na mesma medida que um valor novo, e a
      // DICA NATIVA do WebKit fecha quando o `title` do elemento sob o cursor
      // muda. As dicas vivas desta casa — os `dica-modo-*` da `03-gatilhos`, o
      // `title` do Salvar e do Exportar em todas as dez — passavam por aqui
      // DEZ VEZES POR SEGUNDO: a dica abria e morria antes de ela conseguir
      // ler. Medido com `--conta-mutacoes 100`, mesa parada, na `03-gatilhos`:
      // 1.200 trocas de `title` em 100 tiques, com o texto sempre igual.
      //
      // O `null` DO `getAttribute` É O VAZIO DESTE RAMO, e por isso a
      // comparação do apagamento é contra ele: apagar o que já não existe volta
      // 0 e não escreve, como antes.
      if(vazio || t === '—'){
        if(antes === null) return 0;
        el.removeAttribute(nome);
        return 1;
      }
      if(antes === t) return 0;
      el.setAttribute(nome, t);
      return el.getAttribute(nome) === antes ? 0 : 1;
    }
    // O TEXTO IGUAL COM MARCAÇÃO POR DENTRO TAMBÉM SE ESCREVE — 21/09/2026. O
    // rótulo do lugar que NASCE vazio vem do desenho como `P3 <span
    // class="pt">•</span> Desconectado`; o `textContent` dele é igual ao que o
    // pacote manda, e a comparação sozinha o deixava como estava. Numa caixa
    // `flex` os espaços em volta do `<span>` somem, e a tela dizia
    // `P3•Desconectado` ao lado de um `P1 • Desconectado` — ela viu: *"p1,p2
    // tão diferentes do p3 e p4"*. Escrever uma vez deixa os quatro com a
    // mesma forma.
    //
    // SÓ QUANDO OS FILHOS SÃO O SEPARADOR, e nenhum outro: o `.pt` é o único
    // filho que o texto devolve inteiro (o `•` está na string). Qualquer outro
    // — a bolinha de quem navega, um endereço, um botão — o texto apagaria e
    // não devolveria, que é o defeito que `enderecos_que_o_texto_apaga` guarda.
    const so_o_ponto = !!el.firstElementChild
      && Array.prototype.every.call(el.children, function(f){
           return f.classList.contains('pt') && !f.firstElementChild; });
    if(el.textContent !== t || so_o_ponto){
      el.textContent = t;
      // O PAINEL QUE MOSTRA O FIM. Um registro tem ordem: o que acabou de
      // acontecer é a última linha, e um painel de seis linhas que abre nas
      // seis PRIMEIRAS de oitenta mostra o mais velho — inútil para quem
      // clicou "Ver detalhes" agora. Fotografado em 01/09/2026.
      //
      // É UM ATRIBUTO, e não uma regra geral por altura: rolar todo elemento
      // que transborde mexeria em painéis onde o começo é o que importa.
      if(el.dataset.hefRolar === 'fim'){ el.scrollTop = el.scrollHeight; }
      return 1;
    }
    return 0;
  }
  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO, e nenhum se aposenta. Medido em
  // 01/09/2026, nas dez páginas publicadas:
  //
  //     data-campo   oito abas          o mais novo, e o do piloto único
  //     data-papel   só a Vibração (28) um PAR com `data-lado`
  //     data-hef     só a Perfis (77)   nomes com ponto: `perfis.linha.nome`
  //
  // Cada um nasceu com o piloto da sua aba, e os pilotos ainda os usam. Trocar
  // tudo por um só renomearia 105 endereços e quebraria cinco pilotos vivos
  // para ganhar consistência de nome — o piloto único aceita os três, que é o
  // que custa uma linha aqui.
  function achar(raiz, chave){
    const esc = chave.replace(/"/g, '\\"');
    return raiz.querySelectorAll(
      '[data-campo="' + esc + '"],[data-papel="' + esc + '"],[data-hef="' + esc + '"]');
  }
  // O RECADO NA TELA SAIU — 13/09/2026, FRASES-E-DICAS-01.
  //
  // Aqui moravam `pintar_recados` e os quatro estilos dele (a cara do aviso, a
  // cor do sucesso, a tarja de rodapé e o recado na grade). Era o canal que
  // levava a frase de um gesto ao CARTÃO do controle: nasceu em 02/09/2026
  // porque `RuntimeError` era *"o produto recusou, e a frase VAI PARA A TELA"*,
  // e a recusa saía só no terminal de quem lançou a janela.
  //
  // O CONTRATO CADUCOU EM DUAS METADES. O sucesso saiu na TELA-CALADA-01 (*"em
  // todas as abas da interface"*); a recusa saiu na FRASES-E-DICAS-01, com a
  // foto da caixa laranja que o `player` da aba 04 pousava no cartão (o índice
  // da leva, `2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`, linha 19). O defeito
  // de origem continua curado por outra peça: o clique recusado não responde
  // calado — ele pisca no botão (ver `voltouDoVoo`), e a frase fica no diário.
  //
  // O QUE A MEDIÇÃO DE 04/09 ENSINOU FICA VALENDO para quem um dia desenhar um
  // nó dentro de um cartão: num `[data-controle]` de linhas fixas (grid ou
  // flex), um filho inserido pela ORDEM ocupa uma célula e desloca a coluna
  // inteira — 65 px no desenho da aba 05.
  // O ESTADO "EM VOO" DO BOTÃO — decisão dela, `09` [03], 04/09/2026: **o botão
  // diz que está trabalhando**, e diz DURANTE a espera, no lugar exato do
  // clique.
  //
  // O DEFEITO MEDIDO: `daemon.reload` leva **9,5 segundos** (medido no daemon
  // dela em 01/09), o gesto corre em thread para a janela não congelar, e
  // NENHUMA das dez abas tinha estado "em voo" — o clique sumia por nove
  // segundos e meio e o segundo clique parecia o primeiro. É o mesmo enunciado
  // da recusa que ia para o terminal, um degrau antes: ali a resposta existia e
  // não chegava; aqui a ESPERA não tinha como se anunciar.
  //
  // AS DUAS METADES, e a segunda é opcional de propósito:
  //
  //   a CLASSE `hef-em-voo`   sempre. Mora na folha do módulo
  //                           (`interface/janela.FOLHA_DA_CASA`), vale nas dez
  //                           abas sem republicar desenho, e não inventa texto.
  //   `data-hef-em-voo="…"`   quando a página publica um rótulo, ele entra no
  //                           lugar do original — *"Reaplicando…"* na `09`. O
  //                           texto continua sendo dela; o piloto só o troca.
  //
  // O ORIGINAL VOLTA INTEIRO, e por isso ele é guardado como `innerHTML` num
  // mapa, e não como texto num `data-`: os botões desta casa têm `<span>` dentro
  // (o `.pt` da fita, os ícones), e devolver `textContent` os achataria — o
  // botão voltaria da espera diferente de como entrou.
  window.__hef.voo = 0;
  window.__hef.rotulos = {};
  function em_voo(el){
    const n = String(++window.__hef.voo);
    el.setAttribute('data-hef-voo', n);
    el.classList.add('hef-em-voo');
    const dito = el.dataset.hefEmVoo;
    if(dito){
      window.__hef.rotulos[n] = el.innerHTML;
      el.textContent = dito;
    }
    return n;
  }
  // E ELE VOLTA SOZINHO. Um botão que ficasse "trabalhando" para sempre é pior
  // que um botão calado: o calado ao menos não afirma nada.
  //
  // O `querySelectorAll` E NÃO UMA REFERÊNCIA GUARDADA: entre o clique e a
  // volta, a pintura pode ter trocado o bloco inteiro (a fita, a tabela de
  // perfis, o mapa do gabinete). Uma referência apontaria para um nó que já saiu
  // do documento, e o botão que está na tela ficaria em voo para sempre. Zero
  // elementos é a resposta certa nesse caso, e o rótulo guardado é jogado fora
  // junto — senão o mapa cresce a cada gesto, para sempre.
  //
  // E O POUSO PISCA — 05/09/2026, decisão dela na `03-Q4`, e desde 13/09/2026
  // em DUAS CORES (FRASES-E-DICAS-01). O `certo` chega do `finally` do piloto,
  // que é quem sabe qual dos desfechos aconteceu; o JS não adivinha:
  //
  //   true     aplicou              `hef-deu-certo`, a borda verde
  //   false    recusou, ou sem dono `hef-recusou`, a borda de aviso
  //   outro    só armou, ou quem    nenhuma piscada: o botão só volta do voo
  //            chama sem dizer      (`voltouDoVoo(n)` à mão, numa régua)
  //
  // A RECUSA PISCA EM VEZ DE FALAR: a frase que ia ao cartão saiu da tela, e o
  // botão é o único lugar em que a resposta ao clique mora sem texto. O `false`
  // é ESTRITO de propósito — um `undefined` que acendesse a recusa faria toda
  // régua que chama `voltouDoVoo(n)` medir uma recusa que não houve.
  //
  // UMA ACENDE, A OUTRA APAGA: dois cliques no mesmo botão dentro de um segundo
  // e meio, um que aplicou e outro que recusou, não podem deixar as duas bordas
  // vestidas — a tela diria as duas coisas sobre o mesmo campo.
  //
  // A CLASSE SAI SOZINHA em MS_DA_PISCADA, e o número é dela (*"cerca de um
  // segundo e meio"*). Um campo que ficasse aceso para sempre afirmaria um
  // clique de dez minutos atrás — a mesma doença do botão que fica em voo, que
  // este arquivo já nomeia acima.
  //
  // O `data-hef-voo` SAI ANTES DA PISCADA, e a ordem importa: se ele ficasse
  // até a classe apagar, o pouso seguinte acharia dois elementos com o mesmo
  // número. Por isso a retirada agendada procura pela CLASSE, não pelo número.
  window.__hef.voltouDoVoo = function(n, certo){
    const chave = String(n);
    const acende = certo === true ? 'hef-deu-certo'
      : (certo === false ? 'hef-recusou' : '');
    const apaga = acende === 'hef-deu-certo' ? 'hef-recusou' : 'hef-deu-certo';
    let k = 0;
    const piscando = [];
    for(const el of document.querySelectorAll('[data-hef-voo="' + chave + '"]')){
      el.classList.remove('hef-em-voo');
      if(window.__hef.rotulos[chave] !== undefined){
        el.innerHTML = window.__hef.rotulos[chave];
      }
      el.removeAttribute('data-hef-voo');
      if(acende){ el.classList.remove(apaga); el.classList.add(acende); piscando.push(el); }
      k += 1;
    }
    delete window.__hef.rotulos[chave];
    if(piscando.length){
      setTimeout(function(){
        for(const el of piscando){ el.classList.remove(acende); }
      }, 1500);  // MS_DA_PISCADA — ver o portão logo abaixo do BOOTSTRAP
    }
    return k;
  };
  window.__hef.pintar = function(p){
    let n = 0;
    // A DICA CONFERE O PRÓPRIO ALVO ANTES DE O TIQUE MEXER NA PÁGINA —
    // TOOLTIP-C1, 11/09/2026. Um bloco trocado inteiro leva embora o nó em que
    // a dica está pousada, e uma dica aberta sobre um nó que saiu do documento
    // é a tela afirmando o que já não existe. Ela NÃO conta como pintura: não
    // há pixel do produto aqui, e um contador que subisse a cada tique faria
    // toda aba parecer inquieta — a quietude é o que aquele número mede.
    if(window.__hefDica) window.__hefDica.varrer();
    // O ALVO QUE A FITA ESCOLHEU. Ele NÃO conta como pintura — não há pixel
    // aqui —, e por isso `n` não sobe: um contador que subisse a cada tique
    // faria toda aba parecer inquieta, e a quietude é o que este número mede.
    //
    // ELE É REESCRITO EM TODO TIQUE de propósito: `window.__hef` morre com o
    // documento, e sem isto a escolha dela sobreviveria no Python e sumiria da
    // página na primeira troca de aba — o alvo voltaria a ser vazio sem que
    // nada na tela mudasse.
    if('alvo' in p){ window.__hef.alvoPadrao = p.alvo || ''; }
    // A FITA SE TROCA INTEIRA, e não campo a campo: o número de chips muda com
    // a mesa, e não há endereço para um chip que ainda não existe.
    if(p.fita){
      const f = document.querySelector('.fita');
      if(f){
        // O SELO SAI DA COMPARAÇÃO, e sem isto a fita se trocava A CADA TIQUE.
        // Medido em 03/09/2026: o laço abaixo escreve `data-hef-visto` nos
        // chips, o `outerHTML` do DOM passa a trazer o atributo, o texto que o
        // Python emitiu nunca o traz — e a igualdade nunca mais casava. Treze
        // tiques, treze pinturas, com a mesa parada. Um contador que mente é
        // pior que um campo parado: é O instrumento com que esta casa prova que
        // um endereço existe.
        // A INDENTAÇÃO SAI DOS DOIS LADOS, e sem isto a comparação NUNCA casa:
        // `monta.fita()` devolve o bloco com os quatro espaços com que ele
        // entra no esqueleto (`f'    <div class="fita…'`), e `outerHTML` começa
        // no `<`. Medido em 03/09/2026: treze tiques, treze trocas da fita
        // inteira, com a mesa parada — e cada troca deixava mais um nó de texto
        // de quatro espaços ao lado dela, porque `outerHTML =` insere o
        // fragmento inteiro, espaço e tudo.
        //
        // O DEFEITO É VELHO E ESTAVA DORMINDO: até hoje `_fita` devolvia `""`
        // sempre que UM controle não tinha cor — e pelo rádio nenhum tem —,
        // então o ramo quase nunca corria na mesa dela. Curar a guarda acordou
        // o contador.
        // E NUNCA COM UM CHIP EM VOO DENTRO — A-TELA-SAMBA-01, 06/09/2026, e é
        // o mesmo cuidado do laço de blocos lá embaixo, aqui no caso mais
        // extremo dele: a fita não troca o MIOLO, ela troca o próprio nó
        // (`outerHTML`), então TUDO o que está dentro dela morre junto. Os
        // chips da fita são clicáveis — são eles que escolhem o alvo —, e um
        // chip clicado veste `hef-em-voo` até o gesto responder. Sem esta
        // guarda, um chip em voo desaparece no primeiro tique, com o clique
        // dela no meio do caminho.
        const desejado = String(p.fita).trim();
        const agora = f.outerHTML.split(' data-hef-visto="1"').join('');
        // A MEMÓRIA DO QUE ESTE LAÇO ESCREVEU, e ela é a única comparação que
        // sobrevive à camada da dica — TOOLTIP-C1, 11/09/2026.
        //
        // O DEFEITO MEDIDO: a `DICA_DA_CASA` colhe o `title` de todo elemento
        // para `data-hef-dica`, e a fita tem dois (a tarja e o chip). O
        // `outerHTML` passa a trazer um atributo com outro NOME e em outra
        // POSIÇÃO — `removeAttribute` + `setAttribute` mandam o atributo para o
        // fim da tag —, e o texto que o Python emitiu nunca vai casar com isso.
        // Sem esta memória a fita se trocava inteira DEZ VEZES POR SEGUNDO, com
        // a mesa parada: é o defeito de 03/09 de volta, com outra causa.
        //
        // É O MESMO REMÉDIO DOS BLOCOS (`alvo.__hefBloco`, três passos abaixo),
        // com uma diferença de forma: a fita se troca por `outerHTML`, ou seja
        // o NÓ morre a cada troca e uma memória pendurada nele morreria junto.
        // Por isso ela mora em `window.__hef`, que vive enquanto o documento.
        //
        // A COMPARAÇÃO VELHA FICA AO LADO, e não é redundância: no primeiro
        // tique de cada carga não há memória nenhuma, e é ela que impede a
        // primeira troca inútil enquanto a colheita ainda não aconteceu.
        if(window.__hef.fitaEscrita === desejado){ /* já é esta */ }
        else if(agora === desejado){ window.__hef.fitaEscrita = desejado; }
        else if(f.querySelector('.hef-em-voo') || f.closest('.hef-em-voo')){
          window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
        } else {
          f.outerHTML = desejado; n += 1;
          window.__hef.fitaEscrita = desejado;
        }
        // O SELO DA VISITA NOS CHIPS, e sem ele o endereço deles pareceria
        // MORTO. Os chips ganharam `data-campo` em 03/09/2026 (`monta.fita`)
        // para que a régua da identidade saiba que ali não há desenho
        // congelado — mas quem os escreve é esta troca de bloco, e não o laço
        // de campos: sem o selo, a régua do mockup os contaria como endereço
        // que ninguém pinta. Ele é escrito a cada tique, mesmo quando o HTML
        // não mudou, porque é a visita SEM mudança que não deixa rastro.
        // UMA VEZ SÓ, pela mesma razão do selo em `escrever()`: reescrever `'1'`
        // sobre `'1'` é uma mutação de DOM, e o chip da fita é clicável.
        for(const c of document.querySelectorAll('.fita [data-campo]')){
          if(c.dataset.hefVisto !== '1'){ c.dataset.hefVisto = '1'; }
        }
      }
    }
    // OS BLOCOS QUE SE TROCAM INTEIROS, e a fita acima é o primeiro deles —
    // esta é a mesma ideia, com endereço. Um bloco cujo NÚMERO DE FILHOS muda
    // com o dado não tem como ser pintado campo a campo: não há endereço para
    // um filho que ainda não existe.
    //
    // O SEGUNDO CASO É O MAPA DO GABINETE (01/09/2026): as faces e as entradas
    // são as que ELA declarou, e podem ser zero. Enquanto o bloco era estático,
    // a aba mostrava um gabinete de bancada — e os seis botões que mexem no
    // mapa não podiam ser ligados, porque clicar declararia no disco dela o
    // desenho de um exemplo.
    //
    // TROCA O MIOLO, e não o próprio nó: `outerHTML` no container mataria o
    // elemento que o seletor achou, e a próxima pintura não teria onde pousar.
    //
    // E NUNCA COM UM BOTÃO EM VOO DENTRO — A-TELA-SAMBA-01, 06/09/2026, e é a
    // cura de *"botões não funcionam"* e *"cliques não aplicam ou atrasam"*.
    //
    // O DEFEITO É DE TEMPO, e por isso régua nenhuma o via numa foto: um bloco
    // cujo HTML carregue um valor que muda a cada tique (uma contagem, uma
    // bateria, uma hora) é reconstruído DEZ VEZES POR SEGUNDO, e `innerHTML =`
    // destrói todos os descendentes. Quem clicou fica com o `mousedown` num nó
    // que já não existe — o `click` nunca completa — e o `hef-em-voo`, que é a
    // única coisa na tela dizendo *"estou trabalhando"*, some com o nó que o
    // vestia. Um gesto lento desta casa leva 9,5 s (`daemon.reload`): são 95
    // chances de o botão ser arrancado debaixo do dedo dela.
    //
    // ADIAR É A RESPOSTA CERTA, e não "trocar só o pedaço que mudou": o HTML do
    // bloco vem pronto do pacote, e casar filho a filho aqui seria escrever um
    // segundo motor de reconciliação no piloto. O voo dura o gesto; assim que
    // ele pousa, o tique seguinte aplica o bloco inteiro. O que se perde é
    // atualização de UM bloco por alguns tiques; o que se ganha é o clique.
    //
    // O CONTADOR SAI NA TABELA do `--conta-mutacoes`: um bloco que fica adiado
    // para sempre é defeito, e sem contá-lo ele seria invisível.
    // E A COMPARAÇÃO É COM O QUE ESTE LAÇO ESCREVEU, não com o `innerHTML` de
    // agora — A-TELA-SAMBA-01, 06/09/2026, e é o que fazia CINCO abas
    // reconstruírem bloco a dez vezes por segundo com a mesa parada.
    //
    // O DEFEITO É UM CICLO, e ele se fecha DENTRO do mesmo tique: o bloco entra
    // com os endereços que o pacote desenhou; o laço de campos, três passos
    // abaixo, escreve nesses endereços e carimba `data-hef-visto` em cada um;
    // o `innerHTML` do bloco passa a trazer o selo, o texto que o Python emitiu
    // nunca o traz — e a igualdade nunca mais casa. No tique seguinte o bloco é
    // reconstruído inteiro, os selos somem com os nós, e recomeça.
    //
    // **É O MESMO DEFEITO QUE A FITA JÁ TINHA MEDIDO** três dias antes (ver o
    // `split(' data-hef-visto="1"')` logo acima) — e a cura de lá nunca foi
    // trazida para cá. Medido com `--conta-mutacoes 40`, mesa parada:
    //
    //     10-perfis    4.000 mutações em 40 tiques — a lista dos 33 perfis
    //                  inteira, 132 nós por tique, dez vezes por segundo
    //     04-iluminacao  a barra de luz e os players, 24 nós por tique
    //     08-conexoes    a tabela de adaptadores
    //
    // POR QUE A MEMÓRIA E NÃO O `split` DA FITA: o selo é UM dos jeitos de o
    // DOM divergir do texto emitido, e não o único — o CSSOM normaliza cor, um
    // `style` esvaziado deixa `style=""` na tag, e o próximo alvo que nascer
    // trará a sua. Guardar o que ESTE laço escreveu compara duas strings da
    // MESMA língua e fica imune a todas elas de uma vez. É a mesma memória de
    // elemento dos alvos `cor` e `plastico`, e morre com o nó pelo mesmo
    // motivo.
    for(const [seletor, html] of Object.entries(p.blocos || {})){
      const alvo = document.querySelector(seletor);
      if(!alvo) continue;
      if(alvo.__hefBloco === html) continue;
      // A MEMÓRIA SE ESCREVE TAMBÉM QUANDO NADA PRECISOU MUDAR — TOOLTIP-C1,
      // 11/09/2026. Sem esta linha, o bloco que já nasce igual nunca ganha
      // memória; a camada da dica colhe os `title` de dentro dele logo depois,
      // o `innerHTML` passa a divergir do texto do Python, e o tique seguinte
      // reconstrói um bloco que ninguém mudou — uma vez por carga, em cada
      // bloco de cada aba.
      if(alvo.innerHTML === html){ alvo.__hefBloco = html; continue; }
      if(alvo.querySelector('.hef-em-voo') || alvo.closest('.hef-em-voo')){
        window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
        continue;
      }
      alvo.innerHTML = html;
      alvo.__hefBloco = html;
      n += 1;
    }
    // 0b. O MOLDE QUE CLONA — 19/09/2026, decisão dela: *a lista rola, sem teto*.
    //
    // O QUE ISTO CURA, e são DUAS pontas do mesmo defeito, as duas medidas no
    // Check-up da aba Conexões em 19/09 com o Chrome dirigindo a página
    // PUBLICADA:
    //
    //   * a lista que SOBRA some. O desenho tinha cinco blocos e o exame da
    //     bancada dela devolve sete: dois achados sumiam, e a tira ficava com
    //     cinco CERTO — a tela dizendo "está tudo bem" com dois achados
    //     abertos escondidos no fim;
    //   * a lista que FALTA mente. Com três achados (medido numa máquina sem a
    //     bancada dela), os dois blocos que sobravam ficavam com o travessão de
    //     `escrever(el, '')` — a tela INVENTANDO duas linhas.
    //
    // UM TETO MAIOR NÃO RESOLVERIA, e é por isso que a peça é esta: as
    // conferências do exame devolvem LISTAS (`a08_conexoes._conferencias`), uma
    // porta problemática por item. O número de achados não tem máximo, e todo
    // número cravado no desenho seria o mesmo defeito com outra data.
    //
    // O CONTRATO É DE DUAS LINHAS no HTML: a caixa diz o SELETOR do bloco que
    // se repete (`data-hef-molde`) e a CHAVE da lista que manda na contagem
    // (`data-hef-molde-conta`). O bloco original mais à frente é o molde.
    //
    // OS CLONES SE MARCAM (`data-hef-clone`), e é o que torna isto idempotente:
    // sem a marca, o tique seguinte leria os clones como originais e a lista
    // dobraria de tamanho a cada volta. Com ela, o piloto sabe o que ele mesmo
    // pôs e converge para o número certo — clona o que falta, remove o que
    // sobra, esconde o original excedente.
    //
    // ESCONDER O EXCEDENTE E NÃO REMOVÊ-LO: os originais são o DESENHO, e são
    // eles que o mockup mostra. Removê-los deixaria a aba sem molde no dia em
    // que a lista voltasse a crescer.
    for(const caixa of document.querySelectorAll('[data-hef-molde]')){
      const seletor = caixa.dataset.hefMolde;
      const chave = caixa.dataset.hefMoldeConta;
      const lista = (p.mesa || {})[chave];
      if(!seletor || !chave || !Array.isArray(lista)) continue;
      const todos = Array.from(caixa.querySelectorAll(seletor));
      const originais = todos.filter(function(el){ return !el.hasAttribute('data-hef-clone'); });
      if(!originais.length) continue;
      const clones = todos.filter(function(el){ return el.hasAttribute('data-hef-clone'); });
      const querido = lista.length;
      const molde = originais[originais.length - 1];
      while(originais.length + clones.length > Math.max(querido, originais.length)){
        const fora = clones.pop();
        if(fora && fora.parentNode) fora.parentNode.removeChild(fora);
        n += 1;
      }
      let cauda = clones.length ? clones[clones.length - 1] : molde;
      while(originais.length + clones.length < querido){
        const copia = molde.cloneNode(true);
        copia.setAttribute('data-hef-clone', '1');
        // O `__hefBloco` é memória de PINTURA e viaja no clone como lixo: o
        // laço dos blocos compararia o HTML novo com o do molde e pularia a
        // escrita. `cloneNode` não copia propriedades de objeto, mas o
        // `dataset` e os atributos sim — e é só o atributo que interessa aqui.
        if(cauda.parentNode) cauda.parentNode.insertBefore(copia, cauda.nextSibling);
        clones.push(copia);
        cauda = copia;
        n += 1;
      }
      // E O EXCEDENTE SOME. A classe é da FOLHA DA CASA
      // (`folha_da_casa.FOLHA_DA_CASA`), porque é peça do piloto e não do tema:
      // ela vale nas dez páginas e não depende de nenhuma aba declará-la.
      Array.from(caixa.querySelectorAll(seletor)).forEach(function(el, i){
        const sobra = i >= querido;
        if(el.classList.contains('hef-sem-item') !== sobra){
          el.classList.toggle('hef-sem-item', sobra);
          n += 1;
        }
      });
    }
    // 1. OS CAMPOS DA MESA — soltos no documento, valem para a página toda.
    for(const [k, v] of Object.entries(p.mesa || {})){
      const alvos = achar(document, k);
      // UMA LISTA SE DISTRIBUI pelos elementos de mesmo endereço, na ordem.
      // É como a aba Conexões mostra os achados do exame e a Perfis a lista de
      // perfis: N blocos iguais, um por item, todos com o mesmo `data-campo`.
      // Sem isto o pacote teria de emitir `achado-0`, `achado-1`… e o gerador
      // teria de saber de antemão QUANTOS itens o exame acha.
      if(Array.isArray(v)){
        alvos.forEach(function(el, i){ n += escrever(el, i < v.length ? v[i] : ''); });
        continue;
      }
      if(v !== null && typeof v === 'object') continue;
      for(const el of alvos) n += escrever(el, v);
    }
    // 1b. OS LUGARES VAZIOS ganham a marca do desenho. `data-conectado` e a
    // classe `off` são o que o gerador escreve nos dois lugares que ela mandou
    // deixar desconectados — usar as MESMAS marcas é o que faz o produto
    // parecer o desenho, em vez de inventar um terceiro estado.
    for(const pref of (p.vazios || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        if(el.dataset.conectado !== 'nao'){  // (noqa-acento) valor do atributo
          el.dataset.conectado = 'nao'; n += 1;  // (noqa-acento) idem
        }
        if(!el.classList.contains('off')){ el.classList.add('off'); }
        // O `remove` TAMBÉM PERGUNTA ANTES — A-TELA-SAMBA-01, 06/09/2026.
        // `classList.remove` de uma classe AUSENTE reserializa o atributo
        // `class` do mesmo jeito, e cada reserialização é uma mutação: 400 por
        // 100 tiques na `01-jogar`, com a mesa parada e nenhum lugar mudando de
        // dono. O `add` acima já perguntava; faltava o irmão.
        if(el.classList.contains('alvo')){ el.classList.remove('alvo'); }
      }
    }
    // 1c. E OS LUGARES QUE TÊM DONO REABREM — o simétrico do passo acima, e
    // ele faltava. Sem esta linha a marca é de mão única: o piloto fechava o
    // cartão de um controle que sai e NUNCA o reabria quando ele voltava. Quem
    // liga o controle depois de a aba estar aberta via o cabeçalho contar `1
    // controle` e o cartão continuar em 24 px, com o travessão — o dado dela
    // chegando invisível. Só recarregar a página desfazia.
    for(const pref of (p.ocupados || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        // COMPARA COM `sim`, e não com o valor de desconectado — a diferença
        // foi medida no DOM vivo em 03/09/2026: nas abas 02, 05 e 08 o lugar
        // CHEIO nasce SEM o atributo, e a versão anterior, que só trocava um
        // valor pelo outro, deixava os três em `null`. A folha não tem como vestir de conectado
        // um lugar sobre o qual a tela não afirma nada.
        if(el.dataset.conectado !== 'sim'){
          el.dataset.conectado = 'sim'; n += 1;
        }
        // PERGUNTA ANTES — ver a nota do `alvo` no passo `1b` logo acima. Este
        // é o pior dos dois, porque roda para todo lugar OCUPADO: numa mesa de
        // dois controles são dois `class` reserializados por tique, para
        // sempre, sem que um lugar tenha mudado de dono.
        if(el.classList.contains('off')){ el.classList.remove('off'); }
      }
    }
    // 1d. AS MARCAS DO LUGAR — 21/09/2026, `pacotes.MARCAS_DO_LUGAR`. A classe
    // acende nos lugares da lista e apaga nos outros; a que o pacote não nomeia
    // fica como está. Sem isto o `navega` da Navegação ficava no P1 do desenho
    // para sempre: verde com a mesa vazia, verde com o P2 no comando.
    for(const [classe, com] of Object.entries(p.marcas || {})){
      for(const pref of ['p1', 'p2', 'p3', 'p4']){
        const quer = (com || []).indexOf(pref) >= 0;
        for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
          if(el.classList.contains(classe) !== quer){
            el.classList.toggle(classe, quer); n += 1;
          }
        }
      }
    }
    // 2. OS CAMPOS POR CONTROLE — dentro do bloco daquele `data-controle`.
    for(const [pref, campos] of Object.entries(p.colunas || {})){
      for(const raiz of document.querySelectorAll('[data-controle="' + pref + '"]')){
        for(const [k, v] of Object.entries(campos)){
          if(v !== null && typeof v === 'object') continue;
          for(const el of achar(raiz, k)) n += escrever(el, v);
        }
      }
    }
    // 3. OS RECADOS SAÍRAM DA PINTURA — 13/09/2026, FRASES-E-DICAS-01. Este
    // passo pintava a lista `p.recados` que o tique mandava; nenhuma carga a
    // traz mais. Ver a nota no lugar em que `pintar_recados` morava.
    //
    // 4. A PÁGINA APARECE — 22/09/2026, DEPOIS da primeira pintura (ver
    // `folha_da_casa.CLASSE_DA_ESPERA`). A GUARDA É DO SAMBA: `remove` de
    // classe ausente reescreve o atributo — 40 mutações em 40 tiques, medido.
    if(document.documentElement.classList.contains('hef-esperando'))
      document.documentElement.classList.remove('hef-esperando');
    return n;
  };
  // O OUVINTE DE CLIQUE, e ele é UM SÓ para a página inteira. Um
  // `addEventListener` por botão seria N ouvintes a religar a cada repintura —
  // e um botão que a pintura substitua perde o seu, calado. Delegar no
  // documento sobrevive a qualquer troca de HTML, que é o que a fita faz a
  // cada mudança de mesa.
  if(!window.__hef.ouvindo){
    window.__hef.ouvindo = true;
    // O `change` ALÉM DO `click`, e ele é o que faltava para metade dos botões
    // sem dono. Um `<select>` não se "clica" no sentido útil — ele MUDA; e um
    // `<input>` de texto nunca dispara clique com o valor novo. Medido em
    // 01/09/2026: os quatro campos do editor da aba Perfis, os selects da
    // Conexões e o nome da face nova ficaram sem dono por isto, e o relato dos
    // agentes nomeia a causa uma vez por aba — *"o ouvinte manda `texto:
    // alvo.textContent`, que num `<input>` é vazio"*.
    document.addEventListener('change', function(ev){ manda_do_alvo(ev); }, true);
    document.addEventListener('click', function(ev){
      // Os quatro atributos que marcam algo CLICÁVEL nas dez páginas. Eles já
      // existiam — cada piloto de aba usava o seu.
      manda_do_alvo(ev);
    }, true);
    // E O `blur`, que é a TERCEIRA porta e faltava — achado pela frente da aba
    // 08 em 04/09/2026, e a forma do defeito é a mesma das outras duas: um
    // `contenteditable` (o apelido do adaptador) **não dispara `click` nem
    // `change`** ao perder o foco. O motor do apelido estava de pé, completo e
    // testado, e simplesmente NUNCA era acionado — o gesto existia e a tela
    // não tinha como chamá-lo.
    //
    // `blur` não borbulha, por isso a captura (`true`) é obrigatória, e não
    // uma preferência de estilo.
    //
    // A LIÇÃO É A DE 01/09, repetida com outro elemento: **o ouvinte único só
    // ouve o que alguém lembrou de ensinar a ele.** Quem puser na tela um
    // elemento novo que carregue valor confere se ele fala por uma destas três
    // portas — senão o gesto nasce mudo, e mudo dá verde em toda régua que
    // pergunte se o motor existe.
    document.addEventListener('blur', function(ev){
      if(ev.target && ev.target.isContentEditable) manda_do_alvo(ev);
    }, true);
    // E O `input`, QUE É A QUARTA PORTA — ver `manda_do_vivo` logo abaixo. Ela
    // é a única das quatro que NÃO despacha o gesto de `data-hef-gesto`, e a
    // razão é que ali o gesto grava no disco dela.
    document.addEventListener('input', function(ev){ manda_do_vivo(ev); }, true);
    // A JANELA ESCONDIDA — A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01. Quem
    // sabe se a janela está à vista é o WebKit, e ele diz isso por
    // `document.hidden`, o mesmo sinal com que para de pintar. O aviso vai
    // pelo canal de sempre, sem `gesto`, e o `_gesto` do Python o separa antes
    // de contar clique.
    //
    // TROCAR DE ABA NÃO É ESCONDER. O documento que sai passa a `hidden`
    // antes de morrer, e o `pagehide` vem antes disso: sem esta marca, cada
    // troca de aba escreveria no diário que a janela foi escondida, e a linha
    // que prova o minimizar na máquina dela não provaria nada. A página nova
    // diz `vista` assim que nasce; a que volta do cache diz no `pageshow`.
    window.addEventListener('pagehide', function(){ window.__hefSaindo = true; });
    window.addEventListener('pageshow', function(){
      window.__hefSaindo = false;
      dizer_a_vista();
    });
    document.addEventListener('visibilitychange', function(){
      if(!window.__hefSaindo) dizer_a_vista();
    });
  }
  function dizer_a_vista(){
    // SEM O CANAL NÃO HÁ A QUEM DIZER: as réguas rodam este BOOTSTRAP num
    // WebView sem o `hefesto`, e um erro aqui derrubaria a instalação inteira.
    const canal = window.webkit && window.webkit.messageHandlers
                  && window.webkit.messageHandlers.hefesto;
    if(!canal) return;
    canal.postMessage(JSON.stringify({
      visibilidade: document.hidden ? 'escondida' : 'vista',
      pagina: location.pathname.split('/').pop()}));  // (noqa-acento) a chave das outras mensagens
  }
  // A SÉRIE DO GESTO VIVO. Ela é própria e não o contador do voo: o voo carimba
  // o elemento e volta pelo `voltouDoVoo`; a série do vivo nunca toca o DOM —
  // ela só diz ao Python qual leitura é a mais nova.
  window.__hef.vivoN = window.__hef.vivoN || 0;
  function manda_do_alvo(ev){
      const alvo = ev.target.closest(
        '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
        '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
        '.r-aplicar,.r-salvar,.r-importar,.r-exportar');
      if(!alvo) return;
      const d = alvo.dataset;
      // O RODAPÉ ENDEREÇA POR CLASSE, e não por `data-`: ele mora no
      // `topo.html`, o esqueleto das dez, e um `data-gesto` ali mudaria as dez
      // páginas de uma vez. A classe `r-<nome>` já era o endereço dele no
      // `jogar_vivo.py` — este é o quarto vocabulário, e é o último.
      const doRodape = (alvo.className.match(/\br-([a-z]+)\b/) || [])[1];
      // O CARIMBO DO VOO, e ele é aplicado ANTES de a mensagem sair: a resposta
      // tem de ser do CLIQUE, não da volta do Python. O gesto atravessa uma
      // thread e o IPC; esperar por ele para dizer "estou trabalhando" seria
      // dizê-lo tarde demais — que é o defeito inteiro.
      //
      // TODO CLIQUE QUE VAI PARA O PYTHON É CARIMBADO, inclusive o que vai ser
      // recusado por não ter dono. O piloto despacha o pouso nos TRÊS desfechos
      // (aplicou, recusou, sem dono), e um botão que ficasse em voo porque o
      // gesto não existia seria a tela mentindo sobre um trabalho que ninguém
      // começou.
      manda(carga_do_alvo(
        alvo, ev, d.gesto || d.hefGesto || d.papel || doRodape || 'clique',
        em_voo(alvo)));
  }
  // A QUARTA PORTA — `data-hef-vivo`, o gesto que LÊ e não grava.
  //
  // POR QUE ELA PRECISOU EXISTIR, e o relato é da `ONDA5-10-02`: a decisão
  // 10-Q4 dela pede o rótulo do jogo *"ao vivo"*, e `input` é o único evento que
  // um campo de texto dispara a cada TECLA. As três portas de hoje despacham o
  // gesto de `data-hef-gesto` — que naquele campo é `editor.jogo`, e ele GRAVA
  // O PERFIL DELA. Ligar `input` ao mesmo atributo regravaria o `.json` a cada
  // letra digitada.
  //
  // ENTÃO O ENDEREÇO É PRÓPRIO, e é essa a peça inteira: um elemento pode
  // carregar `data-hef-vivo="<gesto>"`, e o `input` despacha ESSE gesto — nunca
  // o de `data-hef-gesto`, ainda que o mesmo elemento traga os dois.
  //
  // SEM O ATRIBUTO O `input` NÃO FAZ NADA. Nenhuma das dez abas muda de
  // comportamento por esta porta nascer: quem a usa é quem publicar o atributo,
  // e publicar é ato dela.
  //
  // ELE NÃO VESTE O `em_voo`, e é decisão: o cursor `progress` e a opacidade a
  // cada tecla seriam a tela dizendo *"trabalhando"* sobre uma leitura de
  // milissegundos — o oposto do que aquele sinal existe para dizer.
  //
  // UM VIVO EM VOO POR ELEMENTO. Cada disparo leva um número de série e a
  // identidade do elemento; o Python guarda o último e DESCARTA a resposta que
  // chegar fora de ordem. Sem isso, a leitura da tecla `1` pode voltar depois da
  // leitura de `15` e pintar o rótulo do jogo errado — e ficar assim até a
  // próxima tecla.
  function manda_do_vivo(ev){
      const alvo = ev.target.closest('[data-hef-vivo]');
      if(!alvo) return;
      const g = String(alvo.dataset.hefVivo || '').trim();
      if(!g) return;
      const o = carga_do_alvo(alvo, ev, g, '');
      // A IDENTIDADE DO ELEMENTO, e ela é o endereço que ele já tem: o
      // `data-campo`/`data-hef`/`data-papel` do próprio campo mais o dono. Dois
      // campos vivos diferentes na mesma coluna não compartilham série; dois
      // disparos do MESMO campo, sim — que é exatamente o que se quer cancelar.
      o.vivoChave = g + '|'
        + (alvo.dataset.campo || alvo.dataset.hef || alvo.dataset.papel || '')
        + '|' + String(o.controle || '');
      o.vivo = String(++window.__hef.vivoN);
      manda(o);
  }
  function carga_do_alvo(alvo, ev, gesto, voo){
      const d = alvo.dataset;
      // DE QUAL CONTROLE, e sem isto o gesto é ambíguo: a mesa tem quatro
      // colunas iguais e um "Desligar" clicado na terceira não diz em qual
      // barra de luz mexer. O `closest` sobe até o bloco do controle — é o
      // mesmo `data-controle` que a pintura usa para achar onde escrever.
      //
      // O DONO É O ASSENTO, e o seletor é uma lista de PERMITIDOS — ver
      // `SELETOR_DO_DONO` no Python, que é quem tem a razão inteira e a régua.
      // Em uma linha: o desenho compartilhado carrega o MODELO no mesmo
      // atributo, e um botão posto dentro dele chegaria aqui dizendo que o
      // controle se chama como o plástico.
      const dono = alvo.closest(
        '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
      // O DATASET INTEIRO VAI JUNTO, e ele vem PRIMEIRO para que a lista
      // explícita abaixo continue mandando no que ela nomeia.
      //
      // POR QUE ISTO PRECISOU EXISTIR, medido em 02/09/2026: a lista explícita
      // tinha catorze nomes, escritos à mão, e os gestos da aba Conexões leem
      // `caminho`, `entrada` e `face` — NENHUM dos três estava nela. O botão
      // "escolher aparelho" traz `data-caminho` (o pacote o gera em
      // `a08_conexoes.py:1149`), as entradas do gabinete trazem `data-entrada`
      // no HTML publicado, e o clique chegava ao Python sem eles. Resultado:
      // SEIS gestos recusavam dizendo *"o clique não disse qual aparelho"* — e
      // recusavam para ELA também, não só para a régua. O diagnóstico que
      // circulava era outro: que faltava dizer em qual CONTROLE agir. Não é o
      // controle; é o argumento do próprio botão.
      //
      // UMA LISTA ESCRITA À MÃO DE ATRIBUTOS QUE A PÁGINA PODE TER É A MESMA
      // FORMA DE DEFEITO QUE ESTA CASA JÁ NOMEOU: ela só cresce quando alguém
      // se lembra, e o esquecimento é silencioso. O dataset inteiro não
      // esquece — e o custo é uma cópia de meia dúzia de strings por clique.
      const tudo = Object.assign({}, d);
      return Object.assign(tudo, {
        voo: voo,
        gesto: gesto,
        // A MARCA DO VIVO NASCE VAZIA AQUI, e quem a preenche é o
        // `manda_do_vivo`. Sem esta linha, uma página que um dia escrevesse
        // `data-vivo` num botão faria um CLIQUE cair no caminho do gesto vivo —
        // sem voo, sem recado e com a guarda de gravação por cima. É a mesma
        // razão de a lista explícita vir depois do dataset, um risco abaixo:
        // aqui o defeito seria calado.
        vivo: '', vivoChave: '',
        modo: d.modo || '', forca: d.forca || '', player: d.player || '',
        lado: d.lado || '', campo: d.campo || '', hef: d.hef || '',
        hex: d.hex || '', sensor: d.sensor || '', rota: d.rota || '',
        mudo: d.mudo || '', micModo: d.micModo || '', v: d.v || '',
        // O ALVO PADRÃO — O CONTROLE QUE A FITA APONTOU.
        //
        // FATO SUBSTITUÍDO EM 06/09/2026, e ele estava aqui desde que a fita
        // aprendeu a escolher. Esta linha dizia que o alvo padrão *"é da RÉGUA —
        // no produto fica indefinido"*. **Não fica**: o tique escreve
        // `carga["alvo"]` nas abas cuja fita ESCOLHE, e o `pintar` o guarda em
        // `window.__hef.alvoPadrao` (ver a nota do `carga["alvo"]` no `_tique`).
        // No produto, um botão que não mora em coluna de controle nenhuma chega
        // ao Python com o controle que ela apontou na fita — e isso é DESENHO,
        // não acidente: *"Esta aba passa a mirar o P2."*
        //
        // O QUE ISSO CUSTAVA, medido pela ONDA5-01-03 em 06/09 com foto: a
        // recusa de um gesto de PÁGINA (o cadeado da 01, que liga o Hefesto
        // inteiro) seguia o mesmo alvo e pousava no cartão do P1, cobrindo o
        // nome dele (`ONDA5-P-01` §7).
        // **Deixou de custar em 13/09/2026** (FRASES-E-DICAS-01): a recusa não
        // pousa em cartão nenhum — pisca no botão clicado.
        //
        // ELE CURA A VIBRAÇÃO, e só ela. Medido com dublê em 02/09/2026:
        // `testar` e `parar` recusam com *"o clique não disse em qual controle
        // — e sem alvo a mesa inteira treme"*, e passam a chamar a ponte assim
        // que o clique traz um `controle`. Os botões do gabinete da aba
        // Conexões NÃO se curam com isto: o que falta a eles é o argumento do
        // próprio botão (`caminho`, `entrada`, `face`), que o dataset acima
        // agora carrega.
        //
        // POR QUE NÃO NO PRODUTO: escolher o primeiro controle conectado por
        // conta própria é uma DECISÃO de produto — se o botão não diz em qual
        // aparelho age, quem decide é ela, com a tela dizendo. A régua só o usa
        // para conseguir medir, e o relato marca esses cliques como ALVO
        // FORÇADO, para ninguém ler a ajuda dela como o produto funcionando.
        controle: dono ? (dono.dataset.controle || dono.dataset.uniq || '')
                       : (window.__hef.alvoPadrao || ''),
        // O VALOR, e ele é o que o `textContent` não alcança: num `<input>` o
        // texto é vazio, e num `<select>` é a lista INTEIRA de opções. Sem
        // isto, um campo digitado chega ao Python sem o que ela digitou.
        valor: (('value' in alvo) ? String(alvo.value ?? '') : ''),
        // `selectedOptions` dá o rótulo VISÍVEL da opção escolhida — o que ela
        // leu na tela — enquanto `value` dá a chave do contrato. Os dois vão,
        // porque o gesto precisa de um e a mensagem de erro do outro.
        rotulo: (alvo.selectedOptions && alvo.selectedOptions[0]
                 ? alvo.selectedOptions[0].textContent.trim() : ''),
        tipo: (alvo.tagName || '').toLowerCase(),
        evento: ev.type,
        // A FORMA INTEIRA, e ela nasceu em 01/09/2026 para os três "Guardar"
        // das telas de pop-up. O ouvinte manda o valor do elemento CLICADO — e
        // o Guardar é OUTRO elemento, a três telas de distância dos 21
        // `<select>` que ele promete gravar. Sem isto, o botão só podia
        // recusar: não tinha como saber o que estava escolhido em cada linha.
        //
        // SÓ QUANDO O BOTÃO PEDE. `data-hef-forma` nomeia o container a
        // recolher; um clique comum não paga a varredura, e nenhum outro gesto
        // recebe um campo que não pediu.
        forma: (function(){
          const pedido = alvo.dataset.hefForma;
          if(!pedido) return null;
          // DOIS RECIPIENTES, e o segundo nasceu em 01/09/2026 para a aba
          // Gatilhos: lá o "Guardar" é da COLUNA de um controle, e as colunas
          // não têm `id` — elas se endereçam por `data-controle`, que é o
          // vocabulário que a mesa inteira já usa. `@controle` quer dizer "o
          // bloco do controle em que eu estou".
          const cx = pedido === '@controle'
            ? alvo.closest(
                '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]')
            : document.getElementById(pedido);
          if(!cx) return null;
          const fora = {};
          // A CHAVE É O `data-linha` (Navegação) OU o `data-campo` (Gatilhos) —
          // nunca os dois. O RÁDIO (21/09/2026, a escolha do jogo da aba 07) divide
          // UM endereço entre as opções: só a MARCADA responde, senão vence a última.
          for(const el of cx.querySelectorAll('[data-linha],[data-campo]')){
            if(el.type === 'radio' && !el.checked) continue;
            const chave = el.dataset.linha || el.dataset.campo;
            fora[chave] = ('value' in el)
              ? String(el.value ?? '') : (el.textContent || '').trim();
          }
          return fora;
        })(),
        texto: (alvo.textContent || '').trim().slice(0, 60),
      });
  }
  function manda(o){
    o.pagina = location.pathname.split('/').pop();
    window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o));
  }
  // UMA VEZ NA CARGA, e a cada troca pelo ouvinte lá em cima: a página que
  // nasce com a janela minimizada já diz que ninguém a vê.
  dizer_a_vista();
  return 'ok';
})();
"""


#: paginas isso ocorre."*  <!-- noqa-acento: citação literal dela -->
#: Medido em 11/09/2026 nesta árvore, com o daemon vivo, um DualSense no cabo,
DICA_DA_CASA = r"""
(function(){
  if(window.__hefDica && window.__hefDica.instalada) return 'ja';
  if(!document.body) return 'sem body';
  var SVG = 'http://www.w3.org/2000/svg';
  // MEIO SEGUNDO, o mesmo do GTK (`HOVER_TIMEOUT`). Copiar o número é
  // deliberado: a dica tem de parecer a mesma coisa que ela já conhece.
  var ATRASO = 500;
  var caixa = document.createElement('div');
  caixa.id = 'hef-dica';
  caixa.setAttribute('role', 'tooltip');
  // A CARA É A DA `.dica` DA CASA (`interface/topo.html`), variável a variável,
  // com literal de reserva para a página que não as definir. `pointer-events`
  // desligado: a dica não pode roubar o ponteiro de quem ela explica — seria o
  // mesmo defeito de novo, um elemento por cima comendo o evento.
  caixa.style.cssText =
    'position:fixed;left:0;top:0;z-index:2147483000;display:none;'
    + 'max-width:340px;pointer-events:none;white-space:pre-line;'
    + 'background:var(--elevated,#2b2d3a);border:1px solid var(--linha,#44475a);'
    + 'border-radius:7px;padding:9px 11px;font-size:11.5px;line-height:1.5;'
    + 'color:var(--texto-suave,#d8dae6);text-align:left;font-weight:400;'
    + 'box-shadow:0 8px 24px rgba(0,0,0,.5);';
  document.body.appendChild(caixa);

  var E = {alvo: null, texto: '', tempo: 0, x: 0, y: 0, aberta: false, abriu: 0};

  // O NOME ACESSÍVEL — F7, 11/09/2026, e ele é a DÍVIDA QUE A COLHEITA CRIOU.
  //
  // A colheita abaixo tira o `title` do DOM vivo para o popup do compositor não
  // ter de que nascer. Só que o `title` não era só a dica: quando o elemento
  // não tem outro rótulo, ele é também o NOME que um leitor de tela anuncia.
  // Sem ele, um botão de ícone vira *«botão»* — e a queixa de quem não enxerga
  // é a mesma dela, com outro nome: o produto deixa de se explicar.
  //
  // **MEDIDO NO DOM VIVO das treze páginas publicadas, com esta camada de pé:**
  // 693 `title` colhidos com texto, e destes 388 já tinham nome por outra via
  // (357 pelo próprio conteúdo, 31 por `aria-label` que a aba escreveu) e 215
  // estão em `span`/`div`/`label` — casca sem papel, que nome nenhum alcança.
  // **90 ficavam mudos**: 52 botões de ícone, 14 deslizantes, 12 campos de
  // digitar, 12 listas. Mais **1.930 `<title>` de SVG**, nenhum com outra via.
  //
  // A REGRA É UMA SÓ, E ELA É NEGATIVA: veste `aria-label` **só em quem ficaria
  // sem nome**. Um `aria-label` por cima de um botão que já diz «Aplicar» faz o
  // leitor de tela ler duas vezes — é pior do que não fazer nada, e é por isso
  // que `tem_nome()` abaixo é tão detalhado quanto a conta do HTML-AAM.
  //
  // E A DESCRIÇÃO FICOU DE FORA, declarada: nos 388 que já têm nome o `title`
  // era a DESCRIÇÃO, e ela não volta aqui. A dica da casa continua mostrando a
  // frase a quem vê; devolvê-la a quem não vê pede `aria-description`, que é
  // outra sprint e outro suporte de motor.
  var PAPEL_SEM_NOME = {presentation: 1, none: 1, generic: 1};
  //: Quem aceita um nome acessível SEM papel declarado. A lista é a do
  //: HTML-AAM, podada ao que existe nestas dez abas — `div` e `span` ficam de
  //: fora de propósito: o papel deles é genérico, e o ARIA proíbe nomeá-lo.
  var TAG_QUE_ACEITA_NOME = {a: 1, button: 1, input: 1, select: 1, textarea: 1,
    summary: 1, img: 1, area: 1, iframe: 1, meter: 1, progress: 1, output: 1,
    details: 1, dialog: 1, fieldset: 1, optgroup: 1, option: 1, audio: 1,
    video: 1, th: 1, table: 1, svg: 1};
  //: Quem tira o nome do PRÓPRIO CONTEÚDO — o botão que diz «Aplicar» dentro.
  var TAG_NOME_DO_CONTEUDO = {a: 1, button: 1, summary: 1, th: 1, td: 1,
    option: 1, optgroup: 1, legend: 1};
  var PAPEL_NOME_DO_CONTEUDO = {button: 1, link: 1, tab: 1, menuitem: 1,
    menuitemcheckbox: 1, menuitemradio: 1, option: 1, checkbox: 1, radio: 1,
    switch: 1, heading: 1, treeitem: 1, gridcell: 1, cell: 1, columnheader: 1,
    rowheader: 1, tooltip: 1};
  //: QUEM VESTIMOS, e o valor que vestimos. É um `WeakMap` e não um atributo
  //: novo no DOM: `data-hef-*` é território de endereço desta casa, e um
  //: marcador a mais ali seria mais uma coisa para as réguas tropeçarem. O
  //: valor guardado é o que permite largar a posse sem briga — se a aba
  //: escrever outro `aria-label` por cima, o nosso deixa de ser nosso.
  var NOSSOS = (typeof WeakMap === 'function') ? new WeakMap() : null;

  // O TEXTO QUE NOMEIA, e ele NÃO é o `textContent` cru. Duas podas, e as duas
  // são medidas: um `<title>` de SVG está DENTRO do elemento e não é texto de
  // tela — contá-lo faria todo botão de ícone passar por botão com rótulo, que
  // é exatamente o botão que perde o nome aqui; e uma subárvore com
  // `aria-hidden` não conta para nome nenhum, por definição.
  function texto_que_nomeia(no, fundo){
    if(!no || fundo > 12) return '';
    if(no.nodeType === 3) return no.nodeValue || '';
    if(no.nodeType !== 1) return '';
    if(no.namespaceURI === SVG
       && (no.localName === 'title' || no.localName === 'desc')) return '';
    if(no.getAttribute && no.getAttribute('aria-hidden') === 'true') return '';
    var s = '', f = no.firstChild;
    while(f){ s += texto_que_nomeia(f, fundo + 1); f = f.nextSibling; }
    return s;
  }
  function rotulo_de_formulario(el){
    if(el.id){
      var id = (window.CSS && CSS.escape) ? CSS.escape(el.id) : el.id;
      var l = document.querySelector('label[for="' + id + '"]');
      if(l && texto_que_nomeia(l, 0).trim()) return true;
    }
    var p = el.parentElement, n = 0;
    while(p && n < 8){
      if(p.localName === 'label' && texto_que_nomeia(p, 0).trim()) return true;
      p = p.parentElement; n += 1;
    }
    return false;
  }
  // JÁ TEM NOME? A conta do HTML-AAM na ordem dela: o que vem ANTES do `title`
  // é nome; o que vem depois não salva ninguém. O `placeholder` é o caso que
  // decide sozinho — ele vem DEPOIS do `title`, e rotular por `placeholder` é
  // falha conhecida de acessibilidade; então um campo que só tem `placeholder`
  // conta como MUDO aqui, e ganha o `aria-label`.
  function tem_nome(el){
    if(String(el.getAttribute('aria-label') || '').trim()) return true;
    var lb = String(el.getAttribute('aria-labelledby') || '').trim();
    if(lb){
      var ids = lb.split(/\s+/);
      for(var i = 0; i < ids.length; i++){
        var o = document.getElementById(ids[i]);
        if(o && texto_que_nomeia(o, 0).trim()) return true;
      }
    }
    var tag = el.localName;
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(tag === 'img' || tag === 'area') return el.hasAttribute('alt');
    if(tag === 'input'){
      var t = String(el.getAttribute('type') || 'text').toLowerCase();
      if(t === 'button' || t === 'submit' || t === 'reset'){
        return !!String(el.getAttribute('value') || '').trim();
      }
      if(t === 'image') return !!String(el.getAttribute('alt') || '').trim();
      return rotulo_de_formulario(el);
    }
    if(tag === 'select' || tag === 'textarea' || tag === 'meter'
       || tag === 'progress') return rotulo_de_formulario(el);
    if(tag === 'option' && String(el.getAttribute('label') || '').trim()){
      return true;
    }
    if(papel ? PAPEL_NOME_DO_CONTEUDO[papel] : TAG_NOME_DO_CONTEUDO[tag]){
      return !!texto_que_nomeia(el, 0).trim();
    }
    return false;
  }
  function aceita_nome(el){
    var papel = String(el.getAttribute('role') || '').trim().toLowerCase();
    if(papel) return !PAPEL_SEM_NOME[papel];
    return !!TAG_QUE_ACEITA_NOME[el.localName];
  }
  //: O NOSSO `aria-label`, e só ele, pode ser trocado ou tirado depois.
  function e_nosso(el){
    if(!NOSSOS || !NOSSOS.has(el)) return false;
    return el.getAttribute('aria-label') === NOSSOS.get(el);
  }
  function vestir_nome(el, t){
    if(!el || !t || !el.getAttribute) return;
    if(!aceita_nome(el) || tem_nome(el)) return;
    el.setAttribute('aria-label', t);
    if(NOSSOS) NOSSOS.set(el, t);
  }
  // O NOME QUE TROCA DE TEXTO. O alvo `atributo` do piloto escreve `title` nas
  // dicas vivas (a carga da bateria, a taxa do giroscópio) e a camada desvia
  // esse texto para `data-hef-dica`; o nome tem de ir junto, ou o leitor de
  // tela fica com a frase do instante em que a página carregou. Só mexe no que
  // é nosso: um `aria-label` que a aba escreveu manda mais que este.
  function trocar_nome(el, t){
    if(!el || !e_nosso(el)) return;
    if(t){ el.setAttribute('aria-label', t); NOSSOS.set(el, t); }
    else { el.removeAttribute('aria-label'); NOSSOS.delete(el); }
  }
  // NO DESENHO O NOME É DO DONO DO `<title>`, e há dois casos medidos:
  //
  // * **o ícone** — um `<svg class="gl">` de 18 px com UM `<title>` e nada
  //   dentro: 222 nas treze páginas. Ele ganha `role="img"`, que é o papel que
  //   ele já tinha de fato;
  // * **a zona de um desenho** — os 1.708 `<g>`, `<path>`, `<circle>` e
  //   `<rect>` que dão nome a cada pedaço do DualSense. Aqui o papel NÃO se
  //   mexe: `role="img"` torna a subárvore apresentacional, e num desenho com
  //   zonas ele engoliria os 1.708 nomes de dentro para pôr um só por fora.
  //
  // E O ÍCONE QUE REPETE O TEXTO DO LADO SAI DA ÁRVORE — 63 dos 222. Quando a
  // frase vizinha já diz «Cruz», um `aria-label` de «Cruz» no desenho ao lado
  // faz o leitor ler duas vezes. Decorativo ao lado de quem já nomeia é
  // `aria-hidden`, e a conta é do DOM: o nome aparece no texto do pai.
  function eco_no_vizinho(svg, t){
    var pai = svg.parentElement;
    if(!pai) return false;
    var fora = texto_que_nomeia(pai, 0).trim().toLowerCase();
    if(!fora) return false;
    return fora.indexOf(String(t).trim().toLowerCase()) >= 0;
  }
  function vestir_nome_do_desenho(dono, t){
    if(!dono || !t || !dono.getAttribute) return;
    if(String(dono.getAttribute('aria-label') || '').trim()) return;
    if(String(dono.getAttribute('aria-labelledby') || '').trim()) return;
    if(dono.getAttribute('aria-hidden') === 'true') return;
    if(dono.localName === 'svg'){
      if(eco_no_vizinho(dono, t)){
        dono.setAttribute('aria-hidden', 'true');
        return;
      }
      // UM `<title>` SÓ é a assinatura do ícone: o desenho com zonas tem
      // dezenas, e ele não pode virar `img`.
      if(!dono.getAttribute('role')
         && dono.querySelectorAll('title').length <= 1){
        dono.setAttribute('role', 'img');
      }
    }
    dono.setAttribute('aria-label', t);
    if(NOSSOS) NOSSOS.set(dono, t);
  }

  // A COLHEITA — E ELA É O QUE FAZ O POPUP DO SISTEMA NÃO NASCER.
  //
  // MEDIDO em 11/09/2026, e derrubou a primeira forma desta camada: tirar o
  // `title` no `mousemove` é TARDE. O WebKit resolve a dica no MESMO evento, e
  // remover o atributo depois não desfaz o que ele já resolveu — só o próximo
  // movimento de ponteiro refaria a conta. Com a mão parada as DUAS ficavam na
  // tela, uma por cima da outra: a da casa e a do compositor.
  //
  // Então o texto sai do `title` ANTES de qualquer ponteiro chegar, para
  // `data-hef-dica`, que é onde o `escrever()` e o `LER_CAMPOS` deste piloto já
  // sabem procurá-lo. O `title` deixa de existir no DOM vivo; nas páginas
  // publicadas ele continua onde sempre esteve, e é de lá que esta camada o
  // colhe a cada carga.
  //
  // O `title` VAZIO É UMA ORDEM, e ela se preserva: no HTML um `title=""` CALA
  // a dica dos ancestrais, e a `10-perfis` tem quinze. Ele vira
  // `data-hef-dica=""`, e a busca para nele — como pararia no navegador.
  function colher(raiz){
    var n = 0;
    var lista = raiz.querySelectorAll('[title]');
    for(var i = 0; i < lista.length; i++){
      var el = lista[i];
      if(el === caixa) continue;
      var d = String(el.getAttribute('title') || '').trim();
      el.setAttribute('data-hef-dica', d);
      el.removeAttribute('title');
      // O NOME ANTES DO `title` SAIR NÃO MUDA NADA, e depois muda: `tem_nome`
      // não olha para o `title`, então a ordem aqui é indiferente — o que não
      // é indiferente é a ordem DOS DOIS LAÇOS. Este roda antes do laço do
      // SVG, e por isso `texto_que_nomeia` tem de podar o `<title>` de
      // desenho: nesta linha ele ainda tem texto dentro do botão de ícone.
      vestir_nome(el, d);
      n += 1;
    }
    // NO SVG A DICA É UM FILHO, NÃO UM ATRIBUTO — `interface/monta.py` já pagou
    // essa lição: quem escreve `<svg title="…">` não vê dica nenhuma. São 1.756
    // `<title>` nos desenhos das dez abas, e sem este laço a camada deixaria de
    // fora a metade da tela que é desenho. O `<title>` do documento fica de
    // fora pelo namespace: ele é o nome da janela, não uma dica.
    var tt = raiz.querySelectorAll('svg title:not([data-hef-dica])');
    for(var j = 0; j < tt.length; j++){
      var t = tt[j];
      if(t.namespaceURI !== SVG) continue;
      var st = String(t.textContent || '').trim();
      t.setAttribute('data-hef-dica', st);
      t.textContent = '';
      vestir_nome_do_desenho(t.parentElement, st);
      n += 1;
    }
    return n;
  }

  // O TEXTO DE UM ELEMENTO, em três estados e não dois: uma frase, o SILÊNCIO
  // declarado (o `title=""`), ou nada a dizer. Sem o do meio a busca subiria
  // por cima de um `title=""` e mostraria a dica que a página mandou calar.
  function textoDe(el){
    if(!el || !el.getAttribute) return null;
    if(el.hasAttribute('data-hef-dica')){
      var g = String(el.getAttribute('data-hef-dica') || '').trim();
      return g ? g : '';
    }
    if(el.hasAttribute('title')){
      // COLHEITA TARDIA: um bloco que o produto acabou de trocar traz o `title`
      // de volta. Colher aqui, no caminho, é o que mantém a camada inteira sem
      // varrer o documento a cada movimento do ponteiro.
      var t = String(el.getAttribute('title') || '').trim();
      el.setAttribute('data-hef-dica', t);
      el.removeAttribute('title');
      vestir_nome(el, t);
      return t ? t : '';
    }
    return null;
  }
  function svgTituloDe(el){
    if(!el || el.namespaceURI !== SVG) return null;
    var f = el.firstChild;
    while(f){
      if(f.nodeType === 1 && f.localName === 'title' && f.namespaceURI === SVG){
        if(!f.hasAttribute('data-hef-dica')){
          var ft = String(f.textContent || '').trim();
          f.setAttribute('data-hef-dica', ft);
          f.textContent = '';
          vestir_nome_do_desenho(el, ft);
        }
        var s = String(f.getAttribute('data-hef-dica') || '').trim();
        if(s) return {no: f, texto: s};
        return null;
      }
      f = f.nextSibling;
    }
    return null;
  }
  // SOBE A ÁRVORE como o próprio navegador faz para o `title`: a dica pode
  // estar no pai do nó que recebeu o evento, e quase sempre está.
  function achar(no){
    var e = (no && no.nodeType === 1) ? no : (no ? no.parentElement : null);
    while(e){
      var s = svgTituloDe(e);
      if(s) return {el: e, texto: s.texto, svg: s.no};
      var t = textoDe(e);
      if(t) return {el: e, texto: t, svg: null};
      if(t === '') return null;   // silêncio declarado: não sobe mais
      e = e.parentElement;
    }
    return null;
  }
  function esconder(){
    if(E.tempo){ clearTimeout(E.tempo); E.tempo = 0; }
    caixa.style.display = 'none';
    E.aberta = false;
  }
  function limpar(){
    esconder();
    E.alvo = null; E.texto = '';
  }
  function mostrar(){
    E.tempo = 0;
    if(!E.alvo || !document.contains(E.alvo.el)){ limpar(); return; }
    caixa.textContent = E.texto;
    caixa.style.display = 'block';
    E.aberta = true;
    E.abriu += 1;
    // POSICIONA DEPOIS DE MEDIR, e dentro da janela: uma dica que nasce fora da
    // borda é uma dica que não abriu. A `05-vibracao` já mediu essa regra do
    // lado do desenho (`tests/unit/test_moldura_a_dica_nao_atravessa_a_janela.py`);
    // esta é a mesma regra, agora do lado de quem desenha a dica.
    var r = caixa.getBoundingClientRect();
    var x = E.x + 14, y = E.y + 20;
    if(x + r.width + 6 > window.innerWidth){
      x = Math.max(6, window.innerWidth - r.width - 6);
    }
    if(y + r.height + 6 > window.innerHeight){
      y = Math.max(6, E.y - r.height - 12);
    }
    caixa.style.left = Math.round(x) + 'px';
    caixa.style.top = Math.round(y) + 'px';
  }
  // O MOVIMENTO, E A DIFERENÇA MEDIDA COM O GTK: lá a contagem de meio segundo
  // RECOMEÇA a cada evento de movimento, e por isso a mão que treme nunca vê a
  // dica — medido nesta bancada em 11/09/2026, 0 de 200 amostras em 80 s com o
  // ponteiro tremendo 1 px a cada 150 ms. Aqui a contagem começa na ENTRADA do
  // elemento e só se reinicia quando o elemento MUDA: a dica abre com a mão em
  // cima, e não só com a mão parada. Passar correndo por cima continua não
  // abrindo nada, porque a troca de alvo zera tudo.
  document.addEventListener('mousemove', function(ev){
    E.x = ev.clientX; E.y = ev.clientY;
    var a = achar(ev.target);
    if(!a){ if(E.alvo) limpar(); return; }
    if(!E.alvo || a.el !== E.alvo.el || a.svg !== E.alvo.svg){
      limpar();
      E.alvo = a; E.texto = a.texto;
      E.tempo = setTimeout(mostrar, ATRASO);
      return;
    }
    if(!E.aberta && !E.tempo){ E.tempo = setTimeout(mostrar, ATRASO); }
  }, true);
  // SAIR DA JANELA fecha. `relatedTarget` nulo é o único `mouseout` que diz
  // isso; escutar `mouseleave` em captura fecharia a dica ao sair de QUALQUER
  // elemento filho, que é o contrário do que se quer.
  document.addEventListener('mouseout', function(ev){
    if(!ev.relatedTarget) limpar();
  }, true);
  document.addEventListener('mousedown', function(){ esconder(); }, true);
  document.addEventListener('wheel', function(){ esconder(); }, true);
  document.addEventListener('scroll', function(){ esconder(); }, true);
  document.addEventListener('keydown', function(){ esconder(); }, true);
  window.addEventListener('blur', function(){ limpar(); });

  var colhidas = colher(document);

  window.__hefDica = {
    instalada: true,
    colhidas: colhidas,
    aberta: function(){ return E.aberta; },
    texto: function(){ return E.aberta ? E.texto : ''; },
    quantas: function(){ return E.abriu; },
    // A VARREDURA, chamada pelo tique. Duas coisas, e as duas são de tempo:
    // um alvo cujo nó saiu do documento (um bloco trocado inteiro debaixo do
    // ponteiro) não tem mais dica a mostrar; e um bloco recém-trocado traz
    // `title` de volta, que é o popup do compositor voltando com ele.
    //
    // O CUSTO É UMA CONSULTA, e não uma varredura: `querySelector` para na
    // primeira ocorrência, e com a colheita feita não há ocorrência nenhuma.
    varrer: function(){
      if(E.alvo && !document.contains(E.alvo.el)){
        esconder(); E.alvo = null; E.texto = '';
      }
      if(document.querySelector('[title]')
         || document.querySelector('svg title:not([data-hef-dica])')){
        window.__hefDica.colhidas += colher(document);
      }
    },
    // O PRODUTO TROCANDO O TEXTO DA DICA QUE ESTÁ ABERTA. Sem isto, a dica de
    // um valor vivo (a taxa do giroscópio, a carga da bateria) congelaria no
    // texto do instante em que abriu.
    trocar: function(el, t){
      trocar_nome(el, String(t || ''));
      if(E.alvo && E.alvo.el === el){
        E.texto = String(t);
        if(E.aberta) caixa.textContent = E.texto;
      }
    },
  };
  return 'ok';
})();
"""


def _com_dono(ctx: pacotes.Contexto) -> list[str]:
    """Os `pN` que têm controle DE VERDADE agora — QUEM-TEM-DONO-01, 03/09/2026.

    NASCEU DE UMA REGRESSÃO MINHA, no mesmo dia. O passo `1c` do piloto (o que
    REABRE o cartão de um controle que chega) lia `carga["ocupados"]`, e a
    primeira versão daquela conta era `set(colunas)` — as colunas que a aba
    emitiu. Medido no DOM vivo, com UM controle na bancada: a `03-gatilhos`
    manda coluna para os QUATRO lugares, porque as vazias levam travessão de
    propósito, e o piloto passou a escrever `data-conectado="sim"` em dois
    lugares onde não há aparelho nenhum.

    **TER COLUNA NÃO É TER DONO.** A aba manda coluna para desenhar; quem diz
    quem está aqui é a MESA. Esta função é essa pergunta, e ela tem um dono só.

    A DECISÃO QUE ELA SUSTENTA é de 03/09/2026: *"tem que aparecer desligado
    enquanto não tem nenhum controle. A partir do momento que tiver, ele aparece
    o controle devidamente conectado."*
    """
    prefs: list[str] = []
    por_uniq = {str(c.get("uniq") or ""): c.get("pref") for c in ctx.mesa}
    for c in ctx.conectados:
        pref = por_uniq.get(str(c.get("uniq") or ""))
        if pref:
            prefs.append(str(pref))
    return prefs


#: casa: `pref` é POSIÇÃO (`mesa_viva.mesa_do_estado` reenumera de 1 a cada
class _EscolhaDaFita:
    """O único estado que o chip muda. Nada de perfil, nada de daemon."""

    def __init__(self) -> None:
        self.uniq = ""


ESCOLHA_DA_FITA = _EscolhaDaFita()


def _escolher_na_fita(ctx: pacotes.Contexto, o: dict[str, Any],
                      _ipc: Any) -> dict[str, Any]:
    """O clique no chip do `Selecionar:` — ele só ESCOLHE, e é todo o contrato.

    O QUE ELE NÃO FAZ, e está escrito porque é o risco desta cura: não troca de
    perfil, não fala com o daemon e não grava no disco dela. O `_ipc` chega e
    não é usado de propósito — a assinatura é a das dez abas.

    O `("*", …)` É O MESMO CORINGA DO RODAPÉ: a fita mora no `topo.html`, o
    esqueleto das dez, e registrá-la por página seria a mesma linha dez vezes.

    ELE RECUSA DIZENDO quando o `pref` clicado não está na mesa — um chip de um
    controle que saiu entre o desenho e o clique. Escolher calado o primeiro que
    sobrou é como a tela passa a mostrar um aparelho e a mexer noutro.

    E ELE MANDA A PRÓPRIA FRASE, que desde 13/09/2026 vai ao diário da janela e
    não à tela (TELA-CALADA-01: a tarja de rodapé que a mostrava saiu por pedido
    dela, *"em todas as abas da interface"*). Na tela, o clique responde pela
    piscada (`MS_DA_PISCADA`). O cartão fica de fora de propósito: ver
    `_endereco_do_chip`.
    """
    pref = str(o.get("pref") or "").strip()
    if pref == "todos":
        if not monta.cabe_o_todos(ctx.mesa):
            raise ValueError(
                "o chip `Todos` não se escolhe com um controle só na mesa: "
                "ele É a escolha.")
        ESCOLHA_DA_FITA.uniq = "todos"
        return {"recado": f"Esta aba passa a mirar os {len(ctx.mesa)} controles."}
    for c in ctx.mesa:
        if str(c.get("pref") or "") == pref:
            ESCOLHA_DA_FITA.uniq = norm_mac(str(c.get("uniq") or "")) or ""
            return {"recado": f"Esta aba passa a mirar o {pref.upper()}."}
    raise ValueError(
        f"o chip {pref!r} não está na mesa de agora — o controle saiu entre o "
        f"desenho da fita e o clique.")


def _registrar_a_fita() -> None:
    """O gesto da fita no despachante, uma vez só, por qualquer dos dois nomes."""
    if ("*", monta.GESTO_DA_FITA) not in pacotes.GESTOS:
        pacotes.gesto("*", monta.GESTO_DA_FITA)(_escolher_na_fita)


def _a_fita_desta_pagina_escolhe(pagina: str) -> bool:
    """`monta.a_fita_escolhe`, sem derrubar a janela numa página que não é aba."""
    try:
        return monta.a_fita_escolhe(pagina)
    except SystemExit:
        return False


def _pref_escolhido(mesa: list[dict[str, Any]]) -> str:
    """Que `pref` a fita acende AGORA, traduzido da escolha dela."""
    if not mesa:
        return "todos"
    se = ESCOLHA_DA_FITA.uniq
    if se == "todos":
        return "todos"
    if se:
        for c in mesa:
            if norm_mac(str(c.get("uniq") or "")) == se:
                return str(c["pref"])
    return str(mesa[0]["pref"])


def _fita(mesa: list[dict[str, Any]], pagina: str) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho."""
    #              chip nasce sem `--plastico` e cai no tom neutro do esqueleto.
    # veio é o `monta.fita`: o chip nasce sem `--plastico`, e o `.chip` cai
    #
    titulo = monta.casca_da_fita(pagina)
    try:
        return monta.fita(ativo=_pref_escolhido(mesa),
                          inerte=not _a_fita_desta_pagina_escolhe(pagina),
                          mesa=mesa, titulo=titulo)
    except (Exception, SystemExit):
        return ""


SELETOR = ("(document.querySelector('[data-gesto=\"%s\"],[data-hef-gesto=\"%s\"],"
           "[data-papel=\"%s\"],.r-%s')||{click(){}}).click()")

CLIQUE_COM_ALVO = r"""
(function(g, prefs){
  const sel = '[data-gesto="' + g + '"],[data-hef-gesto="' + g + '"],'
            + '[data-papel="' + g + '"],.r-' + g;
  for(const p of prefs){
    const bloco = document.querySelector('[data-controle="' + p + '"]');
    const dentro = bloco && bloco.querySelector(sel);
    if(dentro){ window.__hef.alvoPadrao = p; dentro.click(); return 'no bloco de ' + p; }
  }
  const el = document.querySelector(sel);
  if(!el) return 'NAO ACHEI NA PAGINA';
  // A MESMA REGRA DO OUVINTE — ver `SELETOR_DO_DONO`. Uma régua que resolvesse
  // o dono de outro jeito mediria um clique que o produto não faz.
  const dono = el.closest(
    '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
  if(dono){
    const q = dono.dataset.controle || dono.dataset.uniq || '';
    window.__hef.alvoPadrao = q;
    el.click();
    return 'no bloco de ' + q;
  }
  // FORA DE QUALQUER CONTROLE: o botão não diz em quem agir. A régua empresta
  // o primeiro conectado só para conseguir medir, e o relato marca.
  window.__hef.alvoPadrao = prefs[0] || '';
  el.click();
  return 'ALVO FORCADO ' + (prefs[0] || '(mesa vazia)');
})(%s, %s)
"""

PEDIR_A_PINTURA = r"""
(window.__hef && window.__hef.pintar) ? window.__hef.pintar(CARGA) : -1
"""

LER_CAMPOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('[data-campo],[data-papel],[data-hef]')){
    const chave = el.dataset.campo || el.dataset.papel || el.dataset.hef || '';
    // O DONO É O ASSENTO — ver `SELETOR_DO_DONO`. Sem esta lista, os quatro
    // campos que moram dentro do desenho compartilhado (`treme-e` e `treme-d`,
    // nas colunas do p1 e do p2 da `05-vibracao`) voltavam com o nome do MODELO
    // no lugar do assento, e a régua do mockup não os casava com a coluna que
    // os pinta.
    const bloco = el.closest(
      '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
    const dono = bloco ? (bloco.dataset.controle || bloco.dataset.uniq || '') : '';
    const alvo = el.dataset.hefAlvo || 'texto';
    let v;
    if(alvo === 'largura'){ v = el.style.width; }
    // O gêmeo vertical, na MESMA língua: `style.height` volta com a unidade
    // que o CSSOM acrescenta (`64%`), e `_declarado_neste_elemento` põe o `%`
    // do lado do pacote pelo mesmo ramo que já serve o `largura`.
    else if(alvo === 'altura'){ v = el.style.height; }
    else if(alvo === 'valor'){ v = ('value' in el) ? String(el.value ?? '') : ''; }
    // O ALVO `posicao`, na língua do pacote: `x,y` sem o `%`, ou vazio quando o
    // pontinho está no repouso. `regua_do_mockup._campo` lê o `style=` do
    // arquivo pelo mesmo par de variáveis.
    else if(alvo === 'posicao'){
      const px = el.style.getPropertyValue('--hef-x').trim().replace(/%$/, '');
      const py = el.style.getPropertyValue('--hef-y').trim().replace(/%$/, '');
      v = (px || py) ? (px + ',' + py) : '';
    }
    else if(alvo === 'cor'){ v = el.style.color; }
    else if(alvo === 'atributo'){
      // O ATRIBUTO, NA MESMA LÍNGUA DOS DOIS LADOS: o texto que ele guarda, ou
      // `''` quando não há atributo nenhum. `regua_do_mockup._campo` lê o mesmo
      // atributo do arquivo com o mesmo vazio por omissão — sem isso um SVG cujo
      // `data-colorway` o produto APAGOU (o aparelho não disse a cor) seria lido
      // como `null` de um lado e `''` do outro, e a régua acusaria a pintura
      // certa.
      const qual = (el.dataset.hefAtributo || '').trim().toLowerCase();
      v = el.getAttribute(qual) || '';
      // E O `title` PODE ESTAR EMPRESTADO — TOOLTIP-C1, 11/09/2026. Enquanto o
      // ponteiro está sobre o elemento, a camada da dica guarda o texto em
      // `data-hef-dica` para o popup do sistema não abrir junto. Sem esta
      // linha, a régua do mockup leria `''` de um endereço que o produto
      // acabou de pintar e acusaria a pintura CERTA — que é exatamente a
      // família de defeito que esta casa chama de instrumento falso.
      if(!v && qual === 'title') v = el.getAttribute('data-hef-dica') || '';
    }
    else if(alvo === 'marcado'){
      // NA MESMA LÍNGUA DO `escrever`: `sim` quando está marcado, vazio quando
      // não. Devolver `true`/`false` faria a régua do mockup comparar a palavra
      // do arquivo com um booleano do navegador e acusar toda pintura certa —
      // é a mesma cura de forma que o alvo `cor` já custou uma medição.
      v = el.checked ? 'sim' : '';
    }
    else if(alvo === 'classe'){
      // O QUE ESTE ELEMENTO MOSTRA, na MESMA língua em que o `escrever` recebe:
      // o `data-hef-quando` de quem está aceso, ou `sim` quando o alvo é
      // booleano. Devolver "quem do grupo está aceso" exigiria o leitor
      // conhecer o grupo, e o parser de Python do outro lado não conhece — as
      // duas leituras têm de casar endereço a endereço, e é essa igualdade que
      // a guarda do DOM virgem cobra a cada aba.
      const c = el.dataset.hefClasse || 'on';
      v = el.classList.contains(c) ? (el.dataset.hefQuando || 'sim') : '';
    }
    else { v = (el.textContent || '').replace(/\s+/g, ' ').trim(); }
    fora.push([chave, dono, alvo, v, el.dataset.hefVisto === '1']);
  }
  return JSON.stringify(fora);
})()
"""

VOLTAS_ATE_ASSENTAR = 20

#: que já existe (`window.__hef.pintar` devolve quantos valores escreveu) também
OBSERVAR_MUTACOES = r"""
(function(){
  window.__hef = window.__hef || {};
  if(window.__hef.observador){ window.__hef.observador.disconnect(); }
  const linhas = {};
  window.__hef.mutacoes = linhas;
  window.__hef.mutacoesTotal = 0;
  function endereco(no){
    let el = (no && no.nodeType === 1) ? no : (no ? no.parentElement : null);
    while(el && el.getAttribute){
      const c = el.getAttribute('data-campo') || el.getAttribute('data-papel')
                || el.getAttribute('data-hef');
      if(c) return c;
      if(el.classList && el.classList.contains('fita')) return '(a fita)';
      el = el.parentElement;
    }
    return '(sem endereco)';
  }
  function somar(campo, tipo, detalhe, nos){
    const k = campo + '|' + tipo + '|' + detalhe;
    let l = linhas[k];
    if(!l){ l = linhas[k] = {campo: campo, tipo: tipo, detalhe: detalhe,
                             n: 0, nos: 0}; }
    l.n += 1;
    l.nos += (nos || 0);
    window.__hef.mutacoesTotal += 1;
  }
  const obs = new MutationObserver(function(regs){
    for(const r of regs){
      const onde = endereco(r.target);
      if(r.type === 'attributes'){
        somar(onde, 'attributes', r.attributeName || '?', 0);
      } else if(r.type === 'childList'){
        somar(onde, 'childList', '(filhos)',
              r.addedNodes.length + r.removedNodes.length);
      } else {
        somar(onde, 'characterData', '(texto)', 0);
      }
    }
  });
  obs.observe(document.documentElement, {
    attributes: true, childList: true, characterData: true, subtree: true});
  window.__hef.observador = obs;
  window.__hef.mutacoesDesde = Date.now();
  return 'observando';
})()
"""

LER_MUTACOES = r"""
(function(){
  const h = window.__hef || {};
  const linhas = [];
  for(const k of Object.keys(h.mutacoes || {})) linhas.push(h.mutacoes[k]);
  linhas.sort(function(a, b){ return b.n - a.n; });
  return JSON.stringify({
    total: h.mutacoesTotal || 0,
    ms: Date.now() - (h.mutacoesDesde || Date.now()),
    // OS BLOCOS ADIADOS SAEM NA MESMA LEITURA: um bloco que o piloto NÃO
    // trocou porque havia um botão em voo dentro dele é um fato do mesmo
    // fenômeno, e sem ele a tabela diria só o que aconteceu, nunca o que foi
    // evitado.
    blocos_adiados: h.blocosAdiados || 0,
    linhas: linhas
  });
})()
"""

_METODO_DO_GESTO = {
    "atualizar": "daemon.reload", "modo-dualsense": "gamepad.emulation.set",
    "modo-xbox": "gamepad.emulation.set", "modo-navegacao": "mouse.emulation.set",
    "hefesto": "native.mode.set", "ativar": "profile.switch",
    "aplicar": "profile.reaplicar", "reconectar": "coop.sync",
}

PERIGOSOS: set[tuple[str, str]]


def _achatar(o: Any, prefixo: str = "") -> dict[str, Any]:
    """O estado do daemon como `{caminho: valor}` — para comparar antes/depois."""
    fora = {}
    if isinstance(o, dict):
        for k, v in o.items():
            fora.update(_achatar(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            fora.update(_achatar(v, f"{prefixo}.{i}"))
    else:
        fora[prefixo] = o
    return fora


RUIDO = ("visto_ha_s", "ha_s", "_count", "nascimento", "age_sec", "uptime",
         "inputs.", "motion_", "forwards", "counters.", "_ultimos_",
         "lx", "ly", "rx", "ry", "l2_raw", "r2_raw", "buttons",
         "battery_pct", "bt_mic")


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`."""
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


MUDOS_SEGUIDOS_QUE_VOLTARAM = 3


def _o_servico_so_demorou(erro: BaseException) -> bool:
    """O tique mudo foi DEMORA (`TimeoutError`), e não serviço fora do ar?"""
    return (isinstance(erro, TimeoutError)
            or isinstance(erro.__cause__, TimeoutError))


class FolgaDoServicoMudo:
    """O estado que o tique pinta quando o serviço não respondeu — RECONECTAR-SAMBA-02."""

    def __init__(self, folga: int = MUDOS_SEGUIDOS_QUE_VOLTARAM) -> None:
        self.folga = folga
        self.seguidos = 0
        self._ultimo_bom: dict[str, Any] | None = None

    def respondeu(self, estado: dict[str, Any]) -> None:
        """O serviço respondeu: zera a conta e guarda o estado para a folga."""
        self.seguidos = 0
        self._ultimo_bom = estado

    def mudo(self, erro: BaseException) -> dict[str, Any]:
        """O estado a pintar neste tique mudo: o último bom, ou a verdade (`{}`)."""
        self.seguidos += 1
        if (self._ultimo_bom is not None and self.seguidos <= self.folga
                and _o_servico_so_demorou(erro)):
            return self._ultimo_bom
        self._ultimo_bom = None
        return {}


class LeitorDoEstado:
    """O `state_full` lido FORA do laço do GTK — A-TELA-QUE-TRAVA-01, 15/09/2026.

    A QUEIXA DELA, com os dois controles na mesa: *"tem algo muito estranho
    travando a interface do app. como um todo."*  (noqa-acento: citação dela)

    A CAUSA JÁ ESTAVA ESCRITA DENTRO DO PRÓPRIO TIQUE, na A-TELA-SAMBA-01 de
    03/09: *"as DUAS VIAGENS de IPC do começo deste método são SÍNCRONAS — elas
    seguram o laço do GTK inteiro"*. O que aquela leva fez foi PULAR o tique
    seguinte, que encurta a fila e não desbloqueia nada: enquanto o
    `estado_do_daemon()` não volta, o laço do GTK não roda, e a janela inteira
    — rolagem, clique, `:hover`, o cursor de texto — fica parada.

    O NÚMERO, medido no diário dela (`interface.log`, a sessão de 14/09):

    ========  ======  ==========  ===========
    aba       lentos  IPC médio   IPC pior
    ========  ======  ==========  ===========
    01-jogar     244      568 ms     6.016 ms
    02-controles  55      929 ms     2.665 ms
    09-sistema     7      678 ms     2.002 ms
    ========  ======  ==========  ===========

    612 tiques lentos numa sessão, e em 457 deles o IPC é **80% ou mais** do
    custo. Seis segundos de janela morta é o que ela chama de travar.

    A CURA É DE FORMA, e não de velocidade: a leitura passa a um fio próprio,
    que lê na mesma cadência de antes (uma por tique) e deixa a resposta num
    escaninho. O tique pega o que está lá e segue — **nunca espera**. Um daemon
    que demore seis segundos deixa a tela com dado de seis segundos atrás, que é
    exatamente o que ela já mostrava enquanto congelava; o que muda é que a
    janela continua andando.

    A FOLGA CONTINUA CONTANDO RESPOSTAS, E NÃO TIQUES, e é por isso que existe a
    `self._geracao`: sem ela, uma leitura que falhasse seria entregue a dez
    tiques por segundo, e os `MUDOS_SEGUIDOS_QUE_VOLTARAM` da
    `FolgaDoServicoMudo` — três respostas mudas — queimariam em 300 ms. O
    tique só mexe na folga quando a geração ANDA; entre duas respostas ele
    repinta o que já tinha.

    O QUE ESTA CLASSE NÃO FAZ: pedir mais depressa. O `intervalo` é o mesmo
    `TIQUE_MS`, então o daemon recebe o mesmo número de perguntas por segundo
    que recebia — a mudança é quem espera pela resposta, não quantas são.
    """

    SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA = 1.0

    def __init__(
        self,
        ler: Callable[[], dict[str, Any]] | None = None,
        *,
        intervalo: float = TIQUE_MS / 1000.0,
    ) -> None:
        self._ler = ler if ler is not None else mesa_viva.estado_do_daemon
        self._intervalo = intervalo
        self._trava = threading.Lock()
        self._estado: dict[str, Any] | None = None
        self._erro: BaseException | None = None
        self._geracao = 0
        self._ultima_viagem_ms = 0.0
        self._parar = threading.Event()
        self._a_vista = threading.Event()
        self._a_vista.set()
        self._acordar = threading.Event()
        self._fio: threading.Thread | None = None

    def ultimo(self) -> tuple[dict[str, Any] | None, BaseException | None, int]:
        """O estado, o erro e a geração de agora. Não espera por ninguém."""
        with self._trava:
            return self._estado, self._erro, self._geracao

    def ultima_viagem_ms(self) -> float:
        """Quanto a última leitura do serviço custou, em ms."""
        with self._trava:
            return self._ultima_viagem_ms

    def comecar(self) -> None:
        """Semeia UMA leitura e sobe o fio. Chamar duas vezes não sobe dois."""
        if self._fio is not None:
            return
        self._uma_leitura()
        self._fio = threading.Thread(
            target=self._laco, name="hefesto-estado", daemon=True)
        self._fio.start()

    def parar(self) -> None:
        """Pede o fim do fio. Ele é `daemon`, então o processo não o espera."""
        self._parar.set()
        self._acordar.set()

    def pausar(self) -> None:
        """A janela foi escondida: o fio passa a ler de segundo em segundo."""
        self._a_vista.clear()
        self._acordar.clear()

    def retomar(self) -> None:
        """A janela voltou: o fio acorda, lê já e volta à cadência do tique."""
        self._a_vista.set()
        self._acordar.set()

    def _uma_leitura(self) -> None:
        t0 = time.perf_counter()
        try:
            st = self._ler()
        except Exception as erro:  # noqa: BLE001 — o motivo viaja para a folga
            with self._trava:
                self._estado, self._erro = None, erro
                self._geracao += 1
                self._ultima_viagem_ms = (time.perf_counter() - t0) * 1000
        else:
            with self._trava:
                self._estado, self._erro = st, None
                self._geracao += 1
                self._ultima_viagem_ms = (time.perf_counter() - t0) * 1000

    def _laco(self) -> None:
        while not self._parar.is_set():
            if self._a_vista.is_set():
                self._parar.wait(self._intervalo)
            else:
                self._acordar.wait(max(self._intervalo,
                                       self.SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA))
                self._acordar.clear()
            if self._parar.is_set():
                return
            self._uma_leitura()


class Piloto:
    #: foi por isso que o daemon a deixou FORA do `state_full` e atrás de um
    #: do `TIQUE_MS`** — o portão `citacoes-no-codigo` foi quem mostrou: QUATRO
    SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS = 4.0
    SEGUNDOS_DE_ESPERA_DOS_EXTERNOS = 3.0

    TIQUES_ENTRE_CARGAS_INTEIRAS = 10
    CUSTOS_GUARDADOS = 6000

    def __init__(self, args: argparse.Namespace) -> None:
        from collections import deque

        self._abertura: dict[str, float] = {"piloto": time.monotonic()}
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        self.pinturas: dict[str, list[int]] = {}
        self.tiques: dict[str, int] = {}
        self.trocas: dict[str, int] = {}
        self.visitadas: list[str] = []
        self.custos: deque[float] = deque(maxlen=self.CUSTOS_GUARDADOS)
        self.gestos: list[dict[str, Any]] = []
        self.aplicados: list[str] = []
        self.recusados: list[str] = []
        self.provas: list[dict[str, Any]] = []
        self.desfechos: dict[str, tuple[str, str]] = {}
        self._onde_clicou: dict[str, str] = {}
        #: botão e vai ao diário (`_recusou_dizendo`).
        self._vivos: dict[str, str] = {}
        self.vivos_atendidos: list[str] = []
        self.vivos_recusados: list[str] = []
        self.vivos_descartados = 0
        self._fila: list[str] = []
        self.cravados: dict[str, list[regua_do_mockup._Campo]] = {}
        self.pristino: dict[str, list[list[str]]] = {}
        self.vereditos: dict[str, list[regua_do_mockup._Veredito]] = {}
        self.cegueiras: list[str] = []
        self._fila_de_abas: list[str] = []
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora: dict[str, Any] = {}
        self._mesa_de_agora: list[dict[str, Any]] = []
        self._voltas_do_contador = 0
        self._mutacoes_lidas = False
        self.mutacoes: dict[str, Any] = {}
        self._pulados_por_voo = 0
        self._pulados_por_custo = 0
        self._pintura_no_ar = False
        self._pular = 0
        self._folga = FolgaDoServicoMudo()
        #: repinta o estado que já tinha e NÃO mexe na folga — ver a classe.
        self._geracao_vista = -1
        self._st_de_agora: dict[str, Any] = {}
        self.custo_do_ipc: deque[float] = deque(maxlen=self.CUSTOS_GUARDADOS)
        self._escondida = False
        self._geracao_na_volta: int | None = None
        self._pintada: dict[tuple[str, ...], tuple[Any, Any]] | None = None
        self._ate_a_inteira = 0
        self._moldes: dict[str, frozenset[str]] = {}
        #: EXTERNOS-01, 06/09/2026. A lista é a ÚLTIMA resposta boa; o carimbo
        #: A LISTA NÃO SE APAGA ENTRE LEITURAS, e é escolha: entre um tique e o
        self._externos: list[dict[str, Any]] = []
        self._externos_lidos_em = 0.0
        self._externos_no_ar = False

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._navegou,
            ao_morrer_a_pagina=self._a_pagina_morreu,
            oculta=args.oculta,
            esperar_a_pintura=True,
            # `scripts/check_a_janela_nao_confessa.py`, que nasceu com esta
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        self.view.connect("load-changed", self._carregou)
        self._abertura["janela"] = time.monotonic()
        _importar_as_abas(self.tela)
        self._ctx_de_agora = pacotes.Contexto(state={})
        #: O `state_full` lido FORA do laço do GTK — A-TELA-QUE-TRAVA-01. O fio
        self._estado_vivo = LeitorDoEstado()
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)

        ponte.escolher_arquivo = self._escolher_arquivo
        ponte.salvar_arquivo = self._salvar_arquivo

    def _dialogo(self, titulo: str, acao: Any, rotulo: str, *,
                 sugestao: str = "", padrao: str = "*") -> str | None:
        """Um `FileChooserDialog` modal, e ele RODA NO LAÇO DO GTK.

        POR QUE `Gtk.Dialog.run()` E NÃO UM CALLBACK: o gesto está numa thread
        (os gestos correm fora do laço, porque `daemon.reload` leva 9,5 s), e
        precisa do caminho para seguir. `run()` bombeia o laço do GTK por
        dentro, então a janela continua viva enquanto ela escolhe.

        COM A JANELA OCULTA NÃO HÁ DIÁLOGO: uma `Gtk.OffscreenWindow` não tem
        onde pôr um modal, e abrir um sem pai o jogaria NA TELA DELA — que é
        exatamente o que `--oculta` existe para impedir. Nesse caso devolve
        `None`, e o gesto o lê como "cancelou".
        """
        if self.args.oculta:
            print(f"[seletor] {titulo}: a janela está oculta, não abro diálogo",
                  file=sys.stderr)
            return None
        dlg = Gtk.FileChooserDialog(title=titulo, transient_for=self.tela.janela,
                                    action=acao)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        rotulo, Gtk.ResponseType.ACCEPT)
        if sugestao:
            dlg.set_current_name(pathlib.Path(sugestao).name)
            with contextlib.suppress(Exception):
                dlg.set_current_folder(str(pathlib.Path(sugestao).parent))
        if padrao != "*":
            f = Gtk.FileFilter()
            f.set_name(padrao)
            f.add_pattern(padrao)
            dlg.add_filter(f)
        try:
            escolhido = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        finally:
            dlg.destroy()
        return escolhido

    def _escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.OPEN, "Abrir", padrao=padrao)

    def _salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.SAVE, "Guardar",
                             sugestao=sugestao)

    def _com_uniq(self, o: dict[str, Any]) -> dict[str, Any]:
        """O clique com o `uniq` do controle resolvido contra a mesa de agora."""
        pref = str(o.get("controle") or "")
        for c in self._mesa_de_agora:
            if c.get("pref") == pref or str(c.get("uniq") or "") == pref:
                return {**o, "uniq": str(c.get("uniq") or "")}
        return o

    def _gesto_vivo(self, o: dict[str, Any], pagina: str, nome: str) -> None:
        """A quarta porta — o gesto que LÊ enquanto ela digita, e não grava."""
        serial = str(o.get("vivo") or "")
        chave = str(o.get("vivoChave") or f"{pagina}:{nome}")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.vivos_recusados.append(f"{pagina}:{nome} (sem dono)")
            print(f"[vivo sem dono] {pagina} · {nome} — o `data-hef-vivo` "
                  f"aponta para um gesto que ninguém registrou", file=sys.stderr)
            return
        grava = (pacotes.GESTOS_QUE_MEXEM.get((pagina, nome))
                 or pacotes.GESTOS_QUE_MEXEM.get(("*", nome)) or "")
        if grava:
            self.vivos_recusados.append(f"{pagina}:{nome} (grava: {grava})")
            print(f"[vivo recusado] {pagina} · {nome} declara gravação "
                  f"({grava}) — a quarta porta é de LEITURA, e ela dispara a "
                  f"cada tecla", file=sys.stderr)
            return
        self._vivos[chave] = serial
        o = self._com_uniq(o)

        def trabalhar() -> None:
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                self.vivos_recusados.append(
                    f"{pagina}:{nome} ({type(erro).__name__}: {erro})")
                print(f"[vivo falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
            else:
                GLib.idle_add(
                    lambda r=resposta: self._vivo_voltou(pagina, nome, chave,
                                                         serial, r))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _vivo_voltou(self, pagina: str, nome: str, chave: str, serial: str,
                     resposta: object) -> bool:
        """A leitura chegou. Se ainda é a mais nova, ela pinta."""
        if self._vivos.get(chave) != serial:
            self.vivos_descartados += 1
            return False
        if not isinstance(resposta, dict) or not resposta:
            self.vivos_atendidos.append(f"{pagina}:{nome}")
            return False
        proibidas = [k for k in CHAVES_QUE_O_VIVO_RECUSA if k in resposta]
        if proibidas:
            self.vivos_recusados.append(
                f"{pagina}:{nome} (devolveu {', '.join(proibidas)})")
            print(f"[vivo recusado] {pagina} · {nome} devolveu "
                  f"{', '.join(proibidas)} — a quarta porta dispara a cada "
                  f"tecla, e essas chaves trocam HTML inteiro ou mandam "
                  f"frase", file=sys.stderr)
            return False
        self.vivos_atendidos.append(f"{pagina}:{nome}")
        _esquecer_a_pintura(self)
        self._js(f"window.__hef && window.__hef.pintar({_json(resposta, pagina=pagina)})")
        return False

    def _gesto(self, o: dict[str, Any]) -> None:
        """tela → Python, já em JSON. Quem recusa o que não é objeto é a ponte."""
        if "gesto" not in o and o.get("visibilidade") in ("escondida", "vista"):
            self._a_janela_mudou(o.get("visibilidade") == "escondida")
            return
        _esquecer_a_pintura(self)
        self.gestos.append(o)
        nome = str(o.get("gesto") or "")
        pagina = str(o.get("pagina") or self.pagina)  # (noqa-acento: verbo)  (nome de variável)
        if str(o.get("vivo") or ""):
            self._gesto_vivo(o, pagina, nome)
            return
        voo = str(o.get("voo") or "")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.recusados.append(f"{pagina}:{nome}")
            self.desfechos[f"{pagina}:{nome}"] = ("sem dono", "")
            print(f"[gesto sem dono] {pagina} · {nome} · {o.get('texto', '')!r}")
            self._pousou(voo, False)
            return
        o = self._com_uniq(o)
        # O `uniq` DO CLIQUE vai aos dois relatos (`_recusou_dizendo` e
        alvo = norm_mac(str(o.get("uniq") or "")) or ""

        # dela: `daemon.reload` leva **9,5 segundos** — `daemon.resume` leva 1
        def trabalhar() -> None:
            desta_vez: tuple[str, str] = ("", "")
            so_armou = False
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                desta_vez = ("recusou dizendo", f"{type(erro).__name__}: {erro}")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                # relatos. Ela ia à tela de 02/09 a 13/09/2026 — ver
                # `_recusou_dizendo`, que guarda a história.
                GLib.idle_add(
                    lambda x=erro: self._recusou_dizendo(pagina, nome, alvo, x))
            else:
                desta_vez = ("aplicou", "")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                so_armou = (isinstance(resposta, dict)
                            and bool(resposta.get(CHAVE_DO_CLIQUE_QUE_SO_ARMOU)))
                GLib.idle_add(lambda r=resposta: self._deu_certo_dizendo(
                    pagina, nome, alvo, self._o_arranjo_relido(pagina, r)))
            finally:
                certo: bool | None = (None if so_armou
                                      else desta_vez[0] == "aplicou")
                GLib.idle_add(lambda v=voo, c=certo: self._pousou(v, c))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _a_janela_mudou(self, escondida: bool) -> None:
        """A página disse se alguém pode vê-la. Escondida, a janela não trabalha."""
        if escondida == self._escondida:
            return
        self._escondida = escondida
        _esquecer_a_pintura(self)
        if escondida:
            self._geracao_na_volta = None
            self._estado_vivo.pausar()
            _soltar_as_ondas()
            print("[janela] escondida: o tique parou", file=sys.stderr)
            return
        self._geracao_na_volta = self._estado_vivo.ultimo()[2]
        self._estado_vivo.retomar()
        print("[janela] à vista: o tique voltou", file=sys.stderr)

    def _moldes_da_pagina(self) -> frozenset[str]:
        """As chaves de lista que um `data-hef-molde` conta nesta página."""
        import re

        if self.pagina not in self._moldes:
            try:
                texto = onde.pagina(self.pagina, publicado=True).read_text(encoding="utf-8")
            except OSError:
                texto = ""
            self._moldes[self.pagina] = frozenset(
                re.findall(r'data-hef-molde-conta="([^"]+)"', texto))
        return self._moldes[self.pagina]

    def _pousou(self, voo: str, certo: bool | None = None) -> bool:
        """O botão volta do voo — a classe sai e o rótulo original é devolvido."""
        if not voo:
            return False
        _esquecer_a_pintura(self)
        self._js(
            f"window.__hef && window.__hef.voltouDoVoo("
            f"{_json(voo, pagina=self.pagina)}, {_json(certo, pagina=self.pagina)})"
        )
        return False

    def _deu_certo(self, pagina: str, nome: str, resposta: object = None) -> bool:
        """O gesto voltou. Se ele TROUXE ALGO, o que trouxe vai para a tela.

        O CAMINHO DE VOLTA, e por que ele precisou existir (01/09/2026): o gesto
        devolvia `None` e não havia por onde escrever um resultado na página.
        Isso deixou sem dono os botões cuja promessa é MOSTRAR — "Ver os
        plugins carregados" e "Ver detalhes" da aba Sistema. O daemon atende
        `plugin.list` desde sempre; o que faltava era o retorno. Um gesto que
        chamasse `plugin.list` e jogasse a lista fora seria o botão que responde
        calado — o defeito que esta casa tem nome para.

        A CARGA É A MESMA DA PINTURA, de propósito: `{"mesa": {...}}`,
        `{"colunas": {...}}`. Nenhum segundo vocabulário nasce aqui, e um gesto
        que devolve endereço escreve no mesmo lugar em que a pintura escreveria
        — logo o tique seguinte não briga com ele, sobrescreve com o valor vivo.
        """
        self.aplicados.append(f"{pagina}:{nome}")
        if isinstance(resposta, dict) and resposta:
            _esquecer_a_pintura(self)
            self._js(f"window.__hef && window.__hef.pintar({_json(resposta, pagina=pagina)})")
            print(f"[gesto] {pagina} · {nome} → aplicado, e a resposta foi para a tela")
            return False
        print(f"[gesto] {pagina} · {nome} → aplicado")
        return False

    def _recusou_dizendo(self, pagina: str, nome: str, uniq: str,
                         erro: BaseException) -> bool:
        """A recusa do produto chegando ao DIÁRIO — e ao botão, pela piscada."""
        print(f"[gesto falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
        return False

    def _deu_certo_dizendo(self, pagina: str, nome: str, uniq: str,
                           resposta: object = None) -> bool:
        """O gesto voltou SEM levantar — e agora a tela dela sabe disso.

        **O DEFEITO, e a decisão que o fecha.** Até 04/09/2026 a interface nova
        só falava quando RECUSAVA: um gesto que dava certo imprimia
        `[gesto] … → aplicado` no terminal de quem lançou a janela, e quem clica
        não lê terminal. **Cinco linhas do CSV paravam neste mesmo buraco**, em
        cinco abas (02, 03, 05, 06 e 09). A decisão dela, no mesmo dia:

            *"No próprio cartão, como a recusa."*   — D-01

        DUAS RECOMENDAÇÕES PROPUNHAM OUTRO CANAL e as duas foram recusadas por
        UM FATO, UM SINAL — e é o que faz esta peça fechar as cinco abas de uma
        vez em vez de virar cinco peças que divergem. Esta metade continua
        valendo inteira.

        A OUTRA METADE CADUCOU EM 05/09/2026, e a data importa. Este parágrafo
        dizia que ELA recusara *o campo que pisca* (aba 03) e *a faixa embaixo
        da grade* (aba 05), e mandava: **"não construa nenhum dos dois"**. Quem
        recusou foi o PO, lendo a D-01 (*"no próprio cartão, como a recusa"*)
        como se ela fechasse a FORMA — os conflitos C-3 e C-6 de
        `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` são dele, não
        dela. Em 05/09 ela respondeu a `03-Q4` vendo as quatro formas lado a
        lado e escolheu o campo que pisca. **A palavra dela vence a leitura que
        o PO fez da palavra dela.**

        E a piscada não é um segundo canal para o mesmo fato: é o mesmo fato num
        sinal mais barato. O cartão passa a dizer só o que tem notícia, e as
        duas peças deixam de disputar.

        A FRASE É DO DONO DO ASSUNTO, e não deste arquivo: um gesto que devolva
        `{"recado": "…"}` manda a própria, e o piloto a leva. O `recado`
        SAI da carga antes de a resposta ir para a pintura: ele não é endereço de
        página nenhuma, e deixá-lo entrar faria o `escrever()` procurar um
        `data-campo="recado"` que não existe.

        E QUANDO NÃO HÁ FRASE, A TELA NÃO FALA — 05/09/2026, decisão dela na
        `03-Q4`. Até aqui valia uma frase do piloto (*"Pronto."*), e ela tirou
        a palavra nova da tela:

            *"nada muda de lugar e nenhuma palavra nova entra na tela"*

        A regra que isso escrevia — *"quando ele tem NOTÍCIA, a tela fala"* —
        caducou em 13/09/2026 (nota abaixo). Quem pisca continua sendo o
        `voltouDoVoo`, no pouso, e agora a piscada é a resposta inteira do
        sucesso na tela.

        ELE NÃO SUBSTITUI O `_deu_certo`, ele o EMBRULHA — e isso é de propósito:
        `_deu_certo` é o caminho da carga de volta (`plugin.list`, "Ver
        detalhes"), tem régua própria e não precisa saber que existe recado.

        **A METADE DO SUCESSO DA D-01 CADUCOU EM 13/09/2026** — TELA-CALADA-01,
        pela palavra dela, com a foto do rodapé: *"essas frases de status que
        aparecem no rodapé isso não deveria estar aparecendo"*, *"em todas as
        abas da interface"*. O recado de sucesso chegava por três portas — o
        cartão, as faixas `data-hef-recados` da 01 e da 05, e a aba seguinte —,
        e as três passavam por um depósito de tom `sucesso` feito aqui. **A frase
        continua vindo do dono e continua saindo da carga**; o que mudou é o
        destino: o diário da janela, como `[relato] <página> · <gesto>: <frase>`
        (o desenho que a aba 10 ganhou no mesmo dia, `a10_perfis._anotar`).
        **A metade da recusa caducou no mesmo dia** (FRASES-E-DICAS-01): ver
        `_recusou_dizendo`.

        E A CHAVE `armou` SAI JUNTO COM O `recado` — 13/09/2026. Ela é sinal
        para o POUSO (`CHAVE_DO_CLIQUE_QUE_SO_ARMOU`, lida em `_gesto`), e não
        endereço de página.
        """
        frase = ""
        if isinstance(resposta, dict):
            bruto = resposta.get("recado")
            if isinstance(bruto, str) and bruto.strip():
                frase = bruto.strip()
            fora_da_pintura = ("recado", CHAVE_DO_CLIQUE_QUE_SO_ARMOU)
            if any(k in resposta for k in fora_da_pintura):
                resposta = {k: v for k, v in resposta.items()
                            if k not in fora_da_pintura}
        if frase:
            print(f"[relato] {pagina} · {nome}: {frase}", file=sys.stderr)
        return self._deu_certo(pagina, nome, resposta)

    def _a_pagina_morreu(self, motivo: str) -> None:
        """O processo web do WebKit caiu. A janela já está recarregando; aqui se DIZ."""
        print(f"[página morreu] {motivo} — a pintura pausou até a página voltar",
              file=sys.stderr)
        self.pronto = False


    def _navegou(self, titulo: str) -> None:
        """Ela clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view: Any, evento: Any) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            self._a_mesma_recarregou(nova)
            return
        if nova != self.pagina:
            pacotes.largar_o_que_as_abas_seguram(ponte)
        self.pagina = nova
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        self.pronto = False
        self._antes_de_instalar()

    def _a_mesma_recarregou(self, nova: str) -> None:
        """O MAPA RECARREGADO VOLTA COM O ARRANJO — O-MAPA-QUE-ELA-CORRIGE-01."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if nova != arranjo_desta_maquina.PAGINA or nova != self.pagina or not self.pronto:
            return

        def respondeu(valor: Any, erro: Any) -> None:
            if erro is None and str(valor) == "false" and self.pagina == nova:
                self.pronto = False
                self._antes_de_instalar()

        self.ponte.perguntar("String(!!window.__hef)", respondeu)

    def _instalar(self) -> None:
        self._antes_de_instalar()

    def _antes_de_instalar(self) -> None:
        """O DOM VIRGEM é lido AQUI, e é o único instante em que ele existe."""
        self._voltas_do_contador = 0
        if self.args.prova_de_mockup and self.pagina not in self.pristino:
            pagina = self.pagina

            def retratou(valor: Any, erro: Any) -> None:
                self._leu_virgem(pagina, valor, erro)

            self.ponte.perguntar(LER_CAMPOS, retratou)
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _dica_instalada(self, valor: Any, erro: Any) -> None:
        """A camada da dica respondeu — ou a página ficou com a dica do sistema."""
        if erro is not None:
            self.cegueiras.append(f"{self.pagina}: a camada da dica não instalou — {erro}")
            print(f"ERRO: a camada da dica não instalou em {self.pagina}: {erro}",
                  file=sys.stderr)
            return
        resposta = str(valor)
        if resposta not in ("ok", "ja"):
            self.cegueiras.append(
                f"{self.pagina}: a camada da dica respondeu {resposta!r}")

    def _entregar_o_arranjo(self) -> None:
        """Entrega ao `mapa-das-portas` o gabinete de quem abriu a janela."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        pagina = self.pagina

        def ler() -> None:
            dado = arranjo_desta_maquina.para_a_pagina()
            if dado is not None:
                GLib.idle_add(lambda: self._entregar(pagina, dado, reexame=False))

        threading.Thread(target=ler, name="arranjo-desta-maquina", daemon=True).start()

    def _entregar(self, pagina: str, dado: Any, *, reexame: bool = False,
                  como: str = "") -> bool:
        """O arranjo lido vai à página — no laço do GTK, e só se ela ainda é a dele."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if self.pagina != pagina:
            return False
        js = arranjo_desta_maquina.js_da_entrega(dado, reexame=reexame, como=como)
        self.ponte.perguntar(js, self._arranjo_entregue)
        return False

    def _o_arranjo_relido(self, pagina: str, resposta: object) -> object:
        """A resposta do «Examinar» traz um arranjo: ele sai da carga e vai à página."""
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina as arranjo

        if pagina != arranjo.PAGINA or not isinstance(resposta, dict):
            return resposta
        modos = ((arranjo.CHAVE_DA_ENTREGA, arranjo.COMO_REEXAME),
                 (arranjo.CHAVE_DEPOIS_DE_GRAVAR, arranjo.COMO_GRAVOU))
        achadas = [(chave, como) for chave, como in modos if chave in resposta]
        if not achadas:
            return resposta
        for chave, como in achadas:
            self._entregar(pagina, resposta[chave], como=como)
        return {k: v for k, v in resposta.items() if k not in dict(achadas)}

    def _arranjo_entregue(self, valor: Any, erro: Any) -> None:
        if erro is not None:
            self.cegueiras.append(f"{self.pagina}: o arranjo desta máquina não "
                                  f"chegou à página — {erro}")
            return
        if str(valor) != "ok":
            self.cegueiras.append(f"{self.pagina}: a página recusou o arranjo "
                                  f"desta máquina — respondeu {valor!r}")

    def _leu_virgem(self, pagina: str, valor: Any, erro: Any) -> None:
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li o DOM virgem — {erro}")
            self.pristino[pagina] = []
            return
        try:
            self.pristino[pagina] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: o DOM virgem não veio em JSON — {e}")
            self.pristino[pagina] = []

    def _instalado(self, _valor: Any, erro: Any) -> None:
        if erro is not None:
            print(f"ERRO: o bootstrap não instalou em {self.pagina}: {erro}", file=sys.stderr)
            return
        self.pronto = True
        # que é o defeito que ela relatou *"em todas as paginas"*.  # noqa-acento: citação literal dela
        self.ponte.perguntar(DICA_DA_CASA, self._dica_instalada)
        from hefesto_dualsense4unix.interface import arranjo_desta_maquina

        if self.pagina == arranjo_desta_maquina.PAGINA:
            self._entregar_o_arranjo()
        self._estado_vivo.comecar()
        _esquecer_a_pintura(self)
        _soltar_as_ondas()
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    def _contexto(self, st: dict[str, Any], *,
                  perguntar: bool = True) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        self.leitor.esquecer_ausentes(
            {str(c.get("uniq") or "") for c in ctx_conectados})
        if perguntar:
            self.leitor.disparar(ctx_conectados)
        conectados = ctx_conectados
        if perguntar:
            self._talvez_ler_os_externos()
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={},
                               externos=list(self._externos), escolhido=_pref_escolhido(mesa))
        return ctx, para_pref

    def _talvez_ler_os_externos(self) -> None:
        """Pede `controller.list {external: true}` no tique LENTO, em thread."""
        agora = time.monotonic()
        if self._externos_no_ar:
            return
        if (agora - self._externos_lidos_em
                < self.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS):
            return
        self._externos_lidos_em = agora
        self._externos_no_ar = True

        def perguntar() -> None:
            try:
                r = ponte.resultado(
                    "controller.list",
                    timeout=self.SEGUNDOS_DE_ESPERA_DOS_EXTERNOS,
                    external=True,
                )
            except Exception as e:
                print(f"[externos] não li o inventário: {e}", file=sys.stderr)
                return
            finally:
                self._externos_no_ar = False
            from hefesto_dualsense4unix.app.actions.home_actions import externos_na_mesa

            bruto = r.get("external") if isinstance(r, dict) else None
            self._externos = externos_na_mesa(
                None, bruto if isinstance(bruto, list) else ())

        threading.Thread(target=perguntar, daemon=True).start()

    def _da_resposta(
        self, st: dict[str, Any] | None, erro: BaseException | None
    ) -> dict[str, Any]:
        """O estado a pintar a partir de UMA resposta do leitor — boa ou muda."""
        if erro is not None:
            print(f"[daemon mudo] {erro}", file=sys.stderr)
            return self._folga.mudo(erro)
        bom = st if isinstance(st, dict) else {}
        self._folga.respondeu(bom)
        return bom

    def _estado_do_tique(self) -> dict[str, Any]:
        """O estado que ESTE tique pinta — e ele não espera por ninguém."""
        st_lido, erro_lido, geracao = self._estado_vivo.ultimo()
        if geracao != self._geracao_vista:
            self._geracao_vista = geracao
            self._st_de_agora = self._da_resposta(st_lido, erro_lido)
        return self._st_de_agora

    def _o_contexto_anda_escondido(self) -> None:
        """Com a janela escondida, o CONTEXTO anda com o leitor; a pintura não."""
        if self._estado_vivo.ultimo()[2] == self._geracao_vista:
            return
        st = self._estado_do_tique()
        try:
            ctx, _ = self._contexto(st, perguntar=False)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx

    def _esperando_o_estado_novo(self) -> bool:
        """A janela voltou e o leitor ainda não trouxe resposta depois disso?"""
        if self._geracao_na_volta is None:
            return False
        if self._estado_vivo.ultimo()[2] == self._geracao_na_volta:
            return True
        self._geracao_na_volta = None
        return False

    def _o_que_mandar(self, carga: dict[str, Any]) -> dict[str, Any]:
        """A carga que ESTE tique manda à página: inteira, só a diferença, ou nada."""
        agora = _achatar_a_carga(carga)
        antes, self._pintada = self._pintada, agora
        self._ate_a_inteira -= 1
        if antes is None or self._ate_a_inteira <= 0:
            self._ate_a_inteira = self.TIQUES_ENTRE_CARGAS_INTEIRAS
            return carga
        dif = _o_que_mudou(antes, agora)
        if _a_diferenca_muda_a_forma(dif, self._moldes_da_pagina()):
            self._ate_a_inteira = self.TIQUES_ENTRE_CARGAS_INTEIRAS
            return carga
        return dif

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        if self._escondida or self._esperando_o_estado_novo():
            self._o_contexto_anda_escondido()
            pacotes.bater_os_coracoes(self._ctx_de_agora, ponte)
            return True
        if self._pintura_no_ar:
            self._pulados_por_voo += 1
            return True
        if self._pular > 0:
            self._pular -= 1
            self._pulados_por_custo += 1
            return True
        if self.args.prova_de_mockup:
            if self.pagina not in self.pristino:
                return True
            self._voltas_da_aba += 1
            if self._voltas_da_aba >= self.args.voltas_por_aba and not self._medindo:
                self._medindo = True
                pagina = self.pagina

                def mediu(valor: Any, erro: Any, p: str = pagina) -> None:
                    self._fechou_a_aba(p, valor, erro)

                self.ponte.perguntar(LER_CAMPOS, mediu)
        t0 = time.perf_counter()
        st = self._estado_do_tique()

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        t_ipc = (time.perf_counter() - t0) * 1000
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx
        pacotes.bater_os_coracoes(ctx, ponte)
        t_pacote0 = time.perf_counter()
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except Exception as e:
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            pacote = {}
        t_pacote = (time.perf_counter() - t_pacote0) * 1000

        carga = pacotes.normalizar(pacote, para_pref)
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        carga["fita"] = _fita(ctx.mesa, self.pagina)

        alvo = (_pref_escolhido(ctx.mesa)
                if _a_fita_desta_pagina_escolhe(self.pagina) else "")
        carga["alvo"] = "" if alvo == "todos" else alvo

        pacotes.apagar_os_lugares_sem_dono(carga, _com_dono(ctx), pagina=self.pagina)


        def contou(valor: Any, erro: Any) -> None:
            self._pintura_no_ar = False
            if erro is not None:
                _esquecer_a_pintura(self)
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            if n < 0:
                _esquecer_a_pintura(self)
                self.trocas[self.pagina] = self.trocas.get(self.pagina, 0) + 1
                return
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
            if n > 0:
                self.pinturas.setdefault(self.pagina, []).append(n)
                abertura = getattr(self, "_abertura", None)
                if abertura is not None and "pintura" not in abertura:
                    Piloto._contar_a_abertura(self)

        enviar = self._o_que_mandar(carga)
        if enviar:
            pedido = PEDIR_A_PINTURA.replace("CARGA", _json(enviar, pagina=self.pagina))
            self._pintura_no_ar = True
            self.ponte.perguntar(pedido, contou)
        else:
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
        self._carga_de_agora = carga
        self.voltas += 1
        custo = (time.perf_counter() - t0) * 1000
        self.custos.append(custo)
        self.custo_do_ipc.append(t_ipc)
        # tique que custa mais que `TIQUE_MS` já entregou dado atrasado; mandar
        if custo > TIQUE_MS:
            self._pular += 1
            viagem = getattr(getattr(self, "_estado_vivo", None), "ultima_viagem_ms", None)
            daemon_ms = viagem() if callable(viagem) else 0.0
            print(f"[tique lento] {self.pagina}: {custo:.0f} ms "
                  f"(pacote {t_pacote:.0f} · contexto {t_ipc:.0f} · daemon "
                  f"{daemon_ms:.0f}) — teto {TIQUE_MS} ms, pulando o próximo",
                  file=sys.stderr)
        self._contar_mutacoes()
        return True

    def _contar_a_abertura(self) -> None:
        """A linha `[abertura]`, uma vez — O-APP-RESPONDE-NA-HORA-01, cura 3."""
        agora = time.monotonic()
        self._abertura["pintura"] = agora
        vida = _segundos_de_vida()
        piloto = self._abertura["piloto"]
        janela = self._abertura.get("janela", piloto)
        total = vida if vida is not None else agora - piloto
        importar = max(0.0, total - (agora - piloto))
        print(f"[abertura] primeira pintura em {total * 1000:.0f} ms "
              f"(importar {importar * 1000:.0f} · janela {(janela - piloto) * 1000:.0f} "
              f"· página {(agora - janela) * 1000:.0f})", file=sys.stderr)

    def _contar_mutacoes(self) -> None:
        """Um passo do `--conta-mutacoes`, por tique. Fora dele, é um `if` falso."""
        quantos = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        if quantos <= 0 or self._mutacoes_lidas:
            return
        self._voltas_do_contador += 1
        if self._voltas_do_contador == VOLTAS_ATE_ASSENTAR:
            self.ponte.rodar(OBSERVAR_MUTACOES)
            print(f"[mutações] observando {self.pagina} por {quantos} tiques "
                  f"(~{quantos * TIQUE_MS / 1000:.0f} s), com a mesa parada")
        if self._voltas_do_contador >= VOLTAS_ATE_ASSENTAR + quantos:
            self._mutacoes_lidas = True
            self.ponte.perguntar(LER_MUTACOES, self._leu_mutacoes)

    def _leu_mutacoes(self, valor: Any, erro: Any) -> None:
        """Imprime a tabela do observador — e SAI, porque a medição acabou."""
        import json

        if erro is not None:
            print(f"REPROVA: o observador não respondeu — {erro}",
                  file=sys.stderr)
            Gtk.main_quit()
            return
        try:
            fora = json.loads(str(valor))
        except ValueError as e:
            print(f"REPROVA: a tabela não veio em JSON — {e}", file=sys.stderr)
            Gtk.main_quit()
            return
        self.mutacoes = fora
        tiques = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        print(f"\nMUTAÇÕES DE DOM em {tiques} tiques "
              f"({fora.get('ms', 0) / 1000:.1f} s) na {self.pagina}, "
              f"com a mesa parada")
        print(f"{'endereço':34s} {'tipo':14s} {'o quê':22s} {'n':>6s} {'nós':>6s}")
        for linha in fora.get("linhas", []):
            print(f"{str(linha['campo'])[:34]:34s} {linha['tipo']:14s} "
                  f"{str(linha['detalhe'])[:22]:22s} {linha['n']:6d} "
                  f"{linha['nos']:6d}")
        total = int(fora.get("total", 0))
        print(f"TOTAL: {total} mutações · {total / max(tiques, 1):.1f} por tique")
        if fora.get("blocos_adiados"):
            print(f"blocos ADIADOS por haver um `hef-em-voo` dentro: "
                  f"{fora['blocos_adiados']}")
        with contextlib.suppress(SystemExit):
            self._relatar()
        Gtk.main_quit()

    def _agendar(self) -> None:
        if self.args.passear:
            for i, alvo in enumerate(sorted(pacotes.PACOTES)):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: self._ir(a),
                )
            total = 1600 + len(pacotes.PACOTES) * self.args.parada
        elif self.args.segundos:
            total = int(self.args.segundos * 1000)
        else:
            return
        def fechar() -> bool:
            self._relatar()
            Gtk.main_quit()
            return False

        GLib.timeout_add(total, fechar)

    def _provar_mockup(self) -> bool:
        """Passa pelas DEZ abas e mede, em cada uma, o que é dado e o que é desenho."""
        self._fila_de_abas = [
            p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit()]
        self.lugar_vazio_com_desenho: dict[str, list[str]] = {}
        print(f"[prova-de-mockup] {len(self._fila_de_abas)} abas · "
              f"{self.args.voltas_por_aba} voltas de {TIQUE_MS} ms em cada uma")
        return self._proxima_aba()

    def _proxima_aba(self) -> bool:
        if not self._fila_de_abas:
            self._relatar_mockup()
            Gtk.main_quit()
            return False
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora = {}
        self.pronto = False
        self._ir(self._fila_de_abas.pop(0))
        return False

    def _fechou_a_aba(self, pagina: str, valor: Any, erro: Any) -> None:
        """A aba rodou o bastante. Classifica cada campo e segue para a próxima."""
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li a tela ao fim — {erro}")
            self._proxima_aba()
            return
        try:
            vivos: list[list[Any]] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: a leitura final não veio em JSON — {e}")
            self._proxima_aba()
            return

        arquivo = onde.pagina(pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        cravados = regua_do_mockup._campos_cravados(texto)
        self.cravados[pagina] = cravados

        virgem = self.pristino.get(pagina) or []
        if len(virgem) != len(cravados):
            self.cegueiras.append(
                f"{pagina}: o DOM virgem trouxe {len(virgem)} endereços e o "
                f"arquivo {len(cravados)}")
        else:
            for c, linha in zip(cravados, virgem, strict=True):
                k, d, _alvo, v = linha[:4]
                if (str(k), str(d)) != (c.chave, c.dono):
                    self.cegueiras.append(
                        f"{pagina}: o arquivo põe {c.endereco} onde a página "
                        f"virgem põe {d}·{k} — as duas leituras estão fora de ordem")
                elif str(v) != c.valor:
                    self.cegueiras.append(
                        f"{pagina}: a régua lê {c.endereco} como {c.valor!r} no "
                        f"arquivo e a página virgem mostra {v!r} — o parser e o "
                        f"leitor de tela discordam neste alvo ({c.alvo})")

        alinhados, nasceram = regua_do_mockup._alinhar(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3])) for x in vivos])
        selos = regua_do_mockup._selos_alinhados(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3]),
                        bool(x[4]) if len(x) > 4 else False) for x in vivos])
        if nasceram:
            print(f"[prova-de-mockup] {pagina}: {len(nasceram)} endereço(s) "
                  f"NASCERAM na tela (o produto trocou um bloco): "
                  f"{', '.join(f'{d}·{k}' if d else k for k, d in nasceram[:8])}")

        vazaram = _o_desenho_cheio_no_lugar_vazio(
            cravados, alinhados,
            [str(p) for p in (self._carga_de_agora.get("vazios") or [])], texto)
        if vazaram:
            self.lugar_vazio_com_desenho[pagina] = vazaram
            print(f"[prova-de-mockup] {pagina}: {len(vazaram)} campo(s) de lugar "
                  f"SEM controle mostram o desenho de um lugar CHEIO")

        if self.args.sem_cravado:
            cravados = [dataclasses.replace(c, valor="\x00cura arrancada")
                        for c in cravados]
        declarados = regua_do_mockup._declarados_do_pacote(self._carga_de_agora)
        if self.args.sem_selo:
            selos = [False] * len(cravados)
        self.vereditos[pagina] = regua_do_mockup._classificar(
            cravados, alinhados, declarados, selos)
        contas = regua_do_mockup._contar(self.vereditos[pagina])
        print(f"[prova-de-mockup] {pagina:22s} "
              f"produto {contas[regua_do_mockup.PRODUTO]:3d} · "
              f"mockup {contas[regua_do_mockup.MOCKUP]:3d} · "
              f"indecidível {contas[regua_do_mockup.INDECIDIVEL]:3d}")
        self._proxima_aba()

    def _relatar_mockup(self) -> None:
        """A tabela das três contagens, e a lista NOMINAL do que ainda é desenho."""
        r = regua_do_mockup
        print("\n" + "=" * 74)
        print("A RÉGUA DO MOCKUP — o que a tela mostra é dado, ou é o desenho?")
        print("=" * 74)
        print(f"{'aba':22s} {'campos':>7s} {'PRODUTO':>8s} {'RÓTULO':>7s} "
              f"{'MOCKUP':>7s} {'INDECID':>8s} {'pronto':>7s}")
        soma = {r.PRODUTO: 0, r.ROTULO: 0, r.MOCKUP: 0, r.INDECIDIVEL: 0}
        for pagina in sorted(self.vereditos):
            contas = r._contar(self.vereditos[pagina])
            for classe, quantos in contas.items():
                soma[classe] = soma.get(classe, 0) + quantos
            n = sum(contas.values())
            pronto = contas[r.PRODUTO] + contas.get(r.ROTULO, 0)
            print(f"{pagina:22s} {n:7d} {contas[r.PRODUTO]:8d} "
                  f"{contas.get(r.ROTULO, 0):7d} {contas[r.MOCKUP]:7d} "
                  f"{contas[r.INDECIDIVEL]:8d} {(100 * pronto // n) if n else 100:6d}%")
        total = sum(soma.values())
        pronto = soma[r.PRODUTO] + soma[r.ROTULO]
        print(f"{'TODAS':22s} {total:7d} {soma[r.PRODUTO]:8d} "
              f"{soma[r.ROTULO]:7d} {soma[r.MOCKUP]:7d} "
              f"{soma[r.INDECIDIVEL]:8d} {(100 * pronto // total) if total else 100:6d}%")

        print("\nOS CAMPOS QUE AINDA MOSTRAM O DESENHO — é este número que tem de cair:")
        for pagina in sorted(self.vereditos):
            presos = [v for v in self.vereditos[pagina] if v.classe == r.MOCKUP]
            if not presos:
                print(f"  {pagina}: nenhum")
                continue
            print(f"  {pagina} ({len(presos)}):")
            for preso in presos:
                marca = " ← ENDEREÇO MORTO" if preso.declarado is not None else ""
                print(f"      {preso.campo.endereco:28s} = {preso.vivo!r}{marca}")

        coincidem = sum(
            1 for vs in self.vereditos.values() for v in vs
            if v.classe == r.PRODUTO and v.vivo == v.campo.valor
            and v.declarado is not None and v.declarado == v.vivo)
        if coincidem:
            print(f"\nDESTES, {coincidem} SÃO PRODUTO PELO SELO DA VISITA: o valor que o "
                  "piloto\nescreveu COINCIDE com o que o desenho cravou, e antes do selo "
                  "isso\nera INDECIDÍVEL. O selo não é a tela — é o `escrever()` "
                  "registrando\nque esteve naquele elemento com aquele valor. Para "
                  "conferir que ele\ndecide alguma coisa: `--sem-selo` tem de devolvê-los "
                  "aos indecidíveis.")
        if soma[r.INDECIDIVEL]:
            print(f"\nOS {soma[r.INDECIDIVEL]} INDECIDÍVEIS que SOBRAM são campos em que o "
                  "valor coincide\ncom o desenho e o piloto NÃO passou pelo elemento — "
                  "quase sempre\num bloco que a pintura trocou inteiro. Ler a tela não "
                  "separa\n'pintou igual' de 'não pintou', e a régua prefere dizer "
                  "quantos são\na inventar certeza.")

        if self.lugar_vazio_com_desenho:
            print("\nREPROVA: lugar SEM controle mostrando o desenho de um lugar "
                  "COM controle:")
            for pagina in sorted(self.lugar_vazio_com_desenho):
                for linha in self.lugar_vazio_com_desenho[pagina]:
                    print(f"   · {pagina}: {linha}")
        else:
            print("\nNenhum lugar sem controle mostra o desenho de um lugar com "
                  "controle.")
        if self.cegueiras:
            print(f"\nA RÉGUA NÃO ENXERGOU {len(self.cegueiras)} coisa(s) — e isso reprova, "
                  "porque\numa régua que não sabe o que está lendo mede o que quiser:")
            for cegueira in self.cegueiras:
                print(f"   · {cegueira}")
            raise SystemExit(1)
        if self.lugar_vazio_com_desenho:
            raise SystemExit(1)
        if 0 <= self.args.teto_de_mockup < soma[r.MOCKUP]:
            print(f"\nREPROVA: {soma[r.MOCKUP]} campos no desenho, e o teto pedido "
                  f"era {self.args.teto_de_mockup}.")
            raise SystemExit(1)

    def _provar_cliques(self) -> bool:
        """Cliques SINTÉTICOS nos gestos INÓCUOS, para provar o caminho.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato — o
        ouvinte delegado do bootstrap é o que responde. Clicar por coordenada é
        a armadilha que esta casa já pagou duas vezes, e a janela é Offscreen.

        SÓ OS INÓCUOS, e a lista é curta de propósito: `atualizar` é
        `daemon.reload` e `retomar` é `daemon.resume` num daemon que não está
        pausado. `desligar`, `restaurar-de-fabrica` e `refazer-proton` NÃO
        entram — uma régua não mexe na máquina dela para provar que sabe clicar.

        **E ATÉ 06/09/2026 ESSA FRASE ERA SÓ UMA FRASE.** Este caminho clicava o
        que a bandeira nomeasse, sem consultar `PERIGOSOS` uma única vez — só o
        `--prova-no-aparelho` a consultava. Achado pela `ONDA5-03-02`, que
        mediu o próprio estrago: o clique dela **gravou no perfil real** da dona
        (a gravação foi no-op — o valor já era o mesmo desde as 02:46, e nenhum
        arquivo nasceu no `.historico/` — mas a porta estava aberta e nenhum
        agente sabia). É a terceira vez em quatro dias que o comentário que
        AVISA do risco fica ao lado do código que o comete.

        A recusa é BARULHENTA e não um pulo em silêncio: uma régua que pula
        calado ensina quem a roda que ela cobriu o botão. `--incluir-perigosos`
        continua sendo a porta, e aí é escolha de quem roda.
        """
        proibidos = sorted(
            g for g in dict.fromkeys(self.args.prova_clique.split(","))
            if (self.pagina, g.strip()) in PERIGOSOS)
        if proibidos and not self.args.incluir_perigosos:
            print(f"[prova] RECUSA: {', '.join(proibidos)} mexe(m) na máquina "
                  f"dela em {self.pagina}. Use --incluir-perigosos se for "
                  "mesmo isso que você quer.", file=sys.stderr)
            raise SystemExit(1)
        def clicar(g: str) -> bool:
            if not self.pronto:
                return True
            self._js(SELETOR % (g, g, g, g))
            return False

        for i, gesto in enumerate(self.args.prova_clique.split(",")):
            GLib.timeout_add(600 + i * 900, lambda g=gesto: clicar(g))
        return False

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _provar_no_aparelho(self) -> bool:
        """A PROVA BOTÃO A BOTÃO, no aparelho dela — pedido dela, 01/09/2026."""
        arquivo = onde.pagina(self.pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        da_pagina = regua_do_mockup._gestos_cravados(texto)
        registrados = {n for (p, n) in pacotes.GESTOS if p in (self.pagina, "*")}
        perigosos = set() if self.args.incluir_perigosos else PERIGOSOS
        alvos, pulados = regua_do_mockup._alvos_a_clicar(
            da_pagina, registrados, self.pagina, perigosos)
        faltou = regua_do_mockup._cobertura_dos_gestos(
            da_pagina, registrados, alvos, pulados)
        if faltou:
            print(f"[prova] REPROVA: {len(faltou)} endereço(s) clicável(is) de "
                  f"{self.pagina} ficaram de fora: {', '.join(faltou)}", file=sys.stderr)
            raise SystemExit(1)
        so_na_pagina = sorted({g.nome for g in da_pagina} - registrados)
        so_no_codigo = sorted(registrados - {g.nome for g in da_pagina})
        papeis = sorted({g.nome for g in regua_do_mockup._papeis_cravados(texto)}
                        - registrados)
        print(f"[prova] {self.pagina}: {len(da_pagina)} endereços na página · "
              f"{len(registrados)} registrados no código")
        if so_na_pagina:
            print(f"[prova] SÓ NA PÁGINA (ninguém os ligou): {', '.join(so_na_pagina)}")
        if so_no_codigo:
            print(f"[prova] SÓ NO CÓDIGO (a página não tem `data-gesto`): "
                  f"{', '.join(so_no_codigo)}")
        if papeis:
            print(f"[prova] `data-papel` que o ouvinte aceita como gesto e nenhum "
                  f"pacote registra: {', '.join(papeis)}")
        if pulados:
            print(f"[prova] pulados por mexerem na máquina dela: {', '.join(pulados)}")
        if not alvos:
            print(f"[prova] {self.pagina} não tem gesto seguro a clicar")
            return False
        print(f"[prova] {len(alvos)} gesto(s) em {self.pagina}: {', '.join(alvos)}")
        # constante os gestos se ATROPELAM: `daemon.reload` leva 9,5 s e o
        self._fila = list(alvos)
        GLib.timeout_add(400, self._proximo_da_fila)
        return False

    def _proximo_da_fila(self) -> bool:
        """O próximo gesto da prova no aparelho."""
        if self._fila:
            self._um_botao(self._fila.pop(0))
        return False

    def _um_botao(self, nome: str) -> None:
        """Um gesto: fotografa o daemon, clica NO ALVO CERTO, e mede o que mudou."""
        try:
            antes = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon antes ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return
        self._antes_do_gesto = (nome, antes)
        self.desfechos.pop(f"{self.pagina}:{nome}", None)
        prefs = [c["pref"] for c in self._mesa_de_agora if c.get("pref")]

        def anotou(valor: Any, erro: Any) -> None:
            self._onde_clicou[nome] = (
                f"o clique falhou: {erro}" if erro is not None else str(valor))

        self.ponte.perguntar(CLIQUE_COM_ALVO % (_json(nome, pagina=self.pagina),
                                                _json(prefs, pagina=self.pagina)), anotou)
        # E ELA É POR GESTO: o `TETOS` da ponte diz que `daemon.reload` leva 15 s
        from pacotes import ponte as _p

        espera = max(self.args.espera, int(_p.teto(_METODO_DO_GESTO.get(nome, "")) * 1000) + 800)
        GLib.timeout_add(espera, self._depois_do_gesto)

    def _depois_do_gesto(self) -> bool:
        nome, antes = getattr(self, "_antes_do_gesto", (None, {}))
        antes_do_daemon: dict[str, Any] = dict(antes)
        if nome is None:
            return False
        try:
            depois = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon depois ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return False
        mudou = {k: (antes_do_daemon.get(k), v) for k, v in depois.items()
                 if antes_do_daemon.get(k) != v
                 and not any(r in k for r in RUIDO)}
        # acusar um botão que funciona. O `state_full` do daemon não publica
        # gatilho — o DualSense não devolve o modo em que está, é comando de ida
        sem_eco = nome in self._sem_eco_da_pagina()
        desfecho, frase = self.desfechos.get(f"{self.pagina}:{nome}", ("aplicou", ""))
        onde_ = self._onde_clicou.get(nome, "")
        self.provas.append({"gesto": nome, "mudou": mudou, "sem_eco": sem_eco,
                            "desfecho": desfecho, "frase": frase, "onde": onde_})
        cabeca = f"[PROVA] {self.pagina} · {nome}"
        if onde_:
            cabeca += f" ({onde_})"
        if desfecho == "sem dono":
            print(f"{cabeca} → SEM DONO: nenhum pacote registra este gesto")
        elif desfecho == "recusou dizendo":
            print(f"{cabeca} → RECUSOU DIZENDO: {frase}")
        elif mudou:
            print(f"{cabeca} → MUDOU {len(mudou)} campo(s):")
            for k, (a, d) in sorted(mudou.items())[:6]:
                print(f"          {k}: {a!r} → {d!r}")
        elif sem_eco:
            print(f"{cabeca} → ACEITO, sem eco no state "
                  f"(o daemon não publica este assunto)")
        else:
            print(f"{cabeca} → DISSE APLICADO E NADA MUDOU no estado do daemon")
        return self._proximo_da_fila()

    def _sem_eco_da_pagina(self) -> set[str]:
        """Os gestos daquela aba cujo efeito o daemon não publica."""
        import importlib

        sem_eco = {monta.GESTO_DA_FITA}
        for arq in sorted((AQUI / "pacotes").glob("a[0-9][0-9]_*.py")):
            mod = importlib.import_module(f"pacotes.{arq.stem}")
            if getattr(mod, "PAGINA", "") == self.pagina:
                return sem_eco | set(getattr(mod, "SEM_ECO", ()))
        return sem_eco

    def _ir(self, pagina: str) -> bool:
        """Abre uma aba. `False` para o GLib — ver `_proximo_da_fila`."""
        alvo = onde.pagina(_a_pagina_pedida(pagina), publicado=True)
        if not alvo.exists():
            self.tela._morrer(f"não existe a página pedida: {alvo.name}")
            return False
        # sobre o teste naquele momento isso nao interfere in game"*  # (noqa-acento): dela
        pacotes.largar_o_que_as_abas_seguram(ponte)
        _soltar_as_ondas()
        self.view.load_uri(alvo.as_uri())
        return False

    def _relatar(self) -> bool:
        if self.relatou:
            return False
        self.relatou = True
        self._estado_vivo.parar()
        pacotes.largar_o_que_as_abas_seguram(ponte)
        if self.args.foto:
            self.tela.fotografar(self.args.foto)
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'tiques':>7s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            tiques = self.tiques.get(pagina, 0)
            print(f"{pagina:22s} {tiques:7d} {len(conta):8d} {pico:8d}")
            if tiques and not conta:
                mudas.append(pagina)
        if self.trocas:
            print("página trocada no meio do tique: " + " · ".join(
                f"{p} {n}" for p, n in sorted(self.trocas.items())))
        if self.provas:
            def classe(p: dict[str, Any]) -> str:
                if p.get("desfecho") == "sem dono":
                    return "sem dono"
                if p.get("desfecho") == "recusou dizendo":
                    return "recusou dizendo"
                if p["mudou"]:
                    return "mudou o daemon"
                if p["sem_eco"]:
                    return "aceito sem eco"
                return "disse aplicado e nada mudou"

            marcas = {"mudou o daemon": "✓", "aceito sem eco": "·",
                      "recusou dizendo": "!", "sem dono": "?",
                      "disse aplicado e nada mudou": "—"}
            contas: dict[str, int] = {}
            for p in self.provas:
                contas[classe(p)] = contas.get(classe(p), 0) + 1
            print("\nPROVA NO APARELHO: " + " · ".join(
                f"{n} {k}" for k, n in sorted(contas.items())))
            for p in self.provas:
                k = classe(p)
                extra = f" — {p['frase']}" if p.get("frase") else ""
                onde_ = f" ({p['onde']})" if p.get("onde") else ""
                print(f"   {marcas[k]} {p['gesto']}{onde_}{extra}")
            mudos = [p["gesto"] for p in self.provas
                     if classe(p) == "disse aplicado e nada mudou"]
            if mudos:
                print(f"   sem efeito e sem `SEM_ECO`: {', '.join(mudos)}")
            forcados = [p["gesto"] for p in self.provas
                        if str(p.get("onde", "")).startswith("ALVO FORCADO")]
            if forcados:
                print(f"   alvo FORÇADO pela régua (a página não diz em quem "
                      f"agir): {', '.join(forcados)}")
        if self.gestos:
            print(f"gestos: {len(self.gestos)} · aplicados: {len(self.aplicados)} · "
                  f"sem dono: {len(set(self.recusados))}")
            for r in sorted(set(self.recusados)):
                print(f"   sem dono: {r}")
        if self.custos:
            ordenado = sorted(self.custos)
            print(f"custo do tique: mediana {ordenado[len(ordenado)//2]:.2f} ms · "
                  f"max {ordenado[-1]:.2f} ms · teto {TIQUE_MS} ms")
        if self.custo_do_ipc:
            ipc = sorted(self.custo_do_ipc)
            print(f"custo do IPC:   mediana {ipc[len(ipc)//2]:.2f} ms · "
                  f"max {ipc[-1]:.2f} ms")
        if self._pulados_por_voo or self._pulados_por_custo:
            print(f"tiques pulados: {self._pulados_por_voo} com pintura no ar · "
                  f"{self._pulados_por_custo} pelo custo do anterior")
        if mudas:
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)
        return False


#: a folha de estilo os esconde num lugar vazio (`.ctl[data-conectado="nao"]
_ALVOS_QUE_O_LUGAR_VAZIO_COBRA = frozenset(
    {"texto", "html", "cor", "atributo", "plastico"})

_TAG_DO_LUGAR = r'<[a-zA-Z][^>]*\bdata-controle="(p\d+)"[^>]*>'
_ENDERECO_NA_TAG = r'\bdata-(?:campo|papel|hef)="([^"]+)"'


def _o_lugar_no_arquivo(texto: str) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Os lugares que o arquivo publica VAZIOS, e os endereços que SÃO o lugar."""
    import re

    vazios: set[str] = set()
    proprios: set[tuple[str, str]] = set()
    for m in re.finditer(_TAG_DO_LUGAR, texto):
        tag, pref = m.group(0), m.group(1)
        if 'data-conectado="nao"' in tag:  # (noqa-acento) valor do atributo
            vazios.add(pref)
        proprios |= {(pref, chave) for chave in re.findall(_ENDERECO_NA_TAG, tag)}
    return frozenset(vazios), frozenset(proprios)


def _o_desenho_cheio_no_lugar_vazio(
        cravados: list[regua_do_mockup._Campo],
        vivos: list[str],
        vazios_agora: Iterable[str],
        texto: str) -> list[str]:
    """Os campos de um lugar SEM controle que mostram o desenho de um lugar CHEIO."""
    do_desenho, proprios = _o_lugar_no_arquivo(texto)
    cheio: dict[tuple[str, str], set[str]] = {}
    vazio: dict[tuple[str, str], set[str]] = {}
    for c in cravados:
        if c.dono not in pacotes.TODOS_OS_LUGARES:
            continue
        (vazio if c.dono in do_desenho else cheio).setdefault(
            (c.chave, c.alvo), set()).add(c.valor)
    agora = set(vazios_agora)
    fora: list[str] = []
    for c, vivo in zip(cravados, vivos, strict=True):
        if (c.dono not in agora or c.rotulo
                or c.alvo not in _ALVOS_QUE_O_LUGAR_VAZIO_COBRA
                or (c.dono, c.chave) in proprios
                or vivo in ("", pacotes.TRAVESSAO, regua_do_mockup.SUMIU)):
            continue
        k = (c.chave, c.alvo)
        if vivo in cheio.get(k, ()) and vivo not in vazio.get(k, ()):
            fora.append(f"{c.endereco} [{c.alvo}] = {vivo[:70]!r}")
    return fora


_SECOES_POR_CHAVE: dict[str, int] = {"mesa": 1, "colunas": 2, "blocos": 1, "marcas": 1}


def _achatar_a_carga(carga: dict[str, Any]) -> dict[tuple[str, ...], tuple[Any, Any]]:
    """`{caminho: (retrato, valor)}` de cada valor que o `pintar` lê sozinho."""
    import json

    fora: dict[tuple[str, ...], tuple[Any, Any]] = {}

    def descer(caminho: tuple[str, ...], valor: Any, niveis: int) -> None:
        if niveis and isinstance(valor, dict):
            for k, v in valor.items():
                descer((*caminho, str(k)), v, niveis - 1)
            return
        retrato = (("t", valor) if isinstance(valor, str)
                   else ("j", json.dumps(valor, sort_keys=True, ensure_ascii=False,
                                         default=str)))
        fora[caminho] = (retrato, valor)

    for secao, valor in carga.items():
        descer((str(secao),), valor, _SECOES_POR_CHAVE.get(str(secao), 0))
    return fora


def _o_que_mudou(antes: dict[tuple[str, ...], tuple[Any, Any]],
                 agora: dict[tuple[str, ...], tuple[Any, Any]]) -> dict[str, Any]:
    """A carga com só o que mudou entre as duas, na forma que o `pintar` lê."""
    dif: dict[str, Any] = {}
    for caminho, (retrato, valor) in agora.items():
        velho = antes.get(caminho)
        if velho is not None and velho[0] == retrato:
            continue
        no = dif
        for k in caminho[:-1]:
            no = no.setdefault(k, {})
        no[caminho[-1]] = valor
    return dif


def _a_diferenca_muda_a_forma(dif: dict[str, Any], moldes: frozenset[str]) -> bool:
    """A diferença troca ou clona nós? A fita, um bloco ou a lista de um molde."""
    return ("fita" in dif or "blocos" in dif
            or any(k in moldes for k in (dif.get("mesa") or {})))


def _esquecer_a_pintura(piloto: Any) -> None:
    """O próximo tique do `piloto` manda a carga INTEIRA, e não só o que mudou."""
    piloto._pintada = None


def _soltar_as_ondas() -> None:
    """As ondas sonoras soltam todo nó. Nunca levanta."""
    from hefesto_dualsense4unix.integrations import ondas_de_som

    with contextlib.suppress(Exception):
        ondas_de_som.o_de_sempre().seguir({})


def _json(obj: Any, pagina: str = "") -> str:
    """Serializa para o WebView — e DENUNCIA o que ela mandou tirar da tela."""
    import json

    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        FRASES_BANIDAS,
        PALAVRAS_BANIDAS,
        primeiro_trecho_banido,
        sem_o_citado,
        sem_o_trecho,
    )

    saida = json.dumps(obj, ensure_ascii=False, default=str)
    teto = len(FRASES_BANIDAS) + len(PALAVRAS_BANIDAS) + 1
    for campo, folha in _folhas_da_carga(obj):
        if isinstance(folha, str) and folha in _TEXTOS_LIDOS_PELO_FUNIL:
            banidas = _TEXTOS_LIDOS_PELO_FUNIL[folha]
        else:
            lido = sem_o_citado(folha) if isinstance(folha, str) else folha
            resto = json.dumps(lido, ensure_ascii=False, default=str)
            achadas: list[str] = []
            for _ in range(teto):
                banida = primeiro_trecho_banido(resto)
                if banida is None:
                    break
                achadas.append(banida)
                resto = sem_o_trecho(resto, banida)
            banidas = tuple(achadas)
            if isinstance(folha, str):
                if len(_TEXTOS_LIDOS_PELO_FUNIL) >= TEXTOS_QUE_O_FUNIL_LEMBRA:
                    _TEXTOS_LIDOS_PELO_FUNIL.pop(next(iter(_TEXTOS_LIDOS_PELO_FUNIL)))
                _TEXTOS_LIDOS_PELO_FUNIL[folha] = banidas
        for banida in banidas:
            dono = (banida, pagina, campo)
            if dono in _BANIDAS_JA_DENUNCIADAS:
                continue
            _BANIDAS_JA_DENUNCIADAS.add(dono)
            print(f"[texto banido] {banida!r} em {_onde_foi(pagina, campo)}. A frase "
                  "é defeito do dono dela — ver `interface/frases_que_ela_baniu.py`.",
                  file=sys.stderr)
    return saida


def _onde_foi(pagina: str, campo: str) -> str:
    """`09-sistema.html · registro-texto` — a página e o campo da denúncia."""
    return f"{pagina or 'página sem nome'} · {campo or 'campo sem nome'}"


def _folhas_da_carga(obj: Any, campo: str = "") -> Iterable[tuple[str, Any]]:
    """`(campo, valor)` de cada valor que pode ter letra — o campo é a chave."""
    if isinstance(obj, dict):
        for chave, valor in obj.items():
            yield from _folhas_da_carga(valor, str(chave))
    elif isinstance(obj, (list, tuple)):
        for valor in obj:
            yield from _folhas_da_carga(valor, campo)
    elif obj is None or isinstance(obj, (bool, int, float)):
        return
    else:
        yield campo, obj


_BANIDAS_JA_DENUNCIADAS: set[tuple[str, str, str]] = set()

TEXTOS_QUE_O_FUNIL_LEMBRA = 4096
_TEXTOS_LIDOS_PELO_FUNIL: dict[str, tuple[str, ...]] = {}


@contextlib.contextmanager
def _o_processo_da_janela() -> Iterator[None]:
    """O que o processo da janela liga ao subir e desliga ao sair."""
    from hefesto_dualsense4unix.profiles import loader

    loader.ligar_a_leitura_pela_assinatura()
    try:
        yield
    finally:
        loader.desligar_a_leitura_pela_assinatura()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true",
                   help="Gtk.OffscreenWindow — nada aparece na tela dela. "
                        "Ela tem UMA tela; é o padrão de toda régua desta casa.")
    p.add_argument("--segundos", type=float, default=0.0,
                   help="fecha a janela depois de N segundos e relata. ZERO (o "
                        "padrão) mantém a janela aberta até ela fechar — que é "
                        "o comportamento do PRODUTO. Só a bancada põe prazo.")
    p.add_argument("--passear", action="store_true",
                   help="visita as dez abas e mede a pintura de cada uma")
    p.add_argument("--parada", type=int, default=900,
                   help="ms em cada aba durante o passeio")
    p.add_argument("--foto", default="")
    p.add_argument("--abre", default="",
                   help="abrir direto numa aba: o número (`10`), o nome sem "
                        "extensão (`10-perfis`) ou o arquivo "
                        "(`10-perfis.html`). Página que não existe REPROVA")
    p.add_argument("--prova-no-aparelho", action="store_true",
                   help="clica CADA gesto da aba, um por vez, e mede o que mudou "
                        "no estado do daemon — a prova que ela pediu")
    p.add_argument("--entre", type=int, default=2500,
                   help="ms entre um gesto e o próximo")
    p.add_argument("--espera", type=int, default=1200,
                   help="ms entre o clique e a leitura do daemon")
    p.add_argument("--incluir-perigosos", action="store_true",
                   help="inclui os gestos que mexem na máquina dela (desligar, "
                        "reiniciar, restaurar) — escolha de quem roda")
    p.add_argument("--prova-clique", default="",
                   help="lista de gestos a clicar, separada por vírgula — "
                        "eles chegam ao daemon de verdade")
    p.add_argument("--sem-cor", action="store_true",
                   help="MORDIDA: sem o leitor de cor do plástico")
    p.add_argument("--sem-ondas", action="store_true",
                   help="MORDIDA: arranca o medidor de áudio das ondas sonoras "
                        "da aba 02. As catorze barrinhas de cada medidor têm de "
                        "ACHATAR e ficar cinza — se continuarem desenhando a "
                        "onda do arquivo, elas nunca foram dado")
    p.add_argument("--prova-de-mockup", action="store_true",
                   help="passa pelas dez abas e diz, campo a campo, o que é DADO "
                        "e o que ainda é o DESENHO cravado no arquivo")
    p.add_argument("--voltas-por-aba", type=int, default=8,
                   help="quantos tiques a pintura corre em cada aba antes da "
                        "medição. Uma volta só mede um INSTANTE, não um "
                        "comportamento — o padrão dá 4 s por aba")
    p.add_argument("--teto-de-mockup", type=int, default=-1,
                   help="reprova se mais de N campos ainda mostrarem o desenho. "
                        "NEGATIVO (o padrão) só mede e relata — é assim que ele "
                        "vira catraca quando o número começar a cair")
    p.add_argument("--sem-cravado", action="store_true",
                   help="MORDIDA: arranca a comparação com o arquivo publicado e "
                        "compara a tela com ela mesma. A régua tem de parar de "
                        "acusar — se continuar acusando, ela não mede o que diz")
    p.add_argument("--sem-selo", action="store_true",
                   help="MORDIDA: arranca o selo da visita. Os campos que "
                        "coincidem com o desenho voltam a ser INDECIDÍVEIS — e "
                        "se o número não voltar, o selo não estava decidindo nada")
    p.add_argument("--conta-mutacoes", type=int, default=0, metavar="N",
                   help="conta as mutações de DOM em N tiques COM A MESA "
                        "PARADA, por endereço e por tipo, e sai. O número certo "
                        "é ZERO para tudo o que não mudou de valor — o que "
                        "sobrar é a tela sambando")
    args = p.parse_args()

    if args.conta_mutacoes and not args.oculta:
        print("[conta-mutações] ligando `--oculta`: ela tem UMA tela.")
        args.oculta = True

    if args.prova_de_mockup and not args.oculta:
        print("[prova-de-mockup] ligando `--oculta`: esta régua abre dez abas e "
              "ela tem UMA tela.")
        args.oculta = True

    from hefesto_dualsense4unix.integrations import ondas_de_som

    ondas_de_som.ligar(not args.sem_ondas)

    piloto = Piloto(args)

    def _quando_a_pagina_estiver_de_pe(tarefa: Callable[[], Any]) -> None:
        """Agenda ``tarefa`` para o instante em que a PÁGINA confirmar — não o relógio."""

        def _tique() -> bool:
            if piloto.tela.morreu is not None:
                return False
            if not piloto.tela.na_aba:
                return True
            tarefa()
            return False

        GLib.timeout_add(120, _tique)

    if args.prova_de_mockup:
        _quando_a_pagina_estiver_de_pe(piloto._provar_mockup)
    if args.prova_no_aparelho:
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2500, piloto._provar_no_aparelho))
    if args.prova_clique:
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2000, piloto._provar_cliques))
    if args.abre:
        _quando_a_pagina_estiver_de_pe(lambda: piloto._ir(args.abre))
    with _o_processo_da_janela():
        Gtk.main()

    if piloto.tela.morreu is not None:
        print(f"\nREPROVA: a página morreu e nada foi medido — {piloto.tela.morreu}",
              file=sys.stderr)
        raise SystemExit(1)
    if args.prova_de_mockup and not piloto.visitadas:
        print("\nREPROVA: `--prova-de-mockup` não visitou aba nenhuma.",
              file=sys.stderr)
        raise SystemExit(1)


def _ligar_as_abas() -> None:
    """O que depende das dez abas: o gesto da fita e a lista dos perigosos."""
    global PERIGOSOS, SELETOR_DO_DONO
    _registrar_a_fita()
    PERIGOSOS = pacotes.perigosos()
    SELETOR_DO_DONO = '[data-uniq],[data-controle=""],' + ",".join(
        f'[data-controle="{lugar}"]' for lugar in sorted(pacotes.TODOS_OS_LUGARES))


def _segundos_de_vida() -> float | None:
    """Há quanto tempo este processo nasceu, pelo `/proc` (None fora do Linux)."""
    try:
        with open("/proc/self/stat", encoding="ascii") as arq:
            campos = arq.read().rsplit(")", 1)[1].split()
        nasceu = int(campos[19]) / os.sysconf("SC_CLK_TCK")
        return time.clock_gettime(time.CLOCK_BOOTTIME) - nasceu
    except (OSError, ValueError, IndexError, AttributeError):
        return None


_AS_ABAS_CHEGARAM = __name__ != "__main__"

TETO_DA_ESPERA_DO_WEBKIT_S = 3.0


def _esperar_o_webkit_comecar(tela: Any, teto_s: float = TETO_DA_ESPERA_DO_WEBKIT_S) -> None:
    """Roda o laço do GTK até o WebKit começar a carregar a página (`committed`)."""
    from gi.repository import WebKit2

    fim: list[str] = []
    vigia_no_ar = [True]

    def acabou(motivo: str) -> None:
        if not fim:
            fim.append(motivo)
            Gtk.main_quit()

    def viu(_view: Any, evento: Any) -> None:
        if evento in (WebKit2.LoadEvent.COMMITTED, WebKit2.LoadEvent.FINISHED):
            acabou("carregando")

    def olhar() -> bool:
        if tela.morreu is not None:
            acabou("morreu")
        elif time.monotonic() >= prazo:
            acabou("teto")
        vigia_no_ar[0] = not fim
        return vigia_no_ar[0]

    def sair_do_laco_que_vem() -> bool:
        Gtk.main_quit()
        return False

    ligacao = tela.view.connect("load-changed", viu)
    prazo = time.monotonic() + teto_s
    vigia = GLib.timeout_add(20, olhar)
    try:
        Gtk.main()
    finally:
        if vigia_no_ar[0]:
            GLib.source_remove(vigia)
        tela.view.disconnect(ligacao)
    if not fim:
        GLib.idle_add(sair_do_laco_que_vem)


def _importar_as_abas(tela: Any = None) -> None:
    """As dez abas e a `mesa_viva`, depois de a janela pedir a página."""
    global _AS_ABAS_CHEGARAM, mesa_viva, pacotes, ponte
    if _AS_ABAS_CHEGARAM:
        return
    if tela is not None:
        _esperar_o_webkit_comecar(tela)
    from hefesto_dualsense4unix.interface import mesa_viva, pacotes
    from hefesto_dualsense4unix.interface.pacotes import ponte

    _AS_ABAS_CHEGARAM = True
    _ligar_as_abas()


if __name__ != "__main__":
    _ligar_as_abas()

if __name__ == "__main__":
    main()
