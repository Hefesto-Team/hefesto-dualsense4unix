#!/usr/bin/env bash
# wifi_usb.sh — o dongle Wi-Fi USB sem scan de fundo, o vigia do travamento mudo
# e o diagnóstico da porta.
#
# DE ONDE VEIO (O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01, 23/09/2026). Nasceu no repo
# pessoal dela, como `aurora-wifi-usb.sh` do self-heal do zsh, e mudou para cá
# por ordem dela: *"tudo que diz respeito ao funcionamento do hefesto tem que
# ser tirado do meu repo pessoal (…) e fazer parte do hefesto como um todo
# dentro do install"*. É da mesma família da Onda W, que o Hefesto já possui
# (o DKMS `rtw88_usb` e o powersave do NetworkManager), e o `--status` responde
# uma pergunta que é do rádio dos controles: o dongle voltou a dividir hub com
# um adaptador Bluetooth? Vale para a CLASSE — qualquer Wi-Fi USB —, não para
# o aparelho dela. Sem Wi-Fi USB na máquina, não faz nada.
#
# O SCAN DE FUNDO (medido em 23/09/2026). O Wi-Fi caía de 5 em 5 minutos, com
# duas cadências exatas: 300 s depois de associar no AP forte e ~30 s no fraco.
# São os dois intervalos do bgscan que o NetworkManager 1.46 entrega ao
# wpa_supplicant quando enxerga mais de um AP da mesma rede
# (`simple:30:-65:300`). Cada scan de fundo derrubava o `rtw88_8822bu` ("device
# gone", "failed to get tx report from firmware", "mac power on failed"): 82
# quedas num boot só, e 26 minutos sem rede quando a porta do hub extensor não
# reabilitou. A RAIZ É A PORTA (no hub alimentado da mesa os scans passaram sem
# queda); O GATILHO É O SCAN, e é ele que sai. Um desktop parado na mesa não
# precisa trocar de AP sozinho: se o AP some, o NetworkManager escaneia e
# associa no outro, que é o único scan que serve aqui.
#
# POR QUE NÃO PRENDER O BSSID: o NetworkManager 1.46 não tem opção para desligar
# o bgscan; ele só o omite quando a conexão está presa a um BSSID, e aí, se
# aquele AP cair, fica sem rede nenhuma. Então o bgscan é zerado NO
# wpa_supplicant, depois de cada associação, pela interface de controle:
# `wpa_cli set_network <id> bgscan ""` reinicia o bgscan da rede corrente sem
# reassociar (medido ao vivo: nenhuma queda, estado COMPLETED).
#
# O TRAVAMENTO MUDO É OUTRO DEFEITO, e o `--vigiar` é a cura dele (23/09/2026).
# Por quatro horas a internet sumiu com o dongle "associado": nenhuma queda no
# kernel, nenhum DISCONNECTED no wpa_supplicant, e nenhuma troca de chave de
# grupo depois da última (o roteador faz uma por hora). O rádio parou de ouvir
# e de falar, e ninguém percebeu: o firmware é quem vigia a perda de beacon, e
# firmware travado não avisa. Só desplugar o dongle trouxe a rede de volta.
# O `--vigiar` roda de minuto em minuto (`hefesto-wifi-usb-vigia.timer`):
# associado E o roteador sem responder nem ao ping nem ao ARP por 3 minutos
# seguidos = o travamento mudo. Aí ele reinicia a PORTA USB do dongle
# (USBDEVFS_RESET), que é o mesmo reset que o `hang_reset` do nosso `rtw88_usb`
# faz sozinho quando o driver VÊ a queda — os gatilhos são disjuntos por
# construção: um age quando o driver vê, o outro quando não vê. Freio: um
# reinício a cada 10 min no máximo, e depois de 3 seguidos sem cura ele PARA e
# diz para pôr a mão. O ARP entra na conta para um roteador que não responde a
# ping não virar "travamento": esse ainda responde ao ARP.
#
# O MODO USB2 FOI RECUSADO POR ELA (23/09/2026). O `switch_usb_mode=N` do
# rtw88_usb tiraria o ruído do USB3 em 2,4 GHz (a faixa do Bluetooth), mas a rede
# é de 5 GHz e o plano é de 1 Gb: cair para ~200-300 Mb/s é preço alto demais por
# uma ligação com as quedas do rádio que nem está provada. Se o ruído virar
# suspeita medida, a rota é distância (o dongle longe dos adaptadores
# Bluetooth), e o `--status` já avisa quando os dois voltam a dividir hub.
#
# OS GATILHOS, todos idempotentes:
#   - o dispatcher do NetworkManager (`up`): cada associação nova nasce sem bgscan;
#   - o vigia, de minuto em minuto: o reforço (pega a associação que o
#     dispatcher perdeu — script instalado depois de a rede subir, dispatcher
#     parado), calado quando não há o que fazer, e depois o travamento mudo;
#   - à mão: `sudo /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh --status`.
#
# Alcance: só interfaces Wi-Fi cujo aparelho está no barramento USB. Wi-Fi PCIe
# não tem o defeito e continua com o bgscan do NetworkManager.
#
# OS GANCHOS DE TESTE, e por que existem: o PATH abaixo é FIXO (o script roda
# como root, pelo systemd e pelo NetworkManager), e o script lê o sysfs e abre
# /dev/bus/usb direto. Sem ganchos, a suíte não conseguiria pôr dublês de
# `wpa_cli`, `ping` e `ip` na frente — e leria o dongle DE VERDADE de quem roda.
# Os cinco são resolvidos na CHAMADA:
#   HEFESTO_WIFI_BIN      diretório de dublês, posto na FRENTE do PATH fixo;
#   HEFESTO_WIFI_SYSFS    raiz do sysfs (default /sys);
#   HEFESTO_WIFI_DEV      raiz do /dev (default /dev) — onde mora o nó do reset;
#   HEFESTO_WIFI_ESTADO   onde o vigia guarda a contagem (default /run/hefesto-wifi-usb);
#   HEFESTO_WIFI_GW_TESTE o roteador, sem perguntar ao `ip route`.
# E UMA TRAVA: gancho de comandos sem sysfs de mentira é recusado — dublê de
# `wpa_cli` falando do dongle de verdade é o teste que reinicia a porta dela.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin
if [ -n "${HEFESTO_WIFI_BIN:-}" ]; then
  if [ -z "${HEFESTO_WIFI_SYSFS:-}" ] || [ -z "${HEFESTO_WIFI_DEV:-}" ]; then
    echo "wifi_usb.sh: HEFESTO_WIFI_BIN sem HEFESTO_WIFI_SYSFS e HEFESTO_WIFI_DEV — recuso (o dublê falaria do dongle de verdade)" >&2
    exit 97
  fi
  PATH="${HEFESTO_WIFI_BIN}:${PATH}"
