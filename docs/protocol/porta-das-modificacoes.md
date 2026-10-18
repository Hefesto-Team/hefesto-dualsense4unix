# A porta das modificações

O contrato entre uma modificação ([ADR-021](../adr/021-modificacoes-por-processo.md)) e o serviço.
Versão da porta: **1** (`API_DAS_MODIFICACOES`, em `src/hefesto_dualsense4unix/mods/__init__.py`).

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
| `acessorios.estado` | `{ligado, nivel (0 a 10), perfil?, aparelhos: [...], ajustes?}` | `ler:acessorios.gesto` | `{recebido}` |
| `luz.pulso` | `{uniq, cor: [r, g, b], cor_quente?, fundo (0 a 1), periodo_s}` ou `{uniq, parar: true}` | `pedir:luz.pulso` | `{aplicado, motivo, periodo_s?}` |

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
- `perfil.marcas` (`ler:perfil.marcas`) entrega `nome: "perfil.trocou"`: `{perfil, marcas: [...], t}`, a cada
  troca do perfil efetivo ou das marcas do arquivo dele (a marca posta no jogo já aberto também vale). É estado, não evento: o serviço guarda o último, e quem assina depois recebe o
  de agora logo na assinatura. As marcas são as do arquivo do perfil (`[]` sem marca), e o envelope leva o
  `uniq` do posto;
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
- `acessorios.gesto` (`ler:acessorios.gesto`) entrega `nome: "acessorios.gesto"`: o gesto do PS que comanda os
  acessórios, `{uniq, jogador, gesto, valor}`. `gesto` é `sobe`, `desce`, `para`, `perfil_seguinte`,
  `perfil_anterior`, `nivel_ao_vivo` (`valor` de 0 a 1), `surto` ou `camada` (`valor` 1 liga, 0 desliga); nunca um
  botão cru. Só existe com a modificação ligada e com aparelho: ela devolve o próprio estado por
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

- **`tipo`**: `escolha` (lista em `escolhas`), `ligado`, `numero` e `cor`. A `cor` é um seletor de cor da
  interface; o valor é `#rrggbb` em minúsculas, e um `padrao` que não seja `#rrggbb` recusa o manifesto.
- **`grupo`**: o nome (até 30 letras) da aba interna em que a opção mora. Com dois ou mais grupos a janela
  desenha uma aba por grupo, na ordem em que aparecem; a opção sem grupo vai à primeira aba; com um grupo
  só, não há aba. Ao mudar uma opção a janela reabre na aba dela.
- **onde ficam os valores**: a tela grava cada opção em `<dados>/<id>/opcoes.json`, um objeto `{id: valor}`, em
  `0600`, depois de validar contra o manifesto. A extensão lê o mesmo arquivo na pasta de dados
  (`HEFESTO_MOD_DADOS`). Valor ausente, ou que o manifesto não aceita mais, vale o `padrao` (sem `padrao`: a
  primeira `escolha`, `false`, `0` ou `#ffffff`).
- **`agora`**: a lista do que a coluna «Agora» mostra, ao vivo, do `acessorios.estado` da extensão:
  `nivel`, `perfil` e `aparelhos`, sem repetir.
- **`parar_tudo`**: `true` pede o botão «Parar tudo», sempre à vista: ele manda a ela o gesto `para`, e o
  nível e o perfil ficam guardados.

`agora` e `parar_tudo` só valem com `ler:acessorios.gesto` nas permissões, que é o retorno que os dois usam;
sem a permissão o manifesto é recusado. A interface ainda não desenha o «Agora» nem o «Parar tudo»: o
manifesto os aceita, e a janela os desenha quando o serviço entregar o estado e receber o gesto pelo IPC.

## Os erros

Além dos códigos do IPC principal (`-32700`, `-32600`, `-32601`, `-32602`), a porta tem quatro próprios:

| código | quando |
| --- | --- |
| `-32010` | falta a permissão (a mensagem nomeia: «falta a permissão ler:botoes») |
| `-32011` | o jogo está escrevendo aquele canal daquele controle |
| `-32012` | quem é você: ficha desconhecida, processo estranho ou primeira palavra errada |
| `-32013` | o serviço não conseguiu aplicar a escrita |

Toda escrita sem `uniq` é recusada com `-32602`, porque escrever em todos é proibido. Em toda escrita,
o jogo tem a vez: se ele está escrevendo a luz, o gatilho ou a vibração daquele controle, a modificação
espera.
