# A porta das modificações

O contrato entre uma modificação ([ADR-021](../adr/021-modificacoes-por-processo.md)) e o serviço.
Versão da porta: **2** (`API_DAS_MODIFICACOES`, em `src/hefesto_dualsense4unix/mods/__init__.py`). A 2
(19/10/2026) acrescentou o `aviso` do manifesto e o `lancador.jogos`; o resto é o da 1, e a faixa
`">=1,<3"` aceita as duas.

## O que o filho recebe

O supervisor abre o processo com este ambiente, e com mais nada da sessão:

| variável | o que é |
| --- | --- |
| `HEFESTO_MOD_SOCKET` | o caminho da porta, `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/mods.sock` |
| `HEFESTO_MOD_FICHA` | a ficha desta execução (aleatória, nova a cada abertura) |
| `HEFESTO_MOD_ID` | o `id` do manifesto |
| `HEFESTO_MOD_DADOS` | a pasta gravável da modificação |
| `HEFESTO_MOD_API` | a versão da porta que este Hefesto fala |

O diretório de trabalho é a pasta do código, que dentro da caixa é só de leitura. A saída e o erro do
processo vão para `diario.log`, na pasta de dados.

## O enquadramento

É o mesmo do IPC principal: um objeto JSON-RPC 2.0 por linha, terminado em `\n`, com até 32 KiB por
pedido. A conexão começa obrigatoriamente com `mod.ola`. Qualquer outra primeira palavra, uma ficha
desconhecida ou um processo que não foi o supervisor que abriu fecham a conexão.

## Os métodos

| método | params | pede | resposta |
| --- | --- | --- | --- |
| `mod.ola` | `{ficha}` | a ficha e o `SO_PEERCRED` | `{id, api, permissoes}` |
| `eventos.assinar` | `{topicos: [...]}` | `ler:<tópico>` para cada um | `{assinados}` |
| `luz.set` | `{uniq, rgb: [r, g, b], brilho?}` | `escrever:luz` | o resultado do `led.set` |
| `vibracao.set` | `{uniq, fraco, forte}` (0 a 255) | `escrever:vibracao` | o resultado do `rumble.set` |
| `gatilho.set` | `{uniq, lado: esquerdo\|direito, modo, params}` | `escrever:gatilho` | o resultado do `trigger.set` |
| `eventos.publicar` | `{topico, dados}` | `publicar:<tópico>` | `{publicado}` |
| `acessorios.estado` | `{ligado, nivel (0 a 10), perfil?, aparelhos: [...], ajustes?}` | `ler:acessorios.gesto` | `{recebido}` |
| `luz.pulso` | `{uniq, cor: [r, g, b], cor_quente?, fundo (0 a 1), periodo_s}` ou `{uniq, parar: true}` | `pedir:luz.pulso` | `{aplicado, motivo, periodo_s?}` |
| `lancador.jogos` | `{jogos: [{chave, nome, abrir: [...], janela?}]}` | `lancador` | `{recebidos}` |
| `controles.lista` | `{}` | `ler:conexao` | `{controles: [{uniq, jogador}]}` |

Os tópicos de leitura são estes. Os quatro primeiros são do controle do posto:

- `estado`: o estado do controle a cada tique;
- `botoes`: um botão apertado ou solto;
- `bateria`: a carga;
- `conexao`: o controle que entra ou sai.

Os demais são do jogo e do perfil, e cada um é uma permissão à parte:

- `jogo.vibracao` (`ler:jogo.vibracao`) entrega duas notificações. `nome: "jogo.vibracao"` é a vibração que o
  jogo pede a UM controle, de qualquer jogador (P1 a P4), com o `uniq` dele no envelope:
  `{uniq, jogador, pedido: [fraco, forte], efetivo: [fraco, forte], jogo: [esq, dir], toques: [esq, dir], t}`.
  `pedido` é o que o jogo mandou; `efetivo` é o que chegou aos motores (`[0, 0]` quando o par fixado pela tela
  vence ou a escrita foi recusada), e a batida segue o `efetivo`. `jogo` e `toques` dizem de quem é cada parte do
  `efetivo`, por lado do controle (`esq` é o motor forte, `dir` o fraco; os dois ficam em `pedido`/`efetivo` na
  ordem `[fraco, forte]`): `toques` é o que os toques do perfil (`meus_toques`) pediram, `[0, 0]` quando o modo
  é só o jogo; nenhum dos dois traz nome de botão. `jogador` é o número que o controle acende agora (ou `null`); `t` é
  o `time.monotonic()` do serviço. Enquanto o `efetivo` não for zero o evento se repete a cada 250 ms, mesmo
  sem valor novo: quem acompanha para o aparelho dele quando a batida some. O teto é de 60 por segundo por
  controle; o que o teto atrasa sai no tique seguinte, e o último valor, sobretudo o zero, sempre chega.
  `nome: "jogo.fechou"` (`{appid, t}`) diz que o jogo em cena saiu; quem vibrava recebe antes o zero que
  faltava. A batida roda no tique do gamepad virtual do P1, e `jogo.fechou` sai do tique do autoswitch (só com
  ele ligado): no Modo Nativo o Hefesto não vê a vibração;
- `perfil.jogo` (`ler:perfil.jogo`) entrega `nome: "perfil.trocou"`: `{perfil, jogo, estilo, controles: [...], t}`,
  em que `jogo` é a chave do jogo em cena (`steam_app_<N>`, ou `null` fora de jogo), `perfil` o nome do perfil
  efetivo e `estilo` a chave do estilo dele (ou `null`). `controles` tem um item por controle,
  `{jogador, perfil, jogo, estilo}`, com o número que o controle acende (ou `null`): a extensão segue o
  controle cujo `jogo` está na lista que a pessoa escolheu. Sai a cada troca de perfil, de jogo ou de estilo
  (no arquivo do perfil), e quando um controle entra ou sai; quando o jogo fecha, sai depois do `jogo.fechou`.
  É estado, não evento: o serviço guarda o último, e quem assina depois recebe o de agora logo na assinatura.
  Nenhuma marca do perfil sai neste evento, nem em outro, e o envelope leva o `uniq` do posto;
- `jogo.gatilho` (`ler:jogo.gatilho`) entrega `nome: "jogo.gatilho"`: o efeito que o jogo escreveu no gatilho de
  UM controle, de P1 a P4, `{uniq, jogador, lado, modo, forca, posicao, t}`. `lado` é `esquerdo` ou `direito`;
  `modo` é `desligado`, `resistencia`, `arco`, `galope`, `arma`, `vibracao`, `metralhadora` ou `outro`; `forca`
  vai de 0 a 1 (o galope diz 1, porque o bloco dele carrega pés e frequência) e `posicao` é onde o efeito começa
  no curso, de 0 a 1. Sai uma vez por mudança de bloco, no máximo 50 por segundo por lado; o que o teto atrasa
  sai no tique seguinte e o último valor sempre chega. Quando o pad sai ou o jogo fecha, quem tinha efeito
  recebe `desligado`. Vale para cabo e Bluetooth;
- `jogo.haptica` (`ler:jogo.haptica`) entrega `nome: "jogo.haptica"`: o envelope da háptica por áudio de UM
  controle, `{uniq, jogador, intensidade: [esquerdo, direito], t}`, cada lado de 0 a 1 (o RMS dos canais 3 e 4;
  senoide de fundo de escala vale 1), em passos de 0,02, de 20 em 20 ms, no máximo 50 por segundo por controle e
  só quando o nível muda. Enquanto não for zero o evento se repete a cada 250 ms. Sem som por meio segundo, com
  a fonte seca ou com o jogo fechado, o zero sai. No cabo e no Bluetooth é o que o controle recebe: depois do
  ganho da háptica dele, e zero quando a vibração não vai a ele. Não há segundo gravador: o envelope lê o PCM
  que a ponte do rádio e o ouvido da placa já leem;
