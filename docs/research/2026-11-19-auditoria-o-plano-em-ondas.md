# A auditoria de 19/11/2026: o plano em ondas

O que a auditoria de 19/11/2026 escreveu e ainda não foi construído: 284 sprints em 50 conjuntos, na ordem em que
se constroem. Cada linha é uma sprint (prioridade, identificador, título); o texto de cada uma, com o defeito medido, a
cura e a prova, mora no diretório de processo, fora do repositório. Este arquivo é gerado: não se edita à mão.

A ordem: a Onda 0 conserta o controle no cabo e barateia a construção (tamanho, fecho, docstring); a Onda 1 fecha o que
sobrou de P0; a Onda 2 leva os conjuntos com P1; a Onda 3, o resto. Uma onda tem dez sprints, cada uma implementada e
depois conferida e corrigida por outra mão. Marcas: «desenho escolhido» diz que a mudança de tela já tem mockup
aprovado; «desenho recusado», que a parte de tela não entra; «espera medida», que a sprint depende de uma medida no
aparelho.

## Onda 0: o cabo (P0) e velocidade e tokens (12 sprints)

### `cabo-p0` (1: 1 P0)

- P0 `O-CONTROLE-NO-CABO-NAO-CAI-SEGUNDOS-DEPOIS-DE-CONECTAR-01`: O controle no cabo não cai segundos depois de conectar

### `tamanho` (4: 2 P1, 2 P2)

- P1 `AS-CATRACAS-DESCEM-O-PISO-SOZINHAS-01`: As catracas do texto e da docstring longa descem o piso sozinhas
- P1 `O-TAMANHO-SE-MEDE-EM-TOKENS-E-SO-SOBE-POR-ORCAMENTO-01`: O tamanho se mede em tokens no repositório inteiro e só sobe por orçamento decidido
- P2 `CADA-REGUA-RODA-UMA-VEZ-E-SO-COM-A-ENTRADA-QUE-LE-01`: Cada régua roda uma vez e só com a entrada que lê
- P2 `O-QUE-SE-GERA-OU-SE-COPIA-SAI-DO-CAMINHO-DA-LEITURA-01`: O que se gera ou se copia sai do caminho da leitura · desenho escolhido, sem mudança visível

### `fecho` (5: 2 P1, 2 P2, 1 P?)

- P1 `O-FECHO-RODA-TODAS-AS-PARTES-E-GUARDA-O-RECIBO-DAS-VERDES-01`: O fecho roda todas as partes da suíte e guarda o recibo das verdes
- P1 `A-SUITE-DO-FECHO-CORRE-EM-TRES-FAIXAS-01`: A suíte do fecho corre em três faixas
- P2 `OS-QUATRO-TESTES-QUE-OSCILAM-ESPERAM-PELO-EVENTO-01`: Os quatro testes que oscilam esperam pelo evento
- P? `O-SIGSEGV-DO-LOTE-SE-CAPTURA-COM-PILHA-01`: O SIGSEGV do lote se captura com pilha
- P2 `O-FECHO-TIRA-AS-SPRINTS-FECHADAS-E-A-INTEGRACAO-COPIA-COM-FILTRO-01`: O fecho tira as sprints fechadas e a casa arquiva o bruto dos estudos velhos

### `docstring` (1: 1 P2)

- P2 `A-DOCSTRING-FICA-NO-CONTRATO-EM-SRC-SCRIPTS-E-TESTES-01`: A docstring fica no contrato em src, scripts e testes

### `desenho-contrato` (1: 1 P1)

- P1 `A-COSTURA-CONFERE-A-FOTO-CONTRA-O-DESENHO-ESCOLHIDO-01`: A costura confere a foto contra o desenho escolhido

## Onda 1: o que sobrou de P0 (1 sprints)

### `lovense-p0` (1: 1 P0)

- P0 `A-PAGINA-DE-FORA-NAO-COMANDA-A-LOVENSE-SEM-O-ACEITE-01`: A página de fora não comanda a Lovense sem o aceite

## Onda 2: conjuntos com P1 (128 sprints)

### `instalacao-1` (4: 4 P1)

- P1 `O-INSTALL-NAO-REBAIXA-O-QUE-O-ATUALIZADOR-PROVOU-01`: O install não rebaixa o que o atualizador provou
- P1 `O-UNINSTALL-SOLTA-O-PROTON-COM-A-STEAM-FECHADA-01`: O uninstall solta o Proton com a Steam fechada
- P1 `O-UPGRADE-DO-PACOTE-NAO-REENUMERA-O-CONTROLE-DO-JOGO-ABERTO-01`: O upgrade do pacote não reenumera o controle do jogo aberto
- P1 `OS-PACOTES-LEVAM-TODO-MODULO-QUE-O-PRODUTO-IMPORTA-01`: Os pacotes levam todo módulo que o produto importa

### `atualizacao-2` (8: 3 P1, 5 P2)

- P1 `A-INSTALACAO-POR-PACOTE-SABE-QUE-HA-VERSAO-NOVA-01`: A instalação por pacote sabe que há versão nova e por onde subir · desenho escolhido
- P1 `A-PECA-HEFESTO-SO-DIZ-ATUALIZADO-QUANDO-CONFERIU-01`: A peça Hefesto só diz «Atualizado» quando conferiu
- P1 `O-AVANCO-DO-DEV-OBEDECE-A-ATUALIZACAO-AUTOMATICA-E-SE-DIZ-01`: O avanço do dev obedece à Atualização automática e se diz
- P2 `A-CHAVE-NOVA-SE-SEGUE-PELA-LINHAGEM-ASSINADA-01`: A chave nova se segue pela linhagem assinada
- P2 `A-CONFIGURACAO-SE-GUARDA-ANTES-DO-AVANCO-QUE-MIGRA-01`: A configuração se guarda antes do avanço que migra
- P2 `A-NOTA-DO-INSTALL-PENDENTE-DIZ-O-QUE-FICOU-POR-FAZER-01`: A nota do install pendente diz o que ficou por fazer
- P2 `QUEM-USA-ESCOLHE-ENTRE-AS-VERSOES-PUBLICADAS-E-O-DEV-01`: Quem usa escolhe entre as versões publicadas e o dev
- P2 `VOLTAR-O-KERNEL-SE-DESFAZ-NA-PROXIMA-SUBIDA-01`: Voltar o kernel se desfaz na próxima subida

### `jogos` (6: 4 P1, 1 P2, 1 P?)

