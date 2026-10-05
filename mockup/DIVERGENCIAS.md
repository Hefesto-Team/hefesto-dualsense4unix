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
- **04/10/2026** — o desenho 1 das Conexões que ela aprovou (uma faixa por aparelho, a marca de quem
  briga, a legenda no título, o celular e o relógio na régua): o produto recebe com o `--publicar 08`
  do fecho do conjunto «Conexões 2». Até publicar, a tela dela segue a de hoje (uma pista por adaptador e a
  fileira das portas) e a integração não é instalada antes: o pacote já fala o desenho novo, e a página
  nova entra junto, no mesmo fecho.
