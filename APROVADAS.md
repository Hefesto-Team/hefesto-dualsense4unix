# As 78 propostas APROVADAS da frente A1

Ela aprovou TODAS, com estas palavras: *"ok aprovadíssimo todas. Manda ver."* (11/09/2026). Aplique cada uma como está escrita na coluna **proposta** — o texto dela é o contrato.

## A1-001 · 09 Sistema · 08 Conexões · `aba09.py:1180`

**HOJE:** *"Esta aba é sobre a **máquina**, não sobre um controle: o serviço que fala com os 2, os gamepads virtuais que ele cria para os jogos, o exame do que costuma brigar com controle nesta máquina, e os gestos raros.<br><br>Por isso a fita lá em cima está apagada — nada aqui muda de controle para controle."*

**PASSA A SER:** **"Esta aba é sobre o computador, não sobre um controle. Por isso a fita de controles está apagada aqui."**

**POR QUÊ:** A lista de quatro itens repete os quatro títulos que já estão na tela abaixo dela (pergunta 4). *"lá em cima"* é referência de lugar: muda com o layout e obriga o tradutor a olhar a tela. **289 → 101**

## A1-002 · 09 Sistema · 08 Conexões · `aba09.py:1081`

**HOJE:** *"O serviço é o Hefesto rodando em segundo plano. (…) **Reiniciar** resolve a maioria dos travamentos e não perde nenhum ajuste seu, em nenhum dos 2.<br><br>**Retomar** só acende quando o serviço está pausado. A pausa fica gravada em disco e **sobrevive a desligar o computador**: sem este botão, ele renasce pausado."*

**PASSA A SER:** **"O Hefesto rodando por trás. Sem ele, o Linux vê 2 gamepads comuns e nada mais. Parar aqui não é o mesmo que desligar o Hefesto na aba Jogar: lá ele só sai do meio do jogo."**

**POR QUÊ:** Os parágrafos de *Reiniciar* e de *Retomar* repetem, quase palavra por palavra, o `title` dos próprios botões, a três centímetros (pergunta 4). Sobra o que não está em nenhum outro lugar. **508 → 171**

## A1-003 · 09 Sistema · 08 Conexões · `aba09.py:1105`

**HOJE:** *"O que fica ligado em todos os controles (…) **Tudo ligado** — nada é limitado (…) **Bateria longa** — põe teto na vibração: 30% da força. **Eu escolho** — você decide item a item (…) É o perfil **geral**: vale para os 2 controles. Cada um pode sobrepô-lo na linha dele."*

**PASSA A SER:** **"Quanto os controles podem gastar de bateria. Vale para os 2, e cada um pode ter o seu na aba Conexões. Nenhum ajuste seu é apagado."**

**POR QUÊ:** As três linhas do meio são derivadas de `ROTULOS_DOS_PERFIS` e saem **idênticas** no `title` dos três botões logo abaixo. E *"na linha dele"* não diz onde: a aba Conexões diz. **394 → 131**

## A1-004 · 09 Sistema · 08 Conexões · `aba09.py:1113`

**HOJE:** *"(…) o **?** ao lado dela diz o que foi visto, por que importa e o que fazer.<br><br>O selo carrega **símbolo e cor** juntos, para quem não distingue verde de laranja ler o estado pelo desenho.<br><br>Os três botões à direita **já rodaram sozinhos neste exame** — é por isso que os achados falam no passado (…)"*

**PASSA A SER:** **"O que costuma brigar com os controles neste computador. Passe o mouse numa linha para ler o que foi visto e o que fazer. Os consertos já rodaram; os botões ao lado servem para repetir."**

**POR QUÊ:** **A frase promete um `?` que o produto não tem** — ver §4.1. O parágrafo do selo explica uma escolha de desenho nossa, e o último explica por que ESCREVEMOS no pretérito: é a casa falando com a casa. **493 → 184**

## A1-005 · 09 Sistema · 08 Conexões · `aba09.py:1125`

**HOJE:** *"Gestos raros. **Restaurar de fábrica** devolve o perfil de fábrica e pergunta antes (…) **Aplicar aos jogos da Steam** põe a linha de inicialização (…) por uns 20 segundos (…) O painel ao lado é a saída crua do Hefesto (…)"*

**PASSA A SER:** **"Gestos raros. O painel ao lado é a saída crua do Hefesto: copie daqui para relatar um problema."**

**POR QUÊ:** Os dois primeiros parágrafos são o `title` dos dois primeiros botões, reescritos. **443 → 95**

## A1-006 · 09 Sistema · 08 Conexões · `aba09.py:1197`

**HOJE:** rótulo **"O serviço está"**

**PASSA A SER:** **"Serviço"**

**POR QUÊ:** Rótulo + valor formam frase partida em duas colunas (*"O serviço está │ Ligado"*). É a construção que mais quebra na tradução: em muitas línguas o verbo concorda com o valor, que a tela não conhece. As outras três linhas do bloco já são rótulo puro.

## A1-007 · 09 Sistema · 08 Conexões · `aba09.py:1198`

**HOJE:** valor **"Sim, e volta pausado"**

**PASSA A SER:** **"Sim — e continua depois de reiniciar"**

**POR QUÊ:** *"volta pausado"* exige saber que *voltar* quer dizer *ligar o computador de novo*. A dica da mesma linha gasta 144 caracteres explicando isso; dito no valor, a dica encolhe.

## A1-008 · 09 Sistema · 08 Conexões · `aba09.py:1198`

