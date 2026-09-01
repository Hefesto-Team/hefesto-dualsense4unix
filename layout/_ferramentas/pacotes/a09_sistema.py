#!/usr/bin/env python3
"""O pacote da aba `09` Sistema.

O QUE TEM DONO: o serviço está de pé (o daemon respondeu — se ele calasse, não
haveria pacote), o perfil ativo, a política de bateria (`rumble_policy`, que é o
mesmo dado do Perfil de Bateria desta aba) e quantos controles ela alcança.

O ALCANCE É A LINHA QUE MAIS ERRA, e errou hoje: ela dizia *"Os 4 controles"*
com dois na mesa. Aqui ele sai de `conectados`, e a régua da aba o cobra.

O QUE NÃO TEM: as versões, os plugins e o estado dos consertos automáticos —
tudo isso é do `doctor` e do instalador, não do `state_full`.
"""
from __future__ import annotations

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. "versoes" e "consertos" tinham dono e viraram  # (noqa-acento) id
#: pintura. **"plugins" continua sem dono NA TELA, e a razão não é minha** — a
#: `gui/aba_sistema.py:95` já a tinha medido e escrito:
#:
#:     "IPC `plugin.list`/`plugin.reload`. Só a CLI chama
#:      (`cli/cmd_plugin.py`). Não há botão no produto de hoje."
#:
#: O método existe no daemon; o que não existe é quem o chame fora do terminal.
#: Este é o `sem_dono` legítimo desta casa: um valor que a tela mostraria como
#: se funcionasse, e que ninguém atende.
SEM_DONO: dict[str, str] = {
    "plugins": "o IPC `plugin.list` existe e só a CLI o chama — não há botão no "
               "produto de hoje (medido em `gui/aba_sistema.py:95`)",
}


def _versao() -> str:
    try:
        perfil._com_o_src()
        import hefesto_dualsense4unix as h

        return str(getattr(h, "__version__", "") or "")
    except Exception:
        return ""


def _leitura(ctx: Contexto):
    """O `Leitura` que a camada do produto espera.

    Cada campo dele nomeia quem o produz, e o docstring de lá lista os seis. O
    que esta função faz é buscá-los; nenhum é calculado aqui.
    """
    import subprocess

    perfil._com_o_src()
    from hefesto_dualsense4unix.gui import aba_sistema as _tela

    try:
        auto = subprocess.run(
            ["systemctl", "--user", "is-enabled", "hefesto-dev-dualsense4unix.service"],
            capture_output=True, text=True, timeout=3).stdout.strip()
    except Exception:
        auto = None
    # `online_systemd` porque o daemon respondeu: se `ctx.state` tem chave, ele
    # está no ar. O `daemon_actions._daemon_status()` distingue avulso de unit,
    # e essa distinção é da janela antiga — aqui o que importa é responder.
    return _tela.Leitura(status="online_systemd" if ctx.state else "offline",
                         autostart=auto, state=ctx.state or None)


