# As abas em trabalho no desenho

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ainda não recebeu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** O `mockup/` é o desenho de hoje; o produto
só recebe quando a aba é aprovada **inteira**, que é a escolha de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto na aba.
```

Quando a aba for aprovada, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## calibrar-sensores.html
- **07/11/2026** — o desenho da mira com horizontal e vertical, o início do analógico, a velocidade do jogo e os passos do sentido e do início, em duas opções: `calibrar-sensores.html` (A, tudo na coluna da mira) e `escolha/calibrar-sensores-b.html` (B, os três passos na fita). Enquanto a escolha não vem, o produto continua com a sensibilidade única de hoje. Publicar a B é copiar esse arquivo por cima do `calibrar-sensores.html` antes do `--publicar`.