fi
SYSFS="${HEFESTO_WIFI_SYSFS:-/sys}"
DEV="${HEFESTO_WIFI_DEV:-/dev}"

usage() {
  cat <<'EOF'
uso: wifi_usb.sh --ensure           zera o scan de fundo das interfaces Wi-Fi USB
     wifi_usb.sh --status           porta, velocidade, scan de fundo e quedas do boot
     wifi_usb.sh --vigiar [--seco]  o reforço do scan e o travamento mudo: reinicia
                                    a porta do dongle (--seco só diz o que faria)
     wifi_usb.sh --lista            as interfaces Wi-Fi USB, uma por linha (sem root)
     (chamado pelo NetworkManager como dispatcher, age só na ação `up`)
EOF
}

# As interfaces Wi-Fi cujo aparelho está no barramento USB, uma por linha.
wifi_usb() {
  local n usb
  usb="$(readlink -f "$SYSFS/bus/usb" 2>/dev/null)"
  [ -n "$usb" ] || return 0
  for n in "$SYSFS"/class/net/*; do
    [ -d "$n/wireless" ] || [ -e "$n/phy80211" ] || continue
    [ "$(readlink -f "$n/device/subsystem" 2>/dev/null)" = "$usb" ] || continue
    echo "${n##*/}"
  done
}

