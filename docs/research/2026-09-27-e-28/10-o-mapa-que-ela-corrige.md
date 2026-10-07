# O mapa de canais corrigido pela bancada

Por que o «Mapa das Conexões» identificou errado as entradas USB de uma máquina real, e o que a sprint `O-MAPA-QUE-ELA-CORRIGE-01` deu à tela para ela corrigir. Medido e construído em 26/09/2026, a partir do `dev` em `34a474e9a`.

Legenda: **MEDIDO** (rodou-se e viu-se), **LIDO** (código ou disco), **INFERIDO** (dedução sem medida). As medidas e o piloto rodaram num lar de mentira (`HOME` e `XDG_*` desviados), com uma cópia do `maquina.json` e o `/sys` real só lido, e não mudaram o `maquina.json` dela (o mesmo sha256 antes e depois). Os caminhos curtos são relativos a `src/hefesto_dualsense4unix/`, e as linhas são as desta árvore.

## O pedido

*«me referi as portas renomear, trocar elas de lugar no meapemento identificar onde fica o hub e afins. corrigir quando for 2.0 e tal. até agora não entendi pq identificou errado.»* <!-- noqa-acento: citação literal -->

Quatro atos numa entrada do mapa (renomear, trocar de lugar, dizer onde fica o hub, corrigir a velocidade) e uma explicação.

## Por que identificou errado

1. **As duas pistas, e o hub de dois chips (curado antes desta sprint).** Cada buraco USB 3 tem uma pista 2.0 e uma 3.0, cada uma com seu endereço no `/sys`; o hub de 7 entradas são dois chips em fila (`3-1`/`3-1.1` a 480M e `4-1`/`4-1.1` a 5000M, Genesys Logic). O «Mapear» anotava só a pista 2.0, e o Wi-Fi USB 3, em `4-1.1.4`, caía «sem entrada»; os chips do hub apareciam como aparelhos. MEDIDO: com a leitura de antes da cura, `sem_entrada` saía com exatamente os quatro itens errados da foto dela; com a cura, sai vazio e o Wi-Fi é lido na entrada 9. A cura é `_leitura_pelas_entradas` (`src/hefesto_dualsense4unix/integrations/mapa_das_portas.py:373`, commit `7d24bcec7`), e o nome próprio do adaptador veio em `6ca4a413b` (`D-2609-O-ADAPTADOR-TEM-NOME-PROPRIO`). Ela não tinha reaberto o mapa depois dessas curas.
2. **A tabela da placa-mãe está trocada (INFERIDO, e forte).** MEDIDO no `/sys`: `usb1-port3` e `usb1-port4` (a frente, entradas 2 e 1) não têm `peer` SuperSpeed; `usb1-port5↔usb2-port1` e `usb1-port6↔usb2-port2` (entradas 8 e 7) têm. Ela disse que a frente é azul (USB 3.0) e que a 7 e a 8 são pretas (USB 2.0); a placa é uma Gigabyte B450M S2H (pelo DMI), cuja ficha técnica põe atrás 4 USB 3 e 2 USB 2, e um conector interno USB 3 para a frente. O `connect_type` não separa nada, e o `location` ACPI se repete em várias portas. Como nenhuma velocidade estava declarada (`declarado` vazio nas 15 entradas), a frente saía USB 2 e a 7 e a 8 saíam USB 3, o contrário do que ela disse. **A placa erra, não o Mapear.**
3. **O número segue a ordem em que ela plugou, não a do metal.** `_menor_livre` dá o número e `_por_na_face` põe no fim da fileira (LIDO). A ordem 9 a 15 do hub é a do Mapear, e o `par` de duas em duas herda o erro. Nenhum gesto reordenava.
4. **Os nomes eram o próprio número.** 13 das 15 entradas se chamavam «2»… «15»; a 1 se chamava «Meio», sobra da herança D3 (o nome do adaptador copiado para a entrada). Daí «O 13» e «no 13» no governador do rádio (que adivinhava o gênero pelo nome) e «Entrada: 2» no Mapear.
5. **O hub aparecia solto.** Um quadrado «Hub» na entrada 3 e uma face «Num hub ou extensão» sem dono: `daEntrada` só nascia de declaração. Declarar «Hub» na 3 piorava: nascia uma segunda face, «Hub na Entrada 3», com quatro buracos inventados, e o painel passava de «15 de 15» para «15 de 19» (a deduplicação comparava só o nome da face).
6. **A discordância entre o mapa e a amarra em 3↔4, 5↔6 e 7↔8 não veio do Mapear.** MEDIDO: veio de uma gravação feita por script direto no `maquina.json` real, às 15h43 de 26/09, fora do Mapear e do editor (o diário não tem nenhum gesto `entrada-*`). Ela trocou `caminho` e `nos` nesses pares e declarou `usb: 2` na 1, na 2, na 7 e na 8, sem tocar nos `lugares`. Por isso a página passou a dizer «Hub na Entrada 4». INFERIDO: essa troca é a correção que ela pediu, e «Trocar 3↔4» a desfaria.