- P1 `A-STEAM-EM-FLATPAK-OU-SNAP-RECEBE-O-ATALHO-E-O-PROTON-01`: A Steam em Flatpak ou Snap recebe o atalho e o Proton fixado · desenho escolhido
- P1 `AS-RECEITAS-DE-AMBIENTE-VIAJAM-NOS-PACOTES-01`: As receitas de ambiente viajam nos pacotes
- P1 `O-DOCTOR-PERGUNTA-O-PROTON-AO-PYTHON-DO-PRODUTO-01`: O doctor pergunta o Proton fixado ao Python do produto
- P1 `OS-ARQUIVOS-DOS-LANCADORES-SE-LEEM-E-SE-ESCREVEM-POR-UM-DONO-SO-01`: Os arquivos dos lançadores se leem e se escrevem por um dono só
- P2 `A-JANELA-WAYLAND-NATIVA-SE-LE-EM-TODO-COMPOSITOR-01`: A janela Wayland nativa se lê em todo compositor, ou o produto diz que não
- P? `O-CARTAO-DO-BOTTLES-E-DO-UMU-NA-ABA-LANCADORES-01`: O cartão do Bottles e do umu na aba Lançadores · desenho escolhido

### `som` (6: 2 P1, 1 P2, 3 P?)

- P1 `O-MICROFONE-DO-CONTROLE-RENASCE-QUANDO-O-CANAL-CAI-01`: O microfone do controle renasce quando o canal cai
- P1 `O-SOM-DO-PC-VOLTA-QUANDO-O-CONTROLE-SAI-01`: O som do PC volta à saída de antes quando o controle sai
- P? `A-CAIXA-DO-CONTROLE-TOCA-SO-O-SFX-01`: A caixa do controle toca só o SFX · desenho recusado
- P2 `A-FALHA-NA-VOLTA-DO-SOM-E-DO-MICROFONE-CHEGA-AO-DIARIO-01`: A falha na volta do som e do microfone chega ao diário
- P? `A-FONTE-SO-DO-JOGO-NO-ALTO-FALANTE-E-O-VIGIA-DO-GRAFO-01`: A fonte só do jogo no alto-falante, e o vigia do grafo · desenho recusado
- P? `A-PORTA-PEDE-O-CORPO-O-LADO-E-A-FONTE-01`: A porta pede o corpo, o lado e a fonte

### `entrada` (3: 1 P1, 2 P?)

- P1 `TODA-ACAO-OFERECIDA-AO-BOTAO-TEM-QUEM-A-FACA-01`: Toda ação oferecida ao botão tem quem a faça
- P? `A-ENTRADA-DO-CONTROLE-NAO-ESPERA-O-LACO-01`: A entrada do controle não espera o laço · espera medida
- P? `O-PAD-VIRTUAL-VAI-AO-NEUTRO-QUANDO-A-ENTRADA-EMUDECE-01`: O pad virtual vai ao neutro quando a entrada do controle de fora emudece · espera medida

### `abas` (8: 5 P1, 2 P2, 1 P?)

- P1 `A-BIBLIOTECA-DE-EFEITOS-SOBREVIVE-AO-ARQUIVO-CORTADO-01`: A biblioteca «Meus efeitos» sobrevive ao arquivo cortado · desenho escolhido, sem mudança visível
- P1 `A-NAVEGACAO-INTERNA-ALCANCA-TODO-BOTAO-DA-PAGINA-01`: A Navegação Interna alcança todo botão da página · desenho escolhido
- P1 `ABRIR-A-LISTA-SUSPENSA-NAO-MANDA-GESTO-01`: Abrir uma lista suspensa não manda gesto · desenho escolhido, sem mudança visível
- P1 `O-GATILHO-E-O-MODO-SE-GUARDAM-SEM-PERFIL-ATIVO-01`: O efeito do gatilho e o «Modo automático» se guardam sem perfil ativo · desenho escolhido
- P1 `O-TESTE-DE-VIBRACAO-PARA-QUANDO-A-JANELA-SE-ESCONDE-01`: O teste de vibração para quando a janela se esconde · desenho escolhido, sem mudança visível
- P2 `A-ILUMINACAO-PUBLICADA-SAI-SEM-SOBRA-DO-DESENHO-01`: A Iluminação publicada sai sem sobra do desenho · desenho recusado
- P2 `A-INTERFACE-SO-GUARDA-GESTO-QUE-A-TELA-MANDA-01`: A interface só guarda gesto que a tela manda, e o piloto de uma aba sai · desenho escolhido, sem mudança visível · espera medida
- P? `A-TELA-TEM-CHIP-DA-MIRA-PARA-O-CONTROLE-DE-FORA-01`: A tela tem chip da mira para o controle de fora · desenho escolhido

### `abas-8-9` (7: 1 P1, 4 P2, 2 P?)

- P1 `O-SERVICO-IMPROVISADO-SO-SE-DIZ-COM-PROVA-01`: O serviço improvisado só se diz com prova · desenho escolhido
- P? `A-CONEXOES-DESCOBRE-OS-APARELHOS-DE-ENTRADA-AINDA-NAO-DECLARADOS-01`: A Conexões descobre os aparelhos de entrada ainda não declarados · desenho escolhido
- P2 `AS-ABAS-CONEXOES-E-SISTEMA-SO-DIZEM-O-QUE-ACONTECEU-01`: As abas Conexões e Sistema só dizem o que aconteceu · desenho escolhido
- P? `O-ACIONADOR-ENTREGA-A-UM-CONTROLE-DE-FORA-02`: A Conexões oferece o controle de fora como destino do acionador e o desenha pelo modelo · desenho escolhido
- P2 `O-PROCURAR-SO-MANDA-ADAPTADOR-QUE-O-BLUEZ-CONHECE-01`: O «Procurar» só manda adaptador que o BlueZ conhece · desenho escolhido
- P2 `O-REINICIAR-ESPERA-O-SERVICO-E-DIZ-O-QUE-FEZ-01`: O «Reiniciar» espera o serviço e diz o que fez · desenho escolhido
- P2 `OS-BOTOES-DO-SERVICO-IMPROVISADO-CONFEREM-ANTES-DE-AGIR-01`: Os botões do serviço improvisado conferem antes de agir · desenho escolhido

### `janela` (8: 3 P1, 4 P2, 1 P?)

- P1 `A-BANDEJA-DESLIGADA-NAO-VOLTA-NO-LOGIN-01`: A bandeja desligada não volta no login
- P1 `A-JANELA-ABRE-EM-QUALQUER-INSTALACAO-01`: A janela abre em qualquer instalação, não só na da árvore · desenho escolhido, sem mudança visível
- P1 `O-PACOTE-DE-TODA-ABA-SE-MONTA-FORA-DO-FIO-DO-GTK-01`: O pacote de toda aba se monta fora do fio do GTK · desenho escolhido, sem mudança visível
- P2 `A-ABA-LANCADORES-NAO-PINTA-NO-FIO-DO-GTK-01`: A aba Lançadores não pinta no fio do GTK · desenho escolhido, sem mudança visível
- P? `A-ABA-PERFIS-NAO-PINTA-NO-FIO-DO-GTK-01`: A aba Perfis não pinta no fio do GTK · desenho escolhido, sem mudança visível
- P2 `O-MAPA-DO-CONTROLE-NAO-RELE-OS-PERFIS-A-CADA-TIQUE-01`: O Mapa do controle não relê os perfis a cada tique · desenho escolhido, sem mudança visível
- P2 `A-BANDEJA-AVISA-QUANDO-NAO-APARECE-E-QUANDO-NAO-CONSEGUE-01`: A bandeja avisa quando não aparece e quando um clique não deu certo
- P2 `A-PRIMEIRA-PINTURA-SE-MEDE-POR-PARTE-E-ENCURTA-01`: A primeira pintura da janela se mede por parte e encurta

