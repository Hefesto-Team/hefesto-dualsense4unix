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
- **21/10/2026** — o «Ligado na entrada» do hub diz a entrada pelo dono: «Ligado na Entrada 10», ou «Ligado na entrada Meio» com o nome dado à entrada, e a pergunta do «Acrescentar hub» é «Ligado» com a lista «Entrada 1», «Meio»… (cada opção abre com maiúscula) (O-LIGADO-NA-ENTRADA-DIZ-A-ENTRADA-PELO-DONO-01, leva fim-da-fila). Até publicar, a página publicada guarda o «Ligado na entrada 10» velho; o mapa que o produto monta na hora já sai da composição nova.