- `jogo.acessorio` (`ler:jogo.acessorio`) entrega `nome: "jogo.acessorio"`: o que o jogo pede a um acessório,
  passado por outra extensão, `{funcoes: {<função>: 0 a 1}, origem, t}`. O nome de cada função é das extensões que
  conversam (minúsculas, algarismos e `_`, até 32 letras, começando por letra; até 16 por extensão); o Hefesto não
  sabe que acessório é nem o que cada função faz, e quem assina traduz cada uma para o aparelho dele. `origem` é o
  `id` da extensão que publicou (o serviço o põe; o que a extensão mandar em `origem` ou `t` cai) e `t` é o
  `time.monotonic()` do serviço. Quem publica nunca recebe o próprio evento. Quando a extensão que publicou sai
  (parada, morta ou desligada) com alguma função acima de zero, o serviço publica em nome da extensão um
  `jogo.acessorio` com cada função que ela usou em 0, e quem assina nunca fica com a última força presa. Só existe
  publicado por extensão: o serviço não o origina;
- `acessorios.gesto` (`ler:acessorios.gesto`) entrega `nome: "acessorios.gesto"`: o gesto do PS que comanda os
  acessórios, `{uniq, jogador, gesto, valor}`. `gesto` é `sobe`, `desce`, `para`, `perfil_seguinte`,
  `perfil_anterior`, `nivel_ao_vivo` (`valor` de 0 a 1), `surto` ou `camada` (`valor` 1 liga, 0 desliga); nunca um
  botão cru. O «Parar tudo» da janela chega como `para` com `uniq` e `jogador` nulos e `mod`, o `id` da
  extensão a que se destina; só ela o recebe. Só existe com a modificação ligada e com aparelho: ela devolve o próprio estado por
  `acessorios.estado`, o Hefesto guarda o último e, sem ele (ou sem aparelho, ou quando a conexão cai), PS + R2 é o
  que sempre foi. Enquanto o gesto vale, o R2, o L2, o R1, o L1 e o direcional que o comandam não chegam ao
  jogo, por controle. `ajustes` aceita `limiar_fundo` (50 a 100 %), `acelerador`, `camada`, `camada_s`,
  `lado_unico`, `gestos_no_nativo`, `toque_de_confirmacao`, `pulso_da_barra` e `sem_pisca`; o resto cai. Um `para` sem o `ligado: false` de
  volta em 300 ms faz o serviço encerrar a modificação pelo PID (SIGTERM, depois SIGKILL).

`jogo.momento`, `sistema.app_abriu` e `sistema.hora` são nomes reservados: nenhum existe como permissão nem tem
fonte, e uma modificação que peça um deles é recusada como qualquer permissão desconhecida.

As escritas valem para qualquer controle, de P1 a P4, pelo `uniq` dele.

Cada evento chega como notificação, sem `id`:

```json
{"jsonrpc": "2.0", "method": "evento",
 "params": {"topico": "estado", "nome": "state.update", "uniq": "<uniq>", "dados": {}}}
```

O serviço guarda até 256 eventos por assinatura. Quando a fila enche, o mais antigo sai: quem lê devagar
perde eventos velhos, e o tique do serviço nunca espera.

## Uma extensão publica para as outras

O `eventos.publicar` `{topico, dados}` passa um evento de uma extensão a todas as que têm `ler:<tópico>`, pela
mesma fila de 256 por assinatura. Só vale para a lista fechada de tópicos publicáveis, que hoje é um,
`jogo.acessorio`, e pede `publicar:jogo.acessorio` no manifesto (a frase aparece no ⋮ da linha antes do «sim»). Em
`dados` vai só `funcoes`; o serviço monta o envelope com `origem` e `t`. As recusas:

- sem a permissão: `-32010`;
- tópico fora da lista, `dados.funcoes` ausente, vazio ou que não seja objeto, nome de função fora da
  regra, mais de 16 funções da mesma extensão ou valor fora de 0 a 1: `-32003`, com a frase;
- mais de 20 publicações aceitas por segundo da mesma extensão: `-32003`; a janela é de 1 s, e a recusada não
  conta.

