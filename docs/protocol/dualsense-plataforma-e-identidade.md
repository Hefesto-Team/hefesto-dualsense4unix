# DualSense — plataforma e identidade: probe, clone, pareamento

O que terceiros mapearam sobre **subir o controle** e **saber quem ele é**,
levantado em 03/09/2026 numa leva que não tocou o aparelho.

> Ela pediu isto com todas as letras: *"lançar novo workflow pra agentes
> procurarem no Github tais canais ou tais id (…) peneiraram em vários repo e
> acharam pessoas que nem a gnt que tinham mapeado parte do quebra cabeça e
> **como é só informação eles trouxeram**"*.

**Grau de tudo o que está aqui: `afirmado-no-doc` ou leitura de fonte.** Nenhum
byte saiu para o aparelho nesta leva — os dois controles estavam na mesa dela.
O que foi lido da máquina foi o `report_descriptor` no sysfs, que o kernel
guarda desde a probe: ler o arquivo não gera tráfego.

As células correspondentes estão em `docs/data/mapa-controles.csv`, nas seis
linhas `plataforma.probe`, `plataforma.probe.retry`, `plataforma.inventario`,
`plataforma.distinguir_clone`, `identidade.pareamento` e
`identidade.req_dev_info.fallback` — todas do controle `dualsense`. **O mapa é o
hub; este arquivo é o rodapé de fonte.**

---

## 1. O censo de feature reports, por transporte

Lido do `report_descriptor` que o kernel guarda para os dois controles da mesa
dela, em 03/09/2026. Bate report a report com a tabela da Game Controller
Collective e com o dump de descritor do `nondebug/dualsense`.

| | quantos | quais |
| --- | --- | --- |
| **cabo** | 22 | `0x05 0x08 0x09 0x0A 0x0B 0x0C 0x20 0x21 0x22 0x80 0x81 0x82 0x83 0x84 0x85 0xA0 0xE0 0xF0 0xF1 0xF2 0xF4 0xF5` |
| **rádio** | 17 | `0x05 0x08 0x09 0x0B 0x20 0x22 0x80 0x81 0x82 0x83 0xF0 0xF1 0xF2 0xF4 0xF5 0xF6 0xF7` |

**As três diferenças que importam:**

1. **`0x0A` só existe por cabo.** É o «Set Bluetooth Pairing» — ver §3.
2. **`0x03` não existe em nenhum dos dois.** É o que o SDL pergunta a um pad de
   terceiro; ver §4.
3. O firmware do aparelho dela declara `0x0B`/`0x0C` (cabo) e `0x0B`/`0xF6`/`0xF7`
   (rádio) que **nenhuma das duas fontes de terceiro traz**. Diferença de
   firmware, não de fonte.

Nomes que as fontes dão aos que este projeto usa ou pode usar:

| report | tam. | o que é |
| --- | --- | --- |
| `0x05` | 41 B | calibração (a probe do driver lê) |
| `0x08` | 47 B | «Set Bluetooth Control» — buf[1] = 1 liga, 2 desliga |
| `0x09` | 20 B | **«Get Controller and Host MAC»** — dois endereços, não um |
| `0x0A` | 27 B | **«Set Bluetooth Pairing»** — host + link key. Só por cabo |
| `0x20` | 64 B | firmware info: data de build, versões, `update_version` |
| `0x22` | 64 B | «Get Hardware Info» — **nunca lido por linha nenhuma desta casa** |
| `0x80`/`0x81` | 64 B | «Set test command» / «Get test result» — é por aqui que este projeto lê serial e cor |
| `0xE0` | 64 B | «Get system profile» — só por cabo |
| `0xF0`…`0xF5` | — | comando de flash e atualização de firmware. **Não mexer.** |

---

## 2. A probe é uma conversa de três reports

A **nossa** probe não tem report: é `hidapi.enumerate` por VID/PID. A do
**driver** tem, e são três, nesta ordem:

```
0x09 PAIRING_INFO (20 B) → 0x20 FIRMWARE_INFO (64 B) → 0x05 CALIBRATION (41 B)
```

Qualquer um que falhe **aborta a probe inteira** — sem input, sem LED, sem
bateria (`assets/dkms/hid-playstation/hid-playstation.c`, `dualsense_init`). O
driver ainda exige que a resposta ecoe o report ID e tenha o tamanho exato, e
**por rádio** que o CRC-32 dos quatro últimos bytes bata com a semente `0xA3`.

