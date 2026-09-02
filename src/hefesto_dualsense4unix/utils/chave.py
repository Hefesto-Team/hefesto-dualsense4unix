"""A chave que desliga um Hefesto por completo — e o religa.

Pedido dela, 29/08/2026: *"temos que garantir que eu possa DESLIGAR o impacto
do outro Hefesto por completo e RELIGAR ele. (...) com o botão de desligar
funcionando sem zuar o resto"*.

POR QUE `systemctl mask` SOZINHO NÃO BASTA — MEDIDO, E CONTRA O ESPERADO
--------------------------------------------------------------------------
O plano óbvio é `stop` + `disable` + `mask` nas units do usuário, e a suposição
que vem junto é que isso também fecha o botão "Ligar daemon" da GUI, porque
`systemctl --user start` numa unit mascarada falha. **Falha, e o daemon sobe
assim mesmo.** ``app/actions/daemon_actions.py:2162-2176``: quando o
``systemctl start`` volta com ``rc != 0``, o código registra
``systemctl_start_falhou_tentando_popen`` e CAI num ``subprocess.Popen`` que
levanta o daemon direto::

    cmd = [sys.executable, "-m", "hefesto_dualsense4unix",
           "daemon", "start", "--foreground"]

Esse caminho não passa por systemd nenhum: máscara não o alcança. Por isso a
chave tem DUAS cintas, e esta é a que fecha o buraco — um arquivo que o próprio
daemon lê no boot, antes de tomar o aparelho.

O CONTRATO, e por que ele não pode falhar calado
-------------------------------------------------
A ausência do arquivo é o estado normal: sem ele, NADA muda — é o padrão, e
`test_a_chave_ausente_nao_muda_nada` trava isso. Com ele, o daemon recusa
subir, DIZ por quê, diz desde quando, e imprime o comando exato que desfaz. O
defeito mais caro desta casa é a cura escrita e nunca ligada; o segundo é a
ausência de notícia lida como sucesso. Esta chave não pode ser nenhum dos dois.

O arquivo mora no ``config_dir()``, pelo mesmo slug que nomeia perfis e socket
(``utils/identidade.py``) — e é isso que faz o ``hefesto-chave`` e o daemon
falarem do MESMO arquivo sem nenhum dos dois digitar o caminho do outro.
"""
from __future__ import annotations

from pathlib import Path

# ESTE MÓDULO SÓ LÊ, E ISSO É DECISÃO (29/08/2026)
# ------------------------------------------------
# Quem ESCREVE e APAGA a chave é o `scripts/hefesto-chave.sh`, que é o gesto
# humano; quem a LÊ é o produto, em dois pontos (`daemon/main.py:run_daemon` e
# `app/actions/daemon_actions.py`). Um escritor, um leitor.
#
# A primeira versão deste arquivo trazia também `escrever_a_chave`,
# `apagar_a_chave` e `esta_desligado` — e o
# `portao_a_casa_sabe_e_o_produto_nao_faz` as reprovou, com razão: nenhum
# caminho do produto as chamava, porque o script já escrevia o arquivo com o
# próprio `printf`. Duas mãos escrevendo o mesmo formato é exatamente a
# divergência que esta casa paga caro. `test_o_script_e_o_produto_concordam_no_
# nome_do_arquivo` é a régua que impede o nome de divergir agora que os dois
# lados são de linguagens diferentes.

#: O nome é uma frase, não uma sigla: quem topar com este arquivo sem contexto
#: nenhum — num backup, num `ls -a`, numa busca — tem de entender na hora o que
#: ele faz e que alguém o pôs ali de propósito.
NOME_DO_ARQUIVO = "DESLIGADO-pela-chave.flag"


def caminho_da_chave(config_dir: Path | None = None) -> Path:
    """Onde a chave mora: no ``config_dir()`` do app.

    `config_dir` explícito existe para o teste medir sem tocar o HOME.
    """
    if config_dir is None:
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _cfg

        config_dir = _cfg()
    return Path(config_dir) / NOME_DO_ARQUIVO


def motivo_do_desligamento(config_dir: Path | None = None) -> str | None:
    """O texto da chave, ou `None` quando não há chave nenhuma.

    Devolve string (nunca levanta) para que um arquivo ilegível não vire crash
    de boot do daemon: ilegível conta como desligado, com um motivo que diz
    isso. O estado seguro aqui é RECUSAR — quem pôs o arquivo queria o app
    parado, e um erro de leitura não é permissão para subir.
    """
    alvo = caminho_da_chave(config_dir)
    try:
        if not alvo.exists():
            return None
        texto = alvo.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return f"a chave existe mas não pôde ser lida ({exc})"
    return texto or "sem motivo escrito"


def recado_da_recusa(motivo: str, comando: str = "hefesto-chave estavel on") -> str:
    """A frase que o daemon imprime ao recusar — o quê, por quê e o que fazer.

    Três partes, na ordem da regra desta casa para frase de diagnóstico: o que
    aconteceu, por que, e o que fazer agora.
    """
    return (
        "O daemon NÃO subiu: este Hefesto está desligado pela chave.\n"
        f"  {motivo}\n"
        "Isso é uma decisão gravada em disco, não uma falha — alguém desligou\n"
        "esta instalação de propósito para que a outra rodasse sozinha.\n"
        f"Para religar:  {comando}"
    )


__all__ = [
    "NOME_DO_ARQUIVO",
    "caminho_da_chave",
    "motivo_do_desligamento",
    "recado_da_recusa",
]
