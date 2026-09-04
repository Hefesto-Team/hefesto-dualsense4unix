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

## 08-conexoes.html
- **04/09/2026** — S-09 (D-16: a linha de veredito no topo do Check-up, na cor
  do pior achado), a tabela de adaptadores Bluetooth com endereço, a coluna
  "Onde" dos rádios vizinhos com o aviso de vizinhança, a dica viva do botão
  "A luz não acende" (com o aviso da mesa suja e a razão do nascimento) e o
  escopo do botão físico do microfone virando LEITURA (D-12).

  **O que o produto faz enquanto espera o OK dela:** a página publicada não tem
  os oito endereços novos (`veredito` e os quatro estados dele,
  `adaptadores-tabela`, `vizinho-onde`, `vizinho-onde-dica`, `luz-dica`,
  `mic-dica`, `mic-escopo`), e o `achar()` do piloto não os encontra — o pacote
  emite e a escrita cai no vazio, calada e sem custo. A tela DELA continua
  exatamente como está hoje: sem linha de veredito, com a tabela de adaptadores
  do mockup ("Sala / TP-Link UB500 / Entrada 3" e "Sem nome / Intel AX211 /
  Interno", sobre uma mesa que tem TRÊS adaptadores), sem a coluna "Onde" nos
  vizinhos, com o `title` do botão da luz congelado no transporte da cena e com
  o `<select>` de "Só este controle / O computador inteiro", que a página
  publicada ainda desenha e cujo gesto continua declarado em `SEM_GESTO` — o
  clique nele segue imprimindo a recusa até a publicação, de propósito. O que
  JÁ chega à tela dela sem publicar nada é a régua de Desempenho: ela é um bloco
  trocado inteiro (`regua-do-radio`), então as três pistas com o nome de cada
  adaptador aparecem no próximo tique.

## 01-jogar.html
- **04/09/2026** — S-04 (D-09 e D-10: a coluna Atenção acende até três, o mais
  grave em cima, com `+N`; a linha "Ponte com o jogo" entra nela), S-12 (D-07: a
  frase da mesa vazia e o `+N` do quinto controle) e a queixa 1 dela sobre a
  máscara (a ressalva de "vale quando o gamepad voltar" e o chip que o produto
  não sabe montar, cinza com a razão na dica).
- **O que ela vê hoje, enquanto o produto não recebe:** os três chips de máscara
  de cada cartão parecem iguais, e o **Nintendo Pro** — que o Hefesto não sabe
  montar — só diz isso DEPOIS do clique. Com a mesa vazia, os quatro lugares
  ficam apagados **sem uma palavra**; com mais de quatro controles, o cabeçalho
  conta todos e a fileira mostra quatro, calada. E fora do modo jogo a escolha de
  máscara é gravada sem que a tela diga que ela só vale quando o gamepad voltar.
  Nada disso quebra o que já funciona: são linhas que hoje não existem.

## 02-controles.html
- **04/09/2026** — S-06 (D-08: *"Deslizante nos dois"* — o volume do microfone e
  o do alto-falante deixam de ser pintura), a decisão [09] resolvida (o `♪`
  passa a ACENDER por leitura, e o `alto-estado` invisível sai do desenho) e a
  queixa 8 dela (*"nem giroscopio e acelerometro"*): os quatro interruptores de
  sensor ganham `data-gesto`.
- **O que o produto faz enquanto espera o OK dela:** os dois deslizantes não
  existem na página publicada, então **os dois volumes continuam sendo os
  números do desenho** — 80 no microfone e o valor do daemon no alto-falante —,
  e o `♪` continua travado para sempre em todo controle cujo volume nunca foi
  escrito por outro caminho: sem deslizante ninguém escreve o primeiro volume, e
  sem o primeiro volume o daemon recusa calar (é o beco que a S-06 abre). O
  `alto-estado` continua sendo pintado a cada tique dentro do `<span hidden>` da
  página publicada — o pacote só para de emiti-lo no dia da publicação, porque
  ele passou para `_so_se_a_pagina_tiver`. E os quatro botões de sensor
  continuam emitindo um gesto chamado `clique`, que aba nenhuma registra: a
  recusa que este trabalho escreveu (*"o giroscópio e o acelerômetro deste
  controle JÁ ESTÃO ligados…"*) só chega ao cartão dela depois que a página
  receber o `data-gesto`.
- **O `data-gesto="sensor"` é ENDEREÇO, não desenho** (está em
  `check_o_desenho_aprovado.INVISIVEIS`): se ela quiser a cura da queixa 8 antes
  de aprovar os deslizantes, ela é publicável sozinha por
  `--publicar-enderecos 02` a partir de uma bancada sem as outras duas
  entregas — hoje não, porque a mesma página carrega as três.
- **O que JÁ chegou à tela dela sem publicar nada**, porque é Python: o
  *"Virtual"* do microfone parou de recusar no cabo (queixas 6 e 15) e o *"Todo
  o som do PC"* ganhou dono e passou a mover a saída do sistema (queixa 7).
