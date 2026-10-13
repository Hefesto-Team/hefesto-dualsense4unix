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

Os tópicos de leitura são estes. Os quatro primeiros são do controle do posto:

- `estado`: o estado do controle a cada tique;
- `botoes`: um botão apertado ou solto;
- `bateria`: a carga;
- `conexao`: o controle que entra ou sai.

Os dois últimos são do jogo e do perfil, e cada um é uma permissão à parte:

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
  troca do perfil efetivo. É estado, não evento: o serviço guarda o último, e quem assina depois recebe o
  de agora logo na assinatura. As marcas são as do arquivo do perfil (`[]` sem marca), e o envelope leva o
  `uniq` do posto.

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
