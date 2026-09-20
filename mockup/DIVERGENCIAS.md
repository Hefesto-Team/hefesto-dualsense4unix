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

## 01-jogar.html
- **20/09/2026** — a **legenda** da aba diz duas coisas que o produto já não faz.
  É a `2026-09-17-POINT-AND-CLICK-01`, e as duas afirmações foram medidas:

  1. *"Os DOIS que ainda não têm quem os atenda aparecem, e dizem isso (…) os
     dois entram marcados"* — **nenhum dos dois entra marcado**. O Point And
     Click saiu da fileira em 31/08, por ordem dela (*"nos mockups tira o point
     and click e deixa só o navegação"*), e a linha que sobrou na tabela
     (`painel.CHIPS_DA_ESCADA`) saiu agora: `chips_sem_dono()` devolve `()`;
  2. *"O que ainda não existe é o PS + R3 parar nela"* — **ele para nela** desde
     13/09 (`hotkey.CICLO_DE_PONTES`, MODO-DE-CONEXAO-01), e desde esta sprint
     entra pela mesma porta do clique. A frase confundia a escada AUTOMÁTICA com
     o ciclo do GESTO, que são dois objetos de nomes parecidos.

  A terceira frase do parágrafo estava truncada no meio (*"ela leva traço no
  dica que diz o que falta"*).

  **O QUE ESPERA O OLHO DELA:** só o parágrafo da legenda mudou — nenhum chip,
  nenhum cartão, nenhuma medida. A fileira continua com os mesmos quatro
  `data-degrau`, e a regra CSS `.degrau.sem-dono` continua desenhada e sem uso,
  que é a gramática desta casa para *"botão que aparece e diz que ainda não tem
  quem o atenda"*.

  **O QUE ELA VÊ HOJE, até publicar:** a página que o produto renderiza continua
  com a legenda antiga, e o texto dela é só EXPLICAÇÃO — nenhum clique, nenhuma
  medida e nenhum rótulo dependem dele. O comportamento novo já está na tela
  dela: clicar no chip **Navegação** carrega o perfil desde o merge desta
  sprint, com legenda velha ou nova. O que a espera custa é a explicação
  descrever a fileira de 31/08 em vez da de hoje.

  **E UMA PARTE DISTO É DECISÃO DELA, na §7.1 da sprint:** o **nome** do chip.
  Ela usou as duas palavras na mesma frase — *"o modo point and click é o modo
  navegação"* — e a tela tem UM chip. Ele se chama **Navegação** hoje, e o texto
  novo diz isso; se ela escolher «Point And Click» ou «Navegação (Point and
  click)», este parágrafo é reescrito junto com o `rotulo`. Publicar antes da
  palavra dela custaria a mesma edição duas vezes.

- **20/09/2026** — o chip **Steam Input** ganhou **endereço próprio de estado**.
  É a `2026-09-17-STEAM-INPUT-01`, e a mudança **não move um pixel**: o
  `data-campo` do chip passou de `modo-aceso` para `steam-input-aceso`, com o
  mesmo `data-hef-alvo="classe"` e a mesma classe `on`. Os três atributos estão
  em `scripts/check_o_desenho_aprovado.INVISIVEIS`.

  **POR QUE ELE PRECISOU SAIR DO CAMPO COMPARTILHADO:** o Steam Input não é
  exclusivo dos outros chips. O degrau 4 da `ponte_escada.ESCADA` é
  `Ponte(gamepad, dualsense, steam_input=True)` e tem `recria_vpad=False` — ele
  senta **em cima** do caminho DualSense em vez de substituí-lo. «Sony
  DualSense» e «Steam Input» são verdade ao mesmo tempo, e num campo só o piloto
  escreve o mesmo valor em todos: acender um **apagaria** o outro.

  **O QUE ELA VÊ HOJE, até publicar:** o **clique já funciona** — o
  `data-gesto="modo-steam"` está na página publicada desde 31/08, e o gesto
  nasceu nesta leva. Clicar liga o Steam Input **daquele jogo** e o recado
  aparece. O que espera por ela é só o **acender**: na página publicada o chip
  continua ouvindo o `modo-aceso`, e o produto não manda o valor `steam` por
  esse endereço — então ele fica apagado mesmo com a ponte de pé. Nada pisca
  errado, nada some, nenhum clique morre calado.

  **Fecha com** `scripts/check_o_desenho_aprovado.py --publicar 01`, junto com a
  legenda do item acima. Enquanto as duas coisas esperarem o mesmo OK, publicar
  uma custaria a mesma conferência duas vezes.

## 02-controles.html
- **20/09/2026** — o **trilho do ganho de entrada** do microfone entrou na linha
  do rótulo, à direita de «Microfone · ATIVO». É a
  `2026-09-20-O-GANHO-DO-MIC-TEM-DONO-01`, e a decisão dela mudou duas vezes no
  mesmo dia: às 13h03 *"Não ligar mas escreve a Sprint e coloca uma imagem de
  como ficaria"* e, cerca de uma hora depois, olhando a imagem, *"deixa o slicer
  2 dele na telka"*. <!-- noqa-acento: citação literal dela -->

  **O QUE ELE MOSTRA, e não é o volume de baixo:** o `Headset Capture Volume` da
  placa do DualSense — 0 a +48 dB em 102 degraus — que vivia no topo sem
  ninguém ter escolhido. Ganho é o quanto o APARELHO amplifica o que entra;
  volume é o quanto disso o produto ENTREGA ao PC. A unidade e essa diferença
  estão no `?` da moldura.

  **O QUE ISSO CUSTOU DE ALTURA: ZERO.** Medido no navegador a 1120, 1180 e
  1440px, com o cartão em **327,63px** antes e depois (teto 328). Os outros três
  arranjos foram medidos e recusados: linha nova embaixo do volume **+22,00px**,
  na fileira dos modos +2,00px e encolhendo Virtual/Nativo, e dividindo o trilho
  do volume derruba-o de 182,25 para 48,38px a 1120. O estado CINZA — o do rádio,
  com o `?` da razão aceso — também mede 327,63px nas três larguras.

  **O QUE ESPERA O OLHO DELA:** só a moldura do Microfone mudou. O deslizante de
  volume continua com a mesma largura, o 🎙 e os botões Virtual/Nativo não
  encolheram um pixel, e nenhuma outra coluna do cartão foi tocada.

  **O QUE ELA VÊ HOJE, até publicar:** a página que o produto renderiza não tem
  o trilho, e o pacote **não emite** os três campos dele — a guarda
  `a02_controles._a_pagina_tem_o_ganho` pergunta à página PUBLICADA antes de
  escrever, pela mesma razão do «Nativo» e do «Ouvir junto»: emitir para um
  endereço que a página não tem põe as chaves em `orfaos`. No dia em que ela
  publicar, os três ligam sem ninguém tocar em código.

  **O QUE JÁ VALE SEM PUBLICAR:** o `assets/ucm/DualSense-HiFi.conf` passou a
  declarar `CaptureVolume`/`CaptureMixerElem` sobre o `Headset Capture Volume`.
  Isso é do SISTEMA, não da tela, e só chega à máquina dela pelo `install.sh` —
  que esta sprint não roda.
