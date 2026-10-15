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

## mapa-do-controle.html
- **15/10/2026** — o mapa deixa de ser a página dos sensores, das luzes e do áudio e vira a tela de configurar os 23
  botões (rodadas 3 e 4 do desenho do todo; sprint A-ABA-MAPA-DO-CONTROLE-DO-TODO-01): perfil em três grupos
  (Navegação, Moldes, Meus perfis), quatro moldes (Point and click, Visual novel, Mouse, Mouse e teclado), cor do tipo,
  seletor por botão com três abas (Controle, Mouse, Teclado) e a captura de tecla. O pacote novo roda sobre a página
  de antes até publicar, que não tem a linha de perfil nem as linhas dos botões: o `--publicar` leva a página no mesmo
  fecho que leva o código.


## 06-navegacao.html
- **15/10/2026** — a Navegação vira a aba dos 23 botões do desenho do todo (sprint A-ABA-NAVEGACAO-DO-TODO-01, e as
  três que ela absorve): 22 linhas de botão e o Toque desabilitado (a sprint dizia 22, o desenho tem 23 com o Toque),
  a fila «Trocar os botões», «Point and click» e «Acessibilidade» com o «Voltar ao padrão», os selects Quem navega,
  Tipo, Na Steam, Perfil de point and click e Função do teclado (quatro palavras, com o «Sempre»), duas barras
  (cursor e rolagem) e seis ações dos gestos do PS. O pacote novo roda sobre a página de antes até publicar: o
  `--publicar` leva a página no mesmo fecho que leva o código.
- **Fica diferente do desenho, de propósito:** a Acessibilidade renderiza inteira mas todo controle sem dono sai
  `disabled`/`inert`, e o Guardar e o Voltar ao padrão dela saem apagados com a dica «Chega com a próxima versão»
  (os donos futuros são as sprints do botão que alterna, do tremor, dos analógicos e do cursor); os chips «Navega com»
  só pintam; os rótulos do Tipo encurtam («Interna», «Mouse e teclado»); o ritmo da repetição diz «Hz» e o rótulo do
  glifo começa em maiúscula (a régua de primeira maiúscula reprovava «por s» e «cima»); a dica do Point and click
  espera o mapa ler a escolha e as âncoras `#trocar`, `#point-and-click` e `#acessibilidade`; o padrão do mockup da
  Função do teclado é «Só fora do jogo» (o «Sempre» é escolha dela, não o padrão); o desenho trocou o «−/+» e as
  duas colunas da sprint por barras e linhas.
