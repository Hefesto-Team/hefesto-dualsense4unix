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
| **Conexão Nativa (Sony)** | o Hefesto solta o controle e o jogo fala direto com o hardware |
| **Controlar o PC** | o controle vira mouse e teclado (fora do jogo) |

Dentro de "Jogar pelo Hefesto", a máscara diz **o que o jogo enxerga**:
`DualSense (PS)` ou `Xbox 360`.

## Como decidir, sem decorar lista

O sinal é direto:

- o controle funciona na Steam mas **fica morto dentro do jogo** → o jogo é
  Xbox-only → use **Xbox 360**;
- funciona com vibração, gatilhos e luz → deixe **DualSense (PS)**.

Com `Xbox 360` a vibração continua; o que se perde são **cinco coisas**:
giroscópio, touchpad, cor da lightbar, gatilhos adaptativos e leitura de
bateria.

A causa não é o Linux nem falta de trabalho aqui — é o **formato do controle
que a máscara imita**. O relatório de um Xbox 360 tem vinte bytes, treze deles
usados por botões, analógicos e gatilhos: não sobra lugar para eixos de
movimento, pontos de toque, cor ou carga. Escolher `Xbox 360` é escolher
**vibração que funciona em tudo** e pagar com as cinco. A demonstração, em três
camadas independentes, está em
[a pilha do Steam Input](../protocol/pilha-steam-input-xpad-sdl.md), seção 1.5.

## O terceiro caso, que confunde: suporte a DualSense **pela Steam**

Alguns jogos não falam com o controle direto — eles pedem os recursos do
DualSense à **API da Steam** (`SetDualSenseTriggerEffect`, da Steamworks). Esses
títulos têm suporte a DualSense de verdade, mas ele só funciona com o **Steam
Input daquele jogo LIGADO**, e o jogo precisa enxergar o **controle físico**.

Como o Hefesto normalmente esconde o hidraw do físico (para o jogo não ver o
controle duplicado), esses jogos precisam de uma **exceção por jogo** — o botão
**"Este jogo não funciona"**, na aba **Sistema**.

**O co-op continua funcionando nesses jogos.** A exceção troca *qual* controle o
jogo enxerga, e não derruba ninguém da partida: o gamepad virtual continua de pé
e o jogador 2 permanece.

> **NOTA DATADA — 06/08/2026, e metade dela caducou em 09/08.** Medido em jogo,
> com o Mullet Mad Jack aberto: durante a exceção o Hefesto **continua
> escrevendo no seu controle** — a cor que você escolheu **fica**, e a
> resistência de gatilho que você aplicou **segura**. A exceção **não** cala o
> Hefesto: ela troca **qual dispositivo o jogo enxerga**, e só isso. **Isto
> continua valendo.**
>
> **O que mudou:** naquele dia a exceção soltava o físico e **tirava o virtual
> de cena** — e era isso que derrubava o jogador 2, com o
> `coop_derrubado_pela_excecao_steam_input` aparecendo vinte vezes num dia. Em
> 09/08, por decisão dela, a
> [ESCONDER-EM-VEZ-DE-SAIR-01](../process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md)
> inverteu o mecanismo: **esconde-se o físico, e o produto FICA**. O duplicado
> se cura pelos dois lados, e este é o lado que não custa o co-op.
>
> A frase antiga — *"nesse jogo vale só o controle 1, sem co-op"* — sobreviveu
> nesta página por dois dias depois de a cura entrar. Foi achada na varredura de
> 11/08 e é a razão de o índice daquele dia se chamar
> [duas verdades no mesmo repositório](../process/sprints/2026-08-11-INDICE-duas-verdades-no-mesmo-repositorio.md).
>
> **O critério de quando marcar também mudou de nome.** Esta lista de exceções
> **não** é "os jogos com DualSense nativo" — é **"os jogos cujo DualSense passa
> pela Steam"**, como o próprio título desta seção diz. Um jogo com suporte
> nativo de verdade **não precisa** dela: o Sackboy foi medido no mesmo dia, fora
> da lista, e funcionou completo. Registro em
> [CONTROLE-SONY-MEDIDO-01](../process/sprints/2026-08-06-CONTROLE-SONY-MEDIDO-01-o-experimento-que-decide-metade-da-doutrina.md).

Para desfazer, a caixinha está na aba **Perfis** desde 07/08/2026: abra o perfil
daquele jogo, com **"Jogo da Steam"** escolhido e o número do jogo preenchido, e
desmarque **"Esconder os controles físicos neste jogo"**. A marca sai na hora,
sem "Salvar" — ela é do jogo, não do perfil. Se houver jogo aberto na hora do
gesto, a janela **pergunta antes de gravar**: o que o jogo já enumerou não muda
no meio da partida. Feche e abra o jogo para valer.

