---
sprint: MESA-DE-QUATRO-01
estado: aberta
posse:
  BANCADA:
    - docs/data/ensaios.csv
cria:
  - docs/process/2026-09-07-A-MESA-DE-QUATRO-o-que-a-bancada-mediu.md
bancada: true
depois_de:
  - A-PALAVRA-MESA-SAI-01
  - A-TELA-SAMBA-01
  - CONEXOES-LIGAR-TUDO-01
  - ONDA4-S10-O-TRANSPORTE-01
  - ONDA5-01-01
  - ONDA5-02-01
  - ONDA5-MIC-VIRTUAL-01
  - SPECS-A-PROCEDENCIA-01
nao_toca:
  - src/
  - tests/
  - mockup/
  - docs/data/paridade-gtk-html.csv
---

# MESA-DE-QUATRO-01 · BANCADA — quatro DualSense, por cabo e por rádio, com ela

> **ESTADO 08/09/2026, 22h:** o §1 está PAGO — merge em `dev`, **51 portões**,
> `install.sh` rodado (daemon reiniciado às 21h38, `doctor` sem falha), os quatro
> na mesa dela (P2 e P3 no cabo, P1 e P4 no rádio). Do roteiro, o que já tem
> medição no caderno: **linha 9/20** — o mic pelo rádio ENTREGA VOZ com a ponte de
> pé, um de cada vez, e o negativo do mudo (`mic-radio-a-voz-sai-0907`,
> `mic-radio-negativo-do-mudo-0907`, 07/09); **linha 11** — a bomba MONTOU os dois
> arranjos sem escrever (07/09) e em 08/09 seis passadas escrevendo deram
> silêncio nas seis, **ainda sem linha no caderno**. A conferência dela de 08/09
> fechou `7 ✓ / 0 falta`. O documento de `cria:` ainda não existe — nasce da hora
> dela. **O giroscópio com o jogo aberto é desta bancada:** a
> [SENSORES-NO-JOGO-01](2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md)
> levou a prova até o vpad, e o que falta — o jogo aberto receber e reagir — é
> daqui, como diz a dona da linha `sensor` na régua da quinta pergunta
> (RESTOS-DA-ONDA-TRES-01, 13/09).
> **Nota de 13/09/2026, antes de escrever as células `movimento.*.jogo` do mapa:**
> o zero em Modo Virtual do laudo de 09/09 era da libSDL2 2.30.0 do sistema, que
> nenhum jogo da Steam carrega. As bibliotecas dos runtimes entregam os dois
> sensores do vpad
> ([SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md)).
> A célula se escreve com a biblioteca que o jogo carregou, lida em
> `/proc/<pid>/maps`.

> **A palavra dela, 06/09/2026:** *"o foco do programa hoje é fazer os 4
> dualsense funcionar seja via bt ou cabo."* E, sobre quando: a bancada dos
> quatro é *"no FECHO, junto com o ensaio do som BT"*.

**Isto não é sprint de código.** É a hora dela com os quatro controles, no
FECHO das 24 horas, e é ela que decide **o que ainda está vivo** das dezoito
sprints antigas do co-op e do rádio — as que o `SPRINT_ORDER.md` §2.1 lista e
que ninguém remediu desde 27/08. Cada linha reprovada vira UMA sprint nova com
posse. **Nada se conserta durante a bancada:** um conserto no meio invalida o
resto do roteiro.

---

## 1. ANTES DE SENTAR (o coordenador, 15 min)

1. o merge em `dev` feito, os portões verdes (51 em 08/09), a suíte pelo
   `scripts/rodar-a-suite.sh` (24 partes) — 8 vermelhos conhecidos em 08/09;
2. o `install.sh --yes` rodado **na árvore dela, com a palavra dela**
   (`D-0609-INSTALL-PELO-OPUS`); o `doctor` sem FALHA — feito em 08/09;
3. o journal indo para arquivo, nunca para o terminal dela:
   `journalctl --user -u hefesto-dualsense4unix -f > ~/.local/state/hefesto-dualsense4unix/bancada-0907.log &` (anote o PID; é por ele que se mata);
4. a janela aberta pelo `.desktop`; um jogo dela aberto — o que ela escolher;
5. os quatro DualSense carregados; dois cabos USB à mão.