# O id da rede corrente no wpa_supplicant, só se a associação estiver completa.
rede_corrente() {
  local st
  st="$(wpa_cli -i "$1" status 2>/dev/null)" || return 1
  printf '%s\n' "$st" | grep -qx 'wpa_state=COMPLETED' || return 1
  printf '%s\n' "$st" | sed -n 's/^id=//p' | head -1
}

# A cadeia física do hub de um aparelho USB, sem o número do barramento:
# 4-4.1.2 -> 4.1 (o hub na porta 1 do hub da porta 4). Direto na raiz -> "raiz".
hub_de() {
  local cadeia="${1#*-}"
  case "$cadeia" in
    *.*) echo "${cadeia%.*}" ;;
    *)   echo raiz ;;
  esac
}

bgscan_de() {
  wpa_cli -i "$1" get_network "$2" bgscan 2>/dev/null
}

zerar() {
  local ifc="$1" seco="${2:-0}" id atual
  if ! id="$(rede_corrente "$ifc")" || [ -z "$id" ]; then
    echo "$ifc: sem associação completa, nada a fazer"
    return 0
  fi
  atual="$(bgscan_de "$ifc" "$id")"
  case "$atual" in
    ''|'""'|FAIL) echo "$ifc: scan de fundo já desligado"; return 0 ;;
  esac
  if [ "$seco" = 1 ]; then
    echo "$ifc: scan de fundo LIGADO ($atual) — desligaria agora (--seco, nada feito)"
    return 0
  fi
  if [ "$(wpa_cli -i "$ifc" set_network "$id" bgscan '""' 2>/dev/null)" = OK ]; then
    echo "$ifc: scan de fundo DESLIGADO (era $atual)"
  else
    echo "$ifc: ERRO ao desligar o scan de fundo (continua $atual)"
    return 1
  fi
}

# O TRAVAMENTO MUDO — ver o cabeçalho. O estado mora em /run (some no boot, de
# propósito: depois de um boot a contagem recomeça).
ESTADO="${HEFESTO_WIFI_ESTADO:-/run/hefesto-wifi-usb}"
FALHAS_PARA_REINICIAR=3      # minutos seguidos, com o timer de 1 min
INTERVALO_MINIMO_S=600       # um reinício a cada 10 min, no máximo
REINICIOS_SEM_CURA_MAX=3     # depois disso, para e pede a mão

ler_numero() {
  local v
  v="$(cat "$1" 2>/dev/null)"
  case "$v" in ''|*[!0-9]*) echo 0 ;; *) echo "$v" ;; esac
}

# O roteador responde? Ping primeiro; se o ping falhar, o ARP decide: roteador
# que bloqueia ping ainda responde ao ARP, e o travamento mudo deixa o vizinho em
# FAILED ou INCOMPLETE (ou sem entrada nenhuma).
roteador_responde() {
  local ifc="$1" gw="$2" viz
  ping -q -n -c 3 -W 1 -I "$ifc" "$gw" >/dev/null 2>&1 && return 0
  viz="$(ip neigh show "$gw" dev "$ifc" 2>/dev/null)"
  case "$viz" in
    ''|*FAILED*|*INCOMPLETE*) return 1 ;;
    *) return 0 ;;
  esac
}

