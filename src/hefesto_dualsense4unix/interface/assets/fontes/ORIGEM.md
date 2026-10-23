# As fontes da interface

As duas famílias abaixo vêm com o produto, sob a SIL Open Font License 1.1 (o texto
de cada uma está ao lado). O `topo.html` as declara por `@font-face`; nenhuma página
pede fonte à rede.

| arquivo | família | versão | eixo | origem | licença |
| --- | --- | --- | --- | --- | --- |
| `SpaceGrotesk-wght.ttf` | Space Grotesk | 2.000 | `wght` 300–700 | `google/fonts`, `ofl/spacegrotesk` | `OFL-SpaceGrotesk.txt` |
| `JetBrainsMono-wght.ttf` | JetBrains Mono | 2.211 | `wght` 100–800 | `google/fonts`, `ofl/jetbrainsmono` | `OFL-JetBrainsMono.txt` |

Os dois arquivos são os mesmos que a Forja já guarda em `godot/assets/fontes/`
(23/10/2026). SHA-256:

```
acad6de1fc93436f5c0f1f4137751ef04f1aea3063e7036535970ffcfbd79f72  SpaceGrotesk-wght.ttf
48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda  JetBrainsMono-wght.ttf
```

O `@font-face` declara os pesos que o antigo `<link>` do Google pedia: 400–700 da Space Grotesk e
400–500 da JetBrains Mono. A mono não declara 600 e 700 de propósito: o negrito dela continua o
sintetizado de antes, e a letra das abas não muda (com o eixo inteiro, 100–800, quatro abas mudavam
de peso).