@registrar("09-sistema.html")
def pacote(ctx: Contexto) -> dict:
    """DELEGA para `gui/aba_sistema.pacote` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA: dezoito nomes públicos em
    `gui/aba_sistema.py`, e o `casa-sabe` os listava como promessa sem caminho.
    E ela foi escrita PARA ESTA PÁGINA — as chaves que devolve são os
    `data-campo` daqui: `hefesto-estado`, `hefesto-pausa`,
    `hefesto-troca-de-perfil`, `hefesto-ambiente`.

    E SABE MAIS QUE O QUE EU TINHA ESCRITO: cada valor vem com `txt`, a classe
    do selo (`cls`), o glifo (`g`) e a dica. Meu pacote só tinha o texto — e as
    frases dele eram minhas, enquanto estas foram escritas com ela.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.gui import aba_sistema as _tela

    try:
        bruto = _tela.pacote(_leitura(ctx))
    except Exception as erro:
        return {"sem_dono": {"tela": {"sem_dono": True, "oque": str(erro)}},
                "cobertura": {"pintados": 0, "sem_dono": 1}}

    fora: dict[str, object] = {}
    for chave, v in (bruto.get("valores") or {}).items():
        # O ACHATAMENTO: a camada devolve `{"txt": …, "cls": …}` e a tela
        # endereça o texto. A classe e o glifo são pintura de estado, e ficam
        # para quem os quiser — o `-cls` e o `-g` são endereços novos.
        if isinstance(v, dict):
            fora[chave] = v.get("txt", "—")
            fora[f"{chave}-cls"] = v.get("cls", "")
        else:
            fora[chave] = v
    for chave in ("frase", "autostart", "perfil", "registro"):
        if not isinstance(bruto.get(chave), (dict, list)):
            fora[chave] = bruto.get(chave)
    fora["sem_dono"] = {k: {"sem_dono": True, "oque": v} for k, v in SEM_DONO.items()}
    fora["cobertura"] = {"pintados": len(fora), "sem_dono": len(SEM_DONO)}
    return fora




# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("09-sistema.html", "retomar")
def retomar(ctx: Contexto, o: dict, p) -> None:
    """Sair da pausa. `daemon.resume`.

    ELE TINHA UM CHAMADOR EM TODO O `src/` — o terminal (`cli/app.py:421`), como
    a `gui/aba_sistema.py:77` já tinha medido: *"a pausa fica gravada em disco e
    sobrevive a desligar o computador; até hoje só o terminal saía dela."* Este
    é o segundo, e é uma tela.
    """
    # `daemon.resume` não tem função no `ipc_bridge` — é o degrau 3 da ponte, e
    # passa pelo mesmo `_safe_call`, com o mesmo timeout do resto do produto.
    p.chamar("daemon.resume")


@gesto("09-sistema.html", "atualizar")
def atualizar(ctx: Contexto, o: dict, p) -> None:
    """Recarregar a configuração. `daemon.reload`.

    ELE LEVA 9,5 SEGUNDOS, medido no daemon dela em 01/09/2026 — contra 1 ms do
    `daemon.resume` e 57 ms do `daemon.status`. É a razão de os gestos rodarem em
    thread: síncrono, este botão congelaria a janela inteira por nove segundos e
    meio, e quem clicou concluiria que o app travou.
    """
    p.chamar("daemon.reload")


def _teto_do_perfil(escolha: str) -> str | None:
    """O que aquele botão grava em DISCO. Lido do produto, nunca digitado.

    `TETO_POR_PERFIL` (`app/actions/config/secao_orcamento.py:137`) é o dono da
    tradução botão → disco, e ela não é óbvia: `tudo_ligado` grava
    `"balanceado"` e não `"max"` (os dois devolvem o mesmo teto, e `balanceado`
    é o nome que a aba Vibração já usa), `bateria_longa` grava `"economia"`, e
    `eu_escolho` grava `None` — a AUSÊNCIA de teto de mesa.

    **O `None` não é "não mandar a chave", e a diferença decide o botão.** O
    `fundir_declaracao` (`utils/maquina.py:650`) documenta as duas: *"`None`
    presente na declaração é uma escolha e SOBRESCREVE. Só a AUSÊNCIA da chave
    preserva o que havia."* Omitir a chave no "Eu escolho" deixaria o teto
    antigo em disco com o botão aceso dizendo que não há teto.

    `KeyError` de propósito num `data-v` que não é perfil: gravar um teto que
    ninguém escolheu é pior que o gesto cair dizendo o nome.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        TETO_POR_PERFIL,
    )

    return TETO_POR_PERFIL[escolha]


