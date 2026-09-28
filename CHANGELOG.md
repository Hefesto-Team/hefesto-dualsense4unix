# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). A série 0.9.4.x tem quatro números; onde um formato exige três, a quarta casa vira metadado de build (`0.9.4+5`).

## [Unreleased]

### Adicionado

- Uma janela nova, com dez abas: Jogar, Controles, Gatilhos, Iluminação, Vibração, Navegação, Lançadores, Conexões, Sistema e Perfis.
- Cada controle é um jogador, com gatilhos, luz, vibração, microfone, alto-falante e máscara próprios no perfil.
- Mira Virtual: o giroscópio de cada controle vira o analógico direito; no modo Navegação, ele move o cursor.
- Microfone e alto-falante de cada controle por cabo e por Bluetooth, com os quatro microfones ligados ao mesmo tempo.
- A vibração fina do DualSense, que o jogo manda como áudio, chega ao controle em jogos pelo Proton, no cabo e no Bluetooth.
- Troca de botões no perfil, e a troca chega ao jogo.
- PS + L3 troca a máscara sem sair do jogo.
- Um perfil por jogo nasce sozinho na primeira vez que o jogo abre.
- Perfis por jogo também no Heroic e no Lutris: o jogo é reconhecido pela janela.
- A aba Lançadores, com um cartão por lançador e uma lista de jogos que abrem sem nada do Hefesto.
- A aba Conexões: parear pelo botão Conectar, ver o modo de conexão de cada controle e mapear as portas USB do computador.
- O Modo Freestyle, na aba Jogar.
- Três níveis de brilho para as luzes de número, no cabo e no Bluetooth.
- O menu da bandeja, que abre a janela e sobe sozinho no login.
- `./uninstall.sh --dry-run` mostra o que seria removido, sem remover nada.
- `hefesto-dualsense4unix esquecer-controles` guarda a memória dos controles numa pasta e a devolve com `--restaurar`.
- O `doctor` mostra, para cada jogador, o modo pedido e o controle virtual que está no ar.

### Mudado

- O menu de aplicativos e o `hefesto-dualsense4unix-gui` abrem a janela nova, em Wayland nativo.
- O botão do microfone liga e desliga o microfone daquele controle, em vez de calar o microfone do sistema.
- O DualSense físico fica fechado para os outros programas: só o controle virtual do Hefesto recebe o acesso da sessão, e o Modo Nativo devolve o físico ao jogo.
- A versão fixa do Proton passou para o GE-Proton 11-7, que leva o som e a vibração fina do controle ao jogo.
- Perfil e jogo novos nascem com tudo ligado: microfone, giroscópio, touchpad, vibração e gatilhos.
- O Perfil Econômico de cada controle, na aba Conexões, gasta menos bateria sem desligar nenhum recurso.

### Removido

- A janela antiga, de onze abas.
- O applet do COSMIC; a bandeja cobre o que ele fazia.

### Corrigido

- O primeiro aperto no botão do microfone depois de conectar desligava o microfone em vez de ligar.
- Um controle que passa do Bluetooth para o cabo mantém o número de jogador.
- Um controle no cabo que perde a conexão por erro de USB volta sozinho.
- Com a Steam aberta, a cor da barra e o número de jogador voltam em até um segundo.
- A janela deixou de travar enquanto espera o serviço responder.
- O botão Salvar apagava ajustes que as abas já tinham gravado no perfil.

## [0.9.4.5] — 2026-08-20

### Adicionado

- Ao trocar de modo, os controles piscam três vezes na cor do modo novo e voltam à cor do perfil.
- PS + R3 troca de modo sem sair do jogo, e o Hefesto lembra o modo que funcionou em cada jogo.
- O instalador descobre a família da distribuição (apt, dnf ou pacman) e instala as bibliotecas que o produto precisa.

### Corrigido

- O instalador parava sem mensagem em máquina sem BlueZ.
- O Hefesto não encontrava a `libhidapi` instalada.
- O giroscópio chegava ao jogo com um terço das amostras faltando.
- O instalador travava em máquina sem Bluetooth.
- No Modo Nativo, a aba Vibração dizia «Vibração travada» com o motor parado.
- O `doctor` não cobrava duas dependências obrigatórias.
- O `uninstall.sh` não desfazia a troca do BlueZ.
- O botão Parar da vibração não parava o motor.
- Com vários controles, o controle deslizante do microfone mexia no microfone de outro jogador.

## [0.9.4.4] — 2026-08-19

### Adicionado

- A lista de exceções liga o Steam Input nos jogos que só funcionam com ele.
- PS + seta para a direita passa para o próximo modo.
- A aba Início diz por onde o jogo recebe o controle.

### Corrigido

- Travar o Proton trocava a versão que você tinha escolhido para um jogo; agora a escolha é respeitada.
- Uma troca de modo recusada com o jogo aberto recriava o controle virtual em laço, e o jogo perdia o controle.
- Algumas cores do tema eram aplicadas e não apareciam na janela.
- Um aperto no botão do microfone podia alternar o mudo várias vezes.