### `perfis` (8: 5 P1, 3 P2)

- P1 `A-EXPRESSAO-TORTA-NO-PERFIL-NAO-PARA-A-TROCA-AUTOMATICA-01`: A expressão torta num perfil não para a troca automática
- P1 `O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR-E-O-CAMPO-FICA-01`: O duplo clique renomeia sem ativar, e o campo fica · desenho escolhido
- P1 `O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR-01`: O nome que não serve se recusa antes de renomear · desenho escolhido
- P1 `O-PERFIL-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO-01`: O perfil importado de nome repetido ganha nome próprio · desenho escolhido
- P1 `O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA-01`: O perfil que vale se remove com a pergunta · desenho escolhido
- P2 `O-FREESTYLE-NAO-SE-APAGA-E-RENASCE-SE-FALTAR-01`: O Freestyle não se apaga e renasce se faltar
- P2 `O-PERFIL-DE-OUTRA-VERSAO-CONTINUA-NA-LISTA-01`: O perfil de outra versão continua na lista
- P2 `O-PERFIL-ILEGIVEL-APARECE-COM-O-MOTIVO-E-SE-APAGA-PELO-ARQUIVO-01`: O perfil ilegível aparece com o motivo, e o comando apaga e cria só o arquivo pedido

### `extensoes-1` (4: 3 P1, 1 P?)

- P1 `A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR-01`: A atualização da extensão espera o jogo e volta se cair
- P1 `A-EXTENSAO-TEM-TETO-E-CAI-SOZINHA-01`: A extensão tem teto de memória e de processos, e cai sozinha
- P1 `O-BLUETOOTH-DA-EXTENSAO-FALA-SO-COM-O-BLUEZ-01`: O Bluetooth da extensão fala só com o BlueZ
- P? `A-RECUSA-DA-EXTENSAO-FICA-NA-LINHA-DO-CARTAO-01`: A recusa da extensão fica na linha do cartão · desenho escolhido

### `extensoes-2` (8: 4 P1, 4 P?)

- P1 `O-COMO-EXTENSAO-DO-NOVO-LANCADOR-INSTALA-A-EXTENSAO-01`: O «Como extensão» do novo lançador instala a extensão · desenho escolhido
- P1 `O-INSTALL-TRAZ-A-REDE-PROPRIA-DA-CAIXA-01`: O install traz a rede própria da caixa
- P1 `O-QUE-E-DA-PESSOA-MORA-ONDE-A-CAIXA-SO-LE-01`: O que é da pessoa mora onde a caixa só lê
- P1 `O-REGISTRO-DAS-EXTENSOES-TEM-TRAVA-E-COPIA-01`: O registro das extensões tem trava e cópia
- P? `A-ENGRENAGEM-DO-LANCADOR-ABRE-A-CONFIGURACAO-DELE-01`: A engrenagem do lançador abre a configuração dele · desenho escolhido
- P? `A-PAGINA-DA-EXTENSAO-NAO-NAVEGA-PARA-FORA-01`: A página da extensão não navega para fora
- P? `O-SIM-DA-EXTENSAO-SE-LE-INTEIRO-01`: O sim da extensão se lê inteiro · desenho escolhido
- P? `A-ABA-DESLIGADA-MOSTRA-A-FAIXA-COM-O-BOTAO-LIGAR-01`: A aba desligada mostra a faixa com o botão Ligar · desenho escolhido

### `imersao` (8: 3 P1, 3 P2, 2 P?)

- P1 `A-ESCRITA-QUE-O-TETO-RECUSA-SE-TENTA-DE-NOVO-01`: A escrita que o teto recusa se tenta de novo
- P1 `A-LUZ-E-O-IMPACTO-DO-IMERSAO-TEM-PRAZO-E-SE-REPETEM-01`: A luz e o impacto do Modo imersão têm prazo e se repetem
- P1 `A-PORTA-DEVOLVE-A-LUZ-E-O-GATILHO-QUE-A-EXTENSAO-TOMOU-01`: A porta devolve a luz e o gatilho que a extensão tomou
- P2 `A-BUSCA-DAS-RECEITAS-RECUA-QUANDO-FALHA-E-RESPEITA-O-UNIVERSAL-01`: A busca das receitas recua quando falha e respeita o «Sempre o universal»
- P2 `A-CHAVE-MEMORIA-SO-APARECE-COM-O-AJUSTE-QUE-LE-A-MEMORIA-01`: A chave «Memória neste jogo» só aparece com o ajuste que lê a memória
- P? `A-EXTENSAO-SOLTA-O-TOPICO-QUE-A-RECEITA-NAO-LE-01`: A extensão solta o tópico que a receita não lê
- P? `A-JANELA-DO-IMERSAO-DIZ-A-CONEXAO-E-O-EFEITO-01`: A janela do Modo imersão diz a conexão de cada controle e o efeito que tocou · desenho escolhido
- P2 `A-RECEITA-QUE-LE-MEMORIA-OU-TELA-ASSINA-NA-LINGUA-DA-PORTA-01`: A receita que lê memória ou tela assina na língua da porta

### `lovense` (8: 4 P1, 1 P2, 3 P?)

- P1 `A-RECUSA-DO-TETO-NAO-CEGA-O-CONTROLE-DA-LOVENSE-POR-UM-SEGUNDO-01`: A recusa do teto não cega o controle da Lovense por um segundo
- P1 `O-BRINQUEDO-DA-LOVENSE-PARA-SOZINHO-COM-O-LINK-CAIDO-01`: O brinquedo da Lovense para sozinho com o link caído
- P1 `O-ESTUDO-DA-LOVENSE-NAO-FALA-DE-QUEM-USA-01`: O estudo da Lovense não fala de quem usa
- P1 `O-SERVIDOR-BUTTPLUG-SEGURA-O-NIVEL-DE-CADA-APP-01`: O servidor Buttplug segura o nível de cada app
- P? `A-LOVENSE-ACHA-TODOS-OS-SERVICOS-PELO-BLUETOOTH-01`: A Lovense acha todos os serviços pelo Bluetooth
- P2 `A-LOVENSE-NAO-FICA-VIVA-E-MUDA-01`: A Lovense não fica viva e muda
- P? `A-LOVENSE-TEM-UM-NOME-SO-01`: A Lovense tem um nome só
- P? `O-SACUDIR-SE-SOLTA-COM-O-CONTROLE-PARADO-MESMO-COM-GIRO-RESIDUAL-01`: O «Sacudir» se solta com o controle parado, mesmo com giro residual