## 2. O ROTEIRO (60 min) — cada linha tem PASSA/REPROVA e a sprint antiga que fala disso

| # | o que se faz | o que cada controle faz | passa quando | se reprovar, quem já descreveu isto |
| --- | --- | --- | --- | --- |
| 1 | Liga dois no cabo e dois no rádio, um a um | P1: liga PRIMEIRO, pelo cabo · P2: liga SEGUNDO, pelo cabo · P3: liga TERCEIRO, pelo rádio · P4: liga POR ÚLTIMO, pelo rádio | cada um aparece na fita com P1…P4 e a cor do plástico certa em menos de 5 s | ORDEM-DE-CHEGADA-01 · IDENTIDADE-VEM-DE-CIMA-01 |
| 2 | Move cada controle dentro do jogo | P1: só o analógico esquerdo · P2: só o analógico direito · P3: só o direcional · P4: só os botões de face | o jogo vê os quatro; nenhum some nos dois primeiros minutos | COOP-QUE-NAO-DESMONTA-01 · JOGO-01 |
| 3 | Tira o P1 do cabo e põe no rádio, no meio da partida | P1: TROCA de cabo para rádio, com o jogo aberto · P2: fica no cabo, ninguém toca · P3: fica no rádio, ninguém toca · P4: fica no rádio, ninguém toca | ninguém mais cai; ele volta com o mesmo número | DUAS-CONTABILIDADES-01 · RESERVA-DO-POSTO-01 · PARTIDA-PICOTADA-01 |
| 4 | Desliga um controle do rádio, com PS longo | P1: fica ligado, no cabo · P2: fica ligado, no cabo · P3: é ESTE que desliga (PS longo) · P4: fica ligado, no rádio | os outros três seguem; a vibração dele não fica presa; a barra dos outros não muda | BORDA-DE-QUEDA-01 · DOIS-CAIRAM-DE-UMA-VEZ-01 |
| 5 | Religa o controle que foi desligado | P1: ninguém toca · P2: ninguém toca · P3: é ESTE que religa · P4: ninguém toca | volta ao mesmo assento; a luz de jogador confere | JOGADOR-3-FANTASMA-01 · LUGAR-A-MESA-01 |
| 6 | Vibração: testa em um de cada vez | P1: é ESTE que deve tremer · P2: não pode tremer · P3: não pode tremer · P4: não pode tremer | só o escolhido treme; o teto por controle vale | POSSE-POR-CONTROLE-01 · QUATRO-NA-MESA-01 |
| 7 | Gatilhos: aplica um efeito só no P3 | P1: não pode mudar · P2: não pode mudar · P3: é ESTE que recebe o efeito · P4: não pode mudar | só o P3 muda, no cabo e no rádio | as linhas da aba 03 no CSV |
| 8 | Iluminação: uma cor diferente em cada um, e depois o automático | P1: põe VERMELHO · P2: põe AZUL · P3: deixa no AUTOMÁTICO · P4: põe VERDE e depois devolve ao AUTOMÁTICO | cada um obedece, inclusive no rádio; a troca automática de perfil volta a valer | A-TRAVA-DO-LED-NAO-SOLTA-01 · LUZ-NO-RADIO-01 |
| 9 | Microfone: aperta o botão físico de cada um, um por vez | P1: cabo, aperta o botão do microfone · P2: cabo, aperta o botão do microfone · P3: rádio, aperta o botão do microfone · P4: rádio, aperta o botão do microfone | a luz inverte e o canal DAQUELE controle aparece no sistema, no cabo e no rádio | ONDA5-MIC-VIRTUAL-01 · MIC-VIRTUAL-02 · QUATRO-MICROFONES-01 |
| 10 | Bateria: anota os quatro números e volta neles aos 20 minutos | P1: cabo, anota o número agora e aos 20 min · P2: cabo, anota o número agora e aos 20 min · P3: rádio, anota o número agora e aos 20 min · P4: rádio, anota o número agora e aos 20 min | mudaram | BATERIA-PARADA-01 |
| 11 | **Som pelo rádio — O ENSAIO 1 FECHOU EM 10/09/2026; o que resta aqui é o NEGATIVO DE ROTA e o teste CEGO** | P1: cabo, é o de comparação · P2: ninguém toca · P3: rádio, é ESTE que recebe o som · P4: rádio, **não pode tocar — é o negativo** | o **`0x35`** (334 B, UM quadro Opus, 10,667 ms) toca no P3 e **NÃO** toca no P4 nem sai pelo HDMI. O `0x39` era o report errado, e nove passadas desta casa bateram nele | A-BANCADA-QUE-O-RADIO-PEDE-INDICE, ensaio 1 **FEITO** · `scripts/ensaios/o_som_pelo_035.py` |
| 12 | Fecha o jogo, fecha a janela, e reabre as duas | P1: no cabo, tem de continuar · P2: no cabo, tem de continuar · P3: no rádio, tem de continuar · P4: no rádio, tem de continuar | os quatro continuam; o perfil ativo é o mesmo | AUTOMATISMO-MORTO-01 · CONECTA-E-DESLIGA-01 |
| 13 | **Perfil vivo por controle, sem clicar em Salvar** | P1: muda a VIBRAÇÃO na aba 05 · P2: muda o GATILHO na aba 03 · P3: ninguém toca, é a testemunha · P4: muda a COR na aba 04 | cada aba mostra o que foi feito NAQUELE controle, e o outro não mudou — sem Aplicar nem Salvar em aba nenhuma | ONDA5-01-01 · ONDA5-02-01 · QUEM-E-QUEM-03 |
| 14 | Gatilhos: usa o "Todos" com três ligados, e liga o quarto depois | P1: ligado quando o "Todos" foi escrito · P2: ligado quando o "Todos" foi escrito · P3: ligado quando o "Todos" foi escrito · P4: LIGA DEPOIS, e tem de herdar | o quarto herda o que "Todos" escreveu | GATILHOS-EM-TODOS-01 |
| 15 | Lançadores: cria um lançador para o jogo aberto e abre o jogo por ele | P1: no cabo, tem de seguir no jogo · P2: no cabo, tem de seguir no jogo · P3: no rádio, tem de seguir no jogo · P4: no rádio, tem de seguir no jogo | o jogo abre, o perfil troca sozinho, os quatro seguem no jogo | a aba 07 do CSV · a01_jogar |
| 16 | Conexões: pareia um controle pela aba, quando a luz não acende | P1: ninguém toca · P2: ninguém toca · P3: ninguém toca · P4: é ESTE que se pareia pela aba | a espera pelo PS, a contagem e o Cancelar aparecem e obedecem | CONEXOES-A-LUZ-QUE-NAO-ACENDE-01 |
| 17 | Reserva do posto: desliga o P2 por 20 segundos e religa | P1: ninguém toca · P2: é ESTE que sai e volta · P3: ninguém toca · P4: ninguém toca | o assento fica reservado; ele volta P2 | RESERVA-DO-POSTO-01 |
| 18 | Modo Nativo com dois controles no jogo | P1: entra no jogo, em modo nativo · P2: entra no jogo, em modo nativo · P3: fica FORA do jogo · P4: fica FORA do jogo | os dois jogam; nenhum "jogador 2" fantasma | COOP-NA-CONEXAO-NATIVA-01 · QUATRO-NA-MESA-01 |
| 19 | Som: escolhe o alto-falante do P2 como saída de um tocador | P1: não pode tocar · P2: é ESTE que deve tocar · P3: não pode tocar · P4: não pode tocar | só o P2 toca (no cabo); a lista de som tem um nó por controle | O-ALTO-FALANTE-VIRTUAL-01 |
| 20 | Mudo no rádio: o botão do microfone do P3 | P1: não pode mudar · P2: não pode mudar · P3: é ESTE que muta, pelo rádio · P4: não pode mudar | o mudo obedece e o cartão diz | MIC-BT-DONO-01 |
| 21 | Luz no rádio: uma cor no P4 | P1: não pode mudar de cor · P2: não pode mudar de cor · P3: não pode mudar de cor · P4: é ESTE que muda, pelo rádio | obedece | LUZ-NO-RADIO-01 |

