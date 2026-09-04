#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as dez abas, tudo pintado pelo despachante.

DECISÃO DELA, 01/09/2026: *"melhor assim mesmo. aba a aba. igual vc falou. mas
já usando o trabalho do specs pra fazermos tudo de uma vez. já o trampo final."*
E depois: *"a única que não faremos, só deixamos o botão levando pra ela, é a de
lançadores."*

O QUE ELE SUBSTITUI, e é o motivo de existir: até aqui havia CINCO pilotos, um
por aba — `controles_vivos`, `jogar_vivo`, `conexoes_vivas`, `perfis_vivos`,
`sistema_viva`. Cada um abre a sua página e morre nela; clicar na tira levava a
uma página ESTÁTICA, o mockup sem dado. O produto que ela pediu é uma janela em
que as dez abas estão vivas e a navegação entre elas funciona.

COMO ELE SABE O QUE PINTAR: pelo nome do arquivo à vista. O `load-changed` do
WebView chega em toda carga, e o `pacotes.pacote_da_pagina()` devolve o pacote
daquela página — ou `None`, que quer dizer "esta aba ainda não tem quem a pinte"
e é diferente de um pacote vazio.

AS DUAS LÍNGUAS, e a tradução mora AQUI de propósito:

    o daemon fala `uniq`   — `d4:2f:00:00:…`, o endereço do aparelho
    o desenho fala `pref`  — `p1`, `p2`, que é o que o `data-controle` traz

As funções de pacote falam a língua do daemon, porque é dele que leem. A tela
fala a língua do desenho, porque é o mockup dela. Traduzir no pacote misturaria
as duas e faria cada aba carregar a mesa; traduzir no JS espalharia a regra por
dez páginas. Fica no piloto, que é quem já tem a mesa na mão.
"""
from __future__ import annotations

from typing import Any

import argparse
import contextlib
import dataclasses
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

# PELO NOME DO PACOTE, e não pelo nome curto do vizinho. Eram
# `import mesa_viva` / `import pacotes`, herdados de quando esta pasta vivia em
# `layout/` e os pilotos entravam nela pelo `sys.path`. Dentro do `src/` isso
# custava caro e em silêncio: uma ferramenta que lê o código ESTÁTICO não
# resolve `import pacotes` para `hefesto_dualsense4unix.interface.pacotes`, e o
# `portao_a_casa_sabe_e_o_produto_nao_faz` chegava a **zero** módulos da interface
# alcançados a partir das bocas do produto. O portão que existe para achar a
# cura escrita e nunca ligada não enxergava a interface INTEIRA — e por isso
# acusava de dívida as camadas que ela já chama.
from hefesto_dualsense4unix.interface import (  # noqa: E402
    mesa_viva,
    onde,
    pacotes,
    regua_do_mockup,
)
from hefesto_dualsense4unix.interface.pacotes import ponte  # noqa: E402

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

#: A PRIMEIRA PÁGINA é a Jogar, que é a primeira da tira. Não é escolha de
#: gosto: é a aba que o `.desktop` dela abre.
PRIMEIRA = "01-jogar.html"

#: O tique da pintura. 500 ms é o mesmo do `controles_vivos`, medido lá: o custo
#: por volta ficou em 0,9% do orçamento, com IPC de mediana 0,8 ms.
TIQUE_MS = 500

#: OS QUATRO LUGARES DA MESA DO DESENHO mudaram de casa em 02/09/2026: vivem em
#: `pacotes.TODOS_OS_LUGARES`, junto com a conta que os apaga
#: (`pacotes.apagar_os_lugares_sem_dono`). O acoplamento entre o molde e quem o
#: aplica tinha aqui uma régua que cobrava LITERAIS deste arquivo — e literal
#: não é comportamento: a cura morria inteira com os três literais em pé.

#: A aba que NÃO tem pacote, por decisão dela — só o botão que leva a ela.
SEM_PACOTE = {"07-lancadores.html"}

#: QUANTO TEMPO A FRASE DE RECUSA FICA NA TELA. Decisão dela, 02/09/2026, sobre
#: a recusa do microfone: *"a frase de recusa SOME depois de um tempo — ~30 s e
#: desaparece. É aviso, não estado."*
#:
#: O CANAL É UM SÓ PARA AS DEZ ABAS, então a vida da frase também é: dois
#: relógios para a mesma coisa seriam a segunda cópia da mesma regra, e a
#: segunda divergiria. Ver `Piloto._recados_para_a_tela`.
SEGUNDOS_DO_RECADO = 30.0

#: O QUE A GUARDA DE CARGA ACEITA. Os pilotos de uma aba só passavam o nome
#: dela — `"Controles"` — e a guarda matava a janela em qualquer outra página.
#: Aqui as DEZ são legítimas, então o esperado é o que as dez compartilham:
#:
#:     Hefesto — aba JOGAR (mockup 26/08/2026)
#:     Hefesto — aba GATILHOS (mockup 26/08/2026)
#:
#: A guarda casa por SUBSTRING, e `"Jogar"` não casa com `"aba JOGAR"` — foi o
#: que matou a primeira execução deste piloto. Continua servindo para o que ela
#: existe: uma página que NÃO é do mockup (um erro de carga, um `about:blank`)
#: não tem este título e a guarda a pega.
TITULO_DE_QUALQUER_ABA = "Hefesto — aba "

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
    const t = vazio ? '—' : String(v);
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
    el.dataset.hefVisto = '1';
    if(alvo === 'largura'){
      if(el.style.width !== t + '%'){ el.style.width = t + '%'; return 1; }
      return 0;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){
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
      // `gui.aba_conexoes.teto_que_vale` já tomava do lado Python.
      if(el.tagName === 'SELECT'){
        const tem = Array.prototype.some.call(el.options,
                                              function(o){ return o.value === t || o.text === t; });
        if(!tem) return 0;
      }
      if(el.value !== t){ el.value = t; return 1; }
      return 0;
    }
    // O ALVO `html` EXISTE PARA UM BLOCO COM MARCAÇÃO — a dica do `?` do teto
    // da vibração (`aba08.teto_dica`) traz `<b>` e `<code>` no desenho dela, e o
    // `textContent` do ramo padrão escreveria os marcadores como texto literal
    // na tela. Acrescentado em 01/09/2026.
    //
    // POR QUE NÃO O `blocos:` QUE JÁ EXISTE: aquele troca UM elemento por
    // `document.querySelector`, e o `?` do teto é um POR CONTROLE. É o mesmo
    // degrau, um tamanho menor — o endereço é `data-campo`, distribuído.
    if(alvo === 'html'){ if(el.innerHTML !== t){ el.innerHTML = t; return 1; } return 0; }
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
    if(alvo === 'classe'){
      const c = el.dataset.hefClasse || 'on';
      const quando = el.dataset.hefQuando;
      const aceso = (quando === undefined || quando === '') ? ligado(t) : (t === quando);
      if(el.classList.contains(c) === aceso) return 0;
      el.classList.toggle(c, aceso);
      return 1;
    }
    // O ALVO `cor` — o `color` do elemento, e ele é o par que faltava do
    // `fundo`. O clique do analógico é COR na GTK
    // (`app/widgets/controller_card.py:5462`, "accent do CONTROLE quando
    // pressionados") e era cor no piloto velho desta aba
    // (`interface/controles_vivos.py:388`,
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
    if(alvo === 'plastico'){
      const antes = el.style.getPropertyValue('--plastico');
      if(vazio || t === '—'){ el.style.removeProperty('--plastico'); }
      else { el.style.setProperty('--plastico', t); }
      return el.style.getPropertyValue('--plastico') === antes ? 0 : 1;
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
      const antes = el.getAttribute(nome);
      if(vazio || t === '—'){ el.removeAttribute(nome); }
      else { el.setAttribute(nome, t); }
      return el.getAttribute(nome) === antes ? 0 : 1;
    }
    if(el.textContent !== t){
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
  // A CARA DO AVISO, e ela REUSA a paleta das dez páginas em vez de inventar
  // cor: `--orange` é o alerta do mockup e `--elevated` é o fundo de caixa. Os
  // literais só valem se a página não definir a variável.
  const ESTILO_DO_RECADO =
    'margin:6px 0;padding:6px 9px;border-radius:6px;font-size:12px;'
    + 'line-height:1.35;pointer-events:none;'
    + 'color:var(--orange,#ffb86c);background:var(--elevated,#2b2d3a);'
    + 'border:1px solid var(--orange,#ffb86c);';
  //: A TARJA é o recado que não tem cartão a que pertencer — um gesto do
  //: rodapé, uma aba sem coluna de controle (`09-sistema`, `10-perfis`), ou o
  //: cartão daquele controle que não existe NESTA página.
  const ESTILO_DA_TARJA =
    'position:fixed;left:12px;right:12px;bottom:12px;z-index:9999;margin:0;';
  // O RECADO DA RECUSA — a frase do produto CHEGANDO AO CARTÃO.
  //
  // POR QUE ELE PRECISOU EXISTIR, medido em 02/09/2026 PELO CAMINHO DELA: o
  // contrato desta casa diz que `RuntimeError` é *"o produto recusou, e a frase
  // VAI PARA A TELA"*. Ela ia para a SAÍDA DE ERRO DO PROCESSO — `[gesto
  // falhou] …` no terminal de quem lançou a janela. Quem clica não lê terminal:
  // o botão respondia calado, e o segundo clique parecia o primeiro. Dois
  // cliques no 🎙 da `02-controles`, com um dublê que faz o daemon recusar: os
  // dois recusaram com a frase certa, o `desfechos` a guardou, e o DOM não tinha
  // uma letra dela.
  //
  // ELE NÃO USA ENDEREÇO DE PÁGINA, e isso é decisão: nenhuma das dez tem
  // `data-campo` de recado, e a `a04_iluminacao` já enterrou um justamente por
  // ser emitido num endereço que NENHUMA página tinha. Publicar HTML é ato
  // dela; o piloto é dono da JANELA e desenha o próprio aviso sem pedir campo a
  // ninguém.
  //
  // E ELE NÃO GANHA `data-campo`/`data-papel`/`data-hef` DE PROPÓSITO: o
  // `LER_CAMPOS` varre exatamente esses três, e um nó novo com um deles entraria
  // na conta da régua do mockup como campo da página — a régua passaria a medir
  // o próprio instrumento.
  function pintar_recados(lista){
    let n = 0;
    const vivas = [];
    for(const r of lista){
      // DOIS ENDEREÇOS, E ELES NÃO SÃO O MESMO. `chave` é a IDENTIDADE do
      // aviso — o `uniq` normalizado do controle que recusou —, e é por ela
      // que este nó se reencontra entre um tique e outro. `cartao` é a COLUNA
      // em que ele pousa AGORA, resolvida contra a mesa deste tique lá no
      // Python. Endereçar o nó pela coluna foi o defeito de 02/09/2026: a
      // coluna troca de dono quando um controle sai da mesa, e a recusa de quem
      // saiu passava a aparecer no cartão de quem ficou.
      const chave = String(r.chave || '');
      const onde = String(r.cartao || '');
      vivas.push(chave);
      // O CARTÃO DAQUELE CONTROLE, quando ele existe NESTA página. Quando não
      // existe — outra aba, ou o controle já fora da mesa —, a frase vira tarja
      // em vez de sumir: um recado depositado e não mostrado é o mesmo silêncio
      // que esta função nasceu para curar.
      const cartao = onde
        ? document.querySelector('[data-controle="' + onde + '"],[data-uniq="' + onde + '"]')
        : null;
      const pai = cartao || document.body;
      let el = document.querySelector('.hef-recado[data-hef-recado="' + chave + '"]');
      // A PINTURA TROCA BLOCOS INTEIROS — a fita, a tabela de perfis, o mapa do
      // gabinete. Um recado que perdeu o pai é recriado no pai de agora, com o
      // estilo do lugar em que passou a morar.
      if(el && el.parentNode !== pai){ el.remove(); el = null; }
      if(!el){
        el = document.createElement('div');
        el.className = 'hef-recado';
        el.setAttribute('data-hef-recado', chave);
        // `role=status` é o que um leitor de tela anuncia sem roubar o foco.
        el.setAttribute('role', 'status');
        // SEM CLIQUE: o aviso mora DENTRO do cartão e o ouvinte é delegado —
        // sem isto um clique nele subiria pelo `closest` e viraria gesto.
        el.style.cssText = ESTILO_DO_RECADO + (cartao ? '' : ESTILO_DA_TARJA);
        if(cartao){ pai.insertBefore(el, pai.firstChild); } else { pai.appendChild(el); }
        n += 1;
      }
      if(el.textContent !== r.texto){ el.textContent = r.texto; n += 1; }
    }
    for(const el of document.querySelectorAll('.hef-recado')){
      if(vivas.indexOf(el.getAttribute('data-hef-recado') || '') < 0){
        el.remove(); n += 1;
      }
    }
    return n;
  }
  window.__hef.pintar = function(p){
    let n = 0;
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
        const desejado = String(p.fita).trim();
        const agora = f.outerHTML.split(' data-hef-visto="1"').join('');
        if(agora !== desejado){ f.outerHTML = desejado; n += 1; }
        // O SELO DA VISITA NOS CHIPS, e sem ele o endereço deles pareceria
        // MORTO. Os chips ganharam `data-campo` em 03/09/2026 (`monta.fita`)
        // para que a régua da identidade saiba que ali não há desenho
        // congelado — mas quem os escreve é esta troca de bloco, e não o laço
        // de campos: sem o selo, a régua do mockup os contaria como endereço
        // que ninguém pinta. Ele é escrito a cada tique, mesmo quando o HTML
        // não mudou, porque é a visita SEM mudança que não deixa rastro.
        for(const c of document.querySelectorAll('.fita [data-campo]')){
          c.dataset.hefVisto = '1';
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
    for(const [seletor, html] of Object.entries(p.blocos || {})){
      const alvo = document.querySelector(seletor);
      if(alvo && alvo.innerHTML !== html){ alvo.innerHTML = html; n += 1; }
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
        el.classList.remove('alvo');
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
        el.classList.remove('off');
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
    // 3. OS RECADOS DE RECUSA, e eles vêm por ÚLTIMO porque os passos acima
    // trocam blocos inteiros — recriar antes seria pôr o aviso num cartão que a
    // pintura estava prestes a substituir.
    //
    // `undefined` QUER DIZER "esta carga não fala de recado", e é diferente de
    // uma lista vazia: a resposta de um gesto (`_deu_certo`) pinta o que trouxe
    // e não pode apagar o aviso que acabou de nascer. Quem manda a lista —
    // cheia ou vazia — é o tique, que é o dono do depósito.
    if(p.recados !== undefined){ n += pintar_recados(p.recados || []); }
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
  }
  function manda_do_alvo(ev){
      const alvo = ev.target.closest(
        '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
        '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
        '.r-aplicar,.r-salvar,.r-importar,.r-exportar');
      if(!alvo) return;
      const d = alvo.dataset;
      // DE QUAL CONTROLE, e sem isto o gesto é ambíguo: a mesa tem quatro
      // colunas iguais e um "Desligar" clicado na terceira não diz em qual
      // barra de luz mexer. O `closest` sobe até o bloco do controle — é o
      // mesmo `data-controle` que a pintura usa para achar onde escrever.
      // O RODAPÉ ENDEREÇA POR CLASSE, e não por `data-`: ele mora no
      // `topo.html`, o esqueleto das dez, e um `data-gesto` ali mudaria as dez
      // páginas de uma vez. A classe `r-<nome>` já era o endereço dele no
      // `jogar_vivo.py` — este é o quarto vocabulário, e é o último.
      const doRodape = (alvo.className.match(/\br-([a-z]+)\b/) || [])[1];
      const dono = alvo.closest('[data-controle],[data-uniq]');
      // O DATASET INTEIRO VAI JUNTO, e ele vem PRIMEIRO para que a lista
      // explícita abaixo continue mandando no que ela nomeia.
      //
      // POR QUE ISTO PRECISOU EXISTIR, medido em 02/09/2026: a lista explícita
      // tinha catorze nomes, escritos à mão, e os gestos da aba Conexões leem
      // `caminho`, `entrada` e `face` — NENHUM dos três estava nela. O botão
      // "escolher aparelho" traz `data-caminho` (o pacote o gera em
      // `a08_conexoes.py:541`), as entradas do gabinete trazem `data-entrada`
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
      manda(Object.assign(tudo, {
        gesto: d.gesto || d.hefGesto || d.papel || doRodape || 'clique',
        modo: d.modo || '', forca: d.forca || '', player: d.player || '',
        lado: d.lado || '', campo: d.campo || '', hef: d.hef || '',
        hex: d.hex || '', sensor: d.sensor || '', rota: d.rota || '',
        mudo: d.mudo || '', micModo: d.micModo || '', v: d.v || '',
        // O ALVO PADRÃO, e ele é da RÉGUA — no produto fica indefinido e esta
        // linha vale exatamente o que valia antes: string vazia.
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
            ? alvo.closest('[data-controle],[data-uniq]')
            : document.getElementById(pedido);
          if(!cx) return null;
          const fora = {};
          // A CHAVE É O `data-linha`, OU o `data-campo` quando não há. A aba
          // Navegação marcou as 21 linhas com `data-linha`; a Gatilhos já tinha
          // `data-campo` em cada valor da coluna, e marcá-los de novo seria a
          // segunda cópia do mesmo endereço.
          for(const el of cx.querySelectorAll('[data-linha],[data-campo]')){
            const chave = el.dataset.linha || el.dataset.campo;
            fora[chave] = ('value' in el)
              ? String(el.value ?? '') : (el.textContent || '').trim();
          }
          return fora;
        })(),
        texto: (alvo.textContent || '').trim().slice(0, 60),
      }));
  }
  function manda(o){
    o.pagina = location.pathname.split('/').pop();
    window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o));
  }
  return 'ok';
})();
"""


