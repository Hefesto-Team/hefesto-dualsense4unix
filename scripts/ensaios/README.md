# Os instrumentos do ensaio 2+2

**Dois controles no cabo e dois no rádio, ao mesmo tempo.** Não é capricho de
arrumação: é o desenho que torna a medição possível.

Com a mesa 2+2, o **mesmo instrumento, no mesmo minuto, na mesma máquina** mede
os dois transportes. Toda diferença que aparecer na tabela é do **transporte** —
não do dia, não da versão do kernel, não do humor do BlueZ naquela tarde. É o
único jeito de separar *"o aparelho não faz"* de *"o transporte não leva"*, e
essa distinção é a diferença entre uma decisão de produto certa e uma errada.

Medir cabo hoje e rádio amanhã não responde nada: qualquer diferença encontrada
tem candidatos demais.

---

## Como preparar a mesa

1. **Dois controles no cabo.** USB-C de dados — cabo de só-carga não enumera o
   HID, e o controle simplesmente não aparece.
2. **Dois controles no rádio**, pareados e conectados.
3. **Confirme que a mesa é a que você pensa** antes de medir qualquer coisa:

   ```bash
   .venv/bin/python scripts/ensaios/quem_e_quem.py
   ```

   A coluna `transporte` tem de mostrar **dois `cabo` e dois `rádio`**. Todo
   instrumento desta pasta imprime essa contagem no começo e **diz na cara**
   quando só há um transporte presente — porque uma tabela "cabo x rádio" com
   um transporte só não compara nada, e já enganou gente.

### O que confere sozinho, e o que não

O transporte sai do **barramento** no `HID_ID` do `uevent`: `0005` é Bluetooth,
`0003` é USB. **Topologia de sysfs não serve** — com BlueZ ≥ 5.73 os controles
de rádio moram sob `/devices/virtual/misc/uhid/`, no mesmo lugar do vpad do
próprio produto. Essa armadilha custou uma sessão em 11/08/2026.

---

## Os quatro instrumentos

### `quem_e_quem.py` — comece por aqui

**Pergunta:** qual controle físico é qual jogador?

Resolve por sysfs: MAC ↔ hidraw ↔ evdev ↔ placa ALSA ↔ bateria ↔ vpad. E lê o
**desenho do player LED direto do sysfs** (`leds/…:white:player-N/brightness`),
decodificando o padrão aceso para número de jogador:

```
00100 = P1     01010 = P2     10101 = P3     11011 = P4
```

Isso transforma *"olhar o controle e contar as luzinhas"* numa **medição** — e
é assim que ele enxerga sozinho a divergência entre o número que o daemon diz e
o desenho que ele de fato escreve.

**O que ele NÃO resolve, e diz isso em voz alta:** a ligação **vpad ↔ MAC**.
Nenhum arquivo de `/sys` a carrega, e o `state_full` publica `coop.players` como
um NÚMERO, não como lista. `--apertar` resolve à mão.

**O que muda com a resposta:** se a tabela e o LED discordam, o defeito é do
desenho do LED; se discordam o vpad e o físico, o defeito é do roteamento —
são curas diferentes, em lugares diferentes.

### `censo_features.py`

**Pergunta:** cada feature report é o mesmo byte a byte no cabo e no rádio?

Lê os feature reports de cada controle e imprime, por report: quantas tentativas
precisou, se o CRC-32 confere, e se o valor **difere entre cabo e rádio**. Os
tamanhos saem do próprio `report_descriptor` do aparelho, nunca de chute.

> **Não existe "a lista dos feature reports do DualSense".** Existe **uma por
> transporte**, e nenhuma é subconjunto da outra — medido em 15/08/2026, com o
> mesmo controle: **17 por rádio, 22 no cabo**. Só o rádio declara `0xf6`
> (547 B) e `0xf7`; só o cabo declara `0x0a`, `0x0c`, `0x21`, `0x84`, `0x85`,
> `0xa0`, `0xe0`. Até um id comum muda de tamanho: `0xf5` são 8 B no rádio e
> 4 B no cabo.
>
> A primeira versão deste instrumento tirava a lista do **primeiro** aparelho e
> a aplicava a todos — e assim nunca pedia os reports exclusivos do outro
> transporte. O erro **só aparece com os dois transportes na mesa ao mesmo
> tempo**, que é exatamente o que o ensaio 2+2 existe para pegar. Hoje ele usa a
> união dos descritores e imprime quem declara o quê antes de ler qualquer coisa.

Ele carrega quatro coisas que custaram caro:

- **Por rádio o `GET_FEATURE` falha por TIMEOUT, não por erro.** O pedido sai
  pelo canal de controle L2CAP e bate no `REPORT_REQ_TIMEOUT` de 3 s do BlueZ;
  cada falha custa ~3,2–3,7 s, e essa é a assinatura. **A cura é repetir** —
  em 15/08/2026, dois controles responderam de primeira e um precisou de 5.
