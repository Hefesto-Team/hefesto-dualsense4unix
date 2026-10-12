# As sprints de todas as abas: a forma que cada montador usou

Cada montador acrescenta a sua seção; ninguém apaga a de outro.

## Montador das abas 01 Jogar e 02 Controles (12/10/2026)

O trecho exato que pus nas minhas abas (menu e alvos) está em
`~/.local/state/hefesto-casa/leva-volta/todo/trechos-de-todas-as-abas.html`. Em cada aba, o `n` do
`data-todo` é o da própria aba.

- **T6, `O-BOTAO-DIREITO-ABRE-O-MENU-DO-HEFESTO-EM-TODA-ABA-01`.** Alinhado à forma do montador das 03-05 (a
  seção abaixo): opção A do BRIEF-T6, `recomendada-a-escolher`; `div#todo-menu-direito` em `position:fixed`,
  **aberto por padrão** num vazio da aba (01: embaixo do quadro «O controle é visto como», à direita; 02: sobre as
  linhas vazias do P3 e do P4, à direita), com o mesmo visual (fundo `--elevated`, borda `--border-forte`, raio 8,
  13px, item de 28px com padding `0 14px`, separador `--border-sutil` entre «Copiar» e «Atualizar» e entre
  «Reiniciar» e «Fechar», «Copiar» em `--texto-mudo` com `aria-disabled`). O «Desligar» vira «Ligar» quando o
  Status está Desligado; o `contextmenu` reposiciona, o clique fora e o Esc fecham.
- **T7, `CADA-FEATURE-TEM-UM-DONO-SO-NA-INTERFACE-01`.** Só sai da tela o que a tabela do BRIEF-T7 manda sair do
  lado que não é dono. Nas abas 01 e 02 nada sai: a 01 só ativa o point and click (a T2 troca o chip), a 02 é a
  dona do liga e do lado do analógico virtual (quem perde o liga é a Calibrar), e a máscara já aparece na 02 só
  como selo com dica. Vai em `por_baixo` nas duas.
- **Maiúscula, `SO-A-PRIMEIRA-LETRA-E-MAIUSCULA-EM-TODA-ABA-01`.** Já está na 1-11 (costurada `b3222fa9f`):
  nada a refazer. O texto novo que escrevi segue a regra. Ficam como estão os nomes próprios («Sony DualSense»,
  «Steam Input», «Nintendo Pro», «Cosmic Red») e o selo em caixa alta «ATIVO»/«DESLIGADO» (ordem dela de 21/09,
  citada na `TESTAR-O-MICROFONE-01`).
- **Tema, `O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01`** (em voo na `voo/lancadores-fds`). Sem tema de
  modificação ligado nada muda na tela; nas abas 01 e 02 vai em `por_baixo`. Os tokens `--c-<tipo>` são da 08.
- **Alvos, `OS-ALVOS-E-A-LETRA-CRESCEM-E-A-INTERFACE-GANHA-TAMANHO-01`.** Alinhado às 03-05: a opção 1 da sprint
  (alvo de 24 px, a letra fica), `recomendada-a-escolher` (a sprint não recomenda; é a menor mudança, e o item B0.T2
  da bancada segue sem resposta). Forma: `<style id="todo-alvos">` no fim do `head`; o `?` passa a 24x24 e todo
  `[data-gesto]` ganha `min-height:24px`. O «Tamanho da interface» é da 09.
- **Comportamento sem desenho** (`A-INTERFACE-INTEIRA-SE-ALCANCA-PELO-CONTROLE-E-PELO-TECLADO-01`,
  `O-NUMERO-DA-BARRA-NAO-CONGELA-NO-VALOR-VELHO-01`, `FECHAR-A-JANELA-DEVOLVE-O-QUE-AS-ABAS-SEGURAVAM-01`,
  `A-ALTURA-E-A-LARGURA-DA-JANELA-NAO-PULSAM-01`, `A-JANELA-REGISTRA-O-PROPRIO-TAMANHO-E-O-MOTIVO-DE-FECHAR-01`):
  em `por_baixo`, sem mudar o desenho.
