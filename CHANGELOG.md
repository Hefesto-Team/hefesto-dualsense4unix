# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). A versão tem três números e, numa correção entre duas versões, quatro (0.9.5, 0.9.5.1); onde um formato exige três, a quarta casa vira metadado de build (`0.9.5+1`).

## [Unreleased]

## [0.9.5.1] — 2026-10-29

### Adicionado

- Com a modificação do KytyPS5 ligada, ele aparece entre os lançadores, os jogos dele entram na escolha do perfil e cada jogo pode ter o seu perfil.
- O prontuário mostra, para cada jogo, o que a Steam e os arquivos do jogo dizem sobre controle: se ele entende o DualSense, se conta com a tradução do Steam Input ou se só declara Xbox, e quais modelos de controle Sony o jogo conhece. Ele explica por que a capa da Steam pode dizer que o controle não é suportado.
- Antes de trocar o Proton que o Hefesto fixa, a versão nova passa por uma prova automática da vibração, do gatilho e do microfone; se alguma falha, o Proton fixado continua o mesmo.
- O Hefesto passa a servir o giroscópio, o acelerômetro e o touchpad de cada controle pelo protocolo DSU (cemuhook), e emuladores como Cemu, Dolphin e Azahar os recebem em qualquer máscara, inclusive a Xbox, pelo cabo e pelo rádio.
- A lista de navegação interna na aba Navegação não fazia nada. Agora o interruptor liga o tipo escolhido, interno ou do computador. Na interna, R1 e L1 trocam de aba em círculo, cada controle tem a sua seleção com moldura na cor do plástico, o direcional move, o X aciona e o Start salva no perfil.
- O círculo do L3 e do R3 no cartão do controle mostrava só a posição da mão, mas com o analógico virtual ligado o jogo recebe outra coisa. Agora um anel verde marca o que o jogo vê, ao lado do ponto da mão, em cada controle.
- O Hefesto depende de ferramentas externas, como o Bluetooth, a Steam e o PipeWire, e uma atualização delas podia quebrar algo sem explicação. O diagnóstico agora tem um bloco de nove contratos de fora, só de leitura, que nomeia o que falhou e o comando que o confere.
- O botão Modo Steam da aba Navegação não fazia nada. Agora o Modo Big Picture na Steam, em qualquer modo de conexão, faz o direcional, a Cruz e o Círculo virarem setas, Enter e Esc quando a janela da Steam está na frente, por cabo ou rádio, nos quatro controles.
- Os números da faixa de rádio não diziam se um controle com poucos pacotes estava longe ou sofria interferência. Agora o Hefesto lê o sinal de cada controle no rádio e dá uma frase: longe, interferência ou adaptador cheio. Sem o sinal, a linha fica neutra e diz que não sabe.
- Para um controle externo, a cor e a família de botões declaradas não apareciam no cartão, e só se gravavam editando um arquivo à mão. Agora o cartão em Jogar e Conexões mostra a cor na borda e as letras da face, e a Conexões ganha três listas para declarar modo, botões e cor.
- O botão Começar da aba Calibrar não fazia nada, e o texto prometia gravar o zero no controle, o que o Hefesto nunca faz. Agora o Começar mede o zero com o controle parado e o guarda no Hefesto, sem escrever nada no aparelho.
- A frase O jogo pinta por cima e o termo Jogo decide confundiam. Agora a Iluminação e os Gatilhos têm o par Modo Automático e Modo Personalizado no alto. No Automático, a luz fica na cor do plástico e os gatilhos sem efeito; no Personalizado, você altera as cores e os efeitos.
- O Wi-Fi sumia da aba Conexões por desenho, e o mouse e o teclado sem fio não apareciam. Agora os outros dispositivos sem fio aparecem, com a faixa medida, e quando a linha do Wi-Fi não cabe na seção, um selo compacto toma o lugar da linha.
- Cada controle aparece com o desenho do modelo; o botão Acrescentar hub pergunta em qual entrada ele está.
- Com a opção ligada na aba Iluminação, a barra de luz pulsa ou muda de cor a cada tiro e volta sozinha à cor do perfil, sem passar de três piscadas por segundo.
- Em jogos que só falam Xbox, o início de cada tiro passa a dar um toque curto e nítido no controle, em vez de uma vibração mole.
- Escolher um estilo no perfil do jogo (Arco, Tiro…) liga junto o gatilho, a luz, a háptica e os motores dos dois lados, que reagem ao jogo, também no modo Xbox.
- Em jogos que não configuram o gatilho, o controle passa a trocar entre o estalo de tiro único e as batidas de rajada conforme o ritmo em que você atira.
- L2 e R2 podem virar o botão do mouse ou uma tecla, mesmo com o controle jogando como Xbox, e o analógico esquerdo só mexe o cursor se você escolher.
- Com a opção ligada, o estalo de cada tiro toca no pequeno alto-falante do controle, como no PlayStation, sem calar o som do jogo.
- A opção «Só dentro do jogo», da função do teclado, deixa de recusar e passa a valer: o teclado emulado só age com um jogo ativo, em qualquer modo e conexão.
- Em jogos com som posicional, o toque do tiro passa a vir do lado esquerdo ou direito do controle, conforme o lado de onde o som chega.
- A aba Lançadores ganha uma seção recolhível com as modificações instaladas, de onde vêm, o que fazem no controle, e a chave para ligar ou desligar cada uma.
- Uma modificação com permissão pode acompanhar a vibração que o jogo manda a cada controle, com o número do jogador, e sabe quando o jogo fecha.
- Cada gesto dos acessórios dá um toque curto no controle e acende as luzinhas no nível escolhido; num jogo marcado «Adulto», a barra pode pulsar na cor escolhida, mais rápido conforme o nível, nunca mais que uma vez por segundo.
- Um perfil pode levar as marcas Visual novel e Adulto, além do estilo; o campo do estilo mostra o estilo escolhido em vez do travessão.
- Dá para instalar uma modificação a partir de um endereço git ou de uma pasta. Ela roda separada do serviço, só faz o que as permissões mostradas permitem e pode ser desligada ou removida sem deixar resto.
- Cada botão pode passar a alternar em vez de segurar, repetir enquanto segurado, ou dar outra ação no toque longo e no toque duplo, por jogador e em todo jogo.
- O cursor do controle pode ir devagar enquanto um botão está apertado, clicar sozinho quando para, e prender o clique para arrastar sem segurar; a zona morta e a curva passam a se ajustar.
- A aba Vibração mostra a vibração pelos seus toques e pelo touchpad em cada perfil. A engrenagem de cada extensão abre as opções por cliques, e a janela dos acessórios mantém à vista o nível e o botão «Parar tudo».
- quem usa o Hefesto sem a janela liga o Freestyle, escolhe a intensidade da vibração, liga o microfone e troca a máscara pela linha de comando
- Uma modificação pode trocar as cores da interface. O tema só troca cores, não esconde botão nem busca nada na rede, e é recusado se o texto ficar ilegível.
- Na aba Vibração, o touchpad pode virar fonte de vibração: o lado tocado vibra o motor daquele lado, e a altura do dedo dá a força; no modo de mistura, deslizar faz a vibração atravessar o controle.
- Cada botão pode ignorar aperto repetido rápido demais ou curto demais, e um botão pode travar até o próximo, para fazer combinações e gestos sem apertar dois ao mesmo tempo.
- Cada jogador pode ajustar a zona morta, a curva e a sensibilidade dos analógicos e dos gatilhos, inverter cada eixo, trocar os dois analógicos e escolher uma predefinição para jogar com uma mão.
- Com a modificação dos acessórios ligada, segurar o PS e tocar o R2 liga e sobe a intensidade, o L2 desce e, até o fundo, para tudo; o R1 e o L1 trocam o perfil de vibração. O jogo não recebe esses toques.
- Na aba Vibração, cada perfil escolhe se o controle vibra só pelo jogo, pelo jogo e pelos seus toques, ou só pelos seus toques; o analógico, os botões, os gatilhos e o chacoalhar ganham uma vibração fina, e o jogo nunca fica mais fraco.
- Cada aparelho USB ganha tipo e nome (o que ele diz de si e o que o sistema sabe dele); um hub de dois lados conta como um só; um aparelho que sabe 5 Gb/s e ficou a 480 Mb/s é apontado; e o que entra, sai, volta ou muda de velocidade fica registrado com a hora.
- O registro da janela passa a dizer por que ela fechou, o tamanho e o monitor a cada mudança, e quando a tela está mostrando o último estado conhecido porque o serviço não respondeu. Isso ajuda a achar a causa de uma janela que some ou que mostra dado velho.
- O diagnóstico agora mostra a versão do firmware de cada controle e avisa quando ela é antiga, dizendo onde atualizar com segurança. O Hefesto não atualiza firmware.
- Um aparelho Bluetooth sem tipo conhecido ficava com «?» para sempre. Agora clicar no «?» abre uma grade com nove tipos (Controle, Fone, Caixa de som, Teclado, Mouse, Celular, Relógio, Acessório e Outro), e a sua escolha vale mesmo depois de reabrir.
- O mapa do controle ganha a aba Sequência: um botão pode tocar uma sequência gravada de botões, com os tempos que você fez, uma vez, repetindo ou alternando, em ritmo gravado, rápido ou devagar. O jogo vê só os passos da sequência.
- Para desligar um controle sem tirar o Bluetooth do computador, basta segurar o botão PS por 10 segundos: só aquele controle desliga, e os outros do mesmo adaptador seguem. Vale no rádio; no cabo o Hefesto recusa o desligar.
- Com o Modo automático ligado na aba Controles, um perfil Terror manda o som do jogo também para o alto-falante do controle e abre o microfone dele, com ou sem fone.
- As extensões do Hefesto podem assinar dois avisos novos: o efeito de gatilho que o jogo pede a cada controle e a intensidade da vibração fina, que alguns jogos mandam como áudio. Cada aviso diz o controle e o jogador, e zera quando o jogo fecha.
- Jogos e aplicativos que falam Buttplug, como os da Intiface, agora podem fazer o DualSense vibrar pelo Hefesto, sem brigar com ele pelo controle. É uma extensão local: cada controle aparece como um aparelho com força e teto próprios, escolhidos na janela da extensão, e nada passa pela nuvem.
- Quando um jogo traz no disco o sinal de que precisa de uma variável de ambiente para abrir, e a peça que a variável pede está lá, o Hefesto a passa ao jogo ao lançá-lo. Quando falta a peça, o prontuário do jogo avisa.
- O mapa mostra cada hub como um só, o nome de cada aparelho, o que ficou mais lento do que sabe ser, e um registro com a hora do que entrou, saiu, voltou ou mudou de velocidade.
- O diagnóstico agora diz, numa frase, quando o kernel carregou o módulo de fábrica do controle e o microfone pelo Bluetooth deixou de funcionar, e o que fazer para voltar.
- A lista de perfis passa a mostrar a data de criação e a da última mudança de cada perfil.
- A troca de botões valia para o perfil inteiro. Agora, no mapa do controle, o campo «Vale para» permite trocar os botões de um controle só, escolhido pela cor do plástico, e a troca dele vence a do perfil, botão a botão.
- Cada controle tem o touchpad Ligado ou Desligado, por cabo ou Bluetooth. Desligado, o toque não chega ao jogo nem vira mouse do sistema enquanto o jogo está aberto. Ligado, o toque vai ao jogo que tem controle de toque e, nos outros, move o cursor.
- Com a extensão de acessórios ligada, você marca em quais jogos os acessórios seguem a vibração do controle e ajusta a força de cada canal (vibração, gatilho e háptica) em cada acessório.
- Botões grandes, pedais e chaves de toque que o Linux vê como teclado ou joystick USB agora podem virar botões de um controle. Na linha do aparelho, em Conexões, use «Usar como botões de…», escolha o controle e o botão do desenho para cada tecla.
- O diagnóstico passa a avisar quando a versão instalada do GE-Proton, do SDL ou da configuração de som do sistema muda o que o jogo vê do controle, em vez de o efeito sumir sem explicação.
- cada controle informa a forma que o jogo vê (DualSense, Xbox 360 ou Pro Controller) e quais funções chegam a ele
- com a máscara Pro Controller, o diagnóstico diz que o jogo recebe os botões, os analógicos e a vibração, sem o giroscópio e as luzes de jogador, porque o Proton só abre o acesso direto ao DualSense e ao DualShock 4
- A linha Efeito da aba Iluminação mostra oito efeitos com uma frase dizendo o que se vê em cada um. Um interruptor Sem piscar deixa toda a luz do controle em transição lenta, para quem é sensível a luz.
- Duas linhas novas na aba Vibração: Efeito háptico, abaixo do Sensor háptico, e Efeito imersão, abaixo dos motores esquerdo e direito. Cada controle escolhe o seu.
- Na lista de jogos da extensão Lovense, os jogos com suporte à Lovense aparecem marcados, e quem não alcança o computador mostra o que mudar no menu do jogo.
- Doze efeitos novos de imersão no gatilho: Golpe leve, Golpe pesado, Golpe carregado, Escudo que aguenta, Besta, Agarrar, Energia que cresce, Clique no meio, Mira firme, Motor no acelerador, Duas travas e Pique que cansa. Cada um sente a mão do jogador e se adapta ao tempo do aperto.
- Além do toque seco de hoje, o controle passa a ter cinco formas de sentir a háptica: Impacto, Estalo, Guarda, Aparo e Som no corpo. A forma escolhida vale nos quatro controles, e o Sensor háptico segue como o ganho de todas.
- O efeito de imersão dos motores passa a ter cinco padrões: Tranco, Batida, Onda, Coice e Pancada do lado. Eles tocam quando o jogo não vibra, junto do gesto que o estilo já reconhece, e param enquanto a Metralhadora vibra o gatilho.
- O Hefesto reconhece pela pasta os jogos que conversam com brinquedos Lovense e lê, sem alterar nada, o endereço e a porta que o jogo guardou, para saber se ele alcança o computador.
- O que um jogo pede a um brinquedo, recebido por uma extensão, pode chegar a outra extensão que a pessoa ligou, sem as duas se falarem por fora do Hefesto. Quando a extensão que mandou sai, a outra recebe o zero.
- Quem desinstala o Hefesto ouve a pergunta se quer voltar o PipeWire às versões que a máquina tinha antes do install; a resposta sim devolve os pacotes, e a trava do apt que o install pôs sai nos dois casos. Com a Steam aberta, o passo recusa e diz por quê.
- Os efeitos de imersão da aba Gatilhos ganham o tempo do aperto: o pino que falha endurece ao apertar, a rajada sobe a força enquanto você segura e o cano esquenta depois de três segundos, com a variante do estilo do jogo. Só nos jogos que não escrevem os gatilhos, por cabo e por Bluetooth, em cada controle.
- Um perfil com «Aplicar em: Eventos» passa a entrar ao conectar um controle, ao abrir o programa ou quando o seu comando dá certo
- O `hefesto doctor` lê o Proton fixado de cada jogo e diz quando ele sumiu do disco.
- Um jogo GDK sem o ajudante de login aparece no prontuário com o aviso de que abre só local, sem conta nem amigos, e com o que instalar para entrar na conta.
- A janela de uma extensão não mostrava o que ela estava fazendo. Agora a coluna «Agora» mostra nível, perfil e aparelhos que a extensão declara, atualizados com a janela aberta, e o botão «Parar tudo» aparece no topo nas extensões que o oferecem.
- Uma extensão instalada pelo endereço do repositório recebe a versão nova sem precisar clicar em Atualizar; a que pede permissão nova espera você aceitar.
- As extensões do Hefesto ficam em repositórios próprios, com o aviso de uso e o endereço para instalar.
- Ao conectar, o controle acende a barra na cor dele, dá um toque e clica o gatilho uma vez. O toque de cada um tem uma nota diferente, e no escuro a mão sabe qual controle é qual.
- Uma extensão nova deixa a interface do Hefesto em fundo claro, com os textos e os destaques escurecidos para continuar legíveis.
- O Point and click ganha um gatilho que clica como um mouse, o Furtivo prende o fôlego na mira, o Souls/RPG faz o golpe forte ecoar, a Simulação sente o chão pelo corpo do controle, o Retrô vibra como os consoles antigos, a Corrida acende a barra com o acelerador e a Maratona só avisa a bateria, devagar.
- A extensão da Lovense passa a ser uma só, com o servidor Buttplug do controle e a ponte do Game Mode juntos; ao atualizar, a antiga sai sozinha e as suas escolhas passam para a nova.
- A janela Configurar de uma extensão ganha a coluna «Agora», com o estado ao vivo de cada ponte e de cada aparelho, ao lado dos ajustes em abas; os toques por botão valem para os quatro controles, e a aba Conexões mostra os aparelhos que as extensões ligadas trazem.
- A extensão da Lovense passa a levar a cena do jogo ao brinquedo de verdade, pelo adaptador USB da Lovense ou pelo Bluetooth do computador, e cada botão do DualSense pode ter o seu toque no brinquedo.
- A aba Iluminação ganha o efeito «Ao som»: o brilho da barra segue a energia do som que toca no computador, e os graves puxam a cor escolhida e os agudos o branco. Ele ouve só a saída de som, nunca o microfone, e só enquanto um controle usa o efeito.
- A aba Iluminação ganha a Aurora, um degradê lento entre cores que você escolhe; as Estrelas, que cintilam nas luzinhas do jogador; a cor da bateria de cada controle, de verde a vermelho; e a cor da temperatura, do azul ao vermelho, pela leitura mais quente da máquina.
- A aba Iluminação ganha o grupo «Que reage»: a barra acende na cor do símbolo apertado, gira de cor conforme você inclina o controle, ou segue a posição do dedo no touchpad. Cada controle reage à própria mão, e apertos rápidos não viram estrobo.
- Com o estilo Corrida ou Simulação, um jogo que publica a telemetria (o Data Out do Forza) faz o L2 pulsar quando a roda trava e o R2 vibrar quando o carro patina. A troca de marcha e a batida também chegam ao controle.
- No modo DualSense, o controle que o Hefesto entrega ao jogo pode se apresentar como DualSense comum, e não só como DualSense Edge. O DualSense de plástico continua escondido do jogo, no cabo e no Bluetooth, sem que o controle virtual some junto.
- No modo DualSense, o Hefesto lê os arquivos do jogo antes de ele abrir. Se o jogo conhece o DualSense Edge, o controle virtual chega como Edge; se ele só conhece o DualSense comum, chega como DualSense comum; se não dá para saber, fica como hoje. Ao fechar o jogo, o controle volta ao Edge.
- Jogos Xbox não têm canal para o gatilho do DualSense, então ele ficava calado. Agora, nos estilos Ação, Luta, Souls, Terror, Aventura e Esportes, o gatilho vibra com a força do rumble do jogo quando o dedo está apertado. Gatilho solto não vibra, e o que o jogo escreve no gatilho tem prioridade.
- Uma extensão de tema pode abrir espaço para o seu CSS: você escreve as regras de layout e de cor que quiser, o Hefesto as aplica por cima do tema sem reabrir a janela, e desligar a opção devolve o tema como era.
- Os botões de fechar, maximizar e minimizar ficam do lado do sistema; uma extensão de tema, como o Tema claro, pode levá-los para a esquerda, e a cor e o lado se escolhem separados.
- A lista de efeitos da aba Iluminação ganha Ondulação, Vaivém, Enche e Respira em cores; os três primeiros correm também pelas luzinhas do jogador, por cabo e por Bluetooth, em cada controle.
- A lista «Padrão dos motores» da aba Vibração ganha Ressoar, um golpe nos dois motores com uma cauda grave que decai no esquerdo, e Ricochete, um golpe num lado com respostas mais fracas no outro, como uma bola quicando. A força respeita o multiplicador e o teto do perfil de bateria.
- A janela «Configurar» de uma extensão pode ter um botão que age na hora, a lista dos aparelhos que a extensão comanda, com ligar, testar e esquecer, e uma área para comandar o efeito ao vivo.
- Na extensão da Lovense, «Sacudir» e «Inclinar» dão força ao brinquedo pelo movimento de qualquer controle.
- Na Lovense, apertar o gatilho devagar, empurrar o analógico ou deslizar o dedo no touchpad muda a força do brinquedo na hora, em qualquer DualSense.
- Os brinquedos da Lovense com luz ganham, na janela da extensão, uma aba para acender, apagar e escolher a cor de cada um, pelo adaptador USB.
- Uma extensão pode reagir ao analógico, à pressão do gatilho e ao dedo no touchpad de cada controle, no cabo e no Bluetooth, e não só aos botões.
- Na janela «Configurar» de uma extensão, cada aparelho pode ter controles próprios, como uma chave ou uma paleta de cores, e o aparelho que não os tem não ganha nada.
- Na Lovense, arrastar na janela muda a força do brinquedo na hora; dá para segurar a força, repetir o desenho e gravá-lo como um efeito novo para um botão.
- Na janela de uma extensão com controle ao vivo, três botões escolhem o que acontece ao soltar: a força volta a zero, fica onde estava, ou repete o desenho.
- Uma extensão pode pedir o giroscópio e o acelerômetro de cada controle, no cabo ou no Bluetooth, para reagir a sacudir ou inclinar.
- Sem a permissão de ler um teclado ou um pedal, o acionador da aba Conexões não funcionava, e o diagnóstico não dizia por quê.
- Um botão, em todas as abas, impede que os controles mexam na janela do Hefesto; destravado, eles voltam a navegar.
- A aba Jogar escolhe DualSense, Xbox ou Nintendo Pro e ajusta cada controle sem trocar de aba

