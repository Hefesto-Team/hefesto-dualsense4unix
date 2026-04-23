# Firmware DualSense — survey bibliográfico 2026-04-23

> **Documento em expansão.** Esta é a primeira versão; seções sinalizadas **WIP** serão preenchidas em commits sucessivos desta sessão.
>
> Complementação ao `firmware-update-protocol.md` (PHASE1, 304 linhas, 2026-04-23). Este survey agrega achados de WebSearch/WebFetch obtidos via pesquisa direta na sessão 11e7e66d. Não reescreve o doc PHASE1; acrescenta.
>
> Sprint de destino: FEAT-FIRMWARE-UPDATE-PHASE2-01 (research/BLOCKED-ON-HARDWARE) como material de preparação para captura real quando hardware estiver disponível.

## Sumário executivo

- **Confirmação:** o blob de firmware do DualSense **é criptografado**. Dumps publicados desde 2021 permanecem sem chave pública. Isto muda o escopo de PHASE3: não-objetivo "rodar blob modificado" ganha reforço — nem há como; só aplicar a imagem da Sony.
- **Confirmação:** URL canônica Sony (`controller.dl.playstation.net/controller/lang/en/DualSenseUpdater.exe`) permanece ativa e é o único caminho oficial. Existe também uma variante por app Windows Store (`winget install PlayStation.DualSenseFWUpdater`) — mesmo binário empacotado.
- **Achado novo:** `nondebug/dualsense` (GitHub) publica **report descriptor completo** de 280 bytes, sample de input report 0x01 USB com 64 bytes de payload, tabelas de reports USB e BT. PHASE1 cita o repo superficialmente; este survey detalha.
- **Achado novo:** `Paliverse/DualSense-List-of-Firmwares` — repo de terceiro que **redistribui blobs firmware extraídos do Updater Sony**. Status legal ambíguo. Projeto Hefesto **não** deve referenciar/linkar como método de distribuição; apenas reconhecer existência como fenômeno documental.
- **Achado novo:** precedente DS4 — chave AES-128-CBC pública `9B03D4FB5FEC1A2373462C45E4BC72A6` (IV zerado) decifra firmware DS4. DualSense provavelmente usa esquema similar porém com chave nova (ainda secreta). Sugere que **reverse do bootloader DualSense** deve esperar scene — fora de escopo Hefesto (que não visa derivar custom FW).
- **Achado novo:** CachyOS forum e PCGamingWiki têm threads recentes (2024-2025) sobre atualização em Linux. Todos os métodos publicados dependem de **Wine/Proton/Bottles** para rodar o updater Windows oficial. Nenhum é nativo puro.
- **Achado legal:** 9ª rodada triennial DMCA §1201 (out/2024) renovou exemption de interoperabilidade de dispositivos por mais 3 anos (até out/2027). Base legal para PHASE2/3 permanece sólida.

## 1. Projetos upstream — novos e atualizados em 2024-2026

### 1.1 `nondebug/dualsense` (detalhamento)

- **URL:** https://github.com/nondebug/dualsense
- **Conteúdo documentado:** report descriptor de 280 bytes, report 0x01 input USB/BT com breakdown byte-a-byte, udev rule `99-sony-dualsense.rules`, `dualsense-explorer.html` (ferramenta web de análise).
- **Status DFU:** **não cobre** DFU. Foco em reports de uso normal.
- **Valor para PHASE2:** descriptor canônico permite diff contra estado de bootloader (se DualSense muda descriptor ao entrar em DFU, este é o baseline para comparar).

### 1.2 `Paliverse/DualSense-List-of-Firmwares`

- **URL:** https://github.com/Paliverse/DualSense-List-of-Firmwares
- **Natureza:** repositório que **hospeda blobs de firmware** extraídos do updater Sony, indexados por versão. Versão mais recente citada: 0x0217 (DualSense Edge).
- **Mantenedor:** "Paliverse" — **mesma organização por trás do DualSenseX original** (o app Windows que Hefesto porta para Linux). Fato relevante: sugere acesso privilegiado a firmware histórico.
- **Risco legal:** redistribuição de blob proprietário sem autorização Sony é território cinzento (depende de jurisdição). Hefesto **não linka nem baixa** deste repo — apenas registra sua existência.
- **Valor para PHASE2:** nenhum direto (blob continua cifrado). Poderia servir, em tese, para **diff de metadados entre versões** se algum dia a decriptação for pública.