### `instalacao-2` (8: 2 P1, 5 P2, 1 P?)

- P1 `O-AJUDANTE-DE-HOST-DO-FLATPAK-GRAVA-E-DESFAZ-NO-HOST-01`: O ajudante de host do Flatpak grava e desfaz no host
- P1 `O-ATALHO-DO-MENU-DOS-PACOTES-ABRE-A-JANELA-01`: O atalho do menu dos pacotes abre a janela
- P2 `A-PAGINA-DE-INSTALACAO-DIZ-O-QUE-O-INSTALL-FAZ-HOJE-01`: A página de instalação diz o que o install faz hoje
- P2 `A-PAGINA-DE-INSTALACAO-LEVA-AOS-PACOTES-DA-RELEASE-01`: A página de instalação leva aos pacotes da release
- P2 `O-AJUDANTE-DE-HOST-NAO-DEIXA-MARCADOR-CRU-NO-BROKER-01`: O ajudante de host não deixa marcador cru no broker
- P? `O-APPIMAGE-DA-RELEASE-NAO-DEPENDE-DA-COTA-ANONIMA-DO-GITHUB-01`: O AppImage da release não depende da cota anônima do GitHub
- P2 `O-DEB-INSTALA-NAS-DISTROS-EM-SUPORTE-01`: O .deb instala nas distros em suporte
- P2 `O-FLATPAK-RODA-SOBRE-UM-RUNTIME-EM-SUPORTE-01`: O Flatpak roda sobre um runtime em suporte

### `privilegio` (8: 3 P1, 4 P2, 1 P?)

- P1 `O-AJUDANTE-DO-ROOT-NAO-ACHA-O-BASH-PELO-PATH-DE-QUEM-CHAMA-01`: O ajudante do root não acha o bash pelo PATH de quem chama
- P1 `O-BROKER-SOLTA-A-CONTA-QUE-FICOU-ATRAS-NA-TROCA-01`: O broker solta a conta que ficou atrás na troca de usuário
- P1 `O-SECURE-BOOT-LIGADO-DEVOLVE-O-DRIVER-DE-FABRICA-01`: O Secure Boot ligado depois do install devolve o driver de fábrica
- P? `REVOGAR-O-NO-DO-FISICO-NAO-INUNDA-O-DIARIO-01`: Revogar o nó do físico não inunda o diário
- P2 `A-PLACA-ACORDADA-SO-ACEITA-O-JOGO-DE-QUEM-PEDIU-01`: A placa acordada só aceita o jogo de quem pediu
- P2 `O-BROKER-AGUENTA-RECUSA-DEMORA-E-FALTA-DE-DESCRITOR-01`: O broker e o cliente aguentam recusa, demora do logind e falta de descritor
- P2 `O-BROKER-ENTREGA-SO-AS-TECLAS-DECLARADAS-DO-ACIONADOR-01`: O broker entrega só as teclas declaradas do acionador, e a lista do root só cresce com a senha
- P2 `O-DIARIO-DO-RADIO-DO-ROOT-SO-SE-LE-POR-QUEM-USA-O-PRODUTO-01`: O diário do rádio do root só se lê por quem usa o produto

### `doctor` (3: 1 P1, 2 P2)

- P1 `O-DOCTOR-PARA-COLAR-SAI-NA-MASCARA-01`: O doctor para colar sai na máscara
- P2 `O-DOCTOR-JULGA-AS-PARADAS-E-DA-UM-VEREDITO-SO-01`: O doctor julga as paradas do serviço e dá um veredito só
- P2 `O-DOCTOR-VE-O-GIROSCOPIO-DO-PAD-USB-01`: O doctor vê o giroscópio do pad USB virtual

### `docs` (8: 1 P1, 6 P2, 1 P?)

- P1 `OS-AVISOS-DE-LICENCA-ACOMPANHAM-TODO-ARQUIVO-PUBLICADO-01`: Os avisos de licença acompanham todo arquivo publicado
- P2 `A-TRIAGEM-SO-PEDE-O-DOCTOR-A-QUEM-RELATA-DE-FORA-01`: A triagem só pede o doctor a quem relata de fora
- P2 `AS-NOTAS-DA-VERSAO-SO-ANUNCIAM-A-TELA-FEITA-01`: As notas da versão só anunciam a tela que foi feita
- P2 `AS-NOTAS-DE-VERSAO-DIZEM-SO-O-QUE-MUDA-PARA-QUEM-USA-01`: As notas de versão dizem só o que muda para quem usa
- P2 `AS-PAGINAS-DO-RADIO-DIZEM-A-FAIXA-DO-BLUEZ-DO-DOCTOR-01`: As páginas do rádio dizem a faixa do BlueZ que o doctor decide
- P? `O-CATALOGO-DE-TRADUCAO-SO-TRAZ-O-QUE-O-PRODUTO-DIZ-01`: O catálogo de tradução só traz o que o produto diz
- P2 `O-MODO-UNICO-SE-ENSINA-EM-TODA-PAGINA-DE-USO-01`: O modo único se ensina em toda página de uso
- P2 `OS-TEXTOS-DE-QUEM-CONTRIBUI-DIZEM-O-PRODUTO-DE-HOJE-01`: Os textos de quem contribui dizem o produto de hoje

### `achados-1911` (15: 8 P1, 7 P2)

- P1 `QUEM-RECUSOU-O-SUDO-SEM-SENHA-NAO-OUVE-RODE-O-INSTALL-01`: Quem recusou o sudo sem senha não ouve «rode o install»
- P1 `O-CONTROLLERS-JSON-SE-GRAVA-PELO-DONO-DA-GRAVACAO-INTEIRA-01`: O controllers.json se grava pelo dono da gravação inteira
- P1 `O-SAIR-DO-MODO-JOGO-AGE-COM-A-SUPRESSAO-LIGADA-PELO-GESTO-01`: O «Sair do modo jogo» age com a supressão ligada pelo gesto
- P1 `O-PILOTO-DE-TELA-NAO-LE-A-MAQUINA-NEM-ALCANCA-O-SUDO-01`
- P1 `O-WATCHDOG-DO-SERVICO-SE-PROVA-DEPOIS-DA-SUSPENSAO-01`: O watchdog do serviço se prova depois da suspensão
- P1 `O-MONTADOR-PROVA-QUE-OS-CONJUNTOS-EM-VOO-NAO-DIVIDEM-ARQUIVO-01`: O montador prova que os conjuntos em voo não dividem arquivo
- P1 `A-LISTA-DE-QUEM-ASSINA-VIAJA-NO-PACOTE-01`: A lista de quem assina viaja no pacote
- P1 `A-QUARENTENA-VALE-TAMBEM-NO-DOWNLOAD-E-NO-RECUO-01`: A quarentena vale também no download e no recuo
- P2 `A-REGUA-DAS-GRAVACOES-VIGIA-TODA-FORMA-DE-ESCREVER-01`: A régua das gravações vigia toda forma de escrever
- P2 `O-INSTALL-DIZ-A-RECUSA-DO-GRUB-EM-UMA-FRASE-01`: O install diz a recusa do grub em uma frase
- P2 `O-UNINSTALL-PROCURA-O-MODULO-ONDE-O-INSTALL-O-POE-01`: O uninstall procura o módulo onde o install o põe
- P2 `O-TESTE-DO-DESLIGAR-DO-SERVICO-ESPERA-O-IPC-SUBIR-01`: O teste do desligar do serviço espera o IPC subir
- P2 `O-GANCHO-DO-RUFF-ACHA-O-EXECUTAVEL-EM-TODA-ARVORE-01`: O gancho do ruff acha o executável em toda árvore
- P2 `O-BROKER-DEIXA-A-PILHA-NO-DIARIO-QUANDO-CAI-01`: O broker deixa a pilha no diário quando cai
- P2 `O-MAPA-CITA-A-LUZ-DO-MICROFONE-NA-LINHA-CERTA-01`