### Mudado

- Os balões do desenho do controle na aba Jogar apareciam em caixa alta, e algumas dicas traziam palavras em maiúsculas só para dar ênfase. A tela também oferecia máscaras que o produto não monta. Agora os textos voltam à primeira letra maiúscula e a recusa de máscara cita só as que existem.
- O Hefesto gravava a opção de lançamento no arquivo interno da Steam sem conferir depois, e a Steam pode apagar o lançador do Hefesto sem aviso. Agora ele relê o arquivo após gravar, o doctor avisa quando a Steam desfaz a opção, e o que existe de porta oficial passa a ser usado.
- O Hefesto e o doctor mexiam em arquivos internos do BlueZ, e o doctor aconselhava apagar arquivos de cache com sudo. Agora o estado do pareamento é lido e gravado pela interface oficial do BlueZ, e o doctor só aconselha o que a medida mostrar necessário.
- A aba Lançadores agora se chama Experimental e mostra as extensões em cima. Todo lançador tem os mesmos botões: Identificar no que não foi achado, e Criar perfis e Configurar no que foi achado. Os impedimentos viram uma dica no selo, sem janela.
- O Hefesto achava o cartão do shadPS4, mas não sabia qual janela era a dele, e a linha de todos os jogos do emulador não casava com a janela aberta. Agora os cartões do shadPS4 oficial e do shadps4-cosmic trazem os nomes de janela certos, e o perfil do emulador passa a valer no jogo que está aberto.
- O cartão do Vita3K achado no sistema não trazia o nome da janela, e a linha de todos os jogos só tinha o nome do arquivo, que não casa com o Vita3K do AppImage nem com o do AUR. Agora o cartão traz o nome certo da janela, e o perfil do emulador passa a valer no jogo aberto.
- Os avisos que apareciam só numa coluna de atenção da aba Jogar, limitada a três, passam a constar inteiros na lista do exame da aba Sistema, com o selo AVISO. Quem queria ver todos os avisos não precisa mais adivinhar o que ficou de fora.
- Os ajustes do analógico virtual de cada controle só existiam na tela Calibrar. Agora as abas Navegação, Conexões e Perfis mostram os mesmos números, lidos da mesma fonte, e acompanham uma mudança feita na Calibrar sem reabrir nada. A Calibrar diz em que perfil esses números ficam.
- O cartão aberto de um controle mostrava só a cor, a conexão e o modelo, enquanto o fechado mostrava o número do jogador. Agora o cartão aberto diz o nome que você deu ao controle ou o número do jogador, e esse número segue o jogador vivo, mesmo que o controle mude de lugar.
- Cada versão do Proton instalada fazia a Steam rodar testes demorados ao abrir e ocupava cerca de 1,5 GB. Agora, ao ligar o Fixar Proton, o Hefesto remove as versões que nem o pino nem nenhum jogo usam, e o recibo diz quantas saíram e quantos GB foram liberados.
- Nas abas Iluminação e Vibração, a linha Modelo mostrava só o número, o modelo e a conexão. Agora o nome que você deu ao controle vem antes do modelo, como número, nome, modelo e USB. Sem nome, a linha continua como era.
- Na aba Vibração, os três degraus da Força e os três do Testar agora ficavam em duas linhas, com larguras diferentes, e o Parar tinha só a letra vermelha. Agora cada trio fica lado a lado, com a mesma largura, e o Parar tem fundo vermelho e letra branca.
- A Mira Virtual e a Inclinação eram dois interruptores para a mesma ideia, e a tela só permitia o analógico direito. Agora o interruptor se chama Analógico Virtual, e o chip Usar como analógico virtual deixa escolher o lado esquerdo ou o direito, por controle.
- Em Outros dispositivos sem fio, a procura da faixa de um teclado ou mouse sem fio só respondia «Faixa não encontrada». Agora ela diz o que viu: a faixa, que o receptor salta de canal, que falta um aparelho no Bluetooth para medir, ou que o mapa de canais não mudou com ele.
- Em jogos pelo Wine ou Proton com vários DualSense, o jogo varria todos os áudios para achar o de cada controle e engasgava. Agora cada controle virtual nasce como um DualSense USB de verdade e o som dele aponta para esse mesmo aparelho, então o jogo o acha de primeira.
- Quando o adaptador aperta, o Hefesto reduz a vibração e o som de quem está parado em vez de calá-los, e a tela de Conexões mostra quantas pontes cabem em cada entrada.
- Com o Hefesto em Desligado, ele garante que a Steam Input da própria Steam fica desligada nos jogos com perfil, e a aba Jogar mostra isso travado, sem opção de ligar. O jogo fala direto com o controle, como no PS5.
- As dez abas, as telas que abrem por cima, a calibração e as dicas passam a se alcançar pelo controle e pelo teclado, e Esc e o Círculo fecham a tela aberta.
- Escolher o estilo Point-and-click num perfil já traz os botões de avançar, voltar o texto, pular, abrir o menu e esconder a caixa, e os ombros deixam de trocar de janela.
- Todo botão da interface passa a ter no mínimo o tamanho recomendado para quem tem pouca precisão, e o Sistema ganha um ajuste de tamanho da interface.
- Os pontos de interrogação e o «i» dos cartões saíram: as explicações aparecem ao passar o mouse no título, e cada conselho se ignora pelo × do canto. O pedido de conexão diz a cor do plástico do controle, como Galactic Purple, e não «Roxo».
- Cada controle ganha o interruptor do touchpad, o alto-falante tem três escolhas claras, e o giroscópio como analógico tem um interruptor só.
- Cada gatilho escolhe um efeito de acionamento e um efeito de imersão, como a metralhadora que sobe sozinha. Embaixo, você cria os seus efeitos e eles entram nas listas.
- A guia tem doze cores em duas fileiras, e cada controle pode usar luz fixa ou um efeito seu, como respirar ou piscar.
- Ligado, o terceiro modo é o Point and click; desligado, a Navegação faz o controle virar mouse e teclado. Cada modo do Desligado tem a cor em que a barra de luz pisca.
- O mapa do controle vira a tela de configurar os botões: escolha o perfil, clique num botão e diga o que ele vira, entre outro botão, mouse ou tecla. O botão trocado ganha a cor do tipo na linha e no desenho.
- As explicações dos dois mapas aparecem ao passar o mouse no título, em vez de um «?», e os dois passam a usar o mesmo menu do botão direito do restante do app.
- Cada botão do DualSense aparece com o que faz no computador, e a Steam pode navegar no lugar do Hefesto. Setas, touchpad e botões do touchpad também aparecem na aba, e as janelas separadas dão lugar ao mapa do controle.
- Clicar num perfil já o ativa e abre no editor. Visual novel e Adulto passam a ser estilos de jogo, e o editor pede o nome do jogo e onde aplicar o perfil.
- Um interruptor cuida das correções automáticas a cada jogo novo, em vez de quatro botões para a mesma ideia, e a coluna Interface aumenta letras e botões em três tamanhos: 100, 125 e 150%.
- O Modo automático deixa o jogo decidir a força, ajustada pelo estilo do perfil, e você cria efeitos de vibração como uma batida de coração.
- Os botões de interrogação saíram; a dica aparece ao passar o mouse. O botão direito abre o menu do Hefesto, e o Modo automático deixa o jogo mandar, ajustado pelo estilo do perfil.
- A força da vibração vai de 0 a 200% e a aba Gatilhos ganha a linha «Intensidade do gatilho», também de 0 a 200% por controle. Até 100%, o ajuste é aplicado pelo firmware do controle e vale também sobre o que o jogo manda; acima de 100%, o Hefesto reforça por software.
- A janela diz o que calibra, sem botões de interrogação; a ajuda aparece ao passar o mouse no título.
- Visual novel e Adulto aparecem na lista de estilos da aba Perfis, como FPS ou Corrida, em vez de marcas à parte.
- Cada ajuste se muda num lugar só; as outras abas só mostram o estado dele.
- A prova das versões novas do Proton passa a exigir a peça do GE-Proton que esconde o controle Sony do caminho do SDL; sem ela, a versão não entra no lugar da fixada, e o jogo segue vendo só o controle do Hefesto, também com o Proton em Wayland.
- O Piscar passa a subir e descer suave em vez de acender e apagar de uma vez, e o Arco-íris gira com uma cor diferente em cada controle, para você reconhecer o seu. Entram a Batida do coração, a Chama e a Maré. Nenhum efeito passa de três trocas por segundo.
- As imersões de gatilho já existentes passam a usar as batidas limpas da Metralhadora e o Disparo oficial. A Rajada sobe de verdade em três degraus, a Batida do coração para de repetir sem fim, dois nomes mudam para dizer o que se sente (Corda que estica e Pedal duro) e a Porta emperrada para de repetir.
- O estilo do jogo passa a escolher o gatilho, a imersão da frente, o efeito da luz e o efeito háptico. A luz da Corrida acende conforme o gatilho e a do Ritmo sobe na batida da música. Com o Sem piscar, tudo isso vira transição lenta.
- A lista de gatilhos cai de dezenove para onze. Rígido, Rígido simples e Ponto duro viram Resistência; os dois disparos viram Disparo; a arma automática vira Metralhadora. Perfis antigos continuam abrindo e a Vibração passa a tremer no gatilho. Alguns nomes de curva mudam para dizer o que se sente.
- A aba Sistema deixa de sugerir um perfil de bateria por controle em outra aba; o perfil de bateria vale para todos os controles
- Configurar um lançador volta a escolher onde ele está e a ligar o perfil por jogo, e só grava no Guardar
- Cada jogador pode configurar o próprio bloco pelo próprio controle, com R1 e L1 dando a volta nas abas, mas a Navegação Interna nascia desligada. Agora ela nasce ligada, as listas dão a volta ao chegar ao fim, e quem escolhe ganha um anel na cor oposta à do plástico.
- O Hefesto passa a ser para qualquer idade; o suporte aos acessórios Lovense e ao servidor Buttplug se instala à parte, como extensão.
- O estilo escolhe o R2 e o L2 separados, o toque, os motores e a luz da barra. A Luta separa o golpe forte do fraco, o FPS separa o tiro da mira, o Terror tem o coração na luz e nos motores, a Corrida tem o motor no acelerador e a Simulação sente o chão no L2. Nascem os estilos Souls/RPG e Furtivo, e o Arco vira uma escolha dentro de Ação e Aventura.
- O Hefesto traz a Steam, o Heroic e o Flatpak; o Lutris, o RetroArch, o Dolphin, o mGBA, o Azahar e o Kyty se instalam como extensões, cada uma do seu repositório.
- Quando o Hefesto reinicia (numa atualização, por exemplo), cada controle ligado acende a luz e toca a sua nota, como se tivesse acabado de chegar.
- A «Intensidade do gatilho» da aba Gatilhos passa a valer para o computador inteiro, como a força da vibração, e o perfil de um jogo só a troca quando você escolhe nele.
- Com os quatro DualSense ligados, um quinto controle não ganha cartão nas abas Jogar e Conexões: o Hefesto trabalha com quatro jogadores.
- Nas abas de gatilhos, luz, vibração e perfis, cada efeito ganha um nome pela família e pela variante (Golpe · forte, Carga · estica), com a frase do que se sente, e os acionamentos técnicos vão para o avançado.
- Ligar ou desligar uma extensão de tema muda as cores da interface na hora, sem fechar e abrir a janela, e as listas que abrem seguem o tema claro ou escuro.
- Fechar, minimizar e maximizar a janela do Hefesto passam para o canto esquerdo da barra.
- Nas abas de gatilhos, luz e vibração, cada efeito tem o nome pelo que acontece (Golpe · forte, Carga · estica), agrupado por família, com a explicação na dica. Os acionamentos técnicos ficam atrás da chave Avançado, e o «Efeito imersão» da vibração passa a se chamar «Padrão dos motores».
- No modo Padrão, a háptica por áudio do DualSense passa a chegar em 150%, como nos outros modos; antes ela chegava em 100%, do jeito que o jogo mandou.
- Em jogos que não mandam vibração, o controle ficava mudo. Agora o Hefesto ouve o som do próprio jogo e transforma estalos em toques e o grave em um corpo leve nos estilos de golpe (Ação, Souls, Aventura e Terror). Se o jogo passar a vibrar, o toque do som cede a ele.
- O Proton fixado passa a ser sempre a versão mais recente que passa na ficha de qualificação; todo jogo vai para ela, e as outras versões saem do disco.
- No jogo Xbox, todo rumble virava dois senos fixos, igual em qualquer estilo, e só o golpe ganhava a forma do estilo. Agora o rumble médio e o contínuo também ganham o timbre do estilo, sem perder energia. Sem estilo, no Nativo e no Personalizado segue o seno de antes.
- Com a Navegação Interna, o Options salva e aplica o perfil mesmo quando o mouse do controle está ligado; antes, com o mouse ligado, ele era só a tecla do teclado.
- A extensão da Lovense mostra na hora o que está ligado, o brinquedo e cada controle, e cada escolha responde na tela.
- A janela de cada extensão mostrava campos que não faziam nada com a escolha feita; agora eles só aparecem quando valem.
- O alto-falante e a vibração do controle liam o som da máquina cada um por conta própria; agora pedem a uma leitura só.
- Jogar e Controles viram uma aba só; o modo DualSense, Xbox ou Nintendo Pro vale para todos os controles
- O modo vale para todos os controles, e a coluna «Ajuste próprio» da aba Perfis deixa de ter a célula da máscara.
- A aba Jogar tem os modos e, embaixo, cada controle conectado; a aba Controles saiu, e a tira tem nove abas
- As abas de ajuste mostram menos linhas e mais o que importa, e a tira de cima tem nove abas, sem o contador de controles
- A luz e a vibração perdem o criador que não criava nada; o do gatilho compõe efeitos como a metralhadora
- A lista de efeitos do gatilho abre com «Do estilo» e tem só efeitos que funcionam e são diferentes, em grupos com mais de um
- Ao soltar uma barra do criador do gatilho, o controle já toca o efeito, sem precisar apertar Sentir
- DualSense, Xbox ou Nintendo Pro vale para todos os controles de uma vez, e o PS + L3 troca o modo de todos
- O Point and click sai dos modos e vira um estilo de jogo, que já abre com os botões da aba Navegação
- A barra do sensor háptico termina em 100 %, e quem estava em 200 % fica em 100 % com a mesma força