## [0.9.4.3] — 2026-08-18

### Corrigido

- O `install.sh` parava com código 2, sem mensagem.
- O Proton não era extraído em sistemas com Python 3.10.
- O serviço de pareamento Bluetooth do Hefesto reiniciava em laço no systemd 249.
- A janela abria maior do que a tela, com o rodapé escondido.
- O ícone da bandeja sumia da barra, e fora do COSMIC aparecia como três pontinhos.
- O cartão do controle alternava entre a frase curta e a longa.
- Um controle acendia um número de jogador e era chamado por outro.

### Mudado

- O BlueZ corrigido é instalado a partir do código-fonte onde o pacote da distribuição não serve.

## [0.9.4.2] — 2026-08-13

### Corrigido

- Por Bluetooth, a cor e o número de jogador também saem por uma segunda rota, que funciona com a Steam aberta.
- A luz do botão do microfone apagava sem desmutar o microfone.
- O serviço varria a lista de processos inteira duas vezes por segundo.
- As métricas não eram encerradas quando o serviço desligava.

## [0.9.4] — 2026-08-12

### Mudado

- A intensidade da vibração faz o que o nome diz: Balanceado entrega o que o jogo pediu, e Máximo amplifica.

### Corrigido

- A vibração que o jogo manda parava quase na hora, porque o Hefesto escrevia por cima meio segundo depois.
- Com a Steam aberta, a barra de luz não pegava a cor por Bluetooth; a cor e o número de jogador passam a ser escritos depois que os controles terminam de conectar.
- Em co-op, só um controle virava jogador.

## [0.9.3] — 2026-08-10

### Corrigido

- Um desligamento feito numa sessão anterior podia deixar o Hefesto fora dos dois modos de jogo, sem aviso. A aba Início passa a avisar, com as duas saídas.

## [0.9.2] — 2026-08-10

### Corrigido

- O botão Aplicar não aplicava o volume, o mudo e a saída do alto-falante.
- O editor avançado abria com os campos da regra vazios, e salvar assim tirava o perfil da troca automática.

## [0.9.1] — 2026-08-10

### Corrigido

- O jogador 2 perdia o controle quando o controle do jogador 1 saía.
- O ajuste do microfone passa a valer em todos os formatos de instalação.
- O applet do COSMIC dizia «Ligado» sobre um microfone que perdia para o eco.
- O `doctor` acusava como falha o microfone do controle promovido pelo próprio instalador.

## [0.9.0] — 2026-08-10

### Adicionado

- A aba «No jogo» mostra, recurso por recurso, o que chega ao jogo, e diz quando o perfil daquele jogo não entrou e o que ele exigia.
- O instalador instala o teclado na tela que o L3 abre: wvkbd no Wayland, onboard no X11.

### Mudado

- «Jogar direto (Sony)» passou a se chamar «Conexão Nativa (Sony)».
- O co-op deixou de ser opção: todo controle ligado vira jogador.

### Corrigido

- O touchpad voltou a ser o touchpad do sistema em todos os modos.
- A janela passa a dizer que o teclado emulado não digita letras.
- Com o Steam Input ligado, o jogo via três controles.
- O botão «Ligar» do microfone desfazia o ajuste que faz a voz vencer o eco.
- O volume, o mudo e a saída do alto-falante voltaram a ser gravados no perfil.
- A bateria do controle chega ao jogo, em vez de ficar em 5%.
- «Controlar o PC» entrava sem som.
- A janela trocava sozinha o nome do perfil, e o Salvar gravava no arquivo errado.
- A janela travava num aviso que abria fora da tela.

### Segurança

- O instalador corrige o `JustWorksRepairing=always` que uma versão anterior escrevia em `/etc/bluetooth/main.conf`: com ele, um aparelho que clonasse o endereço de um controle pareado podia trocar a chave sem confirmação.

## [0.8.0] — 2026-08-02

### Mudado

- A aba Status mostra o que chega ao jogo, e não só o que existe.

### Corrigido

- Sete predefinições de gatilho não faziam nada; três delas mandavam o modo desligado.
- O controle tremia sem parar quando o jogo mandava a parada com todos os campos zerados.
- Os 60% de cima do controle deslizante do alto-falante não faziam nada; o alto-falante ganhou o pré-amplificador e a rota de saída.
- Por Bluetooth, o botão do microfone mutava o microfone de outro aparelho.
- Um perfil sem opinião sobre a máscara virava Xbox ao ser salvo.

## [0.7.0] — 2026-08-01

### Adicionado

- `HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED=1` liga as métricas Prometheus, e `HEFESTO_DUALSENSE4UNIX_METRICS_PORT` escolhe a porta.

### Mudado

