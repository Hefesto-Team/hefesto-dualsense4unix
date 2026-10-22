# A telemetria da corrida: o «Data Out» do Forza

Só bytes e regras: o que o Hefesto lê do pacote que o jogo de corrida publica por UDP, e como isso chega aos
gatilhos, ao corpo e à barra de luz. Cada campo leva a fonte; os endereços completos estão em «Fontes», no fim.
**Nenhum campo que as fontes não mostram é lido**, e nada se injeta no jogo: o Hefesto só escuta.

O código que segue este documento é o `integrations/telemetria_de_corrida.py` (o pacote vira estado, sem I/O) e o
`daemon/subsystems/telemetria_do_jogo.py` (a porta, a tradução e o atuador do tato).

## 0 · O que NÃO foi medido

**O envio pelo Proton ao localhost não foi medido.** Não há jogo de corrida com «Data Out» na biblioteca de teste
em 22/10/2026; tudo o que está aqui foi provado só com pacotes sintéticos, montados nos deslocamentos da seção 2.
Também não foi medido qual formato (seção 1) cada edição manda de fato: o tamanho do pacote decide, e um tamanho
desconhecido é contado como «ignorado» e não vira estado. A lista do que falta conferir com um jogo está na seção 5.

## 1 · Os formatos, pelo tamanho

Todo número é little-endian. O pacote começa sempre pelo bloco curto («Sled», 232 bytes); os longos acrescentam o
bloco do painel («Dash», 79 bytes) [G1, G2, N1].

| tamanho | formato (no código) | quem manda | onde o «Dash» começa |
| ---: | --- | --- | ---: |
| 232 | `sled` | o modo «Sled» de qualquer edição | (não tem) |
| 311 | `dash` | Forza Motorsport 7, modo «Car Dash» | 232 |
| 324 | `horizon` | Forza Horizon 4 e 5 | 244 (12 bytes do Horizon antes) [G3, G5] |
| 331 | `motorsport_2023` | Forza Motorsport de 2023 | 232 (20 bytes no fim) [G4, G5] |

Os 12 bytes do Horizon (232 a 243) são a categoria do carro e dois inteiros sem nome nas fontes; o byte 323 sobra
[G3, G5]. Os 20 bytes do Motorsport de 2023 (311 a 330) são o desgaste dos quatro pneus e a pista [G4]. O Hefesto não
lê nenhum dos três.

## 2 · Os campos lidos

Do bloco curto («Sled»), a partir do byte 0 [G1, N1]:

| byte | tipo | campo | uso |
| ---: | --- | --- | --- |
| 0 | s32 | `IsRaceOn` | 0 no menu e na pausa: nada toca |
| 8 | f32 | `EngineMaxRpm` | o topo da luz |
| 12 | f32 | `EngineIdleRpm` | o pé da luz |
| 16 | f32 | `CurrentEngineRpm` | a luz da rotação |
| 20 | f32 ×3 | `Acceleration` X, Y, Z (m/s², X à direita, Y para cima, Z para a frente) | a batida |
| 32 | f32 ×3 | `Velocity` X, Y, Z (m/s) | a trava de parado, no formato curto |
| 84 | f32 ×4 | `TireSlipRatio` FL, FR, RL, RR | a roda travada (o ABS) |
| 100 | f32 ×4 | `WheelRotationSpeed` (rad/s) | a trava de parado |
| 116 | s32 ×4 | `WheelOnRumbleStrip` | a zebra |
| 180 | f32 ×4 | `TireCombinedSlip` | a patinação |

Nas três patinações, **0 é aderência toda e |x| > 1 é aderência perdida**, nos comentários do próprio formato [G1].
Do bloco do painel («Dash»), a partir do início dele [G2, N1]:

| byte | tipo | campo | uso |
| ---: | --- | --- | --- |
| +12 | f32 | `Speed` (m/s) | a trava de parado |
| +71 | u8 | `Accel` (0 a 255) | o acelerador |
| +72 | u8 | `Brake` (0 a 255) | o freio |
| +75 | u8 | `Gear` | a troca de marcha |

O bloco curto não tem pedal nem marcha: **com ele não há ABS, patinação nem marcha**, porque não se sabe se a roda
travou sob freio ou sob acelerador. Ficam a batida, a zebra e a luz.

## 3 · A tradução (valores de partida, a validar pelo usuário)

O mapa é o que três projetos independentes desenharam (ForzaDSX, HorizonHaptics, DualSenseXLink) [F1, F2, F3], com
os dois defeitos que eles mostram curados na origem.

- **A trava de parado** [F1]: nada toca com o carro abaixo de 0,1 m/s e nenhuma roda acima de 1 rad/s. Sem ele, a
  roda travada com o carro parado vibra o gatilho para sempre.
- **A prioridade** [F2]: colisão, troca de marcha, ABS e patinação, a resistência do perfil, a superfície. A colisão e
  a marcha são toques no corpo (um por pacote, a colisão primeiro); o ABS e a patinação vencem o momento do estilo no
  mesmo lado (o freio que pulsa da Corrida cede e volta depois); a zebra só toca no R2 sem patinação.
- **L2, o ABS:** freio a partir de 10% e alguma roda com |`TireSlipRatio`| > 1 → vibração no curso inteiro, 15 Hz,
  amplitude 6 de 8.