- **Nem toda falha merece retry.** Um report que o descritor declara mas o
  firmware não implementa devolve `EPIPE` (stall) na hora, sempre. Isso é
  resposta **definitiva** do aparelho, categoria diferente do timeout, e
  repeti-la seis vezes só faz o censo demorar seis vezes mais. E se as falhas
  voltam em ~0,01 s, o controle **desconectou no meio do ensaio** (`ENODEV`) —
  o instrumento avisa alto, porque isso não é recusa do aparelho: o aparelho
  não está mais lá.
- **O aparelho pode devolver o report errado.** Um respondeu `0x80` a um pedido
  de `0x20` — resposta trocada, não erro, com o ioctl retornando sucesso. Por
  isso `buf[0] == report_id` é validado sempre.
- **A cor de fábrica não sai daqui.** Ela exige um `SET_FEATURE 0x80` antes, que
  é **escrita**. `--mostrar-comando-da-cor` imprime o comando exato e para.

**O CRC-32 de semente `0xA3` é o enquadramento do Bluetooth**, e só é conferido
no rádio: no cabo os quatro últimos bytes são payload como outro qualquer, e
checá-los ali produzia "difere" em *todos* os reports — alarme convincente e
inteiramente falso. Trailer zerado também não é CRC quebrado: é report que não
carrega CRC, e a coluna diz `sem trailer`.

> **Este é o único instrumento que exige o daemon PARADO** — veja a seção
> seguinte, que é o achado mais importante desta pasta.

**O que muda com a resposta:** se um report difere entre transportes, ele é
fonte de identidade dependente de canal e não serve para identificar unidade.
Se é idêntico, serve.

### `taxa_de_entrada.py`

**Pergunta:** o rádio entrega entrada, giro e acelerômetro na mesma taxa que o
cabo?

Mede por evdev — o caminho que os jogos usam — em **três colunas separadas**:
entrada (`SYN_REPORT` do nó principal), giro (`ABS_RX/RY/RZ`) e **acelerômetro**
(`ABS_X/Y/Z`).

O acelerômetro **não aparece em célula medida nenhuma do mapa de canais**. Esta
é a dívida que este instrumento paga: `movimento.giro` estar verde nunca foi
promessa de que o acelerômetro chega.

> **Mexa os controles enquanto ele mede.** Botão parado não gera evento, e zero
> num controle imóvel não é falha de transporte.

**O que muda com a resposta:** se o rádio entrega taxa menor, é decisão de
produto informar isso na interface; se entrega igual, "cabo é melhor para
movimento" sai da documentação.

### `audio_por_transporte.py`

**Pergunta:** o áudio existe no rádio, ou só no cabo?

Inventaria quatro camadas: placas ALSA, sinks/sources do PipeWire, o que o
descritor HID declara de OUTPUT, e os nós `Headset Jack`. Amarra cada placa ao
seu controle pelo **dispositivo USB em comum** (a interface `:1.0` é o áudio, a
`:1.3` é o HID) — com dois controles no cabo, adivinhar por ordem erraria
metade das vezes.

**Ele só INVENTARIA, e a distinção é deliberada.** Ele não conclui que o rádio
não tem áudio: lista o que existe de cada lado e deixa a diferença à vista.
Concluir "não tem" a partir de "não achei" é a **falácia do perfil ausente**, e
"impossível" nesta casa só se declara com prova de impossibilidade.

**O que muda com a resposta:** se o áudio por rádio não tem caminho, alto-falante
e microfone são feature de cabo e a interface tem de dizer isso. Se tem caminho e
só falta implementar, é sprint.

---

## O achado que muda como se lê tudo isto

**Com o daemon rodando, o `censo_features.py` não mede nada — e isso é o produto
funcionando.**

O `hefesto-hidraw-broker` deixa o hidraw de cada controle **físico** em
`0600 root:root` de propósito, para esconder o aparelho do jogo. Um leitor
externo leva `PermissionError`.

O instrumento **não escreve "o controle não respondeu"** — essa seria uma
afirmação sobre o aparelho, e seria falsa. Ele nomeia o broker:

```
sem permissão (modo 0600, root:root) — assinatura do broker do Hefesto
ESCONDENDO o físico
```

Para medir feature report de verdade:

```bash
systemctl --user stop hefesto-dualsense4unix
.venv/bin/python scripts/ensaios/censo_features.py
systemctl --user start hefesto-dualsense4unix
```