#: A TABELA LOCAL MORREU em 01/09/2026, e a razão é de processo: ela era um
#: dicionário num arquivo só, e ligar as dez abas em paralelo significaria oito
#: pessoas editando a MESMA linha. Cada pacote passa a declarar os seus com
#: `@gesto(...)`, no próprio arquivo — território exclusivo, zero merge.
#:
#: Os dois que moravam aqui foram para `a09_sistema.py` e `a10_perfis.py`.


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


def _fita(mesa: list[dict[str, Any]]) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho.

    `monta.fita()` é o dono dela nas dez páginas. Passar `mesa` é obrigatório:
    sem o argumento ele cai nos `CONECTADOS` do mockup, que são derivados no
    IMPORT e nunca recalculados — trocar `monta.MESA` de fora não alcança.
    """
    # A VERSÃO DESTA GUARDA É DA FRENTE DA ABA 05, e ela venceu a minha na
    # integração de 03/09/2026. As duas achavam o mesmo defeito; a diferença é
    # o que fazem com o controle SEM cor lida:
    #
    #   a minha  — filtrava (`[c for c in mesa if c.get("cor")]`), e o controle
    #              sem cor SUMIA da fita;
    #   a dela   — deixa todos, e quem trata a cor ausente é o `monta.fita`: o
    #              chip nasce sem `--plastico` e cai no tom neutro do esqueleto.
    #
    # A dela é a certa, e a razão é dela também: ver QUE HÁ um controle ali
    # importa mais do que saber a cor dele. Sumir da fita esconderia o controle
    # do rádio da própria fonte de identidade que a lei manda consultar.
    if not mesa:
        # MESA VAZIA é a única razão de não pintar: sem controle nenhum não há
        # chip a emitir, e devolver "" deixa a fita como está.
        #
        # A GUARDA ERA MAIOR E MENTIA — 03/09/2026. Ela dizia
        # `any(not c.get("cor") for c in mesa)`, e a intenção era esperar a
        # resposta do leitor de plástico, que é perguntado em thread. Só que
        # pelo RÁDIO a resposta NUNCA vem: o mapa de canais responde
        # `identidade.cor_do_aparelho = não` e `mesa_viva.LeitorDeCor` marca
        # aquele endereço como perguntado com `None` para sempre. Com um
        # controle no cabo e outro no rádio — a mesa dela — a fita ficava
        # eternamente no desenho, e a tela dizia `P1 · Cosmic Red · USB` /
        # `P2 · Starlight Blue · BT` sobre um White e um controle sem cor
        # legível. Fotografado nas dez abas em 03/09/2026.
        #
        # ESPERAR PELO QUE NUNCA CHEGA É CAIR DE VOLTA NO MOCKUP, que é
        # exatamente o que a lei da identidade proíbe. Quem trata a cor que não
        # veio é o `monta.fita`: o chip nasce sem `--plastico`, e o `.chip` cai
        # no tom neutro que a folha de estilo já declara como recurso.
        #
        # `SystemExit` NÃO é `Exception` — herda de `BaseException`, e um
        # `except Exception` passa ao lado. O `except` abaixo cobre os dois.
        return ""
    try:
        from hefesto_dualsense4unix.interface import monta

        return monta.fita(ativo=(mesa[0]["pref"] if mesa else "todos"), mesa=mesa)
    except (Exception, SystemExit):
        return ""


#: O SELETOR DO CLIQUE SINTÉTICO, e ele cobre os QUATRO vocabulários das dez
#: páginas — `data-gesto`, `data-hef-gesto`, `data-papel` e a classe `r-<nome>`
#: do rodapé, que endereça assim porque mora no esqueleto compartilhado.
#:
#: Um seletor que cobrisse só o primeiro daria "clicou" sobre um `null` — e
#: `null.click()` não levanta com o `||{click(){}}`, então a prova passaria em
#: silêncio sobre um botão nunca tocado. Foi assim que o `--prova-gesto` da
#: Controles deu verde sobre dois botões mortos em 29/08.
SELETOR = ("(document.querySelector('[data-gesto=\"%s\"],[data-hef-gesto=\"%s\"],"
           "[data-papel=\"%s\"],.r-%s')||{click(){}}).click()")

#: O CLIQUE QUE SABE EM QUEM CLICAR — e ele nasceu de uma medição, em
#: 02/09/2026: dos 48 gestos clicados, DEZESSEIS disseram "aplicado" sem mudar
#: o estado do daemon, e SETE deles tinham recusado CORRETAMENTE, porque o
#: clique automático não disse em qual controle agir.
#:
#: `document.querySelector` pega o PRIMEIRO nó da página, que na mesa de quatro
#: colunas do desenho é o do P1 — e o P1 pode ser justamente o lugar VAZIO.
#: Aqui a ordem é outra: primeiro os blocos dos controles CONECTADOS, na ordem
#: da mesa; só então qualquer um.
#:
#: ELE DEVOLVE ONDE CLICOU, e isso é metade do valor: o relato passa a
#: distinguir "cliquei no bloco do p1" de "cliquei num botão que não pertence a
#: controle nenhum, com o alvo forçado pela régua" — que é um DEFEITO DA
#: PÁGINA, não um sucesso do produto.
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
  const dono = el.closest('[data-controle],[data-uniq]');
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

#: O PEDIDO DE PINTURA — a expressão exata que o tique manda ao WebView.
#:
#: A GUARDA `window.__hef` NÃO É ZELO: entre o tique começar e o JS rodar, a
#: página pode ter trocado, e o `__hef` é do DOCUMENTO — morre com ele. Medido
#: em 01/09/2026, passeando pelas dez: duas abas devolviam `TypeError:
#: undefined is not an object` a cada travessia. O `-1` diz "a página trocou no
#: meio", que é diferente de "pintei nada", e o relato conta os dois separados.
#:
#: E ELA É UM TERNÁRIO, NÃO UM `|| -1`. Em JavaScript `0 || -1` é `-1`: com o
#: `||`, TODO tique que pintava zero voltava como "a página trocou", nunca
#: entrava na conta, e o detector de aba muda do relato era **ramo morto** —
#: justamente a linha escrita para pegar a `06-navegacao` publicando zero
#: endereços em 01/09. Medido em 02/09/2026: 178 tiques na `02-controles` e a
#: lista de pinturas com UM elemento só.
#:
#: ELA É CONSTANTE, e não uma f-string solta no tique, para que
#: `test_um_tique_que_pinta_zero_nao_vira_pagina_trocada` possa RODÁ-LA no
#: WebKit — a expressão que o produto manda, e não uma reescrita dela.
PEDIR_A_PINTURA = r"""
(window.__hef && window.__hef.pintar) ? window.__hef.pintar(CARGA) : -1
"""

#: O LEITOR DO DOM, e ele é O instrumento do `--prova-de-mockup`: devolve, em
#: ordem de documento, o que a TELA está mostrando em cada endereço de pintura.
#:
#: ELE LÊ O MESMO ALVO QUE O `escrever()` ESCREVE — a largura da barra, o
#: `value` do campo, o texto. Ler sempre `textContent` diria que toda barra de
#: bateria continua no mockup, porque a pintura dela nunca toca texto nenhum.
#:
#: `fundo` e `html` caem no texto de propósito: o WebKit devolve os dois
#: NORMALIZADOS (a cor vira `rgb(…)`, as aspas dos atributos trocam) e comparar
#: a forma do arquivo com a forma do navegador acusaria mudança onde não houve.
#: `regua_do_mockup._campo` lê os mesmos dois pelo texto, e é isso que faz os
#: dois lados casarem.
#:
#: `cor` NÃO CAI NO TEXTO, e a diferença com o `fundo` é medida, não de gosto.
#: Sondado no WebKit desta máquina em 02/09/2026, com a página offscreen:
#:
#:     '#6272a4'   → 'rgb(98, 114, 164)'     'red'         → 'red'
#:     '#fff'      → 'rgb(255, 255, 255)'    'transparent' → 'transparent'
#:     'var(--x)'  → 'var(--x)'              'rgb(1,2,3)'  → 'rgb(1, 2, 3)'
#:
#: **A FRASE QUE ESTAVA AQUI CAIU NO MESMO DIA**: *"a normalização é FECHADA e
#: pequena — hexadecimal e `rgb()` viram uma só forma, e todo o resto volta como
#: foi escrito"*. Não é fechada. A sonda de 51 formas mostrou que o `hsl()`
#: também vira `rgb()`, que o alfa é serializado CURTO, que o alfa cheio some, e
#: que todo CSS inválido volta `''` em vez de voltar como foi escrito.
#: `regua_do_mockup._cor_css` acompanha TODAS essas famílias, e quem confere não
#: é uma transcrição: `test_a_cor_e_medida_no_webkit_e_nao_transcrita` refaz a
#: sonda neste motor a cada execução. Por isso a régua pode ler o `color` de
#: verdade em vez do texto visível. Um campo de cor lido pelo texto seria
#: INDECIDÍVEL para sempre: pintar a cor não mexe numa letra.
#:
#: O QUINTO CAMPO É O SELO DA VISITA, e ele não vem da tela — vem do piloto.
#: Ver o comentário do `el.dataset.hefVisto` no BOOTSTRAP: é o que separa
#: "pintou igual" de "não pintou" nos 74 campos que a régua não decidia.
LER_CAMPOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('[data-campo],[data-papel],[data-hef]')){
    const chave = el.dataset.campo || el.dataset.papel || el.dataset.hef || '';
    const bloco = el.closest('[data-controle],[data-uniq]');
    const dono = bloco ? (bloco.dataset.controle || bloco.dataset.uniq || '') : '';
    const alvo = el.dataset.hefAlvo || 'texto';
    let v;
    if(alvo === 'largura'){ v = el.style.width; }
    else if(alvo === 'valor'){ v = ('value' in el) ? String(el.value ?? '') : ''; }
    else if(alvo === 'cor'){ v = el.style.color; }
    else if(alvo === 'atributo'){
      // O ATRIBUTO, NA MESMA LÍNGUA DOS DOIS LADOS: o texto que ele guarda, ou
      // `''` quando não há atributo nenhum. `regua_do_mockup._campo` lê o mesmo
      // atributo do arquivo com o mesmo vazio por omissão — sem isso um SVG cujo
      // `data-colorway` o produto APAGOU (o aparelho não disse a cor) seria lido
      // como `null` de um lado e `''` do outro, e a régua acusaria a pintura
      // certa.
      v = el.getAttribute((el.dataset.hefAtributo || '').trim().toLowerCase()) || '';
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

#: O MÉTODO LENTO DE CADA GESTO, para a prova esperar o tempo dele. Só os que
#: passam do padrão precisam de linha aqui.
_METODO_DO_GESTO = {
    "atualizar": "daemon.reload", "modo-dualsense": "gamepad.emulation.set",
    "modo-xbox": "gamepad.emulation.set", "modo-navegacao": "mouse.emulation.set",
    "hefesto": "native.mode.set", "ativar": "profile.switch",
    "aplicar": "profile.apply_draft", "reconectar": "coop.sync",
}

#: OS GESTOS QUE MEXEM NA MÁQUINA DELA, e que a prova botão a botão NÃO clica
#: sozinha. Não é timidez: `desligar` para o daemon e ela fica sem controle no
#: meio do trabalho; `restaurar-de-fabrica` apaga configuração; `reiniciar`
#: derruba a sessão do daemon. Uma régua não mexe na máquina de alguém para
#: provar que sabe clicar.
#:
#: Para incluí-los, `--incluir-perigosos` — e aí é escolha de quem roda.
#: A chave é `(página, gesto)`, e a qualificação NÃO é preciosismo: `modo` na
#: Navegação liga a emulação de mouse e MEXE NO CURSOR DELA — na tela dela,
#: enquanto ela trabalha. O mesmo `modo` nos Gatilhos escolhe um efeito e é
#: inócuo. Uma lista por nome cru trataria os dois igual, e a escolha seria
#: entre não provar o seguro ou estragar o trabalho dela.
PERIGOSOS = {
    ("09-sistema.html", "desligar"), ("09-sistema.html", "reiniciar"),
    ("09-sistema.html", "restaurar-de-fabrica"), ("09-sistema.html", "refazer-proton"),
    ("09-sistema.html", "autostart"),
    ("10-perfis.html", "remover"), ("10-perfis.html", "novo"),
    ("10-perfis.html", "voltar-a-de-ontem"), ("10-perfis.html", "duplicar"),
    # OS CAMPOS DO EDITOR GRAVAM NO DISCO DELA, e o `editor.nome` RENOMEIA o
    # perfil escolhido. Uma régua que os clicasse com o valor que estivesse na
    # tela renomearia um perfil dela para provar que sabe digitar — e o `nome` é
    # a identidade do arquivo, não um campo qualquer.
    ("10-perfis.html", "editor.nome"), ("10-perfis.html", "editor.jogo"),
    ("10-perfis.html", "editor.ambiente"), ("10-perfis.html", "detectar"),
    # O CURSOR É DELA. Ligar a emulação de mouse move o ponteiro na tela em que
    # ela está trabalhando — é o mesmo motivo de toda janela desta casa nascer
    # com `--oculta`.
    ("06-navegacao.html", "modo"),
    # E A MESMA COISA PELA OUTRA PORTA, achada em 03/09/2026 pelo juiz da leva:
    # o chip "Navegação" da aba Jogar chama `mouse.emulation.restore` (o
    # terceiro dos três IPCs de `a01_jogar.modo_navegacao`), que LIGA o mouse
    # conforme a preferência persistida. Só o `("06-navegacao.html", "modo")`
    # estava isento, e o cursor é o mesmo cursor.
    ("01-jogar.html", "modo-navegacao"),
    # A TELA É DELA, E A STEAM ABRE EM CIMA. `abrir-lancador` chama
    # `steam_launch_options.reopen_steam`, que abre a janela da Steam
    # DESANEXADA — ela não nasce oculta, não obedece ao `--oculta` desta casa e
    # não some quando a prova termina. Uma régua que a clicasse encheria a tela
    # dela de Steam a cada volta.
    # ELA ESCOLHEU ESTA COMBINAÇÃO — decisão 17 dela, 03/09/2026: o botão LIGA
    # *e* o gesto entra aqui, para que a prova automática nunca o clique. As
    # duas metades são uma decisão só: ligar sem o isento seria ligar contra
    # ela.
    ("07-lancadores.html", "abrir-lancador"),
    # O SALVAR GRAVA NO PERFIL DELA, SEM PERGUNTAR. O rodapé o registra como
    # `@gesto("*", "salvar")`, então ele vive nas DEZ abas — e a prova botão a
    # botão, rodando aba por aba, escrevia dez vezes no disco dela por volta.
    # MEDIDO EM 03/09/2026: dez gravações em `meu_perfil.json` entre 07:14 e
    # 07:47, uma por aba provada. Nada dela se perdeu desta vez — as dez foram
    # re-salvamentos do mesmo conteúdo —, mas o caminho para perder existe e
    # está nomeado: desligar a barra de luz e salvar copia a cor apagada por
    # cima da que ela escolheu, e isso não se desfaz.
    #
    # A CHAVE É CORINGA de propósito: o gesto é um só nas dez páginas, e
    # `_alvos_a_clicar` casa `("*", nome)` além de `(página, nome)`.
    ("*", "salvar"),
    # E O `salvar` NÃO ERA O ÚNICO QUE ESCREVE — medido em 03/09/2026, rodando
    # o `--prova-no-aparelho` na aba Gatilhos com o produto instalado. O
    # `rodape.salvar` diz na docstring *"é o único gesto desta leva que
    # escreve"*, e a lista acima foi montada sobre essa frase. Ela é FALSA:
    # `a03_gatilhos.guardar` também grava em `meu_perfil.json`. A prova é o log
    # da própria régua, que anunciou `pulados por mexerem na máquina dela:
    # salvar` e mesmo assim deixou para trás
    # `profile_salvo arquivo=meu_perfil.json origem=interface-nova`, com backup
    # novo em `.historico/` e um bloco `triggers` a mais no perfil dela.
    #
    # O GESTO É LEGÍTIMO — "Guardar esse efeito" existe para gravar, e gravar é
    # o que ela pediu dele. O que não é legítimo é uma RÉGUA escrever no perfil
    # dela para provar que sabe clicar; é a mesma razão do `salvar` acima.
    ("03-gatilhos.html", "guardar"),
    # E O TRILHO DE BRILHO PASSOU A GRAVAR — 03/09/2026, decisão dela:
    # perguntada se mexer no brilho grava o perfil na hora ou espera o "Salvar
    # Perfil", ela respondeu *"Grava na hora"*. O gesto entra aqui na MESMA
    # decisão que o liga, como o `abrir-lancador` da Lançadores: ligar sem o
    # isento seria ligar contra ela.
    #
    # O QUE A RÉGUA FARIA SEM ESTA LINHA: `_alvos_a_clicar` acha o
    # `<input type="range">` pelo `data-gesto` e o aciona com o valor que
    # estiver na tela — e o gesto grava `lightbar_brightness` no override do
    # controle, no perfil ATIVO, com backup novo em `.historico/`. Pior que o
    # `salvar`, que ao menos regrava o que já estava lá: um arraste da régua
    # copia por cima do brilho que ela escolheu, e isso não se desfaz.
    ("04-iluminacao.html", "brilho"),
    # O ⊘ DA CONEXÕES DISPENSA UMA ORDEM DE SERVIÇO DELA, E NÃO VOLTA SOZINHO.
    #
    # MEDIDO EM 03/09/2026, com o journal dos dois lados. Às 16:11:53, ANTES da
    # prova, o daemon tinha `MesaDeclarada(… ordens_dispensadas={})`; depois da
    # volta, o `maquina.json` dela trazia
    # `ordens_dispensadas={'dongle_atras_de_hub': {'arranjo': '3-1.2 3-1.4',
    # 'quando': '2026-09-03'}}` — e o Check-up dela tinha perdido a linha
    # *"2 de 3 adaptadores Bluetooth chegam ao computador por dentro de um
    # hub"*, uma das DUAS únicas que acusam nesta máquina.
    #
    # POR QUE SÓ ESTE, e não os outros onze gestos desta aba que também chamam
    # `machine.declare`: os outros clicam o valor que a PÁGINA mostra, e a
    # página mostra o que a declaração já dizia — re-declarar é idempotente. Foi
    # o que a medição do mesmo dia mostrou: `sala-altura`, `sala-visada` e
    # `mic-existe` gravaram exatamente o que já estava lá, e o ÚNICO campo que
    # mudou no arquivo foi `ordens_dispensadas`. O ⊘ é diferente porque o que
    # ele grava não vem da declaração: vem do EXAME.
    #
    # DISPENSAR NÃO É RECUPERÁVEL PELA TELA: `ordens_da_mesa.ordens_novas`
    # compara o arranjo guardado com o de agora, e enquanto os cabos não
    # mudarem a linha fica calada. Uma régua não cala um achado da máquina dela
    # para provar que sabe clicar.
    ("08-conexoes.html", "ignorar"),
    # A FORÇA DA VIBRAÇÃO PASSOU A ESCREVER NO PERFIL DELA — 03/09/2026, e é
    # consequência direta da decisão dela de construir a política POR CONTROLE.
    # Até ontem o clique num degrau ia por IPC (`rumble.policy_set`), que não
    # deixa rastro em disco; hoje ele grava `controllers[uniq].rumble` no perfil
    # ATIVO e dispara `profile.switch`, exatamente como o `teto-da-vibracao` da
    # Conexões — que já está isento acima, pelo mesmo motivo.
    #
    # SÃO OS DOIS, e o segundo não é o mesmo botão: `forca` são os quatro
    # degraus, `intensidade` é a barra arrastável. Uma prova botão a botão que
    # clicasse os dois deixaria, por volta e por aba, uma escolha de vibração
    # que ela não fez em cada controle da mesa — e a régua não tem como saber
    # qual era a de antes.
    ("05-vibracao.html", "forca"), ("05-vibracao.html", "intensidade"),
}


def _achatar(o: Any, prefixo: str = "") -> dict[str, Any]:
    """O estado do daemon como `{caminho: valor}` — para comparar antes/depois.

    Achatar é o que torna a comparação LEGÍVEL: sem isso, "o estado mudou" seria
    um diff de dois dicionários aninhados de 49 chaves, e ninguém leria qual
    campo se mexeu. Com isso, o relato diz
    `controllers.0.lightbar_rgb: [0,0,255] → [126,184,212]`.
    """
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


#: OS CAMPOS QUE MUDAM SOZINHOS a cada tique — o relógio do daemon, os contadores
#: de força-feedback, a posição dos analógicos. Compará-los faria TODO gesto
#: parecer que mudou alguma coisa, que é o mesmo que não medir nada.
RUIDO = ("visto_ha_s", "ha_s", "_count", "nascimento", "age_sec", "uptime",
         "inputs.", "motion_", "forwards", "counters.", "_ultimos_",
         # OS EIXOS NA RAIZ DO STATE, e não só dentro de `inputs`. O daemon
         # publica `lx`, `ly`, `rx`, `ry`, `l2_raw` e `r2_raw` nos DOIS lugares,
         # e o filtro só cobria o segundo. Um analógico em repouso oscila um
         # ponto — `ry: 128 → 129` — e isso fazia um botão qualquer parecer que
         # mudou o aparelho. Medido em 01/09 na aba Conexões: o `sala-altura`
         # deu ✓ sobre o tremor do polegar dela.
         "lx", "ly", "rx", "ry", "l2_raw", "r2_raw", "buttons",
         "battery_pct", "bt_mic")


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`.

    É o que o despachante usa de chave, e é o que o `load-changed` entrega. Sai
    da URI e não de um estado que o piloto guarde: guardar seria uma segunda
    fonte da verdade sobre em que aba a janela está, e as duas divergiriam na
    primeira navegação que falhasse no meio.
    """
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


