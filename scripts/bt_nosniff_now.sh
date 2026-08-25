#!/usr/bin/env bash
# bt_nosniff_now.sh — tira UM link BR/EDR do SNIFF no instante em que ele nasce.
#
# POR QUE EXISTE (BT-SNIFF-BORDA-01, 24/07)
#
# O `bt_active_mode.sh` já aplica o no-sniff por-conexão no Pro Controller
# genuíno, mas só a cada tick da vigia — 2 minutos. O comentário dele dizia que
# isso "cobre reconexão sem precisar caçar a borda"; a premissa caiu ao vivo: o
# Pro voltou a desconectar, e a janela entre o connect e o primeiro tick é
# exatamente onde o link negocia sniff e cai sob carga.
#
# O desfecho já estava previsto no próprio commit que criou o split por-OUI:
#
#   "Fica em aberto (gate humano): confirmar que o Pro aguenta uma sessão de 4
#    jogadores sob carga real com o no-sniff aplicado por-conexão em vez de
#    global. Se cair, o aprendizado é que ele precisa do no-sniff já DURANTE o
#    connect."
#
# Este script é esse "durante o connect": o udev o dispara na borda de criação
# do device HID (`82-nintendo-pro-nosniff.rules`), com o MAC vindo do HID_UNIQ
# e — quando o chamador o passa — o nome vindo do HID_NAME.
#
# O QUE ELE NÃO FAZ: mexer no default do adaptador. O adaptador tem de MANTER o
# SNIFF permitido — o 8BitDo clone precisa dele para probar, e negá-lo
# globalmente mata a probe com `ret=-110` (medido 23/07). Aqui é por-link.
#
# Reverter um link: `hcitool lp <MAC> RSWITCH,HOLD,SNIFF,PARK`.
set -euo pipefail

MAC="${1:-}"
#: Nome do controle. Vem por ARGUMENTO (chamada à mão, teste) ou, na falta
#: dele, do AMBIENTE — o udev exporta as propriedades do device para o programa
#: do `RUN+=`, e `HID_NAME` é uma delas. É por isso que a regra 82 não precisou
#: mudar o `RUN+=`: pôr o nome em `$env{}` na linha de comando o quebraria em
#: cinco argumentos, porque o udev separa o argv por espaço DEPOIS de
#: substituir, e "Nintendo Co., Ltd. Pro Controller" tem quatro espaços.
#:
#: OPCIONAL, e a ausência dele NÃO é "não é um Pro" — ver `_recusar` lá embaixo,
#: onde as duas recusas são palavras DIFERENTES.
NOME="${2:-${HID_NAME:-}}"
if [[ -z "${MAC}" ]]; then
    printf 'bt_nosniff_now.sh: uso: %s <MAC> [NOME]\n' "${0##*/}" >&2
    exit 2
fi

# A REGRA de "quem é um Pro genuíno" tem UM DONO:
# `src/hefesto_dualsense4unix/core/linhagem_nintendo.py` — `OUIS_CLONE`,
# `OUIS_NINTENDO_VISTAS` e `NOMES_PRO`. As três listas abaixo são a MESMA regra
# escrita em shell, e existem porque este script roda pelo udev, como root, na
# borda do connect: importar Python aqui é depender de um venv que pode não
# estar de pé exatamente no instante em que o Pro conecta.
#
# Cópia PINADA, não cópia solta:
# `tests/unit/test_o_no_sniff_alcanca_todo_pro.py` lê os dois lados e reprova se
# eles se separarem — inclusive quando o `linhagem_nintendo` ganhar uma faixa
# nova e esta cópia não.
#
# UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 / A1 (curado em 25/08/2026). Até esta data a
# linha aqui era `OUI_NINTENDO_REAL="E0:F6:B5"` e a decisão era a IGUALDADE com
# ela — uma faixa, a desta bancada, promovida a definição de "Pro". A Nintendo
# tem 82 faixas MA-L registradas e a 8BitDo tem UMA (medido contra
# `/usr/share/ieee-data/oui.csv` em 22/08/2026), então a lista fechada que
# funciona é a do CLONE, e a pergunta vai por NEGATIVA.
#
# FATO ERRADO, SUBSTITUÍDO: o comentário antigo dizia que esta constante era a
# "mesma fonte da verdade" do `NINTENDO_REAL_OUI` do `external_identity.py`.
# Aquele módulo parou de decidir por ela em 22/08 (passou a chamar
# `e_pro_genuino`), e a frase ficou descrevendo uma comunhão que não existia
# mais — que é como uma correção pela metade mantém as duas versões vivas.
OUIS_CLONE=("e4:17:d8")
OUIS_NINTENDO_VISTAS=("e0:f6:b5")
NOMES_PRO=("pro controller")

# DIÁRIO-QUE-NAO-MENTE-01 (15/08/2026): vazio = journal (produção); caminho =
# arquivo; `none` = nada. Existe porque a suíte roda estes scripts DE VERDADE e
# sem isto grava, no journal da máquina dela, linhas que descrevem eventos que
# nunca aconteceram. Motivo completo no cabeçalho do bt_bonds_autorestore.sh.
LOG_TAG=hefesto-bt
LOG_DEST="${HEFESTO_BT_LOG_DEST:-}"
_registrar() {
    case "${LOG_DEST}" in
        "")   logger -t "${LOG_TAG}" "$*" 2>/dev/null || true ;;
        none) : ;;
        *)    printf '%s %s: %s\n' "$(date -Is 2>/dev/null || true)" "${LOG_TAG}" "$*" \
                  2>/dev/null >>"${LOG_DEST}" || true ;;
    esac
}

