#!/usr/bin/env bash
# interface — a interface nova do Hefesto, para ela abrir e testar.
#
# Pedido dela, 29/08/2026: um `.sh` chamado `interface` na raiz, para ela clicar
# e ver a visão final das páginas desenvolvidas — para ir testando sempre.
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

# UM CÉREBRO, UMA CARA. Este arquivo é a CARA — o que ela clica. Quem sabe
# abrir a interface é o `run.sh --gui`, e ele é o mesmo caminho que o `.desktop`
# instalado usa. Duas rotas separadas para a mesma janela é como uma delas fica
# para trás sem ninguém ver: aconteceu aqui, com este arquivo procurando o
# piloto em `…/interface/_ferramentas/hefesto_vivo.py` — pasta que não existe —
# e saindo com "não achei o piloto". Medido em 01/09/2026, clicando este arquivo.
#
# O QUE O `run.sh --gui` FAZ E ESTE ARQUIVO NÃO FARIA SOZINHO: ativa a venv
# desta árvore, desarma o `GDK_PIXBUF_MODULE_FILE` de terminal empacotado, força
# XWayland no COSMIC (os popups de GtkMenu quebram no Wayland nativo) e só então
# chama `scripts/abrir_interface.py`, que veste prgname, WM_CLASS e ícone no
# PROCESSO antes da primeira janela nascer.
MOTOR="$AQUI/run.sh"
if [ ! -x "$MOTOR" ]; then
    echo "não achei $MOTOR — a árvore está incompleta" >&2
    read -rp "Enter para fechar" _ || true
    exit 1
fi

echo "Hefesto — a interface nova"
echo
echo "As DEZ abas estão vivas, com o dado do daemon. 48 botões agem."
echo "Feche a janela para sair."
echo

exec "$MOTOR" --gui "$@"
