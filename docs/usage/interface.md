# A janela, aba por aba

A janela principal tem dez abas. Esta página diz o que cada uma faz e o que se
ajusta nela.

> **Sobre as capturas.** Elas são geradas por
> `scripts/gui-captura/retratar_abas.py` — um comando, sem clique nenhum — e
> por isso **acompanham a versão**: quem mexe na interface roda o script antes
> de commitar. As desta página foram regeradas em **10/08/2026**, com a aba
> "No jogo" já na tira.
>
> **NOTA DATADA — 10/08/2026.** Esta caixa dizia que as capturas eram de
> 25/07/2026, com *"quatro controles conectados por Bluetooth ao mesmo
> tempo"*, e que o bloco "Detalhes técnicos" da aba Sistema aparecia **borrado
> de propósito** porque carregava endereço Bluetooth real. As duas afirmações
> caducaram e a segunda não descreve mais um risco: desde a
> `RETRATO-DAS-ABAS-01` o script **nunca fala com o daemon** — ele monta a
> própria interface do zero e a alimenta com os dublês da suíte de testes, e
> isso é travado por teste (`test_retrato_das_abas_nao_vaza_dado_real.py`).
> Nenhuma imagem desta pasta tem dado real, e nenhuma precisa de borrão. O
> cenário retratado hoje é o de **dois** controles (um USB, um BT), que é o que
> o script monta.

## Início

![Aba Início](assets/readme_inicio.png)

A aba de decisão, dividida em três quadros.

**"Quando o jogo abrir"** — o seletor **"O que o controle faz agora:"** com os
três modos (Controlar o PC · Jogar pelo Hefesto · Conexão Nativa (Sony)), o
seletor de máscara **"O jogo vê o controle como:"** e o cadeado **"Não trocar de
perfil sozinho ao abrir um jogo"**.

> **O nome do quadro é literal, e é a razão dele existir** (AGORA-E-DEPOIS-01,
> 08/08/2026): o jogo lê modo e máscara **uma vez, na abertura**. Clicar num
> modo com o jogo já aberto não muda nada dentro dele — o clique **marca** a
> escolha, e é o **Aplicar** do rodapé que a aplica. O que muda na hora (cor,
> brilho, gatilho, vibração, microfone) mora nas outras abas. Quando a mudança
> só valeria na próxima abertura e há jogo na frente, a janela **pergunta** em
> vez de aplicar por cima.

**"Controles"** — um card por controle conectado, com transporte, número de
jogador e bateria, mais o botão **"Reconciliar jogadores"** (força um ciclo de
co-op e a renumeração quando um controle não aparece para o jogo).

**"Sessão"** — **"Desligar Hefesto (voltar ao Linux puro)"**, que para tudo até
você clicar em "Ligar o Hefesto" no mesmo lugar.

Os avisos de degradação (controle virtual em modo reduzido, jogo aberto sem o
atalho da Steam) aparecem no topo dela. E desde 09/08/2026 há mais um: escolher
**"Controlar o PC"** com o mouse ou o teclado emulado **desligado** faz a aba
dizer isso com todas as letras e apontar onde ligar — antes o modo cujo nome
promete controlar o PC entrava sem fazer nada e nenhuma tela dizia por quê.

Detalhe dos modos em [`modos.md`](modos.md).

## Status

![Aba Status](assets/readme_status.png)

O painel ao vivo. Conexão, transporte (USB ou Bluetooth), bateria, perfil ativo e
estado do Hefesto; barras de L2 e R2 de 0 a 255; os dois sticks analógicos; e a
grade de botões que acende quando você pressiona.

Também mostra os sensores por controle: **giroscópio** (três barras
bidirecionais), **microfone** (ativo ou mudo, com medidor de nível) e **touchpad**
(os pontos de toque). Os sensores só são lidos enquanto a aba está visível — as
threads morrem quando você sai dela.

Um controle sem nó de movimento (externo, kernel antigo) simplesmente não mostra
o sensor. Nunca aparece um zero fingindo repouso.

## No jogo

![Aba No jogo](assets/readme_no_jogo.png)