**HOJE:** `title`: *"A pausa fica gravada em disco e sobrevive a desligar o computador. O botão Retomar, ao lado, é a saída — até 27/08/2026 só o terminal saía dela."*

**PASSA A SER:** **"O botão Retomar, ao lado, tira o serviço da pausa."**

**POR QUÊ:** *"até 27/08/2026 só o terminal saía dela"* é a nossa história de obra na tela dela. *"gravada em disco"* é como fazemos; o efeito já está no valor. **144 → 50**

## A1-009 · 09 Sistema · 08 Conexões · `aba09.py:1200`

**HOJE:** rótulo **"Como ele enxerga a janela"**

**PASSA A SER:** **"Ambiente gráfico"**

**POR QUÊ:** O rótulo descreve a mecânica interna, e *"ele"* não tem antecedente na linha. O valor é `Wayland · COSMIC` — um ambiente gráfico, não um modo de enxergar.

## A1-010 · 09 Sistema · 08 Conexões · `aba09.py:1200`

**HOJE:** `title` = o próprio valor (`Wayland · COSMIC`)

**PASSA A SER:** **"É por ele que o Hefesto descobre qual janela está na frente."**

**POR QUÊ:** A dica repete o valor que está ao lado (pergunta 4) e some com a única coisa que o rótulo novo não diz: por que isto importa.

## A1-011 · 09 Sistema · 08 Conexões · `aba09.py:1206`

**HOJE:** `title` do **Retomar**: *"Tira o serviço da pausa agora. Só acende com a pausa ativa — e ela sobrevive a desligar o computador."*

**PASSA A SER:** **"Tira o serviço da pausa."**

**POR QUÊ:** *"Só acende com a pausa ativa"* descreve o botão para quem já o está vendo aceso — é a única forma de ler esta dica. O resto repete a linha *Pausado*, acima. **101 → 24**

## A1-012 · 09 Sistema · 08 Conexões · `aba09.py:1207`

**HOJE:** rótulo **"Corrigir modo de execução"**

**PASSA A SER:** **"Corrigir o serviço"**

**POR QUÊ:** *"modo de execução"* é vocabulário de quem construiu. O que acontece no clique é: o serviço sai e sobe do jeito certo.

## A1-013 · 09 Sistema · 08 Conexões · `aba09.py:1207`

**HOJE:** `title`: *"Aparece no lugar do «Reiniciar o serviço» quando o serviço está de pé por fora do sistema: ali reiniciar não funciona (…)"*

**PASSA A SER:** **"O serviço está de pé por fora do sistema, e ali reiniciar não funciona. Este botão o faz sair e subir do jeito certo. Nada do que você ajustou se perde."**

**POR QUÊ:** A dica começa explicando **onde o botão aparece** — e ela só é lida quando ele já apareceu. **250 → 152**

## A1-014 · 09 Sistema · 08 Conexões · `aba09.py:1208`

**HOJE:** `title` do **Reiniciar**: *"(…) não perde nenhum ajuste seu."*

**PASSA A SER:** **"Para e liga de novo. Resolve a maioria dos travamentos, e nenhum ajuste seu se perde."**

**POR QUÊ:** *"não perde nenhum ajuste seu"* põe o programa como sujeito de uma perda; a voz passiva diz a mesma coisa sem sugerir que ele poderia perder.

## A1-015 · 09 Sistema · 08 Conexões · `aba09.py:1210`

**HOJE:** `title` do **Parar o serviço**: *"(…) Não é o interruptor Hefesto da aba Jogar, que só o tira do meio do jogo. Pergunta antes (…)"*

**PASSA A SER:** **"O Hefesto deixa de rodar e os 2 viram gamepads comuns do Linux. Pergunta antes, dizendo o que se perde."**

**POR QUÊ:** A frase do meio é o `?` da faixa, a três centímetros, dita de novo. **176 → 103**

## A1-016 · 09 Sistema · 08 Conexões · `aba09.py:1236`

**HOJE:** rótulo **"O que ele impõe"**

**PASSA A SER:** **"Limite"**

**POR QUÊ:** *Impor* é verbo de autoridade, não de limite, e *"ele"* de novo sem antecedente. O valor (`Nada é limitado`) já traz o verbo.

## A1-017 · 09 Sistema · 08 Conexões · `aba09.py:1236`

**HOJE:** `title`: *"(…) O degrau vem de **RUMBLE_POLICY_MULT**, no daemon — nenhum número escrito nesta tela."*

**PASSA A SER:** **"O que este perfil limita hoje, em todos os controles."**

**POR QUÊ:** `RUMBLE_POLICY_MULT` é identificador de código na tela dela, e a frase em volta (*"nenhum número escrito nesta tela"*) é um recado de quem desenvolve para quem desenvolve. **135 → 53**

## A1-018 · 09 Sistema · 08 Conexões · `aba09.py:1237`

**HOJE:** `title` do **Vale para**: *"É o teto geral. Cada controle pode sobrepô-lo na linha dele (…)"*

**PASSA A SER:** **"É o limite geral. Cada controle pode ter o seu na aba Conexões, e o campo de lá diz qual está valendo."**

**POR QUÊ:** *"na linha dele"* não diz onde; e *teto* sai junto com as outras três (abaixo).

## A1-019 · 09 Sistema · 08 Conexões · `aba09.py:1238`

**HOJE:** rótulo **"O teto alcança"**

**PASSA A SER:** **"Com limite"**

**POR QUÊ:** **"Teto" é metáfora de bancada.** A tradução literal não diz limite de força em língua nenhuma, e a §0 dela manda o oposto: *linguagem universal*. Com *Com limite* / *Sem limite* o par se lê numa passada.