## A vibração de um controle

A extensão que acompanha o jogo lê `jogo.vibracao` (a vibração de cada controle, acima) e a que faz um controle
vibrar pede `vibracao.set {uniq, fraco, forte}`: o serviço aplica pelo `rumble.set`, com o teto e a força de
cada controle, e o jogo tem a vez. Os dois nomes não dizem que aparelho está do outro lado. Quando a conexão
cai (parada, morta ou desligada), cada controle que o último `vibracao.set` da extensão deixou acima de zero recebe
`fraco: 0, forte: 0`, menos aquele em que o jogo está vibrando: nenhum motor fica preso.

Quem faz CADA controle vibrar (não só o do posto) pede `controles.lista`: os controles ligados agora, cada um
uma vez, com o `jogador` que ele acende (ou `null`). Sem a lista do serviço, vale o controle do posto; a lista
que falha volta vazia. O método entrou na versão 2 da porta sem mudar a faixa: quem pede `>=2,<3` e não o usa
não muda nada. O servidor Buttplug do próprio DualSense mora na extensão `intiface`
(`https://github.com/Hefesto-Team/hefesto-mod-intiface`), que usa este método e o `vibracao.set`.

## A extensão de lançador

A extensão de tipo `lancador` e `processo`, com a permissão `lancador`, entrega os jogos que conhece
por `lancador.jogos`. A lista inteira substitui a anterior, até 5000 jogos:

- `chave`: a identidade do jogo na extensão (até 120 letras, sem repetir na lista);
- `nome`: o que a tela mostra (até 120 letras);
- `abrir`: o comando que abre o jogo, de 1 a 64 termos. O primeiro é um dos `lancador.comandos` do manifesto;
  outro qualquer é recusado com `-32010`, e o manifesto sem `lancador.comandos` não entrega jogo;
- `janela`: o app-id da janela do jogo, quando a extensão sabe (vazio, se não).

A forma errada volta `-32003`, com a frase. A interface lê a lista pelo IPC do serviço (o `ipc.sock`):
`mods.jogos {mod}` devolve `{mod, jogos}`, a última lista que aquela extensão entregou, e a lista vazia sem
conexão viva da extensão. O leitor da biblioteca do lançador mora na extensão, nunca no serviço.

A aba 07 pede o `mods.jogos` de cada extensão de lançador ligada e sem leitor, e a extensão vira uma linha
da lista, ao lado da Steam e do Heroic, com a contagem dos instalados («2 jogos»). Desligada ou
desinstalada, a linha some.

### O leitor no manifesto

A extensão só de `lancador` (sem `processo`) declara o leitor no `lancador.leitor`, e a interface o roda
numa caixa só de leitura, sem rede (`bwrap`), quando a biblioteca muda:

- `executar`: o comando, a partir da pasta da extensão (`["python3", "-I", "leitor.py"]`);
- `prazo_s`: o prazo da leitura, em segundos;
- `fontes`: os arquivos que o leitor lê, relativos à `HOME` (o `*` vale no último pedaço). A mudança de
  um deles é o que faz a leitura sair de novo.

O leitor imprime uma lista JSON, um objeto por jogo: `chave` e `nome` são exigidos; `caminho`,
`titulo_do_jogo` (que casa o `lancador.titulo_do_jogo` do manifesto), `janela` (o app-id da janela do
jogo), `proton` (a versão do Proton do jogo, que conta no «Proton que sobra») e `instalado` (verdadeiro
quando falta) são opcionais. A linha torta sai sozinha, e as outras ficam.

Os lançadores que eram de fábrica e saíram em 19/10/2026 (o Lutris, o RetroArch, o Dolphin e o mGBA)
estão em `mods/viraram_extensao.json`, com o endereço do repositório de cada um; o Azahar e o KytyPS5
nascem como extensão. Quem tem a
pasta de um deles no disco e não tem a extensão lê na 07 uma linha que diz que ele virou extensão, com o
endereço; nada se instala sozinho.

