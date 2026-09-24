"""O doctor diz a PORTA e o APARELHO de cada -71 — STORM-USB-01, 20/09/2026.

A prova de pronto da sprint, na metade que é de código: *"o doctor passa a
dizer a porta e o aparelho de cada -71 dos últimos 7 dias"*. Até 19/09 ele
dizia só *"33 vez(es) nos últimos 7 dias"*, e a porta estava gravada em cada
uma das 33 linhas do `kernel.log` desde que o `storm_watch.sh` nasceu.

O QUE ESTE ARQUIVO MEDE, e o que ele NÃO mede: aqui é o DOCTOR — a costura
entre o log, o módulo e a frase do terminal. A lógica de endereçamento (as
cinco formas de linha do kernel, o hub em comum, a porta vazia) é cobrada em
`tests/unit/test_o_endereco_do_storm_usb.py`, e o tempo verbal da contagem em
`tests/unit/test_o_doctor_diz_quando_foi.py`.

**Nada aqui olha o `/sys` da máquina que roda a suíte.** A raiz entra por
`HEFESTO_DOCTOR_RAIZ_USB`, que é o mesmo argumento `--raiz-usb` com que o
suporte endereça um -71 contra o retrato de barramento de OUTRA máquina. Sem
isso a régua mudaria de resposta quando ela tirasse um DualSense da mesa.

AS MORDIDAS:

* :func:`test_o_doctor_diz_a_porta_e_o_aparelho` — apague a chamada a
  `_o_endereco_do_storm` em `check_kernel_watch` e ela reprova: volta o número
  sem endereço, que é o defeito inteiro da sprint.
* :func:`test_o_hub_em_comum_e_aviso_e_nao_nota_de_rodape` — troque o `warn`
  do caso `hub)` por `info` e ela reprova. O hub é a ÚNICA linha deste bloco
  sobre a qual há o que fazer; enterrá-la entre `info` é publicar a cura em
  letra miúda.
* :func:`test_evento_velho_nao_ganha_endereco` — arranque AS DUAS travas da
  janela (o `-gt 0` do doctor E o corte do módulo) e ela reprova. Arrancar
  uma só não morde, e foi assim que se descobriu que a guarda do doctor é
  ECONOMIA, não comportamento — está escrito lá.
* :func:`test_sem_python_do_produto_o_doctor_diz_que_nao_sabe` e
  :func:`test_python_que_nao_responde_o_doctor_diz_que_nao_sabe` — são DUAS
  guardas e agora são duas réguas. A primeira versão passava um python
  inexistente e dizia cobrir a primeira guarda; `py` vinha não-vazio, a guarda
  nem rodava, e arrancá-la deixava a régua verde.
* :func:`test_o_evento_sem_endereco_chega_ao_terminal` — engula o
  `sem_endereco` no trecho Python do doctor e ela reprova: a soma das portas
  ficaria menor que o total sem ninguém ver.
* :func:`test_a_janela_do_doctor_e_a_do_modulo_sao_uma_so` — fixe o
  ``--dias`` em 7 e ela reprova. **Achada pela conferência de 20/09**: era a
  mesma cegueira do `sem_endereco` entrando pela porta de trás — duas janelas
  diferentes deixam a soma dos endereços menor que a contagem com
  ``sem_endereco`` igual a zero, e nenhuma régua acusava.

* :func:`test_o_controle_sem_hid_vira_aviso_com_o_gesto` e
  :func:`test_a_entrada_largada_vira_aviso_com_o_gesto` (24/09, «nomear e
  religar») — troque o `warn` do `parada_hid)` ou do `parada_vazia)` por `info`
  e a régua dela reprova. São as duas entradas em que o kernel DESISTIU: nelas
  o controle não volta pelo kernel, e é a linha sobre a qual há o que fazer.

**DUAS MORDIDAS DESTE ARQUIVO NÃO MORDERAM NA PRIMEIRA TENTATIVA**, e as duas
estão corrigidas acima em vez de escondidas. Elas custaram também uma
sentinela do `doctor.sh` que foi escrita e removida: nenhuma entrada a
alcançava.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
import sys
import textwrap
from collections.abc import Callable

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts/doctor.sh"

#: O ambiente mínimo do doctor. Rodar o doctor inteiro traria sudo, systemd e o
#: daemon vivo para dentro de um teste — e o que se mede aqui é UMA costura.
_PREAMBULO = textwrap.dedent(
    """
    set -uo pipefail
    HOME="$TMPHOME"
    ROOT_DIR="$TMPROOT"
    warn() { printf 'WARN %s\\n' "$*"; }
    info() { printf 'INFO %s\\n' "$*"; }
    pass() { :; }
    conselho_de_instalacao() { :; }
    so_no_checkout() { :; }
    _python_do_produto() { printf '%s\\n' "$TMPPYTHON"; }
    """
)


def _do_fonte(abre: str) -> str:
    """O corpo de um trecho do doctor, do FONTE — nunca uma cópia.

    Copiar o bloco para dentro deste arquivo faria a régua medir a si mesma: no
    dia em que o doctor mudasse, ela continuaria verde sobre o texto antigo.
    """
    fonte = DOCTOR.read_text(encoding="utf-8")
    i = fonte.index(abre)
    j = fonte.index("\n}\n", i)
    return fonte[i:j] + "\n}\n"


def _roteiro() -> str:
    """O `_o_endereco_do_storm` e o corpo do `check_kernel_watch`, juntos."""
    endereco = _do_fonte("_o_endereco_do_storm() {\n")
    corpo = _do_fonte(
        '    local log="${HOME}/.local/state/hefesto-dualsense4unix/kernel.log"'
    )
    # O corpo usa `local`, que só existe dentro de função — mesmo contexto do
    # doctor de verdade, onde ele é o corpo de `check_kernel_watch`.
    return _PREAMBULO + "\n" + endereco + "\n_bloco() {\n" + corpo + "\n_bloco\n"


def _no(raiz: pathlib.Path, porta: str, vid: str, pid: str, nome: str, classe: str) -> None:
    no = raiz / porta
    no.mkdir(parents=True, exist_ok=True)
    (no / "idVendor").write_text(vid + "\n", encoding="utf-8")
    (no / "idProduct").write_text(pid + "\n", encoding="utf-8")
    (no / "product").write_text(nome + "\n", encoding="utf-8")
    (no / "bDeviceClass").write_text(classe + "\n", encoding="utf-8")


def _rodar(
    linhas: list[str],
    *,
    janela: int = 7,
    com_sys: bool = True,
    python: str | None = None,
    montar: Callable[[pathlib.Path], None] | None = None,
    vigia: str = "active",
) -> str:
    """Escreve um `kernel.log` e um `/sys` de mentira; devolve o que o bloco imprime."""
    import tempfile

    with tempfile.TemporaryDirectory() as lar:
        lar_path = pathlib.Path(lar)
        estado = lar_path / ".local/state/hefesto-dualsense4unix"
        estado.mkdir(parents=True)
        (estado / "kernel.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        raiz_usb = lar_path / "sys"
        raiz_usb.mkdir()
        if com_sys:
            _no(raiz_usb, "3-4", "05e3", "0610", "USB2.1 Hub", "09")
            _no(raiz_usb, "3-4.1", "05e3", "0610", "USB2.1 Hub", "09")
            _no(raiz_usb, "3-4.1.3", "054c", "0ce6", "DualSense", "00")
            _no(raiz_usb, "3-4.4", "2357", "0604", "UB500", "e0")
        if montar is not None:
            montar(raiz_usb)
        env = dict(
            os.environ,
            TMPHOME=lar,
            TMPROOT=str(RAIZ),
            TMPPYTHON=(python if python is not None else sys.executable),
            HEFESTO_DOCTOR_JANELA_DIAS=str(janela),
            HEFESTO_DOCTOR_RAIZ_USB=str(raiz_usb),
            # O estado do timer do watchdog, pelo gancho: a régua não pergunta
            # ao systemd de quem a roda.
            HEFESTO_DOCTOR_VIGIA_DO_REBIND=vigia,
        )
        r = subprocess.run(
            ["bash", "-c", _roteiro()],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(RAIZ),
        )
        return r.stdout + r.stderr


def _linha(dias_atras: int, mensagem: str) -> str:
    d = datetime.date.today() - datetime.timedelta(days=dias_atras)
    return f"{d.isoformat()}T12:00:00-03:00 [USB-71] {mensagem}"


def test_o_doctor_diz_a_porta_e_o_aparelho() -> None:
    """A entrega da sprint: o -71 sai com o endereço, não só com o número.

    A MORDIDA: apague a chamada a `_o_endereco_do_storm` dentro de
    `check_kernel_watch` e esta régua reprova — sobra o "33 vez(es)" que não
    manda ninguém a lugar nenhum.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ]
    )
    assert "3-4.1.3" in saida, f"o doctor não disse a porta:\n{saida}"
    assert "DualSense (054c:0ce6)" in saida, f"o doctor não disse o aparelho:\n{saida}"
    # O PREFIXO, FIXADO AQUI DE PROPÓSITO: quem o vigiava era
    # `test_log_limpo_nao_ganha_bloco_de_endereco`, e só pela AUSÊNCIA. Mudar o
    # texto do `porta)` deixava as duas verdes — a régua do log limpo passaria a
    # afirmar a ausência de uma frase que já não existe em lugar nenhum.
    # E A ENTRADA PELO DONO DO NOME (24/09, «nomear e religar»): com a bancada
    # injetada, os nomes que ela deu não valem — é outra máquina — e sobra o
    # que o desenho dá a qualquer um, «Entrada 4.1.3», com o caminho junto.
    assert "-71 em Entrada 4.1.3 (3-4.1.3)" in saida, f"o prefixo do bloco mudou:\n{saida}"