## A1-020 · 09 Sistema · 08 Conexões · `aba09.py:1238`

**HOJE:** `title`: *"(…) Sai de **LINHAS_DO_TETO**, no produto — nenhum nome escrito nesta tela."*

**PASSA A SER:** **"Onde o limite do perfil age hoje."**

**POR QUÊ:** Mesmo caso do `RUMBLE_POLICY_MULT`. **110 → 33**

## A1-021 · 09 Sistema · 08 Conexões · `aba09.py:1239`

**HOJE:** rótulo **"Ainda sem teto"**

**PASSA A SER:** **"Sem limite"**

**POR QUÊ:** *"Ainda"* promete que um dia terá — promessa sobre trabalho nosso, na tela.

## A1-022 · 09 Sistema · 08 Conexões · `aba09.py:1239`

**HOJE:** `title`: *"Estes ficam livres do teto do perfil. Quando um ganhar limite próprio, ele sai desta lista sozinho."*

**PASSA A SER:** **"Estes ficam livres do limite do perfil."**

**POR QUÊ:** A segunda frase descreve o comportamento do nosso código, não o do aparelho. **99 → 39**

## A1-023 · 09 Sistema · 08 Conexões · `aba09.py:1287`

**HOJE:** `title` do **Refazer os consertos automáticos**: *"Sem senha e sem fechar nada: arruma o áudio (…) O exame já rodou isto — o botão refaz."*

**PASSA A SER:** **"Arruma o áudio dos 2 controles, desliga o Steam Input onde ele atrapalha e põe a linha de inicialização nos jogos. Sem senha e sem fechar nada, e com cópia de segurança."**

**POR QUÊ:** *"O exame já rodou isto — o botão refaz"* é o `?` da faixa, que já diz isso **para os três botões**. **217 → 169**

## A1-024 · 09 Sistema · 08 Conexões · `aba09.py:1288`

**HOJE:** `title` do **Refazer a fixação do Proton**: *"(…) e diz o motivo **em português** quando não dá."*

**PASSA A SER:** **"Trava de novo o Proton que você validou nos jogos escolhidos. Quando não dá, diz o motivo."**

**POR QUÊ:** **"em português" é a frase menos traduzível do produto** — num produto traduzido ela vira falsa por construção. É o caso exato que a §0 dela descreve.

## A1-025 · 09 Sistema · 08 Conexões · `aba09.py:1289`

**HOJE:** `title` do **Tirar a sobreposição Vulkan**: *"(…) **Já medimos** tirar no jogo que engasgava e o engasgo continuou — não prometo que resolve."*

**PASSA A SER:** **"Mostra, jogo por jogo, a sobreposição Vulkan pendurada por dentro, e só então tira. Guarda cópia do arquivo. Tirar pode não resolver o engasgo."**

**POR QUÊ:** O aviso honesto **fica** — é fato do mundo. O que sai é a nossa bancada (*"já medimos"*), que põe o laboratório na tela dela. **217 → 143**

## A1-026 · 09 Sistema · 08 Conexões · `aba09.py:1300`

**HOJE:** `title` do **Restaurar de fábrica**: *"(…) os seus perfis salvos continuam onde estão."*

**PASSA A SER:** **"(…) os seus perfis salvos ficam onde estão."**

**POR QUÊ:** *"continuam onde estão"* insinua movimento possível; *ficam* é o fato.

## A1-027 · 09 Sistema · 08 Conexões · `aba09.py:1301`

**HOJE:** `title` do **Aplicar aos jogos da Steam**: *"(…) em **TODOS** os jogos instalados, preservando as opções que você já tem e deixando cópia de segurança ao lado de cada arquivo (…)"*

**PASSA A SER:** **"Põe a linha de inicialização do Hefesto em todos os jogos instalados, sem perder as opções que você já tem e com cópia de segurança. Pergunta antes: precisa fechar a Steam por uns 20 segundos."**

**POR QUÊ:** *TODOS* em versal grita uma palavra que o resto da frase já garante; dois gerúndios encadeados (*preservando… deixando…*) são a construção que pior sobrevive à tradução. **224 → 192**

## A1-028 · 09 Sistema · 08 Conexões · `aba09.py:1302`

**HOJE:** rótulo **"Ver os plugins carregados"**

**PASSA A SER:** **"Ver os plugins"**

**POR QUÊ:** *"carregados"* distingue de um estado que a tela não oferece.

## A1-029 · 09 Sistema · 08 Conexões · `aba09.py:1302`

**HOJE:** `title`: *"Lista os plugins do **daemon** e relê. **Hoje só o terminal alcança isso.**"*

**PASSA A SER:** **"Lista os plugins do serviço e relê."**

**POR QUÊ:** *daemon* é palavra da casa (a aba inteira já diz **serviço** desde 31/08 — e esta linha ficou para trás). E a última frase **manda a pessoa para o terminal**, que a régua da casa proíbe. **67 → 35**

## A1-030 · 09 Sistema · 08 Conexões · `aba09.py:1303`

**HOJE:** `title` do **Ver detalhes**: *"**Joga** as últimas 80 linhas (…)"*

**PASSA A SER:** **"Põe as últimas 80 linhas do registro técnico no painel ao lado."**

**POR QUÊ:** *Jogar* é figura de linguagem; o verbo neutro é o que o tradutor acerta sem contexto.

## A1-031 · 09 Sistema · 08 Conexões · `aba09.py:994`

**HOJE:** *"(…) gatilho, luz e vibração ficam mudos **nos quatro**."*

