# `mockup/` — o desenho aprovado

**Decisão de 31/08/2026**, com este diagnóstico: o problema original foi não
separar a pasta do mockup e fazer a interface com o HTML do mockup. **Se o layout
final muda, a referência do mockup se perde.**

Mockup e produto eram o mesmo arquivo — então toda mudança de produto apagava,
em silêncio, o desenho contra o qual comparar.

## As duas pastas, e o que cada uma é

| | o que é | quem escreve |
|---|---|---|
| **`mockup/`** | o desenho que se constrói e que se olha antes de aprovar. | os geradores `src/hefesto_dualsense4unix/interface/abaNN.py` |
| **`src/hefesto_dualsense4unix/interface/paginas/`** | o **publicado**: o que o produto renderiza. | só o `--publicar NN`, e só depois do OK |

**A DIREÇÃO É `mockup/` → PUBLICADO, NUNCA O CONTRÁRIO** — e o sentido inverso
foi o defeito original, o que o diagnóstico nomeou lá em cima. Rodar `abaNN.py` muda o
DESENHO e não toca no que quem usa vê; sem `--publicar` a tela fica igual.

**ENDEREÇOS QUE MUDARAM, e o comando velho não existe mais:**

* `layout/` foi aposentada em 31/08/2026 — era cópia velha que já tinha
  divergido 25 KB sem ninguém ver. Quem renderiza hoje é `interface/paginas/`.
* Os geradores saíram de `_ferramentas/` para dentro do pacote, em
  `src/hefesto_dualsense4unix/interface/`.

## O portão

`scripts/check_o_desenho_aprovado.py` compara as duas pastas por sha256 e
**reprova toda divergência não declarada**. Ele existe porque o preço de duas
cópias sem régua foi medido em 31/08/2026: `layout/` e `novo-layout/` divergiram
**25 KB** sem ninguém ver, o lançador passou a abrir a errada, e os glifos L2 e
R2 sumiram da aba Gatilhos por dois dias.

**Quando o desenho andar na frente e a divergência for legítima**, declare em
`mockup/DIVERGENCIAS.md` com data e motivo — é o que fica visível enquanto espera.

**QUANDO A ABA FOR APROVADA, o comando é `--publicar`, e `--aprovar` MORREU:**

```
scripts/check_o_desenho_aprovado.py --publicar 07     a aba 07 foi aprovada
scripts/check_o_desenho_aprovado.py --publicar        as dez foram aprovadas
```

O `--aprovar` copiava o PRODUTO para o DESENHO — a direção que apaga a
referência — e hoje o script o RECUSA dizendo, apontando o `--publicar`. Há um
terceiro, o `--publicar-enderecos NN`, que leva só `data-campo`/`data-gesto`
novos em elementos que já existiam: isso não muda um pixel, então não precisa
de aprovação. Ele RECUSA sozinho quando o desenho mudou.

**Nunca** conserte o portão editando `mockup/` à mão para calar o vermelho: o
vermelho é a informação.