# A DECISÃO, POR NEGATIVA — e as três recusas são palavras DIFERENTES.
#
# A ordem importa e cada degrau responde uma pergunta distinta:
#
#   1. está numa faixa de CLONE conhecida?  -> recusa, e a recusa é a CURA:
#      o firmware do 8BitDo em modo Switch trata a negativa de sniff como erro
#      e não completa o handshake (`ret=-110`, A/B de 23/07/2026);
#   2. está numa faixa que esta casa JÁ VIU num aparelho?  -> aplica, sem
#      consultar nome nenhum. É exatamente o comportamento de antes da cura, e
#      está aqui de propósito: nada que já funcionava passa a depender de um
#      dado novo;
#   3. o nome declarado tem cara de Pro?  -> aplica. É por AQUI que o Pro de
#      outra safra entra, que é o defeito que esta cura existe para matar;
#   4. nenhum dos dois  -> recusa, e o MOTIVO separa duas coisas que não são a
#      mesma (D-O-QUE-O-PRODUTO-DIZ-SEM-SABER, 25/08/2026): "você não declarou
#      o nome" é ausência de DECLARAÇÃO, do chamador; "o nome que você declarou
#      não é de um Pro" é ausência de CASAMENTO, medida aqui. Confundir as duas
#      é o defeito de forma F7, e era o que o `exit 0` mudo fazia.
_recusar() { _registrar "no-sniff na borda NÃO aplicado em ${MAC}: $*"; exit 0; }

# ANTES DE TUDO: o endereço tem de ter FORMA de endereço BR/EDR.
#
# Não é zelo tipográfico — é o preço de a regra 82 ter passado a casar por NOME
# (25/08/2026). Pelo CABO o `HID_UNIQ` do Pro é o serial `000000000001` (e o
# clone mente o MESMO serial: `assets/84-nintendo-pro-variant.rules`), e ali não
# existe link BR/EDR nenhum para tirar do sniff. Sem esta guarda, um Pro no cabo
# chegaria até o `hcitool lp`, falharia três vezes contra um "endereço" que não
# é endereço, e o journal registraria "a vigia tenta no próximo tick" — uma
# falha que não é falha, sobre uma cura que não tinha o que curar.
if [[ ! "${MAC}" =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
    _recusar "'${MAC}' não tem forma de endereço BR/EDR (seis octetos hex separados por ':') — pelo cabo o HID_UNIQ é o serial do device, e cabo não tem link para tirar do sniff"
fi

for _marca in "${OUIS_CLONE[@]}"; do
    if [[ "${MAC,,}" == "${_marca}"* ]]; then
        _recusar "é a faixa do clone 8BitDo, e para ele o no-sniff é veneno — o firmware trata a recusa de sniff como erro e a probe morre em 'ret=-110' (A/B de 23/07/2026). Recusar aqui É a cura, não uma falha"
    fi
done

_conhecida=1
for _marca in "${OUIS_NINTENDO_VISTAS[@]}"; do
    [[ "${MAC,,}" == "${_marca}"* ]] && { _conhecida=0; break; }
done

if [[ "${_conhecida}" -ne 0 ]]; then
    _parece_pro=1
    for _marca in "${NOMES_PRO[@]}"; do
        [[ "${NOME,,}" == *"${_marca}"* ]] && { _parece_pro=0; break; }
    done
    if [[ "${_parece_pro}" -ne 0 ]]; then
        if [[ -z "${NOME}" ]]; then
            _recusar "a faixa não é nenhuma das que esta casa já viu num aparelho e o CHAMADOR NÃO DECLAROU o nome — isto é 'não dá para saber se é um Pro', e não 'não é um Pro'. Quem chama passa o HID_NAME como 2º argumento e eu decido"
        fi
        _recusar "o nome declarado ('${NOME}') não é de um Pro Controller — o sniff fica como está"
    fi
fi

# SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026): escrever link
# policy não existe na mgmt API do BlueZ — `btmgmt` e `bluetoothctl` do 5.86 não
# têm comando para isso (conferido nos dois `--help` em 19/08/2026). O
# `hcitool lp` é o único caminho, e continua sendo. O que mudou é que a AUSÊNCIA
# dele deixou de ser um `exit 0` mudo: numa distro que moveu as depreciadas para
# `bluez-deprecated`, este script virava no-op invisível e o Pro seguia caindo
# sob carga sem nenhum rastro de por quê.
if ! command -v hcitool >/dev/null 2>&1; then
    _registrar "no-sniff na borda de ${MAC} NÃO aplicado: o 'hcitool' foi depreciado pelo BlueZ e não está nesta máquina (pacote bluez-deprecated / bluez-deprecated-tools), e nenhuma ferramenta viva escreve link policy — o Pro genuíno vai cair sob carga até isso ser resolvido"
    exit 0
fi

# O device HID pode nascer alguns milissegundos antes de o link aceitar mudança
# de policy. Três tentativas curtas cobrem isso sem segurar o udev: se ainda
# assim falhar, a vigia de 2 min aplica no próximo tick (degradação, não perda).
for _ in 1 2 3; do
    if hcitool lp "${MAC}" RSWITCH >/dev/null 2>&1; then
        _registrar "no-sniff aplicado na borda de conexão de ${MAC} (Pro genuíno)"
        exit 0
    fi
    sleep 0.2
done

_registrar "no-sniff na borda falhou para ${MAC}; a vigia tenta no próximo tick"
exit 0
