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
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-01, esperando a sessão dela. A
  coluna «Status» (o ajuste próprio de cada controle) ganha a oitava célula, a
  da Mira Virtual, com o glifo do analógico direito, e a dica do cabeçalho passa
  a contar oito. O campo já está no perfil (`ControllerOverrides.movimento`);
  enquanto ela não publicar, o produto distribui sete células por linha e a
  frase da linha conta sete (`perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA`). Quem
  publicar move o `movimento` de lá para `a10_perfis.SECOES_DA_COLUNA` no mesmo
  commit — a régua reprova até isso.
