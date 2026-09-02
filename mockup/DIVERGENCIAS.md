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

## 05-vibracao.html
- **02/09/2026** — **nada muda na tela; muda o ENDEREÇO.** São 14 linhas, todas
  de atributo — nenhuma cor, nenhum texto, nenhuma medida. Duas coisas:
  - cada coluna ganhou `data-controle="pN"` (as quatro, viva e vazia). Sem ele o
    pintor não achava onde pôr os valores daquele controle **e** "Testar" e
    "Parar" chegavam sem dizer de quem foi o clique — medido no DOM: os quatro
    botões recusavam sempre, com o rato de verdade;
  - o par de endereços da linha "Personalizado" passou de `forca`/`forca-pct`
    para `mult`/`mult-pct`. O nome `forca` era o `data-papel` dos quatro degraus
    **e** o `data-campo` do número: o pintor escrevia `"balanceado"` dentro dos
    botões e apagava a linha inteira. Está fotografado em `/tmp/antes-05.png`.

  **O que o produto ganha quando você publicar:** a coluna passa a dizer o
  controle que está ali (hoje diz `P1 • Cosmic Red • USB` com o P1 no rádio), o
  "Personalizado" passa a mostrar o multiplicador de verdade (70%, não 150% do
  desenho), os dois motores passam a dizer `—` quando ninguém pediu vibração em
  vez de `0` e `60`, e os quatro "Testar"/"Parar" passam a ter dono.

  O comando é `scripts/check_o_desenho_aprovado.py --publicar 05`, e é seu.