- **Já na 1-11, não reaplicadas:** `O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01`, `A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01`,
  `O-CARTAO-ABERTO-DIZ-O-NUMERO-DO-JOGADOR-01`, `O-CIRCULO-DO-ANALOGICO-MOSTRA-O-QUE-O-JOGO-VE-01`,
  `A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01`, `O-ICONE-DO-DOCK-E-O-DO-HEFESTO-01`,
  `A-LINHA-DO-SALVAR-DIZ-O-GESTO-E-O-QUE-MUDOU-01`, `A-LINHA-DO-EXTERNO-VOLTA-AOS-30-PX-E-A-COR-FORA-DA-LISTA-SE-ESCOLHE-01`.
- **Medida:** sem rolagem vertical em 1212x809 (a janela que a página declara: `--piso-da-vista` 777 px mais o
  recuo de 16 px dos dois lados), conferida também em 1212x740 e 1918x840.
# As formas que valem em todas as abas (mockups do todo)

## Abas 03 Gatilhos, 04 Iluminação e 05 Vibração (montadas em 12/10/2026)

Base: o publicado da `integra/1-11` (`29d620816`), medido com a `FOLHA_DA_CASA` injetada (a `.nota` e o
`.hef-sem-item` escondidos, como no produto), em 1212x809, sem rolagem vertical.

### T6, o menu do botão direito (O-BOTAO-DIREITO-ABRE-O-MENU-DO-HEFESTO-EM-TODA-ABA-01)

- Origem: `recomendada-a-escolher` (a opção A do BRIEF-T6, o menu do sistema no tema do COSMIC; o «Desligar» é o
  interruptor da aba Jogar, a leitura recomendada da pergunta 1).
- Forma no mockup: um `<div id="todo-menu-direito" data-todo="N" role="menu">` em `position:fixed`, **aberto por
  padrão**, como se ela tivesse clicado com o direito num vazio da aba, sem cobrir nada que a cena mostra (03: o
  vazio embaixo do quadro, em x=724 y=560; 04 e 05: a coluna do P4 desconectado, em x=968, abaixo da linha
  Modelo). O `contextmenu` da página o reposiciona no ponteiro; o clique esquerdo fora ou o Esc fecham. O CSS vai
  num `<style id="todo-menu-css" data-todo="N">` e o roteiro num `<script data-todo="N">`, os dois no fim.
- Visual: fundo `var(--elevated)`, borda 1px `var(--border-forte)`, raio 8px, padding 4px, sombra
  `0 6px 18px rgba(0,0,0,.45)`, Space Grotesk 13px, item com 28px de altura e padding `0 14px`, largura mínima
  168px, `:hover` com `var(--sel-bg)`; um separador de 1px `var(--border-sutil)` entre «Copiar» e «Atualizar» e
  entre «Reiniciar» e «Fechar».
- Itens, nesta ordem: «Copiar» (cor `var(--texto-mudo)`, `aria-disabled="true"`, porque não há seleção),
  «Atualizar», «Desligar», «Reiniciar», «Fechar». Só a primeira letra maiúscula.

### T7, um dono por feature (CADA-FEATURE-TEM-UM-DONO-SO)

- Nenhum caso da T7 cai nas 03, 04 e 05. A forma que usei onde o caso apareceu (a seção «Meus toques» da 05 e a
  janela Acessórios): **a aba é a dona e grava; a outra tela só lê**, sem controle duplicado.

### A maiúscula (SO-A-PRIMEIRA-LETRA-E-MAIUSCULA-EM-TODA-ABA-01 e TODO-TEXTO-QUE-ABRE-UMA-LINHA…)

- Já está no publicado da 1-11 (`b3222fa9f`). Todo rótulo novo nasce com só a primeira letra maiúscula, e o texto
  explicativo vai para o `?` (`title`), nunca para a tela.

### O tema de cores (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01)