### Removido

- Várias abas tinham a escolha Só neste jogo ou PC, que confundia onde a alteração era gravada. Ela saiu das abas Controles, Iluminação, Vibração e Navegação: o que você muda vale para o perfil ativo, o do jogo aberto ou o do computador quando não há jogo.
- O daemon sempre reconecta o controle que cai; a opção que dizia desligar isso não desligava, e sai da linha de comando
- O jogo já excluído e o lembrete já dispensado continuam valendo; não se exclui nem se dispensa jogo novo
- Identificar e Criar perfis de cada lançador ficam no lugar de Procurar e Detectar
- O chip «Todos» é o único jeito de voltar a mandar para todos os controles
- Quando o serviço do Hefesto não responde, a tela não escreve mais «O Hefesto está desligado» no topo nem a frase no meio dos cartões; o Status marcado em Desligado é o sinal.

### Corrigido

- A opção de lançamento de um jogo, como o MangoHud, era gravada no arquivo da Steam e o Hefesto dizia «aplicado», mas a Steam lançava o jogo com a opção antiga. Agora o escritor respeita o bloco de cada jogo, e o relato só diz «aplicado» depois de ler a opção de volta.
- O Hefesto detectava o cabo em espera e o nascimento do controle lendo frases do diário do sistema, e se o sistema trocasse a frase o controle deixava de ser visto, sem erro. Agora esses eventos vêm do udev e do banco de dispositivos do sistema, e o diário fica só para quem o lê.
- Ao instalar um jogo na Steam, o Hefesto aplica a ele o atalho de lançamento e as opções no instante em que a Steam fecha, sem esperar a volta seguinte do vigia e sem precisar apertar nada. Dá para desligar na aba Sistema.
- Jogos que trazem o runtime de jogos da Microsoft recebem do Hefesto uma peça que segue o contrato desse runtime, sem tocar no que você pôs na pasta do jogo.
- Em Ubuntu, Fedora, Arch e nas outras, o install grava o ajuste do cabo no carregador de boot que a máquina usa
- Os controles virtuais respondiam ao jogo só a cada tique, e com muitos pedidos seguidos o sistema descartava vibração, gatilho e luz. Agora cada controle virtual atende o jogo na hora. Com o jogo fechado, o nome do controle virtual também passa a seguir o número do jogador.
- No modo Xbox o Hefesto criava um controle virtual com identidade de DualSense ou Nintendo que o jogo não conseguia abrir, e nenhum controle respondia. Agora esse controle virtual se apresenta como Xbox 360. Sem canal próprio, o modo DualSense também cai para o Xbox 360 até o canal voltar.
- Ao reconectar um controle ou reiniciar o serviço, o Hefesto podia recriar o controle virtual no modo errado e tratar o modo Xbox como queda, voltando ao DualSense. Agora o modo escolhido tem um dono só e vale desde a abertura do sistema. O botão PS e suas combinações funcionam em qualquer um dos quatro controles.
- Abrir o Hefesto com a janela já aberta não a trazia para a frente. Agora o segundo pedido apenas traz a janela existente para a frente e sai sem abrir outra. O lançador também ajusta o ambiente gráfico antes de carregar a interface.
- Um aperto no botão do microfone do controle, logo depois de um clique no botão do microfone da tela, podia ser engolido e não fazer nada. Agora cada aperto vale pelo estado real do microfone, sem janela de tempo escondida, nos quatro controles, por cabo e por rádio.
- Quando um controle caía e a numeração mudava, as cores escolhidas para os outros saíam sozinhas, e cada controle ficava com a cor de outro. Agora cada cor escolhida fica guardada no controle em que foi escolhida, mesmo que o número dele mude.
- Na aba Iluminação, a linha sob a cor escolhida tinha só 2 px e, em vários plásticos, quase não se via sobre o painel. Passa a ter 6 px, na cor do plástico de cada controle, sem mudar o tamanho da grade.
- Um controle largado sobre uma superfície, com a inclinação ligada, empurrava o analógico do jogo para um lado, e o personagem andava sozinho. Agora o analógico do jogo volta ao centro quando o controle está parado, e o neutro ajustado na mão fica como estava.
- Na fita de seleção dos controles, só o primeiro ficava com a fonte destacada, e escolher Todos não acendia cada um. Agora escolher um controle acende só ele, Todos acende o Todos e os quatro, e nas abas que não escolhem, todos nascem acesos.
- Quando um controle saía no meio do jogo, o número das luzes e o dos controles virtuais ficavam fora de sincronia, e os controles se comportavam de forma estranha. Agora o número que se solta é o mesmo que acende na luz do controle, e com o jogo aberto o lugar guardado espera, em vez de renumerar.
- Ao tocar em Aplicar soluções nos lançadores enquanto a lista de exclusão estava sendo gravada, a janela dizia que nenhum lançador precisava de nada. Agora ela espera até 5 s pela lista e, se não conseguir, avisa que a lista estava sendo gravada e que os outros lançadores ficaram como estavam.
- Quando o controle virtual DualSense nascia sem o canal próprio, o quadrado e o triângulo chegavam trocados ao jogo. Agora a tabela de botões segue a identidade que o jogo vê, e as máscaras DualSense e Nintendo usam a mesma tabela.
- Quando um lançamento acabava sem o jogo assumir o controle, por exemplo um jogo que fecha antes da janela, o controle virtual ficava travado e o Hefesto recusava recriá-lo. Agora a trava solta quando o lançamento termina.
- Quando o controle virtual do primeiro jogador caía para um modo mais simples, o aviso e o diário podiam dizer jogador 1 enquanto o controle se chamava com outro número. Agora o aviso, o nome e o número de série do controle virtual dizem o mesmo número.
- As dicas e a coluna Funciona em chamavam o Freestyle de Sempre e ofereciam Qualquer jogo, o que nunca valia sozinho. Agora a dica do Salvar trata o Freestyle pela identidade dele, a coluna diz Só quando eu escolher e Qualquer jogo sai da oferta.
- Ao parar o serviço ou sair pelo ícone da bandeja, o controle continuava fechado para os outros programas. Agora, 30 s depois do último cliente sair, o Hefesto entrega o DualSense ao sistema, por cabo ou rádio, e o Sair da bandeja também para o serviço.
- Sem perfil ativo, clicar em Padrão no alto-falante da aba Controles não fazia nada: a barra seguia verde e travada, e o volume não podia ser ajustado. Agora o clique grava a escolha no padrão do computador, destrava a barra e permite ajustar o volume.
- Várias linhas da interface começavam em minúscula, como nenhum aparelho no ar ou a faixa dele ainda não foi descoberta. Agora todo texto que abre uma linha, célula, selo ou dica começa com maiúscula nas dez abas, com exceção de unidades e marcas.
- Ao parear um controle novo com PS e Create, a linha voltava a pedir o pareamento, o Tirar esta linha não tirava, o Conectar prendia a seção e a gaveta abria enorme e vazia. Agora o controle fica conectado, a linha sai ao tirar, outro adaptador pode ser escolhido e a gaveta tem o tamanho do conteúdo.
- Na fileira de cores da Iluminação, o X que marca a cor usada por outro controle sumiu quando a cor automática passou a ser a do plástico. Agora a cor do plástico é associada ao tom mais próximo da paleta, e o X volta a aparecer na fileira de cada controle.
- A luz do botão de mudo ficava acesa parada mesmo quando um app de fora gravava o microfone do controle no cabo, porque só um dos dois caminhos do som era observado. Agora a luz considera o canal do controle e a placa que o alimenta, e pisca enquanto outro app grava a voz daquele controle.
- Conforme a janela era aberta (menu do sistema ou bandeja), o dock mostrava uma engrenagem genérica e o nome técnico em vez do ícone do Hefesto. Agora todas as formas de abrir a janela passam pela mesma entrada, e a janela sempre se anuncia com a mesma identidade.
- Mesmo com o microfone de um controle desligado, as barras do cartão dele se mexiam e o som ainda entrava. Agora o desligado vale na própria entrada de som daquele controle, e cada medidor lê só o microfone do seu controle.
- A instalação pelo Nix falhava na construção porque o pacote pedia uma biblioteca de nome parecido, mas diferente, da que o Hefesto usa para falar com o controle. Agora o pacote traz a dependência correta.
- Ao parar e iniciar o serviço (inclusive na instalação), sobravam alto-falantes «Controle N» duplicados, e um nó de som removido por fora nunca voltava. Agora o Hefesto confere com o servidor de som o que existe, derruba o que sobrou e recria o que sumiu.
- Se o zero não puder ser gravado o controle volta a «Parado» em vez de dizer «Calibrado», o giro passa a descontar o zero também no movimento do cursor, e os botões do Inverter cabem em janela estreita.
- Se um jogo manda o efeito do gatilho logo ao abrir o controle, o controle passa a recebê-lo desde o primeiro instante, em vez de esperar o jogo mandar de novo.
- Com dois controles externos na Conexões, a lista deixa de ganhar barra de rolagem, e a cor do plástico que não está na lista de fábrica passa a poder ser escolhida de novo.
- Os efeitos Metralhadora, Arma automática e Vibração do gatilho passam a bater sem parar enquanto você aperta, como no PS5, em vez de dar um toque só.
- Se a Steam reescrever a linha de inicialização de um jogo que você configurou no Hefesto, ou se a opção ficar fora do lugar onde a Steam lê, o doctor diz qual jogo e o que fazer.
- Com o controle longe ou esperando a vez, a caixa da ponte para de dizer 94 Hz e mostra o que ela entrega agora, e a proposta de mudar de adaptador diz quando veio do sinal fraco.
- A Rampa de força passa a manter a firmeza até o fim do curso, e um perfil antigo de Vibração por posição volta a vibrar como a aba mostra.
- Os efeitos Arco de flecha e Galope passam a usar o ajuste próprio do controle, com a tensão do arco e a cadência do galope no lugar certo, quando você aprovar a sensação nova.
- Com o Hefesto desligado do início do sistema, o controle fica livre para o Linux e para outros programas, sem esperar você abrir o Hefesto.
- O efeito Disparo passa a funcionar como arma de verdade, que resiste, estala e arma de novo ao soltar, em vez de uma vibração lenta.
- Num perfil de jogo, apagar uma tecla herdada do computador ou escolher o valor de fábrica agora vale, em qualquer modo e conexão. Antes a tecla do computador voltava sozinha.
- Em todas as abas, o número ao lado de uma barra às vezes ficava no valor antigo enquanto a alavanca já estava no novo, e o gesto seguinte mandava esse valor velho ao controle. Agora o número sai sempre da alavanca.
- Quando o jogador 1 sai e outro controle assume o lugar dele, a vibração do jogo para o jogador 1 continua nesse controle, sem ser cortada pelo lugar que ele deixou.
- Quando o Hefesto não conseguia anotar o que tinha posto no arquivo de um jogo do Lutris, o tirar da lista deixava duas linhas do Xalia para trás. Agora o arquivo só muda depois da anotação.
- Depois de fechar um jogo aberto pela Steam, o computador sai do modo de desempenho na hora, e o jogo pode ser aberto de novo sem esperar.
- Com a navegação pela janela ligada e o mouse do controle desligado, o Start do primeiro controle guarda o perfil sem abrir a visão geral do sistema por cima.
- Ao desligar o Hefesto, se o servidor de som do sistema não responde, ele desiste dentro de um prazo curto em vez de esperar cada comando, e o sistema não precisa matar o programa à força.
- O diagnóstico da instalação passa a perguntar ao udev, pelo comando oficial, se o controle nasceu aberto para qualquer programa, em vez de ler o arquivo interno dele; o medidor de microfone de cada controle pergunta ao servidor de som no formato próprio para programas.
- Quando a pasta de configuração ou a do serviço não deixa o Hefesto ler ou escrever, o serviço para com uma mensagem que diz qual pasta conferir, em vez de dizer que foi desligado de propósito ou ficar ligado sem responder; e a mensagem da chave de desligar passa a mostrar o comando certo para religar.
- `status`, `battery` e o diagnóstico deixam de esperar para sempre quando o serviço não responde; sem controle conectado, bateria e luz dizem que não há controle em vez de mostrar 0% ou confirmar a cor; os comandos param de imprimir mensagens internas; e o diagnóstico sai com erro quando encontra problema.
- O instalador e os pacotes passam a instalar o WebKit da interface; antes, numa máquina sem ele, o serviço subia e a janela não abria.
- O que o jogo manda ao controle deixa de esperar uma pausa que crescia com cada jogador; no cabo sai assim que o jogo pede, e no Bluetooth guarda só o espaçamento que o rádio precisa.
- Nas distribuições com o WirePlumber 0.4, o microfone do controle deixa de virar o padrão sozinho e o alto-falante do controle não corta o começo dos sons.
- Na aba Conexões, um aparelho Bluetooth de baixa energia que não informa o tipo deixa de aparecer como interrogação: ganha categoria própria, mostra o sinal medido e a faixa explica o que se sabe do rádio.
- Mira e câmera deixam de esperar o ciclo interno de 60 vezes por segundo; o movimento do analógico chega ao jogo no ritmo do próprio controle, para todos os jogadores, no cabo e no Bluetooth.
- No Ubuntu 24.04 e no Debian 12, o diagnóstico deixa de dar falha pela versão do Bluetooth e explica o que pode acontecer com controles sem fio; quem instalou o BlueZ do Hefesto é avisado quando a distribuição publica uma correção mais nova.
- Numa máquina com mais de uma conta, o controle passa a responder para quem está usando o computador agora, e os pacotes trazem a mesma proteção contra o controle aparecer duas vezes no jogo.
- O Hefesto lê a versão do firmware de cada controle e, nos firmwares recentes, manda a vibração no modo novo, com a força que o jogo pediu, no cabo e no Bluetooth.
- Um perfil com defeito é avisado uma vez, e não a cada dois segundos; sem servidor de som, o serviço avisa uma vez em vez de repetir que está ligado; e a configuração da máquina corrompida é guardada ao lado antes de ser refeita, para poder ser recuperada.
- Nas distribuições somente leitura, o instalador deixa de tentar instalar pacotes do sistema e diz, uma linha por item, o que fica de fora.
- Quem instala pelo pip, pelo Flatpak, pelo Arch, pelo Fedora ou pelo Nix passa a receber o Freestyle e os Estilos de Jogo, e o serviço sobe sozinho no login; antes, nesses formatos, o Freestyle nascia sem perfil e o serviço falhava ao iniciar.
- quando o sistema não diz qual janela está na frente, o Hefesto reconhece o jogo que está rodando e entra no perfil dele
- o perfil criado pela linha de comando herda gatilho, luz e vibração do computador, e um perfil novo ou editado fora da janela já vale na primeira vez que o jogo abre
- Em notebook, o Hefesto deixa de manter todas as portas USB e o Bluetooth sempre acordados; os ajustes do Wi-Fi USB só entram se houver um adaptador desses; as ferramentas de desenvolvimento só vêm com --dev.
- O comando de recarregar os plugins carrega de novo os plugins do disco, em vez de desligar todos e devolver erro.
- O jogo que toca sons no alto-falante do DualSense passa a ser ouvido no controle sem fio, como já era no cabo.
- O serviço que cuida dos pareamentos passa a agir só em controles de jogo. Fones, teclados e outros aparelhos Bluetooth deixam de receber pedidos de pareamento repetidos e deixam de encher o registro do sistema com avisos a cada dois minutos.
- As páginas do Hefesto mantêm a altura e a largura quando a tela dorme e volta, quando a janela é maximizada ou quando o serviço demora a responder.
- Quando o Hefesto está configurado para abrir a janela no início da sessão, ela abre e fica aberta. Antes, o serviço que a abria a fechava logo em seguida.
- A página do mapa das portas dizia que a vibração não pesava no rádio. Agora ela mostra quanto o som e a vibração de cada controle sem fio ocupam e quantos controles ainda cabem com eles ligados.
- Uma extensão só troca de versão depois que a anterior parou, só liga com as permissões que você viu, e o desinstalador do Hefesto para as extensões que estão rodando. Com --purge-config, ele remove também as extensões instaladas, com backup.
- Com o Modo automático ligado, um perfil Ritmo/Música mantém a música só no PC, sem a cópia atrasada no alto-falante do controle; os outros estilos deixam o alto-falante com o jogo.
- Se o arquivo que guarda o número de cada controle estiver corrompido, o Hefesto guarda uma cópia dele ao lado, avisa no registro e recomeça, em vez de gravar por cima calado.
- Um jogo do Windows rodando com o driver Wayland do Wine, fora da Steam, agora troca para o perfil dele como os outros.
- A luz do botão de mudo acende fixa com o microfone ligado, pisca enquanto entra som e apaga no mudo, em qualquer modo. No cabo ela pisca sem precisar de app de fora; no rádio, só com app ouvindo. No Modo Nativo, a luz antes não chegava ao controle.
- Ao aplicar as soluções nos lançadores, o Hefesto troca só o trecho que ele mesmo escreveu na opção de lançamento de cada jogo. O que você escreveu à mão fica no lugar, mesmo quando o jogo tem opções na tabela do Hefesto.
- A cada lançamento pela Steam, o Hefesto tira do prefixo do jogo as saídas e entradas de som que sumiram, inclusive as dos controles de sessões antigas. Menos dispositivos para o jogo varrer é menos memória gasta.
- Um teclado ou um mouse Bluetooth de baixa energia que não se anunciava pelo ícone aparecia com um ponto de interrogação nas Conexões. Agora ele aparece como teclado ou mouse.
- Quando um controle virtual demora a aparecer no sistema, só ele volta ao modo de reserva, e os seguintes continuam nascendo completos. O diagnóstico diz qual controle está no modo de reserva e por quê.
- a versão do Bluetooth que o Hefesto instala passa a trazer as correções de segurança que a distribuição publicou, e o diagnóstico avisa quando aparecer uma correção nova que ela ainda não tem
- Com um GE-Proton que já cria sozinho o dispositivo de áudio do controle, o Hefesto deixa de criar o dele, e o jogo acha um alvo só para a vibração de cada controle.
- O driver do Pro Controller e do 8BitDo que o Hefesto instala só entra no kernel em que foi conferido; num kernel mais novo, o do sistema assume com as correções dele, e o diagnóstico avisa.
- quando o Bluetooth do sistema demora a confirmar o pareamento, o Hefesto confere se o controle ficou pareado e o marca como confiável, para ele voltar sozinho da próxima vez
- o Hefesto passa a perceber o controle que ficou ligado ao rádio sem funcionar mesmo onde a distribuição não instala as ferramentas antigas do Bluetooth, como no Arch e no Fedora
- Sem perfil ativo, a aba Iluminação passa a mostrar o modo e o brilho guardados, em vez de valores vazios. O efeito da barra é conferido no cabo e no Bluetooth, nos quatro controles.
- Com a economia «Bateria longa» ligada, a barra de luz fica fixa na cor do perfil e o efeito (respirar, piscar, mudar de cor) para; ao sair da economia, o efeito volta sozinho. A aba Iluminação mostra o efeito guardado mesmo sem perfil ativo.
- Com o serviço parado, a aba Jogar marca Desligado e explica por que nenhum controle aparece, em vez de mostrar Ligado com os controles sumidos
- Jogos Unity que trazem o kit da Lovense por Bluetooth direto (LovenseWinrtBleDll.dll) caíam na abertura sob o Proton. O Hefesto reconhece o kit na pasta do jogo e desliga só essa DLL no lançamento; o jogo abre, e o brinquedo passa a ir pela ponte do Game Mode que a extensão Lovense abre no próprio computador.
- O efeito que repete batidas deixa de reescrever o mesmo gatilho várias vezes por segundo, e os efeitos de gatilho passam a perceber quando o Disparo passou do clique. Na Bateria longa, ao calar o jogo ou ao soltar o outro gatilho, o gatilho volta sozinho para a mão.
- o Hefesto traz uma receita do PipeWire 1.6.9 e do WirePlumber 0.5.18, as versões mais novas do upstream, com a correção para o caso em que a Steam ficava presa ao fechar depois de um reinício do serviço de som, e o diagnóstico avisa quando o PipeWire instalado não tem a correção
- Quando o instalador troca o servidor de som, o painel do COSMIC volta a mostrar a saída e a entrada de som na hora, sem precisar sair da sessão. O diagnóstico avisa se o painel perdeu o som e diz como trazê-lo de volta.
- A dica de um título do mapa das portas e dos cartões da aba Conexões passa a abrir quando o foco chega a ele, e não só quando o mouse passa por cima.
- A webcam deixa de aparecer em laranja no mapa das portas, porque ela roda a 480 Mb/s em qualquer porta e não perde nada
- Se o controle perdia a conexão, a leitura falhava ou você saía do jogo com um clique segurado pelo controle, o clique ficava preso. Agora o Hefesto solta o clique, a ativação e o controle virtual nesses casos, e também na pausa.
- Ao abrir um perfil, o seletor de estilo mostra o estilo guardado nele, e o Nome do jogo não aceita mais o nome do Freestyle, que é o botão do controle.
- O serviço só se diz ligado quando já atende a interface, então o botão Ligado e o menu da bandeja deixam de mostrar uma recusa logo depois de ligar
- Os botões Trocar os botões e Point and click da aba Navegação abrem o mapa do controle já no perfil que prometem, em vez de sempre abrir em Navegar no computador.
- Ao fixar o Proton, as versões em uso por jogos do Lutris e do Heroic ficam instaladas, e só as que ninguém usa saem
- Se uma troca de gesto do botão PS deixaria o controle sem saída de emergência, a aba Navegação diz isso na resposta da troca.
- Na largura mínima da janela, a lista de sugestões do mapa das portas deixa de rolar, e o nome longo de um aparelho corta com reticências em vez de quebrar a linha.
- Sem perfil ativo, a forma do toque escolhida na aba Vibração passa a tocar no controle
- O teste da háptica na aba Vibração passa a tocar a forma escolhida em Efeito háptico, e um Testar apertado durante um padrão espera o padrão terminar e não é mais cortado.
- As opções Teclas WASD e Setas aparecem só nas linhas dos analógicos da aba Navegação, e passam a mover as teclas também no desktop, sem jogo aberto.
- A força da vibração de cada controle muda só na aba Vibração, e as correções automáticas das abas Sistema agem só pelo interruptor Permitir correções automáticas.
- Sem perfil ativo, a luz e o efeito do gatilho deixam de ficar parados no último perfil e seguem o que o computador está fazendo.
- Quando o sistema tem uma atualização interrompida, o instalador diz só isso e não acrescenta uma causa errada para o GTK ou o wlrctl.
- O jogo deixa de fechar com a janela de erro do Unreal no meio da partida.
- As três seções da aba Acessibilidade passam a valer no controle de verdade, e o toque segue a mão escolhida.
- Cursor e Rolagem aparecem só nas linhas dos analógicos, e as teclas soltas só nas linhas de botão.
- Remover o gesto atribuído ao botão PS deixa o botão sem ação, em vez de devolvê-lo ao PS do jogo sem aviso.
- Se o sistema tem uma atualização a meio, como um kernel novo cujo driver de vídeo não compilou, o instalador avisa, mostra o comando que conserta o sistema e segue, em vez de tentar reconfigurar o que não é dele.
- O controle vibra nos jogos da Microsoft que pedem a vibração pelo GameInput.
- O prontuário deixa de marcar como impedido o jogo que abre e joga, só sem conta.
- Na janela estreita, os quatro botões de controle do Mapa ficam numa linha só, com o nome e a conexão inteiros, qualquer que seja a fonte do sistema.
- Apagar o perfil que está ativo desfaz o remapeamento e o roteamento dele no controle na hora.
- O perfil criado pela aba Lançadores mostra o nome do jogo no editor, inclusive para emuladores, e nasce com a máscara que o jogo pede.
- O hefesto doctor confere o Proton fixado também quando o Hefesto veio de pacote.
- Quem escolhe WASD ou Setas num analógico digita no desktop mesmo sem ligar a emulação de mouse.
- Quando o sistema passar ao kernel 7.2.6, os módulos do Hefesto para os controles virtuais e para o Wi-Fi USB compilam nele, em vez de ficarem de fora.
- O duplo clique conta pelo seu clique, mesmo quando a janela demora a responder
- Nada muda para quem usa
- Aplicar, Salvar perfil, Importar, Exportar e os botões do Selecionar mudam de cor quando o mouse passa por cima, como os outros botões da interface.
- Instalar uma extensão de lançador cujo manifesto não serve mostra o motivo, em vez de instalar uma extensão que nunca aparece
- Em janelas de até 1212 px de largura, a coluna do ID da peça some da tabela da aba Perfis, e a tabela deixa de rolar para o lado.
- Com um tema de cores ligado, o fundo em volta da área da interface muda junto, em vez de ficar escuro em volta de um tema claro.
- Ligar o cabo num controle que está no Bluetooth, ou tirar o cabo e ele seguir no Bluetooth, não faz mais a barra subir de novo, o controle vibrar e o gatilho clicar no meio do jogo.
- Acrescentar um jogo a uma lista do RetroArch, ou mudar um jogo no Lutris, já atualiza os perfis dos jogos
- Na aba Sistema, os avisos sobre o modo falam «Point and click», «Navegação», «Xbox», «Sony DualSense» e a «Função do teclado», no lugar dos nomes da janela antiga.
- O `diario.log` de cada extensão fica em até 1 MiB também enquanto ela está ligada; antes, o limite só valia quando ela abria de novo, e uma extensão que escreve muito podia encher o disco.
- Quando um controle externo fica sem número de jogador (por exemplo, com quatro DualSense ligados), o cartão dele diz «Controle — Nintendo», com um travessão só.
- A barra Criar efeitos novos da aba Iluminação mostra quantos efeitos você criou num chip só, com os nomes na dica, e a aba deixa de rolar na janela estreita.
- Copiar um jogo para a pasta do Dolphin, do Azahar ou do KytyPS5 já cria o perfil dele, sem esperar outra mudança
- O botão Parar do Testar agora, na aba Vibração, ganha um vermelho mais fundo, e a letra branca passa a se ler bem.
- O modo Point and click da aba Jogar passa a aplicar os botões do «Perfil jogo - navegação», e a Navegação segue com as linhas da aba Navegação.
- O primeiro comando do procedimento entra na pasta onde você baixou o Hefesto, e não numa pasta fixa
- Um tema de cores que deixaria os nomes dos campos ou as cores de destaque ilegíveis sobre o fundo dele não liga mais, e a recusa diz qual cor e qual fundo.
- Com o tamanho da interface em 150 %, as abas cabem na janela sem rolar nem cortar
- Ligar uma extensão de tema com texto ilegível mostra o motivo na hora e a deixa desligada, em vez de acender a chave e não mudar cor nenhuma.
- O README e o guia de problemas diziam que janelas Wayland nativas não eram reconhecidas; no COSMIC e nos compositores wlroots elas são, e a janela abre em Wayland nativo.
- Depois de escolher um controle só na aba Conexões, o «Todos» do alto devolve as ações a todos os controles
- O tempo do passo «Medindo» sai do mesmo lugar que o Hefesto usa para medir o repouso
- «Ligado» e «OK» aparecem em verde, os avisos ficam em laranja, e saíram os avisos que não pediam nada de você.
- Com muitas extensões instaladas, o cartão dos lançadores não sai mais da tela.
- O controle virtual se apresenta a cada jogo como o modelo que o jogo conhece, pela mesma regra em todo jogo e em todo jogador, cabo e Bluetooth.
- Navegando a aba Vibração pelo controle, o direcional pulava as listas «Padrão dos motores» e «Efeito háptico», e não dava para escolher o modo. Agora ele vai ao vizinho mais alinhado e nunca pula a caixa que está na frente, em todas as abas e para todo controle.
- Abrir o Hefesto traz o serviço de volta quando ele está parado, e o Ativar da aba Perfis troca o perfil ativo; se o serviço não responde, o topo e o botão dizem isso em vez de mostrar o perfil antigo como ativo.
- Ligar um DualSense com o jogo já aberto não deixa mais o jogo ler o controle físico ao lado do virtual, e nenhum botão fica apertado sozinho.
- No jogo que só conhece o DualSense comum, o segundo, o terceiro e o quarto controle também se apresentam como ele, e trocar o número do jogador vale no jogo e na tela.
- Antes de cada jogo, o Hefesto tira do Proton a lembrança de controles que não estão mais ligados. Jogos como o Mullet MadJack deixam de ignorar o DualSense por causa de um controle de meses atrás.
- O Status da aba Sistema mostra sempre as mesmas seis linhas; um aviso entra na linha do assunto dele, que fica laranja, em vez de abrir uma sétima.
- Na aba Experimental, os cartões dos lançadores não esticam mais para ocupar o espaço que sobra quando há poucas extensões; cada um fica com a altura do conteúdo.
- O Hefesto desliga a economia de energia do Wi-Fi na instalação, na hora e de vez, sem derrubar a conexão.
- Com o estilo Terror no Modo automático, a fileira do som acende «Sons do jogo» e mostra que o som do PC também toca no controle
- Ao abrir ou trocar de aba, o miolo ficava visível por um instante com os dados de exemplo antes de mostrar os seus. Agora ele aparece já com os seus.
- Quando um jogo instalado ganha um arquivo numa subpasta, por atualização ou por mod, o controle virtual passa a vestir o modelo que ele pede já no lançamento seguinte.
- As fontes da interface vêm instaladas com o Hefesto, e a janela não espera mais a internet para terminar de abrir.
- Com a Steam aberta, desligar o Hefesto devolvia o controle ao sistema, mas a Steam não o via até ser reaberta. Agora ela o encontra em poucos segundos.
- Com um Pro Controller ou um 8BitDo como destino, a janela desenha esse controle. Sem permissão de ler o teclado ou o pedal, ela diz como liberar.
- No primeiro jogo depois de abrir a Steam, o Hefesto podia tomar as luzes do controle por dois segundos logo na abertura. Agora o jogo que está abrindo fica com elas desde o começo.
- A dica do botão «Mapa do controle» e a do ícone do mapa das entradas passam a dizer que abrem na própria janela, e não no navegador.
- O Hefesto não deixa mais a roupa de um jogo desatualizada quando um arquivo dele chega no mesmo instante da leitura anterior, em discos de relógio grosso como FAT e exFAT.
- O meu.css aceita @container e @layer. Remover a extensão de tema não apaga o CSS que você escreveu, e a recusa aparece uma vez no diário, não a cada gravação.
- Fechar um jogo e abrir outro em menos de meio minuto deixava o segundo com o controle do primeiro (a identidade e o modo). Agora cada jogo recebe o controle que pede, mesmo aberto em seguida.
- Quando o Point and click usava um perfil e esse perfil é apagado, ele volta ao padrão, em vez de parar de responder sem aviso.
- O movimento e o toque enviados aos emuladores pelo DSU dizem a conexão verdadeira de cada controle, cabo ou Bluetooth.
- Digitar o nome de um lançador que já tem cartão, como a Steam, manda você ao «Configurar» do cartão dele, e não a um botão que a aba não tem mais.
- A Iluminação, a Vibração e a Conexões nasciam com um nome de pessoa no controle 1, antes de ler o seu. Agora o lugar fica com «P1» até você dar um nome.
- Ao conectar, a extensão recebia um aviso sem dizer de qual controle era, com o transporte do controle 1 valendo para todos. Agora cada controle avisa por si, com o cabo ou o Bluetooth dele.
- Depois de atualizar a extensão Lovense pelo Hefesto, faltava o programa que ela usa para falar com o brinquedo, e era preciso instalar de novo à mão. Agora o Hefesto prepara a extensão ao instalar e ao atualizar.
- Em «Rádio e adaptadores», o «Segure PS + Create» ficava apagado atrás do «Onde fica?», o aviso ficava por cima dos dois e o «Onde fica?» quebrava em duas linhas. Agora cada um tem o seu lugar.
- Com «Sacudir» e «Inclinar» de volta a «Nenhum», a extensão da Lovense para de pedir o movimento do controle.
- Uma extensão que deixa de usar o movimento ou o touchpad do controle avisa o Hefesto, que para de lê-los.
- Três linhas do mapa dos controles não diziam como se confere cada uma no aparelho. Agora dizem, no cabo e no rádio.
- Com o adaptador USB da Lovense mais novo, a extensão subia o servidor e nenhum brinquedo aparecia. Agora o adaptador conecta o brinquedo, ou a janela diz que ele não tem suporte.
- ao parar, o serviço não registra mais um erro de escrita sem sentido
- Atualizar, ver as permissões e remover ficam só no menu dos três pontinhos, que flutua sem esticar os cartões; ligar uma extensão que pede permissão mostra «Aceitar e ligar» na própria chave, com o que ela pede na dica
- Com o DualSense no cabo, o som da vibração andava no ritmo da placa de som do controle, e o jogo podia congelar quando reabria a vibração. Agora ele anda no ritmo próprio, como no Bluetooth.
- Enquanto um controle caído esperava para voltar ao mesmo lugar, o diário do Hefesto repetia um aviso de LED várias vezes por segundo. Agora o aviso sai uma vez.
- quem cai e volta reacende o número mesmo quando o sistema demora a achar a luz dele, e o diário não repete aviso
- Só o controle do jogador 1 tinha o lugar guardado no jogo; o 2, o 3 e o 4 sumiam do jogo ao menor soluço do Bluetooth. Agora os quatro esperam a volta pelo mesmo prazo, no cabo e no Bluetooth.
- Em jogos com ™, ® ou acento no nome, o Hefesto ouvia o som do jogo e largava a cada 10 segundos.
- Jogos com ™, ® ou acento no nome apareciam como «audio stream» no Hefesto; agora aparecem com o nome certo.
- Logo depois de ligar o computador, o controle que já estava conectado podia ficar sem a háptica própria no jogo até o Hefesto reiniciar. Agora ele ganha a porta dele assim que a sessão abre, no cabo e no Bluetooth.
- Com vários brinquedos no adaptador USB da Lovense, um toque curto vibra todos, não só os primeiros.
- Ao ligar a extensão, o adaptador USB da Lovense não fica caindo e voltando antes de achar os brinquedos.
- A extensão da Lovense tratava mal alguns valores vazios do adaptador e do servidor; agora cada um tem resposta certa.
- Se o computador ligava antes de o sistema liberar o DualSense virtual, o controle 2, 3 ou 4 ficava como Xbox no jogo, sem gatilhos adaptativos nem giroscópio, até ser desconectado. Agora ele volta a ser DualSense sozinho, como o controle 1, no cabo e no Bluetooth.
- Com vários brinquedos ligados, só um recebia por vez. Agora todos recebem juntos, a janela tem um botão para parear e uma lista para ligar, testar e esquecer cada um, e as opções não dependem mais de quantos DualSense estão ligados.
- Quando o teclado ou o pedal sumia no meio do «Esperar a próxima tecla», a aba Conexões dizia uma frase diferente das outras recusas.
- A janela da extensão dizia que não havia opções logo acima dos modos Soltar, Segurar e Repetir, e a barra Ao vivo só avisava que a extensão estava desligada depois de arrastada.
- Na extensão da Lovense, um «Parear» às vezes não buscava, a bateria piscava em zero e a escolha «Ligado» se perdia ao reconectar.
- Para usar um teclado ou um pedal como botões do controle, o Hefesto pedia para entrar no grupo input, que deixa ler todo teclado da máquina.
- O serviço do Hefesto deixava avisos falsos no diário do sistema várias vezes por hora; agora só ele fala com o sistema.
- Trocar Soltar, Segurar ou Repetir e depois Cancelar deixava a extensão no modo novo, e uma recusa da extensão não aparecia.
- Quando a porta USB virtual de um controle caía, os outros podiam parar de responder por alguns segundos.
- Quando um jogador desligava o controle, os controles dos outros podiam parar de responder por alguns segundos.
- Com a extensão desligada, a janela da extensão recusava a troca entre Soltar, Segurar e Repetir depois de um arrasto.
- Ao trocar a ordem dos jogadores, o primeiro controle podia parar de responder por alguns segundos.
- Ao ligar a emulação, sair do Modo Nativo ou trocar a roupa do controle, os controles podiam parar de responder por até 2 segundos.
- Quando um controle se conectava com o jogo aberto, os outros podiam parar de responder por até 2 segundos.
- A háptica que o jogo toca chega ao controle sem depender de você ter apertado alguma coisa, inclusive nas cenas de abertura.
- Na aba Conexões, o controle ligado por cabo USB mostra a cor e o jogador, como o que está no Bluetooth.
- No cabo USB, a vibração do jogo volta a mexer o motor, e a háptica do jogo continua tocando junto, sem uma calar a outra.
- O Calibrar giroscópio, o Mapa das portas e o Mapa do rádio usam a letra do Hefesto em qualquer computador
- Sem o adaptador no computador, a aba Conexões não mostra erro; com ele ligado, a linha dele aparece
- Com outra versão das bibliotecas de texto, o nome do controle no topo deixa de terminar em reticências
- A configuração copiada para outro computador chega sem o mapa das entradas, sem os rádios e sem os adaptadores
- Na janela estreita, o nome do controle e a ação de cada botão no mapa deixam de sair cortados
- Na janela estreita, a frase cortada da aba Sistema e a escolha cortada da aba Gatilhos aparecem inteiras ao passar o mouse

## [0.9.5] — 2026-10-06

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

- `hefesto-dualsense4unix metrics ligar` liga as métricas Prometheus, e `HEFESTO_DUALSENSE4UNIX_METRICS_PORT` escolhe a porta.

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
