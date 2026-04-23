# Research — Protocolo de atualização de firmware do DualSense em Linux

Sprint de origem: `FEAT-FIRMWARE-UPDATE-PHASE1-01` (fase 1 da spec-mãe `FEAT-FIRMWARE-UPDATE-01`).
Data da pesquisa: 2026-04-23.
Status: **preliminar — requer validação empírica**.

Este documento é uma análise do estado da arte para atualização de firmware do controle Sony DualSense em ambiente Linux. Nenhum código executável é entregue aqui; a fase 2 da spec-mãe depende do desfecho desta análise.

---

## 1. Objetivo e não-objetivo

**Objetivo** — determinar se é tecnicamente viável construir, em Linux, um aplicador de firmware oficial Sony para o DualSense (VID `054c`, PID `0ce6` principal; `0df2` para a variante Edge). Caso viável, produzir documento de desenho que habilite a fase 2 (protótipo CLI).

**Não-objetivo** — não implementamos nem publicamos:

- código que aplica firmware de fato (isso é fase 2);
- blobs de firmware da Sony (usuário baixa do site oficial);
- modificação de firmware (o projeto só aplica imagens assinadas pela Sony);
- análise de vulnerabilidades ou engenharia reversa do conteúdo do blob (escopo limitado a interoperabilidade do protocolo de aplicação).

---

## 2. Motivação concreta

O usuário relatou em 2026-04-22:

> A Sony tem um updater oficial, para Windows, mas não para Linux. Pode investigar se conseguimos fazer o update do firmware do DSX por aqui também? Não precisa ser via Wine, já sei que não rola. Eu e meus amigos só queremos rodar o update deles para fazer esse controle funcionar no Android — eu não tenho PS5, só o controle.

Updates de firmware melhoram compatibilidade com Android, iOS e, em teoria, Switch 2. Usuários Linux sem PS5 e sem Windows ficam excluídos do ecossistema. Existe demanda clara.

---

## 3. Estado da arte — projetos upstream

### 3.1 `dualsensectl` (nowrep/dualsensectl, licença MIT)

CLI Linux maduro para interação com o DualSense: bateria, LED, rumble, player LEDs, triggers. Usa `libhidapi` sobre hidraw. **Não implementa atualização de firmware**. Revisão da issue tracker (preliminar, precisa confirmar) sugere que o tema foi discutido mas engavetado por falta de contribuidores com hardware de sacrifício.

Fonte: `https://github.com/nowrep/dualsensectl`.

### 3.2 `pydualsense` (flok/pydualsense)

Biblioteca Python que serve de backend ao Hefesto. Cobre output/input reports de uso normal (feature reports para RGB, trigger effects, rumble, áudio do fone). **Não expõe API de DFU**. Código não sugere que o autor tenha investigado o tema.

Fonte: `https://github.com/flok/pydualsense`.

### 3.3 `Ryochan7/DS4Windows` (DualShock 4 Windows driver)

Ancestral do DualSense. **DS4 tem protocolo DFU parcialmente documentado** em issues históricas do projeto. Pontos de partida relevantes por analogia:

- feature report específico coloca o controle em modo bootloader;
- chunking sequencial com checksum por bloco;
- timeout de ~2s por chunk antes de abortar.

Não é garantia de que o DualSense use o mesmo esquema, mas é o ponto de partida mais próximo publicamente documentado.

Fonte: `https://github.com/Ryochan7/DS4Windows`.

### 3.4 `hid-playstation` (driver do kernel Linux)

Arquivo `drivers/hid/hid-playstation.c` no kernel mainline. Mapeia reports de uso regular do DualSense (input report 0x01 USB, 0x31 BT; output report 0x02 control). **DFU não aparece** — correto, pois um driver de kernel não deveria expor caminho de flash em operação normal.

Fonte: `https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/hid/hid-playstation.c`.

### 3.5 `controllers.fandom.com — Sony DualSense`

Wiki community com tabela de HID reports documentados. Fonte secundária mas bem-mantida. Reports de uso confirmados; reports privados e feature reports exóticos listados como "unknown" ou "speculation".