## Onda 3: P2 e P3 (143 sprints)

### `atualizacao-1` (1: 1 P2)

- P2 `A-LINHA-DA-ATUALIZACAO-MOSTRA-O-QUE-A-VERSAO-TRAZ-01`: A linha da atualização mostra o que a versão traz · desenho recusado

### `tato` (3: 1 P2, 2 P?)

- P? `O-SERVICO-NAO-DISPUTA-O-GIL-COM-O-CONTROLE-01`: O serviço não disputa o GIL com o controle
- P? `A-ARMA-DE-CADA-ESTILO-TEM-UM-DONO-SO-01`: A arma de cada estilo tem um dono só · desenho escolhido, sem mudança visível
- P2 `A-RECUSA-DO-TOCADOR-SE-DIZ-E-CAI-PARA-O-MOTOR-01`: A recusa do tocador se diz e cai para o motor

### `radio` (3: 3 P?)

- P? `O-ADAPTADOR-NAO-TRAVA-AO-CANCELAR-A-BUSCA-01`: O adaptador não trava ao cancelar a busca
- P? `O-AGENTE-DE-PAREAMENTO-SO-RESPONDE-AO-GESTO-01`: O agente de pareamento só responde ao gesto
- P? `O-BLUEZ-DA-CASA-LEVA-AS-CURAS-DE-SEGURANCA-DEPOIS-DO-5-88-01`: O BlueZ da casa leva as curas de segurança depois do 5.88

### `servico` (1: 1 P?)

- P? `A-LEITURA-DA-FEATURE-NAO-SEGURA-A-TRAVA-DO-LACO-01`: A leitura da feature não segura a trava do laço · espera medida

### `mapa` (4: 3 P2, 1 P?)

- P? `O-PERFIL-COM-TECLA-LIGA-O-TECLADO-01`: O perfil que manda tecla liga o teclado virtual · desenho escolhido, sem mudança visível
- P2 `A-CAPTURA-DE-TECLA-RESPONDE-A-TECLA-QUE-NAO-CONHECE-01`: A captura de tecla responde à tecla que não conhece · desenho escolhido
- P2 `A-EDICAO-DO-MAPA-DO-CONTROLE-SO-SE-LARGA-AO-SAIR-01`: A edição do Mapa do controle só se larga ao sair · desenho escolhido
- P2 `O-MAPA-DO-CONTROLE-DIZ-DE-QUEM-E-CADA-TROCA-01`: O Mapa do controle diz de quem é cada troca e para qual jogo · desenho escolhido

### `historia` (3: 3 P?)

- P? `A-HISTORIA-REESCRITA-UMA-VEZ-SO-01`: A história reescrita uma vez só: a coautoria e a biblioteca pessoal
- P? `A-HISTORIA-SEM-A-BIBLIOTECA-PESSOAL-01`: A história sem a biblioteca pessoal
- P? `AS-EXTENSOES-DA-CASA-SAO-GPL-3-E-PUBLICAS-01`: As extensões da casa são GPL-3 e públicas

### `jogos-p2` (4: 4 P2)

- P2 `O-DOWNLOAD-DO-PROTON-CORTADO-RETOMA-DE-ONDE-PAROU-01`: O download do Proton cortado retoma de onde parou
- P2 `O-JOGO-DE-FORA-ADICIONADO-A-STEAM-RECEBE-O-ATALHO-01`: O jogo de fora adicionado à Steam recebe o atalho
- P2 `O-JOGO-QUE-NAO-ABRE-NO-GE-NOVO-TEM-SAIDA-01`: O jogo que não abre no GE novo tem saída · desenho recusado
- P2 `O-MODO-DE-ENERGIA-ESPERA-O-ULTIMO-JOGO-E-O-HEROIC-E-O-DESTA-CONTA-01`: O modo de energia espera o último jogo, e o Heroic aberto é o desta conta

### `tato-p2` (5: 1 P2, 4 P?)

- P? `A-HAPTICA-PELO-RADIO-NAO-SOLTA-O-MOTOR-QUE-O-JOGO-ACENDE-01`: A háptica pelo rádio não solta o motor que o jogo acende
- P? `A-VIBRACAO-FINA-NAO-SE-CORTA-NO-TETO-01`: A vibração fina não se corta no teto
- P2 `O-LACO-DO-TATO-DIZ-A-FALHA-E-SEGUE-DE-PE-01`: O laço do tato e o da telemetria dizem a falha e seguem de pé
- P? `O-SUMICO-NO-CABO-SE-MEDE-NOS-TRES-PONTOS-01`: O sumiço no cabo se mede nos três pontos
- P? `O-TATO-VIVO-CABE-NO-RADIO-01`: O tato vivo cabe no rádio

### `som-p2` (4: 2 P2, 1 P3, 1 P?)

- P2 `A-VOLTA-DO-MICROFONE-DEVOLVE-A-FONTE-DE-ANTES-01`: A volta do microfone devolve a fonte de antes
- P2 `O-LACO-DE-AUDIO-MORRE-COM-A-JANELA-01`: O laço de áudio morre com a janela
- P? `TODO-LOGGER-PASSA-PELO-DONO-DO-LOG-01`: Todo logger passa pelo dono do log
- P3 `OS-TOCADORES-DA-HAPTICA-MORREM-COM-O-PAI-01`: Os tocadores da háptica morrem com o pai

### `radio-p2` (7: 4 P2, 3 P?)

