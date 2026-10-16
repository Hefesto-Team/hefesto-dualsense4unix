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

Os tópicos de leitura são estes. Os quatro primeiros são do controle do posto:

- `estado`: o estado do controle a cada tique;
- `botoes`: um botão apertado ou solto;
- `bateria`: a carga;
- `conexao`: o controle que entra ou sai.

Os demais são do jogo e do perfil, e cada um é uma permissão à parte:

- `jogo.vibracao` (`ler:jogo.vibracao`) entrega duas notificações. `nome: "jogo.vibracao"` é a vibração que o
  jogo pede a UM controle, de qualquer jogador (P1 a P4), com o `uniq` dele no envelope:
  `{uniq, jogador, pedido: [fraco, forte], efetivo: [fraco, forte], t}`. `pedido` é o que o jogo mandou;
  `efetivo` é o que chegou aos motores (`[0, 0]` quando o par fixado pela tela vence ou a escrita foi
  recusada), e a batida segue o `efetivo`. `jogador` é o número que o controle acende agora (ou `null`); `t` é
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
  botão cru. Só existe com a modificação ligada e com aparelho: ela devolve o estado dela por
  `acessorios.estado`, o Hefesto guarda o último e, sem ele (ou sem aparelho, ou quando a conexão cai), PS + R2 é o
  que sempre foi. Enquanto o gesto vale, o R2, o L2, o R1, o L1 e o direcional que o comandam não chegam ao
  jogo, por controle. `ajustes` aceita `limiar_fundo` (50 a 100 %), `acelerador`, `camada`, `camada_s`,
  `lado_unico`, `gestos_no_nativo` e `toque_de_confirmacao`; o resto cai. Um `para` sem o `ligado: false` de
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