- Nada visível no tema padrão. Toda peça nova usa só os tokens do `:root` da página (`--elevated`, `--panel`,
  `--border-forte`, `--fg`, `--texto-suave`, `--texto-mudo`, `--cyan`, `--green`, `--sel-bg`…), nenhuma cor
  literal, para o tema do usuário alcançar as peças novas pela mesma folha.

### Os alvos de 24 px (OS-ALVOS-E-A-LETRA-CRESCEM-E-A-INTERFACE-GANHA-TAMANHO-01)

- Origem: `recomendada-a-escolher`. A sprint ainda não tem desenho nem recomendação; apliquei a opção 1 dela
  (alvos de 24 px, a mesma letra), a menor mudança que cumpre o WCAG 2.5.8. A letra mínima de 12 px e o «Tamanho da
  interface» do Sistema ficam para a escolha dela.
- Forma: um bloco só `<style data-todo="N" id="todo-alvos">` no fim do `<head>`, sem mexer nas regras da página:
  `.ajuda` (o `?`) passa de 17x17 a 24x24 (a letra fica); os botões do par «Modo automático | Modo personalizado»
  ganham `min-height:24px`; os trilhos (`input[type=range]`) ganham 24 px de área de toque com o trilho desenhado
  igual (o fundo só na faixa do meio, `background-clip:content-box`). Cada elemento tocado leva o mesmo `data-todo`.
- Na 04, as onze casas de cor `.tom` passam de 16x26 a 24x24 e, para caber na coluna, quebram em duas fileiras
  (6 + 5, `max-width:174px`, a linha do dono embaixo de cada casa); a linha Cor sobe de 46 para 89 px e o quadro
  continua sem rolagem (termina em y=721, o rodapé em 745). É desenho nosso, a validar com a escolha da sprint.

### Por baixo, em todas (o desenho não muda)

- A-INTERFACE-INTEIRA-SE-ALCANCA-PELO-CONTROLE-E-PELO-TECLADO-01 (só atributos e foco; a própria sprint para se a
  foto mudar), A-ALTURA-E-A-LARGURA-DA-JANELA-NAO-PULSAM-01, A-JANELA-REGISTRA-O-PROPRIO-TAMANHO…,
  O-NUMERO-DA-BARRA-NAO-CONGELA-NO-VALOR-VELHO-01, FECHAR-A-JANELA-DEVOLVE-O-QUE-AS-ABAS-SEGURAVAM-01.

### A chave Ligado/Desligado e a seção nova (05, «Meus toques»)

- Seção nova do perfil do jogo = um `.quadro` a mais no `.miolo`, depois do quadro da aba, com `data-todo` e
  `flex:0 0 auto`; o título no `.quadro-titulo` e as opções na mesma linha do topo quando cabem.
- Opção de escolha única: botões de 28 px, `--app-bg` com borda `--linha`; o escolhido com borda `--purple`,
  fundo `--sel-bg` e peso 600 (o mesmo par da `.seg`).
- Chave: botão de 28 px com um ponto de 7 px em `currentColor` e a palavra «Ligado» (borda e texto `--green`) ou
  «Desligado» (`--texto-mudo`), com `aria-pressed`.
- A frase de cada opção vai para o `title`; o texto da seção, para o `?` do título.

## Aba 08 Conexões, Mapa das conexões e Mapa do rádio (montadas em 12/10/2026)

Base: o publicado da `integra/1-11`. Na 08 entra antes o patch do mockup da `voo/lancadores-fds` (o acessório
e o tema). O mapa do rádio parte do mockup da 1-11, que já tem a costura da ponte à espera do `--publicar`.
Medido em 1212x809 com a folha da casa: as três sem rolagem vertical.

