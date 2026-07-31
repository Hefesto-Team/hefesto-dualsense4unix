"""O uninstall tem de saber desfazer tudo que o install faz.

O `install.sh` descobre as regras udev por glob em `assets/*.rules`; o
`uninstall.sh` traz uma lista ESCRITA À MÃO. A assimetria é silenciosa e só
aparece muito depois: quem adiciona uma regra nova ganha a instalação de graça
e esquece a remoção, e a regra fica órfã em `/etc/udev/rules.d` depois do
uninstall — mexendo no comportamento de devices de quem já desinstalou.

Foi o que aconteceu ao acrescentar `82-nintendo-pro-nosniff.rules`.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

TEXTO_UNINSTALL = UNINSTALL.read_text(encoding="utf-8")
LINHAS_UNINSTALL = TEXTO_UNINSTALL.splitlines()


def _regras_do_repo() -> set[str]:
    """Nomes das regras udev versionadas — as que o install instala por glob."""
    return {p.name for p in ASSETS.glob("[0-9][0-9]-*.rules")}


def _regras_removidas() -> set[str]:
    """Regras que o uninstall de fato APAGA.

    Só valem as citadas dentro de um `rm`: o script também IMPRIME caminhos numa
    seção "fora do escopo (não removido — não é do hefesto)", onde lista regras
    de terceiros (`50-system76-power.rules` do Pop!_OS, `99-storage-no-link-pm`
    do self-heal da usuária) para deixar claro que não encosta nelas. Casar o
    texto inteiro confundiria "avisa que preserva" com "remove".
    """
    linhas = UNINSTALL.read_text(encoding="utf-8").splitlines()
    removidas: set[str] = set()
    dentro_de_rm = False
    for linha in linhas:
        if re.search(r"\brm\b\s+-[a-zA-Z]*f", linha):
            dentro_de_rm = True
        if dentro_de_rm:
            removidas.update(
                re.findall(r"/etc/udev/rules\.d/([0-9]{2}-[\w.-]+\.rules)", linha)
            )
            # a lista continua enquanto a linha terminar em barra invertida
            if not linha.rstrip().endswith("\\"):
                dentro_de_rm = False
    return removidas


def test_uninstall_remove_toda_regra_que_o_install_instala() -> None:
    faltando = _regras_do_repo() - _regras_removidas()
    assert not faltando, (
        "regras que o install instala e o uninstall NÃO remove: "
        f"{sorted(faltando)}. Elas ficariam órfãs em /etc/udev/rules.d."
    )


def test_uninstall_nao_cita_regra_que_nao_existe_mais() -> None:
    """O espelho vale nos dois sentidos.

    Uma regra citada no uninstall que não existe mais no repo é um `rm -f` de
    caminho morto: inofensivo em execução, mas é rastro de renomeação
    incompleta e engana quem lê a lista para saber o que o projeto instala.
    """
    # Regras que o projeto já instalou no passado e removeu do repo continuam
    # na lista de propósito, para limpar quem atualizou de uma versão antiga.
    historicas = {
        "73-ps5-controller-hotplug.rules",
        "74-ps5-controller-hotplug-bt.rules",
    }

    fantasmas = _regras_removidas() - _regras_do_repo() - historicas
    assert not fantasmas, (
        f"o uninstall cita regras que não existem em assets/: {sorted(fantasmas)}. "
        "Se forem herança de versão antiga, declare-as em `historicas` com o motivo."
    )


def test_helpers_bt_instalados_sao_os_mesmos_removidos() -> None:
    """Mesma armadilha, outra lista: os scripts de resiliência do Bluetooth."""
    inst = INSTALL.read_text(encoding="utf-8")
    unin = UNINSTALL.read_text(encoding="utf-8")

    m = re.search(r"for _btres_s in ([^;]+); do", inst)
    assert m is not None, "a lista de helpers BT do install mudou de forma"
    instalados = {n for n in m.group(1).split() if n.endswith(".sh")}

    removidos = set(
        re.findall(r"/usr/local/lib/hefesto-dualsense4unix/([\w.-]+\.sh)", unin)
    )

    faltando = instalados - removidos
    assert not faltando, (
        f"helpers BT instalados e nunca removidos: {sorted(faltando)}"
    )


# ---------------------------------------------------------------------------
# As fontes que o install põe e o uninstall nunca tirava
# ---------------------------------------------------------------------------


def _invocacoes_do_removedor_de_fontes() -> list[str]:
    """Linhas que de fato EXECUTAM o removedor — não as que só o citam.

    Este filtro é a diferença entre um teste que morde e um que não morde. O
    teste gêmeo do lado do install (`test_fonte_padrao_01_e_cura_do_fix_mic.py`)
    já caiu nessa: procurar a string no arquivo inteiro fica VERDE com a chamada
    arrancada, porque o nome sobrevive no comentário do passo e na mensagem de
    erro.
    """
    invocacoes = []
    for linha in LINHAS_UNINSTALL:
        nu = linha.strip()
        if nu.startswith("#") or nu.startswith("log ") or nu.startswith("printf "):
            continue
        if "install_fonts.sh" not in nu:
            continue
        if not (nu.startswith("bash ") or " bash " in nu):
            continue
        if "--remove" not in nu and "--uninstall" not in nu:
            continue
        invocacoes.append(nu)
    return invocacoes


def test_uninstall_remove_as_fontes_que_o_install_instala() -> None:
    """O passo 4e do install grava fontes no HOME e nada as removia.

    Medido em 31/07: `grep -ci font uninstall.sh` = 3, todas em comentário sobre
    `dkms.conf`. O removedor já existia pronto (`install_fonts.sh --uninstall`,
    que apaga SÓ o diretório do projeto) e ninguém o chamava.

    Mordida: apagar a chamada deixando o nome do script num comentário tem de
    deixar este teste vermelho.
    """
    assert _invocacoes_do_removedor_de_fontes(), (
        "o uninstall voltou a não EXECUTAR o scripts/install_fonts.sh --remove — "
        "citar o nome em comentário não remove fonte nenhuma"
    )


def test_a_remocao_das_fontes_e_best_effort() -> None:
    """Fonte é acabamento: derrubar o uninstall por causa dela seria trocar um
    problema cosmético por uma desinstalação pela metade."""
    for linha in _invocacoes_do_removedor_de_fontes():
        assert "|| true" in linha, (
            f"chamada do removedor de fontes sem proteção contra `set -e`: {linha}"
        )


# ---------------------------------------------------------------------------
# --keep-udev: regra preservada não pode ficar sem o alvo do RUN+=
# ---------------------------------------------------------------------------


def _alvos_run_das_regras() -> dict[str, set[str]]:
    """Alvos do hefesto que as regras de `assets/` invocam por `RUN+=`.

    Só entram alvos NOSSOS: um `RUN+="/bin/chmod ..."` da 77 não é artefato do
    projeto e não pode ficar órfão.
    """
    alvos: dict[str, set[str]] = {}
    for regra in sorted(ASSETS.glob("[0-9][0-9]-*.rules")):
        achados: set[str] = set()
        for comando in re.findall(r'RUN\+="([^"]+)"', regra.read_text(encoding="utf-8")):
            for token in comando.split():
                if token.startswith("/usr/local/lib/hefesto-dualsense4unix/") or re.fullmatch(
                    r"hefesto-[\w.-]+\.service", token
                ):
                    achados.add(token)
        if achados:
            alvos[regra.name] = achados
    return alvos


def _indices_no_gate_do_udev() -> set[int]:
    """Índices das linhas dentro do ramo `then` de `if REMOVE_UDEV -eq 1`.

    O ramo `else` fica de fora de propósito: ele é o caminho do `--keep-udev`, e
    incluí-lo faria a dica impressa lá dentro valer como se fosse remoção.
    """
    dentro: set[int] = set()
    i = 0
    while i < len(LINHAS_UNINSTALL):
        if re.search(r'if \[\[ "\$\{REMOVE_UDEV\}" -eq 1 \]\]', LINHAS_UNINSTALL[i]):
            profundidade = 1
            j = i + 1
            while j < len(LINHAS_UNINSTALL) and profundidade > 0:
                nu = LINHAS_UNINSTALL[j].strip()
                if nu.startswith("if ") or nu.startswith("if["):
                    profundidade += 1
                elif nu == "fi":
                    profundidade -= 1
                    if profundidade == 0:
                        break
                elif nu == "else" and profundidade == 1:
                    # daqui até o `fi` é o caminho do --keep-udev
                    while j < len(LINHAS_UNINSTALL) and LINHAS_UNINSTALL[j].strip() != "fi":
                        j += 1
                    break
                dentro.add(j)
                j += 1
            i = j
        i += 1
    return dentro


def _indices_de_remocao() -> dict[int, str]:
    """Linhas que fazem parte de um comando `rm` — inclusive as continuações.

    `log`/`printf`/comentário ficam de fora: a dica impressa para quem usou
    `--keep-udev` cita os mesmos caminhos e não remove nada.
    """
    encontradas: dict[int, str] = {}
    dentro_de_rm = False
    for i, linha in enumerate(LINHAS_UNINSTALL):
        nu = linha.strip()
        if nu.startswith("#") or nu.startswith("log ") or nu.startswith("printf "):
            dentro_de_rm = False
            continue
        if re.search(r"\brm\b", nu):
            dentro_de_rm = True
        if dentro_de_rm:
            encontradas[i] = nu
            if not nu.endswith("\\"):
                dentro_de_rm = False
    return encontradas


def test_alvo_de_regra_preservada_sai_no_mesmo_gate_da_regra() -> None:
    """`--keep-udev` preservava as regras 82/83 e apagava os alvos delas.

    O bloco ONDA-R2 não consultava `REMOVE_UDEV`: as regras ficavam em
    `/etc/udev/rules.d` apontando com `RUN+=` para `bt_nosniff_now.sh` e para a
    unit de snapshot, que tinham acabado de ser removidos. O udev passa a logar
    falha de `RUN+=` a cada device HID por Bluetooth, e as duas curas morrem sem
    avisar.

    Mordida: devolver a remoção de qualquer um desses alvos para fora do gate
    (como estava até 31/07) deixa este teste vermelho.
    """
    gate = _indices_no_gate_do_udev()
    remocoes = _indices_de_remocao()
    assert gate, "não achei o gate `if [[ \"${REMOVE_UDEV}\" -eq 1 ]]` no uninstall"

    for regra, alvos in sorted(_alvos_run_das_regras().items()):
        for alvo in sorted(alvos):
            removem = {i for i, linha in remocoes.items() if alvo in linha}
            assert removem, (
                f"a regra {regra} chama {alvo} por RUN+= e o uninstall não remove "
                "esse alvo em lugar nenhum"
            )
            fora = removem - gate
            assert not fora, (
                f"{alvo} é alvo do RUN+= da regra {regra} e é removido FORA do "
                f"gate do --keep-udev (linhas {sorted(i + 1 for i in fora)}): com "
                "--keep-udev a regra fica órfã e o udev falha o RUN+= a cada "
                "device HID por Bluetooth"
            )


def _dica_do_keep_udev() -> str:
    inicio = next(
        i
        for i, linha in enumerate(LINHAS_UNINSTALL)
        if "udev rules preservadas (--keep-udev)" in linha
    )
    fim = next(
        i for i in range(inicio, len(LINHAS_UNINSTALL)) if LINHAS_UNINSTALL[i].strip() == "fi"
    )
    return "\n".join(LINHAS_UNINSTALL[inicio:fim])


def test_a_dica_do_keep_udev_cita_todas_as_regras() -> None:
    """Este morde só TEXTO, e é declarado como tal.

    A dica impressa para quem usou `--keep-udev` é a única instrução escrita de
    como limpar depois. Ela citava 70 a 81 com chaves de expansão e omitia as
    82, 83 e 84 — as três mais novas. Não prova nada sobre execução; existe para
    a dica não envelhecer de novo. Mordida: tirar uma regra da linha → vermelho.
    """
    dica = _dica_do_keep_udev()
    faltando = sorted(p.name for p in ASSETS.glob("[0-9][0-9]-*.rules") if p.name not in dica)
    assert not faltando, (
        f"regras ausentes da dica de limpeza do --keep-udev: {faltando}"
    )


def test_a_dica_do_keep_udev_cita_os_alvos_que_ficaram() -> None:
    """Quem for remover as regras depois precisa saber o que remover junto."""
    dica = _dica_do_keep_udev()
    for alvo in sorted({a for alvos in _alvos_run_das_regras().values() for a in alvos}):
        assert alvo in dica, (
            f"a dica do --keep-udev não cita o alvo preservado {alvo}"
        )


# ---------------------------------------------------------------------------
# A mensagem de erro que ensinava a rodar o desinstalador como root
# ---------------------------------------------------------------------------


def test_nenhuma_linha_sugere_rodar_o_script_inteiro_sob_sudo() -> None:
    """`sudo bash uninstall.sh` limpa o /etc e não toca no HOME real.

    Medido em 31/07 na máquina da mantenedora: `sudo printenv HOME` devolve
    `/root` (`Defaults env_reset`). O uninstall monta os alvos da usuária a
    partir de `${HOME}` — units --user, atalho, wrapper, símbolo no PATH,
    drop-ins do WirePlumber. Rodado sob sudo ele imprime "concluída" tendo
    removido metade.

    Mordida: devolver a sugestão `sudo bash $0` → vermelho.
    """
    culpadas = [
        f"{i + 1}: {linha.strip()}"
        for i, linha in enumerate(LINHAS_UNINSTALL)
        if re.search(r"sudo\s+bash\s+(\$0|\./uninstall|\"?\$\{?0)", linha)
    ]
    assert not culpadas, (
        "o uninstall voltou a sugerir rodar a si mesmo sob sudo: " + "; ".join(culpadas)
    )


# ---------------------------------------------------------------------------
# A unidade fantasma
# ---------------------------------------------------------------------------


def test_a_unit_dsx_recover_nao_existe_em_lugar_nenhum() -> None:
    """Morde só ORTOGRAFIA — e está escrito aqui de propósito.

    Decisão de 31/07: o `hefesto-dsx-recover.service` sai dos três lugares em
    que existia (o asset, os removedores do uninstall e o conselho do doctor).
    A unidade nunca foi instalada por caminho nenhum — nem o install a conhecia,
    e o `.deb` a excluía por decisão escrita — e a auditoria do storm de 26/06
    classificou a "cura" por authorized-toggle como realimentação positiva do
    próprio storm. O doctor ensinava a instalá-la à mão.

    Este teste impede o arquivo de voltar; ele não prova nada sobre execução.
    O `scripts/dsx_recover.sh` continua no repositório porque o `.deb` o
    empacota — quem sai é a UNIT.
    """
    assert not (ASSETS / "hefesto-dsx-recover.service").exists(), (
        "o asset da unidade fantasma voltou"
    )
    for arquivo in (UNINSTALL, DOCTOR, INSTALL):
        texto = arquivo.read_text(encoding="utf-8")
        assert "hefesto-dsx-recover" not in texto, (
            f"{arquivo.name} voltou a citar a unit hefesto-dsx-recover"
        )
