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
- **02/09/2026** — a barra da Prioridade ganhou `data-hef-alvo="largura"`. Nada
  muda no DESENHO: é um atributo de pintura, invisível na tela. Sem ele o
  pintor escrevia `"0%"` como TEXTO dentro de uma barra de 5px e deixava a
  LARGURA nos 90% do mockup — uma barra quase cheia para um perfil em 1 de 200.
  Enquanto esta página não for publicada, `a10_perfis.NAO_PINTAVEIS` segura a
  emissão daquele endereço e quem diz a verdade é o número ao lado. A régua é
  `tests/unit/test_a_guarda_do_perfil_nao_apaga_a_tabela.py`.
