# A janela, aba por aba

A janela principal tem nove abas. Esta página diz o que cada uma faz e o que se
ajusta nela.

> **Sobre as capturas.** Foram feitas em 25/07/2026, com a interface já
> redesenhada e **quatro controles conectados por Bluetooth ao mesmo tempo** —
> dois DualSense, um Nintendo Pro e um 8BitDo em modo DirectInput/PS4 —, que é o
> cenário de co-op que o projeto persegue. Na aba Sistema, o bloco "Detalhes
> técnicos" aparece borrado de propósito: o log traz o endereço Bluetooth real
> dos controles desta máquina, e os gates de anonimato do projeto não varrem
> imagens.

## Início

![Aba Início](assets/readme_inicio.png)

A aba de decisão. Tem o seletor **"O que o controle faz agora"** com os três
modos (Controlar o PC · Jogar pelo Hefesto · Jogar direto (Sony)), o seletor de
máscara **"O jogo vê o controle como:"**, o cadeado **"Não trocar de perfil
sozinho ao abrir um jogo"**, e um card por controle conectado com o número de
jogador. Os avisos de degradação (controle virtual em modo reduzido, jogo aberto
sem o atalho da Steam) aparecem no topo dela.

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

## Navegação DSX

![Aba Navegação DSX](assets/readme_navegacao_dsx.png)

Mouse e teclado lado a lado, em duas colunas. À esquerda, a emulação de mouse:
liga/desliga, velocidade, rolagem, escolha entre stick e touchpad. À direita, o
mapeamento de botão para tecla.

As duas já foram abas separadas. Voltaram juntas em colunas porque empilhadas
elas inflavam a altura mínima da janela inteira — o `GtkNotebook` adota o maior
mínimo entre todas as páginas.

O interruptor do mouse só fica disponível no modo **Controlar o PC**. Fora dele,
ligar o mouse derrubaria o controle virtual e os jogadores do co-op no meio do
jogo, sem aviso — por isso ele nasce bloqueado, com a razão escrita em texto.

## O rodapé

Vale para qualquer aba: **Aplicar**, **Salvar Perfil**, **Importar** e **Restaurar
Default** persistem o que está editado para o perfil corrente.