**PASSA A SER:** **"(…) gatilho, luz e vibração ficam mudos."**

**POR QUÊ:** **O "quatro" é digitado** numa aba onde tudo o mais é contado (§4.4). Com dois controles na mesa, a frase mente. Aqui o número não acrescenta nada: a regra vale para todos.

## A1-032 · 09 Sistema · 08 Conexões · `aba09.py:1021`

**HOJE:** *"É também por isso que `/dev/input/js*` tem 6 nós para 4 aparelhos."*

**PASSA A SER:** **(sai)**

**POR QUÊ:** Caminho de kernel na tela. Está na mesma família de `uinput` e `hidraw`, que o glossário proíbe, e a frase acima já explicou o co-op inteiro. **64 → 0**

## A1-033 · 09 Sistema · 08 Conexões · `a09_sistema.py:1980`

**HOJE:** *"Não consegui falar com o **systemd**"*

**PASSA A SER:** **"Não consegui falar com o sistema."**

**POR QUÊ:** `systemd` é nome de programa do Linux, não da tela.

## A1-034 · 09 Sistema · 08 Conexões · `a09_sistema.py:2019`

**HOJE:** *"Não consegui perguntar ao systemd se o serviço liga sozinho — e sem saber o estado de agora, o interruptor não adivinha."*

**PASSA A SER:** **"Não consegui saber se o serviço liga sozinho, então o interruptor não se mexe."**

**POR QUÊ:** *"o interruptor não adivinha"* é personificação; e a explicação do porquê é duas vezes a mesma. **120 → 78**

## A1-035 · 09 Sistema · 08 Conexões · `a09_sistema.py:2359`

**HOJE:** *"Não liguei o serviço, e o **systemd** nem chegou a ser chamado: ou esta máquina não tem a **unit** instalada (o instalador nunca rodou aqui), ou já há um Hefesto vivo fora do systemd — e nesse caso subir a unit criaria um segundo."*

**PASSA A SER:** **"Não liguei o serviço. Ou esta máquina não tem o Hefesto instalado pelo sistema, ou já há um Hefesto rodando por fora — e subir outro criaria um segundo."**

**POR QUÊ:** Três ocorrências de vocabulário de administração de sistema num recado que ela lê quando **nada funcionou**. **222 → 152**

## A1-036 · 09 Sistema · 08 Conexões · `a09_sistema.py:2516`

**HOJE:** *"O serviço não está em **modo improvisado** — não há modo a corrigir agora."*

**PASSA A SER:** **"O serviço já sobe pelo sistema — não há o que corrigir."**

**POR QUÊ:** *"modo improvisado"* só existe no vocabulário desta casa; e a frase diz duas vezes *modo*.

## A1-037 · 09 Sistema · 08 Conexões · `a09_sistema.py:2521`

**HOJE:** *"O Hefesto **improvisado** não saiu quando pedi (…)"*

**PASSA A SER:** **"O Hefesto que roda por fora não saiu quando pedi (…)"**

**POR QUÊ:** Mesma palavra, mesmo motivo.

## A1-038 · 09 Sistema · 08 Conexões · `a09_sistema.py:2802`

**HOJE:** *"Vou rodar 3 **conserto(s) automático(s)**, sem pedir senha e sem fechar nada."*

**PASSA A SER:** **"Vou rodar 3 consertos automáticos, sem pedir senha e sem fechar nada."**

**POR QUÊ:** **O plural entre parênteses não existe em língua nenhuma além da nossa** e não tem como ser traduzido: em inglês são duas formas, em russo são três. O número já está na frase; a casa já tem `_plural()` (`aba08.py`) para isto.

## A1-039 · 09 Sistema · 08 Conexões · `a09_sistema.py:2811`

**HOJE:** *"Steam Input ligado em 2 **jogo(s)**: …"*

**PASSA A SER:** **"Steam Input ligado em 2 jogos: …"**

**POR QUÊ:** idem

## A1-040 · 09 Sistema · 08 Conexões · `a09_sistema.py:3007`

**HOJE:** *"4 **plugin(s) carregado(s)**"*

**PASSA A SER:** **"4 plugins carregados"**

**POR QUÊ:** idem

## A1-041 · 09 Sistema · 08 Conexões · `a09_sistema.py:2707`

**HOJE:** *"A Steam está aberta — feche-a e clique de novo. **Não travo** o Proton com a Steam viva **porque ela regrava o arquivo ao sair** e a mudança seria perdida."*

**PASSA A SER:** **"A Steam está aberta — feche-a e clique de novo. Com ela aberta a mudança seria perdida ao sair."**

**POR QUÊ:** A primeira pessoa (*"não travo"*) e a causa mecânica ocupam a linha sem mudar o que ela tem de fazer, que a primeira frase já disse. **147 → 95**

## A1-042 · 09 Sistema · 08 Conexões · `aba08.py:3398`

**HOJE:** *"Um exame da **sala** (…)<br><br>É a resposta para 'por que o controle no rádio engasga **aqui** e não engasga na casa de outra pessoa'.<br><br>O exame **não muda nada sozinho** (…)<br><br>As duas perguntas que **só você** pode responder — a altura do dongle e se tem gente entre ele e o sofá — **mudaram de lugar em 28/08**: elas moram no **Mapear Entradas** (…)"*

**PASSA A SER:** **"Um exame da sala: em que entradas os aparelhos estão, quanta energia elas dão e quem mais está falando no rádio perto do seu adaptador. Ele não muda nada sozinho: quando acha algo, aparece ao lado uma ordem de serviço dizendo o que mover para onde."**