def _ok_e_motivo(resposta) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu.

    O `ipc_bridge.machine_declare:861` devolve `(ok, motivo)` com o motivo já
    traduzido para frase de tela (`_MOTIVOS_MAQUINA`), e ele é o ponto do botão:
    `versao_desconhecida` quer dizer *"não gravei nada, e os bytes ficaram
    intactos"* — o botão aceso na tela passaria a mentir. Um gesto que descarta
    o retorno perde exatamente isso e vira o botão que responde calado.

    A TOLERÂNCIA AO `bool` NÃO É ENFEITE: o dublê da régua
    (`tests/unit/test_os_botoes_tem_dono.py`, `PonteDeMentira.__getattr__`)
    devolve a dupla só para `identity…_set` e `True` para todo o resto. Sem esta
    função o gesto rebentaria com `TypeError` na régua e funcionaria na mão dela
    — a régua reprovando a cura, que é a forma de defeito que esta casa já pagou
    onze vezes em 26/08.
    """
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


@gesto("09-sistema.html", "perfil-da-mesa")
def perfil_da_mesa(ctx: Contexto, o: dict, p) -> None:
    """Os três botões do Perfil de Bateria. `machine.declare`, e vale AGORA.

    POR QUE `machine.declare` E NÃO `rumble.policy_set`, que seria o palpite: o
    teto da MESA e a política de vibração são dois donos diferentes. O
    `_effective_mult` (`core/rumble.py:185`) lê os dois e aplica `min` entre
    eles — `_sob_o_teto`, nunca produto —, então gravar a escolha dela como
    política apagaria a política por controle que as outras abas escrevem. Quem
    é dono desta escolha é o `orcamento.teto` do `maquina.json`, e o contrato do
    produto diz o mesmo: `gui/aba_sistema.GESTOS["perfil-da-mesa"]` aponta para
    `secao_orcamento._ao_escolher:468`, que monta `{"orcamento": {"teto": …}}`.

    O QUE MUDA EM RELAÇÃO À JANELA ANTIGA, e é decisão dela: lá o
    `_ao_escolher` **não manda IPC** — acumula em `host._maquina_pendente` e só o
    "Aplicar" do rodapé grava (`footer_actions.py:353`). Aqui vale a regra de
    01/09: *"clicar na cor já deveria aplicar"*. O gesto age na hora, e o
    caminho é o MESMO que aquele "Aplicar" usa — `machine_declare_detalhado`, do
    `ipc_bridge`. Não é uma segunda porta para o disco.

    E ELE PEGA NA HORA, sem reiniciar nada: o `_handle_machine_declare`
    (`daemon/ipc_handlers.py:5324`) relê o `maquina.json` e **rebinda**
    `daemon._maquina`; o `_orcamento_declarado` (`core/rumble.py:105`) lê a
    fonte a cada pedido de vibração, e não uma cópia do boot. Está escrito lá
    com todas as letras: *"uma cópia feita no boot ficaria velha exatamente no
    instante em que ela acabou de escolher"*.

    A declaração é PARCIAL de propósito. O daemon funde contra o disco sob lock
    (`gravar_maquina_com_descartes:753`), então mandar só o orçamento não apaga
    a mesa, os controles nem o mapa que as outras seções declararam.
    """
    escolha = str(o.get("v") or "")
    if not escolha:
        raise ValueError(
            "perfil-da-mesa: o clique não disse qual dos três perfis. O botão "
            "manda `data-v` — se ele voltou a ser `data-perfil`, o piloto não o "
            "encaminha e os três viram o mesmo clique.")
    try:
        teto = _teto_do_perfil(escolha)
    except KeyError:
        raise ValueError(
            f"perfil-da-mesa: {escolha!r} não é perfil do produto. Os que existem "
            f"estão em `secao_orcamento.PERFIS`.") from None
    ok, motivo = _ok_e_motivo(p.machine_declare({"orcamento": {"teto": teto}}))
    if not ok:
        raise RuntimeError(motivo or "não consegui gravar o perfil da mesa")


#: OS OITO QUE NÃO SÃO IPC, e por isso não estão aqui. Medidos no fonte em
#: 01/09/2026, um a um — a linha de cada um está no relato da leva:
#:
#:   `reiniciar`            `systemctl --user restart` (daemon_actions.py:2277)
#:   `desligar`             `_run_systemctl_async("stop")` (daemon_actions.py:2234)
#:   `autostart`            `systemctl --user enable/disable` (…:2398)
#:   `refazer-consertos`    `bash scripts/*.sh` (…:1218)
#:   `refazer-proton`       diálogo GTK + `config.vdf` da Steam (…:1793)
#:   `procurar-camadas`     censo do `system.reg` em disco (emulation_actions.py:2075)
#:   `restaurar-de-fabrica` cópia do asset + `DraftConfig` (footer_actions.py:1477)
#:   `ver-detalhes`         `journalctl --user -n 80` (daemon_actions.py:2767)
#:
#: `ver-detalhes` É O OITAVO, e ele estava fora desta lista. Ligá-lo da tela
#: exige o helper privilegiado ou um método de log que o daemon não tem.
#:
#: E `ver-plugins` É DE OUTRA ESPÉCIE — o daemon ATENDE (`plugin.list` e
#: `plugin.reload`, `ipc_server.py:184-185`). O que falta é o caminho de VOLTA:
#: o gesto do piloto devolve `None` (`hefesto_vivo.py:_gesto`), e não há por
#: onde escrever a lista na página. Um gesto que chamasse `plugin.list` e
#: jogasse o resultado fora seria o botão "Ver os plugins carregados" que não
#: mostra plugin nenhum — o botão que responde calado, exatamente.
PONTE = {"chamar", "machine_declare"}
METODOS = {"daemon.resume", "daemon.reload", "machine.declare"}


PAGINA = "09-sistema.html"
PISO_DA_ABA = 3
PROVAS = [
    {"pagina": PAGINA, "gesto": "retomar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["daemon.resume"], {})]},
    {"pagina": PAGINA, "gesto": "atualizar", "clique": {},  # (noqa-acento) chave do contrato
     "chama": [("chamar", ["daemon.reload"], {})]},
    # A CHAVE DE DISCO NÃO SE DIGITA NA PROVA. Se a prova dissesse `"economia"`
    # e alguém trocasse a tradução no produto, a régua continuaria verde
    # cobrando o valor VELHO — a régua virando o segundo dono do fato que ela
    # existe para medir.
    {"pagina": PAGINA, "gesto": "perfil-da-mesa",  # (noqa-acento) id
     "clique": {"v": "bateria_longa"},
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("bateria_longa")}}], {})]},
    # O "Eu escolho" grava `None` PRESENTE, e é a prova de que a ausência de
    # teto viaja como escolha e não como omissão.
    {"pagina": PAGINA, "gesto": "perfil-da-mesa", "clique": {"v": "eu_escolho"},  # (noqa-acento) id
     "chama": [("machine_declare",
                [{"orcamento": {"teto": _teto_do_perfil("eu_escolho")}}], {})]},
]

#: OS TRÊS CUJO EFEITO O `state_full` NÃO MOSTRA, e cada um por um motivo:
#:
#:   atualizar       `daemon.reload` relê a configuração — o estado publicado
#:                   fica igual quando nada no disco mudou, e é o certo.
#:   perfil-da-mesa  grava `orcamento.teto` no `maquina.json`, não no daemon.
#:   retomar         `daemon.resume` num daemon que não está pausado é no-op.
#:                   Ele TEM eco — provado em 01/09: com `paused=True`, o clique
#:                   o levou a `False`. A régua o clica sem pausar antes, e é
#:                   por isso que ele entra aqui.
SEM_ECO = ("atualizar", "perfil-da-mesa", "retomar")
