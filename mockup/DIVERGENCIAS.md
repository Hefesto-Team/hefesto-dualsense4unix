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

## 02-controles.html
- **03/10/2026** — o par «Virtual | Nativo» do Microfone saiu do cartão (decisão dela de
  02/10, OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01). No `--publicar 02`, o
  `a02_controles.py` perde junto o gesto `mic-modo`, as provas dele, os campos
  `mic-modo-aceso` e `mic-nativo-fora` e o `SEM_ECO`.
  Até publicar, a página do produto mostra o par, e o gesto `mic-modo` segue gravando
  a chave `microfone` do `maquina.json`, que o daemon lê como a recusa do microfone
  daquele controle (o `False` do «Nativo» tira o canal, nos dois transportes).