**POR QUÊ:** O 2º parágrafo é propaganda: não diz o que fazer. O 4º **conta a nossa mudança de 28/08** — data de obra nossa na tela dela — e manda procurar perguntas noutra janela, que o botão «Mapear Entradas» já abre. **561 → 248**

## A1-043 · 09 Sistema · 08 Conexões · `aba08.py:3550`

**HOJE:** *"Uma linha por controle **ligado** (…) clicar em outro abre ele e fecha os demais (…) **A borda** é a cor do plástico (…) porque uma borda colorida seria uma cor que ninguém leu (…) **A barra de luz** (…) é a cor canônica do jogador (`core/led_control.player_slot_color`).<br><br>**O microfone segue o transporte** (…) As 16,3 turnos que ele custa no rádio são **consequência** (…)"*

**PASSA A SER:** **"Uma linha por controle ligado. A linha fechada diz o que o jogo vê como, o microfone e a bateria — as três são leitura aqui; quem as governa é outra aba. A borda e o desenho usam a cor lida do aparelho; sem leitura, ficam neutros. A barra de luz não é essa cor: é a cor do jogador."**

**POR QUÊ:** **A maior dica da aba, e a que menos ajuda.** O parágrafo do acordeão descreve o clique que a pessoa acabou de dar; `core/led_control.player_slot_color` é código-fonte na tela; e o parágrafo do microfone é o `?` do bloco do microfone, dentro do mesmo cartão, dito de novo. **1.080 → 281**

## A1-044 · 09 Sistema · 08 Conexões · `aba08.py:3641`

**HOJE:** *"**Mapear Entradas** abre o desenho (…) É lá que ficam, **desde 28/08**, as duas perguntas (…) Enquanto isso corre, o que você aperta não vaza para o jogo aberto (…) O sistema entrega o **nome cru**; quem sabe o que é, é você."*

**PASSA A SER:** **"«Mapear Entradas» numera as entradas do seu gabinete — depois disso a tela diz «Entrada 9» em vez de «porta 3-2.1». «Mapear Entrada a Entrada» é um toque por aparelho: você pluga, ele aprende. Os rádios vizinhos são tudo que fala em 2,4 GHz perto do seu adaptador; o sistema não sabe o que são, e você sabe."**

**POR QUÊ:** *"desde 28/08"* de novo. *"nome cru"* é vocabulário de quem lê `lsusb`. E *"o Hefesto para de dizer"* fala do programa quando quem diz é a tela. **586 → 307**

## A1-045 · 09 Sistema · 08 Conexões · `aba08.py:3743`

**HOJE:** *"(…) **De onde vêm os números:** os 1.600 turnos são especificação do Bluetooth Classic (625 µs cada) e **nunca foram medidas aqui**; os 260,4 e os 276,7 são o A/B **desta bancada de 25/07/2026**, com **um** controle — a soma de 4 é derivada, e **o maior ensaio de rádio desta casa foi de dois**. Os quatro moram em `integrations/radio_da_mesa.py` (…)<br><br>**O teto da vibração não mora mais aqui:** o dropdown dos três perfis mudou-se para a aba Sistema (…)"*

**PASSA A SER:** **"O rádio de cada adaptador tem 1.600 turnos de tempo para dividir entre tudo que fala nele. Cada controle come 260,4; com o microfone pelo rádio, 276,7. Hoje 1 dos 4 está no rádio: 276,7. As vagas tracejadas são os que estão no cabo — se os 4 viessem para o mesmo adaptador, seriam 553,4 das 1.600."**

**POR QUÊ:** **A maior peça de texto das duas abas, e dois terços dela é a casa falando com a casa.** O parágrafo *"De onde vêm os números"* conta a procedência das nossas medições — inclusive que não foram feitas e que o maior ensaio foi de dois — e cita um arquivo do motor. O último explica uma **mudança nossa**: quem abre a aba hoje nunca viu o dropdown que saiu. **1.061 → 297**

## A1-046 · 09 Sistema · 08 Conexões · `aba08.py:1763`

**HOJE:** rótulo do botão **"Examinar Portas"**

**PASSA A SER:** **"Examinar Entradas"**

**POR QUÊ:** **A mesma seção ensina que o Hefesto deixou de dizer *porta* e passou a dizer *Entrada*** — e o botão ao lado continua dizendo Portas. Medido no texto visível: **35 ocorrências de "entrada" contra 4 de "porta"**, e as 4 são estas duas peças e a frase que as condena.

## A1-047 · 09 Sistema · 08 Conexões · `aba08.py:3651`

**HOJE:** rótulo do link **"Banco de provas: o mapa das portas ↗"**

**PASSA A SER:** **"O mapa das entradas ↗"**

**POR QUÊ:** *"Banco de provas"* só quer dizer algo para quem construiu o produto; e *portas* de novo.

## A1-048 · 09 Sistema · 08 Conexões · `aba08.py:3651`

**HOJE:** `title` do mesmo link: *"(…) e a conta das 1.600 **fatias** por adaptador. É o desenho do motor que já roda em `integrations/arranjo_da_mesa.py`."*

**PASSA A SER:** **"Abre o mapa das entradas do seu gabinete: os arranjos possíveis, com o porquê de cada um, e a conta dos 1.600 turnos por adaptador."**

**POR QUÊ:** **"fatias" contradiz a decisão dela** (`D-A-FATIA-DO-RADIO-VIRA-TURNO`, 28/08: *"turnos funciona também"*). Medido: **9 "turnos" e 2 "fatias" na mesma aba**. E o caminho do motor está na tela. **243 → 131**