**Aba nova em 10/08/2026.** A Status responde pelo controle **físico**; esta
responde pelo que atravessa para o **jogo**. Ela nasceu de um pedido dela, ao
perguntar como validar giroscópio e touchpad: *"eu sei que a aba status é uma
coisa, mas isso converter em input seja via xbox ou dualsense ou nativo é
outra"*. Antes, a única forma de responder era abrir o testador da Steam.

No alto, a linha de contexto diz em que modo e com que máscara a janela está
agora — sem ela, uma foto da tela não diz de qual dos três modos ela é. Abaixo,
um painel por controle, e dentro dele **seis linhas fixas, sempre na mesma
ordem**: giroscópio, vibração, gatilho, luz, clique do touchpad e som do
controle. Trocar a máscara na aba Início e conferir olhando duas vezes para o
mesmo lugar é o gesto que a aba existe para servir — por isso linha fixa, e não
uma frase corrida.

A coluna da direita tem quatro respostas, e a cor é de significado:

| O que diz | Cor | O que significa |
|---|---|---|
| **no jogo agora** | verde | o dado saiu daqui e alguém escreveu de volta, agora (com o número medido ao lado: `(~158 Hz)`, `(motores: 30/120)`) |
| **parou** | amarelo | já esteve chegando e parou — era para estar chegando e não está |
| **sem pedido ainda** | apagado | o jogo nunca pediu. Não é avaria |
| **a máscara Xbox 360 não tem giroscópio** (ou touchpad) | apagado | a API do controle de Xbox não tem aquele recurso. Também não é avaria — por isso não é vermelho |

Onde não há gamepad virtual para medir, a aba **substitui** os painéis por uma
frase, e diz qual dos três casos é: **Conexão Nativa** (não há controle virtual
nenhum — o jogo abre o controle físico e fala direto com ele), **Controlar o
PC** (o controle está movendo mouse e teclado; o Hefesto não entrega controle
nenhum ao jogo) ou **este controle ainda não tem vpad** (acabou de conectar, ou
use "Reconciliar jogadores" na aba Início).

**O aviso do perfil que não entrou.** Se você tem um perfil escrito para o jogo
que está na frente e ele **não** está valendo, uma linha amarela aparece acima
dos painéis dizendo o que o perfil exige e o que a máquina vê, lado a lado — por
exemplo: *"O seu perfil 'Pragmata' é deste jogo, mas não entrou: ele exige nome
do processo 'PRAGMATA.exe', e aqui vê 'wine64-preloader'. Enquanto isso, vale o
perfil 'fallback'."* Ela é factual, nunca prescritiva, e só fala das regras
**daquele** jogo. Sem ela, a aba dizia "vibração: no jogo agora" com toda a
razão — e com a vibração do perfil errado.

> Nenhuma linha desta aba afirma que o **jogo consumiu** o dado: isso depende de
> qual biblioteca o jogo carregou (medido em 01/08: a `libSDL2` do Ubuntu não
> enumerava o gamepad virtual; a SDL3 que a Steam distribui enumerava). O que se
> afirma é o que o daemon pode saber — o dado saiu daqui, e alguém escreveu de
> volta. E onde não há dado, a tela **cala** em vez de escrever zero.

## Gatilhos

![Aba Gatilhos](assets/readme_gatilhos.png)

Configura o efeito adaptativo de L2 e R2, cada um do seu lado. Por gatilho: o
**Modo** (19 disponíveis — Rigid, Pulse, Galloping, Machine, Bow, Automatic Gun e
os demais), um **efeito pronto** com a intensidade, **Aplicar** e **Desligar**.

Referência dos modos e dos parâmetros brutos em
[`../protocol/trigger-modes.md`](../protocol/trigger-modes.md).

## Lightbar

![Aba Lightbar](assets/readme_lightbar.png)

Cor da barra de LED e LEDs de jogador. Tem seletor de cor com prévia, slider de
luminosidade, **Aplicar no controle** e **Apagar**.

Por padrão as **cores automáticas por controle** estão ligadas: cada DualSense
conectado ganha uma cor de jogador sozinho. Escolher uma cor manualmente desliga
o automático só naquele controle; **Voltar ao automático** (ou **Voltar todos**)
desfaz.

