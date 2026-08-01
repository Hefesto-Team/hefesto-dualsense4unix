# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Segue [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [0.6.0] — 2026-08-01

A leva do alto-falante. Ela pediu *"a ideia é concluirmos tudo que está pelo
caminho de autofalante para demais restantes"*, e as duas sprints do som
estavam paradas em PROPOSTA desde 29/07 — cinco entregas desenhadas, zero
linhas de código. Onze agentes trabalharam com escopos de arquivo disjuntos, e
três deles voltaram dizendo que a sprint estava errada.

### O alto-falante ganhou controle, e o preço está escrito na tela

O volume do controle tem **três camadas** e a janela só alcançava a do meio —
justamente a única sem leitura e com preço. O bloco "Alto-falante" era uma
barra e um rótulo que só sabia dizer `não ajustado`; a função que mandaria o
volume estava exportada na ponte e **não tinha um único chamador no produto**.

Agora ele tem controle deslizante, botão de mudo e devolução da posse. O preço
fica na dica, antes do clique: a partir do primeiro ajuste o Hefesto manda o
volume do alto-falante **e do fone** em todo report, e o DualSense não devolve
esse valor — depois disso quem manda é a janela, até `Devolver` ou desconectar
o controle.

Três armadilhas medidas viraram guardas, e cada uma tem um teste que reprova se
a guarda sair:

- **chamada sem volume toma a posse e manda ZERO.** O estado publicado vira
  `{'volume': 0, 'muted': True}` — por isso o valor é sempre explícito, em toda
  a cadeia;
- **o botão de mudo nasce insensível** enquanto não há volume conhecido. Um
  mudo como primeira escrita trancaria o alto-falante em zero, e o próprio
  botão não teria como soltá-lo, porque o desmudo restaura uma preferência que
  vale zero;
- **a devolução limpa a preferência** e recusa um mudo posterior. Sem isso, um
  `Ativar` depois do `Devolver` ressuscitaria o volume antigo e retomaria a
  posse sem ninguém pedir.

Uma correção de fato ao que estava escrito no protocolo: a posse é por **byte e
por bit**, não por bloco. Mexer no volume pela janela **não** mata o botão de
microfone do controle — são bits diferentes.

Há também `hefesto speaker` na linha de comando (`status`, `volume`, `mute`,
`unmute`, `release`), com a mesma guarda da interface: sem volume conhecido, o
mudo é recusado com a mensagem que diz o caminho.

### O selo que diz quando é o sistema que está mudo

Com o alto-falante do sistema mudo, mover o controle deslizante não produz som
nenhum — e a tela não tinha como dizer isso. São duas verdades diferentes, e a
que decide se sai som é a do PipeWire, não a do registrador do controle.

O bloco agora acende um selo `saída muda` quando a leitura do sistema diz isso,
e **nada** quando não há como saber — "não sei" nunca vira "está mudo". Com
mais de um controle no cabo o selo não acende em ninguém, de propósito: o nome
do dispositivo de áudio do DualSense não carrega identidade, e apontar o card
errado seria pior que calar.

O selo informa e nunca conserta, pela mesma disciplina do `doctor`: o
alto-falante mudo pode ser escolha de quem usa.

### O alto-falante por perfil, sem tomar posse de quem não pediu

Seção `speaker` opcional no perfil, com volume obrigatório. Perfil sem a seção
significa **sem opinião**: ativá-lo não toca no volume e, principalmente, não
toma a posse — tomar posse por um perfil que não pediu nada é o hábito que
produziu *"a config que eu deixo nunca é respeitada"*.

Duas coisas que a entrega exigiu resolver antes de existir:

- **as seções nulas saíram do arquivo salvo.** O gravador emitia
  `"mouse": null, "mic": null, "mode": null` em todo perfil, e acrescentar mais
  uma faria um binário antigo rejeitar **todos** os perfis num downgrade;
- **a trava manual ganhou a categoria de áudio**, para o autoswitch não pisar o
  ajuste feito à mão na troca de janela. O applier de perfil fala direto com o
  backend justamente para **não** armar essa trava — se armasse, o perfil
  funcionaria uma vez e nunca mais, em silêncio.

### O clique do touchpad chega ao jogo

A sprint dizia que faltava uma linha de fiação no controle virtual. Medido: o
clique **já chegava ao processo** — o leitor do controle físico tinha o byte na
mão e o descartava, porque copiava só a fatia do giroscópio.

O clique agora é entregue por borda, e não de carona na janela do movimento:
aquela janela deduplica e limita por taxa, e um controle parado engoliria a
pressionada. As duas armadilhas do desenho seguem preservadas — o cursor não
anda enquanto o dedo desliza dentro do jogo, e o nó do controle virtual segue
fora do gerenciador de entrada do desktop.

Nada precisou mudar no co-op: o leitor por jogador que o daemon já subia passou
a carregar o clique de graça, e é por isso que o jogador 2 funciona com a
janela do Hefesto fechada.

### A capa do projeto parou de mentir

O emblema de versão dizia `0.4.0` com a 0.5.0 publicada, e o de testes dizia
uma contagem que envelhecia a cada leva. A causa era a mesma: dois literais
pintados à mão que nenhum portão cobria.

O emblema de versão virou alvo do verificador. O de testes **deixou de declarar
contagem** e passou a declarar um piso — porque não existe um número: a coleta
varia com o ambiente (um módulo que precisa de biblioteca ausente contribui
zero), e um portão que comparasse com a coleta reprovaria no runner por estar
num runner. O piso só reprova quando a suíte encolhe abaixo do que a capa
promete, que é exatamente quando a capa passa a mentir.

### O portão de anonimato deixou de aprovar no escuro

O portão que audita mensagens de commit engolia o erro do `git log` e, com a
saída vazia, aprovava. **Um comando que falha era indistinguível de "nada a
auditar"** — e num push de branch nova ou force-push o intervalo já nasce
degenerado.

Agora "não havia o que auditar" e "não consegui auditar" são coisas diferentes,
e a segunda reprova. O teste extrai o script do próprio arquivo do portão e o
roda no mesmo interpretador do runner, contra um repositório de mentira.

### A documentação parou de descrever outro programa

O verificador de referências passou de uma regra para três: variáveis de
ambiente e métodos de comunicação citados na documentação agora são conferidos
contra os que **existem no código**, lidos da árvore sintática. Documentos de
processo ficam fora do escopo de propósito — são foto datada, e cobrar deles
seria cobrar o diagnóstico de conter o diagnosticado.

Uma isenção por nota datada foi necessária: sem ela o portão reprovava
justamente quem fez a correção certa, porque uma nota de verificação **precisa**
nomear a coisa morta que está corrigindo.

Junto vieram quatro contagens erradas em páginas de uso e em registros de
decisão, e uma grafia de caminho que só sobrevivia num deles.

### A aba Lightbar parou de culpar o daemon

Quando uma seção falhava ao ser aplicada, a aba dizia *"o Hefesto pode estar
desligado"* — mandando procurar o problema no lugar errado com o daemon vivo. A
informação de qual seção caiu morria na ponte, que devolvia só sim ou não.

A cura foi aditiva de propósito: o valor de sim-ou-não é contrato, e trocá-lo
por um dicionário faria qualquer chamador não migrado voltar a dizer "aplicado"
para um caso em que nada entrou.

### Menores

- A janela ensinava a ir configurar controle na Steam — instrução que deixou de
  ser verdade quando o projeto passou a resolver isso sozinho. Dois avisos de
  diagnóstico também apontavam para um botão que não existe mais com aquele
  nome, e um terceiro mandava rodar um botão que **não** instala a cura de que
  fala.
- Um verificador novo compara o vocabulário das quatro superfícies de
  interface, para a próxima renomeação não deixar três delas para trás. Ele já
  nasceu com um achado: a divergência maior não é entre a janela e o painel, é
  a **janela contra si mesma** — duas abas listam os mesmos modos em ordens
  diferentes.
- Dois identificadores de sprint citados de dentro do código-fonte, e que não
  tinham documento, ganharam um.
- A documentação do controle virtual afirmava que ele não repassa giroscópio, o
  que é falso há várias levas.

## [0.5.0] — 2026-07-31

A leva da auditoria. Ela pediu *"estude e audite o projeto, sua documentação,
suas regras e afins"*, e no meio da rodada *"veja o que ficou pelo caminho em
termos de sprints"*. Treze agentes mediram o projeto inteiro — nove auditores
particionados por área e quatro verificadores independentes com poder de
reprovar. Dos oito achados classificados como graves, o verificador confirmou
cinco e **reenquadrou três**: nenhum era invenção, eram fatos reais com moldura
errada.

### O instalador voltou a rearmar as curas de módulo

Quatro portões do `install.sh` testavam permissão de escrita (`-w`) num arquivo
que pertence ao root. Como a regra desta casa é instalar **sem** sudo, o teste
era sempre falso e os quatro blocos nunca rodavam. O efeito: o ciclo de
desinstalar e instalar desligava seis curas de conexão em silêncio, até o
próximo boot — foi o que ela sofreu em 26/07.

A correção existia pronta num commit que vivia só na linhagem descartada, e foi
portada por releitura, nunca por cherry-pick. **Provado no hardware dela:** o
ciclo real `install → uninstall → install` rodou nesta máquina, e o log agora
imprime as três linhas que antes nunca apareciam — `feature_retries`,
`ds4_short_pairing_info` e `ds4_synthetic_mac` aplicados a quente.

O mesmo ciclo mostrou a simetria fechada: as fontes, que o desinstalador nunca
removia, saem; e a configuração dela fica, que é o certo.

### A aba Status ocupa o espaço que sobrava

Pedido dela, à 1h34 da manhã, olhando a janela maximizada: *"tem muito espaço
vazio aqui, dava pra aumentar a largura do touchpad e lightbar e do microfone e
alto falante pra ocuparem os espaços laterais vazios"*.

O teto elástico já fazia o card crescer com a janela, mas os desenhos dentro
dele continuavam parados no tamanho do piso. A cura separa mínimo de natural: o
mínimo é o de sempre, e o natural cresce. Medido na tela — touchpad, lightbar,
medidor do microfone e alto-falante saíram de 180 para 360 pixels, e o vão entre
blocos caiu de 148 para 28. O piso do card não subiu um pixel e o card compacto
ficou idêntico.

O teto elástico também chegou às seis abas que faltavam, e a barra de bateria
parou de pintar 1242 pixels para dizer dois dígitos.

### A janela parou de mentir em quatro lugares

A reconciliação do rascunho ficava presa para sempre se o daemon engasgasse no
instante errado: as abas passavam a editar e o rodapé a salvar o perfil
**anterior**, sem aviso nenhum. Os dois medidores mais quentes identificavam a
aba por índice de página, contra a regra que a própria casa escreveu. O botão
"Restaurar Padrão" estava morto em qualquer instalação empacotada. E salvar
perfil comparava o nome digitado em vez da identidade em disco, então
"Navegacao" sobrescrevia "Navegação" sem a pergunta que a interface promete.

### O sinal de jogo ganhou de volta uma perna

Medido ao vivo, com o jogo dela rodando: a autoridade de exibição se apoiava numa
evidência só. O marcador do wrapper nunca é escrito, porque o jogo dela não passa
pelo wrapper; e a regra de perfil não contava, porque o probe recebia apenas a
classe da janela, enquanto os perfis dela casam por título. Agora o probe recebe
o título e o executável, e perfil casado por título volta a valer como evidência.

### A sala limpa saiu do papel

O `NOTICE` parou de mentir por omissão: os três drivers de kernel GPL-2.0
embarcados em `assets/dkms/` agora estão declarados, e o `LICENSE` e o `README`
dizem "MIT, exceto `assets/dkms`". Entrou também a guarda que **recusa** valor de
curva sem proveniência — com a mordida provada arrancando cada validador,
rodando a suíte e restaurando com hash conferido.

Os rótulos dos dezenove modos de gatilho perderam o nome em inglês entre
parênteses, por decisão dela e pela regra R2. Dois ficaram, com exceção nomeada
que não cresce nem envelhece: "Arco" e "Arma" sozinhos são ambíguos, e a palavra
é dela.

### Documentação

As receitas que quebravam na primeira colagem foram corrigidas: o primeiro
exemplo do guia de perfis ensinava um modo que o daemon rejeita, e as duas
receitas de ligar plugin do ADR-017 eram vias mortas. O AppStream anunciava esta
versão com a data e o texto da anterior, e a 0.3.0 havia sumido da série — as
duas coisas curadas, com o verificador de versão passando a conferir também a
**data**.

Onze sprints novas, o estudo da auditoria e o índice das ondas — separado por
quem precisa estar presente.


## [0.4.0] — 2026-07-30

Três levas conduzidas por agentes com arquivos particionados e um verificador
independente com poder de reprovar — e ele reprovou duas delas.

### O R1 parou de trocar de aplicativo dentro do jogo

A queixa: *"inicio o jogo e ele quando aperto r1 muda de app ao invés de
funcionar no jogo"*. `r1` é `Alt+Tab` no mapa de teclado emulado, e a emulação de
teclado **não tinha interruptor**: nascia ligada, sem persistência e sem chave na
janela, enquanto o interruptor que existia governava só o mouse.

