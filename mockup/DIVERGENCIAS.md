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

## mapa-do-controle.html
- **23/10/2026** — o centro (Toque, Meio, PS) cabe entre as colunas laterais na vista de 860 px, a ação de cada linha se lê inteira (a que corta ganha reticências), e o nome comprido do chip corta com reticências (O-CHIP-DO-MAPA-CABE-A-860-PX-01). Até publicar, o produto continua com as colunas de 292 px, o chip sem corte e a ação cortada a seco.
