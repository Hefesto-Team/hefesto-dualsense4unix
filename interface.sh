#!/usr/bin/env bash
# interface — a interface nova do Hefesto, para ela abrir e testar.
#
# Pedido dela, 29/08/2026: *"cria um arquivo .sh chamado interface na raiz do
# outro dev pra eu clicar e lá abrir a visão final das páginas desenvolvidas pra
# eu ir testando sempre"*.
#
# O QUE ELE ABRE — 01/09/2026, e mudou: as DEZ abas vivas, não mais só a
# Controles. O mockup aprovado roda num `WebKit2.WebView` dentro de uma janela
# GTK3, pintado pelo daemon duas vezes por segundo, com a mesa REAL (os
# controles ligados agora, não os quatro do desenho). A tira de cima navega, e
# cada aba que ela abre continua viva.
#
# ELE ESCREVE, e isso também mudou. São 48 botões com dono: clicar num tom pinta
# a barra do controle, "Desligar" a apaga, o modo troca a máscara do gamepad
# virtual, "Salvar Perfil" grava no disco. O que o produto NÃO faz continua sem
# gesto, e o piloto recusa dizendo o nome — nunca calado.
#
# A JANELA NÃO FECHA SOZINHA. O `--segundos` existe para a bancada e nasce em
# ZERO; ele já teve `default=6.0`, e em 01/09 ela abriu o lançador e viu a
# janela viver oito segundos e sumir.
#
# A LOGO NA DOCK (29/08/2026, o outro pedido dela). O `.sh` NÃO decide ícone
# nenhum: quem decide é a JANELA, pelo `WM_CLASS` que ela publica e pelo
# `_NET_WM_ICON` que ela carrega. Por isso este lançador não chama o piloto
# direto — chama `scripts/abrir_interface.py`, que veste a identidade no
# PROCESSO (prgname, program_class e ícone) antes da primeira janela nascer, e
# só então carrega o piloto sem tocar numa linha dele. O porquê de cada passo,
# com o que foi medido, está no cabeçalho daquele arquivo.
#
# COMO ABRIR: clique duas vezes (o gerenciador de arquivos pergunta "Executar"),
# ou no terminal: ./interface
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# O PILOTO MORA EM `layout/`, E ESTE ARQUIVO DIZIA `novo-layout/` — corrigido em
# 31/08/2026. O commit `48b4e1a2` ("o produto lê de `layout/`; `novo-layout/`
# volta a ser só referência") migrou o produto, e este lançador ficou para trás.
#
# NÃO QUEBRAVA POR SORTE, e a sorte era fina: quem escolhe o piloto de verdade é
# o `scripts/abrir_interface.py`, que já lia de `layout/`. O `$PILOTO` daqui só
# servia para achar o `.venv` — mas as duas cópias JÁ DIVERGIRAM 25 KB (81.755
# contra 56.416 bytes), e bastava alguém passar a usar este caminho para a
# interface abrir a versão de anteontem.
#
# `layout/` é VERSIONADO e viaja em worktree; o fallback para a árvore de origem
# fica para o caso de esta cópia estar incompleta, e agora procura nas duas
# pastas em ordem: a viva primeiro, a de referência depois.
ORIGEM="/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix"
PILOTO=""
for RAIZ in "$AQUI" "$ORIGEM"; do
    for PASTA in src/hefesto_dualsense4unix/interface; do
        CANDIDATO="$RAIZ/$PASTA/_ferramentas/hefesto_vivo.py"
        [ -f "$CANDIDATO" ] && { PILOTO="$CANDIDATO"; break 2; }
    done
done

if [ -z "$PILOTO" ]; then
    echo "não achei o piloto (src/hefesto_dualsense4unix/interface/hefesto_vivo.py)" >&2
    echo "procurei em: $AQUI e $ORIGEM" >&2
    read -rp "Enter para fechar" _ || true
    exit 1
fi

# O envoltório de identidade é versionado e viaja junto desta árvore.
ABRIDOR="$AQUI/scripts/abrir_interface.py"
if [ ! -f "$ABRIDOR" ]; then
    echo "não achei $ABRIDOR — a árvore está incompleta" >&2
    read -rp "Enter para fechar" _ || true
    exit 1
fi

# O .venv da árvore onde o piloto está — ele importa o próprio produto.
PY="$(dirname "$PILOTO")/../../.venv/bin/python"
[ -x "$PY" ] || PY="$ORIGEM/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

# A VARIANTE, e sem ela nada funciona — medido em 30/08/2026.
#
# O produto escolhe a casa pelo `HEFESTO_VARIANTE` (utils/identidade.py). Sem a
# variável, este lançador procurava o socket do Hefesto ESTÁVEL — que ela
# desliga justamente para testar esta versão. O sintoma na tela era
# "[Errno 111] Conexão recusada" com o daemon de dev vivo e vendo o controle.
#
# Medido: sem a variável, `daemon_state_full()` devolve None; com ela, 1 controle.
# A VARIANTE MORREU EM 01/09/2026 — o `dev` saiu de tudo, por decisão dela, e
# `HEFESTO_VARIANTE` vazia é o app único. Esta linha forçava `dev` e mandaria o
# lançador para uma casa que não existe mais: config, socket e unit foram todos
# migrados para `hefesto-dualsense4unix`.
#
# Ela fica como export vazio para o caso de alguém a ter no ambiente: sem isto,
# um `HEFESTO_VARIANTE=dev` herdado do shell dela abriria a interface contra um
# socket que ninguém escuta, e o sintoma seria a tela dizendo "Hefesto
# desligado" com o daemon no ar.
export HEFESTO_VARIANTE=""

echo "Hefesto — a interface nova"
echo "  piloto : $PILOTO"
echo "  python : $PY"
echo
echo "As DEZ abas estão vivas, com o dado do daemon. 48 botões agem."
echo "Feche a janela para sair."
echo
echo "identidade da janela:"

exec "$PY" "$ABRIDOR" "$@"