- **T6, o menu.** O trecho comum de `trechos-de-todas-as-abas.html`, sem mudança, aberto por padrão. Na 08 ele
  fica sobre o vazio do P4 (`left:968px;top:330px`); no Mapa das conexões, sobre as entradas vazias do hub
  (`left:700px;top:586px`).
  - O Mapa das conexões usa outra família de tokens (`--color-*`). O trecho lê os tokens dele por uma linha a
    mais no mesmo `<style>`, sem cor nova: `.todo-menu{--elevated:var(--color-paper-3);--border-forte:var(--color-rule);…}`.
  - O mapa do rádio não ganha menu: ele é o desenho que a 08 lê, não uma página da janela.
- **Alvos de 24 px.** Na 08 entra o trecho comum, e os nove `class="ajuda"` levam o `data-todo`; a 08 fica sem
  rolagem.
  - No Mapa das conexões, `.ajuda` é um parágrafo de texto, então a regra de 24x24 o quebraria. Lá o
    `#todo-alvos` só põe `min-height:24px` em `.ap-btn` (o nome do aparelho, que tinha 20 px) e `.plug` (23 px).
- **T7.** Nenhum caso da tabela nestas páginas. A linha «Analógico virtual» dos cartões da 08 só lê; o dono é a
  aba 02.
- **Maiúscula.** Já costurada na 1-11. Corrigi só o título do mapa, que passa a «Mapa das conexões», igual ao botão
  da 08.
  - Ficam como estão os nomes de entrada e de adaptador («Entrada 4», «Meio», «Direita»), as cores da Sony e
    a caixa alta decorativa por CSS dos nomes das faces.
- **Tema.** A 08 recebe da fds os `--c-<tipo>` e `--sala-<tipo>` no `:root`. As peças novas do mapa usam só os
  tokens dele (`--color-lacuna` para «Ficou mais lento» e «Não apareceu», `--color-ok` para «Entrou» e
  «Voltou»).
- **Seção ou aba nova numa página com abas no topo** (o «Registro» do mapa):
  - um botão `.modo` a mais, com a grade passando a `repeat(4, 8.5rem)`;
  - a seção nasce com `hidden`, e o `pintar()` esconde `.palco`, `.painel` e `.legenda` enquanto ela está à
    vista;
  - a lista rola dentro do quadro, nunca a página.

## Abas 09 Sistema, 10 Perfis, Calibrar sensores e Mapa do controle (montadas em 12/10/2026)

Base: o publicado da `integra/1-11` (topo `29d620816`). Medido em 1212x809 com a folha da casa: as quatro sem
rolagem vertical (também em 1918x840; a 09 também em 1212x700, com o registro rolando por dentro).

- **T6, o menu.** O trecho comum, sem mudança, aberto por padrão: na 09 sobre o vazio do registro
  (`left:760px;top:560px`); na Calibrar sobre a coluna vazia do P3 (`left:640px;top:520px`); no Mapa acima do
  desenho (`left:50px;top:190px`).
  - A 10 não tem vazio: o menu fica sobre a coluna de datas da lista (`left:448px;top:452px`), cobrindo só
    linhas de exemplo.
  - O Mapa não tem `--sel-bg`: o trecho lê o fallback que ele já traz, sem cor nova.
- **Alvos de 24 px.** O trecho comum nas quatro; `data-todo` nos `.ajuda` (nove na 09, quatro na 10, três na
  Calibrar, nenhum no Mapa). O «Tamanho da interface» (100/125/150 %) mora na 09, na linha do título
  «Configurações avançadas» (desenho nosso, a validar).
- **T7.** A Calibrar perde o liga e o Esquerdo/Direito do analógico virtual; fica um selo de leitura com a dica
  «Liga e escolhe o lado na aba Controles.». No Mapa, o «Grava em» só lê o point and click que a 06 escolheu
  (Mouse/Teclado é da Navegação).
- **Maiúscula.** «Point and click» no select de estilo da 10; o resto já veio costurado na 1-11.
- **Por baixo, sem tela.** As sprints de comportamento da 09 (status fora do fio, Parar cala o teste, janela que
  não pulsa) e da 10 (o editor só grava no perfil que mostra, o Ativar, o Salvar) estão em `por_baixo` dos JSON.