Offsets que a probe usa, confirmados por duas leituras independentes (o driver
desta máquina e o `SDL_hidapi_ps5.c`):

- `0x09`: `buf[1..6]` = endereço do próprio controle, little-endian.
- `0x20`: `buf[24..27]` hardware, `buf[28..31]` firmware, `buf[44..45]`
  `update_version` — o SDL monta o mesmo LE16 com `data[44] | data[45] << 8`.

### O efeito colateral que só existe por rádio

O SDL escreve duas vezes, na cara, que ler `0x09` ou `0x20` por Bluetooth
**liga os reports completos**: «This will also enable enhanced reports over
Bluetooth». Por rádio o DualSense começa mandando o report de entrada `0x01`
reduzido e só troca para o `0x31` (77 B, com IMU, touchpad e CRC) depois de um
feature report.

**Isso contradiz o driver**, que afirma o contrário para justificar o retry:
*«Reading a feature report is a pure read with no side effects»*. As duas se
acomodam se o efeito for de PRIMEIRA leitura e idempotente depois — mas **ninguém
mediu isso aqui**, e até que se meça, «sem efeito colateral» é afirmação mais
forte do que a fonte sustenta.

Consequência prática: por rádio, `feature_retries` não está comprando um
endereço. Está comprando o `0x31`.

---

## 3. Pareamento: o controle guarda o endereço do host, e ninguém pergunta

**Este é o achado que mais rende.** O `0x09` traz **dois** endereços:

```
buf[0]      0x09
buf[1..6]   endereço do PRÓPRIO controle   (little-endian)
buf[7..9]   0x08, 0x25, 0x00               (três constantes)
buf[10..15] endereço do HOST pareado       (little-endian)   ← ninguém lê
buf[16..18] enchimento
```

E o `0x0A` **escreve** o outro lado do bond, só por cabo:

```
buf[0]      0x0A
buf[1..6]   endereço do HOST               (little-endian)
buf[7..22]  link key, 16 bytes             (mesma ordem de bytes do bluez)
```

Três fontes independentes concordam no layout: a Game Controller Collective
publica as duas estruturas com nome de campo; um firmware ESP32-S3 que se faz
passar por DualSense monta a resposta do `0x09` exatamente assim, cauda
`0x08 0x25 0x00` inclusive; e o `hid-playstation` confirma a primeira metade
(`memcpy(mac_address, &buf[1], 6)`) e **conhece a segunda e a ignora de
propósito** — o comentário do caminho do DualShock4, nesta mesma cópia, diz
*«the bytes that follow are the address of the host the controller was last
paired to, which is never read»*.

**O que isso abre.** O bond tem dois lados e esta casa só guarda um:
`scripts/bt_bonds_snapshot.sh` copia o `LinkKey` do BlueZ,
`scripts/bt_bonds_restore.sh` devolve — sempre à mão, sempre com `sudo`. O
`0x0A` escreve **esse mesmo valor** no controle, e a fonte diz explicitamente
que a ordem de bytes é a que o bluez usa nos arquivos `info`.

**O passo barato é o `0x09`, não o `0x0A`**: perguntar ao controle a que host
ele acha que está pareado e comparar com o que o BlueZ acha é leitura pura — o
driver já a faz em toda probe. O `0x0A` é escrita, e mal formado reescreve o
pareamento de um controle que ela está usando.

**E ele explica por que a volta sempre foi do lado do BlueZ:** a única porta
para escrever o par host+chave no controle é o `0x0A`, que não existe por
rádio. Restaurar o bond do lado do CONTROLE por rádio é impossível por
construção.

---

## 4. Distinguir o genuíno do clone

Hoje o produto olha VID/PID e mais nada — um clone que declare `054C:0CE6`
passa. O que a busca acrescentou, do mais barato ao mais conclusivo:

**a) O gabarito do clone, medido num clone vivo.** O firmware ESP32-S3 declara
tamanho para os 20 feature reports do descritor genuíno — para o descritor
casar — mas **só responde três**: `0x05`, `0x09` e `0x20`. Todo o resto devolve
`false`. E três é exatamente o que o `hid-playstation` pede na probe.

> **A regra que isso deixa: a porta aberta é qualquer feature FORA da trinca da
> probe.**

**b) O discriminador que este produto já tem na mão.** Ele manda `0x80`/`0x81`
nos dois transportes para ler a cor, e já valida a resposta — eco `1`/`19`/`2`
em `buf[1..3]` e 17 caracteres ASCII em `buf[4..20]`, cujos caracteres 5 e 6
são um código de cor conhecido. O clone medido não passa nisso. **Usar o
resultado que já está na mão como sinal de autenticidade não custa um byte novo
no fio.**

