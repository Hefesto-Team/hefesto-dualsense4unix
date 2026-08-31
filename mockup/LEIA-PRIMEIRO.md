# `mockup/` — o desenho que ELA aprovou

**Decisão dela, 31/08/2026**, e o diagnóstico é dela, com estas palavras:

> *"o problema original foi não ter separado a pasta do mockup e ter feito a
> interface usando o HTML do mockup. **Se alteramos no layout final a referência
> do mockup se perde.**"*

Ela tem razão, e o próprio `CLAUDE.md` confessava o colapso: *"se você mudar o
mockup, mudou o produto"*. Mockup e produto eram o mesmo arquivo — então toda
mudança de produto apagava, em silêncio, o desenho contra o qual comparar.

## As duas pastas, e o que cada uma é

| | o que é | quem escreve |
|---|---|---|
| **`mockup/`** | o desenho **aprovado por ela**. Congelado até ela aprovar outro. | só ela, pelo `--aprovar` |
| **`layout/`** | o que o produto **renderiza**. Muda por razão de produto. | os geradores `_ferramentas/abaNN.py` |

**Aqui não há gerador.** Estes HTML são uma fotografia: o que ela olhou e disse
que estava bom. Editar um arquivo daqui à mão é falsificar a fotografia.

## O portão

`scripts/check_o_desenho_aprovado.py` compara as duas pastas por sha256 e
**reprova toda divergência não declarada**. Ele existe porque o preço de duas
cópias sem régua foi medido em 31/08/2026: `layout/` e `novo-layout/` divergiram
**25 KB** sem ninguém ver, o lançador passou a abrir a errada, e os glifos L2 e
R2 sumiram da aba Gatilhos por dois dias.

**Quando o produto mudar e a divergência for legítima**, declare em
`mockup/DIVERGENCIAS.md` com data e motivo. **Quando ela aprovar o desenho
novo**, rode `scripts/check_o_desenho_aprovado.py --aprovar` — a fotografia é
refeita e as declarações antigas são apagadas.

**Nunca** conserte o portão editando `mockup/` à mão para calar o vermelho: o
vermelho é a informação.