- **Conflitos.** O Eventos apagado com «Chega com as extensões» confessa dívida; fica a recomendada do BRIEF-T4,
  a decisão é dela. A «opção A escolhida em 09/10» das marcas só aparece nos briefs.

## Abas 06 Navegação e 07 Lançadores (montadas em 12/10/2026)

Base da 06: o publicado da `integra/1-11`, com as duas janelas do desenho A da acessibilidade transplantadas
(`leva-extensoes/acessibilidade/desenho/opcao-a.html`). Base da 07: o desenho B aprovado
(`leva-extensoes/jogo/desenho/kyty-config.html`, cujo head contém tudo o que o head da 1-11 tem), com a janela
dos acessórios do `intiface-config.html`. Medido em 1212x809 com a folha da casa: as duas abas e todas as
janelas (06: point-and-click, acessibilidade, definições, atalhos, trocar botões; 07: kyty, acessórios,
impedimentos, novo lançador) sem rolagem vertical.

- **T6, o menu.** O trecho comum, sem mudança, aberto por padrão: na 06 sobre os cartões vazios do P3/P4
  (`left:352px;top:250px`), na 07 sobre o vazio debaixo das modificações (`left:300px;top:636px`). Uma linha a
  mais esconde o menu enquanto uma janela está aberta: `.tela-nova:target ~ .todo-menu{display:none}`.
- **Alvos de 24 px.** O trecho comum, com `data-todo` em todo `class="ajuda"` (27 na 06, 55 na 07). Na 06 o
  `[data-gesto]{min-height:24px}` engordava o trilho das velocidades. A cura é uma regra a mais, que dá o alvo
  de 24 px sem mudar o desenho:
  `.campo-num .trilho[data-gesto]{height:24px;padding:9.5px 0;box-sizing:border-box;background-clip:content-box}`.
- **T3 e T7 (Navegação), opção A recomendada.**
  - Um dono por feature: a Velocidade e a Rolagem ficam na aba. O −/+ sai da janela do estilo, apesar de o
    desenho A o ter.
  - O liga/desliga sai, porque quem ativa é a aba 01.
  - O «Status» vira «Perfil de point and click» (Mouse | Teclado + «Configurar», que leva a
    `mapa-do-controle.html#captura`).
  - «Teclas do teclado» vira «Atalhos». O texto longo e o «Não dispara» viram `title`.
- **Janelas novas.** Seguem o padrão `section.tela-nova` aberto por `:target`, com `role="dialog"`,
  `aria-modal` e o título em `aria-labelledby`. O rodapé é Cancelar | Voltar ao padrão | Guardar, e o Esc fecha.
  As janelas da 06 têm 980 px de largura, com cartões em grade de duas colunas.
- **Lista que pode crescer** (as modificações na 07): `max-height` e `overflow:auto` na própria lista, nunca na
  janela. A prova é uma cópia com seis modificações: só a lista rola (375/186), e a página não.
- **Maiúscula.** A 1-11 já tem a regra. Os textos novos seguem só a primeira letra («Perfil de point and
  click», «Instalar de um endereço»). Ficam como estão os nomes próprios (Steam, Kyty, Intiface) e os botões
  (L1, R2).
- **Tema.** As peças novas usam só os tokens da página. O laranja de impedimento é `--orange`, igual ao
  `.selo.alerta`.

## Conferência: a forma única

- O menu do botão direito é um só em todas as páginas: o bloco `menu-do-botao-direito` da 01. Ele some quando uma janela está aberta (`.tela-nova:target ~ .todo-menu`).
- Alvos: `[data-gesto]{min-height:24px}` em toda página.
- Só a primeira letra maiúscula conta como desenho escolhido (regra dela de 05/10): «modo nativo», «point and click».
- Um dono por feature (BRIEF-T7): a 05 grava os meus toques e a janela Acessórios da 07 só lê (mudança 10 da 07).
- O detalhe, aba por aba, está no [CONFERENCIA.md](CONFERENCIA.md).
