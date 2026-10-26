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
- **26/10/2026** — a janela Configurar da extensão, pela auditoria: a chave do grupo vira a bolinha da aba, a Toques
  em colunas sem rolagem, a dica, a unidade e o zero da opção, o segundo clique do «Esquecer», o estado do aparelho
  igual nos quatro lugares e o rascunho que acende o Guardar e arma o «Descartar». Até publicar, o produto mostra a
  janela de antes; o `--publicar` sai na costura.