## A1-049 · 09 Sistema · 08 Conexões · `aba08.py:3701`

**HOJE:** `title` do **Examinar Portas**: *"(…) e repinta os selos, as linhas e as ordens de serviço do Check-up."*

**PASSA A SER:** **"Refaz o exame das entradas — energia e rádio — e repinta o Check-up."**

**POR QUÊ:** A lista das três peças que repintam é o nosso mapa de elementos; quem lê vê o Check-up inteiro repintar. **112 → 68**

## A1-050 · 09 Sistema · 08 Conexões · `aba08.py:2445` ×4

**HOJE:** rótulo **"Teto da vibração"**

**PASSA A SER:** **"Limite da vibração"**

**POR QUÊ:** A mesma troca da 09 — uma palavra nas duas abas.

## A1-051 · 09 Sistema · 08 Conexões · `aba08.py:2447` ×4

**HOJE:** `title`: *"O teto da vibração deste controle. **O global manda e o do controle sobrepõe** — o “?” ao lado diz qual dos dois está valendo agora."*

**PASSA A SER:** **"O limite deste controle. Ele vence o limite geral — o ? ao lado diz qual está valendo."**

**POR QUÊ:** Duas regras numa frase, e *sobrepõe* sem objeto. *global* é palavra de programador (aparece **14 vezes** no texto visível desta aba); a 09 já diz *geral*. **128 → 86, ×4**

## A1-052 · 09 Sistema · 08 Conexões · `aba08.py:2042` ×4

**HOJE:** *"**Se o microfone deste controle existe.** Desligado, nenhum programa o **enxerga** — nem o jogo, nem a chamada de voz. **Por onde** ele chega não é escolha: quem decide é **o transporte**, e a linha ao lado diz qual é."*

**PASSA A SER:** **"Liga o microfone deste controle. Desligado, nenhum programa o ouve — nem o jogo, nem a chamada. Por onde ele chega quem decide é o cabo ou o rádio; a linha ao lado diz qual."**

**POR QUÊ:** *"Se o microfone existe"* é o nome do campo interno (`mic-existe`) virado frase: o `<select>` diz Ligado/Desligado, e *existe* faz a pessoa achar que a tela pergunta se o aparelho **tem** microfone. Som se **ouve**, não se enxerga. E *transporte* é palavra da casa — a tela já diz *cabo* e *rádio*.

## A1-053 · 09 Sistema · 08 Conexões · `aba08.py:2441` ×4

**HOJE:** `title` do `<select>`: mesma primeira frase

**PASSA A SER:** **"Liga o microfone deste controle. Desligado, nenhum programa o ouve."**

**POR QUÊ:** A dica do `?` a três pixels já diz o resto. **110 → 67, ×4**

## A1-054 · 09 Sistema · 08 Conexões · `aba08.py:2057` ×4

**HOJE:** *"(…) O que ele cala é **um ajuste da máquina**, não deste controle — a linha ao lado diz qual está valendo."*

**PASSA A SER:** **"(…) O que ele cala vale para o computador todo, não só para este controle."**

**POR QUÊ:** *"um ajuste da máquina"* nomeia a coisa em vez de dizer o efeito; e a última oração manda olhar a linha ao lado, que está ao lado.

## A1-055 · 09 Sistema · 08 Conexões · `aba08.py:2064` ×4

**HOJE:** `title` da leitura: *"(…) É um ajuste da **MÁQUINA**, um só para todos os controles — o Hefesto o lê do serviço **a cada tique**."*

**PASSA A SER:** **"O que o botão físico do microfone cala. É um ajuste do computador, um só para todos os controles."**

**POR QUÊ:** **"tique" é palavra da casa**, listada no glossário como *"não aparece na tela"* — e aparece **4 vezes** nesta aba. A versal em MÁQUINA grita a palavra errada. **135 → 97, ×4**

## A1-056 · 09 Sistema · 08 Conexões · `a08_conexoes.py:2347`

**HOJE:** `title` do resumo, no rádio: *"(…) o DualSense não tem **A2DP** nem **HFP**, então o áudio vem em **Opus** dentro do **relatório HID** e o Hefesto publica uma fonte de captura do **PipeWire** com ele."*

**PASSA A SER:** **"O microfone deste controle chega pelo rádio, pela ponte do Hefesto — o DualSense não tem canal de áudio Bluetooth próprio."**

**POR QUÊ:** **Cinco siglas de protocolo numa dica de hover.** O fato que importa — *não há canal de áudio Bluetooth, então o Hefesto faz a ponte* — cabe em uma linha. **190 → 122**

## A1-057 · 09 Sistema · 08 Conexões · `a08_conexoes.py:2352`

**HOJE:** `title` do resumo, no cabo: *"(…) pela placa de áudio **USB** do próprio aparelho — o **PipeWire** a publica sozinho (**medido em 15/08/2026**)."*

**PASSA A SER:** **"O microfone deste controle chega pelo cabo, pela placa de áudio do próprio aparelho."**

**POR QUÊ:** A data da nossa medição na tela dela. **142 → 84**

## A1-058 · 09 Sistema · 08 Conexões · `a08_conexoes.py:3309` ×2

**HOJE:** `title` do trilho: *"Folgada — 276,7 das 1.600 turnos (17%). **As três palavras são do produto (`integrations/radio_da_mesa.py`) e falam só de OCUPAÇÃO:** rádio cheio tem volta, basta tirar um controle daqui."*

**PASSA A SER:** **"Folgada — 276,7 dos 1.600 turnos (17%). Rádio cheio tem volta: basta tirar um controle daqui."**