## O que se mediu no editor antes da sprint

- **O editor já gravava.** «USB 3.0» na entrada 1 gravou `usb: 3` e «Hub» na 3 gravou `liga: "hub"`; não havia elo quebrado entre o clique e o disco. Mas **ela nunca escolheu uma opção**: nas 7.601 linhas do diário da interface (07/09 a 26/09) não há `entrada-o-que-tem` nem `entrada-velocidade`, e nada na tela dizia que o plugue abre um editor.
- **Três elos frouxos:** a tela apertava o botão antes do disco, e uma recusa seria invisível (INFERIDO); reabrir a mesma página a deixava em «Leitura de Exemplo» (MEDIDO; o `_carregou` saía cedo quando a página era a mesma); «Mudar de Entrada» e o «ensinar» só mexiam na memória (MEDIDO), contra o que a própria página prometia («eu aprendo para sempre»).
- **Um campo novo dentro de `mapa.portas[N]` apagava o mapa inteiro** num código mais velho: `_o_que_ainda_vale` descartava `('mapa',)` e sobravam 0 entradas e 0 faces. `liga` e `usb` já tinham entrado assim em `55b3c11e5`.
- **Declarar a velocidade corrige a cor, não a leitura.** Simulado em memória, um pendrive USB 3 na frente cairia «sem entrada» (se enumerasse em `2-3`/`2-4`) ou seria lido na entrada 8 (se em `2-1`).

## O que se decidiu

Seis decisões, registradas na sprint pelo ID: as quatro primeiras chegaram decididas e ali só se detalham; a quinta e a sexta nasceram nela.

| ID | a regra |
|---|---|
| `D-2609-O-NOME-E-DA-POSICAO` | o nome mora em `mapa.portas[N].nome`, até 24 caracteres; um nome igual ao número, a «Entrada N» ou ao número de outra entrada **não é nome**. A grafia tem um dono só, `src/hefesto_dualsense4unix/utils/rotulo_da_entrada.py` (`PALAVRA_DA_ENTRADA`, `nome_que_vale`, `com_artigo`, com artigo sempre feminino); a leitura é `nome_da_entrada` e `rotulo_do_numero` em `integrations/entrada_a_entrada.py:1110` e `:1462` |
| `D-2609-TROCAR-MOVE-O-BURACO` | «Trocar com…» move entre N e M tudo que é do buraco físico (`caminho` e `nos` sempre juntos, `liga`, `usb`, a ponta do extensor, a amarra em `lugares`, a face do hub declarado); o número, o nome e a posição na face ficam. Desfazer é trocar de novo. Reordenar os números foi recusado: contraria o `_NUMERO_DE_ENTRADA` (`utils/maquina.py:71`), que é o número escrito no gabinete |
| `D-2609-O-HUB-PENDE-DA-ENTRADA` | `de_quem_pende` (`integrations/entrada_a_entrada.py:1529`) liga a face à entrada pelos caminhos e nós que o Mapear gravou (vale com o hub desplugado); a declaração dela vence, e a divergência vira uma linha: «O computador lê este hub na Entrada 5.». A face fantasma só nasce para o hub declarado sem face ligada |
| `D-2609-A-VELOCIDADE-DELA-VENCE-A-PLACA` | a precedência continua aparelho USB 3 enumerado > o que ela disse > a placa (`velocidade_da_entrada`, `integrations/mapa_das_portas.py:524`); o editor diz de onde veio («É o que a placa-mãe diz.», «É o que você disse.») |
| `D-2609-A-TELA-DO-MAPA-ESPERA-O-DISCO` | no produto, o clique do editor não pinta nada local: o gesto grava e devolve o arranjo relido (`CHAVE_DEPOIS_DE_GRAVAR`, `interface/arranjo_desta_maquina.py:27`); uma recusa não repinta, e a piscada acha o botão |
| `D-2609-ENSINAR-GRAVA-O-NO` | o aparelho «sem entrada» posto numa entrada grava o nó onde está e o `peer` dele (`ensinar_a_entrada`, `integrations/entrada_a_entrada.py:1367`), sem tocar em `lugares`; é a cura universal da pista que o firmware não liga |

## O que se construiu

