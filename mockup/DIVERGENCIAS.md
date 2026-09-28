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
- **28/09/2026** — o chip do «Procurando» não acende no clique quando o piloto
  está no ar: quem acende é o rádio, pelo molde (A-CAIXA-FICA-ONDE-ELA-ABRIU-01).
  Aceso no clique, o chip recusado ficava aceso sobre a busca que continuava
  noutro adaptador. Nada muda no desenho: sem o piloto (o desenho aberto no
  navegador), o chip acende no clique como antes. Até publicar, o produto
  continua acendendo o chip no clique: com a busca de pé, o chip de outro
  adaptador treme (a central recusa) e fica aceso até a próxima troca do
  painel.