def test_o_doctor_diz_o_hub_no_caminho() -> None:
    """A pergunta 1 da sprint — *"é a porta, o cabo ou o hub?"* — sai na linha."""
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ]
    )
    assert "atrás de 2 hubs" in saida, saida
    assert "Entrada 4.1 (3-4.1): USB2.1 Hub" in saida, saida


def test_a_porta_que_nao_existe_mais_nao_ganha_aparelho() -> None:
    """Porta vazia: o doctor diz que NÃO SABE qual era, e nunca nomeia um vizinho.

    É o caso mais comum de um -71 de quatro dias atrás — o aparelho caiu e não
    voltou. Emprestar a identidade de quem está no hub ao lado daria um laudo
    convincente e falso.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(3, "usb 3-9.9: device descriptor read/all, error -71"),
        ]
    )
    assert "3-9.9" in saida, saida
    assert "não guarda quem já esteve aqui" in saida, saida
    assert "DualSense" not in saida, f"nomeou um aparelho que não está na porta:\n{saida}"


def test_o_hub_em_comum_e_aviso_e_nao_nota_de_rodape() -> None:
    """Duas portas em pane sob o mesmo hub viram WARN, com o que fazer junto.

    A MORDIDA: troque o `warn` do caso `hub)` por `info` e esta régua reprova.
    Das linhas deste bloco, a do hub é a ÚNICA sobre a qual há ato possível —
    publicá-la no mesmo tom das outras é esconder a cura no meio do laudo.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
            _linha(2, "usbhid 3-4.4:1.3: can't add hid device: -71"),
        ]
    )
    linhas_do_hub = [
        linha for linha in saida.splitlines() if "está no caminho de 2 entradas" in linha
    ]
    assert linhas_do_hub, f"o hub em comum não foi nomeado:\n{saida}"
    assert linhas_do_hub[0].startswith("WARN "), linhas_do_hub[0]
    assert "ligue direto numa entrada do computador" in linhas_do_hub[0]


