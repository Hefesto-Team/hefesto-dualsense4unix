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
- **03/09/2026** — a cor da pílula do Check-up saiu do desenho. Cada linha do
  exame ganhou um interruptor invisível por estado (`selo-certo`,
  `selo-atencao`, `selo-nao-sei`; o `problema` já era a própria pílula), e a
  folha de estilo passa a ler a cor do irmão. Sem isto, um achado `certo` na
  segunda posição mostrava a palavra **CERTO** dentro da pílula **laranja** —
  a palavra era do produto, a cor era do mockup.
  Não publiquei: quem publica é quem integra a leva.
