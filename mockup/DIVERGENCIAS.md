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

## 07-lancadores.html
- **10/09/2026** — o **«Escolher o arquivo…»** na caixa «Localizar um lançador»
  (LANCADOR-LOCALIZAR-01). É a decisão dela de 09/09, a opção **(C)**: o campo
  de texto FICA — é o único caminho para um AppImage solto, que não tem
  `.desktop` — e ganha ao lado o botão que abre o seletor do sistema, para ela
  apontar o atalho com o mouse: *"aí eu mesmo abro a tela e procuro o  <!-- noqa-acento: citação literal dela -->
  .desktop."*  <!-- noqa-acento: citação literal dela -->

  **É A ÚNICA METADE DA SPRINT QUE MUDA A PÁGINA, e o resto dela já está no
  produto:** tirar o «Consertar» do cartão LOCALIZADO e pôr o «Localizar este
  Lançador» nos seis cartões achados mudam **zero byte** das duas páginas,
  porque o estático nasce de `cartoes(None)` — a primeira meia volta, em que os
  seis saem `nao_sei`. Só a pintura viva os mostra.

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA, e ele não fica pela metade:** até
  publicar, a caixa que ela abre na tela dela hoje tem os **dois campos de
  texto e mais nada** — o botão não existe ali, e o gesto que o atende
  (`procurar-o-arquivo`) fica sem nenhum clique que o alcance. Nada de clique
  morto: quem responde ao «Adicionar» continua sendo o mesmo gesto de sempre,
  e a única frase nova que a tela mostra (a que manda usar o botão do cartão
  quando ela digita um nome de fábrica) cita um botão que **já está na tela
  publicada**, porque ele é pintado vivo. O que falta é o olho dela na bancada,
  e depois `scripts/check_o_desenho_aprovado.py --publicar 07`, que é ato dela.
  A foto da caixa com o botão está na entrega
  (`docs/process/agentes/2026-09-10/LANCADOR-LOCALIZAR-01-opus.md`).
