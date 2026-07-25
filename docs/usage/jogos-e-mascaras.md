# Que máscara usar em cada jogo

Guia curto para a pergunta do dia a dia: *"abri um jogo, o que eu escolho na
aba Início?"*

> **Este arquivo é a fonte da verdade sobre compatibilidade de jogos.** Se
> outro texto do projeto disser algo diferente sobre um título específico, o
> outro texto está errado — corrija-o e não este. A regra existe porque um
> exemplo errado escrito num tooltip se propaga para todo mundo que lê o
> projeto depois, inclusive para ferramentas automáticas.

## As três opções, em uma linha cada

| Opção | O que faz |
|---|---|
| **Jogar pelo Hefesto** | o jogo vê um controle virtual criado pelo Hefesto — é o único modo com co-op local |
| **Jogar direto (Sony)** | o Hefesto solta o controle e o jogo fala direto com o hardware |
| **Controlar o PC** | o controle vira mouse e teclado (fora do jogo) |

Dentro de "Jogar pelo Hefesto", a máscara diz **o que o jogo enxerga**:
`DualSense (PS)` ou `Xbox 360`.

## Como decidir, sem decorar lista

O sinal é direto:

- o controle funciona na Steam mas **fica morto dentro do jogo** → o jogo é
  Xbox-only → use **Xbox 360**;
- funciona com vibração, gatilhos e luz → deixe **DualSense (PS)**.

Com `Xbox 360` a vibração continua; o que se perde é o **giroscópio** (a API do
XInput não tem canal de movimento) e os gatilhos adaptativos.

## O terceiro caso, que confunde: suporte a DualSense **pela Steam**

Alguns jogos não falam com o controle direto — eles pedem os recursos do
DualSense à **API da Steam** (`SetDualSenseTriggerEffect`, da Steamworks). Esses
títulos têm suporte a DualSense de verdade, mas ele só funciona com o **Steam
Input daquele jogo LIGADO**, e o jogo precisa enxergar o **controle físico**.

Como o Hefesto normalmente esconde o hidraw do físico (para o jogo não ver o
controle duplicado), esses jogos precisam de uma **exceção por jogo** — o
opt-in em "Steam Input" na aba Emulação. Com a exceção ativa, enquanto o jogo
está em sessão o físico volta a ficar visível.

**Caso medido: Mullet Mad Jack** (appid `2111190`). Ele **funciona nas três
opções** — `Xbox 360`, `DualSense (PS)` e Modo Nativo. O suporte a DualSense
dele vem pela Steam, por isso está na allowlist de exceção
(`steam_input_apps.txt`).

>  Até 25/07/2026 a interface trazia o Mullet Mad Jack como **exemplo de jogo
> Xbox-only**, o que é **falso**. O texto foi corrigido; o registro fica aqui
> porque a informação errada circulou e pode reaparecer em cópias antigas.

## Jogos com suporte nativo a DualSense

Falam com o controle direto, sem intermediário. Funcionam completos com
`DualSense (PS)`: vibração, giroscópio e lightbar.

Casos medidos nesta máquina: **Sackboy: A Big Adventure**, **Pragmata**,
**Mad King Redemption**.

## Não repetir a escolha toda vez

Salve um **perfil** (aba Perfis) com a máscara certa e preencha `process_name`
com o executável do jogo. Ele passa a trocar sozinho quando o jogo abre.

Se você **não** quiser que troque, existe o cadeado *"Não trocar de perfil
sozinho ao abrir um jogo"* na aba Início — o perfil que estiver ativo continua
valendo.

## Como registrar um jogo novo aqui

Testou um título e descobriu o que funciona? Acrescente na seção certa acima,
dizendo **o que foi medido** (funcionou em quais máscaras, precisou de exceção
de Steam Input?). Lista de compatibilidade só vale se cada linha for
observação, não suposição.