reiniciar_o_dongle() {
  local ifc="$1" porta no
  porta="$(dirname "$(readlink -f "$SYSFS/class/net/$ifc/device")")"
  no="$DEV/bus/usb/$(printf %03d "$(ler_numero "$porta/busnum")")/$(printf %03d "$(ler_numero "$porta/devnum")")"
  # USBDEVFS_RESET = _IO('U', 20): reset de porta de verdade. O rtw88 não tem
  # pre_reset/post_reset, então o núcleo USB desliga o driver, reseta e religa — o
  # probe baixa o firmware de novo.
  if python3 - "$no" <<'EOF'
import fcntl
import os
import sys

fd = os.open(sys.argv[1], os.O_WRONLY)
try:
    fcntl.ioctl(fd, 0x5514)
finally:
    os.close(fd)
EOF
  then
    echo "$ifc: porta ${porta##*/} reiniciada (reset USB)"
    return 0
  fi
  # Plano B: desautorizar e reautorizar o aparelho, que refaz o probe.
  if echo 0 > "$porta/authorized" && sleep 2 && echo 1 > "$porta/authorized"; then
    echo "$ifc: porta ${porta##*/} reiniciada (authorized 0 -> 1)"
    return 0
  fi
  echo "$ifc: ERRO — não consegui reiniciar a porta ${porta##*/}"
  return 1
}

vigiar() {
  local seco="$1" ifc gw falhas n reiniciou_em agora base saida
  mkdir -p "$ESTADO" 2>/dev/null
  for ifc in $(wifi_usb); do
    base="$ESTADO/$ifc"
    # O REFORÇO DO DISPATCHER, que era do self-heal horário do zsh: pega a
    # associação que o dispatcher perdeu. Calado quando não há o que fazer — de
    # minuto em minuto, um "já desligado" por interface seria 1.440 linhas por
    # dia no journal de quem não perguntou nada.
    saida="$(zerar "$ifc" "$seco")"
    case "$saida" in *DESLIGADO*|*ERRO*|*desligaria*) echo "$saida" ;; esac
    # Sem associação completa quem cuida é o NetworkManager, que reassocia.
    if ! rede_corrente "$ifc" >/dev/null; then
      rm -f "$base.falhas"
      continue
    fi
    gw="${HEFESTO_WIFI_GW_TESTE:-$(ip -4 route show default dev "$ifc" 2>/dev/null | awk '{print $3; exit}')}"
    [ -n "$gw" ] || continue
    if roteador_responde "$ifc" "$gw"; then
      [ "$(ler_numero "$base.falhas")" -gt 0 ] && echo "$ifc: o roteador voltou a responder"
      [ "$(ler_numero "$base.reinicios")" -gt 0 ] && echo "$ifc: curado depois de $(ler_numero "$base.reinicios") reinício(s)"
      echo 0 > "$base.falhas"
      echo 0 > "$base.reinicios"
      continue
    fi
    falhas=$(( $(ler_numero "$base.falhas") + 1 ))
    echo "$falhas" > "$base.falhas"
    echo "$ifc: associado e o roteador $gw sem responder — $falhas de $FALHAS_PARA_REINICIAR"
    [ "$falhas" -ge "$FALHAS_PARA_REINICIAR" ] || continue
    n="$(ler_numero "$base.reinicios")"
    if [ "$n" -ge "$REINICIOS_SEM_CURA_MAX" ]; then
      echo "$ifc: $n reinícios seguidos sem cura — parei. Tire e ponha o dongle."
      continue
    fi
    reiniciou_em="$(ler_numero "$base.reiniciou_em")"
    agora="$(date +%s)"
    if [ $(( agora - reiniciou_em )) -lt "$INTERVALO_MINIMO_S" ]; then
      echo "$ifc: o último reinício foi há $(( agora - reiniciou_em )) s; espero dar $INTERVALO_MINIMO_S s"
      continue
    fi
    if [ "$seco" = 1 ]; then
      echo "$ifc: reiniciaria a porta do dongle agora (--seco, nada feito)"
      continue
    fi
    reiniciar_o_dongle "$ifc"
    echo $(( n + 1 )) > "$base.reinicios"
    echo "$agora" > "$base.reiniciou_em"
    echo 0 > "$base.falhas"
  done
}

