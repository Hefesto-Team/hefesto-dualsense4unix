"""BG-06 — o grau que sumia no meio de centenas, e o conselho impossível.

DOIS DEFEITOS do `scripts/doctor.sh`, medidos em 25/08/2026.

**(1) O GRAU ESTAVA ERRADO.** Com `JustWorksRepairing=confirm` (o valor que
esta casa instala) e o `hefesto-bt-agent.service` morto, o exame dizia
``[WARN]``. Mas `confirm` só aceita o Just Works repairing se um agente
registrado confirmar — sem agente não há quem confirme, e o BlueZ recusa. Não é
um risco à espreita: é o produto parado na coisa principal. Um aviso no meio
de centenas de linhas SOME; uma falha muda o veredito final e o código de saída
do script.

**(2) O CONSELHO ERA IMPOSSÍVEL.** Trinta e três frases mandavam *"rode
`./install.sh`"*, e `./install.sh` só existe para quem clonou o repositório.
A tabela é da T-03 (medida em 23/08/2026):

| formato | leva os scripts? | tem `./install.sh`? |
|---|---|---|
| checkout | sim | **sim** |
| .deb | sim | não |
| Flatpak / AppImage / Arch / Fedora / Nix | não | não |

Em CINCO dos SEIS formatos a pessoa via a frase com MAIS frequência — porque as
coisas realmente faltavam — e a única instrução que recebia era a que não tinha
como cumprir.

COMO ESTA BANCADA MORDE

Ela não lê o `doctor.sh`: ela o **executa**, nos dois layouts que existem no
mundo. O checkout é a árvore congelada (tem `install.sh` na raiz); o pacote é
uma cópia de `scripts/doctor.sh` sozinha num diretório temporário — que é
LITERALMENTE o layout do `.deb`, onde `ROOT_DIR` aponta para um lugar sem
instalador. Nenhum `monkeypatch`, nenhum dublê da lógica: o mesmo arquivo, dois
discos diferentes.

Arrancar a cura:

* devolver `warn` no lugar do `fail` do agente morto → `test_agente_morto_*`
  reprova nomeando o grau;
* devolver `rode ./install.sh` a qualquer frase → a varredura reprova nomeando
  arquivo, linha e texto.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

#: Cópia da árvore tirada uma vez por sessão (ARVORE-CONGELADA-01). Esta
#: bancada EXECUTA o `scripts/doctor.sh`; se ele mudar debaixo da medição — um
#: agente irmão, um editor salvando —, o veredito é sobre o produto de outra
#: pessoa.
RAIZ = arvore_congelada()
DOCTOR = RAIZ / "scripts" / "doctor.sh"

#: Os três ajudantes que PERGUNTAM se há checkout. Uma frase de conselho que
#: cite o instalador tem de passar por um deles — ou estar dentro do corpo de
#: um deles, que é onde o nome do arquivo pode aparecer cru.
AJUDANTES = (
    "esta_instalacao_e_um_checkout",
    "conselho_de_instalacao",
    "so_no_checkout",
)


# ---------------------------------------------------------------------------
# Ferramenta comum: rodar uma função do doctor de verdade, no layout escolhido
# ---------------------------------------------------------------------------


def _layout_de_pacote(tmp_path: Path) -> Path:
    """O `.deb`/Flatpak: `scripts/doctor.sh` sem `install.sh` ao lado.

    Não é uma imitação. É a mesma árvore de arquivos que o `dpkg` deixa em
    `/usr/share/hefesto-dualsense4unix/`, e é por isso que `ROOT_DIR` — que sai
    de `dirname "${BASH_SOURCE[0]}"/..` — responde a verdade sozinho.
    """
    destino = tmp_path / "pacote"
    (destino / "scripts").mkdir(parents=True)
    shutil.copy2(DOCTOR, destino / "scripts" / "doctor.sh")
    return destino / "scripts" / "doctor.sh"


def _rodar(
    doctor: Path,
    comando: str,
    *,
    ambiente: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """`source` do doctor (sem rodar o `main`) e executa `comando`."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {comando}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            **os.environ,
            "DOCTOR_SH": str(doctor),
            **(ambiente or {}),
        },
    )


# ---------------------------------------------------------------------------
# (1) O GRAU — o agente morto para o pareamento, e isso não é aviso
# ---------------------------------------------------------------------------

_CONFIRM = "[General]\nFastConnectable=true\nJustWorksRepairing=confirm\n"


