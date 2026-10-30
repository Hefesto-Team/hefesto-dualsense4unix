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

## 04-iluminacao.html
- **30/10/2026** — texto sem pessoa (leva do texto neutro): um docstring do gerador que o desenho carrega e a dica do número no lugar sem plástico. Até publicar, o produto mostra o texto antigo do publicado; nenhum pixel muda.

## 08-conexoes.html
- **30/10/2026** — texto sem pessoa (leva do texto neutro): as dicas do mapa das conexões, da extensão nova, da fase em pé e do «não alcanço», a pergunta do Mover («Só este sai daqui») e a dica do acionador. Até publicar, o produto mostra as dicas antigas do publicado; nenhum pixel muda.