Isso **não** é anti-clone forte: um clone que copie o `0x81` passa.

**c) O precedente do DualShock4, da LKML.** *«There are clones of DualShock 4
that are very similar to the originals, except of 1) they do not support HID
feature report 0x81»* — e o `0x81` do DS4 é o get-MAC por USB, o papel que no
DualSense é do `0x09`. Na mesma discussão, um segundo relato separa os dois
pelo **errno**: genuíno devolve `-ETIMEDOUT`, clone devolve `-EPIPE`. **Não
conferido para o DualSense — é pista, não fato.**

**d) O `0x03`, e o cuidado que não se pode perder.** O SDL aceita um pad PS5 de
terceiro **licenciado** quando o feature `0x03` volta com **exatamente 48
bytes** e `data[2] == 0x28` (dentro: `data[4]` e `data[20]` bitmaps de
capacidade, `data[5]` o tipo, `data[24]` as específicas). O `0x03` **não está
em nenhum descritor genuíno** — três fontes, nenhuma com ele.

Mas o SDL só pergunta o `0x03` quando o VID **não** é Sony. Logo *«responde
`0x03` ⇒ não é genuíno»* é **inferência nossa**, não algo que o SDL afirme. É a
inversão que ainda espera medição, e a medição é barata: num aparelho genuíno o
`0x03` tem de voltar vazio.

**e) O que um clone não copia, e nós também não conferimos.** A Game Controller
Collective descreve um campo `AesCmac` de 8 bytes no fim do bloco de estado
(offset 55). Conferir um CMAC sem a chave da Sony não é possível.

**f) O grupo `0xF0`/`0xF1`/`0xF2`: DUAS FONTES SE CONTRADIZEM, e nenhuma fecha.**
Vale escrever porque é a diferença entre «há desafio-resposta neste aparelho» e
«não há», e alguém vai reencontrar as duas leituras:

- **No DualShock 4 esse trio É a autenticação**, e isso é bem documentado: o
  host escreve o nonce em vários `SET 0xF0`, consulta `GET 0xF2` até o aparelho
  dizer que está pronto, e recolhe a assinatura RSA-PSS em vários `GET 0xF1`.
- **Para o DualSense, a Game Controller Collective chama `0xF0` de «Flash
  command» e `0xF1` de «Get flash cmd status»** — mas marca os dois com *«please
  document»* e deixa a nota do `0xF2` **em branco**. A própria fonte declara que
  não sabe.
- **A favor da leitura de autenticação:** os três tamanhos do DualSense são
  IDÊNTICOS aos do DS4 (64 / 64 / 16 bytes com o ID), e uma investigação pública
  de emulação de DualSense relata comportamento «com um jeitão de DS4, embora
  diferente», com um código de status que muda conforme quantos pacotes de nonce
  foram enviados.
- **Contra:** essa mesma investigação **não conseguiu fazer funcionar** o script
  de DS4 no DualSense e termina em aberto; e `0xF4`/`0xF5` são atualização de
  firmware com boa sustentação — o que dá plausibilidade à família «flash».

> **Conclusão honesta: para o DualSense o grupo `0xF0`–`0xF2` NÃO está
> resolvido.** Quem escrever «o DualSense tem desafio-resposta RSA pelos
> `0xF0`/`0xF1`/`0xF2`» está afirmando mais do que qualquer fonte encontrada
> sustenta. E de todo modo isso não vira anti-clone aqui: **verificar a resposta
> exige a chave pública da cadeia da Sony**, que não é nossa.

**Por rádio há uma barra a mais, e é de graça:** o aparelho assina cada resposta
de feature (CRC-32, semente `0xA3`) e cada report de entrada (semente `0xA1`), e
o driver já reprova quem erra. Não é criptografia — CRC-32 com semente conhecida
é copiável por quem ler esta mesma tabela — mas quem passou pela probe por rádio
acertou dois CRC-32.

---

## 5. Identidade quando o pedido não responde: não há saída

**A busca fecha a porta, em vez de abrir.** Não existe identidade sem report
para o DualSense: o `uniq` do sysfs, o `serial_number` do hidapi e a chave que o
produto usa saem todos, no fim, do mesmo `0x09` — o driver escreve `hdev->uniq`
a partir dele, e a pilha inteira lê `uniq`.