def _cena_do_agente(
    tmp_path: Path, *, agente: str
) -> subprocess.CompletedProcess[str]:
    """`JustWorksRepairing=confirm` no disco e o agente no estado pedido.

    O `systemctl` de mentira responde SÓ ao `is-active` e cala no resto — de
    propósito: é o caso que já custou um falso positivo nesta função (o
    `date -d ""` que devolve meia-noite em vez de falhar), e calar mantém o
    aviso de relógio fora do caminho desta medição.
    """
    etc = tmp_path / "bluetooth"
    etc.mkdir(exist_ok=True)
    (etc / "main.conf").write_text(_CONFIRM, encoding="utf-8")

    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    (binario / "systemctl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "is-active" ]]; then\n'
        f'    printf "{agente}\\n"\n'
        f'    [[ "{agente}" == "active" ]] || exit 3\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (binario / "systemctl").chmod(0o755)

    return _rodar(
        DOCTOR,
        "check_bluez_justworks_repairing; "
        "printf 'RESUMO fails=%s warns=%s\\n' \"${FAILS}\" \"${WARNS}\"",
        ambiente={
            "HEFESTO_BT_ETC": str(etc),
            "HEFESTO_BT_ASSETS": str(RAIZ / "assets" / "bluetooth"),
            "PATH": f"{binario}:{os.environ.get('PATH', '')}",
            # Os marcadores de sandbox apontam para caminhos que NÃO EXISTEM:
            # a bancada roda fora de container, e um teste que dependesse do
            # `/.flatpak-info` da máquina seria outro teste a cada máquina.
            "HEFESTO_MARCA_SANDBOX": str(tmp_path / "sem-flatpak-info"),
            "HEFESTO_MARCA_CONTAINER": str(tmp_path / "sem-containerenv"),
            "FLATPAK_ID": "",
            "SNAP": "",
        },
    )


class TestOAgenteMortoNaoEUmAviso:
    """A cena que a BG-06 veio reclassificar."""

    def test_agente_morto_com_confirm_reprova(self, tmp_path: Path) -> None:
        """A mordida do defeito (1), na forma mais curta.

        Trocar o `fail` de volta por `warn` faz esta asserção cair, e a
        mensagem de falha diz exatamente o que voltou a ser tolerado.
        """
        proc = _cena_do_agente(tmp_path, agente="inactive")

        assert "[FAIL]" in proc.stdout, (
            "com JustWorksRepairing=confirm e o hefesto-bt-agent.service morto "
            "o exame voltou a AVISAR em vez de reprovar. Nenhum controle entra "
            "por rádio nesse estado, e um aviso no meio de centenas some.\n"
            f"Saída: {proc.stdout}"
        )
        assert "RESUMO fails=1" in proc.stdout

    def test_a_frase_diz_o_que_parou_e_o_que_fazer(self, tmp_path: Path) -> None:
        """Regra desta casa: o quê, por quê e o que fazer — nas três partes.

        Sem esta asserção, um `fail "agente inativo"` seco passaria: o grau
        estaria certo e a pessoa continuaria sem saber que o pareamento é o
        que parou.
        """
        proc = _cena_do_agente(tmp_path, agente="inactive")

        assert "pareamento" in proc.stdout, "não diz O QUE parou"
        assert "RECUSA" in proc.stdout, "não diz POR QUE parou (o BlueZ recusa)"
        assert "hefesto-bt-agent.service" in proc.stdout, "não nomeia o culpado"
        assert "systemctl enable --now hefesto-bt-agent.service" in proc.stdout, (
            "não diz O QUE FAZER"
        )

    def test_o_estado_do_agente_entra_na_frase(self, tmp_path: Path) -> None:
        """`inativo` e `ausente` são diagnósticos diferentes, e a frase mostra.

        A régua sabe RECUSAR: com o `systemctl` respondendo `failed`, a
        palavra que aparece é `failed`, não um genérico.
        """
        proc = _cena_do_agente(tmp_path, agente="failed")

        assert "failed" in proc.stdout, (
            f"a frase perdeu o estado real da unit: {proc.stdout}"
        )

    def test_agente_vivo_nao_reprova(self, tmp_path: Path) -> None:
        """A contraprova, sem a qual um `fail` incondicional passaria.

        Com o agente ativo o valor está certo E a dependência está de pé: o
        exame aprova e não gasta nem um aviso.
        """
        proc = _cena_do_agente(tmp_path, agente="active")

        assert "[ OK ]" in proc.stdout
        assert "RESUMO fails=0 warns=0" in proc.stdout, (
            f"o exame passou a reclamar de uma cena SÃ: {proc.stdout}"
        )


# ---------------------------------------------------------------------------
# (2) A VARREDURA — nenhuma frase manda rodar o que não está na máquina
# ---------------------------------------------------------------------------


def _faixas_dos_ajudantes(linhas: list[str]) -> set[int]:
    """As linhas DENTRO do corpo dos três ajudantes (índices 0-based).

    É lá — e só lá — que o nome do instalador pode aparecer cru: é a cura em
    pessoa. A extração é por assinatura de função; se alguém renomear um
    ajudante, isto estoura e o arquivo inteiro fica vermelho. Renomear não é
    rota de fuga.
    """
    dentro: set[int] = set()
    for nome in AJUDANTES:
        abertura = f"{nome}() {{"
        inicios = [i for i, ln in enumerate(linhas) if ln.startswith(abertura)]
        assert len(inicios) == 1, (
            f"não achei exatamente um `{abertura}` em {DOCTOR} — o ajudante "
            "que responde pela pergunta 'há checkout?' sumiu ou foi renomeado"
        )
        inicio = inicios[0]
        fim = next(
            (j for j in range(inicio + 1, len(linhas)) if linhas[j] == "}"), None
        )
        assert fim is not None, f"o corpo de {nome}() não fecha"
        dentro.update(range(inicio, fim + 1))
    return dentro


def varrer(fonte: str) -> list[str]:
    """As frases que mandam rodar o instalador SEM perguntar se ele existe.

    Devolve `["<linha>: <texto>", ...]` — vazio quer dizer limpo.

    Comentário EXPLICA, código PINTA NA TELA: só o segundo interessa, e a
    diferença aqui se descobre pela primeira coluna não-branca (é shell, não
    há árvore sintática a consultar). `install-host-udev.sh` e `uninstall.sh`
    saem da conta antes: os dois CONTÊM `install.sh` como pedaço do nome e não
    são o instalador.
    """
    linhas = fonte.splitlines()
    dentro = _faixas_dos_ajudantes(linhas)
    suspeitas: list[str] = []
    for numero, linha in enumerate(linhas):
        texto = linha.strip()
        limpo = texto.replace("install-host-udev.sh", "").replace("uninstall.sh", "")
        if "install.sh" not in limpo or texto.startswith("#") or numero in dentro:
            continue
        if any(ajudante in texto for ajudante in AJUDANTES):
            continue
        suspeitas.append(f"{numero + 1}: {texto}")
    return suspeitas


class TestNenhumaFraseMandaAoLugarQueNaoExiste:
    """O portão da regra "sai de TODOS os lugares onde aparece"."""

    def test_o_doctor_de_hoje_esta_limpo(self) -> None:
        suspeitas = varrer(DOCTOR.read_text(encoding="utf-8"))

        assert not suspeitas, (
            "frase de conselho mandando rodar o instalador sem perguntar se "
            "esta máquina tem um:\n  "
            + "\n  ".join(suspeitas)
            + "\n\nUse `conselho_de_instalacao` (o gesto) ou `so_no_checkout` "
            "(o aparte que só serve a quem tem o repositório). Em cinco dos "
            "seis formatos deste produto esse arquivo não está na máquina."
        )

    def test_a_varredura_sabe_recusar(self) -> None:
        """Régua que só sabe passar não é régua.

        Planta a frase antiga numa CÓPIA do fonte e exige que ela seja pega,
        com o número da linha certo. Sem esta metade, uma varredura quebrada
        (um `continue` a mais, um `strip()` que come tudo) aprovaria o
        `doctor.sh` para sempre e ninguém notaria.

        A conta é o DELTA, não o total: mede o que a frase plantada acrescenta.
        Assim esta régua continua medindo A SI MESMA quando o `doctor.sh`
        estiver sujo — que é exatamente a hora em que ela precisa ser confiável,
        e o modo como uma bancada irmã já mentiu nesta casa (portões em série).

        E a frase entra no FIM, não no meio: inserir no meio empurra o número
        de todas as linhas seguintes, e um `doctor.sh` sujo apareceria no delta
        inteiro só por ter mudado de linha. Medido em 25/08/2026, arrancando a
        cura — a régua acusou duas frases onde havia uma.
        """
        original = DOCTOR.read_text(encoding="utf-8")
        antes = set(varrer(original))

        linhas = original.splitlines()
        veneno = '        warn "wrapper ausente — rode ./install.sh (sem flag)"'
        linhas.append(veneno)
        novas = [s for s in varrer("\n".join(linhas)) if s not in antes]

        assert len(novas) == 1, f"a varredura não pegou a frase plantada: {novas}"
        assert novas[0].startswith(f"{len(linhas)}: "), novas[0]
        assert "rode ./install.sh" in novas[0]

    def test_a_varredura_nao_confunde_o_reparador_com_o_instalador(self) -> None:
        """`install-host-udev.sh` CONTÉM `install.sh` — e não é ele.

        A régua sabe aceitar o que deve: sem esta guarda, as seis frases que
        dão o endereço de quem instalou por pacote seriam reprovadas por
        parecerem o defeito que elas justamente curam.
        """
        original = DOCTOR.read_text(encoding="utf-8")
        antes = set(varrer(original))
        limpo = '        warn "traga o alvo: sudo /usr/share/x/install-host-udev.sh"'

        depois = set(varrer(original + "\n" + limpo))

        assert depois == antes, f"a varredura confundiu o reparador: {depois - antes}"

    def test_os_ajudantes_sao_usados_de_verdade(self) -> None:
        """ENTREGA-QUE-NAO-LIGOU-01: ajudante vivo e nunca chamado.

        A varredura acima passaria verde num `doctor.sh` que simplesmente
        APAGASSE as trinta e três frases. Este conta as chamadas.
        """
        fonte = DOCTOR.read_text(encoding="utf-8")
        dentro = _faixas_dos_ajudantes(fonte.splitlines())
        chamadas = [
            ln
            for numero, ln in enumerate(fonte.splitlines())
            if numero not in dentro
            and not ln.strip().startswith("#")
            and ("$(conselho_de_instalacao" in ln or "$(so_no_checkout" in ln)
        ]

        assert len(chamadas) >= 30, (
            f"só {len(chamadas)} frases perguntam se há checkout; eram 33 "
            "quando a BG-06 fechou. Se alguma sumiu de propósito, ajuste este "
            "número no mesmo commit e diga por quê."
        )


# ---------------------------------------------------------------------------
# OS AJUDANTES — o que cada layout recebe
# ---------------------------------------------------------------------------


def _frase(doctor: Path, comando: str) -> str:
    proc = _rodar(doctor, comando)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


class TestOGestoQueServeParaCadaLayout:
    def test_no_checkout_o_gesto_e_o_de_sempre(self) -> None:
        """A cura não podia piorar o caso que já funcionava.

        Na máquina dela — que roda do clone — a frase tem de sair IDÊNTICA à
        de ontem, incluindo as flags que o chamador passa.
        """
        assert _frase(DOCTOR, "conselho_de_instalacao") == "rode ./install.sh"
        assert (
            _frase(DOCTOR, "conselho_de_instalacao --native")
            == "rode ./install.sh --native"
        )

    def test_fora_do_checkout_o_gesto_nao_cita_o_instalador(
        self, tmp_path: Path
    ) -> None:
        """A mordida do defeito (2), na forma mais curta.

        No layout do pacote, a frase não pode nomear um arquivo que não está
        no disco — nem com flag, que é o caso em que a tentação de citar é
        maior (a flag descreve um passo DO instalador).
        """
        pacote = _layout_de_pacote(tmp_path)

        for comando in ("conselho_de_instalacao", "conselho_de_instalacao --native"):
            frase = _frase(pacote, comando)
            assert "install.sh" not in frase, frase
            assert frase == "atualize o Hefesto pelo mesmo caminho por onde você o instalou"

    def test_o_reparador_do_pacote_so_entra_se_estiver_no_disco(
        self, tmp_path: Path
    ) -> None:
        """MEDIDO, não presumido — e é a mesma pergunta um andar abaixo.

        O `.deb`/rpm/arch leva um `install-host-udev.sh`; o Flatpak não leva
        nada em `/usr/share/hefesto-dualsense4unix`. Mandar todo mundo ao
        reparador trocaria um conselho impossível por outro. A régua sabe
        aceitar E recusar: o MESMO caminho responde diferente antes e depois
        de o arquivo existir.
        """
        pacote = _layout_de_pacote(tmp_path)
        reparador = tmp_path / "reparador.sh"

        sem = _frase(pacote, f'conselho_de_instalacao "" "{reparador}"')
        assert str(reparador) not in sem, sem
        assert sem == "atualize o Hefesto pelo mesmo caminho por onde você o instalou"

        reparador.write_text("#!/bin/bash\n", encoding="utf-8")
        com = _frase(pacote, f'conselho_de_instalacao "" "{reparador}"')
        assert com == f"rode o reparador que veio no seu pacote: sudo {reparador}"

    def test_a_ressalva_do_reparador_nao_aparece_sem_ele(
        self, tmp_path: Path
    ) -> None:
        """O reparador dos pacotes NÃO faz tudo o que o instalador faz.

        Ele traz os alvos das regras 82/83 e **não** os timers de resiliência
        — a frase que o oferece tem de dizer isso. Mas a ressalva não pode
        aparecer numa máquina que nem o reparador tem: falaria de um script
        que ninguém vai rodar. Ela anda amarrada ao ramo, não à frase.
        """
        pacote = _layout_de_pacote(tmp_path)
        reparador = tmp_path / "reparador.sh"
        ressalva = "— não traz os timers"

        sem = _frase(pacote, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert ressalva not in sem, sem

        reparador.write_text("#!/bin/bash\n", encoding="utf-8")
        com = _frase(pacote, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert com.endswith(f"sudo {reparador} {ressalva}"), com

        no_clone = _frase(DOCTOR, f'conselho_de_instalacao "" "{reparador}" "{ressalva}"')
        assert no_clone == "rode ./install.sh", (
            f"a ressalva do reparador vazou para quem tem o repositório: {no_clone}"
        )

    def test_no_checkout_o_reparador_nem_e_consultado(self, tmp_path: Path) -> None:
        """Quem tem o repositório recebe o gesto do repositório, ponto.

        Sem esta asserção, um `.deb` instalado ao lado do clone (o caso desta
        bancada de desenvolvimento) mandaria ela rodar o reparador em vez do
        instalador que ela tem na mão.
        """
        reparador = tmp_path / "reparador.sh"
        reparador.write_text("#!/bin/bash\n", encoding="utf-8")

        assert (
            _frase(DOCTOR, f'conselho_de_instalacao "" "{reparador}"')
            == "rode ./install.sh"
        )

    def test_o_aparte_de_checkout_some_fora_dele(self, tmp_path: Path) -> None:
        """`so_no_checkout` é o que mantém a tela dela intacta.

        No checkout ele devolve o texto com um espaço na frente (para colar no
        fim da frase); no pacote devolve NADA — a flag e o número do passo
        descrevem um instalador que a pessoa não tem.
        """
        pacote = _layout_de_pacote(tmp_path)

        assert _frase(DOCTOR, 'so_no_checkout "(sem flag)"') == " (sem flag)"
        assert _frase(pacote, 'so_no_checkout "(sem flag)"') == ""

    def test_a_pergunta_olha_para_um_arquivo_de_verdade(
        self, tmp_path: Path
    ) -> None:
        """Não é presunção: é a existência do arquivo no disco.

        O mesmo diretório responde diferente antes e depois de o `install.sh`
        nascer — que é o que separa esta cura de um palpite sobre o formato.
        """
        pacote = _layout_de_pacote(tmp_path)
        raiz = pacote.parent.parent

        antes = _rodar(pacote, "esta_instalacao_e_um_checkout")
        assert antes.returncode != 0

        (raiz / "install.sh").write_text("#!/bin/bash\n", encoding="utf-8")
        depois = _rodar(pacote, "esta_instalacao_e_um_checkout")
        assert depois.returncode == 0


class TestAsDuasCopiasNaoPodemDivergir:
    """DUPLICAÇÃO DECLARADA — e um portão em cima dela.

    O raciocínio já morava em `daemon_actions.py` (T-03), e a aba Sistema já o
    usava. O `doctor.sh` é shell e não importa Python: a lógica nasceu lá de
    novo. Duas cópias da mesma decisão é exatamente como duas verdades começam
    nesta casa — então elas ficam AMARRADAS por texto.

    Se alguém unificar as duas (o caminho certo, e está no relatório da BG-06),
    este teste sai junto.
    """

    def test_a_frase_de_fora_do_checkout_e_a_mesma_nos_dois_lugares(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        monkeypatch.setattr(da, "esta_instalacao_e_um_checkout", lambda: False)
        do_produto = da.como_atualizar_esta_instalacao()

        do_doctor = _frase(_layout_de_pacote(tmp_path), "conselho_de_instalacao")

        assert do_doctor == do_produto, (
            "a aba Sistema e o exame passaram a dizer coisas diferentes para a "
            f"MESMA pessoa:\n  GUI....: {do_produto!r}\n  doctor.: {do_doctor!r}"
        )

    def test_a_pergunta_e_a_mesma_nos_dois_lugares(self) -> None:
        """Os dois olham para um `install.sh` ao lado do próprio código."""
        from hefesto_dualsense4unix.app.actions import daemon_actions as da

        assert da.BASES_DE_INSTALACAO[0].name != "src"
        fonte = DOCTOR.read_text(encoding="utf-8")
        assert '[[ -f "${ROOT_DIR}/install.sh" ]]' in fonte, (
            "o doctor deixou de perguntar pelo arquivo e voltou a presumir o "
            "formato"
        )