### 1.3 `nowrep/dualsensectl` (revisão 2026-04)

- **URL:** https://github.com/nowrep/dualsensectl
- **Status DFU:** confirmado que **não implementa** DFU. `main.c` expõe comandos bateria/LED/rumble/lightbar/trigger/player-LEDs/speaker/microphone/volume/haptics/info — nenhum toca área de bootloader.
- **Pendente:** varrer issues do projeto com `gh issue list --search "firmware OR update OR dfu"` para confirmar se o tema foi discutido formalmente. Tarefa para quando WebFetch GitHub issues funcionar.

### 1.4 `dsremap` (ReadTheDocs)

- **URL:** https://dsremap.readthedocs.io/en/latest/reverse.html
- **Escopo:** projeto de reverse engineering do DualShock 4, documentação de metodologia USB capture + análise.
- **Valor para Hefesto:** metodologia aplicável ao DualSense por analogia. **Esta é fonte primária para aprender como DS4 foi engenharia-reversa** — precedente documental.

### 1.5 `passinglink/passinglink`

- **URL:** https://github.com/passinglink/passinglink
- **Natureza:** firmware **open source** para controles game (PS3/PS4/Switch). Relevante porque **implementa** o lado do controle, oferecendo referência de como um firmware Sony-compat é estruturado (do lado open).
- **Valor para PHASE2:** estudar magic bytes, signatures, formato de pacote — se passinglink tiver que fingir ser firmware oficial, tem que replicar estrutura.

### 1.6 `Ohjurot/DualSense-Windows`

- **URL:** https://github.com/Ohjurot/DualSense-Windows
- **Escopo:** API Windows para DualSense. Não cobre DFU mas documenta handshake USB/BT e reports canônicos.

### 1.7 `dualshock-tools/dualshock-tools.github.io`

- **URL:** https://github.com/dualshock-tools/ds4-tools (inclui `ds5-calibration-tool.py`)
- **Achado colateral:** existe tooling Python para **calibração** de DS5. Isto fala com feature reports "privados" (não documentados oficialmente) — modelo mental útil para pensar em que faixa de report IDs pode estar o comando de entrar em DFU.

### 1.8 `AwesomeTornado/PSVR2-controller-explorer`

- **URL:** https://github.com/AwesomeTornado/PSVR2-controller-explorer
- **Relevância:** PSVR2 sense controller compartilha stack Sony PS5. Metodologia de exploration (descritor HID → mapeamento de features) diretamente reutilizável.

## 2. Capturas e análises públicas

### 2.1 PSXHAX — firmware dump 2021

- **URL:** https://www.psxhax.com/threads/ps5-dualsense-controller-firmware-dumped-decryption-by-scene-devs-required.10163/
- **Contexto:** developer usou **Beagle USB 5000 Protocol Analyzer** (~$5k, hardware profissional) para capturar tráfego durante update oficial. Blob extraído está **cifrado** — sem chave publicamente disponível.
- **Valor para PHASE2:** confirma viabilidade técnica da captura via hardware analyzer de alta qualidade; **usbmon de VM pode ser suficiente** para derivar protocolo de aplicação (não conteúdo do blob). Distinção crítica: PHASE2 não precisa decifrar nada — só observar comandos de controle.

### 2.2 Wololo.net (cobertura jornalística)

- **URL:** https://wololo.net/2021/08/31/ps5-dualsense-controller-firmware-dumped-encrypted/
- **Síntese:** reforça PSXHAX. Único fato novo: "all that can be learned from the encrypted dumps are the dates and build numbers of the firmware".
- **Implicação:** mesmo dump cifrado tem metadados legíveis — datas e build numbers ficam no header. PHASE2 pode extrair **versão por hash** sem decifrar conteúdo.

### 2.3 blog.the.al — DualShock4 Reverse Engineering series