- A aba Status reorganizada: o botão do alto-falante foi para o bloco Alto-falante do cartão, e os botões dizem o que o clique faz.
- A máscara Xbox avisa o que o jogo deixa de receber nela.

### Corrigido

- Um ícone quebrado aparecia ao lado dos interruptores da janela.
- Os botões ocupavam largura demais na janela.

## [0.6.0] — 2026-08-01

### Adicionado

- O bloco Alto-falante: controle deslizante de volume, botão de mudo e devolução do volume ao controle.
- Um selo avisa quando quem está mudo é o sistema, e não o controle.
- O perfil ganhou seção de alto-falante.

### Corrigido

- O clique do touchpad passou a chegar ao jogo.
- A aba Lightbar dizia que o Hefesto podia estar desligado quando só uma seção falhava.

## [0.5.0] — 2026-07-31

### Mudado

- A aba Status ocupa o espaço lateral que sobrava.

### Corrigido

- Desinstalar e instalar de novo desligava seis correções dos módulos de kernel até o próximo boot.
- A janela perdia a sincronia quando o serviço demorava a responder.
- O botão Restaurar Padrão falhava em instalação por pacote.
- Salvar perfil passou a reconhecer o arquivo pelo disco, e não pelo texto digitado.
- O NOTICE passou a declarar os três módulos de kernel GPL-2.0 que acompanham o código.

## [0.4.0] — 2026-07-30

### Corrigido

- O R1 trocava de aplicativo dentro do jogo. O teclado emulado ganhou interruptor próprio, e a tecla Alt não fica mais presa.
- O perfil passou a guardar modo, máscara, co-op e modo jogo.
- O microfone voltou a gravar a voz, e não o som do próprio controle.
- O pacote .deb não ativava o serviço, o módulo de kernel ficava depois do `apt remove`, e o pacote Flatpak não era construído.

## [0.3.0] — 2026-07-28

### Mudado

- A aba Status reorganizada.

### Corrigido

- O desempate entre perfis seguia a ordem alfabética; agora, em empate, vence o perfil que já está ativo.
- Salvar um perfil pela janela o rebaixava a perfil genérico com prioridade zero.
- O teto da prioridade subiu de 100 para 200, para um perfil de jogo poder vencer o genérico.
- Aplicar um rascunho de perfil dizia sucesso com seções falhando; o rodapé diz o que não entrou.
- O microfone voltou à faixa, com um botão que funciona, e o diagnóstico dele deixou de reprovar por causa do alto-falante mudo.
- O instalador passou a chamar a correção do microfone.
- O detector de janela volta a funcionar depois de uma falha.

## [0.2.0] — 2026-07-26

### Adicionado

- Co-op pela janela, com quatro controles numerados de 1 a 4.
- Número de jogador editável.
- Mudo do microfone e volume do alto-falante pelo serviço.
- O envelope do DualSenseX passa a ser aceito, e a instrução `TriggerThreshold` funciona.
- Um teto de segurança contra vibração presa.

### Mudado

- O teto de silêncio da vibração caiu de 6 s para 3 s.
- A máscara do controle responde igual pela janela e pelo terminal.

### Corrigido

- O jogo via quatro dispositivos onde havia um controle.
- Um controle sozinho nascia «jogador 2».
- Ajustes se perdiam ao trocar de aba.
- O motor girava para sempre quando o comando de parada se perdia.
- Depois de reiniciar, o sistema carregava o módulo de kernel antigo.
- O serviço não era instalado.

## [0.1.2] — RETIRADA

Publicada e retirada no mesmo dia. Não instale esta versão; a 0.2.0 a substitui.

## [0.1.1] — 2026-07-25

### Adicionado

- «Deixar tudo pronto» e «Este jogo não funciona», na aba Sistema.
- Fechar e reabrir a Steam com permissão; com um jogo aberto, o Hefesto recusa.
- O cadeado da troca automática de perfil aparece na tela.

### Corrigido

- O microfone voltava mudo.
- Perfis alternavam sozinhos.
- O modo jogo não ligava sozinho.
- A numeração dos controles mudava entre inicializações, e dois controles apareciam como jogador 1.
- Um segundo Pro Controller clone não aparecia para o sistema.
- O 8BitDo em modo PS4 passou a conectar por Bluetooth de primeira.
- O serviço ficava num laço a cerca de uma vez por segundo.

## [0.1.0] — 2026-07-24

Primeiro lançamento público, em alfa.

### Adicionado

- Sensores na aba Status: giroscópio, microfone com medidor de nível e touchpad.
- Identidade visual nova.
- As abas Mouse e Teclado viraram uma só, a Navegação.
- Cópia dos pareamentos Bluetooth a cada conexão.

### Corrigido

- A vibração continuava quando o jogo fechava no meio do efeito.
- O aviso de vibração travada aparece em qualquer aba.
- O mesmo controle aparecia com dois números na janela.

As versões anteriores à 0.1.0 foram de desenvolvimento interno.