- **A rede antes do campo novo:** `_o_que_ainda_vale` (`utils/maquina.py:943`) desce um nível em `mapa` e perde só a entrada ou o campo torto.
- **O nome** grava por `dar_nome_a_entrada` (`integrations/entrada_a_entrada.py:1426`), pelo gravador único `_gravar_no_mapa` (`:1226`); a primeira gravação leva o nome de `lugares` para a posição. Os textos de tela que dizem a entrada (ordens, Sugestão, governador, «Já mapeadas», Rádio e Adaptadores, página do mapa) perguntam ao dono, salvo as frases do item 3 de «O que ficou aberto».
- **A troca** é `trocar_as_entradas` (`:1677`), no gesto `entrada-trocar`.
- **A velocidade** tem uma pergunta só para o Mapear e o arranjo, `aparelho_usb3_na_entrada` (`integrations/mapa_das_portas.py:543`); o Mapear olhava só o primeiro aparelho dos nós, um segundo dono vivo que a régua achou.
- **Réguas:** `tests/unit/test_o_nome_da_entrada_e_da_posicao.py`, `test_trocar_duas_entradas_move_o_buraco.py`, `test_o_hub_diz_de_qual_entrada_pende.py`, `test_o_rotulo_da_entrada_tem_um_dono.py`, `test_ensinar_a_entrada_grava_o_no.py`, `test_o_mapa_que_ela_corrige_na_tela.py` (WebKit sob `xvfb-run`), mais as extensões de `test_mapa_da_mesa_sobrevive_a_versao.py` e `test_a_entrada_declarada_vence_o_firmware.py`. Todas morderam com a cura arrancada.
- **Na tela** (piloto no WebKit, máquina sintética): renomear e apagar, «Hub na Entrada 3» com o painel em «15 de 15», trocar 7↔8 e trocar de novo, «USB 3.0» na 1 com «É o Que Você Disse.», a recusa sem mudar o disco, um nome de 25 letras recusado, e um pendrive ensinado na 2 que continua na 2 depois de recarregar. Nenhum controle novo nasce cinza; o editor mede 300 px, e com nome de 24 letras a face desce para a linha de baixo.

A conferência achou e curou três defeitos: o número de **outra** entrada virava nome (com a amarra quebrada, a entrada 3 se chamava «4»); a régua da Sugestão não via o destino; e o cabeçalho do editor com nome comprido quebrava lado a lado. Também corrigiu uma isenção que dizia que `integrations/arranjo_da_mesa.py` não chega à tela: ele chega ao «Mapear Entradas» da aba Conexões, pelo `julgar`.

## O que ficou aberto

1. **O exemplo da aba 08 no gerador** (`interface/aba08.py`, fora da posse da sprint) usava a chave `lugar`, e o «Já mapeadas» passou a ler `lugar_no_gabinete`: duas réguas do gerador da 08 ficaram vermelhas no fecho da rodada. A cura é corrigir o exemplo, regerar `mockup/08-conexoes.html` e publicar.
2. **O «Já mapeadas»** passou a mostrar nome + face, sem o «Entrada N» do desenho aprovado, e só lista entradas com nome de verdade. Espera a aprovação do desenho.
3. **Frases fora do dono:** a dica «Você já colocou este aparelho na entrada {n}.» e a frase do `julgar`, que vêm de `interface/logica_do_mapa.py` e `integrations/arranjo_da_mesa.py`; as composições que sobram estão declaradas em `_OS_QUE_PODEM` (`tests/unit/test_a_costura_da_onda_2.py:818`), entre elas as de `app/actions/config/secao_mesa.py` e `interface/aba08.py`.
4. **A amarra quebrada na máquina dela** (os seis `lugares` que contradizem `portas` depois da gravação das 15h43): o reparo foi só simulado — gravar em cada lugar a entrada cujo caminho é a testemunha dele; os 15 rótulos ficam iguais e o `mapa` não muda. Enquanto isso, «trocar de novo» não devolve o JSON byte a byte nos pares 3↔4, 5↔6 e 7↔8 (a tela volta igual).
5. **O nó que o firmware pareou errado.** Se um pendrive USB 3 na frente aparecer na 8 ou na 7, a cura é mover **um** nó entre entradas, não o buraco: sprint a abrir, se for o caso, `O-NO-QUE-O-FIRMWARE-PAREOU-ERRADO-01`. Ensinar no `/sys` desta placa deu 3 nós à entrada 2, porque o `peer` de `usb2-port3` é `usb1-port7`.
6. **Dois riscos sem régua.** O ensinar não confere a amarra por lugar de outra entrada (INFERIDO). E uma janela da interface aberta desde antes de um install roda código velho: se ela gravar depois de o código novo gravar um `nome`, o mapa sai do disco e fica só no `maquina.json.invalido` (o descarte foi MEDIDO em laboratório). A rede protege do próximo campo, não do código já em memória; o fecho manda conferir, por PID, se sobrou janela de antes do install e reabri-la.
7. **Fora da sprint.** Do censo, noutra sprint: o Wi-Fi «Não Identificado» (classe `ff/ff/ff`), e Mouse e Teclado deduzidos só pela interface 0 (`integrations/censo_do_barramento.py:20`), quando os dois receptores têm as duas. E ainda: o chip de dentro do hub listado como «Entrada 1.1» pelo `ler_o_mapa` (sem tela hoje), e o hub desenhado com quatro buracos, quando o `maxchild` do `/sys` daria sete (com a face ligada, isso deixa de aparecer na máquina dela).
8. **O que só ela confirma no gabinete:** se o hub está na entrada 3 de trás, a cor da frente e das 7 e 8, a ordem 9 a 15 no plástico, se «Meio» é nome da entrada ou só do adaptador, e em que entrada aparece um aparelho USB 3 encaixado na frente.
9. **As seis decisões** não estão em `docs/data/decisoes-de-produto.csv` desta árvore; a sprint manda gravá-las lá.
