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
- **24/10/2026** — a entrada-mãe do extensor diz «Ocupada», com a dica «Com o extensor», como no Mapa das conexões (O-PORTE-E-A-PAGINA-DO-ARRANJO-DIZEM-O-MESMO-TEXTO-01). O quadrado do mapa da aba já vem do motor, então o produto diz isso ao instalar; até publicar, só a cópia estática da aba continua com «Indisponível».

## mapa-das-portas.html
- **24/10/2026** — a linha «Hoje ele está na …» e o porquê «esta opção não usa a …» dizem a entrada pelo nome que você deu («entrada Atrás»), como as outras frases do mapa (O-PORTE-E-A-PAGINA-DO-ARRANJO-DIZEM-O-MESMO-TEXTO-01). Até publicar, o produto continua com o número cru nessas duas frases.