def test_uma_porta_so_nao_acusa_o_hub() -> None:
    """Com uma porta ruim, nenhum WARN de hub — o aparelho dela já explica tudo."""
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ]
    )
    assert "está no caminho de" not in saida, saida


def test_evento_velho_nao_ganha_endereco() -> None:
    """Fora da janela, nenhum endereço — o passado não se conta no presente.

    A MORDIDA EXIGE AS DUAS TRAVAS, e descobrir isso custou uma mordida que
    NÃO mordeu: arrancar só o `-gt 0` do `check_kernel_watch` não faz o evento
    de agosto aparecer (o `--dias` do módulo o corta), e arrancar só o corte do
    módulo também não (a guarda nem chama). Arranque AS DUAS e esta régua
    reprova, com o defeito de 03/09 de volta — um endereço de agosto impresso
    como se fosse a queda de ontem.

    A redundância é deliberada e está escrita no doctor: a guarda é economia
    de dois `python3` por execução; quem decide a janela é o módulo.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(30, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ]
    )
    assert "histórico" in saida, saida
    assert "3-4.1.3" not in saida, f"endereçou um evento de 30 dias atrás:\n{saida}"


def test_a_janela_do_doctor_e_a_do_modulo_sao_uma_so() -> None:
    """O `--dias` que o doctor passa é o `HEFESTO_DOCTOR_JANELA_DIAS` que ele conta.

    A MORDIDA: troque o ``--dias "${dias}"`` por um ``7`` fixo e esta régua
    reprova — com a janela em 30 o WARN continuaria dizendo *"1 vez(es) nos
    últimos 30 dias"* e o bloco de endereços viria VAZIO, que o doctor lê como
    "o módulo não respondeu".

    E O `sem_endereco` NÃO PEGARIA ISSO, que é o ponto: ele mede o que o
    módulo não soube LER dentro da janela DELE. Duas janelas diferentes fazem
    a soma dos endereços ficar menor que a contagem com `sem_endereco` igual a
    zero — exatamente a cegueira que o `sem_endereco` foi escrito para
    impedir, entrando pela porta de trás.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(20, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        janela=30,
    )
    assert "nos últimos 30 dias" in saida, saida
    assert "-71 em Entrada 4.1.3 (3-4.1.3)" in saida, (
        f"a janela do módulo não é a do doctor:\n{saida}"
    )
    assert "não respondeu" not in saida, saida