O que abria a porta dentro da partida era a própria proteção do Steam Input:
quando um jogo da allowlist abre, o vpad é suspenso de propósito — e a exclusão
mútua do laço lia essa **ausência como permissão** para a emulação de desktop
entrar. Com o gate fechando enquanto o R1 estava segurado, o `KEY_LEFTALT` ficava
preso (18 s e 33 s medidos no journal), e quem soltava era o clique dela no
"modo jogo".

- Interruptor próprio para o teclado emulado, com flag persistida e método IPC.
- A exclusão mútua pergunta se há jogo no controle do desktop, e o predicado só
  ESTREITA o gate — nunca o alarga.
- Borda de episódio com flush: a tecla presa é solta na hora, e sair do jogo não
  produz Alt+Tab fantasma.
- Recusado com teste-cadeado: condicionar o gate ao `display_authority`, que é
  sticky e cai sozinho ~30 s depois com o jogo ainda aberto.

### O perfil passou a guardar as outras abas

Modo, máscara, co-op e "modo jogo" iam só para o estado vivo do daemon; o Salvar
reemitia a fotografia do boot por cima. Os cinco gestos das abas Início e
Emulação agora registram no rascunho — **sem aplicar**, com portão por AST
provando que nenhum escritor dispara IPC. Ligar o "modo jogo" em perfil
"vale sempre" é recusado com aviso: seria alçapão de mão única.

### O microfone voltou a gravar a voz, não o alto-falante

`pactl get-default-source` devolvia o **monitor da saída do próprio controle**. O
`doctor.sh` dava `pass` explícito para qualquer fonte com "monitor" no nome, e o
`install.sh` reaplicava a cura **refutada** a cada instalação. Medido no
hardware: o perfil analógico é `available: no` e forçá-lo dá source sem porta de
captura — 327.680 bytes de silêncio digital, pico 0; no `iec958` a mesma gravação
deu pico 4606.

### Empacotamento e portões

- O caminho de ativação do `.deb` estava **morto**: o espelho de regras udev
  parava na 81 e o helper aborta exigindo as 14. Sem grupo, sem broker, sem DKMS.
- `hefesto-hid-playstation` sobrevivia ao `apt remove` com `AUTOINSTALL=yes`.
- Spec do Fedora não compilava; flake Nix quebrava nas regras 73/74, removidas.
- Epoch nos três gerenciadores: 0.4.0 é downgrade de 4.0 e o upgrade era recusado.
- Flatpak com versão no nome do bundle e semeando os perfis default.
- `--default-branch` **não existe** no `flatpak build-bundle`: a release inteira
  teria falhado.
- O hook de acentuação checava **um** arquivo de N, em silêncio.
- Força 8 do gatilho virava 0 (empacotamento de 3 bits), com teste tautológico.
- `--no-systemd` atropelava a resposta dela; `--help` escondia flag real.
- Blocos de paridade DKMS davam falso-verde com dois greps independentes.

### Documentação

README, quickstart e flatpak mandavam clonar uma branch parada dois lançamentos
atrás. Agora apontam para a tag. Seção nova sobre o **controle no cabo USB**, com
o que muda entre cabo e rádio — inclusive o custo medido de ~35% dos relatórios
de input quando o microfone sobe por Bluetooth.


## [0.3.0] — 2026-07-28

**A leva do que desfazia o trabalho dela.** Quatorze agentes leram o repositório
inteiro e mediram a máquina em uso; o que saiu da leitura foram quatro defeitos
críticos, três deles a mesma queixa antiga vista de ângulos diferentes: *"a
config que eu deixo nunca é respeitada"*. Todos foram curados, cada um com teste
provado por arrancamento e com validação na tela — a regra `PROVA-DE-TELA-01`,
escrita em 27/07, foi aplicada pela primeira vez.

O tema desta versão é **a janela parar de afirmar o que não aconteceu**. O
rodapé dizia que aplicou com as sete seções falhando; o aviso do cadeado era o
registro do que foi pedido uma vez, não do estado; o desempate entre perfis não
era critério, era a ordem alfabética do nome do arquivo; e 737 testes de
interface passavam contra um GTK de mentira.

### Corrigido

- **O desempate entre perfis deixou de ser o alfabeto.** Em empate de
  especificidade e prioridade, o perfil que já está ativo vence — nos dois
  seletores, o da aba e o do sinal de jogo. Antes, `sorted(glob())` mais um
  `sort` estável faziam a ordem do nome do arquivo decidir qual configuração
  valia.
- **Salvar um perfil pela janela parou de rebaixá-lo.** `match` e `priority` só
  são reescritos quando ela mexeu neles, e "mexeu" conta pelo gesto, não pela
  coincidência de valor. Era o mecanismo que apagava conserto manual: um perfil
  de jogo com prioridade 100 amanhecia catch-all com prioridade 0.
- **O teto da escala de prioridade subiu de 100 para 200.** Com o catch-all da
  mantenedora em 100, não existia número escolhível pela janela que vencesse.
- **`profile.apply_draft` parou de responder sucesso incondicional.** As seções
  que falham sobem em `failed` e o rodapé nomeia o que não entrou.
- **O microfone parou de sumir da faixa** e ganhou botão que funciona — a função
  do IPC existia desde 25/07 e nunca fora ligada a widget nenhum.
- **O diagnóstico do microfone parou de dar falso positivo:** ele reprovava o
  microfone por causa do alto-falante mudo, porque o grep casava qualquer rota
  com "dualsense" no nome sem separar captura de saída.
- **O instalador passou a chamar a cura do microfone** (`doctor --fix-mic`), que
  existia e nunca era chamada.
- **O medidor do microfone por Bluetooth voltou a aparecer:** ele procurava
  fonte começando com `bluez`, e o nome publicado pelo próprio projeto é
  `hefesto_dualsense_bt_<hex>`.
- **O detector de janela pode adoecer.** A flag de saúde era um trinco de mão
  única: nenhum caminho do código a devolvia para falso, e um detector cego para
  sempre era indistinguível de um saudável. Agora ela cai e volta, o motivo da
  cegueira sobe junto, e o IPC publica a leitura crua e a idade da última
  leitura útil.
- **`IpcClient.close()` não pode mais travar a janela inteira** — o
  `wait_closed()` não tinha prazo e o executor da GUI tem um worker só.

### Adicionado

- **Aba Status reorganizada**, com os cinco defeitos que ela nomeou olhando a
  tela: microfone sempre presente com largura reservada, títulos dos analógicos
  com a mesma altura por construção, moldura por sensor, alto-falante visível e
  o vazio redistribuído. Numa segunda passada, o alto-falante desceu para junto
  do microfone, os glifos dos botões cresceram de 36 para 58 px e o card passou
  a crescer com a janela em vez de travar num número fixo.
- **Guarda de GTK real nos testes de interface.** `importorskip("gi")` aceitava
  o stub que outro arquivo de teste plantava em `sys.modules`; a guarda nova
  exige widget de verdade e torna o pulo visível. No cenário do CI, o projeto
  saiu de 24 erros de coleta e 65 falhas para zero e zero.
- **Sprints SOM-01 e JANELA-CEGA-01** documentadas — o alto-falante nunca tivera
  documento próprio neste repositório.

### Mudado

- A aba "Navegação DSX" passou a se chamar **"Navegação"**. Os modos de gatilho
  e seus parâmetros ganharam nomes em português; `start+1..8` saiu da tela.


## [0.2.0] — 2026-07-26

**Checkpoint.** Esta versão é o ponto da árvore que rodou em hardware real e foi
aprovada olhando a tela: quatro controles em co-op num jogo, numerados 1-2-3-4,
sobrevivendo a reinício do daemon. É a leva das sete queixas — sete frases ditas
em sequência, que viraram oito sprints entregues e mais quatro abertas pela
própria validação.

O tema comum das correções é sempre o mesmo, e vale escrito: **um nome para
várias coisas.** "Modo jogo" eram seis conceitos distintos; "jogador" eram cinco
números colididos em três widgets; o byte de mute do microfone tinha dois
escritores brigando; a máscara do gamepad tinha dois donos que respondiam
diferente conforme você usasse a janela ou o terminal. Nenhum desses defeitos
aparece em teste unitário — todos aparecem quando alguém usa.

**Sobre a validação:** os 5.529 testes desta versão passam, `mypy --strict` está
limpo e os quatro gates do projeto foram lidos, não suprimidos. Isso não é o
mesmo que dizer que funciona na sua mão — e o que a noite dos quatro controles
provou está separado do que ela não provou, em
`docs/research/2026-07-25-validacao-quatro-controles-e-a-numeracao-do-jogo.md`.

### Added

- **Co-op pela janela** (AUTO-01). A funcionalidade central do projeto só existia
  por linha de comando: `grep -ci coop` no arquivo da interface dava **zero**. Um
  botão "Preparar co-op (N jogadores)" encadeia modo jogo, ativação e
  renumeração. Todo o IPC já existia — era ligação, não implementação. A
  emulação de gamepad passa a nascer ligada quando há dois controles na mesa, com
  flag de recusa persistida para distinguir "nunca decidiu" de "decidiu
  desligar".
- **Número de jogador editável** (`identity.number.set`, PLAYER-01). Não existia,
  em lugar nenhum do projeto, comando que atribuísse um número a um controle — só
  o "Renumerar agora", que compacta todos e mora em outra aba. Diferente dele,
  o novo comando permuta apenas entre os controles **presentes** e não rebaixa
  quem está na gaveta.
- **Microfone com dono** (`mic.set`, MIC-USB-01), com três estados: mutar,
  desmutar e **devolver a posse** ao driver. A chave é obrigatória — omiti-la
  levanta erro em vez de virar um "desmuta" silencioso.
- **`speaker.set`**, pelo mesmo bloco de posse do report de saída. A chave só
  aparece no estado depois de uma escrita: o DualSense não devolve volume por
  report nenhum, e publicar um número antes seria inventá-lo.
- **O envelope real do DSX passa a ser aceito.** "Mods que já falam DSX funcionam
  sem adaptação" era falso: o DSX real não manda o campo `version` e serializa
  `type` como inteiro, então um pacote autêntico morria antes de qualquer
  instrução ser lida. Medido na porta 6969 do daemon vivo — antes,
  `udp.unsupported_version: 1`; depois, as seis instruções aplicadas.
- **`TriggerThreshold` implementada de verdade.** Era aceita e descartada. Não é
  efeito háptico: é corte no valor analógico entregue ao pad emulado, aplicado no
  único ponto fiel — a fronteira controle físico → gamepad virtual.
- **Modo jogo padrão** (MODO-01): quando a autoridade é de jogo e nenhum perfil
  específico opina, o modo entra **sem trocar de perfil**. O cadeado congela a
  decisão de *perfil*, não a de *modo* — essa distinção é o centro da sprint.
  Acompanha migração dos presets já instalados, porque a semeadura não
  sobrescreve arquivo existente e sem ela a cura só valeria em instalação nova.
- **Rede de segurança contra rumble preso**: teto de silêncio que zera o motor
  quando o pedido de parada se perde.
- **DKMS `hefesto-hid-playstation`**, para a contenção de canal Bluetooth quando
  dois controles pareiam com segundos de diferença, e patch do 8BitDo em modo PS4
  pelo cabo (responde 9 bytes onde o driver pede 16; dos 16 o driver usa 7).
  Ambos os interruptores nascem **desligados** — o módulo nunca muda de
  comportamento sozinho.
- **`scripts/install_fonts.sh`**: as duas fontes da identidade visual não estavam
  instaladas (0 de 797 na máquina de desenvolvimento; o `fc-match` caía em Noto
  Sans). Pacote da distro primeiro, download pinado por SHA-256 como plano B.
- **Sala limpa**: `docs/process/CLEAN-ROOM.md` com quatro regras normativas, a
  seção "O que este projeto deliberadamente NÃO incorporou" no `NOTICE`, e
  `docs/protocol/curvas-proprias.md` — que nasce vazio de propósito, porque a
  estrutura de proveniência precede o primeiro valor.
- **`docs/usage/jogos-e-mascaras.md`**, declarado fonte da verdade sobre
  compatibilidade de jogos: se outro texto do projeto divergir sobre um título, o
  outro está errado.

### Fixed

- **O jogo enxergava quatro dispositivos onde existe um controle** (JOGO-01). A
  allowlist do Steam Input desligava a deduplicação mas o gamepad virtual
  continuava de pé, então o jogo pegava um como jogador 1 e outro como jogador 2,
  e metade dos comandos ia para o controle que o jogo não lia. Agora a allowlist
  retira o vpad. Trava honesta: se a vigia que reconcilia o ambiente não puder
  ser armada, a suspensão é **abortada** com aviso — duplicado é melhor que ficar
  sem controle até reiniciar.
- **O controle sozinho na mesa nascia "jogador 2"** (NUM-01). A reserva de número
  era permanente por endereço e nada reivindicava um número vago; "Renumerar
  agora" rebaixava quem estivesse ausente — o gesto que consertava um controle
  estragava o outro. O que se persiste passa a ser **ordem de preferência**, e a
  posição exibida conta só quem está presente.
- **A escala tipográfica era código morto** (LEGIBILIDADE-01): 11 das 14 classes
  sem nenhum uso, e ~90% da tela herdava 13,33px do Pango — mexer nos degraus não
  mudaria nada na tela. Entra mecanismo de escala com dono único; dez pares de
  cor que reprovavam contraste AA foram corrigidos; o piso de área clicável
  subiu.