# Uma linha por interface: porta, velocidade, scan de fundo, quedas do driver neste
# boot e se o hub é o mesmo de algum adaptador Bluetooth. Só LÊ.
status() {
  local ifc disp porta hub vel id bg quedas bt h bdisp bporta achou=0
  for ifc in $(wifi_usb); do
    achou=1
    disp="$(readlink -f "$SYSFS/class/net/$ifc/device")"
    porta="$(basename "$(dirname "$disp")")"        # ex.: 4-4.2
    hub="$(hub_de "$porta")"
    vel="$(cat "$SYSFS/bus/usb/devices/$porta/speed" 2>/dev/null)"
    case "$vel" in
      480) vel="USB2 (480M)" ;;
      5000|10000|20000) vel="USB3 (${vel}M)" ;;
      *) vel="velocidade ${vel:-?}" ;;
    esac
    # O `wpa_cli` recusa quem não é root (o socket de controle do
    # wpa_supplicant é de root — medido: "Permission denied"). Dizer "?" ali
    # soaria como defeito; é só falta de permissão, e a frase diz isso.
    if [ "$(id -u)" != 0 ]; then
      bg="sem permissão para ler (só root)"
    elif id="$(rede_corrente "$ifc")" && [ -n "$id" ]; then
      case "$(bgscan_de "$ifc" "$id")" in
        ''|'""'|FAIL) bg="desligado" ;;
        *) bg="LIGADO" ;;
      esac
    else
      bg="sem associação"
    fi
    # O contador é do rtw88 e diz isso: é a família de driver cuja queda por scan
    # foi medida. Outro driver Wi-Fi USB aparece como 0, e a frase não finge que
    # contou o dele.
    quedas="$(journalctl -k -b -q --no-pager 2>/dev/null | grep -cE 'rtw88_[0-9a-z]+ .*(device gone|mac power on failed)')"
    bt=""
    for h in "$SYSFS"/class/bluetooth/hci*; do
      [ -e "$h/device" ] || continue
      bdisp="$(readlink -f "$h/device")"
      bporta="$(basename "$(dirname "$bdisp")")"
      case "$bporta" in *-*) ;; *) continue ;; esac
      # Mesmo PCI (controlador) e mesma cadeia de hub = o mesmo hub físico, ainda
      # que um esteja na metade USB2 e o outro na USB3 dele. A porta raiz não conta:
      # ali quem é compartilhado é o controlador, não um hub.
      if [ "$hub" != raiz ] && [ "${bdisp%%/usb*}" = "${disp%%/usb*}" ] \
         && [ "$(hub_de "$bporta")" = "$hub" ]; then
        bt="$bt ${h##*/}"
      fi
    done
    if [ -n "$bt" ]; then
      bt="AVISO: mesmo hub que o Bluetooth ($bt )"
    else
      bt="hub sem Bluetooth"
    fi
    echo "$ifc · porta $porta · $vel · scan de fundo $bg · ${quedas:-0} quedas do rtw88 neste boot · $bt"
  done
  [ "$achou" = 1 ] || echo "nenhum Wi-Fi USB agora — o vigia fica armado e não faz nada"
}

# MODO DISPATCHER. O NetworkManager exporta NM_DISPATCHER_ACTION para todo
# script do dispatcher. Os argumentos posicionais não bastam: no
# `connectivity-change` a interface vem VAZIA, e a primeira versão deste script
# (no zsh) caía no `usage` e saía com 2 — o NetworkManager registrou "failed".
if [ -n "${NM_DISPATCHER_ACTION:-}" ]; then
  [ "$NM_DISPATCHER_ACTION" = up ] || exit 0
  ifc="${DEVICE_IFACE:-${1:-}}"
  [ -n "$ifc" ] || exit 0
  wifi_usb | grep -qxF "$ifc" || exit 0
  zerar "$ifc" 2>&1 | logger -t hefesto-wifi-usb
  exit 0
fi

case "${1:-}" in
  --ensure)
    rc=0
    for i in $(wifi_usb); do zerar "$i" || rc=1; done
    exit "$rc" ;;
  --status)
    status ;;
  --vigiar)
    seco=0
    [ "${2:-}" = --seco ] && seco=1
    vigiar "$seco" ;;
  --lista)
    wifi_usb ;;
  -h|--help)
    usage ;;
  *)
    usage; exit 2 ;;
esac