def test_sem_python_do_produto_o_doctor_diz_que_nao_sabe() -> None:
    """Sem python, a resposta é "NÃO SEI" — nunca silêncio.

    É o caso da instalação por PACOTE que não carrega o módulo. A MORDIDA:
    troque o `info` desta primeira guarda por um `:` mudo e esta régua reprova.

    **DUAS GUARDAS, DUAS RÉGUAS, e a separação custou uma mordida que não
    mordeu:** a primeira versão deste teste passava um python INEXISTENTE e
    dizia cobrir esta guarda — mas `py` vinha não-vazio, a guarda nem rodava,
    e quem respondia era a segunda (:func:`test_python_que_nao_responde_...`).
    Arrancar esta linha deixava a régua verde. Agora cada guarda tem a sua.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        python="",
    )
    assert "não está ao alcance deste doctor" in saida, saida


def test_python_que_nao_responde_o_doctor_diz_que_nao_sabe() -> None:
    """Python que existe no nome e não roda: também "NÃO SEI", e por outra frase.

    A MORDIDA: troque o `info` do laudo vazio por um `return` mudo e esta régua
    reprova. Depois de um WARN de 33 eventos, a ausência de linhas de endereço
    se lê como "nenhum deles tem endereço" — ausência de medida vendida como
    medida de ausência.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        python="/nao/existe/python",
    )
    assert "não respondeu" in saida, saida


def test_o_evento_sem_porta_nao_vira_modulo_mudo() -> None:
    """Um -71 que o parser não endereça NÃO se lê como "o módulo não respondeu".

    As duas ausências são opostas e a mesma frase serviria às duas: *"não sei
    ler esta forma de linha"* é uma medição; *"o módulo não respondeu"* é a
    falta dela. Aqui o log só tem linhas inendereçáveis — o laudo sai, com a
    confissão certa, e a frase de falha não aparece.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbaudio: a shape this parser has never seen, error -71"),
        ]
    )
    assert "ficaram SEM endereço" in saida, saida
    assert "não respondeu" not in saida, saida


def test_o_evento_sem_endereco_chega_ao_terminal() -> None:
    """A linha que o parser não soube ler é DITA, e o total fecha com a contagem.

    A MORDIDA: engula o `sem_endereco` no trecho Python de
    `_o_endereco_do_storm` e esta régua reprova — o doctor mostraria uma porta
    sobre três eventos, com a diferença invisível.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
            _linha(2, "usbaudio: a shape this parser has never seen, error -71"),
            _linha(1, "outra forma estranha sem dois pontos"),
        ]
    )
    assert "3 vez(es) nos últimos 7 dias" in saida, saida
    assert "2 evento(s) [USB-71] da janela ficaram SEM endereço" in saida, saida