**POR QUÊ:** A frase explica **de onde vem a palavra**, não o que ela significa. É recado de manutenção. (E `das` → `dos`: *turno* é masculino.) **181 → 93, ×2**

## A1-059 · 09 Sistema · 08 Conexões · `a08_conexoes.py:3300`

**HOJE:** `title` da vaga: *"Se o Cosmic Red do Player 1 — hoje no cabo — **viesse** para este rádio (…)"*

**PASSA A SER:** **"Se o Player 1 (Cosmic Red, hoje no cabo) vier para este rádio com o microfone ligado: +276,7 turnos."**

**POR QUÊ:** Imperfeito do subjuntivo mais aposto entre travessões: duas construções que o tradutor automático erra e a leitora relê.

## A1-060 · 09 Sistema · 08 Conexões · `a08_conexoes.py:3333`

**HOJE:** legenda: *"Cada controle do cabo, **se viesse** — +276,7"*

**PASSA A SER:** **"Cada controle que vier do cabo — +276,7"**

**POR QUÊ:** idem, e a legenda é onde o olho passa mais rápido.

## A1-061 · 09 Sistema · 08 Conexões · `aba08.py:3734`

**HOJE:** subtítulo **"O rádio de cada adaptador, em turnos"**

**PASSA A SER:** **"Quanto do rádio de cada adaptador está em uso"**

**POR QUÊ:** *"em turnos"* nomeia a unidade antes de a pessoa saber o que está sendo medido. A régua já traz os números.

## A1-062 · 09 Sistema · 08 Conexões · `a08_conexoes.py:2066` ×2

**HOJE:** `title`: *"**Dê** um duplo clique para dar um nome seu a este adaptador — “Sala”, “Extra”. **É por ele que** o resto da tela passa a chamá-lo."*

**PASSA A SER:** **"Duplo clique para dar um nome a este adaptador — «Sala», «Extra». O resto da tela passa a usá-lo."**

**POR QUÊ:** *"dar um nome seu"* e *"É por ele que… chamá-lo"* são duas voltas de sintaxe onde cabe uma. **123 → 97, ×2**

## A1-063 · 09 Sistema · 08 Conexões · `aba08.py:1956` ×2

**HOJE:** `title` do vizinho por nomear: *"O sistema entrega o **nome cru** e não sabe o que é. Com o nome, o Hefesto sabe o que dá para desligar **e o que não dá**. “Outro” abre um campo (…)"*

**PASSA A SER:** **"O sistema não sabe o que é este rádio. Com o nome, o Hefesto sabe o que dá para desligar. «Outro» abre um campo para você escrever."**

**POR QUÊ:** *"nome cru"*; e *"o que dá… e o que não dá"* é a mesma informação duas vezes. **156 → 131, ×2**

## A1-064 · 09 Sistema · 08 Conexões · `aba08.py:1959` ×2

**HOJE:** `title` do vizinho nomeado: *"(…) Mudar a resposta aqui já é **corrigi-la** (…)"*

**PASSA A SER:** **"O que é este rádio. Mudar aqui já corrige. «Outro» abre um campo para você escrever o nome."**

**POR QUÊ:** Ênclise com pronome oblíquo é a forma que mais se perde fora do português escrito.

## A1-065 · 09 Sistema · 08 Conexões · `aba08.py:3700`

**HOJE:** `title` do **Mapear Entradas**: *"(…) É lá que ficam as duas perguntas que só você pode responder: a altura do dongle e se tem gente entre ele e o sofá."*

**PASSA A SER:** **"Abre o desenho do seu gabinete e numera as entradas. É lá que você responde a altura do dongle e se tem gente entre ele e o sofá."**

**POR QUÊ:** *"as duas perguntas que só você pode responder"* gasta 42 caracteres para dizer *você responde*. **167 → 129**

## A1-066 · 09 Sistema · 08 Conexões · `a08_conexoes.py:154` ×5

**HOJE:** `title` do ⊘: *"Ignora **ESTE** conselho **enquanto os cabos estiverem assim**. A recomendação fica em cinza nesta lista e **volta sozinha se o arranjo dos cabos mudar**."*

**PASSA A SER:** **"Ignora este conselho. Ele fica em cinza na lista e volta sozinho se você mudar os cabos."**

**POR QUÊ:** **A mesma regra dita duas vezes na mesma dica** — *enquanto os cabos estiverem assim* e *se o arranjo dos cabos mudar* são a mesma condição. A versal em ESTE grita. Aparece **5 vezes na tela**: 142 → 88, ×5 = **710 → 440**. **E ATENÇÃO:** o trecho final (`ORDEM_IGNORADA_VOLTA`, `a08_conexoes.py:140`) é lido também pela 5ª linha do Check-up (`aba08.py:3459`) — a troca alcança as duas.

## A1-067 · 09 Sistema · 08 Conexões · `aba08.py:2010`

**HOJE:** `title` do **A luz não acende**, no cabo: *"Só funciona com o controle no rádio: **a cura é derrubar** a conexão Bluetooth para você apertar PS. Este controle está no cabo, onde a barra de luz não depende de reconexão nenhuma."*

**PASSA A SER:** **"Só funciona com o controle no rádio. Este está no cabo, onde a barra de luz não depende de reconexão."**

**POR QUÊ:** *"a cura é"* é vocabulário desta casa; e a frase descreve o que o botão faria **noutro estado**, que a pessoa não está vendo. **178 → 101**

## A1-068 · 09 Sistema · 08 Conexões · `aba08.py:2013`