**A COLUNA "o que cada controle faz" NASCEU EM 07/09/2026**, e é dela: *"cada controle sirva para testarmos variações daquilo e o esperado. vou dar um exemplo do lightbar. Controle A, não liga, o b cor azul. o c, tá conectado no rosa, o y vai conectar azul (…) por isso dois controles dois bt e dois no cabo. Pra batermos de vez o controle que temos do hardware."* Cada linha do roteiro deixou de ser UM gesto repetido quatro vezes e passou a ser **quatro condições do mesmo experimento**, medidas lado a lado — é o que faz uma diferença entre cabo e rádio aparecer sem ninguém repetir o teste. A mesa de medição lê esta coluna.

**As linhas 13-21 são a ACEITAÇÃO DO PRODUTO** (06/09, arrumação da leva): a
definição de pronto dela — *"migrar tudo do gtk pro html, adaptando o html pra
funcionar pra 4 controles, cada perfil vivo, todas as features funcionando pra
cabo e radio, e cada aba se lembrando das configs de cada controle dentro do
perfil sem que eu precise aplicar ou salvar em cada aba e por fim tudo
funcionando (incluindo a aba de lançadores), de conexão e afins"* — dita em
gestos dela, um por sprint das ondas G-J. Cada sprint dessas constrói com dublê
e deixa AQUI a sua linha de prova (`D-0609-A-BANCADA-PROVA-NAO-BLOQUEIA`).

