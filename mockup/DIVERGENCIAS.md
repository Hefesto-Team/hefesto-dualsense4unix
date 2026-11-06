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

## 01-jogar.html
- **06/11/2026** — as dicas dos chips do Desligado viram o nome deles. Até publicar, quem usa vê a página de antes.

## 03-gatilhos.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.

## 04-iluminacao.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.

## 05-vibracao.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.

## 06-navegacao.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.

## 07-lancadores.html
- **06/11/2026** — o resumo da linha «Impedimentos» diz a conta. Até publicar, quem usa vê a página de antes.

## 08-conexoes.html
- **06/11/2026** — saem as dicas do mapa e da borda. Até publicar, quem usa vê a página de antes.

## 09-sistema.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.

## 10-perfis.html
- **06/11/2026** — sai o CSS sem uso do topo. Até publicar, quem usa vê a página de antes.
