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