- P2 `AS-ORDENS-SO-MANDAM-MOVER-O-QUE-A-MAO-ALCANCA-01`: As ordens só mandam mover o que a mão alcança
- P2 `O-APARELHO-ESQUECIDO-NAO-VOLTA-DOS-SNAPSHOTS-01`: O aparelho esquecido não volta dos snapshots
- P? `O-DONGLE-WIFI-CAI-NOS-DOIS-MODOS-USB-01`: O dongle Wi-Fi cai nos dois modos USB
- P2 `O-QUE-O-HEFESTO-MUDA-NO-SISTEMA-VOLTA-COMO-ESTAVA-01`: O que o Hefesto muda no sistema volta como estava
- P? `O-RADIO-DO-NOTEBOOK-DORME-NA-BATERIA-01`: O rádio do notebook dorme na bateria
- P2 `O-RADIO-NAO-INSISTE-EM-QUEM-NAO-VAI-RESPONDER-01`: O rádio não insiste em quem não vai responder
- P? `O-ZERO-TRES-SEIS-SE-MEDE-NA-MESA-01`: O 0x36 se mede na mesa · desenho escolhido, sem mudança visível

### `entrada-p2` (7: 5 P2, 2 P?)

- P? `A-MIRA-GANHA-SENSIBILIDADE-HORIZONTAL-E-VERTICAL-NA-TELA-01`: A mira ganha sensibilidade horizontal e vertical na tela · desenho recusado
- P2 `O-DSU-TEM-TETO-DE-INSCRICOES-POR-CLIENTE-01`: O servidor DSU tem teto de inscrições por cliente
- P? `O-PAD-VIRTUAL-SE-APRESENTA-COMO-O-COMPOSTO-DA-SONY-01`: O pad virtual se apresenta como o composto da Sony: o HID na interface 3, o áudio nas 0 a 2
- P2 `O-QUE-ESTA-PRESO-SE-SOLTA-QUANDO-A-FONTE-CALA-01`: O que está preso se solta quando a fonte cala
- P2 `O-TECLADO-NA-TELA-ABRE-NO-GNOME-E-NO-KDE-01`: O teclado na tela abre no GNOME e no KDE
- P2 `O-TECLADO-VIRTUAL-DIGITA-TODA-TECLA-QUE-O-PERFIL-ACEITA-01`: O teclado virtual digita toda tecla que o perfil aceita
- P2 `O-TOQUE-CURTO-COM-O-PS-TROCA-E-O-LIMIAR-SAI-COM-O-JOGO-01`: O toque curto com o PS segurado troca, e o limiar do DSX sai com o jogo

### `servico-p2` (8: 6 P2, 2 P?)

- P? `A-PARADA-DO-IPC-NAO-ESTOURA-O-TETO-CALADA-01`: A parada do IPC não estoura o teto calada
- P2 `O-ESTADO-DO-SERVICO-SE-LE-SEM-PARAR-O-LACO-01`: O estado do serviço se lê sem parar o laço
- P2 `O-IPC-RECUSA-O-QUE-NAO-SERVE-E-RESPONDE-SEMPRE-01`: O IPC recusa o que não serve e responde sempre
- P2 `O-PAD-VIRTUAL-QUE-NAO-VOLTA-DO-NATIVO-SE-DIZ-01`: O pad virtual que não volta do Nativo se diz
- P2 `O-PASSO-QUE-FALHA-EM-TODO-LACO-CONTA-E-AVISA-UMA-VEZ-01`: O passo que falha em todo laço do serviço conta e avisa uma vez
- P2 `O-PEDIDO-GRANDE-DEMAIS-AO-IPC-RECEBE-O-ERRO-01`: O pedido grande demais ao IPC recebe o erro
- P2 `O-SERVICO-EM-REPOUSO-ESPERA-QUEM-CONSOME-01`: O serviço em repouso espera quem consome
- P? `O-TIQUE-NAO-ESPERA-AS-VARREDURAS-NO-POOL-01`: O tique não espera as varreduras no pool · espera medida

### `servico-privilegio-p2` (6: 6 P2)

- P2 `A-BATERIA-DO-COMPUTADOR-SE-RECONHECE-PELO-TIPO-01`: A bateria do computador se reconhece pelo tipo, e não pelo nome
- P2 `AS-PASTAS-DO-PRODUTO-NASCEM-FECHADAS-01`: As pastas do produto nascem fechadas
- P2 `O-CLIENTE-MUDO-NAO-PRENDE-AS-METRICAS-NEM-A-PARADA-01`: O cliente mudo não prende as métricas nem a parada
- P2 `O-KERNEL-LOG-DA-VIGIA-GIRA-NO-TETO-01`: O kernel.log da vigia gira no teto
- P2 `O-QUADRO-E-O-CARTORIO-QUE-FALHAM-SE-DIZEM-01`: O quadro e o cartório que falham se dizem no diário
- P2 `OS-FIOS-DO-SERVICO-TEM-NOME-E-CUSTO-MEDIDO-01`: Os fios do serviço têm nome e custo medido

### `abas-janela-p2` (6: 2 P2, 4 P?)

- P2 `A-CALIBRAR-NAO-REDESENHA-O-CONTROLE-A-CADA-TIQUE-01`: A Calibrar não redesenha o controle a cada tique
- P? `O-APAGADO-DAS-ABAS-06-08-E-DO-TOPO-SEGUE-A-REGRA-DA-CASA-01`: O apagado das abas 06 e 08 e do topo segue a regra da casa · desenho escolhido
- P? `O-FOCO-DO-CODIGO-NAS-CONEXOES-E-NOS-PERFIS-NAO-ABRE-A-DICA-01`: O foco do código nas Conexões e nos Perfis não abre a dica · desenho escolhido
- P? `O-NUMERO-DA-BARRA-SEGUE-O-POLEGAR-SEM-ESPERAR-O-TIQUE-01`: O número da barra segue o polegar sem esperar o tique · desenho escolhido
- P? `OS-TRES-FIOS-DE-FORA-PASSAM-PELO-DONO-DOS-FIOS-01`: Os três fios de fora passam pelo dono dos fios · desenho escolhido, sem mudança visível
- P2 `TODO-BOTAO-DAS-ABAS-RECEBE-FOCO-E-SE-ANUNCIA-01`: Todo botão das abas recebe o foco do teclado e se anuncia ao leitor de tela · desenho escolhido, sem mudança visível

### `mapa-p2` (8: 7 P2, 1 P?)

