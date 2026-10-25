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
- **25/10/2026** — a janela da extensão ganha os modos do controle livre (Soltar, Segurar e
  Repetir) e os cartões dos controles de cada aparelho. A janela chega pelo pacote, então o
  produto já desenha os modos e os cartões ao instalar; até publicar, a página publicada não traz o
  CSS novo (`.mj-modos`, `.mj-cores`, `.mj-cc-linha`) nem o bloco dos modos do
  `comportamento.js`: os pontos e os modos aparecem sem o desenho do arranjo C.
