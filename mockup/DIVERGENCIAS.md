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

<!-- Nenhuma aba em trabalho: o produto está igual ao desenho dela. -->

## 07-lancadores.html
- **21/10/2026** — a fila dos lançadores rola por dentro e o ⋮ aberto fica à vista na lista das extensões (A-EXPERIMENTAL-MAXIMIZADA-NAO-QUEBRA-COM-AS-EXTENSOES-DE-VERDADE-01, leva fim-da-fila). Até publicar, a página publicada continua com a fila sem rolagem: na janela maximizada, com sete extensões, o miolo rola 13 px e o último ⋮ aberto nasce 8 px abaixo do fim da lista.

## 08-conexoes.html
- **21/10/2026** — o «Vale evitar» da tela «Mapear entradas» diz a entrada pelo dono, «na Entrada 7» (O-MOTOR-DO-ARRANJO-E-O-DESENHO-DIZEM-A-ENTRADA-PELO-DONO-01, leva fim-da-fila). Até publicar, a página publicada guarda a frase velha só no desenho estático; a grade que o produto monta na hora vem do motor e já diz «na Entrada 7».
