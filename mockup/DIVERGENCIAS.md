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
- **05/10/2026** — o desenho aprovado do conjunto «Conexões 3» (`docs/process/estudos/2026-10-05-a-conexoes-enxuta/DESENHO-APROVADO.md`): as dicas em até quatro cartões da mesma altura, «Tudo certo», o lugar vazio só com o número, as ferramentas embaixo, o Rádio com ícone · faixa · ponto, as caixas fechadas e a primeira maiúscula. Espera o `--publicar` de quem coordena, no fecho. Até publicar, o produto continua com a página de 04/10 e o pacote novo pinta nela (as dicas sem «mais N», as linhas do ar só com ícone e ponto, o cartão do pedido) sem a folha nova: por isso o `--publicar 08` vai no MESMO fecho, antes do merge no `dev`.

## mapa-das-portas.html
- **05/10/2026** — o desenho aprovado do conjunto «Conexões 3»: o painel único da entrada e do aparelho, as trocas em cartões, o USB 2.0 cinza e as frases sem maiúscula em toda palavra nem primeira pessoa. As edições moram em `EDICOES_ESPERANDO_A_SESSAO_DELA` até o `--publicar`. Até publicar, o produto continua com o Mapa de 04/10 inteiro: do pacote só mudou o `aparelho-tipo`, que lê o tipo pelo `valor` da lista nova ou pelo `tipodito` do botão velho, e os dois chegam.