**O mesmo vale, por outro mecanismo, para os nós de entrada:** o co-op faz
`EVIOCGRAB` nos evdev **físicos**, e o grab é exclusivo. O `taxa_de_entrada.py`
mostra `MUDO (EVIOCGRAB)` em vez de `0 Hz`, porque a diferença entre as duas
frases é a diferença entre uma medição e uma calúnia contra o aparelho.

Com o daemon vivo, portanto, cada instrumento mede uma coisa legítima **mas
diferente**:

| o que você quer medir | daemon | onde olhar |
|---|---|---|
| o que o **jogo** recebe | rodando | os vpads |
| o que o **aparelho** entrega | parado | os físicos |

---

## As regras que estes instrumentos obedecem

Cada uma nasceu de um defeito real aqui.

1. **Todo instrumento declara de qual ARQUIVO veio cada biblioteca** — não o
   nome, o caminho. O `python3` do sistema e o `.venv/bin/python` deste projeto
   trazem `evdev` diferentes. Medir contra a biblioteca errada produz alarme
   convincente e falso, e já aconteceu três vezes.
2. **Todo instrumento diz se o daemon precisa estar parado, e detecta se está
   rodando.** O `test trigger --raw` desta casa já disputou o hidraw com o
   daemon e imprimiu "aplicado" sem ter aplicado.
3. **Nenhum instrumento escreve no aparelho.** Leitura pura. Onde um ensaio
   exigiria escrita, o script **imprime o comando exato e para**.
4. **Falha barulhenta.** Controle que não responde é nomeado, com o motivo.
   Tabela com buraco silencioso é pior que tabela com a palavra "falhou".
5. **Nada de caminho guardado.** Tudo se resolve do sysfs a cada chamada — em
   15/08/2026, entre duas leituras com segundos de diferença, um controle sumiu
   e outro reapareceu com `eventN` diferente.
6. **Sem dependência nova.** `python3` puro mais o que já existe no venv.

### Uma armadilha que este código já pisou, e que fica registrada

O **vpad não tem transporte**, e chamar o dele de "cabo" falseia a tabela. Ele
forja `BUS_USB` no `UHID_CREATE2` de propósito — é o que o faz passar por
DualSense Edge — então a leitura ingênua do barramento o classifica como cabo.

Na primeira versão do `taxa_de_entrada.py`, a média de giro "do cabo" saiu de
**dois físicos mais dois vpads**. O vpad é a *saída* do produto: ele não fala
com aparelho nenhum. Hoje ele aparece como `vpad (sem transporte)` e fica fora
de toda comparação entre transportes.

A régua que separa vpad de aparelho é reusada de
[`scripts/identidade_do_vpad.py`](../identidade_do_vpad.py), nunca
reimplementada — duas leituras do mesmo dado são duas réguas, e uma delas
envelhece calada.

---

## O que já se sabe, e com que grau de confiança

`medido` é palavra cara: vale só para medição **no aparelho**, com instrumento,
data e quem mediu.

| afirmação | grau | como |
|---|---|---|
| a escada OUTPUT `0x32`–`0x39` (até 547 B) existe **só no rádio**; no cabo o descritor declara só `0x02` (48 B) | **medido** 15/08 | `audio_por_transporte.py`, descritor dos 4 |
| no cabo o controle expõe placa USB Audio `054c:0ce6`; no rádio, nenhuma | **medido** 15/08 | idem |
| cabo e rádio declaram conjuntos **diferentes** de feature report (22 x 17), nenhum subconjunto do outro | **medido** 15/08 | `censo_features.py`, descritor |
| os feature reports são lidos por rádio com retry + validação de id; o CRC-32 confere em todos os que trazem trailer | **medido** 15/08 | `censo_features.py` |
| o rádio entrega movimento a taxa **maior** que o cabo — ~414 Hz contra 250,0 Hz cravados no cabo | **medido** 15/08, janela de 5 s | `taxa_de_entrada.py`, daemon parado |
| reports que o descritor declara e o firmware não implementa devolvem `EPIPE` na hora (10 deles no cabo) | **medido** 15/08 | `censo_features.py` |
| a cor de fábrica está nos caracteres 5–6 do serial, via `SET 0x80` + `GET 0x81` | **caminho identificado, NÃO medido** | fonte de terceiros; exige escrita não autorizada, e por rádio ninguém demonstrou |
| a escada `0x32`–`0x39` carrega áudio | **hipótese viva** | o canal existe; provar exige escrever |
| `hardware_version` distingue os quatro controles | **medido** 15/08, mas **não é a cor** | o byte *Variation* é `0x00` nos quatro; o que varia é a revisão de placa. Dois controles da mesma cor comprados juntos teriam o mesmo valor — é chave de diagnóstico, não fonte de cor |

Nesta pasta, os MACs aparecem **mascarados pela convenção da casa** (octetos 4 e
5 zerados): `14:3a:00:00:eb:ab`.