- **URLs:** https://blog.the.al/2023/01/02/ds4-reverse-engineering-part-2.html, https://blog.the.al/2023/01/04/ds4-reverse-engineering-part-4.html
- **Autor:** Al (Alessandro Stein).
- **Valor para Hefesto:** série técnica completa sobre DS4. Metodologia de usbmon + Ghidra + análise de firmware aplicável por analogia. **Leitura obrigatória antes de PHASE2 real.**

### 2.4 SensePost — DualSense Reverse Engineering

- **URL:** https://sensepost.com/blog/2020/dualsense-reverse-engineering/
- **Autor:** SensePost (consultoria de segurança).
- **Data:** 2020 (dias após lançamento do console).
- **Valor:** análise early-access. Pode conter hipóteses superadas — validar antes de citar.

### 2.5 DualSense descriptor gist (dogtopus)

- **URL:** https://gist.github.com/dogtopus/894da226d73afb3bdd195df41b3a26aa
- **Conteúdo:** dump do USB HID descriptor DualSense.
- **Uso:** referência cruzada com `nondebug/dualsense/report-descriptor-usb.txt`.

## 3. Estrutura do blob de firmware — estado público

| Elemento | Sabido? | Fonte |
|---|---|---|
| Tamanho típico | **Sim** — ~4-8 MB conforme versão | Updater metadata |
| Cifragem | **Sim — AES suspeito, chave secreta** | PSXHAX dump |
| Header legível | **Sim** — data, build number | Wololo, PSXHAX |
| Assinatura RSA | Hipótese | Inferência a partir de padrão Sony |
| Estrutura de chunks | **Não** — informação interna do bootloader | — |
| Magic bytes iniciais | **Desconhecido publicamente** | — |

**Precedente DS4:** chave AES-128-CBC `9B03D4FB5FEC1A2373462C45E4BC72A6`, IV zerado. Publicada na scene e confirmada. DualSense provavelmente usa **algoritmo similar com chave nova** (não-publicada até 2026-04).

**Implicação para PHASE2:** protocolo de aplicação (ordem de comandos DFU) é observável via usbmon **sem** decifrar o blob. PHASE3 implementa esse protocolo e alimenta o blob exatamente como recebido do usuário.

## 4. VID/PID modos — diferenças entre execução normal e bootloader

| Variante | VID | PID normal | PID bootloader | Confirmado? |
|---|---|---|---|---|
| DualSense | 054C | 0CE6 | **desconhecido** | Precedente DS4 tem PID separado; DualSense não confirmado |
| DualSense Edge | 054C | 0DF2 | desconhecido | Edge lançado 2023; update funciona via mesmo updater |
| PSVR2 Sense | 054C | [variado] | — | Fora de escopo atual |

**Ação para PHASE2 real:** durante captura, rodar `lsusb -v` em 3 snapshots — antes do entrar em DFU, durante DFU, após commit/reboot. Confirmar se PID muda. Se mudar, documentar.

`hid-playstation.c` (kernel) em mainline atual mapeia apenas `054c:0ce6` e `054c:0df2` como normais. **Se bootloader usa PID diferente, kernel não oferece driver — mas DFU raramente precisa de driver HID completo; é acesso hidraw ou libusb cru.**

## 5. Feature reports candidatos a entry de DFU

**Status:** hipótese. Nenhuma fonte pública confirma.

Precedente DS4: feature report **0xA0** colocava DS4 em modo bootloader. Implementação:

```c
uint8_t report[2] = { 0xA0, 0x01 };
hid_send_feature_report(dev, report, sizeof(report));
```

Hipótese para DualSense: report ID similar, talvez mudado. Possíveis candidatos a investigar em PHASE2:
- 0xA0 (herdado de DS4)
- 0xB0, 0xB1, 0xB2 (próximos na sequência não-mapeada pelo kernel)
- Reports > 0xF0 (historicamente Sony usa faixa alta para bootstrap)

Método: após plugar DualSense na VM Win e iniciar Updater, filtrar em Wireshark `usb.transfer_type == 0x02 && usb.src == "host"` — primeiro SET_REPORT com tamanho curto é candidato forte.

## 6. Ferramentas "Linux" que existem hoje (todas via emulação)

### 6.1 Linux Gaming Central — guia oficial