- **A configuração que você deixa parava de sumir** (ABAS-01 a ABAS-04). Quatro
  defeitos com uma raiz só: a aba Perfis era a única superfície que editava e
  persistia perfil sem nunca ler nem escrever o rascunho. Renomear perdia toda a
  edição da sessão sem aviso; mover o brilho um pixel limpava os ajustes por
  controle; "Parar" mentia sobre o estado parado.
- **O motor girava para sempre quando o `stop` se perdia** (RUMBLE-PRESO-01). O
  gate que ignora reports sem os bits de vibração está **certo** — sem ele, um
  report de lightbar mataria a vibração em curso. A cura não é removê-lo: é o
  teto de silêncio. A assimetria é deliberada — cortar uma vibração longa é
  aborrecimento; motor girando até a bateria acabar é desgaste de aparelho.
- **O byte de mute do microfone tinha dois escritores.** A/B no controle por
  Bluetooth: mantendo o mute a 20 Hz, nove transições em dois segundos — um
  segundo escritor desfazendo a cada ~0,44 s, a cadência exata do keepalive.
  `microphone_mute` tinha uma única ocorrência no projeto: a leitura.
- **Endereço sintetizado não é identidade.** O `usb_probe_degrade` fabrica um
  endereço a partir de (VID, PID, barramento) — zero bits do aparelho. Dois
  Nintendo-class degradados no mesmo barramento recebiam o **mesmo** endereço, e
  o segundo desaparecia calado. Endereços começando em `02` viram identidade
  volátil, e a deduplicação vira cascata.
- **O initramfs carregava o módulo velho.** O DKMS dizia "installed", o reboot
  tinha sido feito, e o 8BitDo continuava sem driver. O initramfs guardava uma
  cópia e a carregava no boot; sem os parâmetros do patch, o kernel descartava o
  `modprobe.d` **inteiro** com "unknown parameter", derrubando junto as curas que
  já funcionavam.
- **A unit do daemon nunca era instalada.** O `uninstall.sh` a removia e o
  `install.sh` nunca a instalava — quem fizesse o ciclo completo ficava sem
  daemon, sem vpad e sem gatilhos, com o instalador imprimindo o banner de
  sucesso. No mesmo commit: `./uninstall.sh --help` **desinstalava tudo**, e um
  `readonly` reatribuído encerrava o script em silêncio, fazendo perder o guard
  do Steam Input, a migração das Launch Options e o pino do Proton.
- **`led --brightness` da CLI.** Aceita 0–100 e mandava o número cru; o handler
  valida fração. `--brightness 50` era recusado e caía no fallback de hardware
  sem dizer nada; `--brightness 1` virava 100%. O teste travava exatamente o
  valor que o daemon rejeita — verde enquanto o produto não funcionava.
- **Dois gates do projeto se contradiziam.** Um exigia mascarar endereços como
  `OUI:00:00:NN`; o outro reprovava exatamente esse padrão. O desempate tinha
  sido desligar um deles, que não rodava em workflow nenhum. Um gate que ninguém
  pode satisfazer não protege nada — só ensina a ignorá-lo.
- **A hierarquia de profundidade da janela estava invertida** em relação ao
  desenho, com dois tons chapados no lugar de quatro níveis; o log da aba Sistema
  tinha fundo branco no meio do tema escuro; a aba ativa era azul, não rosa; o
  acento do sistema vazava em quatro widgets.

### Changed

- **Teto de silêncio do rumble: 6 s → 3 s**, agora por medição. Noventa minutos
  de jogo real desmentiram a premissa inicial — 17 disparos da rede de segurança,
  sete deles com valores que seriam sentidos. O teste que travava o piso em 5 s
  foi reescrito, não afrouxado: guardava um palpite, agora guarda o que a medição
  sustenta.
- **A máscara do gamepad tem dono único**, o daemon. `gamepad on` pelo terminal e
  "Jogar pelo Hefesto" pela janela entregavam máscaras **diferentes**, e a
  máscara decide se o jogo reconhece o controle.
- **Aba Status reagrupada** em três linhas, com L2/R2 e giroscópio lado a lado.
  Card de 457px para 372px contra uma faixa de 382px — o caminho de um controle
  só, o mais comum, não era aferido por teste nenhum e pedia 411px.
- **O README passou a dizer o que o projeto é.** Ele mandava clonar um
  repositório que não tem este software, e **negava uma capacidade entregue** (a
  ponte de microfone por Bluetooth, com 1.286 linhas no código). Números
  conferidos em vez de copiados. Duas páginas documentavam mecanismos que não
  existem.

### Conhecido e em aberto

Esta versão é um checkpoint honesto, não um produto fechado. O que a validação
em hardware abriu está registrado como sprint, não como promessa:

- **PLAYER-LED-01** — o número que o jogo atribui não chega ao controle físico
  nos jogadores de co-op. O mecanismo existe para o jogador 1.
- **CONTAGEM-01** — a janela exibe três contagens diferentes ao mesmo tempo
  (2, 4 e 8) com quatro controles na mesa. Cada número está certo para a pergunta
  que o próprio código faz; o erro só existe quando os três aparecem juntos.
- **IDENT-01** — o 8BitDo troca de endereço ao trocar de modo e vira dois
  controles no registro. A sprint **recusa** o palpite automático por prefixo, e
  o motivo está escrito.
- **MÁSCARA-01** — escolher, por controle, como ele aparece nos jogos.
- **MIC-BT-01** — o medidor de microfone funciona no cabo e some no Bluetooth,
  porque por rádio o DualSense não expõe placa de áudio nenhuma.
- O patch DKMS do 8BitDo em modo PS4 pelo cabo **compila e nunca foi carregado**.
- As seis sprints de sala limpa (CR-01 a CR-06) seguem abertas, e CR-02 bloqueia
  qualquer curva de gatilho própria entrar no repositório.

## [0.1.2] — RETIRADA

**Publicada em 26/07/2026 e retirada no mesmo dia. Não instale esta versão.**

A tag `v0.1.2` continua no repositório e continua apontando para os commits
originais — o histórico não foi reescrito, por decisão registrada em
`docs/process/CLEAN-ROOM.md`. O que mudou é o rótulo: esta versão não é
recomendada, e a [0.2.0](#020--2026-07-26) é o ponto que a substitui.

**Por que foi retirada.** A leva entrou de madrugada, com quinze commits e sem
nenhuma validação em hardware. Pela manhã, a janela aberta mostrou o oposto do
que fora pedido: o escopo autorizado era a faixa de baixo do card da aba Status,
e a leva mexeu na aba inteira, mandou o microfone para o rodapé quando o pedido
era colocá-lo **à direita** dos analógicos, e mudou coisas em abas que ninguém
tinha mandado tocar. Três mudanças visuais entraram **sem documento de sprint e
sem caixa de validação** — não havia como reprová-las item por item.

**O que sobrevive dela volta pela porta certa**, com caixa escrita antes do
código. A regra de método que este episódio deixou está em
`docs/process/sprints/2026-07-26-INDICE-o-que-falta.md`: mudança que a pessoa vê
na tela não entra sem caixa escrita **antes**. Um pedido que não está escrito é
um pedido que a próxima leva vai extrapolar de novo.

Correções úteis daquela leva que **não** se perderam: a simetria do instalador
(o ciclo `uninstall`+`install` desligava seis curas de módulo em silêncio) e o
conserto do `doctor --fix-mic` seguem em `main` e voltam avaliadas, uma a uma.

## [0.1.1] — 2026-07-25

Uma leva de causas-raiz. O tema comum das correções abaixo é o mesmo: premissas
que valiam **no cabo** estavam escritas como se valessem sempre, e a interface
afirmava sucesso sem verificar.

### Added

- **"Deixar tudo pronto"** e **"Este jogo não funciona"** (aba Sistema): os dois
  botões que dispensam entender a diferença entre Steam Input e opção de
  inicialização. O primeiro fecha a Steam uma vez (com permissão), aplica tudo e
  reabre; o segundo grava o AppID do jogo na allowlist e recarrega. Os quatro
  botões antigos continuam, agora rotulados como "Avançado".
- **Fechar/reabrir a Steam com consentimento** (`with_steam_closed`): jogo aberto
  continua sendo recusa — nunca pergunta, nunca fecha.
- O **cadeado do autoswitch aparece na tela**, com o que ele implica.
- Descriminador de variante para Pro Controllers que colidem em VID:PID e serial
  (`assets/84-nintendo-pro-variant.rules`, por `bcdDevice`).

### Fixed

- **O microfone voltava mudo.** São dois estados em dois arquivos e o projeto só
  conhecia um: `default-nodes` guarda quem é a fonte padrão; `default-routes`
  guarda o *mute*, e sobrevive a tudo. Ligar o mic removia os drop-ins e o
  WirePlumber restaurava fielmente o mute salvo — sem nada no log.
- **Laço eterno a ~1 Hz no daemon.** O leitor de movimento assumia que "um
  DualSense vivo emite sempre (250-765 Hz)" — verdade no cabo, falsa em
  Bluetooth, onde o firmware emudece em repouso. Um controle parado largava o
  fd, desligava o streaming e reabria pelo broker uma vez por segundo, todo
  segundo. O teto de silêncio agora vem do barramento lido no sysfs.
- **Perfis alternando sozinhos.** Três causas: o backend X11 usava o foco real
  apenas como portão e tirava o dado do `_NET_ACTIVE_WINDOW`, que fica rançoso no
  cosmic-comp (medido: as duas fontes discordando ao vivo); um perfil catch-all
  tinha autoridade sobre a janela de um jogo; e sair de um perfil custava os
  mesmos 0,5 s de entrar. Agora o dado vem da janela do foco real, catch-all não
  entra por cima de jogo, e sair exige 12 s.
- **O modo jogo não ligava sozinho.** O cadeado do autoswitch barrava até a regra
  específica do jogo; agora ele cede para ela, e continua barrando troca por
  janela comum. A allowlist do Steam Input passa a pular só a máscara — a
  supressão do perfil não disputa nada com o jogo.
- **A interface afirmava sucesso sobre um no-op.** O botão de desligar Steam Input
  executava um modo que nunca fecha a Steam, adia em silêncio e sai com sucesso —
  e a interface toastava "Steam Input desligado" de qualquer jeito. Todo modo do
  script agora termina numa linha de resultado canônica, e o toast só diz "Pronto"
  relendo o arquivo. Os tooltips que prometiam o que o botão não fazia foram
  corrigidos.
- **`--apply`/`--restore` sem proteção de jogo aberto**, chamados direto pelo
  instalador e pelo purge: `steam -shutdown` ali mataria o jogo em andamento.
- **Numeração de controle instável entre boots.** O mapa MAC→slot era descartado
  como "sessão morta" quando o `boot_id` mudava, e cada reinício renumerava por
  ordem de conexão. A âncora agora degrada (`boot_id` → `machine-id` → nenhuma) e
  quem decide o load é a versão de schema.
- **"Os dois controles aparecem como Player 1"**: havia dois espaços de numeração
  chegando à mesma lâmpada, e um alvo fixo em 1 para o primário.
- **Padrões de player LED colidiam** acima de 4: o slot 7 acendia idêntico ao 4.
  O LED azul virou bit "+5", dando nove padrões distinguíveis.
- **Segundo Pro Controller não existia para o sistema.** Um clone que se identifica
  como Nintendo falha o handshake USB e o driver aborta o probe: sem hidraw, sem
  input, sem LEDs. O comando USB era transmitido com 2 bytes num endpoint de 64 —
  o descritor do próprio controle declara 63 bytes de dados para esse report. O
  módulo DKMS ganhou três curas opcionais (padrão = comportamento original) e um
  aviso onde antes havia silêncio.

### Changed

- A **aba Status coloca os controles lado a lado** (duas colunas): empilhados,
  dois já exigiam rolagem.
- Os **rótulos dos botões do rodapé** recebiam branco de uma regra que atingia o
  label interno, anulando a cor de cada botão — o "Aplicar" ficava branco sobre
  verde. Cada um voltou à sua cor, com o Aplicar num roxo escuro legível.
- **O CI deixou de carimbar verde sobre nada**: o passo de testes engolia a falha
  com um aviso, filtrava por markers que nunca existiram e ignorava um diretório
  inexistente. Os testes de interface pulavam calados por falta de PyGObject, e
  `tests/core` não era executado por job nenhum.

## [0.1.0] — 2026-07-24

**Primeiro lançamento público, em alfa.** A numeração recomeça em 0.1.0: as
versões 0.1.0…4.0.0 anteriores foram desenvolvimento interno, e o número novo diz
o que o software é hoje — funcional no dia a dia da mantenedora, ainda não
validado em outras máquinas. O histórico daquelas versões continua na tabela ao
fim deste arquivo.

### Added

- **Sensores na aba Status**: giroscópio (três eixos em graus/s, lidos do node de
  movimento do kernel), microfone (selo ativo/mudo e medidor de nível) e touchpad
  (posição do toque). A captura de áudio só roda com a aba visível.
- **Identidade visual nova**: logo própria, paleta Drácula com um papel por cor, e
  a interface inteira alinhada a ela.
- **"Navegação DSX"**: as abas Mouse e Teclado viraram uma só, em duas colunas.
- **Perfis manuais-only** ganham representação própria no schema, em vez de
  dependerem de um critério que nunca casa.
- **Snapshot de bond do Bluetooth na borda da conexão**, além do periódico.

### Changed

- A janela abre com a altura que o conteúdo pede: nenhuma aba precisa de barra de
  rolagem. A aba Gatilhos caiu de 606 para 180px na grade de modos, e a Emulação
  de 674 para 403px.
- A aba Perfis perdeu o bloco "Detalhes técnicos" (o JSON cru).
- README de 717 para 252 linhas; o detalhe migrou para `docs/usage/`.
- O subtítulo passa a ser "Gerenciador DualSense para Linux".

### Fixed

- **Vibração que não parava.** Efeito de duração infinita só podia ser encerrado
  pelo jogo; se ele fechasse no meio, travasse ou perdesse o comando de parada, o
  motor ficava ligado. Agora há um teto de segurança, renovado a cada novo pedido
  do jogo — vibração contínua legítima não é cortada.
- **Rumble travado sem aviso.** O botão "Parar" fixa o silêncio e nada o desfazia;
  o aviso existia só dentro da aba Rumble. Agora aparece no cabeçalho, de
  qualquer aba.
- **Um controle, dois números.** A aba Início numerava pela posição na lista
  enquanto o resto usava o identificador de sessão: a mesma janela dizia
  "Controle 1" e "Sony 3" sobre o mesmo controle.
- **Comparação de perfil sem diferenciar maiúsculas**, sem alterar o dado gravado.
- 43 cores fora da paleta, escondidas em marcação dentro do código Python.

### Known issues

- O `bluetoothd` tem um defeito de corrupção de memória, **sem correção upstream
  conhecida**, que pode derrubar os pareamentos de controles da linhagem Nintendo.
  Mitigado com snapshot na borda; ver a seção de limitações do README.
- As capturas de tela da interface ainda não foram feitas.

## [4.0.0] — 2026-07-24

Auditoria por agentes de toda a interação GUI × perfis × config por-controle,
com os 4 controles ligados (2 DualSense + Pro Controller Nintendo + 8BitDo).
65 defeitos confirmados por verificação adversarial, agrupados em 24 causas-raiz
— **todas corrigidas na raiz**. Mais a frente Bluetooth da mesma maratona.

### Added

- **"Não trocar de perfil sozinho ao abrir um jogo" (FEAT-AUTOSWITCH-LOCK-01).**
  Um cadeado na aba Início: marcado, o perfil que você deixou ativo continua
  valendo ao abrir Sackboy, Mullet Mad Jack ou qualquer jogo — o Hefesto não
  troca de perfil por você. Diferente do Modo Nativo (que solta o controle) e do
  pause (que para tudo): aqui só a decisão de perfil congela; gamepad, co-op e
  rumble seguem. Persiste entre reinícios.
- **Editor simples ganhou "Jogo da Steam" (R-12).** Dá para criar um perfil que
  casa por AppID da Steam (`steam_app_<id>`) sem entrar no modo avançado — e ele
  já sugere o AppID do jogo em foco. Perfis sem regra alcançável passam a mostrar
  "Só manual (nunca ativa sozinho)" na coluna "Quando usar".

### Fixed

- **A config que você deixa passa a ser respeitada ao abrir o jogo.** Era a
  queixa central. O rascunho da GUI só carregava no boot, então após o autoswitch
  trocar de perfil as abas editavam e salvavam o perfil ERRADO; "Salvar" na aba
  Perfis descartava o que as outras abas ajustaram; o rodapé reemitia a regra do
  perfil errado; e um perfil catch-all (`vitoria`) era tratado como "o perfil do
  jogo" ao abrir o Mullet Mad Jack, apagando seus ajustes. (R-01, R-02, R-08,
  R-09, R-11.) O perfil do Sackboy agora aplica o MODO mas respeita cor/gatilho/
  rumble que você travou na mão (PERFIL-MANUAL-VENCE-01).
