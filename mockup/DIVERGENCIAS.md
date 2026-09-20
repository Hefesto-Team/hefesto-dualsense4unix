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
- **20/09/2026** — o «Nativo» do microfone nasce CINZA onde o aparelho não o
  alcança, com a razão no `?` ao lado. É a PARTE 3 da
  `2026-09-20-O-APARELHO-NAO-SE-CONTRADIZ-01`, e a decisão é dela, verbatim:
  *"Fica os dois botões. Mas no rádio o botão fica cinza sem ser ativado"*.

  **O QUE ESPERA O OLHO DELA:** a fileira do modo do microfone ganhou o `?` ao
  lado do «Nativo» — mais nada muda de tamanho (o card continua em 328 px, e a
  altura foi medida no próprio gerador). O produto já sabe apagar o botão e já
  recusa o clique com a mesma frase; enquanto a aba não for publicada, o pacote
  NÃO emite o campo (`a02_controles.A_PAGINA_APAGA_O_NATIVO`), então a tela que
  ela usa hoje continua idêntica.