E quando o `0x09` falha, **o driver não degrada**: devolve o erro e a probe morre
inteira. Compare com o DualShock4 no mesmo fork, que tem duas saídas declaradas
(`ds4_short_pairing_info` e `ds4_synthetic_mac`).

O `dualsensectl` percorre o mesmo caminho e mostra o que sobra: exige 17
caracteres e, se não vierem, escreve `00:00:00:00:00:00` — **um endereço falso
com cara de endereço**. A chave volátil `path:<path>` deste produto é menos
enganosa que isso, e essa é a defesa dela: não se parece com identidade nenhuma.

---

## 6. O que a internet NÃO sabe

A lista do que não se achou é informação: ela diz onde só o aparelho responde.

- **O conteúdo dos `0x80`/`0x81` além do serial.** As duas tabelas de terceiro
  dizem literalmente *«please document»*. Esta casa sabe mais desse par do que
  as fontes públicas consultadas — o eco `1`/`19`/`2` e a fatia da cor foram
  medidos aqui.
- **O `0x22` («Get Hardware Info»), o `0xE0` («Get system profile»), o `0x82`/
  `0x85` («individual data») e o `0x84`.** Nomeados, nunca decodificados por
  ninguém que se tenha achado.
- **O `0x0B`, o `0x0C`, o `0xF6` e o `0xF7`**, que o firmware do aparelho dela
  declara e nenhuma fonte pública menciona.
- **Se o `0x03` volta vazio num DualSense genuíno.** É uma leitura, é barata, e
  fecharia o discriminador da §4d.
- **Se o efeito «ligar reports completos» do `0x09`/`0x20` por rádio é só da
  primeira leitura.** É o que decide se o comentário do driver está certo.
- **Se o DualSense repete o errno do DS4** (`-ETIMEDOUT` genuíno,
  `-EPIPE` clone) num feature report que ele não implementa.
- **O que o grupo `0xF0`–`0xF2` faz no DualSense.** Duas leituras públicas
  incompatíveis (§4f), e **nenhuma das duas fechou**. É a maior lacuna deste
  levantamento.
- **Se o `0x09` lido do controle bate com o host que o BlueZ registra.** A
  comparação é leitura pura dos dois lados e ninguém a fez.

---

## Fontes

Todas fixadas por commit ou revisão — os números de linha só valem nelas.

| fonte | o que sustenta |
| --- | --- |
| `libsdl-org/SDL@f443c429` `src/joystick/hidapi/SDL_hidapi_ps5.c` | o `0x03` e o teste 48 B / `data[2]==0x28`; o `0x09` lido ao contrário; o `update_version` em `data[44..45]`; os dois comentários sobre reports completos por Bluetooth |
| `LeonChrome/XinHeLianSheng-Pro2-Bridge@05882f01` `firmware/esp32s3_dualsense_identity_experiment/main/dualsense_report.c` | o clone vivo: declara 20 features, responde três; e a cauda `0x08 0x25 0x00` do `0x09` |
| `nowrep/dualsensectl@d3ae2fa2` `main.c` | o layout completo do `0x20`; as três sementes de CRC-32; o `00:00:00:00:00:00` de recurso |
| `nondebug/dualsense@b87450eb` `report-descriptor-usb.txt` | o censo de features por cabo |
| Game Controller Collective Wiki, `controllers.fandom.com` — «Sony DualSense/Report Summaries» (rev. 595) e «/Data Structures» (rev. 602) | as tabelas por transporte; `ReportFeatureInMacAll` e `ReportFeatureOutBluetoothPairing`; os nomes dos reports; o campo `AesCmac` |
| LKML, «HID: sony: Support for DS4 clones that do not implement feature report 0x81» e «drivers: hid: warn feature report 0x81» | o precedente de clone do DS4 e a diferença de errno |
| `assets/dkms/hid-playstation/hid-playstation.c` (cópia DKMS desta árvore) | os `#define`, a ordem da probe, as sementes, o comentário sobre o endereço do host |

A régua que amarra isto ao mapa é
`tests/unit/test_plataforma_e_identidade_do_dualsense_no_mapa.py`: ela extrai os
`#define` do driver e cobra que o mapa diga o mesmo, e guarda os dois censos de
feature report para que uma lista copiada errada apareça em vermelho.

Antes de acreditar em qualquer linha daqui contra o aparelho, confira em
`docs/protocol/dualsense-referencia-canonica.md` e em
`docs/protocol/driver-hid-playstation.md`.