- **Edição controle-a-controle volta a funcionar.** O alvo de edição seguia a
  CONTAGEM de controles, não o seu gesto — com um único DualSense no kernel, a
  edição por-controle ficava desligada sem aviso, e a queda de um controle
  apagava o override dos outros. Agora segue o gesto. "Apagar" da Lightbar passou
  a mirar o controle certo, e "Aplicar" deixou de dizer "aplicado" quando não
  aplicou nada. (R-16, R-17, R-18.)
- **Player LEDs 1-2-3-4 sem duplicar.** Duas autoridades escreviam o mesmo LED
  com números diferentes; a saída do backend foi reorganizada em camadas com dono
  (jogo > co-op > seu override > automático > padrão), o co-op parou de brigar
  com o reasserto periódico, e a numeração dos externos parou de colidir com a do
  co-op. (R-13, R-14, R-15, R-20.)
- **O modo do perfil deixa de ser descartado em silêncio.** Mexer na máscara e
  abrir o jogo em menos de 30 s não perde mais o modo do perfil (ele é reaplicado
  quando o lock manual expira); o perfil não desliga mais o vpad no meio da
  partida; e a máscara que você escolheu para de ser reescrita no disco pelo
  perfil do jogo. (R-03, R-05, R-07.)
- **O botão "Desligar" dos gatilhos LIBERA a trava** em vez de re-armá-la — antes
  o botão de "voltar ao normal" pausava a troca automática sem avisar. (R-19.)
- **Renomear perfil não apaga mais outro sem querer.** A identidade do arquivo é
  o slug: salvar "Navegacao" deixou de sobrescrever "Navegação" em silêncio, e o
  rename migra de verdade. (R-10.)
- **Sem travadas de segundos durante o jogo.** A leitura de calibração do co-op
  saiu da thread do laço de input — não congela mais os 4 jogadores por segundos.
  (R-22.)

### Fixed — Bluetooth

- **8BitDo por Bluetooth voltou a conectar (BT-SNIFF-PER-OUI-01).** O modo ativo
  "sem sniff" que estabiliza o Pro Controller genuíno estava sendo aplicado ao
  ADAPTADOR inteiro e quebrava a conexão do 8BitDo (clone) — regressão medida por
  A/B ao vivo. Agora o "sem sniff" é aplicado só ao Pro Controller genuíno; o
  8BitDo pega o sniff que precisa para conectar. (Por BT ele conecta mas ainda
  cai sob carga — o cabo segue sendo a via confiável.)
- **Controle "Conectado" mas sem responder curado (SDP-CACHE-01).** Um DualSense
  podia aparecer conectado no sistema e não gerar controle nenhum, por causa de
  um registro de serviço Bluetooth truncado. O snapshot de bonds passou a
  preservar esse registro, o watchdog aprende a recuperá-lo, e o doctor distingue
  "só a direção da conexão" (curável) de "o controle travou" (reset de hardware).
- **O uninstall volta a desfazer o modo ativo Bluetooth.** O comando de reversão
  usava a sintaxe errada (`hciconfig lp` exige vírgula, não espaço) e virava um
  no-op silencioso — quem desinstalava ficava com o adaptador alterado.
- **Watchdog Bluetooth: o `Trusted` deixa de depender de conexão
  (WATCHDOG-TRUST-DEADLOCK-01).** Um controle sem trust é recusado ao reconectar,
  e sem reconectar o watchdog nunca o alcançava — um deadlock. Agora o trust é
  reaplicado a todo controle com bond, conectado ou não.

### Added

- **Controles externos no seletor do topo (8BIT-02).** Os controles que NÃO são
  DualSense (8BitDo/Nintendo em modo Switch, Xbox, etc.) agora aparecem como
  botões no seletor do topo (ao lado de "Todos | 1·BT | 2·BT"), com rótulo
  amigável ("Nintendo · cabo"). Clicar num deles abre uma ficha secreta
  read-only SÓ daquele controle — tipo, como conectou, driver do Linux — deixando
  claro que **ele funciona (pelo Linux + Steam) e o Hefesto não mexe nele**
  (nada de cor/gatilho/co-op virtual: exclusivo do DualSense). Quando é um
  controle em modo Switch por Bluetooth, a ficha avisa que ele pode travar
  sozinho — é o driver `hid-nintendo` do kernel desistindo, não o Hefesto, e a
  saída estável é o cabo. Escopo enxuto de propósito ("só ver como aparecem, não
  uma super central"): superfície 100% read-only, sem o Hefesto adotá-los.
- **Numeração de co-op sincronizada entre a GUI e o LED do controle externo
  (8BIT-02).** No co-op MISTO (DualSense + Nintendo/8BitDo), o daemon continua a
  contagem dos DualSense nos externos — com 2 DualSense (jogadores 1 e 2), o 1º
  externo é o **3** e o 2º é o **4** — e ESCREVE esse número no LED de player do
  próprio controle (os LEDs verdes do modo Switch), para o número da interface
  bater com o LED físico. Só LED, nunca input. A nova regra udev
  `79-external-controller-leds` (instalada por padrão, `< 73` não se aplica: LED
  é inócuo) torna esses nós graváveis pelo daemon sem root; sem ela a escrita
  falha em silêncio e o número cai no default do kernel, sem regressão de input.
- **Orientação de "como o jogo enxerga" o controle Nintendo/8BitDo (8BIT-02).**
  A ficha do controle mostra o modo atual (Nintendo/Switch ou Xbox/X-input) e
  explica, sem jargão, a troca de HARDWARE (combo ao ligar): o modo **Xbox
  (X-input)** é a raiz da estabilidade — o jogo vê um Xbox 360 de verdade (driver
  `xpad`) e foge do driver que morre em Bluetooth; o modo **Switch** dá
  giroscópio mas trava por BT. É orientação honesta, não uma promessa de cura.

## [3.14.0] — 2026-07-17

### Fixed

- **A cor automática por controle agora aparece sozinha no boot e ao acordar o
  controle (COR-WAKE-01).** Ela só surgia depois de uma ativação manual de
  perfil; com os DualSense dormindo em Bluetooth no boot (ou num resume que
  reseta o LED da classe do kernel), os dois ficavam no MESMO azul-fraco padrão.
  O daemon passa a reconciliar a cor resolvida por-controle em TODA
  reconexão/hotplug (validado ao vivo: azul no 1, vermelho no 2, sozinhos).
- **Salvar um perfil de programa específico como "Sempre" agora pede
  confirmação (COR-A).** Desligar o "Modo avançado" e Salvar convertia o alvo
  (janela/processo) em "Sempre" em silêncio — o perfil que valia só num jogo
  passava a valer para tudo, com o toast dizendo "Perfil salvo".
- **Aba Teclado inteira em português de gente (KBD-01).** Os tokens crus do
  kernel (`KEY_LEFTALT`, `__OPEN_OSK__`, ids `l1`/`create`) viraram nomes
  reconhecíveis ("Alt + Tab", "Abrir teclado na tela", "L1"), com a edição
  convertida de amigável para cru na fronteira.
- **Jargão que vazava para quem usa, em toda a GUI.** "daemon offline?" virou
  "ligue na aba Sistema"; a aba Rumble parou de mandar clicar um botão
  inexistente ("Devolver ao jogo"); a aba Emulação mostra "9 controles
  detectados pelo sistema" no lugar dos caminhos crus `/dev/input/js*`; toasts
  pararam de despejar tuplas RGB, exceções Python cruas e comandos de terminal
  (`pip`, `modprobe`, `install_udev.sh`, "storm -71"); "Daemon" virou "Hefesto"
  na aba Status; a prévia da Lightbar mostra a cor REAL do controle (não a
  manual) quando o automático está ligado.
- **README**: o passo de desduplicação parou de mandar colar a variável
  `SDL_GAMECONTROLLER_IGNORE_DEVICES` na Steam — o wrapper `hefesto-launch`
  (instalado por padrão) cuida disso; o botão vira só o último recurso manual.
- **Numeração de controle consistente** entre os cards, o seletor de alvo e o
  applet: tudo pelo número de SESSÃO do controle (`player_slot`), nunca pela
  posição na lista — o mesmo controle deixou de aparecer como "1" num lugar e
  "2" noutro.

Base da auditoria: `docs/process/sprints/2026-07-17-AUDITORIA-onda-validacao-e-correcoes.md`
(28 agentes, verificação adversarial; 6 HIGH + o batch de jargão corrigidos).

### Added

- **Cores automáticas por controle (COR-01/COR-03), estilo PS5.** Cada DualSense
  conectado ganha sozinho uma cor de lightbar (1=azul, 2=vermelho, 3=verde,
  4=rosa, 5+=branco) e o player-LED com o **número do controle**, pela ordem de
  conexão da sessão — replug recupera o mesmo número; sessão nova renumera do 1.
  A precedência é POR CAMPO: cor explícita por-controle > automática > global do
  perfil (o co-op, quando ativo, continua vencendo por cima). Toggle "Cores
  automáticas por controle" na aba Lightbar (`leds.auto_player_colors`, ligado
  por padrão) + botões "Voltar (todos) ao automático".
- **Aba Status em cards por controle (STATUS-01/02/03 + BT-03).** Um card por
  DualSense com swatch da cor real do lightbar, bateria própria, inputs ao vivo
  (sticks/gatilhos/botões) **tintados na cor do próprio controle** com
  contraste garantido ≥ 3.0 (matiz preservado; cor escura é clareada — o
  swatch mostra a cor crua), rótulo honesto da fonte da cor ("apagada" só
  quando fomos nós que apagamos; "cor desconhecida" quando não dá para saber)
  e aviso de emulação degradada por controle (backend uinput + motivo).
