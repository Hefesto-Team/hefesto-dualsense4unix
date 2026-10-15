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

## 03-gatilhos.html
- **15/10/2026** — o desenho do todo (acionamento e imersão por gatilho, um chip por controle, «Criar efeitos novos»): espera a aprovação dela para o `--publicar 03`. Até publicar, o pacote serve à página de hoje (Efeito pronto, ajustes, curvas, Guardar e Em todos) e, quando a página do todo chega, preenche só o acionamento, a imersão e o estilo do perfil; as quatro colunas e os dois modos são os mesmos nas duas.

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