class Piloto:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        #: Quantos valores cada aba pintou, na ordem em que foram visitadas —
        #: só os tiques que escreveram ALGUMA coisa. É o que mede a quietude:
        #: uma aba sadia pinta uma vez e sossega, e uma que soma pintura a cada
        #: tique tem endereço que o navegador recusa.
        self.pinturas: dict[str, list[int]] = {}
        #: Quantos tiques cada aba levou, PINTANDO OU NÃO. Sem este contador não
        #: dá para dizer "a aba tem pacote e nenhum endereço casou": um tique de
        #: zero valor não deixava rastro nenhum, e o detector de aba muda ficava
        #: inalcançável. Medido em 02/09/2026 — 178 tiques na `02-controles` e um
        #: só elemento em `pinturas`.
        self.tiques: dict[str, int] = {}
        #: Quantas vezes a página TROCOU no meio de um tique. É o `-1`, e ele é
        #: um fato diferente de "pintei nada" — misturar os dois foi o que
        #: engoliu o zero.
        self.trocas: dict[str, int] = {}
        self.visitadas: list[str] = []
        self.custos: list[float] = []
        #: O que ESTE processo mandou ao daemon, e o que recusou por falta de
        #: dono. Os dois contados: sem o segundo, "nada aconteceu" e "não havia
        #: quem atendesse" ficariam indistinguíveis.
        self.gestos: list[dict[str, Any]] = []
        self.aplicados: list[str] = []
        self.recusados: list[str] = []
        #: A mesa e o contexto do último tique — é o que o gesto recebe. Sem
        #: eles, um clique que chega entre dois tiques não teria com que
        #: trabalhar, e resolver o `uniq` na hora exigiria um IPC a mais por
        #: clique.
        #: O que a prova botão a botão mediu, um por gesto.
        self.provas: list[dict[str, Any]] = []
        #: O DESFECHO DE CADA GESTO, por `página:nome`. Sem isto, um gesto que
        #: RECUSOU DIZENDO e um gesto que aplicou e não fez nada saem do relato
        #: iguais — foi assim que os sete "recusaram corretamente" de 02/09
        #: entraram na conta dos dezesseis "aplicado e nada mudou".
        self.desfechos: dict[str, tuple[str, str]] = {}
        #: Em que bloco de controle cada clique caiu — ou se o alvo foi FORÇADO
        #: pela régua, que é defeito da PÁGINA e não sucesso do produto.
        self._onde_clicou: dict[str, str] = {}
        #: A FRASE DE RECUSA DE CADA CONTROLE —
        #: `{uniq_normalizado: (frase, quando_monotônico)}`.
        #:
        #: ELA VIVE NO ESTADO, e não no instante do clique: a tela repinta a cada
        #: 500 ms, e uma frase publicada só no tique da borda tem probabilidade
        #: ~0 de coincidir com o tique em que ela olha — existiria e ninguém a
        #: veria. É a mesma razão pela qual
        #: `daemon/subsystems/recado_do_microfone.py` é um DEPÓSITO e não um
        #: evento, e a chave segue a mesma ideia: uma por controle, porque na
        #: mesa de quatro a recusa de um não pode aparecer no cartão do vizinho.
        #: A chave vazia é o recado da MESA — o gesto que não age em controle
        #: nenhum.
        #:
        #: A CHAVE É O ENDEREÇO, E NÃO A POSIÇÃO, e a mudança é de 02/09/2026.
        #: Guardada por `pref` a frase ficava colada à COLUNA, e a coluna troca
        #: de dono: `mesa_viva.mesa_do_estado` enumera os conectados de 1 a cada
        #: tique (*"o `pref` continua sendo a POSIÇÃO … e `jogador` continua
        #: sendo a IDENTIDADE"*). MEDIDO com dublê de dois controles: recusa no
        #: 🎙 do `p1` (o do cabo), o do cabo SAI da mesa, o do rádio vira `p1` —
        #: e o cartão dele passava a mostrar, por até 30 s, uma frase que
        #: termina em *"ou este controle saiu da mesa"*, sobre OUTRO controle.
        #: É o defeito de identidade que esta casa já pagou várias vezes, e o
        #: dono certo do endereço já existia: `core/sysfs_leds.norm_mac`.
        #:
        #: SÓ O LAÇO DO GTK ESCREVE AQUI. O gesto corre em thread, e depositar de
        #: lá deixaria o tique iterando um dicionário que outra thread muda.
        self._recados: dict[str, tuple[str, float]] = {}
        self._fila: list[str] = []
        #: O `--prova-de-mockup`: o que o ARQUIVO crava, o que o DOM mostra
        #: ANTES de qualquer pintura, e o veredito de cada campo por aba.
        self.cravados: dict[str, list[regua_do_mockup._Campo]] = {}
        self.pristino: dict[str, list[list[str]]] = {}
        self.vereditos: dict[str, list[regua_do_mockup._Veredito]] = {}
        #: Onde a régua não conseguiu ler o que prometeu ler. Uma linha aqui é
        #: a régua confessando, e ela reprova por isso.
        self.cegueiras: list[str] = []
        self._fila_de_abas: list[str] = []
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora: dict[str, Any] = {}
        self._mesa_de_agora: list[dict[str, Any]] = []
        self._ctx_de_agora = pacotes.Contexto(state={})
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)
        #: Os `uniq` já perguntados ao leitor de cor. Sem esta trava, cada tique
        #: abriria uma thread nova para o mesmo controle — 2 por segundo.
        self.perguntados: set[str] = set()

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._navegou,
            oculta=args.oculta,
            subtitulo="as dez abas, vivas",
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        # O SEGUNDO OUVINTE, e ele precisa ser próprio: o `ao_sair_da_aba` da
        # biblioteca dispara UMA vez, na saída da aba desta janela. Daqui em
        # diante toda página é "fora da aba" e o callback não volta. Sem este
        # `connect`, Jogar → Gatilhos → Jogar não produziria evento nenhum e o
        # piloto ficaria pintando a página errada. É a mesma nota que o
        # `controles_vivos` carrega, e a razão é a mesma.
        self.view.connect("load-changed", self._carregou)

        # O SELETOR DE ARQUIVO É DA JANELA, e por isso é ligado AQUI. Os pacotes
        # são puros — um `import gi` neles obrigaria toda régua a ter GTK e o CI
        # a rodar com display. A ponte declara o ponto de extensão recusando; o
        # piloto o preenche ao subir.
        ponte.escolher_arquivo = self._escolher_arquivo
        ponte.salvar_arquivo = self._salvar_arquivo

    # -- o seletor de arquivo, que é do sistema ---------------------------
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

    # -- os gestos ---------------------------------------------------------
    def _gesto(self, o: dict[str, Any]) -> None:
        """tela → Python, já em JSON. Quem recusa o que não é objeto é a ponte.

        O QUE ELE FAZ E O QUE NÃO FAZ, e a diferença é a regra desta casa: ele
        despacha o que tem DONO no daemon e RECUSA o resto **com o motivo na
        tela**. Um botão que responde calado quando não há quem atenda é a
        `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura — quem clica conclui que
        funcionou.
        """
        self.gestos.append(o)
        nome = str(o.get("gesto") or "")
        pagina = str(o.get("pagina") or self.pagina)  # (noqa-acento: verbo)  (nome de variável)
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.recusados.append(f"{pagina}:{nome}")
            self.desfechos[f"{pagina}:{nome}"] = ("sem dono", "")
            print(f"[gesto sem dono] {pagina} · {nome} · {o.get('texto', '')!r}")
            return
        # O `uniq` É RESOLVIDO AQUI, e não dentro do gesto: a tela endereça por
        # `pref` (`p1`), o daemon por `uniq` (`d4:2f:00:00:…`), e a mesa que traduz é
        # do piloto. Cada gesto resolvendo por conta própria seria a mesma
        # tradução escrita nove vezes — e a nona estaria errada.
        pref = str(o.get("controle") or "")
        for c in self._mesa_de_agora:
            if c.get("pref") == pref or str(c.get("uniq") or "") == pref:
                o = {**o, "uniq": str(c.get("uniq") or "")}
                break
        # O RECADO É ENDEREÇADO AQUI, PELO MESMO `uniq` que o gesto recebe, e
        # não pelo `pref`: a coluna troca de dono entre o clique e o tique
        # seguinte. Ver `self._recados`. Sem `uniq` resolvido (gesto de mesa, ou
        # clique sobre uma coluna que já esvaziou) a chave é vazia, e o aviso
        # vira tarja de rodapé — que é honesto: não há cartão de quem dizer.
        alvo = norm_mac(str(o.get("uniq") or "")) or ""

        # EM THREAD, e não no laço do GTK. MEDIDO em 01/09/2026, com o daemon
        # dela: `daemon.reload` leva **9,5 segundos** — `daemon.resume` leva 1
        # ms e `daemon.status` 57. Um gesto síncrono congelaria a janela inteira
        # por nove segundos e meio, sem nada na tela dizendo por quê, e quem
        # clicou concluiria que o app travou.
        def trabalhar() -> None:
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                # O `erro` é AMARRADO no argumento do lambda, e não capturado
                # do escopo: o `except ... as` do Python apaga o nome ao sair do
                # bloco, e o lambda roda DEPOIS, no laço do GTK. Sem a amarra é
                # `NameError` na hora de relatar a falha — o erro comendo o
                # relato do erro.
                # A FRASE DA RECUSA É GUARDADA, e não só impressa. `ValueError`
                # é clique inválido e `RuntimeError` é o produto recusando com
                # o motivo — as duas coisas são DESFECHO, e um relato que as
                # some com "não fez nada" mente sobre sete botões desta casa.
                self.desfechos[f"{pagina}:{nome}"] = (
                    "recusou dizendo", f"{type(erro).__name__}: {erro}")
                # A FRASE VAI PARA A TELA, e o `idle_add` é o que a leva ao
                # único laço que pode tocar o DOM e o depósito. Até 02/09/2026
                # esta linha só imprimia no `stderr` — ver `_recusou_dizendo`.
                GLib.idle_add(
                    lambda x=erro: self._recusou_dizendo(pagina, nome, alvo, x))
                return
            # OS DOIS DESFECHOS SÃO ANOTADOS NO MESMO LUGAR, e é aqui: o `except`
            # logo acima guarda a recusa, e esta linha guarda o "voltou sem
            # levantar". Anotar o sucesso lá no `_deu_certo` separaria os dois
            # ramos do mesmo `try`, e quem lesse um não veria o outro.
            self.desfechos[f"{pagina}:{nome}"] = ("aplicou", "")
            GLib.idle_add(lambda r=resposta: self._deu_certo(pagina, nome, r))

        threading.Thread(target=trabalhar, daemon=True).start()

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
            # A GUARDA `window.__hef &&` é a mesma da pintura, e pela mesma
            # razão: entre o clique e a volta da thread a página pode ter
            # trocado, e o `__hef` morre com o documento.
            self._js(f"window.__hef && window.__hef.pintar({_json(resposta)})")
            print(f"[gesto] {pagina} · {nome} → aplicado, e a resposta foi para a tela")
            return False
        print(f"[gesto] {pagina} · {nome} → aplicado")
        return False

    def _recusou_dizendo(self, pagina: str, nome: str, uniq: str,
                         erro: BaseException) -> bool:
        """A recusa do produto chegando ao CARTÃO — e não à saída de erro.

        O CONTRATO É DE ANTES DESTA FUNÇÃO e é explícito: `RuntimeError` quer
        dizer *"o produto recusou, e a frase VAI PARA A TELA"*, escrita para
        quem está com o controle na mão. Até 02/09/2026 ela ia para o `stderr`
        do processo, e quem clica na janela não lê o terminal de quem a lançou.

        MEDIDO PELO CAMINHO DELA, e é a forma de defeito mais cara desta casa —
        *alguém curou o caminho e provou a cura num caminho que ela não usa*:
        dois cliques no 🎙 da `02-controles`, com um dublê que faz o `mic.set`
        recusar, deram DUAS linhas no terminal, `desfechos` com a frase certa, e
        um DOM sem uma letra dela. O segundo clique parecia o primeiro.

        `ValueError` NÃO ENTRA, e a razão é o mesmo contrato: ele é *clique
        inválido*, e as frases que os pacotes escrevem nele falam com quem
        programa — uma delas cita `interface/aba06.py:OPCOES_TECLADO`. Pôr um
        caminho de arquivo no cartão dela trocaria um silêncio por um ruído. O
        que falta ali é uma frase que ela decida, e está no relato desta frente.

        O `uniq` CHEGA NORMALIZADO, e é a chave do depósito. Ele não é o `pref`
        do clique: quem endereça pela coluna endereça um lugar que troca de
        dono. Ver `self._recados`.
        """
        print(f"[gesto falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
        if not isinstance(erro, RuntimeError):
            return False
        self._recados[uniq] = (str(erro), time.monotonic())
        # NA HORA, e não no próximo tique. Meio segundo entre o clique e a
        # resposta basta para ela clicar de novo achando que o primeiro não
        # pegou — que é o defeito de origem, não um detalhe de acabamento.
        self._js(f"window.__hef && window.__hef.pintar("
                 f"{_json({'recados': self._recados_para_a_tela()})})")
        return False

    def _recados_para_a_tela(self) -> list[dict[str, str]]:
        """As frases de recusa ainda vivas, a poda das vencidas, e o CARTÃO de
        cada uma resolvido contra a mesa DE AGORA.

        A PODA MORA NO LEITOR, e não num relógio próprio: um `timeout_add` por
        recado seria um temporizador por clique recusado, e o que apaga a frase
        passaria a ser um agendamento que a troca de aba não cancela. Aqui a
        conta é feita quando alguém pergunta — que é a cada tique, e é o mesmo
        instante em que a lista vai para a tela.

        O RELÓGIO É MONOTÔNICO pelo mesmo motivo do
        `recado_do_microfone.quando_s`: um acerto de hora do sistema não pode
        fazer um aviso de agora parecer de ontem.

        A TRADUÇÃO `uniq → pref` É FEITA AQUI, NO INSTANTE DA PINTURA, e é o que
        fecha o defeito de identidade: o depósito guarda o ENDEREÇO, e quem
        pergunta a que coluna ele corresponde é a mesa deste tique. Quando o
        controle SAIU da mesa não há coluna, e o `cartao` sai vazio: o aviso vira
        tarja de rodapé em vez de pousar no cartão de quem ficou. Deixá-lo
        pousar ali seria a tela afirmando, sobre um controle, uma recusa de
        outro — a forma exata do defeito que o
        `test_a_frase_pousa_no_cartao_de_quem_foi_clicado` já impede no INSTANTE
        e que só aparece no TEMPO.

        SÃO DOIS ENDEREÇOS E NÃO UM: `chave` é a IDENTIDADE do aviso (o `uniq`
        normalizado, e é por ela que o BOOTSTRAP reencontra o próprio nó), e
        `cartao` é ONDE ELE POUSA AGORA. Somar os dois num campo só faria dois
        controles fora da mesa colidirem no mesmo `data-hef-recado` vazio — e a
        segunda frase sumiria calada, que é o silêncio que este canal existe
        para curar.
        """
        agora = time.monotonic()
        for chave, (_frase, quando) in list(self._recados.items()):
            if agora - quando >= SEGUNDOS_DO_RECADO:
                del self._recados[chave]
        onde_esta = {norm_mac(str(c.get("uniq") or "")) or "": str(c.get("pref") or "")
                     for c in self._mesa_de_agora}
        return [{"chave": chave,
                 "cartao": onde_esta.get(chave, "") if chave else "",
                 "texto": frase}
                for chave, (frase, _quando) in sorted(self._recados.items())]

    # O `_ipc` CRU MORREU em 01/09/2026. Ele abria o socket à mão e montava o
    # JSON-RPC — reescrevendo o que o `app/ipc_bridge.py` já faz há meses, com
    # timeout pensado e a recusa do daemon traduzida em frase de tela. Quem
    # escreve agora é `pacotes/ponte.py`, e ele é UM caminho só.

    # -- navegação ---------------------------------------------------------
    def _navegou(self, titulo: str) -> None:
        """Ela clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view: Any, evento: Any) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            return
        self.pagina = nova
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        # A PONTE MORRE A CADA CARGA — o `window.__hef` é do documento antigo.
        # Reinstalar é obrigatório, e esquecer isso é como uma aba nova nasce
        # muda sem uma linha de erro.
        self.pronto = False
        self._antes_de_instalar()

    def _instalar(self) -> None:
        self._antes_de_instalar()

    def _antes_de_instalar(self) -> None:
        """O DOM VIRGEM é lido AQUI, e é o único instante em que ele existe.

        A pintura começa no `_instalado`, logo abaixo. Depois dela, o que a
        página mostra já é uma mistura do que o arquivo cravou com o que o
        produto escreveu — e não há como desfazer a mistura olhando o resultado.
        Por isso o retrato do virgem vem ANTES do bootstrap, e o `_tique()` se
        recusa a pintar enquanto ele não voltou.

        NO PRODUTO ISTO NÃO ACONTECE: sem `--prova-de-mockup` o `if` é falso e a
        instalação segue exatamente como antes, sem um IPC a mais.
        """
        if self.args.prova_de_mockup and self.pagina not in self.pristino:
            pagina = self.pagina

            def retratou(valor: Any, erro: Any) -> None:
                self._leu_virgem(pagina, valor, erro)

            self.ponte.perguntar(LER_CAMPOS, retratou)
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _leu_virgem(self, pagina: str, valor: Any, erro: Any) -> None:
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li o DOM virgem — {erro}")
            # A LISTA VAZIA DESTRAVA O TIQUE. Sem ela a aba ficaria presa para
            # sempre esperando um retrato que não vem, e o passeio inteiro
            # morreria calado na primeira falha de JS.
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
        # O TIMER E A SAÍDA SÓ UMA VEZ, e a flag é própria. Testar `voltas == 0`
        # aqui não funciona: `_tique()` roda logo acima e já a incrementa, então
        # a condição era sempre falsa — a janela ficava viva para sempre, sem
        # tique periódico e sem relato. Medido na primeira execução deste piloto.
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    # -- a pintura ---------------------------------------------------------
    def _contexto(self, st: dict[str, Any]) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        # A COR DO PLÁSTICO vem do leitor, que responde `{}` até a primeira
        # pergunta voltar — por isso a mesa nasce "Não sei" e vira "Starlight
        # Blue" na segunda remontagem. Perguntar é BLOQUEANTE (fala com o
        # aparelho), então vai em thread: no tique ela travaria a janela.
        for c in ctx_conectados:
            uniq = str(c.get("uniq") or "")
            if uniq and uniq not in self.perguntados:
                self.perguntados.add(uniq)
                threading.Thread(
                    target=self.leitor.perguntar, args=(uniq,), daemon=True
                ).start()
        conectados = ctx_conectados
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={})
        return ctx, para_pref

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        if self.args.prova_de_mockup:
            if self.pagina not in self.pristino:
                # O RETRATO DO VIRGEM AINDA NÃO VOLTOU. Pintar antes dele
                # apagaria a única testemunha do que o arquivo crava — e a
                # régua passaria a medir a pintura contra ela mesma.
                return True
            self._voltas_da_aba += 1
            # A CONTA SOBE AQUI, ANTES do `pacote is None` lá embaixo, e não é
            # detalhe: a `07-lancadores` não tem pacote e sai daquele `return`
            # sem contar volta nenhuma. Com a conta lá, o passeio ficava preso
            # nela para sempre — a única aba que o `--passear` também nunca
            # visitou, pela mesma razão.
            if self._voltas_da_aba >= self.args.voltas_por_aba and not self._medindo:
                self._medindo = True
                pagina = self.pagina

                def mediu(valor: Any, erro: Any, p: str = pagina) -> None:
                    self._fechou_a_aba(p, valor, erro)

                self.ponte.perguntar(LER_CAMPOS, mediu)
        t0 = time.perf_counter()
        try:
            st = mesa_viva.estado_do_daemon()
        except Exception as e:
            print(f"[daemon mudo] {e}", file=sys.stderr)
            return True

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        # A MESA DE AGORA fica guardada para o gesto: um clique chega entre dois
        # tiques, e sem ela resolver o `uniq` custaria um IPC a mais por clique.
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except Exception as e:
            # UMA ABA QUE LEVANTA NÃO DERRUBA A JANELA. Ela para de pintar e o
            # motivo sai no relato — que é diferente de a tela congelar sem
            # dizer por quê, e é o estado que o `Contexto.por_uniq` já protege.
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            # A ABA SEM PACOTE AINDA TEM CABEÇALHO, e ele é das DEZ. Antes desta
            # linha ela saía daqui sem pintar nada — nem o topo, nem a fita — e
            # a `07-lancadores` (a única sem pacote, por decisão dela) ficava
            # mostrando o desenho inteiro. Medido pela `--prova-de-mockup` em
            # 02/09/2026, com o daemon dela no ar:
            #
            #     perfil  = 'Mortal Kombat'   ← e o perfil ativo dela era outro
            #
            # É a oitava aparição do defeito que esta casa já nomeou — *a tela
            # afirmando o que não é* —, e ela passa por aqui porque nenhuma aba
            # é dona do topo. Um pacote VAZIO é o que ela é: nada de próprio a
            # pintar, e tudo o que é de todas continua valendo.
            pacote = {}

        # A FORMA CANÔNICA E A TRADUÇÃO `uniq → pref`, as duas no despachante.
        # Ele é quem conhece as três palavras que as abas usam para a mesma
        # coisa (`colunas`, `cartoes`, `cards`) e o que cada uma deixa solto na
        # raiz. Repetir isso aqui seria um segundo dono da mesma regra.
        carga = pacotes.normalizar(pacote, para_pref)
        # O CABEÇALHO É DE TODAS AS ABAS, e não de nenhum pacote: a contagem e o
        # perfil ativo moram no `topo.html`, que é um só para as dez. Sem esta
        # linha os três campos ficavam vazios em TODA aba — cada pacote cuidava
        # da sua e ninguém cuidava do que era de todas.
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        # A FITA É DE TODAS AS ABAS, e ela MENTE se não for repintada: o HTML
        # publicado traz os dois chips do mockup ("P1 · Cosmic Red · USB",
        # "P2 · Starlight Blue · BT"), e com UM controle no cabo a tela dizia
        # que havia dois, um deles no rádio. É a quinta reincidência do mesmo
        # defeito nesta casa — *uma frase que nomeia um controle fora da mesa* —
        # e a foto da aba Perfis o mostrou de novo em 01/09/2026, já com o topo
        # e a tabela corretos ao lado.
        carga["fita"] = _fita(ctx.mesa)

        # OS LUGARES VAZIOS RECEBEM TRAVESSÃO, e sem isto a tela MENTE. O HTML
        # publicado nasce com quatro colunas — a mesa do desenho, dois
        # conectados e dois vazios. Com UM controle na mesa, a coluna do P2
        # continuava mostrando o que o mockup escreveu: "Sony · Player 2 ·
        # Starlight Blue · BT · 64%". Visível na foto de 01/09, ao lado de um
        # topo que dizia "1 controle" e de uma fita já correta.
        #
        # É a sétima aparição do mesmo defeito nesta casa — *a tela afirmando um
        # controle que não está na mesa* — e a única cura que não depende de
        # cada aba lembrar-se dela é esta: quem pinta apaga o que sobra.
        #
        # A CONTA MORA NO DESPACHANTE, e a mudança é de 02/09/2026: escrita
        # aqui, ela só tinha uma régua que procurava LITERAIS neste arquivo — e
        # a cura morria inteira sem que os literais sumissem. Ver
        # `pacotes.apagar_os_lugares_sem_dono`.
        # A MESA VAI JUNTO — QUEM-TEM-DONO-01, 03/09/2026. Sem ela a conta
        # confundiria "a aba mandou coluna" com "há controle aqui", e o passo
        # `1c` reabriria lugar vazio. O `pref` de cada conectado é o `pN` da
        # posição de jogador, que é o mesmo endereço que a página desenha.
        pacotes.apagar_os_lugares_sem_dono(carga, _com_dono(ctx))

        # O RECADO DA RECUSA VIAJA EM TODO TIQUE, e é isto que o faz sobreviver
        # à repintura: a lista CHEIA recria o aviso se a pintura de blocos tiver
        # levado o cartão embora — e se ela trocou de aba, o aviso a acompanha,
        # porque é dela e não da página. A lista VAZIA é o que apaga o que
        # venceu; sem ela a frase ficaria na tela para sempre.
        carga["recados"] = self._recados_para_a_tela()

        def contou(valor: Any, erro: Any) -> None:
            if erro is not None:
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            # O `-1` (página trocada no meio) NÃO entra na conta de tiques:
            # contá-lo como zero faria uma aba viva parecer muda na travessia.
            if n < 0:
                self.trocas[self.pagina] = self.trocas.get(self.pagina, 0) + 1
                return
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
            # O ZERO CONTA COMO TIQUE E NÃO COMO PINTURA, e é essa separação que
            # faltava: `pinturas` mede a quietude (uma aba sadia pinta uma vez e
            # para), `tiques` mede que a aba RODOU. Sem os dois, "pintou uma vez
            # e sossegou" e "a página trocou 177 vezes" saíam iguais.
            if n > 0:
                self.pinturas.setdefault(self.pagina, []).append(n)

        self.ponte.perguntar(PEDIR_A_PINTURA.replace("CARGA", _json(carga)),
                             contou)
        # A CARGA DESTE TIQUE fica guardada: é ela — e não o código-fonte do
        # pacote — que diz o que o produto DECLAROU pintar nesta aba agora. Ler
        # daqui é o que separa esta régua das anteriores, que perguntavam se o
        # nome do campo aparecia em algum lugar do arquivo .py.
        self._carga_de_agora = carga
        self.voltas += 1
        self.custos.append((time.perf_counter() - t0) * 1000)
        return True

    # -- o roteiro e o relato ---------------------------------------------
    def _agendar(self) -> None:
        if self.args.passear:
            # O PASSEIO: clica a tira aba por aba, para provar que as dez
            # pintam. Sem ele o relato só teria a primeira — e "a aba abre" não
            # é o mesmo que "a aba pinta", que é a distinção inteira desta leva.
            for i, alvo in enumerate(sorted(pacotes.PACOTES)):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: self._ir(a),
                )
            total = 1600 + len(pacotes.PACOTES) * self.args.parada
        elif self.args.segundos:
            total = int(self.args.segundos * 1000)
        else:
            # SEM PRAZO: a janela fica aberta até ELA fechar. É o padrão do
            # PRODUTO, e o contrário disso foi um defeito que ela sentiu em
            # 01/09/2026 — abriu o `interface.sh`, a janela viveu 8 segundos e
            # sumiu. O `--segundos` tinha `default=6.0`, herdado de quando este
            # arquivo era só régua de bancada.
            #
            # A REGRA QUE ISSO DEIXA: toda flag de bancada nasce DESLIGADA. Um
            # padrão de régua que vira padrão de produto é um produto que se
            # comporta como régua na mão de quem usa.
            return
        def fechar() -> bool:
            # DUAS AÇÕES, e por isso uma função com nome em vez de um `lambda`:
            # relatar e SÓ ENTÃO fechar. Invertidas, o `main_quit` levaria o laço
            # embora antes de a última linha do relato sair.
            self._relatar()
            Gtk.main_quit()
            return False

        GLib.timeout_add(total, fechar)

    # -- a prova do mockup -------------------------------------------------
    def _provar_mockup(self) -> bool:
        """Passa pelas DEZ abas e mede, em cada uma, o que é dado e o que é desenho.

        O ROTEIRO, por aba: abre → retrata o DOM VIRGEM → deixa a pintura correr
        N tiques → lê a tela de novo → compara com o que o ARQUIVO crava.

        POR QUE N TIQUES E NÃO UM: *uma régua que roda o tique uma vez mede um
        INSTANTE, não um comportamento*. Em 29/08/2026 uma leva introduziu uma
        regressão que só aparecia aos 181 segundos, com 67 testes verdes. Aqui o
        padrão são oito voltas — quatro segundos por aba — porque a mesa demora
        a chegar inteira: a cor do plástico é perguntada ao aparelho em thread e
        a primeira volta pinta "Não sei".
        """
        self._fila_de_abas = [
            p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit()]
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
        # A CARGA DA ABA ANTERIOR NÃO PODE SOBREVIVER À TRAVESSIA: a
        # `07-lancadores` não tem pacote e não produz carga nenhuma, e o que
        # ficasse aqui seria lido como "o pacote da Lançadores declara isto" —
        # os campos da aba anterior, atribuídos a uma aba que não tem dono.
        self._carga_de_agora = {}
        # O `pronto = False` É OBRIGATÓRIO, e a razão é uma armadilha do
        # `_carregou`: quando a aba nova é a MESMA que está à vista (é o caso da
        # primeira), ele volta cedo e não abaixa a bandeira. O tique seguinte
        # pintaria num documento recém-carregado, sem ponte, e contaria a volta.
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
        cravados = regua_do_mockup._campos_cravados(arquivo.read_text(encoding="utf-8"))
        self.cravados[pagina] = cravados

        # A GUARDA, E ELA É SOBRE O VIRGEM — não sobre a tela do fim. O DOM
        # ANTES DE QUALQUER PINTURA tem de dizer exatamente o que o arquivo diz:
        # é o parser de Python e o leitor de JS conferidos um contra o outro,
        # endereço a endereço e valor a valor. Se discordarem, a régua está
        # lendo uma coisa e comparando outra — e diria "PRODUTO" sobre um campo
        # que ninguém tocou. Não há como conferir isto sem abrir a página, e é
        # por isso que ela vive aqui e não no teste unitário.
        #
        # NA TELA DO FIM ESTA IGUALDADE NÃO VALE, e supor que valesse foi o
        # primeiro erro desta régua: a pintura TROCA BLOCOS INTEIROS, e a
        # `10-perfis` acabou o passeio com 55 endereços onde o arquivo tem 81.
        # Aquilo não é cegueira — é o produto trabalhando. Quem casa os dois
        # lados é o `_alinhar()`.
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

        # O SELO VIAJA JUNTO, e ele é o quinto elemento de cada linha. Vem como
        # `true`/`false` do JSON e é o único que NÃO se converte para texto: o
        # `str(False)` é `'False'`, que é verdadeiro em Python, e isso daria selo
        # a todo campo — todos os 74 indecidíveis viravam PRODUTO de graça.
        alinhados, nasceram = regua_do_mockup._alinhar(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3])) for x in vivos])
        selos = regua_do_mockup._selos_alinhados(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3]),
                        bool(x[4]) if len(x) > 4 else False) for x in vivos])
        if nasceram:
            print(f"[prova-de-mockup] {pagina}: {len(nasceram)} endereço(s) "
                  f"NASCERAM na tela (o produto trocou um bloco): "
                  f"{', '.join(f'{d}·{k}' if d else k for k, d in nasceram[:8])}")

        if self.args.sem_cravado:
            # A MORDIDA, e ela mora aqui porque é aqui que a cura mora: se o
            # valor cravado deixar de ser o do arquivo, TUDO parece pintado e a
            # régua não acusa mais nada. Uma régua que continue acusando com
            # isto ligado está acusando por outro motivo — e não é a que ela
            # pediu. Vem DEPOIS das duas guardas de propósito: elas conferem a
            # leitura, não a comparação.
            cravados = [dataclasses.replace(c, valor="\x00cura arrancada")
                        for c in cravados]
        declarados = regua_do_mockup._declarados_do_pacote(self._carga_de_agora)
        if self.args.sem_selo:
            # A OUTRA MORDIDA, e ela é do selo: sem ele, todo campo que coincide
            # com o desenho volta a ser INDECIDÍVEL. Uma execução com isto ligado
            # que devolva o MESMO número de indecidíveis está dizendo que o selo
            # não decidiu nada — e aí ele é enfeite, não instrumento.
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
            # PRONTO = PRODUTO + RÓTULO, e a soma é o ponto da categoria nova:
            # rótulo não é dívida, então uma aba com 20 campos escritos e 5
            # rótulos está 100% pronta — não 80%. Sem isto, 100% era
            # inalcançável por construção (decisão dela, 03/09/2026).
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

        # O QUE O SELO DECIDIU, e a conta é ESTREITA de propósito: só os campos
        # em que a tela continua IGUAL ao arquivo. Contar todo PRODUTO cujo
        # declarado bate com o vivo daria 222 — a maioria são campos que a
        # pintura MUDOU, e esses já eram decididos pelo valor. Errei essa conta
        # uma vez e o relato publicou 222 onde a diferença é 74.
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

        if self.cegueiras:
            print(f"\nA RÉGUA NÃO ENXERGOU {len(self.cegueiras)} coisa(s) — e isso reprova, "
                  "porque\numa régua que não sabe o que está lendo mede o que quiser:")
            for cegueira in self.cegueiras:
                print(f"   · {cegueira}")
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
        """
        # O PRIMEIRO CLIQUE ESPERAVA UM RELÓGIO, e o relógio estava errado.
        # Medido em 01/09/2026: com `--prova-clique "ver-plugins,ver-detalhes"`
        # só o SEGUNDO saía no relato; sozinho, cada um saía. Aos 600 ms o
        # `BOOTSTRAP` ainda não instalou nesta página, e o `el.click()` acha o
        # botão mas não há ouvinte para responder — o clique some, calado.
        #
        # A cura não é aumentar o número: é PERGUNTAR se a página está pronta.
        # Um prazo maior continuaria sendo uma aposta sobre a máquina de quem
        # roda, e a régua voltaria a perder o primeiro gesto na primeira máquina
        # mais lenta que esta.
        def clicar(g: str) -> bool:
            if not self.pronto:
                return True  # ainda não; o GLib chama de novo no próximo tique
            self._js(SELETOR % (g, g, g, g))
            return False

        for i, gesto in enumerate(self.args.prova_clique.split(",")):
            GLib.timeout_add(600 + i * 900, lambda g=gesto: clicar(g))
        return False

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _provar_no_aparelho(self) -> bool:
        """A PROVA BOTÃO A BOTÃO, no aparelho dela — pedido dela, 01/09/2026.

        *"no aparelho por favor valida botão a botão tá bom?"*

        E ela está certa sobre o que basta: `[gesto] → aplicado` só prova que a
        função rodou sem levantar. O que prova de verdade é o ESTADO DO DAEMON
        MUDAR — e é o que este modo mede, um gesto por vez:

            lê o estado → clica → espera → lê de novo → diz o que mudou

        Um gesto que aplica e não muda nada aparece como `SEM EFEITO`, que é
        informação e não falha: pode ser um botão que já estava no valor pedido.
        O que ele nunca faz é passar por sucesso calado.
        """
        arquivo = onde.pagina(self.pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        da_pagina = regua_do_mockup._gestos_cravados(texto)
        # O `"*"` ENTRA, e sem ele o relato acusa mentira: os quatro botões do
        # rodapé (Aplicar · Salvar · Importar · Exportar) moram no `topo.html`,
        # o esqueleto das dez, e por isso se registram em `("*", nome)` — é o
        # mesmo coringa que o `pacotes.gesto_da_pagina` consulta. Sem esta
        # metade, a régua os listaria como "ninguém os ligou" em TODAS as dez
        # abas, e a primeira execução deste bloco fez exatamente isso.
        registrados = {n for (p, n) in pacotes.GESTOS if p in (self.pagina, "*")}
        perigosos = set() if self.args.incluir_perigosos else PERIGOSOS
        alvos, pulados = regua_do_mockup._alvos_a_clicar(
            da_pagina, registrados, self.pagina, perigosos)
        # A COBERTURA É CONFERIDA ANTES DO PRIMEIRO CLIQUE, e ela é o que faz
        # esta prova deixar de mentir. Em 29/08/2026 o `--prova-gesto` da aba
        # Controles deu VERDE sobre dois botões MORTOS: ele clicava o que o
        # CÓDIGO registrava, e os dois botões novos existiam só na PÁGINA.
        # *Uma validação de interface que não cobre o botão novo é uma validação
        # que mente.*
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
        # UMA FILA SERIAL, e não timers fixos. Com `timeout_add` de intervalo
        # constante os gestos se ATROPELAM: `daemon.reload` leva 9,5 s e o
        # intervalo era 2,5 — o segundo gesto começava com o primeiro no ar, o
        # `_antes_do_gesto` (que é um só) era sobrescrito, e o relato saiu com
        # `retomar` DUAS vezes e `perfil-da-mesa` nenhuma. Medido em 01/09.
        #
        # Cada gesto agenda o próximo quando o SEU termina. O relato passa a ter
        # uma linha por gesto, na ordem, e nenhuma medição pega o efeito da
        # anterior.
        self._fila = list(alvos)
        GLib.timeout_add(400, self._proximo_da_fila)
        return False

    def _proximo_da_fila(self) -> bool:
        """O próximo gesto da prova no aparelho.

        O `False` É O CONTRATO DO GLib — "não me chame de novo" —, e ele passou a
        ser dito AQUI em 01/09/2026. Antes cada sítio de chamada montava
        `(self._proximo_da_fila(), False)[1]`: uma tupla feita para se jogar
        fora o primeiro item, que obriga quem lê a saber de cor que o método
        devolve `None`. Os cinco callbacks desta classe seguem a mesma regra.
        """
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
        # OS CONECTADOS, NA ORDEM DA MESA — e é isto que faltava. Sem alvo, sete
        # gestos da aba Conexões recusaram CORRETAMENTE em 02/09/2026 e o
        # instrumento os contou entre os dezesseis "aplicado e nada mudou".
        # O JS devolve ONDE clicou; o `_onde_clicou` guarda para o relato.
        prefs = [c["pref"] for c in self._mesa_de_agora if c.get("pref")]

        def anotou(valor: Any, erro: Any) -> None:
            self._onde_clicou[nome] = (
                f"o clique falhou: {erro}" if erro is not None else str(valor))

        self.ponte.perguntar(CLIQUE_COM_ALVO % (_json(nome), _json(prefs)), anotou)
        # A ESPERA É OBRIGATÓRIA e não é folga: o daemon escreve no aparelho e
        # só então republica o estado. Medir na hora leria o valor VELHO e diria
        # "sem efeito" sobre um botão que funcionou.
        #
        # E ELA É POR GESTO: o `TETOS` da ponte diz que `daemon.reload` leva 15 s
        # e `gamepad.emulation.set` 2 — esperar o mesmo para os dois faz o
        # instrumento medir antes de o lento terminar, e ler "sem efeito".
        from pacotes import ponte as _p

        espera = max(self.args.espera, int(_p.teto(_METODO_DO_GESTO.get(nome, "")) * 1000) + 800)
        GLib.timeout_add(espera, self._depois_do_gesto)

    def _depois_do_gesto(self) -> bool:
        # O TIPO É DITO, e não inferido do `{}`: o padrão do `getattr` faz o
        # `mypy` ler `antes` como um dicionário VAZIO e sem chaves, e aí
        # `antes.get("qualquer coisa")` vira erro de sobrecarga.
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
        # SEM ECO NÃO É SEM EFEITO, e confundir os dois é o que faria esta régua
        # acusar um botão que funciona. O `state_full` do daemon não publica
        # gatilho — o DualSense não devolve o modo em que está, é comando de ida
        # — então um `trigger.set` aceito não muda campo nenhum aqui.
        #
        # Quem declara isso é o PACOTE, em `SEM_ECO`, e a prova daqueles gestos
        # é outra: o gesto usa a porta `_detalhado`, que levanta quando o daemon
        # recusa. Chegar a "aplicado" já é o daemon ter aceitado.
        sem_eco = nome in self._sem_eco_da_pagina()
        # OS TRÊS DESFECHOS, e antes de 02/09/2026 os três saíam iguais. O que
        # o daemon publica não distingue *recusou dizendo* de *não fez nada* —
        # nos dois casos o estado fica igual. Quem sabe a diferença é o próprio
        # gesto, e agora ele deixa dito em `self.desfechos`.
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
            # RECUSAR DIZENDO É O COMPORTAMENTO CERTO, e contá-lo como falha
            # é o que fez a medição de 02/09 acusar sete botões que estavam
            # certos. `ValueError` = clique inválido; `RuntimeError` = o
            # produto recusou, e a frase vai para a tela.
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

        for arq in sorted((AQUI / "pacotes").glob("a[0-9][0-9]_*.py")):
            mod = importlib.import_module(f"pacotes.{arq.stem}")
            if getattr(mod, "PAGINA", "") == self.pagina:
                return set(getattr(mod, "SEM_ECO", ()))
        return set()

    def _ir(self, pagina: str) -> bool:
        """Abre uma aba. `False` para o GLib — ver `_proximo_da_fila`."""
        self.view.load_uri(onde.pagina(pagina, publicado=True).as_uri())
        return False

    def _relatar(self) -> bool:
        # UMA VEZ SÓ. O `_agendar` roda no `_instalado`, que dispara a cada
        # carga de página; sem esta trava o passeio agendava dez saídas e o
        # relato saía repetido — dois "foto:" no log de 01/09.
        if self.relatou:
            return False
        self.relatou = True
        if self.args.foto:
            # `fotografar()` JÁ IMPRIME o caminho — a linha que estava aqui era
            # a segunda, e foi ela que fez o log de 01/09 mostrar dois "foto:"
            # e parecer que o relato rodava duas vezes. Não rodava.
            self.tela.fotografar(self.args.foto)
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'tiques':>7s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            tiques = self.tiques.get(pagina, 0)
            print(f"{pagina:22s} {tiques:7d} {len(conta):8d} {pico:8d}")
            # A ABA MUDA É A QUE RODOU E NUNCA ESCREVEU UM VALOR. Antes esta
            # linha perguntava `pico == 0` sobre uma lista em que o zero nunca
            # entrava — era ramo morto. Agora `tiques` conta o tique e
            # `pinturas` conta só quem escreveu, e a diferença entre os dois é o
            # fato: pacote com endereço que não casa.
            if tiques and not conta:
                mudas.append(pagina)
        # AS TROCAS SAEM NO RELATO, e não ficam num contador que ninguém lê: um
        # `-1` é a página tendo trocado no meio do tique, e ver muitos deles é
        # ver o passeio andando rápido demais para a pintura acompanhar.
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
                # UM GESTO MUDO E NÃO DECLARADO é o que esta régua persegue: ou
                # ele não faz nada, ou faz algo que o daemon não conta e ninguém
                # escreveu isso. As duas coisas precisam de alguém.
                print(f"   sem efeito e sem `SEM_ECO`: {', '.join(mudos)}")
            forcados = [p["gesto"] for p in self.provas
                        if str(p.get("onde", "")).startswith("ALVO FORCADO")]
            if forcados:
                # O ALVO EMPRESTADO NÃO É O PRODUTO FUNCIONANDO: estes botões
                # não dizem em qual aparelho agem, e sem a régua emprestando um
                # eles só podem recusar. É defeito da PÁGINA, e está nomeado.
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
                  f"max {ordenado[-1]:.2f} ms")
        if mudas:
            # ZERO É ERRO, NÃO SILÊNCIO. Uma aba que foi visitada, tem pacote e
            # escreveu zero valores é endereço que não casou — e essa é a forma
            # exata do defeito que deixou a `06-navegacao` publicar sem
            # endereço nenhum.
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)
        return False


def _json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, default=str)


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
    p.add_argument("--abre", default="", help="abrir direto numa aba")
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
    args = p.parse_args()

    if args.prova_de_mockup and not args.oculta:
        # ELA TEM UMA TELA. Uma régua que passeia por dez abas piscando na
        # frente dela quebra o que ela está fazendo — e nenhum ganho de medição
        # paga isso. Aqui a bandeira se acende sozinha, e diz que se acendeu.
        print("[prova-de-mockup] ligando `--oculta`: esta régua abre dez abas e "
              "ela tem UMA tela.")
        args.oculta = True

    piloto = Piloto(args)
    if args.prova_de_mockup:
        GLib.timeout_add(900, piloto._provar_mockup)
    if args.prova_no_aparelho:
        GLib.timeout_add(2500, piloto._provar_no_aparelho)
    if args.prova_clique:
        GLib.timeout_add(2000, piloto._provar_cliques)
    if args.abre:
        GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    Gtk.main()


if __name__ == "__main__":
    main()