Pela linha de comando também dá:
`hefesto-dualsense4unix gamepad steam-input list` mostra os jogos marcados pelo
nome, e `hefesto-dualsense4unix gamepad steam-input remove <nome ou appid>`
tira a marca.

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

> **NOTA DATADA — 06/08/2026. Estes jogos NÃO precisam da lista de exceções — e
> eles mandam na luz e nos gatilhos.** Medido com o Sackboy: fora da lista, com
> o Hefesto no caminho, ele listou **um** controle, com botões de PlayStation, e
> andou normal. Mas ele **também escreve no controle** — e o que ele escreve
> **vence o que você escolheu**: a lightbar voltou ao **azul da Sony** (aplicar a
> sua cor muda por um instante, e o jogo devolve), e os gatilhos ficaram
> **moles** apesar da Resistência aplicada. **A vibração é a exceção: nela você
> continua vencendo**, inclusive o multiplicador do controle deslizante.
>
> Isso é política declarada, não defeito: o Hefesto repassa fielmente ao seu
> controle o que o jogo pede, porque escalar ou trocar o que o jogo pinta seria
> mentir sobre o que ele pediu. **Um jogo desta lista na lista de exceções não
> ganha nada** — e, desde 09/08/2026, também não perde nada: a exceção só troca
> qual controle o jogo enxerga, e o jogador 2 fica. Registro em
> [CONTROLE-SONY-MEDIDO-01](../process/sprints/2026-08-06-CONTROLE-SONY-MEDIDO-01-o-experimento-que-decide-metade-da-doutrina.md).
>
> **Uma contradição desta página, anotada e não resolvida:** o **Pragmata** está
> nesta seção *e* na lista de exceções do produto. Só um dos dois lugares pode
> estar certo, e decidir isso é medição em jogo — não foi feita.

## Não repetir a escolha toda vez

Salve um **perfil** (aba Perfis) com a máscara certa e diga **como reconhecer o
jogo**. Ele passa a trocar sozinho quando o jogo abre.

Qual campo reconhece depende de **como o Hefesto enxerga a janela nesta
máquina**, e isso não é detalhe de implementação: os campos preenchidos são um
**E**, então um campo que não casa não falha sozinho — ele **derruba o perfil
inteiro**.

| Campo do perfil | X11 / XWayland | Wayland puro (COSMIC, GNOME sem XWayland) |
|---|---|---|
| `window_class` — a Steam carimba `steam_app_<id>` | casa | casa (vem do `app_id` da janela) |
| `title_regex` — trecho do título | casa | casa |
| `process_name` — o executável | casa, com a ressalva do Proton abaixo | **não casa nunca** |

**Use `window_class`.** É o único campo que casa nos dois mundos, e é por ele
que **todos** os perfis que o Hefesto já elegeu sozinho nesta máquina foram
identificados — medido em 30 dias de journal em 10/08/2026
([PERFIL-MUDO-01](../process/sprints/2026-08-10-PERFIL-MUDO-01-o-perfil-do-jogo-que-nao-entrou.md)).

**Por que o `process_name` não casa em Wayland puro, medido:** o campo é
comparado com o nome do executável da janela em foco, e os dois backends de
Wayland (`portal` e `wlrctl`) devolvem esse nome **vazio, por construção** — o
portal recebe até o número do processo e ainda assim não o resolve. Um perfil
com esse campo preenchido não entra, e não entra **nem com o `window_class`
certo**: foi essa a causa dos cinco perfis de gênero (`FPS`, `Ação`,
`Aventura`, `Corrida`, `Esportes`) nunca ativarem. O editor avançado da aba
Perfis avisa isso na tela quando o ambiente é esse.

**E mesmo em X11 ele engana com jogo Proton:** o executável lido é o do processo
dono da janela, e sob Proton isso é `wine64-preloader` — não o `.exe` do jogo.

Se você **não** quiser que troque, existe o cadeado *"Não trocar de perfil
sozinho ao abrir um jogo"* na aba Início — o perfil que estiver ativo continua
valendo.

## Como registrar um jogo novo aqui

Testou um título e descobriu o que funciona? Acrescente na seção certa acima,
dizendo **o que foi medido** (funcionou em quais máscaras, precisou de exceção
de Steam Input?). Lista de compatibilidade só vale se cada linha for
observação, não suposição.