Fonte: `https://controllers.fandom.com/wiki/Sony_DualSense`.

### 3.6 `DualSenseUpdater.exe` (Sony, oficial)

Binário Windows distribuído pela Sony em `https://controller.dl.playstation.net/controller/lang/en/DualSenseUpdater.exe`. Cerca de 20 MB. Detecta controle via USB (BT explicitamente bloqueado), consulta CDN Sony pelo blob de firmware, aplica via HID.

**Aviso — não baixar o binário para o repositório.** A URL é a referência canônica pública; análise do tráfego do updater em execução é metodologicamente válida (doutrina de interoperabilidade — ver seção 8).

### 3.7 Linux sem Wine

O usuário já verificou que `wine DualSenseUpdater.exe` não funciona — o updater Sony usa camada `WinUSB`/`HID` específica do Windows que Wine não proxya. Rota viável é reimplementação nativa em Linux via `libhidapi` ou acesso hidraw puro.

---

## 4. Mapa de HID reports relevantes do DualSense

Reports confirmados na literatura pública (fontes: `hid-playstation`, `controllers.fandom.com`, `pydualsense`):

| Report ID | Direção | Tamanho (USB) | Tamanho (BT) | Uso documentado |
|---|---|---|---|---|
| `0x01` | input | 64 B | — | Estado completo (sticks, botões, gatilhos, giroscópio, toque) em USB |
| `0x31` | input | — | 78 B | Estado completo em Bluetooth |
| `0x02` | output | 48 B | — | Controle USB: RGB, rumble, trigger effects, áudio |
| `0x31` | output | — | 78 B | Controle BT: mesmo payload, wrapped em CRC32 |
| `0x03` | feature | varia | varia | Informação do controle (firmware version, hw version, serial) |
| `0x05` | feature | varia | varia | Configuração de áudio/microfone |
| `0x81` | feature | varia | varia | Pareamento Bluetooth |
| `0xA3` | feature | varia | varia | **Privado — candidato forte a DFU** |
| `0x20` | output | — | — | **Não documentado publicamente** — outro candidato a DFU |

**Hipótese de trabalho:** o feature report `0xA3` ou um output report da faixa `0x20–0x30` é usado para transição para modo DFU, tamanho e estrutura a determinar via captura.

---

## 5. Hipóteses de ativação do modo DFU

Três cenários considerados, em ordem de plausibilidade:

### 5.1 Feature report específico

Updater envia `hid_send_feature_report(handle, [0xA3, ...payload])`. Controle responde confirmando transição, possivelmente alterando VID:PID transitoriamente para um pid reservado de bootloader (padrão comum em dispositivos USB com DFU).

Sinais esperados na captura:
- feature report com ID privado (`0x20–0xFF`) imediatamente antes do tráfego de chunks;
- possível `udev` re-enumeração (novo dispositivo aparece).

### 5.2 Combo físico de botões

Sony protege contra trigger acidental. **Improvável** — o updater oficial Windows não pede combo físico; bastaria clicar "Atualizar".

### 5.3 Comando via canal reservado

Sony tem histórico de canais de comunicação privados em controles (o PS5 conversa com o controle por canais que o PC nunca vê em uso normal). Improvável no caso de USB direto.

---

## 6. Metodologia de research reprodutível

### 6.1 Setup

**Host Linux** (Ubuntu 22.04+ ou equivalente) com DualSense plugado via USB-C.

**VM Windows 11** (VirtualBox, licença legítima) com USB passthrough do DualSense configurado. O updater Sony instalado e funcional dentro da VM.

**Ferramentas**:
- `usbmon` (módulo de kernel Linux, habilita captura via `/sys/kernel/debug/usb/usbmon/<bus>u`);
- `wireshark` versão 4.0+ com plugin usbmon carregado;
- `lsusb -v` para mapear bus/endpoints do controle;
- `tshark` para análise offline batch.

### 6.2 Procedimento de captura

