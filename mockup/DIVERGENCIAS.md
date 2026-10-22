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

## 07-lancadores.html
- **22/10/2026** — o arranjo C da janela Configurar (a coluna «Agora», os grupos em abas, o «Parar
  tudo» no topo e os toques por botão com o glifo), escolhido na foto dos três arranjos. Enquanto não
  se publica, o produto continua com a folha de antes: a janela de uma extensão que declara `agora`
  chega com as peças novas sem o estilo delas, e os glifos dos toques não aparecem.

## 08-conexoes.html
- **22/10/2026** — a vaga `extensoes-lista` na moldura dos controles: as conexões e os aparelhos de
  cada extensão ligada, «via» o nome dela. Enquanto não se publica, o produto continua sem a vaga, e
  a aba não mostra os aparelhos das extensões.