- **URL:** https://linuxgamingcentral.org/posts/how-to-update-dualsense-firmware-on-linux/
- **Método:** Bottles + wine-ge-custom (lutris-GE-Proton) + installer Sony oficial. **Não é nativo** — é Windows-via-Wine.
- **Observação:** artigo confirma que "alguns conseguiram usando Proton Experimental" como alternativa, mas não descreve fluxo nativo.

### 6.2 CodeWeavers CrossOver Compat DB

- **URL:** https://www.codeweavers.com/compatibility/crossover/firmware-updater-for-dualsense-wireless-controller
- **Conteúdo:** avaliação de compatibilidade via CrossOver (wine comercial).

### 6.3 CachyOS forum

- **URL:** https://discuss.cachyos.org/t/dualsense-controller-firmware-update/17892
- **Útil para:** troubleshooting — relatos de erros específicos de wine em distros atuais.

### 6.4 winget PlayStation.DualSenseFWUpdater

- **URL:** https://winget.run/pkg/PlayStation/DualSenseFWUpdater
- **Observação:** mesmo binário do updater oficial Sony empacotado para winget. Referência para verificar se o hash bate com download direto.

### 6.5 PCGamingWiki — DualSense Edge

- **URL:** https://www.pcgamingwiki.com/wiki/Controller:DualSense_Edge
- **Nota:** confirma que Edge requer firmware >= certa versão para Bluetooth estável em PC.

## 7. Base legal atualizada (2024-2026)

### 7.1 DMCA §1201 — 9ª rodada triennial (outubro 2024)

- **Fonte oficial:** https://www.copyright.gov/1201/2024/
- **Período de vigência:** 28/10/2024 – outubro/2027.
- **Exemption relevante:** interoperabilidade de dispositivos eletrônicos (jailbreaking/hacking) renovada. Embora o exemption principal seja voltado a celulares/routers, a **doutrina geral de interoperabilidade sob §1201(f)** permanece intacta.
- **Aplicação a Hefesto:** PHASE2 (captura de protocolo) é clara atividade de interoperabilidade entre controle Sony e sistema Linux. PHASE3 (reimplementar aplicação do firmware oficial) é derivativa desse esforço.

### 7.2 Legislação brasileira (LDA art. 77)

- Art. 77 da LDA (BR): descompilação permitida para interoperabilidade.
- Escopo compatível com PHASE2/3 desde que:
  - (a) não haja redistribuição do blob proprietário (Hefesto não redistribui);
  - (b) resultado sirva para interoperabilidade (permitir uso no Linux é interoperabilidade);
  - (c) não haja alteração do firmware (Hefesto só aplica o blob oficial do usuário).

### 7.3 UE — Diretiva 2009/24/EC art. 6

- Permite descompilação para interoperabilidade.
- Usuários europeus de Hefesto cobertos.

### 7.4 Precedente: Copyright Office 2024 rejections

- Copyright Office em 2024 **rejeitou** exemption específico para "AI security research" mas **renovou** todos os 4 exemptions de device interoperability.
- Mensagem implícita: device interoperability está solidamente protegida; outros territórios ainda em disputa.

## 8. PlayStation Remote Play + Android — caso de uso

### 8.1 Motivação do usuário

O usuário do Hefesto relatou (PHASE1 §2):
> "Eu e meus amigos só queremos rodar o update deles para fazer esse controle funcionar no Android".

Updates melhoram compatibilidade com Android/iOS/Switch 2. Hefesto em Linux permite acessar esse caminho sem Windows nem PS5.

### 8.2 PlayStation Remote Play app Android

- **Fonte oficial:** https://play.google.com/store/apps/details?id=com.playstation.remoteplay
- Requer DualSense com **firmware >= 0x0203** (mencionado em várias release notes 2023-2024).

### 8.3 Casos concretos encontrados

**WIP — pesquisa adicional pendente.** Próximas queries:
- Reddit /r/DualSense "android compatibility firmware version"
- XDA developers dualsense android

## 9. Lacunas de conhecimento (só hardware resolve)

Mesmo com todas as pesquisas feitas até agora, estes pontos **permanecem desconhecidos** e só captura real em VM Win + DualSense físico resolve:

1. **Report ID exato** que coloca o DualSense em modo DFU.
2. **PID do modo bootloader** (se difere de 0ce6/0df2).
3. **Sequência exata** de control transfers entre entrar em DFU e sair.
4. **Formato do chunk** enviado a cada bloco (tamanho? checksum local?).
5. **Handshake inicial** — challenge-response? Nonce? Signature check?
6. **Comportamento do watchdog** do controle durante update.
7. **Rollback** — existe path oficial de "cancelar update no meio"? Se sim, qual comando?
8. **Comportamento BT** — updater bloqueia BT; mas por quê? Report de exceção? Timeout? Refusal explícito?

## 10. Recomendações adicionais para PHASE2

Complementando a metodologia documentada em `FEAT-FIRMWARE-UPDATE-PHASE2-01.md`:

### 10.1 Setup de captura aprimorado

- **Não use** VirtualBox — passthrough USB fica flaky em updates longos. Prefira **virt-manager + QEMU + libvirt** com USB redirection. Ou host Windows nativo como dual boot.
- **usbmon em host Linux é suficiente** — a VM vê o dispositivo via passthrough, mas o host vê tudo na bus. Capturar no host = 1 ponto de falha a menos.
- **Cabo USB-C de qualidade com no mínimo 2.0** (USB-C→USB-A do PC; não usar hub). Atualizações Sony são sensíveis a jitter.

### 10.2 Ordem de captura recomendada

1. Baseline: 60s de tráfego normal sem updater aberto.
2. Updater aberto, detectando controle (ainda sem clicar update): 30s.
3. Início do update, até entrar em DFU (inferido por reconnect evento).
4. Progresso de write (maior parte do tempo).
5. Commit + reboot + handshake pós-reboot.
6. Post-reboot: 30s para ver controle novo em normal mode.

Cada etapa num pcap separado (`dfu-step-N.pcap`) para facilitar análise depois.

### 10.3 Ferramentas de análise

- `tshark` para análise offline sem UI.
- `usbhid-dump` para extrair report descriptors em cada etapa (se mudam entre etapas, registrar).
- `hidrd` para parsear report descriptors humanamente.
- Ghidra opcional se você for olhar o updater Sony binário (atenção à legalidade — análise estática de binário acessível publicamente cai em §1201(f) mas varia por jurisdição).

### 10.4 O que registrar no documento final de PHASE2

- Cada transfer de controle catalogado com:
  - Timestamp relativo ao início.
  - Transfer type (CONTROL/INTERRUPT/BULK).
  - Direction (host→device / device→host).
  - bmRequestType, bRequest, wValue, wIndex, wLength (control) ou endpoint (int/bulk).
  - Data (ou hash se > 64 bytes).
- Mapa de estados (enter_dfu → erase → write[0..N] → commit → reboot).
- Qual bloco precedeu qual — linearidade ou paralelismo?
- Resposta de erro hipotética (desligar controle mid-write e ver o que o updater tenta).

## 11. Referências de endereço — índice completo

### Repositórios

- `nowrep/dualsensectl` — https://github.com/nowrep/dualsensectl
- `nondebug/dualsense` — https://github.com/nondebug/dualsense
- `flok/pydualsense` — https://github.com/flok/pydualsense *(PHASE1)*
- `Ryochan7/DS4Windows` — https://github.com/Ryochan7/DS4Windows *(PHASE1)*
- `dsremap` — https://dsremap.readthedocs.io/en/latest/reverse.html
- `passinglink/passinglink` — https://github.com/passinglink/passinglink
- `Ohjurot/DualSense-Windows` — https://github.com/Ohjurot/DualSense-Windows
- `dualshock-tools/ds4-tools` — https://github.com/dualshock-tools/ds4-tools
- `AwesomeTornado/PSVR2-controller-explorer` — https://github.com/AwesomeTornado/PSVR2-controller-explorer
- `Paliverse/DualSense-List-of-Firmwares` — https://github.com/Paliverse/DualSense-List-of-Firmwares *(redistribuição de blobs; apenas contexto)*

### Blogs, artigos, guias