Os cinco LEDs de jogador seguem o desenho oficial do PS5 — Player 1 acende só o
LED central, Player 2 os dois vizinhos, e assim por diante. Não é bug: é o padrão
do console.

## Rumble

![Aba Rumble](assets/readme_rumble.png)

A intensidade da vibração dos jogos: **Economia** (0,3×), **Balanceado** (0,7×),
**Máximo** (1,0×) ou **Auto** (suaviza quando a bateria cai). O multiplicador
vale para o que o jogo pede, antes de chegar ao hardware.

Abaixo, o teste dos motores: vibração leve, vibração forte, **Testar por 500 ms**.
**Parar** trava o controle em silêncio — inclusive no jogo; **Deixar o jogo
controlar a vibração** devolve o comando.

## Perfis

![Aba Perfis](assets/readme_perfis.png)

Lista de perfis salvos com **Novo**, **Duplicar**, **Remover**, **Ativar** e
**Recarregar**. O editor tem dois modos: **Simples** (você diz o nome do jogo) e
**Avançado** (`window_class`, `title_regex`, `process_name` — AND entre os campos
preenchidos, OR dentro de cada lista).

Cada perfil tem prioridade de 0 a 200 e pode carregar um **modo** — o que ele
liga ao ser ativado. A prioridade é o **segundo** critério, não o primeiro: um
perfil com regra de janela sempre vence um perfil "Sempre", por mais alta que
seja a prioridade deste. A faixa tem fonte única em `profiles/schema.py`, e há
portão que reprova se o controle deslizante e o verificador discordarem.

Como escrever um perfil do zero: [`creating-profiles.md`](creating-profiles.md).

## Os avisos que a janela dá antes de estragar um perfil

Três perguntas existem para que um gesto distraído não custe configuração. Em
todas, o botão pré-selecionado é o que **não** mexe em nada — um Enter distraído
nunca destrói.

Salvar um perfil com prioridade menor do que ele tinha:

![Aviso de queda de prioridade](assets/dialogos/dialogo_rebaixa_prioridade.png)

Salvar um perfil que valia só em certos programas de um jeito que o faz valer
para tudo. O texto diz o que o perfil é **hoje**, porque avisar "vale só em
programas específicos" para um perfil que é "Só manual" seria o aviso mentindo:

![Aviso de virar Sempre](assets/dialogos/dialogo_vira_sempre_de_programa_especifico.png)

![Aviso de virar Sempre, vindo de Só manual](assets/dialogos/dialogo_vira_sempre_de_so_manual.png)

Ativar um perfil com alterações não salvas nas abas. Manter as alterações é o
padrão, e nesse caso as abas seguem mostrando o que você ainda não salvou:

![Aviso de edição pendente](assets/dialogos/dialogo_descarta_edicao_pendente.png)

## Sistema

![Aba Sistema](assets/readme_sistema.png)

O painel de manutenção. **Ligar** / **Desligar o Hefesto** (desligado, o controle
continua funcionando — só sem luzes, gatilhos e seus ajustes), **Reiniciar**, e
**Ligar junto com o computador**.

O bloco **Saúde do sistema** roda um diagnóstico ao abrir a aba e **Aplicar
correções** resolve o que é seguro resolver sem senha. Os três botões da Steam
vivem aqui: **Copiar opções p/ jogos**, **Aplicar aos jogos da Steam** e **Travar
Proton validado** — os dois últimos pedem a Steam fechada e fazem cópia de
segurança antes.

**Ver detalhes** abre o registro técnico ali embaixo, que é o que se anexa a um
relato de problema.

## Emulação

![Aba Emulação](assets/readme_emulacao.png)

A visão técnica do que a aba Início resume: qual máscara está ativa, o estado do
modo jogo, o Steam Input, o microfone do DualSense e o teste de criação do device
virtual. O texto de ajuda da própria aba explica qual máscara serve para qual
jogo.

## Navegação

![Aba Navegação](assets/readme_navegacao_dsx.png)

