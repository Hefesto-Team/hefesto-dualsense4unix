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
- **03/10/2026** — o glifo do «⋮» da linha sai da árvore de acessibilidade, e o botão
  deixa de ler o nome duas vezes. Até publicar, o leitor de tela da página publicada lê
  o nome do «⋮» duas vezes. Falta só o `--publicar 08` no fecho.

## mapa-do-controle.html
- **03/10/2026** — o PS do desenho diz «Sem tecla» na Navegação, como a aba 06 passou a dizer.
  Até publicar, o mapa publicado mostra «Abrir a Steam» no PS. Falta só o `--publicar`
  desta página no fecho.