- Linux Gaming Central (guia Wine) — https://linuxgamingcentral.org/posts/how-to-update-dualsense-firmware-on-linux/
- blog.the.al DS4 series — https://blog.the.al/2023/01/02/ds4-reverse-engineering-part-2.html + part 4
- SensePost DualSense RE (2020) — https://sensepost.com/blog/2020/dualsense-reverse-engineering/
- PSXHAX firmware dump thread — https://www.psxhax.com/threads/ps5-dualsense-controller-firmware-dumped-decryption-by-scene-devs-required.10163/
- Wololo (cobertura) — https://wololo.net/2021/08/31/ps5-dualsense-controller-firmware-dumped-encrypted/
- DualSense descriptor gist — https://gist.github.com/dogtopus/894da226d73afb3bdd195df41b3a26aa

### Oficiais Sony

- `controller.dl.playstation.net/controller/lang/en/DualSenseUpdater.exe` (referenciado em PHASE1; não baixar no repo)
- `controller.dl.playstation.net/controller/lang/en/2100004.html` (página do updater Edge)
- `controller.dl.playstation.net/controller/lang/en/fwupdater.html` (updater DS4)

### Regulatório

- U.S. Copyright Office §1201 2024 — https://www.copyright.gov/1201/2024/
- Finnegan IP coverage 2024 — https://www.finnegan.com/en/insights/ip-updates/final-rule-issued-in-the-us-copyright-offices-ninth-triennial-section-1201-proceeding.html

### Comunidade / troubleshooting

- CachyOS forum (firmware update thread) — https://discuss.cachyos.org/t/dualsense-controller-firmware-update/17892
- PCGamingWiki DualSense Edge — https://www.pcgamingwiki.com/wiki/Controller:DualSense_Edge
- CodeWeavers CrossOver compat — https://www.codeweavers.com/compatibility/crossover/firmware-updater-for-dualsense-wireless-controller
- winget page — https://winget.run/pkg/PlayStation/DualSenseFWUpdater

## Apêndice A — Queries WebSearch efetuadas nesta sessão (transparência)

1. `dualsense firmware update linux github 2025 2026`
2. `dualsense DFU bootloader 054c 0ce6 reverse engineering`
3. `DualSenseUpdater wireshark usbmon capture protocol`
4. `nondebug dualsense github reverse engineering output report`
5. `DualShock 4 DS4 DFU protocol firmware update feature report`
6. `dualsense edge firmware 054c 0df2 bootloader update`
7. `dualsense firmware encryption AES decrypt scene dev`
8. `DMCA 1201 interoperability exemption 2024 triennial firmware`

WebFetches efetuados:
- `linuxgamingcentral.org/posts/how-to-update-dualsense-firmware-on-linux/`

Queries/fetches **pendentes para commits futuros** (ver WIP no documento):
- GitHub issues de `nowrep/dualsensectl` com busca `firmware|update|dfu`
- `nondebug/dualsense/blob/main/report-descriptor-usb.txt` fetch completo
- `blog.the.al/2023/01/02/ds4-reverse-engineering-part-2` fetch
- Reddit `/r/DualSense firmware android compatibility`
- Kernel `drivers/hid/hid-playstation.c` git log 2024-2026
- Hackaday DualSense teardowns
- USB.ids / linux-usb.org database para PIDs possíveis de bootloader Sony

## Apêndice B — Metodologia de atualização deste doc

Este survey é **incremental**. Cada commit novo deve:

1. Adicionar conteúdo a uma seção existente OU criar subseção nova numerada.
2. Atualizar Sumário executivo se surgir fato de alto impacto.
3. Mover item do Apêndice A (pendente) para o corpo do doc conforme for pesquisado.
4. Se encontrar **contradição ao PHASE1**, marcar em itálico com prefixo `**CORREÇÃO AO PHASE1:**`.
5. Manter este doc **sob 1000 linhas** — se crescer, fatiar em survey-parte-2.

## Apêndice C — Correções ao PHASE1 encontradas nesta sessão

*(Nenhuma até agora — PHASE1 permanece factualmente consistente. Se aparecerem correções nos próximos commits, serão listadas aqui para facilitar reconciliação.)*