- P2 `A-REGUA-DA-FALA-DE-TELA-MEDE-OU-SAI-01`: A régua da fala de tela mede ou sai
- P2 `O-ARRANJO-JULGA-PELO-QUE-ESTA-MAQUINA-LEU-E-RESPONDEU-01`: O arranjo julga pelo que esta máquina leu e respondeu · desenho escolhido
- P2 `O-MAPA-DAS-PORTAS-NASCE-DA-PAGINA-DE-HOJE-01`: O mapa das entradas nasce da página de hoje, sem a cadeia de remendos · desenho escolhido, sem mudança visível
- P2 `O-MAPA-DAS-PORTAS-NUNCA-MOSTRA-O-EXEMPLO-NO-LUGAR-DA-LEITURA-01`: O mapa das entradas nunca mostra o exemplo no lugar da leitura · desenho escolhido
- P2 `O-MAPA-DE-CANAIS-TEM-A-TROCA-A-SEQUENCIA-E-A-TECLA-01`: O mapa de canais tem a troca, a sequência e a tecla por botão
- P? `O-MAPA-DIZ-OS-CANAIS-DA-PORTA-DAS-EXTENSOES-01`: O mapa diz os canais da porta das extensões
- P2 `O-NOME-DO-APARELHO-ENTRA-ESCAPADO-NO-MAPA-DAS-PORTAS-01`: O nome do aparelho entra escapado no mapa das entradas · desenho escolhido
- P2 `O-PAINEL-DA-ENTRADA-DIZ-O-LUGAR-E-MOVE-SEM-ARRASTO-01`: O painel da entrada diz o lugar e move sem arrasto · desenho escolhido

### `perfis-p2` (5: 4 P2, 1 P?)

- P2 `A-LINHA-DE-COMANDO-SO-FALA-DIRETO-COM-O-CONTROLE-COM-O-SERVICO-PARADO-01`: A linha de comando só fala direto com o controle com o serviço parado
- P? `ATIVAR-O-PERFIL-NAO-RODA-O-PACTL-NO-LACO-01`: Ativar o perfil não roda o pactl no laço
- P2 `O-SERVICO-PARADO-TEM-UMA-FRASE-E-UM-CODIGO-SO-01`: O serviço parado tem uma frase e um código só
- P2 `O-STATUS-E-A-BATERIA-MOSTRAM-CADA-CONTROLE-01`: O status, a bateria e o terminal mostram cada controle, com o valor vivo
- P2 `OS-CAMINHOS-DE-ANTES-SE-MIGRAM-UMA-VEZ-SO-01`: Os caminhos de antes se migram uma vez só

### `experimentais-extensoes-p2` (8: 5 P2, 3 P?)

- P? `A-CHAVE-DA-EXTENSAO-DIZ-QUANDO-A-PORTA-RECUSA-01`: A chave da extensão diz quando a porta recusa · desenho escolhido
- P? `A-EXTENSAO-TROCA-DE-ENDERECO-SEM-PERDER-AS-OPCOES-01`: A extensão troca de endereço sem perder as opções
- P2 `A-LINHA-DE-COMANDO-DAS-EXTENSOES-RESPONDE-COM-FRASE-01`: A linha de comando das extensões responde com frase
- P? `A-RECUSA-DO-TEMA-NAO-NASCE-NA-COR-DO-ALARME-01`: A recusa do tema não nasce na cor do alarme · desenho escolhido
- P2 `A-VARIAVEL-NUMERICA-ILEGIVEL-NAO-DERRUBA-O-SERVICO-01`: A variável de ambiente numérica ilegível não derruba o serviço
- P2 `AS-JANELAS-DA-EXPERIMENTAL-NAO-ABREM-COM-O-EXEMPLO-01`: As janelas da Experimental não abrem com o exemplo
- P2 `O-PROCURAR-UM-JOGO-FILTRA-A-LISTA-01`: O «Procurar um jogo» filtra a lista
- P2 `O-STEAM-PADRAO-DA-NAVEGACAO-TEM-QUEM-O-APLIQUE-01`: O «Steam padrão» da Navegação tem quem o aplique · desenho escolhido

### `extensoes-p2-1` (8: 1 P2, 1 P3, 6 P?)

- P? `O-DIARIO-DA-EXTENSAO-SE-LE-NO-MENU-01`: O diário da extensão se lê no menu · desenho escolhido
- P? `O-DOCTOR-OLHA-AS-EXTENSOES-01`: O doctor olha as extensões
- P? `O-LIGADA-EM-SOBREVIVE-A-ATUALIZACAO-01`: O ligada_em sobrevive à atualização
- P? `O-MANIFESTO-DIZ-O-HEFESTO-QUE-PEDE-01`: O manifesto diz o Hefesto que pede
- P? `O-MOD-DE-FABRICA-TRAZ-DE-NOVO-QUANDO-SE-PEDE-01`: O mod de-fábrica traz de novo quando se pede
- P2 `O-VIGIA-DO-PLUGIN-CONTA-OS-LENTOS-POR-JANELA-01`: O vigia do plugin conta os tiques lentos por janela
- P? `REMOVER-A-EXTENSAO-DESFAZ-O-PREPARO-01`: Remover a extensão desfaz o preparo
- P3 `O-PLUGIN-DE-ANTES-SAI-EM-FAVOR-DAS-EXTENSOES-01`: O plugin de antes sai em favor das extensões

### `extensoes-p2-2` (8: 5 P2, 3 P?)

- P2 `A-EXTENSAO-RECEBE-UM-APELIDO-DO-CONTROLE-01`: A extensão recebe um apelido do controle
- P2 `A-EXTENSAO-SO-FICA-VERDE-DEPOIS-DE-SE-APRESENTAR-01`: A extensão só fica verde depois de se apresentar · desenho escolhido
- P? `A-PAGINA-QUE-FALTA-RECUSA-SO-A-PAGINA-E-NAO-A-EXTENSAO-01`: A página que falta recusa só a página, e não a extensão · desenho escolhido
- P? `A-PASTA-INSTALA-SO-O-QUE-O-GIT-CONHECE-01`: A pasta instala só o que o git conhece
- P2 `A-PORTA-TEM-TETO-DE-ASSINATURAS-PEDIDOS-E-CONEXOES-01`: A porta tem teto de assinaturas, pedidos e conexões
- P2 `A-VERSAO-RECUSADA-NAO-SE-BAIXA-DE-NOVO-01`: A versão recusada não se baixa de novo
- P2 `A-VIGIA-DAS-EXTENSOES-NAO-DESISTE-NEM-MORRE-CALADA-01`: A vigia das extensões não desiste nem morre calada · desenho escolhido
- P? `O-ADR-021-E-A-PORTA-DIZEM-O-QUE-EXISTE-01`: O ADR 021 e a porta dizem o que existe

### `imersao-p2` (8: 6 P2, 2 P?)

- P2 `A-RECEITA-TORTA-SE-RECUSA-COM-A-LINHA-E-NAO-DERRUBA-A-EXTENSAO-01`: A receita torta se recusa com a linha e não derruba a extensão
- P2 `A-TAREFA-DE-FUNDO-QUE-CAI-ENCERRA-A-EXTENSAO-01`: A tarefa de fundo que cai encerra a extensão, e o Hefesto a relança
- P? `AS-RECEITAS-DA-COMUNIDADE-SE-PUBLICAM-01`: As receitas da comunidade se publicam
- P2 `O-CI-DAS-RECEITAS-ASSINA-SO-COM-CODIGO-FIXADO-01`: O CI das receitas assina só com código fixado
- P2 `O-MODO-IMERSAO-REPOUSA-QUANDO-NAO-HA-O-QUE-TOCAR-01`: O Modo imersão repousa quando não há o que tocar
- P? `O-MODO-IMERSAO-UNIVERSAL-01`: O Modo imersão universal
- P2 `O-README-E-A-VERSAO-DO-IMERSAO-DIZEM-O-QUE-EXISTE-01`: O README e a versão do Modo imersão dizem o que existe
- P2 `O-SENTIDO-POR-CONTROLE-GUARDA-A-LEITURA-DE-CADA-CONTROLE-01`: O sentido por controle guarda a leitura de cada controle