- **Lembrete do wrapper 1x por jogo (DEDUP-05).** Com a emulação ativa e um
  jogo Steam em foco que ainda não abre pelo `hefesto-launch`, a GUI mostra UM
  diálogo (nunca popover) com a linha para copiar; "Não perguntar para este
  jogo" persiste a dispensa. Sem o wrapper o pior caso é controle DUPLICADO —
  nunca zero controles.
- **doctor.sh**: as 7 regras udev canônicas (70/71-uhid/71-uinput/72/76/77/78)
  agora são conferidas (antes 4; a 75 de áudio segue opt-in); probe read-only
  da gravabilidade do nó de LED (a rota da cor por-controle em BT); e o
  diagnóstico da cascata de morte do 8BitDo/hid-nintendo por Bluetooth
  (informativo, zero falso-positivo — a linha isolada não dispara).
- **Inventário read-only de gamepads externos** no IPC `controller.list`
  (opt-in): nome, VID:PID, barramento, driver do kernel — o 8BitDo e afins
  aparecem com identidade honesta, sem o hefesto adotá-los.
- **Guia**: `docs/usage/troubleshooting-8bitdo.md` — modos do SN30 Pro, o que
  cada um expõe, a assinatura de morte por BT e os comandos de diagnóstico.

### Changed

- **Mudança visível ao atualizar**: perfis existentes com cor global salva
  passam a exibir **cores automáticas por controle** (o novo
  `auto_player_colors` nasce ligado — é o comportamento pedido, mas muda o que
  se vê sem ação da usuária). Reaplicar uma cor manualmente (por controle ou
  em "Todos", que desliga o automático com aviso) volta a valer como antes.
- **Downgrade quebra para perfis re-salvos**: `LedsConfig` é `extra="forbid"` —
  qualquer perfil salvo pela versão nova (ganha `auto_player_colors`; e
  `controllers` quando usado) fica inválido em daemon antigo (warning
  `profile_invalid`, some da lista). Aceito porque daemon+GUI shippam juntos.
- **O player-LED fora do co-op mostra o número do CONTROLE (slot de sessão),
  não o número de jogador que o jogo atribui** — os dois podem divergir em
  borda de replug do primário (jogos numeram pela ordem de enumeração do SDL).
  Com o co-op ativo, o LED volta a mostrar o número de JOGADOR do co-op.
- **Perfis por controle (PERFIL-06): revert do co-op resolve POR CONTROLE +
  contrato de downgrade.** Desligar o co-op (ou um jogador sair) devolve cada
  controle ao padrão de player-LED RESOLVIDO para ele — o override do mapa
  `controllers` do perfil onde existe, o padrão global onde não — em vez de
  re-emitir o broadcast global por cima do override; o caminho novo também
  deixou de apagar os overrides por-uniq registrados no backend (o revert
  antigo, por `set_player_leds` broadcast, limpava o campo de todos).
  **Downgrade**: como a serialização OMITE o campo `controllers` quando
  ausente/vazio (PERFIL-02), só perfis que USAM `controllers` são rejeitados
  por um binário antigo (`extra="forbid"` → warning `profile_invalid`, o
  perfil some da lista até o campo ser removido do JSON) — aceito porque
  daemon+GUI shippam juntos. Sem a omissão, TODO perfil salvo pelo binário
  novo seria rejeitado no downgrade — por isso ela é requisito de
  compatibilidade, não estética.

## [3.13.3] — 2026-07-14

Três percalços do instalador flagrados num ciclo `./uninstall.sh` seguido de
`./install.sh` rodado não-interativo.

### Fixed

- **`install.sh` agora cacheia a credencial `sudo` UMA vez no início**
  (BUG-INSTALL-SUDO-NONINTERACTIVE-01). Vários sub-passos usam `sudo`
  internamente (regras udev, cura persistente do storm via
  `install_snd_quirk.sh`, e o `just install` do applet COSMIC). Sem cachear a
  credencial, cada um tentava pedir a senha por conta própria e, sem TTY
  (install rodado não-interativo), FALHAVA — e o passo seguia como se tivesse
  dado certo: o `/etc/modprobe.d/hefesto-dualsense-storm.conf` não era gravado
  (a cura runtime pegava, a persistente sumia no reboot) e o applet abortava com
  "Recipe `install` failed". Agora o install prima a credencial no começo
  (uma senha), mantém viva durante a build longa do applet (>10 min) e o step da
  cura tem post-check explícito: se o `.conf` não existir ao final, AVISA em vez
  de fingir sucesso.
- **Applet COSMIC passa a ser instalado por padrão** em sessões COSMIC
  (BUG-INSTALL-APPLET-OPT-IN-SKIPPED-01). Antes era opt-in
  (`--enable-cosmic-applet`), então um `./install.sh` comum PULAVA o applet — e
  quem já o tinha o perdia num ciclo desinstala+reinstala. Agora instala quando
  faz sentido (em COSMIC, ou se já está instalado, ou se forçado pela flag), com
  opt-out via `--no-cosmic-applet`. A build exige `cargo`+`just`; se ausentes, o
  install NÃO falha — só avisa como instalar o Rust.
- **`uninstall.sh` também cacheia o `sudo` uma vez no início**
  (BUG-UNINSTALL-SUDO-NONINTERACTIVE-01), simétrico ao install. Sem isso, num
  ciclo não-interativo o bloco de udev abortava com "sudo recusado/sem TTY" e o
  `sudo rm` do applet era mascarado por `|| true` — a cura `.conf` e o binário do
  applet sobreviviam ao wipe. Agora a credencial é primada e mantida viva, então
  a desinstalação remove tudo de fato.
- **Detecção de "Steam rodando" não confunde mais com o `earlyoom`**
  (BUG-STEAM-DETECT-EARLYOOM-FALSE-POSITIVE-01). O `disable_steam_input.sh` casava
  o `steamwebhelper` pela cmdline inteira (`pgrep -f`), então o `earlyoom` — que
  lista `steam|steamwebhelper` no seu regex `--avoid` — dava falso-positivo: o
  desligar do Steam Input travava com "Steam ainda rodando" e o `pkill -f` de
  fallback chegava a mirar o próprio `earlyoom`. Agora o `steamwebhelper` é casado
  por nome EXATO de processo (`pgrep -x`/`pkill -x`).

### Changed

- **O `venv` do formato nativo já vem com o extra `[dev]`** (ruff/mypy/pytest)
  por PADRÃO (BUG-INSTALL-VENV-NO-DEV-01). Antes o `install.sh` recriava o
  `venv` só com o essencial, e o gate pré-release (`ruff`, `mypy`) não rodava
  local sem um `pip install -e ".[dev]"` manual. Nova flag `--no-dev` pula os
  dev tools para CI/máquina enxuta. Se a instalação com `[dev]` falhar (ex.:
  offline), cai para só o essencial e avisa, em vez de abortar o install.

## [3.13.2] — 2026-07-14

### Removed

- **Launcher standalone "DualSense Fix (dsx)" e o `dsx.sh`** — eram baseados na
  teoria de hardware (I/O die / power) que foi REFUTADA; a causa do storm é o
  áudio USB e a cura de raiz (quirk do `snd_usb_audio`) já está integrada e
  instalada por padrão. Removidos: o `.desktop` do menu, o `dsx.sh`, o
  empacotamento no `.deb`, o botão "Reaplicar tudo (terminal)" da GUI e a flag
  `doctor --reapply-all` (que o invocava). O que fica: o cartão anti-storm
  ("Reaplicar fixes seguros" + cura de raiz) e o watcher de auto-recuperação
  `hefesto-dsx-recover` (coisa separada). O `uninstall.sh` limpa o launcher
  residual.

### Fixed

- **Applet COSMIC: marca visual do item ativo** — o modo/máscara selecionado no
  popover não recebia marcador (eram dois espaços iguais, glifo comido numa
  edição). Agora o ativo mostra "> " e o co-op um "[x]/[ ]".

## [3.13.1] — 2026-07-14

Correções da auditoria pré-release (bugs de UI e paridade de empacotamento) que
não bloqueavam o rumble/storm, mas quebravam fluxos secundários ou pacotes.

### Fixed

- **Trocar a máscara não congela mais o input** (M4): o teardown dos controles de
  co-op fechava o fd só depois de um `join` de 2s por jogador (a thread ficava
  parada em `select()`); trocar dualsensexbox travava o P1 por 2-6s. Agora o fd
  é fechado na hora, desbloqueando a leitura.
- **Botão PS volta a abrir a Steam no desktop** (M5): o botão PS era suprimido
  pela mera existência do gamepad virtual, matando "abrir a Steam" no desktop com
  a Steam fechada. Agora só é suprimido quando a Steam já está rodando (em jogo).
- **Aba Rumble: o teste de 500 ms é cancelável** (M6): clicar Parar/Aplicar/
  Devolver dentro da janela do teste não é mais desfeito pelo timer pendente.
- **Cartão anti-storm reavaliado ao abrir a aba e no "Atualizar"** (M7): o
  diagnóstico não fica mais preso ao estado do bootstrap.
- **"Reaplicar tudo (terminal)" abre mesmo sem o `.desktop`** (M8): confere o
  código de saída do `gtk-launch` e cai num emulador de terminal.
- **"Reaplicar fixes seguros" dá retorno final** (M9): a barra não fica mais em
  "Reaplicando..." para sempre.
- **Empacotamento**: os scripts que a GUI/doctor executam vão no `.deb` (M10); a
  cura de raiz é empacotada no path VIVO `/usr/lib/modprobe.d` também no `.deb` e
  no PKGBUILD (M11/M13); o PKGBUILD usa o conjunto canônico de regras udev (sem
  as 73/74 que alimentavam o storm) e as units systemd corrigidas (M13/M14).

### Added

