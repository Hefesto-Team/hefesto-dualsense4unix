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

- **03/09/2026** — a **decisão 11 dela**: o `Máx` do multiplicador passa a
  esconder **reservando o espaço** (`visibility:hidden`), em vez de sair do
  HTML. A palavra fica sempre no arquivo e quem a acende é a classe `on`, que o
  produto escreve. Isso muda o que se vê e por isso espera o OK dela:
  `scripts/check_o_desenho_aprovado.py --publicar 05`.
  Junto vieram os endereços de pintura dos quatro degraus de Força
  (`data-campo="degrau"`) e as oito marcas `data-hef-rotulo` — esses **não movem
  um pixel**, mas viajam no mesmo arquivo.
  Medido com a mesa dela (um DualSense no cabo, um no rádio): a aba saiu de
  **55% para 91%** pronto na `--prova-de-mockup`; o defeito que fecha é a coluna
  do P1 mostrando "Máximo" com o daemon em `balanceado`.
- **O QUE ELA VÊ ENQUANTO ESPERA, e o custo é ZERO.** A página publicada não tem
  os endereços novos: `achar()` devolve lista vazia para `degrau` e para
  `mult-teto`, e o `escrever()` nem é chamado — nenhum clique morre, nada vaza e
  o contador de pinturas não infla. Até ela publicar, a Vibração continua
  exatamente como está hoje: o degrau aceso e o `Máx` saem do desenho, que é o
  defeito que esta leva mediu. Nenhum outro campo desta aba mudou de nome.