**HOJE:** `title`, no rádio: *"**Derruba** este controle do rádio (…) Enquanto ele espera o PS, **o mesmo botão vira “Cancelar”**."*

**PASSA A SER:** **"Desliga este controle do rádio. Aperte PS para ele voltar, e a barra de luz volta a obedecer."**

**POR QUÊ:** *Derrubar* é violento e ambíguo (derrubar o controle?). A segunda frase descreve o botão mudando — e quem lê a dica ainda não clicou; quando clicar, o rótulo já terá mudado sozinho. **144 → 93**

## A1-069 · 09 Sistema · 08 Conexões · `aba08.py:2073` ×4

**HOJE:** *"Deixa só este controle aberto **—** os outros fecham."*

**PASSA A SER:** **"Deixa só este controle aberto; os outros fecham."**

**POR QUÊ:** Um travessão que separa duas orações independentes lê-se como pausa longa; aqui são duas consequências do mesmo clique.

## A1-070 · 09 Sistema · 08 Conexões · `aba08.py:2434` ×4

**HOJE:** *"Fecha **—** a fita volta para “Todos”, e os 2 controles abrem juntos."*

**PASSA A SER:** **"Fecha. A fita volta para «Todos» e os 2 abrem juntos."**

**POR QUÊ:** idem, e **as aspas**: medido, a aba 08 usa `“ ”` em **15 frases** e a aba 09 usa `« »`. Duas famílias de aspas no mesmo produto. **65 → 53, ×4**

## A1-071 · 09 Sistema · 08 Conexões · `aba08.py:2424`

**HOJE:** *"A borda **deste controle** é a cor lida **do aparelho**."*

**PASSA A SER:** **"A borda é a cor lida deste aparelho."**

**POR QUÊ:** *deste controle* e *do aparelho* são o mesmo objeto, na mesma frase. **48 → 36**

## A1-072 · 09 Sistema · 08 Conexões · `a08_conexoes.py:5125`

**HOJE:** *"ignorar: esta linha é uma **CONFERÊNCIA**, não uma ordem de serviço — ela responde 'está certo?' e não há o que dispensar. Só as linhas 'Mudança recomendada' se calam, e elas aparecem depois de 'Examinar Portas'."*

**PASSA A SER:** **"Esta linha é uma conferência, não um conselho — não há o que dispensar. Só as mudanças recomendadas se calam."**

**POR QUÊ:** 212 caracteres de doutrina num recado de recusa. O prefixo `ignorar:` é o nome do gesto vazando para a tela. **208 → 109**

## A1-073 · 09 Sistema · 08 Conexões · `a08_conexoes.py:4765`

**HOJE:** *"este controle não tem **endereço fixo de doze hexa**, e sem ele não há **chave no perfil** para guardar a força só dele. Um controle sem endereço estável muda de nome a cada conexão, e a escolha cairia num aparelho diferente do que você está vendo."*

**PASSA A SER:** **"Este controle não tem endereço fixo, e sem ele a força só dele não tem onde ser guardada — a escolha cairia noutro aparelho."**

**POR QUÊ:** *"doze hexa"* descreve o formato do endereço, que o glossário mantém fora da tela (`uniq`, `MAC`); e as duas frases dizem a mesma consequência. **240 → 124**

## A1-074 · 09 Sistema · 08 Conexões · `a08_conexoes.py:4551`

**HOJE:** *"mic-existe: este controle não tem endereço de doze hexa, e sem ele não há chave no **maquina.json** para guardar a ponte"*

**PASSA A SER:** **"Este controle não tem endereço fixo, e sem ele não há onde guardar a ponte do microfone."**

**POR QUÊ:** Nome de arquivo interno na tela, e o prefixo do gesto de novo.

## A1-075 · 09 Sistema · 08 Conexões · `a08_conexoes.py:5206`

**HOJE:** *"o clique não disse qual aparelho — sem o **caminho do kernel**, dois adaptadores iguais seriam o mesmo botão."*

**PASSA A SER:** **"O clique não disse qual aparelho — dois adaptadores iguais seriam o mesmo botão."**

**POR QUÊ:** *caminho do kernel* é a nossa explicação do mecanismo; a consequência já está dita.

## A1-076 · 09 Sistema · 08 Conexões · `a08_conexoes.py:4437`

**HOJE:** *"alvo: este controle não está na lista do **daemon** — sem posição, mirar o **0** trocaria o controle debaixo da mão dela"*

**PASSA A SER:** **"Este controle não está na lista do serviço — sem ele, o alvo cairia noutro controle."**

**POR QUÊ:** *daemon*, o índice `0` e **"a mão dela"** — a frase fala da usuária na terceira pessoa, escrita para nós.

## A1-077 · 09 Sistema · 08 Conexões · `a08_conexoes.py:4886`

**HOJE:** *"renomear-adaptador: o clique não disse em qual adaptador — sem o **caminho de barramento** eu daria o seu nome ao rádio errado"*

**PASSA A SER:** **"O clique não disse em qual adaptador — o nome iria para o rádio errado."**

**POR QUÊ:** idem.

## A1-078 · 09 Sistema · 08 Conexões · `a08_conexoes.py:5372`

**HOJE:** *"este controle está no cabo, e no cabo a barra de luz não depende de reconexão nenhuma. **A cura é do rádio:** derrubar a conexão para você apertar PS."*

**PASSA A SER:** **"Este controle está no cabo, e no cabo a barra de luz não depende de reconexão."**

**POR QUÊ:** A segunda frase descreve o que aconteceria noutro estado. **146 → 78**