- **Indicador de estado da vibração na aba Rumble** (Feature #4): mostra se a
  vibração está "com o jogo" ou "fixa" e quantas vezes o jogo pediu vibração
  (`rumble_ff`) — antes essa observabilidade não tinha consumidor.

### Changed

- O gate de versão (`check_version_consistency.py`) agora cobre PKGBUILD, spec,
  nix e debian/control (M12) — Arch/Fedora/Nix estavam presos em 3.4.0, agora
  todos em sincronia. O gate de paridade cobre `assets/modprobe/*.conf` (M11).

## [3.13.0] — 2026-07-14

### Added

- **Cura de raiz do travamento do USB (storm -71)** — instalada **por padrão**. O
  storm foi provado como o `snd-usb-audio` sondando o mixer UAC do DualSense e
  saturando o canal de controle (EP0) a cada re-enumeração, colidindo com o
  `usbhid` (`can't add hid device: -71`) num laço de desconexão. O ajuste
  (`quirk_flags=054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m`, em
  `/etc/modprobe.d/hefesto-dualsense-storm.conf`) torna a sondagem tolerante e
  espaçada — **preservando o microfone e o fone do controle**, ao contrário da
  regra 75 (áudio-off), que segue opt-in. Validado em gameplay: storm ZERO numa
  sessão que antes derrubava o controle em minutos. `scripts/install_snd_quirk.sh`
  (`--status`/`--remove`/`--runtime`); step 3c do `install.sh` (`--no-snd-quirk`
  pula); remoção simétrica no `uninstall.sh`.
- **Vibração dos jogos de ponta a ponta no modo "Jogar pelo Hefesto"** — com a
  máscara **Xbox 360**. Causa-raiz provada: com a máscara DualSense o SDL/HIDAPI
  do jogo adota o controle **físico** via `/dev/hidraw` e **ignora** o gamepad
  virtual (mesmo VID/PID, sem hidraw) — o force-feedback nunca chegava ao nosso
  pipeline. Perfis de jogo migrados para `xbox`.
- **Botão "Copiar opções p/ jogos"** (aba Daemon → cartão Anti-storm): copia as
  Opções de Inicialização da Steam que acabam com o **controle duplicado** no jogo
  (`SDL_JOYSTICK_HIDAPI=0 SDL_GAMECONTROLLER_IGNORE_DEVICES=0x054c/0x0ce6 %command%`)
  mantendo a vibração.
- **Diagnóstico da cura no doctor/GUI**: `check_snd_quirk` (a cura está ativa?) e
  `check_snd_audio_healthy` (mic+fone do controle presentes?).
- **Contador de force-feedback por gamepad virtual** no `daemon.state_full`
  (`rumble_ff.plays`) + estado `rumble_passthrough`/`rumble_active` — dá para ver
  se o jogo está mesmo pedindo vibração.

### Fixed

- **Perfil devolve a vibração ao jogo** (`rumble.passthrough`): testar os motores
  na GUI fixava o rumble e o perfil do jogo **não soltava** — o force-feedback do
  jogo era ignorado mesmo com a máscara certa. Agora ativar um perfil com
  `passthrough` (o padrão) libera o rumble fixado.
- **Máscara propaga aos controles de co-op**: trocar dualsensexbox recriava só o
  gamepad do P1; os jogadores 2+ ficavam na máscara antiga (vibração morta e
  prompts divergentes).
- **Co-op não duplica o input no boot**: com o MAC do primário ainda não resolvido
  (~5 s), o co-op criava um jogador secundário para o **próprio** controle do P1.
- **Modo Nativo não pisa mais nos LEDs do jogo**: a rota sysfs de lightbar/
  player-LED ignorava o mute de output; agora respeita e re-aplica o perfil ao sair.
- **Botão PS não rouba mais o foco para a Steam** durante o jogo (com o gamepad
  virtual ativo, o PS já vai cru para o jogo).
- **Cursor não salta ao sair do Modo Nativo**: o movimento do touchpad acumulado
  enquanto o input está congelado agora é descartado.
- **Aba Rumble**: terminar o teste dos motores devolve a vibração ao jogo (antes
  deixava o rumble travado em silêncio); os botões explicam o que fazem.

### Docs

- README: seção **"Jogar sem travar"** (travamento do USB, vibração e controle
  duplicado — a receita completa) e **"Limitações por modo"** (o que só o Modo
  Nativo entrega — gatilhos adaptativos, giroscópio, touchpad — e por quê).
- Auditoria da matriz capacidade × modo e o design/plano anti-storm em
  `docs/process/sprints/2026-07-14-*`.

## [3.12.0] — 2026-07-13

### Added

- **Multi-controle de verdade (até 4 jogadores locais)**: identidade de
  controle por MAC de ponta a ponta (backend hidapi, evdev e co-op falam a
  mesma língua — FEAT-DSX-CONTROLLER-IDENTITY-01), acabando com a duplicação
  de input ao plugar um 3º controle; co-op local cria um gamepad virtual POR
  jogador sem cap de jogadores; **cada controle mostra o player LED do seu
  jogador** (P1..P4, via sysfs por MAC — FEAT-COOP-PLAYER-LED-01), com
  presets Player 3/Player 4 novos na aba Lightbar.
- **Co-op é o padrão** (FEAT-COOP-DEFAULT-ON-01): com 2+ controles em modo
  jogo, "cada controle = um jogador" já vem ligado; o que se persiste é o
  opt-out. Voltar ao desktop não apaga a preferência.
- **Modo por perfil** (FEAT-PROFILE-MODE-01): perfis ganham a seção `mode`
  (`desktop` | `gamepad` + máscara + co-op | `native`) com lock manual de
  30 s e reversão ao trocar para perfil "sem opinião". Presets novos:
  `sackboy_nativo` (Jogo direto/Sony ao focar o jogo) e `coop_local`.
  Editor de Perfis da GUI ganhou o seletor de modo.
- **Política de rumble por perfil** (FEAT-RUMBLE-POLICY-PROFILE-01):
  `rumble.policy`/`custom_mult` persistem no perfil, com applier próprio
  (mesma semântica de lock/reversão do modo) — "Salvar Perfil" não descarta
  mais a política.
- **Aba Início** (FEAT-GUI-HOME-TAB-01): primeira aba com o comutador
  "O que o controle faz agora" (Controlar o PC / Jogar pelo Hefesto / Jogar
  direto (Sony)), co-op, máscara, um card por controle (transporte, bateria,
  fim do MAC) e "Desligar Hefesto (voltar ao Linux puro)" que NÃO religa
  sozinho ao reabrir a GUI.
- **Applet COSMIC com os modos** : seção "O que o controle faz" no popover
  (3 modos + cada-controle-é-um-jogador + máscara DualSense/Xbox), linha de
  modo no status com origem "(pelo perfil)".
- **Hotplug rápido no backend** (FEAT-BACKEND-HOTPLUG-FAST-01): controle
  plugado com o daemon vivo entra em ~2 s (watch de /dev/input barato no
  reconnect_loop; fallback de 30 s mantido).
- **Diagnóstico do detector de janela** (FEAT-WINDOW-DETECT-DIAG-01):
  `state_full` expõe `window_detect_backend/healthy/last_class` (dá para
  capturar o wm_class de um jogo sem journal) e o `doctor.sh` ganhou a seção
  "detector de janela" com veredito OK/DEGRADADO/CEGO (no COSMIC/Wayland
  nativo: DEGRADADO — jogos XWayland/Proton seguem detectáveis via Xlib).
- **Semeadura runtime dos presets** (FIX-PACKAGING-SEED-PARITY-01): a
  primeira carga de perfis semeia os presets default (copy-if-absent com
  marker compartilhado com o install_profiles.sh) — usuários de `.deb`/
  AppImage passam a receber os perfis novos sem passo manual.
- Regra udev 78: Motion Sensors do DualSense deixam de enumerar como
  joystick (jogos param de ver 3 "joysticks" por controle).

### Changed

- Performance multi-controle: varredura de /dev/input saiu do caminho quente
  (InputDirWatch), forward analógico só emite eixo que mudou, `os.nice(5)`
  (env `HEFESTO_DUALSENSE4UNIX_NICE`), throttle do report HID adaptativo ao
  nº de controles (cap 32 ms) e write OUT com dirty-flag + keepalive 0,5 s.
- `state_full.controllers` agora traz `uniq` (MAC) e `battery_pct` por
  controle.
- Terminologia dos modos sem jargão (UX-MODE-TERMS-01): "Desktop/Jogo
  (gamepad virtual)/Jogo nativo" viraram "Controlar o PC / Jogar pelo
  Hefesto / Jogar direto (Sony)" na GUI e no applet.
- `check_packaging_parity.sh` passou a validar a paridade de TODAS as regras
  udev nos instaladores; a lista de regras do `install.sh` é derivada dos
  assets (não desatualiza mais).

### Fixed

- **Vibração dos jogos no DualSense — 3 causas encadeadas, flagradas em
  gameplay ao vivo (Sackboy)**: (1) o gamepad virtual NÃO anunciava
  force-feedback (a lib python-uinput não suporta FF) — vpad migrado para
  python-evdev com FF_RUMBLE/FF_PERIODIC completos; o rumble do jogo agora
  passa pelo gerenciador do Hefesto (política + intensidade global) e chega
  ao controle físico do jogador certo, inclusive no co-op
  (FEAT-VPAD-FF-PASSTHROUGH-01); (2) no Modo Nativo, o keepalive do
  report_thread pisoteava o rumble/gatilhos/LED que o jogo escrevia no hidraw
  a cada 0,5 s — em nativo o output HID do Hefesto agora é 100% mutado
  (FEAT-NATIVE-OUTPUT-MUTE-01); (3) sair do jogo revertia o nativo-de-perfil
  sem devolver o gamepad/co-op de antes (a usuária ficava sem controle —
  BUG-NATIVE-REVERT-DROPS-STASH-01). Nota: haptics por ÁUDIO (Sackboy & cia)
  seguem indisponíveis por decisão (o áudio do DualSense fica suprimido pelo
  anti-storm); o caminho garantido de vibração é "Jogar pelo Hefesto".
- Comutador de modo e máscara da aba Início não disparavam nada (assinatura
  errada do handler do sinal `changed` — BUG-HOME-SEGMENTED-SIGNATURE-01).
- "Salvar Perfil" do rodapé zerava o `match` (virava "any"), apagava a seção
  `mode`/`suppress` e resetava a prioridade do perfil ativo
  (BUG-FOOTER-SAVE-DROPS-SECTIONS-01); renomear pelo campo Nome criava perfil
  com config default em vez de levar a config do selecionado
  (BUG-RENAME-DROPS-CONFIG-01).
- Trocar de modo na Início mostrava "Falha" com o modo já aplicado (timeout
  IPC de 0,25 s curto demais para criar uinput+grab — agora 2 s); "Desligar
  Hefesto" dava toast de sucesso mesmo com o systemctl falhando; render
  offline deixava descrição/origem/máscara do último estado online.
- Lista de Perfis não re-marcava o ativo quando o autoswitch/hotkey trocava o
  perfil; aba Daemon não re-renderizava ao ser exibida; poller de 10 Hz da
  Status rodava com a aba invisível; cartão UINPUT da Emulação ficava stale
  com o daemon offline.
- Botão "Personalizar" duplicado nos presets por posição dos Gatilhos;
  ajustes de slider/preset de gatilho e a política de rumble exibida agora
  entram/derivam do draft (o que a tela mostra é o que "Salvar Perfil"
  grava); slider de intensidade custom passou a cobrir até 200%.
- Flatpak: o manifesto só embalava 3 das 6 regras udev obrigatórias e o
  `install-host-udev.sh` abortava — setup de udev do Flatpak não instalava
  NADA (FIX-FLATPAK-UDEV-PARITY-01; parity check agora cobre o manifesto).
  AppImage passa a bundlar os presets default (semeadura runtime resolve via
  `sys.prefix`). `dev_bootstrap.sh` criava venv sem `--system-site-packages`
  (GUI sem PyGObject em bootstrap dev fresco).
- Interface "balançava" ao passar o mouse nos botões: hover mudava a
  espessura da borda (1px→2px), o layout renegociava e oscilava em loop —
  ênfase de hover agora é só cor (BUG-GUI-HOVER-JITTER-01).
- Seletor de máscara cortado na borda direita na aba Início e no editor de
  Perfis (BUG-HOME-MASK-CLIP-01) — máscara em linha própria; cards de
  controle com tamanho uniforme.
- Co-op não cria mais gamepad virtual com grab apenas "pendente" — só com
  EVIOCGRAB confirmado (BUG-COOP-GRAB-PENDING-VPAD-01); fim da janela de
  input dobrado no hotplug.
- `Icon=` do `.desktop` do applet apontava para nome de ícone inexistente.

## [3.11.0] — 2026-07-09

### Added

- **Modo Nativo — "release total" do controle** (FEAT-NATIVE-MODE-01): um botão
  de parar que de fato solta o DualSense para o jogo usar os gatilhos adaptativos
  NATIVOS da Sony (Sackboy & cia), sem o hefesto no meio. `hefesto-dualsense4unix
  native on|off|status` (CLI) + `native.mode.set` (IPC). Ligado: gatilhos Off/Off
  (o jogo impõe os seus), rumble em passthrough, emulação de mouse/gamepad off
  (libera o grab), autoswitch/hotkey de perfil travados e o dispatch de input
  congelado (gate pelo próprio flag, não por pause — `daemon.resume` não
  des-solta). O estado da emulação (mouse/gamepad) é guardado e RESTAURADO ao
  desligar; sobrevive a reboot.
- **Modo point-and-click por perfil** (FEAT-POINT-AND-CLICK-01): perfil ganha
  seção `mouse` opcional (`enabled/speed/scroll_speed`); ao focar o jogo (ex.:
  Grim Fandango), o autoswitch liga o modo mouse com a velocidade do perfil,
  respeitando um lock manual de 30 s (não mata um gamepad virtual ligado na mão).
  Preset default `point_and_click` + supressão de bindings de desktop no jogo.
- **Diagnóstico anti-storm unificado no `doctor`** (FEAT-DSX-UNIFY-01): o
  DualSense Fix (dsx) foi trazido para dentro do hefesto na parte segura —
  `doctor` mostra o bloco "anti-storm / sistema" (quirk, Steam Input, WirePlumber,
  regra áudio-off, tudo read-only); `doctor --fix-safe` aplica o seguro sem sudo
  (Steam Input OFF + WirePlumber); `doctor --reapply-all` invoca o `dsx.sh`
  (privilegiado, pede senha). Cartão equivalente na aba Daemon da GUI. A fronteira
  Aurora é respeitada (kernel cmdline + regras 99-usb continuam dela).

### Changed

- **Cursor do modo mouse reescrito** (FEAT-MOUSE-CURSOR-FEEL-01): pipeline float
  com deadzone radial reescalada, curva expo e carry sub-pixel no stick (todas as
  velocidades passam a funcionar; simétrico; sem degrau). Velocidade persiste
  entre restarts. Aba Mouse sincroniza com o estado vivo do daemon e o "Aplicar"
  não desliga mais uma emulação ligada por fora (BUG-MOUSE-GUI-SYNC-01).
- **Últimos dropdowns viram botões segmentados**: os combos de PRESET de gatilho
  (imunes ao bug de foco do cosmic-comp) — completando a migração dos combos.

### Fixed

- **GUI "botões que aumentam e diminuem"**: os labels de posição do stick tinham
  largura variável (o número muda de dígitos) → re-layout do painel a 10 Hz.
  Campo de largura fixa (monospace) elimina o reflow.
- **`point_and_click` não instalava em upgrade** e vários bugs de emulação
  (gamepad morto ao ativar o perfil, flags invertidos no boot, seção mouse
  descartada ao salvar o perfil, race de device uinput) — achados e corrigidos
  por três rodadas de auditoria adversarial.
- **Remediação de estabilidade da GUI no COSMIC** (GUI-ESTABILIDADE-COSMIC-
  REMEDIATION-01): 19 achados de 4 auditorias + reprodução ao vivo, corrigidos em
  5 workstreams. **Rodapé** voltou a `GtkBox` (o `GtkFlowBox` dropava 3 de 4 botões
  / `Negative content width`). **Janela preta no boot** (race de primeiro-frame
  XWayland+NVIDIA): monta os widgets antes do `show_all` + repaint forçado pós-map.
  **Rumble** com exclusão mútua real (1 política afundada por vez; clique sempre
  reenvia IPC). **Teclado** parou de apagar os bindings de OSK de l3/r3
  (`parse_binding` aceita tokens virtuais) — fim da perda de dados. **Emulação**
  reconcilia todos os status ao "Atualizar"/trocar de aba. **Status** diffa o
  repaint a 10 Hz (fim do jank) + guards de inflight nos 3 pollers. **Perfis**
  "Ativar" async (não trava a GUI). **Lightbar** "Apagar" persiste no draft.
  Fim do busy-loop `idle_add` da janela compacta; guard de refresh por-mixin.
- **FakeController sequestrava o socket de produção** (BUG-FAKE-SOCKET-SYNC-01):
  um daemon fake cru (`HEFESTO_DUALSENSE4UNIX_FAKE=1` sem nome de socket) usava o
  socket de produção e a GUI passava a falar com ele ("Conectado Via USB"
  fantasma). O nome do socket agora é derivado do próprio switch de fake
  (`ipc_socket_name`), isolando fake/produção de forma automática.
- **`.deb` não empacotava as regras udev 76/77** (PACKAGING-UDEV-DEB-PARITY-01):
  sem a 76 o touchpad do DualSense brigava com a emulação de mouse; sem a 77 a
  lightbar/player-LED via sysfs não gravava. Agora o `.deb` empacota 70/71/72/76/77
  em paridade com o install nativo, e só empacota units systemd que funcionam nesse
  contexto.

## [3.10.0] — 2026-06-28

### Added

- **Applet COSMIC: "Fechar painel" e "Sair (desligar Hefesto)" no popover**: o
  popover do applet ganhou dois itens. "Fechar painel" fecha a janela da GUI
  (manda SIGTERM só ao processo `-gui`) mantendo o daemon vivo — o controle segue
  funcionando. "Sair (desligar Hefesto)" para o daemon via `systemctl --user stop`
  (saída limpa; como o serviço é `Restart=on-failure`, não ressuscita) — religue
  com `hefesto-dualsense4unix daemon enable`. Antes só o tray GTK tinha "Sair", e
  no COSMIC o tray usado é o applet, que só tinha "Abrir painel".
- **Seletor de controle: config de output por-controle**
  (FEAT-DSX-CONTROLLER-SELECTOR-01): com 2+ controles, dá pra escolher um ALVO e
  as ações de output (lightbar, gatilhos, player-LED, rumble, mic-LED) passam a
  mirar SÓ ele — resolve o "ambos mostram Player 1" (seleciono o Controle 2 →
  seto o LED dele como Player 2) e permite cores/perfis diferentes por controle.
  O backend ganhou um alvo guardado pela KEY estável (serial/MAC), o `_for_each`
  o respeita (e cai em broadcast se o alvo desconectar), e há `set_output_target`
  /`get_output_target_index`. Exposto por IPC `controller.target.set` +
  `output_target_index` no `daemon.state_full`; pela CLI
  `hefesto-dualsense4unix controller target <n|all>` e `controller list`; por um
  seletor no banner da GUI e na lista do popover do applet COSMIC (ambos só
  aparecem com 2+ controles). Padrão = "Todos" (broadcast, idêntico ao histórico
  — não afeta o caso de 1 controle).
- **Co-op local: cada controle vira um jogador (P1, P2, …)**
  (FEAT-DSX-COOP-LOCAL-01): novo modo opcional em que cada DualSense físico ganha
  seu PRÓPRIO gamepad virtual (com grab do controle real) — duas pessoas jogam
  co-op local de verdade. Antes o multi-controle era "N controles, 1 player"
  (output em broadcast, input só do primário → os dois apareciam como P1). O novo
  `CoopManager` adiciona uma camada de jogadores secundários sem tocar no caminho
  do P1; o poll loop repassa cada controle ao seu vpad. Liga/desliga por
  `hefesto-dualsense4unix coop on|off|status` ou IPC `coop.set` (persiste no
  reboot); exige a emulação de gamepad ligada + 2+ controles. Estado em
  `daemon.state_full` (`coop.enabled`/`coop.players`). Fora de escopo (fase
  futura): rumble do jogo por jogador e player-LED por índice.
- **Multi-controle visível no tray, na GUI e no applet COSMIC**
  (FEAT-DSX-MULTI-CONTROLLER-01): `daemon.state_full` passou a expor um bloco
  `controllers` (um item por controle físico, com `transport` e `is_primary`).
  Com 2+ controles conectados, a aba Status mostra "N controles: **BT** + USB"
  (primário em negrito), o item de status do tray ganha " · N controles (BT +
  USB)", a janela compacta lista os transportes e o popover do applet COSMIC
  exibe uma linha "Controles: 2 (BT + USB)". Degrada com graça em daemon antigo
  sem o bloco (a linha some) e em falha de IPC.