def test_log_limpo_nao_ganha_bloco_de_endereco() -> None:
    """Sem -71 na janela, nem uma linha a mais: o doctor não fala do que não houve."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado"])
    assert "-71 em " not in saida, saida
    assert "NÃO SEI em qual porta" not in saida, saida


def test_o_endereco_nao_le_o_sys_da_maquina_que_roda() -> None:
    """Com a raiz injetada VAZIA, nenhum aparelho é nomeado — nem o dela.

    É a guarda de universalidade (F9): se esta régua dependesse do barramento
    de quem a roda, ela mudaria de resposta entre a máquina dela e o CI, e
    nenhuma das duas respostas seria sobre o produto.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(2, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        com_sys=False,
    )
    assert "3-4.1.3" in saida, saida
    assert "054c" not in saida, f"leu o /sys de fora da bancada injetada:\n{saida}"


def _interface_hid_sem_driver(raiz: pathlib.Path) -> None:
    """A HID do DualSense de `3-4.1.3` sem driver — o desfecho do `can't add hid device`."""
    interface = raiz / "3-4.1.3:1.3"
    interface.mkdir()
    (interface / "bInterfaceClass").write_text("03\n", encoding="utf-8")


def test_o_controle_sem_hid_vira_aviso_com_o_gesto() -> None:
    """O controle encaixado sem o HID sai em WARN, com a entrada e o gesto.

    A MORDIDA: troque o `warn` do caso `parada_hid)` por `info` e esta régua
    reprova — o controle mudo para o jogo ficaria no mesmo tom da contagem.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(1, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        montar=_interface_hid_sem_driver,
    )
    linhas = [linha for linha in saida.splitlines() if "sem o HID" in linha]
    assert linhas, f"o controle parado não foi dito:\n{saida}"
    assert linhas[0].startswith("WARN Entrada 4.1.3 (3-4.1.3): o controle está nela"), linhas[0]
    assert "O Hefesto tenta religá-lo sozinho a cada 2 minutos" in linhas[0], linhas[0]
    assert "tire e ponha o cabo desse controle" in linhas[0], linhas[0]


def test_sem_a_vigia_o_doctor_nao_promete_o_religar() -> None:
    """Com o timer do watchdog parado, a linha não diz que o Hefesto religa sozinho.

    Conferência de 24/09: o «tenta religá-lo sozinho a cada 2 minutos» saía
    sem perguntar se a vigia que faz isso estava de pé — o órfão do rádio, no
    mesmo doctor, já perguntava. A MORDIDA: tire o `if` do estado da vigia e
    deixe só a frase de sempre, e esta régua reprova.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(1, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ],
        montar=_interface_hid_sem_driver,
        vigia="inactive",
    )
    linhas = [linha for linha in saida.splitlines() if "sem o HID" in linha]
    assert linhas, f"o controle parado não foi dito:\n{saida}"
    assert linhas[0].startswith("WARN "), linhas[0]
    assert "tenta religá-lo sozinho" not in linhas[0], linhas[0]
    assert "hefesto-bt-health-watchdog.timer) está inactive" in linhas[0], linhas[0]
    assert "tire e ponha o cabo desse controle" in linhas[0], linhas[0]


def test_o_controle_com_hid_nao_vira_aviso() -> None:
    """Sem a interface sem driver, nenhum WARN de parada — o controle está de pé."""
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(1, "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
        ]
    )
    assert "sem o HID" not in saida, saida
    assert "desistiu dela" not in saida, saida


def test_a_entrada_largada_vira_aviso_com_o_gesto() -> None:
    """A entrada que o kernel largou vazia sai em WARN, com o gesto de tirar e pôr.

    A MORDIDA: troque o `warn` do caso `parada_vazia)` por `info` e esta régua
    reprova.
    """
    saida = _rodar(
        [
            "# 2026-07-20 kernel-watch iniciado",
            _linha(1, "usb 3-9.9: device not accepting address 10, error -71"),
            _linha(1, "usb 3-9-port9: unable to enumerate USB device"),
        ]
    )
    linhas = [linha for linha in saida.splitlines() if "desistiu dela" in linha]
    assert linhas, f"a entrada largada não foi dita:\n{saida}"
    assert linhas[0].startswith("WARN Entrada 9.9 (3-9.9): o kernel desistiu dela"), linhas[0]
    assert "tire e ponha" in linhas[0], linhas[0]