> **A aba se chamava "Navegação DSX" até a PALAVRA-01.** O rótulo na tira é
> **"Navegação"** — "DSX" é o nome de outro programa, e não dizia nada a quem
> abre a janela. O nome do arquivo da imagem (`readme_navegacao_dsx.png`)
> continua o antigo de propósito: renomeá-lo quebraria os links desta página e
> do `README.md` sem devolver nada.

Mouse e teclado lado a lado, em duas colunas. À esquerda, a emulação de mouse:
**Emular mouse**, velocidade do cursor e velocidade da rolagem. À direita,
**Emular teclado** e o mapeamento de botão para tecla.

> **NOTA DATADA — 10/08/2026: "escolha entre stick e touchpad" caducou, e a
> medição diz que ela nunca descreveu esta aba.** Esta linha prometia um seletor
> da **fonte do cursor**. **GRAU: MEDIDO** hoje contra o código: não há widget
> nenhum de fonte no `gui/main.glade` (a tabela da aba lista *"Analógico
> esquerdo → Movimento do cursor"* e *"Analógico direito → Rolagem vertical e
> horizontal"*, e mais nada), não há campo de fonte em `ProfileMouseConfig`
> (`enabled`, `speed`, `scroll_speed` — e `extra="forbid"`), e
> `integrations/uinput_mouse.py` não conhece touchpad. **O que é verdade hoje:**
> o cursor do mouse emulado sai do **analógico esquerdo**, sempre. O touchpad do
> DualSense move o cursor por outro caminho — ele é o touchpad do **sistema**,
> pelo libinput, e isso vale nos três modos (ver
> [`modos.md`](modos.md#o-touchpad-é-touchpad-do-sistema)).

Os **dois interruptores são irmãos e independentes**, e isso não é detalhe: o
rótulo único de antes dizia "Emular mouse+teclado" e governava **só** o mouse —
foi por isso que ela concluiu, com razão, que estava "com o modo mouse teclado
desligado" e mesmo assim levava Alt+Tab dentro do jogo. O Alt+Tab é do teclado.
Desligar **Emular teclado** tira tudo o que o controle digita: os atalhos da
lista, e o teclado na tela em L3/R3.

A lista de teclas mostra **os vinte botões**, inclusive os que **não** digitam
nada — antes ela escondia os onze sem tecla e parecia completa. E a legenda diz,
com todas as letras, que **nenhum atalho de fábrica digita uma letra**: os de
fábrica são Super, PrintScreen, Alt+Tab, Alt+Shift+Tab, Enter, Delete e
Backspace. Para escrever texto, o caminho é o teclado na tela do L3.

> **NOTA DATADA — 09/08/2026: as três regiões do touchpad saíram desta aba.**
> Elas existiam (`Touchpad — lado esquerdo/meio/direito`, de fábrica Backspace,
> Enter e Delete) e foram retiradas por decisão dela, junto com a devolução do
> touchpad ao sistema. A razão é que o produto não pode oferecer duas coisas
> que se atropelam no mesmo dedo: com o touchpad de volta ao libinput o clique
> dele já é clique de mouse, e somar a tecla faria um clique **apagar texto**
> sem ninguém pedir. O runtime também se cala — quem responde é o estado real
> do nó, não o modo. Voltar é a mesma decisão do outro lado: o touchpad
> passaria a ser do Hefesto de novo, e as três regiões voltam junto. Uma coisa
> não vai sem a outra.

As duas colunas já foram abas separadas. Voltaram juntas em colunas porque
empilhadas elas inflavam a altura mínima da janela inteira — o `GtkNotebook`
adota o maior mínimo entre todas as páginas.

O interruptor do mouse só fica disponível no modo **Controlar o PC**. Fora dele,
ligar o mouse derrubaria o controle virtual e os jogadores do co-op no meio do
jogo, sem aviso — por isso ele nasce bloqueado, com a razão escrita em texto.

## O rodapé

Vale para qualquer aba: **Aplicar**, **Salvar Perfil**, **Importar** e **Restaurar
Default** persistem o que está editado para o perfil corrente.
