"""Os atos da bandeja que o controle também faz: abrir o painel e o serviço.

OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01 (01/10/2026). A fala dela de 29/09
pediu, na lista dos gestos, *«abrir hefesto reiniciar serviço desligar ou
religar serviço tal como no tray»*. Os três atos moravam em ``cli/cmd_tray.py``
(TRAY-A-LISTINHA-DELA-01, 21/09) e saíram para cá **sem mudar uma linha de
comportamento**: a bandeja os importa, e o gesto do controle os chama pelo
``__main__`` deste arquivo. Um dono só, porque a quarta cópia é a que diverge.
<!-- noqa-acento: citação literal dela -->

O DAEMON NÃO CHAMA O ``systemctl`` DE DENTRO DE SI: ``reiniciar`` e ``parar``
matariam o próprio processo no meio do pedido. Ele abre
``[python, "-m", "…atos_da_bandeja", "reiniciar"]`` pelo
``integrations/fora_do_servico`` (fora do grupo do serviço, que o restart
derruba), e é este mesmo código rodando noutro processo.
"""
from __future__ import annotations

import subprocess
import sys

from rich.console import Console

from hefesto_dualsense4unix.utils import identidade
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

console = Console()

#: O LANÇADOR QUE O `install.sh` ESCREVE, e abre a mesma janela que o atalho
#: do menu dela. Apontar para o `run.sh` da árvore seria amarrar o tray a um
#: caminho de desenvolvimento; apontar para o binário instalado é o que faz o
#: «Abrir painel» funcionar em qualquer computador.
LANCADOR_DO_PAINEL = "hefesto-dualsense4unix-gui"

#: Os verbos do ``__main__``, na língua do gesto, para o verbo da unit.
VERBOS: dict[str, str] = {"reiniciar": "restart", "parar": "stop", "ativar": "start"}


def abrir_o_painel() -> None:
    """O «Abrir painel» — a diferença que mais pesa entre os dois trays.

    `setsid` E `start_new_session` PORQUE O TRAY PODE MORRER DEPOIS: sem
    desligar a sessão de processos, fechar o tray fecharia a janela que ele
    abriu. É o mesmo desenho do lançador que o `install.sh` escreve.
    """
    try:
        # O LANÇADOR É NOSSO e não recebe argumento de fora — nada a escapar.
        subprocess.Popen(
            [LANCADOR_DO_PAINEL],
            start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # BG-INSTALL-01 (20/09/2026): esta frase nasceu com o tray, em
        # 19/09, escrita de dentro de um checkout — e cravava o instalador.
        # Em cinco dos seis formatos deste produto (`.deb`, `.rpm`, Arch, Nix
        # e o pip) o arquivo não está na máquina de quem está lendo, e o
        # conselho vira impossível. Quem sabe o gesto desta instalação é o
        # `utils/repo_files`, que responde pelo formato REAL dela.
        console.print(
            f"[yellow]não achei `{LANCADOR_DO_PAINEL}` no PATH[/] — "
            f"o lançador do painel não veio nesta instalação; "
            f"{como_atualizar_esta_instalacao()}.")


def mexer_no_servico(verbo: str) -> bool:
    """`restart` · `stop` · `start` pela unit desta instalação.

    **QUEM EXECUTA É A CAMADA DE PRODUTO**, `DaemonActionsMixin`, do mesmo jeito
    que a aba Sistema a chama (`a09_sistema._systemctl`): o `reset-failed`
    antes de `start`/`restart` não é zelo — sem ele o `StartLimitBurst` recusa
    o segundo clique e a bandeja receberia "não consegui" sobre uma unit sã.

    **A UNIT NÃO SE DIGITA** — vem de `utils/identidade`. Uma literal do `-dev`
    já sobreviveu a uma purga e fez a tela afirmar `not-found` sobre uma unit
    `enabled` (01/09/2026).
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import DaemonActionsMixin

    unit = identidade.atual().unit_daemon
    janela = DaemonActionsMixin()
    if verbo in ("start", "restart"):
        janela._invoke_systemctl(["reset-failed", unit], check=False)
    resultado = janela._invoke_systemctl([verbo, unit], capture=True)
    pegou = getattr(resultado, "returncode", -1) == 0
    if verbo == "restart" and pegou:
        repor_o_lancador()
    return pegou


def repor_o_lancador() -> None:
    """O «Reiniciar» da bandeja repõe o lançador, como o da aba Sistema.

    **É O MESMO ATO E O MESMO DONO** (`reposicao_dos_lancadores.repor`) — e tem
    de ser: a decisão dela de 21/09/2026 é sobre o REINICIAR, não sobre a aba
    Sistema. Um «Reiniciar» na bandeja que não repusesse o lançador seria o
    mesmo botão fazendo duas coisas diferentes conforme de onde se clica.

    NUNCA LEVANTA: o `restart` já deu `rc=0`, e o tray não cai por um clique.
    O recibo vai ao registro, que é onde a bandeja tem onde falar.
    """
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    try:
        console.print(rl.frase_do_recibo(rl.repor()))
    except Exception as erro:  # ver a docstring
        console.print(f"[yellow]não consegui repor o lançador:[/] {erro}")


def argv_do_ato(ato: str) -> list[str]:
    """A linha que roda ``ato`` (``abrir``, ``reiniciar``, ``parar``) noutro processo.

    O interpretador é o de quem chama (``sys.executable``): é a instalação em
    que o daemon está rodando, e ela tem este pacote.
    """
    return [sys.executable, "-m", __name__, ato]


def main(argv: list[str] | None = None) -> int:
    """``python -m …atos_da_bandeja abrir|reiniciar|parar`` — o gesto do controle."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        console.print("uso: atos_da_bandeja abrir|reiniciar|parar")
        return 2
    ato = args[0]
    if ato == "abrir":
        abrir_o_painel()
        return 0
    verbo = VERBOS.get(ato)
    if verbo is None:
        console.print(f"ato desconhecido: {ato}")
        return 2
    return 0 if mexer_no_servico(verbo) else 1


__all__ = [
    "LANCADOR_DO_PAINEL",
    "abrir_o_painel",
    "argv_do_ato",
    "mexer_no_servico",
    "repor_o_lancador",
]


if __name__ == "__main__":  # pragma: no cover - o gesto do controle
    raise SystemExit(main())
