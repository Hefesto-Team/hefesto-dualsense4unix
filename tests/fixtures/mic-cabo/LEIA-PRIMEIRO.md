# `tests/fixtures/mic-cabo/` — gravadas da máquina, nunca digitadas

MIC-CABO-SPDIF-01, **20/09/2026**, com um DualSense no cabo.

**Por que gravadas.** A régua que digita o que devia ler envelhece calada. Havia
prova viva nesta casa: `tests/unit/test_o_microfone_padrao_no_cabo.py` digitava
à mão a linha

```
iec958-stereo-input: Digital Input (S/PDIF) (type: SPDIF, priority: 0, availability unknown)
```

e ela já divergia do vivo — e, em 20/09, divergia duas vezes: com o UCM desta
casa instalado (`HAPTICA-NATIVA-01`), a porta de captura do DualSense no cabo
**nem se chama mais assim**. Ninguém viu, porque uma fixture digitada não
reclama.

| arquivo | de onde saiu | para que serve |
| --- | --- | --- |
| `descritores-usb-dualsense-2026-09-20.bin` | `/sys/bus/usb/devices/<X>/descriptors`, 245 B | responde «o microfone entra por uma porta digital?» sem servidor de som |
| `sources-cabo-2026-09-20.txt` | `LC_ALL=C pactl list sources`, só o bloco `alsa_input.*DualSense*Controller-00.*` | a porta ATIVA de hoje |
| `scontents-dualsense-2026-09-20.txt` | `LC_ALL=C amixer -c <DualSense> scontents` | o elemento de ganho que a placa TEM |
| `scontents-sem-captura-2026-09-20.txt` | `amixer -c 0 scontents` (placa HDMI desta máquina) | a placa que **não tem** o que ligar — a mordida 2 |
| `porta-ucm-mic-2026-09-20.txt` | o `SectionDevice."Mic"` do `DualSense-HiFi.conf` instalado | a definição da porta de HOJE |
| `porta-acp-iec958-stereo-input.conf` | `/usr/share/alsa-card-profile/mixer/paths/` | a definição da porta de **17/09**, antes do UCM desta casa |
| `porta-acp-analog-input-headset-mic.conf` | idem | uma porta que **liga** o ganho — a mordida 3 |

**Os nós do rádio ficam de fora de propósito:** os nomes deles carregam sufixo
derivado do endereço do controle, e endereço não entra em arquivo versionado.

**Como regravar**, se a máquina mudar: os comandos estão na coluna «de onde
saiu», todos com `LC_ALL=C` — sem ele o `pactl` traduz e o leitor fica cego.
Regravar é a resposta certa quando o mundo muda; **editar à mão é o defeito que
esta pasta existe para matar.**

**E UMA DIFERENÇA QUE NÃO É SUA, para você não a caçar:** o `pre-commit` desta
casa tira o espaço no fim da linha. O `pactl` emite exatamente uma linha assim
por bloco de source (`Flags: … LATENCY `), então um `diff` entre a gravação
crua e o que está aqui acusa **essa** linha, e só ela. Não é o mundo que mudou;
é o gancho. Nenhum parser desta pasta lê esse espaço.