### `lovense-imersao-p2` (4: 3 P2, 1 P?)

- P? `AS-MEDIDAS-DO-MODO-IMERSAO-VEM-ANTES-DO-CODIGO-01`: O que o Modo imersão supõe se prova no aparelho
- P2 `AS-PROVAS-DO-IMERSAO-MORDEM-NO-CONTRATO-COM-A-PORTA-01`: As provas do Modo imersão mordem no contrato com a porta
- P2 `O-JOGO-HAPTICA-DIZ-SO-O-QUE-O-JOGO-MANDOU-01`: O jogo.haptica diz só o que o jogo mandou
- P2 `OS-DADOS-DA-LOVENSE-NASCEM-FECHADOS-01`: Os dados da Lovense nascem fechados

### `ext-pequenas-p2` (7: 6 P2, 1 P?)

- P2 `A-BIBLIOTECA-GRANDE-OU-COM-PASTA-RUIM-CHEGA-LIDA-01`: A biblioteca grande, recursiva ou com uma pasta ruim chega lida e diz onde cortou
- P2 `A-EXTENSAO-QUE-FALHA-NUM-CLIQUE-NAO-FICA-SURDA-01`: A extensão que falha num clique não fica surda com a luz presa
- P2 `CADA-EXTENSAO-CONFERE-A-PROPRIA-VERSAO-NO-CI-01`: Cada extensão confere a própria versão, licença e porta no CI
- P2 `O-LEITOR-DO-LUTRIS-ACHA-O-PROTON-DE-TODO-JOGO-01`: O leitor do Lutris acha o Proton e a janela de todo jogo, dentro da caixa
- P? `O-LUTRIS-FIXA-O-PROTON-PELA-EXTENSAO-01`: O Lutris fixa o Proton pela extensão
- P2 `O-MGBA-E-O-RETROARCH-SE-LEEM-PELO-QUE-O-EMULADOR-GRAVA-01`: O mGBA e o RetroArch se leem pelo que o emulador grava
- P2 `O-PERFIL-POR-JOGO-VALE-NOS-EMULADORES-01`: O perfil por jogo vale nos emuladores, ou o texto não o promete

### `instalacao-p2` (7: 7 P2)

- P2 `O-FLATPAK-SO-FALA-COM-OS-NOMES-QUE-USA-01`: O Flatpak só fala com os nomes que usa
- P2 `O-INSTALL-AVISA-QUE-APAGA-O-PROTON-SEM-JOGO-01`: O install avisa que apaga o Proton sem jogo
- P2 `O-INSTALL-DIZ-O-ERRO-REAL-DO-PIP-01`: O install diz o erro real do pip
- P2 `O-INSTALL-NAO-OFERECE-APPIMAGE-QUE-QUEBRA-FORA-DA-PASTA-DE-BUILD-01`: O install não oferece AppImage que quebra fora da pasta de build
- P2 `O-UNINSTALL-DEVOLVE-O-STEAM-INPUT-DE-ANTES-01`: O uninstall devolve o Steam Input de antes
- P2 `O-UNINSTALL-ENCERRA-SO-OS-PROCESSOS-DO-PRODUTO-01`: O uninstall encerra só os processos do produto
- P2 `OS-PACOTES-LEVAM-O-PERFIL-UCM-DO-DUALSENSE-01`: Os pacotes levam o perfil UCM do DualSense

### `ci-p2-1` (8: 4 P2, 4 P?)

- uma sprint de processo, citada só no diretório de processo
- P? `A-FILA-RECUSA-CICLO-DE-ESPERA-01`: A fila recusa ciclo de espera
- P2 `AS-ACTIONS-QUE-PUBLICAM-ANDAM-POR-SHA-01`: As actions que publicam andam por SHA
- P2 `AS-REGUAS-DA-SUITE-MORDEM-E-O-TESTE-PRESO-SE-NOMEIA-01`: As réguas da suíte mordem e o teste preso se nomeia
- P2 `O-CODEQL-VOLTA-A-LER-O-JAVASCRIPT-01`: O CodeQL volta a ler o JavaScript
- P2 `O-PULO-DA-SUITE-TEM-CENSO-E-A-SONDA-NAO-ESCONDE-FALHA-01`: O pulo da suíte tem censo e a sonda não esconde falha
- P? `O-RUNNER-MONTA-O-CABO-E-O-RADIO-DA-RODADA-01`: O runner monta o cabo e o rádio da rodada
- P? `O-RUNTIME-DA-RODADA-VEM-DA-IMAGEM-PUBLICA-01`: O runtime da rodada vem da imagem pública

### `ci-p2-2` (8: 2 P2, 6 P?)

- P? `A-LEITURA-DO-GADGET-SUMIDO-SE-PROVA-POR-ENCONTRO-01`: A leitura do gadget sumido se prova por encontro
- P? `A-RODADA-DO-PROTON-RODA-FORA-DA-MAQUINA-DE-QUEM-JOGA-01`: A rodada do Proton roda fora da máquina de quem joga
- P? `AS-CITACOES-QUE-O-REAPONTAR-NAO-ACHA-SE-ACERTAM-01`: As citações que o reapontar não acha se acertam
- P? `O-BOOT-RETOMA-O-FREESTYLE-SEM-OSCILAR-01`: O boot retoma o Freestyle sem oscilar
- P? `O-CARD-DO-RADIO-CARREGANDO-NAO-CAI-NO-IMPORT-01`: O teste do card do rádio carregando não cai no import
- P2 `O-NOME-DA-MAQUINA-NAO-ENTRA-NO-REPOSITORIO-01`: O nome da máquina não entra no repositório · desenho escolhido, sem mudança visível
- P? `O-PRAZO-DO-DIARIO-E-DO-PREPARO-SE-PROVA-POR-ENCONTRO-01`: O prazo do diário e do preparo se prova por encontro
- P2 `O-PROCURAR-NAO-RECUSA-A-JANELA-QUE-JA-ABRIU-01`: O «Procurar» não recusa a janela que já abriu

### `ci-p2-3` (2: 2 P2)

- P2 `O-TEMPO-DA-SUITE-SE-MEDE-COM-A-PARTE-REAPROVEITADA-INTEIRA-01`: O tempo da suíte se mede quando a parte reaproveitada rodou inteira
- P2 `OS-INTERMITENTES-DO-CI-TEM-LISTA-MEDIDA-01`: Os intermitentes do CI têm lista medida