```
1. modprobe usbmon
2. lsusb -v | grep -A 3 054c:0ce6    → anotar Bus, Device, Path
3. wireshark → interface "usbmonN" (N do bus)
4. Filtro: usb.src == x.y.z OR usb.dst == x.y.z   (x.y.z do lsusb)
5. VM Windows: abrir updater, clicar "Atualizar"
6. Aguardar conclusão (ou cancelamento — valer as duas)
7. Salvar .pcapng em docs/research/firmware-update/captures/
   (NÃO commitar — pode conter blob de firmware Sony; análise derivada é o que vale)
```

### 6.3 Análise

```
1. Identificar transição para DFU:
   - busca por feature reports não-documentados (report IDs 0xA0+) imediatamente
     antes do volume alto de tráfego;
   - verificar se VID:PID muda (udev re-enumeração durante a captura).
2. Identificar chunking:
   - tamanho de payload consistente (prováveis 56 ou 60 B);
   - campo de ordem (offset ou sequence number);
   - presença de checksum (CRC16, CRC32, MD5 truncado, byte de XOR — testar cada um contra o payload).
3. Identificar conclusão:
   - report de "flash OK";
   - resposta do controle com nova versão de firmware (comparar com report 0x03 antes/depois).
4. Diffar pré-update vs pós-update:
   - feature report 0x03 (info do controle) → campo version muda como?
```

### 6.4 Critério de saída

Dois resultados possíveis, **ambos aceitáveis**:

- **Protocolo claro (≥ 80% confiança)** → documentar em fase 1.5 (`protocol-analysis.md`) e liberar fase 2 (CLI protótipo).
- **Chain of trust com assinatura privada Sony** → fase 1 termina em "inviável no estado atual"; spec-mãe `FEAT-FIRMWARE-UPDATE-01` é fechada honestamente.

Não há fracasso aqui. Aprender que algo é impossível com recursos atuais é entregável válido.

---

## 7. Riscos

### 7.1 Brick de hardware

Probabilidade não-nula durante fase 2 (protótipo CLI). Update interrompido no meio pode deixar o controle em estado inconsistente — inutilizável sem recovery mode que, nos casos conhecidos, não é acessível ao usuário final.

**Mitigações (escopo fase 2)**:
- `--dry-run` que simula tudo menos o chunk final;
- verificação de bateria ≥ 50% antes de proceder;
- `vid:pid == 054c:0ce6` ou `054c:0df2` obrigatório (bail fast se outro);
- timeout de 10s por chunk com retry de 3 tentativas antes de abortar;
- lightbar vermelho intenso durante a aplicação para sinalizar "não tirar o cabo";
- disclaimer em 3 lugares (README do projeto, dialog pré-update, log de runtime).

### 7.2 Chain of trust

Se Sony exige assinatura criptográfica no blob e o updater oficial carrega a chave pública de verificação do controle, tudo bem — o Hefesto só aplica blobs oficiais. Se a Sony exige que o **host** assine cada transação (chave privada embutida no updater Windows), aí é **inviável** sem quebra de DRM — linha que este projeto não cruza.

Análise da fase 1 precisa esclarecer qual modelo a Sony usa.

### 7.3 Responsabilidade civil

Usuário aceita o risco de brick. Disclaimer explícito:

- README do projeto (seção "Firmware update");
- dialog pré-update na GUI (fase 3) com 3 confirmações;
- mensagem no log de runtime do daemon quando um update é iniciado.

---

## 8. Ética e base legal

Engenharia reversa do **protocolo de aplicação** (não do firmware) para interoperabilidade é legal em:

- **Brasil** — Lei 9.279/96 de Propriedade Industrial, art. 77: permite atos necessários à determinação de ideias e princípios subjacentes a elementos do programa. Doutrina de interoperabilidade consolidada.
- **União Europeia** — Directiva 2009/24/EC do Parlamento Europeu, art. 6 (decompilação): reverse engineering para obter informação necessária à interoperabilidade é permitido desde que limitado a partes essenciais.
- **Estados Unidos** — DMCA, 17 USC §1201(f): interoperabilidade de programa independentemente criado é exceção explícita ao bloqueio anti-circunvenção.