**E a passagem do `nao-medido`:** durante o roteiro, quem coordena anota pela
`chave` do mapa cada célula `nao-medido` que a mesa exercitou — **21 células em
12 linhas em 08/09**, por `grep -o nao-medido docs/data/mapa-controles.csv | wc -l`
(o `grep -c` conta LINHAS e mentiria; o «109» que estava aqui era de outra régua); é a P2 da
SPECS-A-PROCEDENCIA-01, e o `ensaios.csv` só ganha linha do que ela viu.

A coluna da direita é **quem já mediu**, não quem executa: o que reprovar
ganha sprint nova, escrita no molde de 05/09 e com a medição desta bancada como
§1. O item 11 é o único que não é dos quatro: entra aqui porque ela mandou
(*"deixa pras últimas etapas da 24h mas ainda nessas 24"*).


### As seis seções das 21

As 21 não são uma fila plana: elas se agrupam pelo que MEDEM, e é assim que a
bancada anda — fecha uma seção, passa à seguinte. A tabela abaixo é a fonte
disso, e **a mesa de medição a lê**; a seção de uma linha não se digita na
página. O agrupamento é o da especificação da mesa (§4), de 06/09/2026.

| seção | linhas |
| --- | --- |
| Chegada e identidade | 1 · 5 · 17 |
| Co-op e queda | 2 · 3 · 4 · 18 |
| Uma feature por controle | 6 · 7 · 8 · 9 · 20 · 21 |
| Bateria e som | 10 · 11 · 19 |
| Perfil vivo, sem Salvar | 12 · 13 · 14 |
| Lançadores e conexões | 15 · 16 |

## 3. O QUE SAI DAQUI

* `docs/process/2026-09-07-A-MESA-DE-QUATRO-o-que-a-bancada-mediu.md`: a tabela
  acima com PASSA/REPROVA por linha, a hora de cada uma, e o trecho do journal
  de cada reprova — **MAC mascarado** (octetos 4 e 5 zerados), sempre;
* para cada REPROVA, **uma sprint nova com posse**; a sprint antiga da coluna da
  direita ganha `estado: absorvida` apontando para a nova;
* para cada PASSA, a sprint antiga ganha `estado: feita` com a linha desta
  bancada como prova — é assim que as dezoito param de ser "não remedidas";
* `docs/data/ensaios.csv` ganha a linha do ensaio 1 do rádio e as células que a
  bancada mediu (o coordenador escreve; a régua `check_paridade_transporte.py`
  confere).

## 4. AS REGRAS DESTA HORA

* `--oculta` não vale aqui: **é a tela dela, com ela**. Ninguém mais abre
  janela durante a hora — nem agente, nem régua de clique.
* Saída de comando em arquivo; processo morre por PID conferido; nada de MAC
  real nem serial no relatório.
* **Quatro controles é o foco. Nenhum externo entra nesta mesa** — o Nintendo
  Pro e o 8BitDo são a EXTERNOS-01, depois.