- **Dropdowns viram botões segmentados (imunes ao bug de foco do COSMIC)**
  (FEAT-DSX-COMBO-TO-SEGMENTED-01): combos com poucas opções (seletor de controle,
  "Aplica a:" dos perfis) deixaram de ser `GtkComboBox` — cujo popup o cosmic-comp
  fechava sozinho ao abrir (cosmic-epoch#2497 + NVIDIA, não era bug nosso) — e
  viraram botões segmentados sem popup. Mesma API por-ID; nenhum menu para piscar.

### Fixed

- **TODOS os combos/menus da GUI piscavam e fechavam ao clicar**
  (BUG-COMBO-POPUP-FLICKER-02): a causa real era o render a 10 Hz. Os sticks do
  DualSense TREMEM em repouso, então os labels "X: 128 Y: 127" mudavam de largura
  a cada tick → `queue_resize` → re-layout da janela → fechava qualquer popup
  aberto (em XWayland E Wayland). Agora os renders (vivo 10 Hz e lento 2 Hz)
  pausam enquanto houver um grab GTK ativo (`Gtk.grab_get_current()`), ou seja,
  enquanto um popup está aberto — retomam sozinhos ao fechar. Inclui também o
  endurecimento do combo do seletor para refresh idempotente
  (BUG-CONTROLLER-SELECTOR-COMBO-FLICKER-01: só toca o GTK quando rótulos/posição/
  visibilidade mudam). Testes de regressão cobrem os dois.
- **Popover do applet COSMIC estourava a tela (itens de baixo cortados)**: com
  status + seletor de alvo + mic + perfis + ações, o popover passava da altura
  útil e os botões finais ("Abrir/Fechar painel", "Sair") ficavam cortados sem
  rolagem. Todo o conteúdo agora vai num `scrollable` limitado em altura
  (`max_height`), então nada some e dá pra rolar até o fim.
- **Corrupção do link Bluetooth com 2 controles (USB+BT) — `DualSense input CRC's
  check failed`** (BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01): com um DualSense por
  USB e outro por Bluetooth, o loop `sendReport` da pydualsense (read+write em
  hidraw sem pausa, na taxa do controle) rodava em 2 threads e saturava o
  controlador USB — e o adaptador BT vive no mesmo controlador (família do storm),
  degradando o link e matando o output do controle BT. `_PinnedPyDualSense` agora
  sobrescreve `sendReport` com um throttle por ciclo (`REPORT_THREAD_THROTTLE_SEC`,
  ~125Hz, env-configurável). Validado ao vivo: de CRC fails recorrentes para **0**
  com os 2 conectados; gatilhos/rumble/player-LEDs estáveis em USB e BT. O INPUT
  vem do evdev, então o throttle não afeta a responsividade.
- **Lightbar (cor) por Bluetooth — RESOLVIDO** (FEAT-DSX-LIGHTBAR-SYSFS-01): a cor
  não obedecia por BT (gatilhos/rumble/player-LED já funcionavam). A causa era
  contenção de DOIS escritores: o kernel `hid_playstation` é dono da lightbar
  (LED class device) e a reafirmava, enquanto a escrita crua por hidraw da
  pydualsense (seq-tag BT fixo) disputava e perdia — só na cor. Agora a cor vai
  pela rota sysfs do kernel
  (`/sys/class/leds/<inputN>:rgb:indicator/{multi_intensity,brightness}` + os
  `:white:player-N/brightness`), que monta o report certo (CRC + seq) IGUAL em USB
  e BT; e a pydualsense para de disputar (limpa os bits de flag de lightbar `0x04`
  e player `0x10` no report quando o sysfs está ativo). Mapeia controle→nó por MAC;
  só usa sysfs se o nó for gravável (regra udev nova `77-dualsense-leds.rules`,
  aplicada pelo install), senão cai no caminho pydualsense sem regressão. Validado
  ao vivo por BT.
- **Botões do rodapé da GUI sumiam sob o tiling do COSMIC**: os 4 botões
  (Aplicar/Salvar/Importar/Restaurar) ficavam cortados porque o `GtkNotebook`
  exigia altura mínima grande (puxada pelas abas maiores) e a janela não encolhia.
  Agora as páginas são roláveis (`GtkScrolledWindow`), os botões vão num
  `GtkFlowBox` (quebram em 2 colunas quando estreito) e a janela tem tamanho
  mínimo — os 4 botões aparecem em qualquer largura. Validado visualmente.
- **Comandos da CLI agora falam com o daemon (não abrem um 2º controle)**:
  `profile activate`, `test trigger` e `test rumble` tentam o daemon vivo por IPC
  antes de cair no hardware direto. Antes abriam um controller próprio e disputavam
  o hidraw com o daemon (mesma família do bug da lightbar), e o `profile activate`
  nem trocava o perfil em uso. O subcomando standalone `emulate xbox360` (que
  duplicava o gamepad do daemon) foi removido — a máscara de gamepad do daemon já
  cobre o caso.
- **Perfil com modo de gatilho inválido é rejeitado na validação** (não mais só no
  apply, em runtime): `TriggerConfig.mode` ganhou validação contra o conjunto
  canônico de efeitos.
- **Endpoint Prometheus `/metrics` agora realmente sobe** quando `metrics_enabled`
  (o subsystem nunca era iniciado — feature morta), e o multiplicador de rumble
  auto reportado no `state_full` passou a vir da política viva (antes ficava preso
  em 1.0).
- **GUI mais fluida e robusta**: o toggle de mic e os 2 fetches periódicos do tray
  saíram da thread GTK (não travam mais a UI por segundos); o I/O de disco de
  salvar/importar/restaurar perfil também foi para worker; as statusbars deixaram
  de empilhar mensagens (no máx. 1 por contexto). Abrir a GUI não dispara mais um
  "Off" de gatilho no controle, e "novo perfil" não cria mais um filtro quebrado.
- **`uninstall.sh` agora remove o AppImage em `~/.local/bin`** e as regras udev
  76/77 (faltava limpar esses rastros).

### Conhecido (TODO)

- **Config por-controle é "ao vivo" (não persiste)** (FEAT-DSX-CONTROLLER-SELECTOR-01):
  o alvo de output vale enquanto o controle estiver conectado. O re-apply de
  perfil no hotplug e a troca de perfil seguem GLOBAIS nesta fase (o `_desired`
  não é por-controle); persistir a config por-controle entre reconexões fica para
  uma fase futura.

## [3.9.0] — 2026-06-27

### Added

- **Troca de perfil por hotkey no controle (PS + D-pad)**: `PS + ↑` vai pro
  próximo perfil e `PS + ↓` pro anterior (com wrap-around), aplicando
  triggers/LEDs/key_bindings pelo mesmo caminho do `profile.switch` (IPC). Como
  feedback in-hand, o lightbar pisca antes de pintar a cor do perfil novo. Antes
  os combos ficavam `disabled_until_wired` (disparavam com callback nulo mas ainda
  comiam o D-pad); agora trocam de verdade e a aba Emulação anuncia o combo em vez
  de "em desenvolvimento". Gesto explícito arma um lock manual contra o autoswitch.
  (FEAT-HOTKEY-PROFILE-CYCLE-01)
- **Watchdog de evdev obsoleto (auto-cura do "controle morto sem erro")**: após
  uma re-enumeração do controle (storm -71 / replug rápido) o kernel cria um novo
  `/dev/input/eventN`, mas o `read_loop` podia seguir preso no fd antigo **sem
  receber ENODEV** — controle morto sem nenhum erro logado. O poll loop agora
  cruza HID × evdev: com o HID conectado, se o node canônico do evdev mudou,
  reabre o reader. É **idle-safe** — só dispara por troca real de node, nunca por
  ociosidade (ficar parado não reabre nada). (FEAT-DSX-EVDEV-WATCHDOG-01)

### Changed

- **`DEFAULT_PS_LONG_PRESS_MS` agora é 0 (long-press do PS desligado por padrão)**:
  o modo jogo passa a ser SÓ pelo combo deliberado PS+Options. Antes, o default
  1000ms fazia o toque de "abrir Steam" que passasse de ~1s **alternar o modo jogo
  sem querer** (modo-jogo acidental). Agora isso vem corrigido de fábrica — não
  depende mais de um `environment.d` na `$HOME` (que uma formatação apagava).
  Quem quiser o gesto de volta: `HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS>0`.
  Atualizados os 4 pontos (constante, env default, DaemonConfig, fallback do
  subsystem) + testes. (FEAT-EMULATION-GAMEMODE-COMBO-01)
- **Auto-start do daemon no boot agora é default no install** (`install.sh` sem
  `--no-...`/com `--yes` habilita): o controle só funciona com o daemon rodando;
  exigir passo manual após cada boot/formatação contrariava "instala tudo".
- **Seletor de gamepad da aba Emulação realça o modo ativo**: o botão do modo
  atual (Desligado / DualSense (PS) / Xbox 360) fica destacado em roxo (classe
  `.hefesto-active-mode`, mesmo visual da política de rumble), refletindo o estado
  vindo do daemon — antes nada indicava qual estava selecionado.

### Fixed

- **Daemon órfão disputando o socket IPC** (GUI/applet/CLI falando com o daemon
  errado → "nada aplica"): o lock de instância única do daemon era sempre
  `"daemon"`, então um daemon de socket ISOLADO (`run.sh --fake`, smoke) fazia
  SIGTERM-takeover do daemon de PRODUÇÃO; o systemd ressuscitava o real e sobravam
  daemons órfãos em ping-pong. Agora **(1)** o nome do lock é derivado do socket
  (fake/smoke/custom ganham pid-lock isolado e NUNCA matam o real;
  `single_instance_name()`), e **(2)** o `run.sh` se recusa a subir um daemon de
  PRODUÇÃO quando o serviço do systemd já está ativo (use `--fake`, pare o serviço,
  ou `--force`). (BUG-MULTI-INSTANCE-ISOLATED-SOCKET-01, BUG-MULTI-INSTANCE-RUNSH-GUARD-01)
- **Controle MORTO no jogo mesmo com gatilhos/cores aplicados** (regressão de
  gameplay): o forward do gamepad virtual no poll loop estava DENTRO dos dois
  gates de emulação de desktop — `_paused` (via o `continue` do gate de pausa) e
  `_emulation_suppressed` (via `emu_active`). Como o controle físico fica
  EVIOCGRAB-grabado quando o gamepad está ligado (fonte única), entrar em "modo
  jogo", pausar, ou renascer pausado no boot deixava o jogo sem ver NADA: real
  escondido + virtual mudo. Agora o forward do gamepad é gateado SÓ pelo
  grace-period (anti-ghost-input) e independe de pausa/supressão; mouse/teclado
  seguem suspensos no modo jogo. (FEAT-DSX-GAMEPAD-ALWAYS-LIVE-01)
- **GUI "Modo jogo" usava `daemon.pause` (persistente) → controle nascia morto
  após reboot**: o botão (e o applet COSMIC) agora usam `daemon.emulation.suppress`
  (transitório, paridade com o combo PS+Options), que NÃO persiste `paused.flag`.
  O label "Modo jogo" passa a refletir o estado certo e o tooltip deixou de
  mentir. (FEAT-DSX-GAMEMODE-SUPPRESS-01)
- **Daemon a 100% de CPU e inresponsivo ("os botões não aplicam")**: cada
  desconexão normal de cliente IPC (a GUI/applet fecham o socket no timeout de
  0,25s) levantava `BrokenPipeError`/`ConnectionResetError` no `writer.drain()`,
  logado com `exc_info=True` → o ConsoleRenderer renderizava um traceback rico COM
  locals (todo o grafo do daemon) a ~5×/s, fritando uma CPU e despejando ~950
  linhas/s no journal numa espiral. Agora desconexão de cliente é logada em
  `debug` sem traceback. (BUG-IPC-DISCONNECT-STORM-01)
- **Rodapé "Aplicar" nunca aplicava os key_bindings editados na aba Teclado**:
  `to_ipc_dict()` omitia `key_bindings` e o `DraftApplier` não tinha seção de
  teclado — só `profile.switch` empurrava bindings ao device. Agora "Aplicar"
  resolve e aplica os bindings ao device vivo (None → DEFAULT_BUTTON_BINDINGS;
  dict → override) sem reativar perfil. (BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01)
- **"Aplicar"/"Parar" do Rumble matavam o rumble do JOGO**: "Aplicar" com sliders
  em 0 (o default) gravava `rumble_active=(0,0)`, reasserido a 5Hz, sobrescrevendo
  a vibração in-game. Agora (0,0) vira passthrough (`rumble_active=None` — o jogo
  controla), e há um botão **"Devolver rumble ao jogo"** na aba Rumble (antídoto
  do "Parar", antes só acessível pela CLI). (BUG-RUMBLE-APPLY-KILLS-GAME-01,
  FEAT-RUMBLE-PASSTHROUGH-GUI-01)
- **`run.sh --fake` sequestrava o socket de PRODUÇÃO**: o modo fake (setters
  no-op, sem HID/evdev) não isolava o socket IPC e, via single-instance "última
  vence", tomava o lugar do daemon real — GUI/applet/CLI passavam a falar com um
  daemon fake e "nada aplicava" no controle. Agora isola o socket como o `--smoke`
  já fazia. (BUG-RUN-FAKE-HIJACK-PROD-SOCKET-01)
- **Ligar o Mic do DualSense podia reabrir o storm -71 sem aviso**: a GUI/applet/
  CLI removiam a supressão do WirePlumber sem checar o quirk de áudio USB. Agora
  avisam (sem bloquear) quando o quirk não está ativo na sessão, e o `install.sh`
  recomenda aplicá-lo. Não mexe no cmdline (gerido pela toolchain pessoal).
  (BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01)
- **Suíte de testes não era hermética e falhava na máquina do mantenedor**: os
  testes liam o `~/.config/hefesto-dualsense4unix` REAL (flags de sessão de
  gamepad/mouse/pause, perfis); numa máquina com a emulação de gamepad LIGADA de
  verdade, 3 testes de dispatch de mouse/teclado falhavam (a CI passava só por
  rodar em HOME limpo). O `conftest` agora isola `XDG_CONFIG_HOME`/data/cache/
  state por teste. (BUG-TEST-CONFIG-LEAK-01)
- **mypy quebrava o gate de CI**: 2 erros novos no `backend_pydualsense.py`
  (subclasse de `pydualsense` Any + anotação de retorno faltando) e 6 legados em
  `trigger_effects.py` (`arg-type`) e `tray.py`
  (`func-returns-value`/`unused-ignore`) — todos corrigidos; `mypy src` limpo.
- **Botões da aba Emulação não faziam nada ao clicar** (gamepad/máscara,
  pausar/retomar, Steam Input e mic): os `<signal handler="...">` existiam no
  `main.glade`, mas as chaves não tinham sido adicionadas ao dict de
  `builder.connect_signals()`. Como o app fia sinais por dict explícito (não por
  `self`), o GTK não achava o callback e o clique era no-op. Adicionadas as 9
  entradas faltantes + teste estático (`test_glade_signal_handlers.py`) que trava
  a regressão garantindo que todo `handler` do glade esteja registrado.
  (BUG-GUI-EMULATION-HANDLERS-UNWIRED-01)
- **`uninstall.sh` assimétrico**: passa a remover o drop-in WirePlumber **53**
  (disable-output, gerado junto do 52) e o **91** do `environment.d` (modo-jogo) —
  antes ficavam órfãos. Mantém o princípio de uninstall simétrico ao install.

### Added

- **Suporte a MÚLTIPLOS DualSense conectados** (FEAT-DSX-MULTI-CONTROLLER-01): os
  gatilhos adaptativos, lightbar, rumble e o **perfil ativo** passam a ser aplicados a
  **TODOS** os controles conectados, com **hotplug** (plugou, já recebe o perfil). A
  emulação (mouse / gamepad virtual / teclado) permanece no **controle primário** (um
  só leitor/grab, sem duplicação). O backend HID foi reescrito de single para
  multi-device: um handle por controle, aberto por `path` via hidapi e indexado pelo
  serial/MAC (a `pydualsense` não é multi-device nativa), com fan-out de escrita e
  reconciliação de hotplug no `connect()`. `controller.list` (IPC) agora lista os N
  controles. (Limitações conhecidas documentadas na sprint: modo-jogo + gamepad virtual,
  e coordenação inputoutput do primário com 2+ controles.)
- **Toggle do microfone do DualSense (liga só quando precisar)**: o mic embutido
  vem suprimido por padrão (não vira microfone padrão / sem spam), e agora há como
  ligá-lo sob demanda para jogos que pedem mic — o quirk segura o storm com o mic
  ativo. Exposto em três lugares: CLI `hefesto-dualsense4unix mic on|off|status`,
  botão na aba Emulação da GUI, e ação no applet COSMIC. Reusa
  `scripts/fix_wireplumber_default_source.sh` (`--enable-mic`/`--disable-source`).
  (FEAT-DUALSENSE-MIC-TOGGLE-01)
- **Regra udev 76 (touchpad ignorado pelo libinput) agora no install padrão**:
  `76-dualsense-touchpad-libinput-ignore.rules` passa a ser instalada por default
  (incondicional, como 70/71/72) em `install.sh`/`scripts/install_udev.sh` e no
  caminho `.deb`/Flatpak (`scripts/install-host-udev.sh`). O kernel `hid_playstation`
  expõe o touchpad do DualSense como ponteiro libinput separado que briga com a
  emulação analógica do hefesto (cursor "engasgado"); a regra deixa o hefesto como
  única fonte de cursor. Não-destrutiva e reversível (remover o arquivo).
  Trigger de `input` aplicado; vale de fato após replug/relogin do controle.
  (FEAT-DUALSENSE-TOUCHPAD-IGNORE-01)
- **Touchpad move o cursor (fonte única, suave)**: complementa a regra 76 — agora
  que o libinput ignora o touchpad, o próprio daemon lê o `event14`
  (`ABS_X`/`ABS_Y` + `BTN_TOUCH`) e o converte em movimento do cursor (REL_X/REL_Y
  via mouse virtual). Como há **uma só fonte** de ponteiro, acaba o "engasgo" da
  briga libinput×emulação. Acumula o delta por tick com **carry sub-pixel** (sem
  travadas em movimento lento) e escala por `mouse_speed`. Respeita o modo-jogo:
  o cursor só anda quando a emulação está ligada e não-suprimida; ao suprimir
  (PS+Options) o movimento acumulado é descartado para o cursor não "pular" ao
  religar. Levantar e reapoiar o dedo não causa salto. (FEAT-DSX-TOUCHPAD-CURSOR-B4)
- **Gamepad virtual com máscara DualSense ou Xbox (integrado ao daemon)**: o
  bridge — antes um processo CLI avulso (`emulate xbox360`) que abria um SEGUNDO
  leitor do controle e causava **input dobrado** — virou um subsystem do daemon
  (1 leitor → fan-out). Duas máscaras: **DualSense** (VID/PID Sony, prompts de
  PlayStation, default) e **Xbox 360** (fallback p/ jogos XInput-only). Faz
  `EVIOCGRAB` do controle real enquanto ativo (o jogo vê só o virtual, sem
  duplicar) e é mutuamente exclusivo com a emulação de mouse. Liga/desliga +
  máscara persistem no boot. Exposto na CLI `hefesto-dualsense4unix gamepad
  on|off|status [--flavor dualsense|xbox]`, no IPC `gamepad.emulation.set` e na
  aba Emulação da GUI. (FEAT-DSX-GAMEPAD-FLAVOR-01)
- **GUI auto-suficiente: botões de gamepad, modo-jogo e Steam Input**: a aba
  Emulação agora liga/desliga o gamepad virtual (Desligado/DualSense/Xbox),
  pausa/retoma a emulação (modo jogo, via `daemon.pause`/`resume`) e verifica/
  desliga o Steam Input (que conflita com o daemon) — tudo sem precisar do
  terminal. (FEAT-DSX-GUI-SELF-SUFFICIENT-01)
- **Storm-watch opt-in (`--with-storm-watch`)**: serviço de usuário que registra
  o storm USB (-71) num log dedicado e legível
  (`~/.local/state/hefesto-dualsense4unix/storm.log`), replicável e sobrevivente
  a reboot (sem `/tmp`, sem sudo). O journald já guarda tudo; isto é só um recorte
  fácil de ler. Simétrico no uninstall. (FEAT-DSX-STORM-WATCH-01)

## Histórico anterior — 3.8.3 e abaixo

As 27 versões de **3.8.3 (2026-06-26) até 0.1.0 (2026-04-20)** saíram
deste arquivo na faxina de lançamento: eram ~1,7 mil linhas de notas do ciclo
pré-público. Elas continuam íntegras no arquivo de processo, preservado na tag
`arquivo/processo-pre-1.0`:

```bash
git show arquivo/processo-pre-1.0:CHANGELOG.md            # o changelog completo
git show arquivo/processo-pre-1.0:CHANGELOG.md | less     # navegável
```

O que está lá, em ordem:

| Versão | Data |
|---|---|
| 3.8.3 | 2026-06-26 |
| 3.8.2 | 2026-05-23 |
| 3.8.1 | 2026-05-22 |
| 3.8.0 | 2026-05-22 |
| 3.7.0 | 2026-05-22 |
| 3.5.0 | 2026-05-21 |
| 3.4.3 | 2026-05-17 |
| 3.4.2 | 2026-05-17 |
| 3.4.1 | 2026-05-17 |
| 3.4.0 | 2026-05-16 |
| 3.3.1 | 2026-05-16 |
| 3.3.0 | 2026-05-16 |
| 3.2.0 | 2026-05-16 |
| 3.1.1 | 2026-05-16 |
| 3.1.0 | 2026-05-16 |
| 3.0.0 | 2026-04-27 |
| 2.3.0 | 2026-04-24 |
| 2.2.2 | 2026-04-24 |
| 2.2.1 | 2026-04-23 |
| 2.2.0 | 2026-04-23 |
| 2.1.0 | 2026-04-23 |
| 2.0.0 | 2026-04-23 |
| 1.2.0 | 2026-04-22 |
| 1.1.0 | 2026-04-22 |
| Pre-1.1.0 (incremental) | 2026-04-22 |
| 1.0.0 | 2026-04-21 |
| 0.1.0 | 2026-04-20 |