- **R2, a patinação:** acelerador a partir de 20% e alguma roda com |`TireCombinedSlip`| > 1 → vibração a 30 Hz,
  amplitude de 1 a 8, um degrau a cada 0,25 acima de 1. Só reescreve quando o degrau anda dois ou mais.
- **R2, a zebra:** uma roda na zebra → vibração leve, 25 Hz, amplitude 2.
- **A marcha:** o número mudou → um Toque de 30 ms, energia 0,5.
- **A batida:** a aceleração horizontal do chassi passa de 3 g (30 m/s²), na borda, com meio segundo de descanso → um
  Impacto de 60 ms, energia cheia a 6 g.
- **A luz:** cinco cores do verde ao vermelho entre metade do giro e 95%. **Sobe no máximo três vezes por segundo e
  só desce depois de segurar um terço de segundo**, para o limitador no corte não virar pisca-pisca (o HorizonHaptics
  pisca a 10 Hz [F2], contra a regra dos três clarões por segundo da WCAG 2.3.1). Vale no brilho do perfil; o Automático da aba, a
  Bateria longa e o brilho zero a calam, como a luz do estilo; a luz explícita do perfil vence a da corrida.
- **Sem pacote há meio segundo** (menu, pausa, jogo fechado), tudo volta ao perfil.

**Onde o jogo escreve, o jogo decide** (`decidir` do tato): o gatilho escrito pelo jogo cala o L2 e o R2 da corrida
naquele controle, a háptica do jogo cala os toques, a barra escrita pelo jogo cala a luz. Os quatro controles recebem
o mesmo pedido, cada um pelos tetos do tato (cabo e rádio iguais).

## 4 · A porta

- **Só `127.0.0.1`**, porta de partida **5300** (a pessoa digita a mesma no jogo). Nunca `0.0.0.0`: nenhum pacote da
  rede chega ao controle.
- **Só abre com a Corrida ou a Simulação no perfil ativo**, e fecha quando o estilo sai. Porta ocupada: fica fechada e
  tenta de novo na volta seguinte, sem erro.
- O laço lê sem esperar, até 64 pacotes por volta, a 60 voltas por segundo.

## 5 · O que falta conferir com um jogo

1. No jogo, ligar o «Data Out» com o IP `127.0.0.1` e a porta `5300`, escolher o estilo Corrida no perfil do jogo.
2. **Chega pacote?** O diário do daemon (o `journal` da unidade `hefesto-dualsense4unix`) diz `telemetria_aberta`
   ao escolher o estilo e `telemetria_primeiro_pacote`, com o formato e o tamanho, ao entrar na pista. Se diz
   `telemetria_tamanho_desconhecido`, o tamanho não é de nenhum formato da seção 1: anote-o. Sem nenhuma das duas
   linhas, o pacote não chegou (o Proton, o IP ou a porta).
3. **O formato bate?** A luz segue o giro (verde em marcha lenta, vermelho no corte) e não pisca no limitador.
4. Frear forte até travar a roda: o L2 pulsa. Soltar o freio: o L2 volta ao perfil.
5. Acelerar com o controle de tração desligado até patinar: o R2 vibra, mais forte quanto mais patina.
6. Trocar de marcha: um toque curto. Bater num muro: um impacto. Passar na zebra: o R2 vibra de leve.
7. Parar o carro com o freio apertado: nada vibra.
8. Repetir por cabo e por rádio, e com quatro controles (cada cor de plástico sente o próprio).

## Fontes

- [G1] geeooff/forza-data-web, `Core/ForzaSledDataStruct.cs` — os campos do bloco curto, na ordem, com os comentários
  da patinação e dos eixos. https://github.com/geeooff/forza-data-web
- [G2] o mesmo repositório, `Core/ForzaCarDashDataStruct.cs` — os campos do bloco do painel.
- [G3] o mesmo repositório, `Core/ForzaHorizonExtrasDataStruct.cs` — os 12 bytes do Horizon.
- [G4] o mesmo repositório, `Core/ForzaMotorsportExtrasDataStruct.cs` — o desgaste e a pista do Motorsport de 2023.
- [G5] o mesmo repositório, `Core/ForzaDataReader.cs` — o tamanho de cada formato e onde cada bloco começa.
- [N1] nettrom/forza_motorsport, `fdp.py` — a mesma ordem e os mesmos tipos, conferidos à parte. <!-- ref-externa: arquivo de outro repositório -->
  https://raw.githubusercontent.com/nettrom/forza_motorsport/master/fdp.py
- [O1] a documentação oficial do «Data Out» (Forza Motorsport e Forza Horizon 6), em support.forza.net — **não
  alcançada** (403 em 22/10/2026); fica a conferir com um jogo.
  https://support.forza.net/hc/en-us/articles/21742934024211-Forza-Motorsport-Data-Out-Documentation
- [O2] o fórum oficial sobre o «Data Out» do Motorsport. https://forums.forza.net/t/data-out-feature-in-forza-motorsport/651333
- [F1] ForzaDSX / RacingDSX (github.com/cosmii02/ForzaDSX) e o port de Linux que achou a trava de parado
  (git.sigkill.computer/titaniumtown/nixos, `hosts/yarn/forza-trigger/forza_trigger.py`). <!-- ref-externa: arquivo de outro repositório -->
- [F2] HorizonHaptics (github.com/haritha99ch/HorizonHaptics) — a prioridade, a zebra a 25 Hz, a luz a 10 Hz.
- [F3] DualSenseXLink (racedepartment.com, Assetto Corsa) — a resistência que sente o pneu travar.