## O aviso do manifesto

O campo `aviso` (até 400 letras, opcional) é o aviso de uso da extensão: a marca que não a endossa, o jogo
comprado, a idade. A linha de comando o imprime antes de gravar e pergunta (`--sim` aceita). Na tela, o
«Instalar» grava a extensão desligada, e o primeiro clique da chave abre o ⋮ com o aviso no topo da lista das
permissões; o segundo liga. O aviso aceito fica no registro (`aviso_aceito`); a versão nova com outro aviso
volta a pedir o «sim» do ligar, e a atualização sozinha a deixa esperando o «Atualizar». O serviço não abre a
extensão cujo aviso ainda não teve o «sim». A função `instalar(…, aviso_visto=…)` recusa com
`AvisoParaVerError` antes de gravar quando o aviso visto é outro.

Cada extensão da casa mora no seu repositório, `Hefesto-Team/hefesto-mod-<nome>`, com o
`hefesto-mod.json` (o `aviso` dentro), o código, os testes (`python3 -m pytest testes`, só a biblioteca
padrão e o `pytest`), o `README.md` com o mesmo aviso, a `LICENSE` MIT de Vitória Maria e André Farias e
o `CHANGELOG.md`. A lista, com o endereço de cada uma, está no [README](../../README.md#extensões).

## A volta dos acessórios no controle

Com o `acessorios.estado` e os gestos, o serviço devolve três coisas ao controle do gesto, sem a modificação
escrever nada:

- um toque de confirmação (`toque_de_confirmacao`, ligado se ausente): `sobe` no motor direito, fino; `desce`
  no esquerdo, grosso; `para`, dois toques longos nos dois; `sobe` com o nível já em 10, toque duplo. No
  máximo 12 por segundo por controle. Soma por 40 ms ao que o jogo pede e nunca o cala: se o jogo vibra, o
  serviço não escreve o zero do fim;
- as luzinhas medidor, por 2 s depois de cada gesto: `ceil(nível / 2)` lâmpadas, no brilho forte e sem o
  esmaecer (`0x20` do byte 43), e depois o número do jogador. Na camada de uma mão ficam no medidor enquanto
  ela vale; `para` as apaga;
- o pulso da barra, só com o perfil marcado «Adulto», `ajustes.pulso_da_barra` ligado e a permissão
  `pedir:luz.pulso`. O `luz.pulso` leva a cor, a `cor_quente` (a cor esquenta com o nível), o `fundo` (a fração
  do brilho no vale, de 0 a 0,5) e o `periodo_s`, que o serviço limita a 1 a 4 s: nunca mais de um ciclo por
  segundo, sempre em curva, no máximo 15 escritas por segundo. Com `ajustes.sem_pisca`, o brilho só acompanha
  o nível (10 % no 1, o brilho do perfil no 10), devagar. A recusa do motor volta como `aplicado: false` e um
  `motivo` (`sem_a_marca_adulto`, `pulso_desligado`, `modo_nativo`, `o_jogo_pinta_a_barra`); a porta recusa
  com o código de «o jogo escreve» quando o jogo pinta a barra e com o de «sem permissão» sem a palavra.
  `{parar: true}` solta. Cada controle tem a sua barra. O pulso e o medidor soltam quando a modificação manda
  `ligado: false` ou a conexão cai.

## A janela da extensão (o que o manifesto declara)

A interface desenha a janela «Configurar» de cada extensão do que o `hefesto-mod.json` declara, sem
código da extensão na tela. Cada `opcoes[]` tem `id`, `rotulo`, `tipo` e, opcionais, `escolhas`, `padrao` e `grupo`.

- **`tipo`**: `escolha` (lista em `escolhas`), `ligado`, `numero`, `cor`, `deslizante` e `jogos`. A `cor` é um
  seletor de cor da interface; o valor é `#rrggbb` em minúsculas, e um `padrao` que não seja `#rrggbb` recusa
  o manifesto. O `deslizante` declara `minimo`, `maximo` e `passo` (`minimo` menor que `maximo`, `passo`
  maior que zero) e o `padrao`, **obrigatório** e dentro da faixa: é a posição inicial; a janela desenha um
  `input[type=range]` com a faixa dele, e o valor guardado cai no degrau do `passo` mais perto. Os `jogos` são
  uma lista de chaves `steam_app_<N>`: a janela desenha uma caixa por jogo que tem perfil no Hefesto, o
  `padrao` é a lista vazia (nenhum jogo marcado) e o valor é a lista das chaves marcadas.
- **`grupo`**: o nome (até 30 letras) da aba interna em que a opção mora. Com dois ou mais grupos a janela
  desenha uma aba por grupo, na ordem em que aparecem; a opção sem grupo vai à primeira aba; com um grupo
  só, não há aba. Ao mudar uma opção a janela reabre na aba da opção.
- **onde ficam os valores**: a tela grava cada opção em `<dados>/<id>/opcoes.json`, um objeto `{id: valor}`, em
  `0600`, depois de validar contra o manifesto. A extensão lê o mesmo arquivo na pasta de dados
  (`HEFESTO_MOD_DADOS`). Valor ausente, ou que o manifesto não aceita mais, vale o `padrao` (sem `padrao`: a
  primeira `escolha`, `false`, `0`, `#ffffff` ou a lista vazia).
- **`agora`**: a lista do que a coluna «Agora» mostra, ao vivo, do `acessorios.estado` da extensão:
  `nivel`, `perfil` e `aparelhos`, sem repetir.
- **`parar_tudo`**: `true` pede o botão «Parar tudo», sempre à vista: ele manda a ela o gesto `para`, e o
  nível e o perfil ficam guardados.

`agora` e `parar_tudo` só valem com `ler:acessorios.gesto` nas permissões, que é o retorno que os dois usam;
sem a permissão o manifesto é recusado. A janela os pede ao serviço por dois métodos do IPC da interface (o
`ipc.sock`, não esta porta):

- `mods.agora {mod}` devolve o último `acessorios.estado` daquela extensão, `{mod, ligado, nivel, perfil,
  aparelhos, ajustes}`. Sem conexão viva da extensão, ou quando a conexão cai, volta o estado vazio (`ligado: false`), e a
  coluna mostra cada pedaço vazio, sem número. A janela pergunta no máximo duas vezes por segundo, fora do tique,
  e desenha só os pedaços do `agora`;
- `mods.parar_tudo {mod}` publica `acessorios.gesto` com `gesto: "para"`, `uniq` e `jogador` nulos e
  `mod: <id>`: só aquela extensão o recebe (as outras com `ler:acessorios.gesto` não), nenhum controle dá o
  toque de confirmação, e o serviço confere o «parar curto» só da extensão. Volta `{parado}`, falso quando ela não
  está conectada. Recusa (`-32003`, com a frase) a extensão que não está instalada ou cujo manifesto não declara
  `parar_tudo`.

## Os erros

Além dos códigos do IPC principal (`-32700`, `-32600`, `-32601`, e `-32003` para parâmetro inválido), a porta tem quatro próprios:

| código | quando |
| --- | --- |
| `-32010` | falta a permissão (a mensagem nomeia: «falta a permissão ler:botoes») |
| `-32011` | o jogo está escrevendo aquele canal daquele controle |
| `-32012` | quem é você: ficha desconhecida, processo estranho ou primeira palavra errada |
| `-32013` | o serviço não conseguiu aplicar a escrita |

Toda escrita sem `uniq` é recusada com `-32003`, porque escrever em todos é proibido. Em toda escrita,
o jogo tem a vez: se ele está escrevendo a luz, o gatilho ou a vibração daquele controle, a modificação
espera.

## Nota de verificação (20/10/2026)

`perfil.jogo` é uma permissão de leitura da porta (`ler:perfil.jogo`), não um método do IPC: o espaço de nomes `perfil.` ganhou métodos de IPC (`perfil.ativacao.set` e os dois irmãos), e o nome da permissão continua certo.
