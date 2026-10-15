# As abas em trabalho na bancada

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ela ainda não deu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** A bancada é o desenho de hoje; o produto
só recebe quando ela aprova a aba **inteira**, que é a escolha dela de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto nela.
```

Quando ela aprovar a aba, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## mapa-do-radio.html
- **08/10/2026** — a caixa e o fone custam 366 fatias (61 pacotes x 6: o 2-DH5 ocupa 5 fatias, mais a
  resposta), e não 244; o número do desenho é demonstrativo e continua estimado (sprint
  O-232-SAI-E-A-CONTA-DA-PONTE-ENTRA-01). Até publicar, a página do produto continua a de antes, com os 244 no dado e no comentário
  da caixa e do fone. A linha da caixa e do fone continua em 61 Hz, mas o ar que sobra no
  adaptador deles cai de 361 para 117 fatias (ele varre: o teto é 849): um controle arrastado
  para lá mostra 0 Hz em vez de 53 Hz. O «Equilibrar» da cena continua apontando a Entrada 4.
- **09/10/2026** — o número de pontes de cada Entrada passa de «N/2» a «N/M», com M = quantas pontes ainda deixam todo
  controle dela em 125 Hz ou mais: `piso((C_eff - 2 x 125 x controles) / 187,5)`, nunca acima de 2 (sprint
  A-PONTE-SE-OTIMIZA-ATE-QUATRO-NO-ULTRA-NUM-ADAPTADOR-01). A sobra («Cabe mais N com som») segue o mesmo M. Na cena de
  sempre as três Entradas continuam em 2; uma Entrada que varre (teto 849) com dois controles cai para 1. A página do
  produto continua em «N/2» até publicar, e o limite do produto só segue a capacidade quando a bancada ligar o
  `radio_da_mesa.N_MAX_PELA_CAPACIDADE`.

## 08-conexoes.html
- **13/10/2026** — o aparelho de baixa energia que não diz o tipo ganha a categoria «Acessório» (glifo, palavra,
  legenda e cor próprios), a faixa dele são os 40 canais de baixa energia «não medidos» com os três de anúncio
  marcados, e o ponto diz o sinal em dBm sem julgar (sprint O-ACESSORIO-SEM-TIPO-GANHA-CATEGORIA-E-SINAL-NA-CONEXOES-01,
  a opção 1 escolhida em 09/10/2026). Na cena do desenho o acessório ocupa a linha do relógio; o relógio continua na
  legenda. As cores de cada tipo passam a tokens da raiz (`--c-<tipo>`, `--sala-<tipo>`), que um tema de cores
  alcança (sprint O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01), com os mesmos valores de antes. Até publicar, o
  produto roda o pacote novo sobre a página de antes, que não define `--sala-<tipo>` nem `--c-acessorio` nem a
  textura do «não medido»: os ícones da sala ficam sem a cor do tipo, e a linha do acessório mostra o nome e o
  sinal, sem o glifo e com a faixa sem cor. A 08 se publica no mesmo fecho que leva o código.

## 01-jogar.html
- **15/10/2026** — a fileira do Ligado troca «Navegação» por «Point and click», e a do Desligado ganha «Navegação»
  como terceiro chip (cores da barra de luz: Nativo branco, Steam Input ciano, Navegação laranja); as ajudas «?» e
  os `title` viram `data-dica` curtas, de uma frase; o «Modo Freestyle» e o novo «Reconectar» são a mesma pílula de
  34 px no canto do quadro, e o «Reconectar controles» sai da faixa final (sprint A-ABA-JOGAR-DO-TODO-01).
  Até publicar, o produto roda o pacote novo sobre a página de antes, que tem quatro chips em `modo-aceso`, o
  «Reconectar controles» na faixa e a ajuda com «?»; a lembrança do lado da Navegação já vale na interface.

## 02-controles.html
- **15/10/2026** — o touchpad liga e desliga em cada controle: o interruptor «Ligado | Desligado» do alto do quadro
  troca o cartão, a superfície esmaece desligada e acende o terço onde o dedo está; «Cursor», «Botões» e a frase do
  número de toques saem. O alto-falante passa de quatro botões a três, uma linha cada («Canais sonoros nativos -
  Padrão», «apenas no DualSense», «apenas no PC»); a linha do Ganho sai do microfone; a Mira virtual vai para baixo de
  cada analógico (clicar no aceso desliga); o «Calibrar sensores de movimento» vira «Calibrar giroscópio», ao lado do
  Modo automático; nenhum «?» na aba, cada explicação é uma `data-dica` curta (sprint A-ABA-CONTROLES-DO-TODO-01).
  Até publicar, o produto roda o pacote novo sobre a página de antes, que tem os quatro botões do som, o Ganho, o chip
  da mira no cabeçalho e o «Cursor | Botões»: o pacote só emite o interruptor, as terças e o botão da mira por
  analógico quando a página os tem, e o perfil «junto» acende o botão «apenas no DualSense» quando o «junto» não existe.
  O passo `junto` do roteiro do piloto sai no mesmo commit do `--publicar`.

## calibrar-sensores.html
- **15/10/2026** — a janela passa a se chamar «Calibrar giroscópio» (`<title>` e título), sem «?» (a dica do título e a
  frase de cada um dos três passos viram `data-dica`, sem `title`); o selo do liga do analógico virtual diz
  «Giroscópio como analógico»; todo alvo clicável mede 24 px ou mais; a coluna dos nomes das seis leituras cabe
  «Acelerômetro» e as barras começam juntas (sprint A-JANELA-CALIBRAR-GIROSCOPIO-DO-TODO-01). O selo muda de texto
  também na linha da aba Conexões, que usa o mesmo rótulo. Até publicar, o produto abre a Calibrar publicada, com o
  nome velho: o pacote só escreve o que a página tem.

## 03-gatilhos.html
- **15/10/2026** — só a folha do Nativo: a «Navegação» da aba Jogar passou a ser um dos vivos do Nativo, e a folha
  comum (`monta.CSS_DO_NATIVO`) entra nas cinco abas por controle. Nada muda na tela desta aba (ela não tem o chip).
  Até publicar, o produto roda a página de antes, com a folha velha do Nativo, que aqui não tem o que esconder;
  sai com o próximo `--publicar 03`.

## 04-iluminacao.html
- **15/10/2026** — só a folha do Nativo, como na 03: o seletor da «Navegação» entra na lista dos vivos e nada muda na
  tela desta aba. Até publicar, o produto roda a página de antes, sem perda; sai com o próximo
  `--publicar 04`.

## 05-vibracao.html
- **15/10/2026** — só a folha do Nativo, como na 03: o seletor da «Navegação» entra na lista dos vivos e nada muda na
  tela desta aba. Até publicar, o produto roda a página de antes, sem perda; sai com o próximo
  `--publicar 05`.
