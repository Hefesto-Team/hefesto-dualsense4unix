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

Os tópicos de leitura são estes, todos do controle do posto (o barramento da versão 1 só publica ele):

- `estado`: o estado do controle a cada tique;
- `botoes`: um botão apertado ou solto;
- `bateria`: a carga;
- `conexao`: o controle que entra ou sai.

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
