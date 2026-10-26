#!/usr/bin/env bash
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

rede_corrente() {
  local st
  st="$(wpa_cli -i "$1" status 2>/dev/null)" || return 1
  printf '%s\n' "$st" | grep -qx 'wpa_state=COMPLETED' || return 1
  printf '%s\n' "$st" | sed -n 's/^id=//p' | head -1
}

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

ESTADO="${HEFESTO_WIFI_ESTADO:-/run/hefesto-wifi-usb}"
FALHAS_PARA_REINICIAR=3
INTERVALO_MINIMO_S=600
REINICIOS_SEM_CURA_MAX=3

ler_numero() {
  local v
  v="$(cat "$1" 2>/dev/null)"
  case "$v" in ''|*[!0-9]*) echo 0 ;; *) echo "$v" ;; esac
}

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
    saida="$(zerar "$ifc" "$seco")"
    case "$saida" in *DESLIGADO*|*ERRO*|*desligaria*) echo "$saida" ;; esac
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

status() {
  local ifc disp porta hub vel id bg quedas bt h bdisp bporta achou=0
  for ifc in $(wifi_usb); do
    achou=1
    disp="$(readlink -f "$SYSFS/class/net/$ifc/device")"
    porta="$(basename "$(dirname "$disp")")"
    hub="$(hub_de "$porta")"
    vel="$(cat "$SYSFS/bus/usb/devices/$porta/speed" 2>/dev/null)"
    case "$vel" in
      480) vel="USB2 (480M)" ;;
      5000|10000|20000) vel="USB3 (${vel}M)" ;;
      *) vel="velocidade ${vel:-?}" ;;
    esac
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
    quedas="$(journalctl -k -b -q --no-pager 2>/dev/null | grep -cE 'rtw88_[0-9a-z]+ .*(device gone|mac power on failed)')"
    bt=""
    for h in "$SYSFS"/class/bluetooth/hci*; do
      [ -e "$h/device" ] || continue
      bdisp="$(readlink -f "$h/device")"
      bporta="$(basename "$(dirname "$bdisp")")"
      case "$bporta" in *-*) ;; *) continue ;; esac
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
