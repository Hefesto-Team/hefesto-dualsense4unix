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

## 10-perfis.html
- **16/10/2026** — a coluna «Ajuste próprio» ganha os glifos da ativação dos botões e da curva dos analógicos, e o vão entre as seções desce de 6 px para 5 px para as dez caberem na célula. Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com as oito seções de hoje na coluna (`perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA`), e esta aba fica sem o contrato do teclado da base comum e sem a alça da divisa pelas setas.

## mapa-das-portas.html
- **16/10/2026** — a base comum dá parada no Tab a todo título, rótulo ou frase com dica (o foco abre a dica e ganha contorno). Só o foco muda; a tela parada é a mesma. Até publicar, o produto abre a dica dos títulos só quando o mouse passa; o desenho abre também pelo foco. Espera o `--publicar` da costura.
- **16/10/2026** — no Sugestões, o tipo e o nome de cada aparelho da cadeia cortam com reticências em vez de quebrar a linha, e o nome inteiro vai na dica do chip. Só muda quando o nome não cabe. Até publicar, o produto quebra o chip em duas linhas; o desenho corta. Espera o `--publicar` da costura.

## mapa-do-controle.html
- **16/10/2026** — a mesma base comum (a dica abre pelo foco nos títulos). Até publicar, o produto abre a dica dos títulos só com o mouse; o desenho abre também pelo foco. Espera o `--publicar` da costura.