O projeto Hefesto:

- **não** redistribui blobs de firmware — usuário baixa diretamente do site oficial Sony;
- **não** modifica firmware — só aplica blobs oficiais assinados pela Sony;
- **não** análisa o conteúdo do firmware — só o protocolo de transferência;
- **assume o risco** — disclaimer em 3 pontos.

---

## 9. Próximos passos

### 9.1 Condições para fase 2 (protótipo CLI)

Todas obrigatórias:

1. Protocolo DFU identificado com ≥ 80% confiança (seção 5 decidida empiricamente).
2. Pelo menos **1 contribuidor** com hardware DualSense de sacrifício disposto a aceitar risco de brick.
3. Chain of trust compreendida — se exige assinatura Sony embedded no updater Windows, projeto encerra aqui.
4. Captura completa reproduzida de forma independente (não depende só do autor inicial).

### 9.2 Condições de encerramento

Se, após fase 1, qualquer uma for verdade:

- Sony usa chain of trust com chave privada que não podemos obter;
- protocolo exige hardware proprietário (cabo especial, chip companheiro, etc.);
- captura não consegue isolar a transição para DFU em 3 tentativas independentes;

a spec-mãe `FEAT-FIRMWARE-UPDATE-01` é **fechada como inviável no estado atual**. O documento de pesquisa permanece como artefato de aprendizado; o projeto Hefesto continua sem suportar update de firmware.

### 9.3 Se fase 2 viabilizar

Spec-filha `FEAT-FIRMWARE-UPDATE-PHASE2-CLI-01` abre, seguindo seção correspondente da spec-mãe.

---

## 10. Referências

Projetos upstream:

- `dualsensectl` — `https://github.com/nowrep/dualsensectl`
- `pydualsense` — `https://github.com/flok/pydualsense`
- `DS4Windows` — `https://github.com/Ryochan7/DS4Windows`
- `hid-playstation` kernel driver — `https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/hid/hid-playstation.c`

Documentação pública:

- Sony DualSense wiki community — `https://controllers.fandom.com/wiki/Sony_DualSense`
- Sony updater Windows — `https://controller.dl.playstation.net/controller/lang/en/DualSenseUpdater.exe`

Ferramentas de captura:

- `usbmon` — documentação do kernel Linux.
- `wireshark` com plugin USB — `https://wireshark.org`.
- `VirtualBox` com passthrough USB — `https://www.virtualbox.org`.

Jurisdição:

- Brasil — Lei 9.279/96, art. 77.
- UE — Directiva 2009/24/EC, art. 6.
- EUA — 17 USC §1201(f).

---

## 11. Honestidade epistêmica

Todas as afirmações marcadas com "preliminar", "hipótese", "improvável", "não confirmado" nesta pesquisa dependem de validação empírica via captura real. O documento é um ponto de partida, não um laudo técnico. Fase 2 ajusta este documento conforme achados de captura.

Se durante a captura for descoberto que algum projeto upstream obscuro (fork de pydualsense, patch pendente no hid-playstation, etc.) já explorou o tema, destacar aqui e considerar contato com mantenedor antes de prosseguir.

---

## Execuções registradas

Esta seção recebe registros cada vez que um humano com hardware físico executar parte da metodologia descrita acima (captura usbmon, comparação de reports, validação de hipóteses). Enquanto estiver vazia, a sprint `FEAT-FIRMWARE-UPDATE-PHASE1-01` permanece em `PROTOCOL_READY` — pesquisa entregue, dívida de execução em aberto (lição L-21-6).

Formato: `| data | quem | etapa | resultado | artefatos |`.

| Data | Quem | Etapa | Resultado | Artefatos (capturas, diffs, etc.) |
|---|---|---|---|---|
| _(nenhum ainda)_ | — | — | — | — |

---

*"A forja não revela o ferreiro. Só a espada."*
