# Esquecer os controles — e a casa inteira — para testar a primeira vez

ESQUECER-OS-CONTROLES-01 (25/09/2026). Para simular a primeira vez que uma
pessoa conecta os controles: o Hefesto guarda o que lembra numa pasta datada,
passa a se comportar como numa máquina nova, e devolve tudo depois, byte a
byte. Nada é apagado: o que sai é MOVIDO (ou copiado), e o que o teste produziu
também fica guardado.

O inventário do que é guardado tem um dono só:
`src/hefesto_dualsense4unix/utils/memoria_dos_controles.py` (`INVENTARIO`).

## Os dois alcances

| alcance | comando | o que sai | o que fica |
|---|---|---|---|
| só os controles | `hefesto-dualsense4unix esquecer-controles` | a fila de números (`controllers.json`), as máscaras por aparelho, o `maquina.json`, os ajustes por controle dentro dos perfis (só a chave `controllers`), as versões antigas dos perfis, os lugares dos adaptadores, os diários do rádio; com privilégio, os pareamentos Bluetooth **dos controles** (fone, teclado e mouse ficam), as cópias de pareamento do Hefesto e o diário do root | perfis, jogos, lançadores, preferências |
| a casa inteira | `python3 scripts/guardar-e-devolver-a-casa.py guardar` | tudo acima, mais uma CÓPIA da configuração inteira, do histórico do estado e do que o Hefesto escreveu nos lançadores (`localconfig.vdf` e `config.vdf` da Steam, `config.json` do Heroic, `overrides` do Flatpak) | a cópia não remove nada: quem remove é o `uninstall.sh` |

O script da casa roda com o `python3` do sistema, **sem o produto instalado** —
é o que permite devolver depois do uninstall.

## Onde vai

- lado da pessoa: `~/.local/state/hefesto-memoria-guardada/<AAAAMMDD-HHMMSS>-<alcance>/`
- lado do root: `/var/lib/hefesto-memoria-guardada/<AAAAMMDD-HHMMSS>-<alcance>/` (700: leva chaves de pareamento)

As duas pastas ficam FORA das pastas do produto, e por isso o
`uninstall.sh --purge-config` não as leva.

## Privilégio

A parte do root passa por `sudo -A` quando há `SUDO_ASKPASS`, e por `sudo -n`
quando não há (vale depois de um `sudo -v` no mesmo terminal). Senha no meio do
comando, nunca: sem privilégio ele recusa **antes** de mover qualquer coisa.

O `bluetoothd` é parado por uns segundos quando há pareamento de controle a
mover — os aparelhos Bluetooth caem e voltam sozinhos. O agente de pareamento
do Hefesto é religado junto.

## Devolver

```bash
hefesto-dualsense4unix esquecer-controles --restaurar [<pasta>]
python3 scripts/guardar-e-devolver-a-casa.py devolver [<pasta>]
```

A mais nova, se não disser qual. O que estiver no lugar vai antes para
`<pasta>/depois-do-teste/<carimbo>/`, e o comando diz o que sobrescreveu. A
pasta guardada fica: dá para devolver de novo. Com `--seco`, os dois só dizem o
que fariam.

**O pareamento é a exceção, e a razão é do controle.** Um DualSense guarda uma
chave de pareamento só. Se ele foi pareado de novo durante o teste (ou resetado
pelo botão de trás), a chave antiga morreu nele: o devolver **não** põe a
antiga por cima de um pareamento vivo do mesmo controle, em adaptador nenhum.
A antiga fica na pasta do root.

Na casa inteira, três registros ficam só na pasta, porque o install novo grava
os dele e devolver o antigo por cima desencontraria o próximo uninstall: o
registro do Proton pinado, o das camadas Vulkan (as camadas que você mandou
MANTER são ditas pelo nome no fim do devolver) e o `kernel.log`.

## O roteiro da primeira vez de verdade

Na árvore do produto, com a Steam e os jogos fechados, e o askpass exportado:

```bash
python3 scripts/guardar-e-devolver-a-casa.py guardar --seco   # conferir a lista
python3 scripts/guardar-e-devolver-a-casa.py guardar          # os controles no rádio caem
# resetar os quatro controles (o furo de trás, cinco segundos)
./uninstall.sh --purge-config --yes
python3 scripts/guardar-e-devolver-a-casa.py limpa            # sobrou algo do Hefesto?
./install.sh --yes
# o teste
python3 scripts/guardar-e-devolver-a-casa.py devolver --seco
python3 scripts/guardar-e-devolver-a-casa.py devolver
```

O `limpa` responde lugar por lugar e sai com `1` se sobrou algo que não é de
propósito. De propósito são: o backup que o próprio uninstall faz
(`~/.config/hefesto-dualsense4unix.backup-*`), o Proton que o Hefesto extraiu
(é seu) e o quirk do boot (só sai com `--remove-usb-quirk`).

## O que a leitura dos apps tem de achar sozinha numa instalação nova

- **Steam**: os jogos da biblioteca (os `appmanifest` de toda biblioteca do
  `libraryfolders.vdf`); o atalho `hefesto-launch` nas Opções de Inicialização
  de todos os jogos, menos os de `jogos_sem_wrapper.txt`; o Proton pinado
  (o nome de `assets/proton-pin.conf`) no `CompatToolMapping` de todo jogo, menos os de fora
  do pino; o Steam Input desligado para o DualSense; e, depois do primeiro
  lançamento de cada jogo, o device de áudio da háptica no prefixo dele.
- **Heroic, Lutris, RetroArch, Dolphin, mGBA** (a aba Lançadores): cada cartão
  com a biblioteca LIDA e a contagem, ou «nunca aberto» se a pasta dele ainda não
  existe. No Heroic, o ambiente da ponte em `defaultSettings.enviromentOptions`
  (que o daemon escreve ao ver um controle); no Flatpak de cada um, o mesmo
  ambiente no `override`; nos prefixos do Heroic, o device da háptica.
- **umu**: os jogos do Heroic e do Lutris que passam pelo umu aparecem com a
  chave `steam_app_<N>` que o `umu.json` do jogo declara.
- **Flatpak**: se cada lançador em caixa enxerga os dispositivos
  (`devices=all`).
