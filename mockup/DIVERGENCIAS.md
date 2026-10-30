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

## 06-navegacao.html
- **30/10/2026** — o molde «Adulto» sai da lista do point and click sem a extensão que o pede (D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA); até publicar, a página publicada traz o «Adulto» estático e o bloco do tique reescreve a lista ao vivo sem ele; o `--publicar 06` é de quem coordena.

## 10-perfis.html
- **30/10/2026** — o «Adulto» sai da lista do «Estilo de jogo» sem a extensão que o pede (D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA); até publicar, a página publicada traz o «Adulto» estático e o bloco do tique reescreve a lista ao vivo sem ele; o `--publicar 10` é de quem coordena.

## mapa-do-controle.html
- **30/10/2026** — o molde «Adulto» sai da lista do perfil sem a extensão que o pede (D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA); até publicar, a página publicada traz o «Adulto» estático e a lista que o tique pinta já sai sem ele; o `--publicar` é de quem coordena.
