"""Regra-cola de udev não viaja sem o alvo do `RUN+=` dela.

As regras 82 e 83 não fazem nada sozinhas: existem só para chamar um alvo — o
`bt_nosniff_now.sh` (tira o Pro Controller genuíno do sniff no instante em que o
link nasce) e a unit de snapshot de bonds (a cura do crash do bluetoothd que
comeu 2 dos 3 pareamentos dela em 24/07). O ARQUIVO de regra viaja nos cinco
instaladores; o ALVO não viajava em nenhum.

MEDIDO em 07/08/2026, no item 9 de
`docs/process/estudos/2026-08-07-O-QUE-EXISTE-E-NAO-CHEGA-a-cobertura-do-install.md`:
o `check_packaging_parity.sh` imprimia `[OK] 82-nintendo-pro-nosniff.rules:
coberta em todos os instaladores` enquanto o `bt_nosniff_now.sh` não existia em
`build_deb.sh`, no PKGBUILD, no `.spec`, no `package.nix` nem no Flatpak. O
estudo nomeou o defeito e nomeou a ferramenta:

    "O extrator necessário JÁ EXISTE e está testado (`_alvos_run_das_regras`,
     em tests/unit/test_uninstall_simetrico_ao_install.py) — é reaproveitá-lo no
     sentido do install."

Este arquivo é esse reaproveitamento. O `uninstall.sh` já tinha a metade que
DESFAZ, com portão próprio (`test_alvo_de_regra_preservada_sai_no_mesmo_gate_da_regra`):
alvo de regra preservada sai quando a regra sai, fica quando ela fica. Aqui é a
metade que FAZ: **o alvo entra quando a regra entra**.

O CONTRATO TEM DUAS METADES, e as duas são necessárias:

1. TODA REGRA-COLA CARREGA UM `TEST==` DO PRÓPRIO ALVO. Regra sem alvo não fica
   quieta por conta própria — o udev executa o `RUN+=` e falha a cada device HID
   por Bluetooth, no journal, que é onde ninguém olha. Com o `TEST==` a regra
   órfã fica INERTE, e quem dá a notícia é o `scripts/doctor.sh`.

2. QUEM INSTALA A REGRA INSTALA O ALVO. O `TEST==` sozinho seria contorno: ele
   silencia o sintoma sem entregar a cura. As duas metades juntas é que fecham.

MORDIDAS (22/08/2026), sete, cada uma arrancada, medida e devolvida:

  - tirado o `TEST==` de UMA das duas linhas da 82 →
    `test_toda_regra_cola_carrega_o_test_do_proprio_alvo` reprovou nomeando a
    linha (a checagem é por LINHA de propósito: a 82 tem duas, uma por caixa da
    OUI, e uma delas desguarnecida basta para o defeito voltar);
  - trocado o `TEST==` da 83 pelo caminho da unit em `/etc/systemd/system` →
    `test_o_sentinela_da_regra_da_unit_e_o_execstart_dela` reprovou;
  - apagada a chamada `install_bt_resilience_host` do lado dos FORMATOS →
    `test_a_camada_do_alvo_alcanca_os_dois_lados_da_cerca` reprovou (e o portão
    geral `test_install_serve_os_dois_lados_da_cerca.py` junto);
  - devolvida ao `scripts/doctor.sh` a frase antiga ("rode ./install.sh (passo
    ONDA-R2 aplica por default)") →
    `test_o_doctor_nao_manda_repetir_o_que_ja_foi_feito` reprovou;
  - arrancado do doctor o par `83-...rules:<sentinela>` →
    `test_o_doctor_avisa_a_regra_cola_sem_alvo` reprovou.

DUAS DESSAS SETE NÃO MORDERAM DE PRIMEIRA, e é o que este arquivo tem de mais
útil para quem vier depois — a régua estava frouxa nos dois pontos onde é mais
fácil ficar:

  - apagado `bt_nosniff_now.sh` do `[1c/3]` do `scripts/install_udev.sh`: VERDE.
    A cobrança era "cita a pasta E cita o nome", e as duas metades sobreviviam
    em lugares que não instalam nada — a pasta na linha do irmão
    `bt_bonds_snapshot.sh`, o nome na lista de pre-flight que confere a ORIGEM.
    Passou a cobrar o caminho de DESTINO por extenso, e aí reprovou;
  - arrancada do `install-host-udev.sh` a gravação da unit de snapshot: VERDE.
    O mesmo arquivo IMPRIME a receita à mão para quem não tem pkexec nem sudo, e
    ela cita `/etc/systemd/system/hefesto-bt-bonds-snapshot.service` num `echo`.
    Passou a descartar `echo`/`printf`/`log`/`warn`/`info`/`die` antes de olhar
    (`_so_o_que_executa`), e aí reprovou.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.unit.test_install_serve_os_dois_lados_da_cerca import (
    alcancadas_de,
    corpos_e_topo,
    regioes,
)
from tests.unit.test_uninstall_simetrico_ao_install import _alvos_run_das_regras

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
SYSTEMD = ASSETS / "systemd"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

#: A casa dos alvos executáveis das regras — a mesma do broker root.
CASA_DOS_ALVOS = "/usr/local/lib/hefesto-dualsense4unix/"

#: Onde as units desta camada são gravadas por quem as instala.
CASA_DAS_UNITS = "/etc/systemd/system"

#: Os instaladores que podem POR A REGRA NO DISCO e, portanto, devem trazer o
#: alvo junto. `install.sh` não entra: ele não copia regra nenhuma, delega ao
#: `install_udev.sh` — e a cobertura dele é medida por alcance, no teste da
#: cerca, mais abaixo.
INSTALADORES = (
    Path("scripts/install_udev.sh"),
    Path("scripts/install-host-udev.sh"),
)


#: O que NÃO executa nada: comentário e as quatro formas de falar com quem
#: instala. Um instalador honesto CITA os caminhos nessas linhas — a receita à
#: mão para quem não tem pkexec nem sudo, o aviso de formato que não traz as
#: fontes, o resumo do que vai ser gravado.
_LINHA_QUE_NAO_EXECUTA = re.compile(r"^\s*(?:#|echo\b|printf\b|log\b|warn\b|info\b|die\b)")


def _so_o_que_executa(texto: str) -> str:
    """Descarta comentário e mensagem — sobra o que grava arquivo.

    Sem isto o portão vira decoração, e não é hipótese: MEDIDO em 22/08/2026,
    na mordida que arrancou do `install-host-udev.sh` a gravação da unit de
    snapshot. O teste ficou VERDE, porque a receita à mão que o mesmo arquivo
    imprime quando não acha pkexec nem sudo cita
    `/etc/systemd/system/hefesto-bt-bonds-snapshot.service` num `echo`. Uma
    instrução de como instalar à mão não instala nada — é a mesma armadilha do
    bloco do teclado na tela, e a mesma disciplina do `_indices_de_remocao` do
    `test_uninstall_simetrico_ao_install.py`, que exclui `log`/`printf` do lado
    que desfaz.
    """
    return "\n".join(
        linha
        for linha in texto.splitlines()
        if not _LINHA_QUE_NAO_EXECUTA.match(linha)
    )


def _execstart_da_unit(unit: str) -> str:
    """O binário do `ExecStart=` de uma unit de `assets/systemd/`."""
    caminho = SYSTEMD / unit
    assert caminho.is_file(), f"unit citada por um RUN+= e ausente de assets/systemd: {unit}"
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.startswith("ExecStart="):
            return linha.split("=", 1)[1].split()[0]
    raise AssertionError(f"{unit} não tem ExecStart= — não dá para derivar o sentinela")


def _sentinela_do_alvo(alvo: str) -> str:
    """O caminho que o `TEST==` da regra tem de conferir, para cada tipo de alvo.

    Alvo que já É um arquivo (o `bt_nosniff_now.sh` da 82) é o próprio sentinela.
    Alvo que é uma UNIT vira o `ExecStart` dela, e a escolha é medida: testar
    `/etc/systemd/system/<unit>` armaria uma armadilha para o dia em que um
    pacote entregar a unit em `/usr/lib/systemd/system` — a regra ficaria inerte
    com tudo funcionando. O `ExecStart` está soldado dentro da unit e não muda
    de lugar sem que ela mude junto.
    """
    if alvo.startswith(CASA_DOS_ALVOS):
        return alvo
    return _execstart_da_unit(alvo)


def _regras_cola() -> dict[str, set[str]]:
    return _alvos_run_das_regras()


def test_a_ferramenta_de_alvos_ainda_enxerga_as_regras_cola() -> None:
    """O caso de vacuidade: extrator quebrado aprova o arquivo inteiro.

    `_alvos_run_das_regras` é a lente por onde todo o resto deste arquivo enxerga
    `assets/`. Se ela voltar vazia — regex quebrada, pasta renomeada — os laços
    abaixo não iteram nada e o portão passa sem olhar coisa nenhuma.
    """
    achadas = _regras_cola()
    assert len(achadas) >= 2, (
        f"`_alvos_run_das_regras` achou {len(achadas)} regra(s) com RUN+= nosso: "
        f"{sorted(achadas)}.\nEram 2 em 22/08/2026 (82 e 83). Se uma regra-cola "
        "saiu de propósito, baixe o piso no mesmo commit; se não saiu, o "
        "extrator quebrou — e um portão que lê zero regras aprova qualquer coisa."
    )
    for regra, alvos in achadas.items():
        assert alvos, f"{regra} entrou na lista sem alvo nenhum — extrator quebrado"


def test_toda_regra_cola_carrega_o_test_do_proprio_alvo() -> None:
    """A checagem é por LINHA, não por arquivo.

    A 82 tem DUAS linhas de `RUN+=` — uma por caixa da OUI, porque o `HID_UNIQ`
    chega ora minúsculo ora maiúsculo. Conferir o arquivo inteiro deixaria passar
    a linha desguarnecida, e meia guarda não guarda nada: basta o controle
    conectar com a caixa da linha sem `TEST==` para o defeito voltar inteiro.
    """
    for regra, alvos in sorted(_regras_cola().items()):
        sentinelas = {_sentinela_do_alvo(alvo) for alvo in alvos}
        texto = (ASSETS / regra).read_text(encoding="utf-8")
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if "RUN+=" not in linha or linha.lstrip().startswith("#"):
                continue
            faltando = sorted(s for s in sentinelas if f'TEST=="{s}"' not in linha)
            assert not faltando, (
                f"{regra}:{numero} chama um alvo por RUN+= e não confere se ele "
                f"existe — falta {faltando} num `TEST==`.\n"
                "Sem o TEST, a regra instalada por um caminho que não trouxe o "
                "alvo NÃO fica quieta: o udev executa o RUN+= e falha a CADA "
                "device HID por Bluetooth, no journal, onde ninguém olha. Foi o "
                "estado medido em 07/08/2026 (cobertura do install, item 9).\n"
                f"A linha inteira:\n  {linha}"
            )


def test_o_sentinela_da_regra_da_unit_e_o_execstart_dela() -> None:
    """Se a unit mudar de `ExecStart`, o `TEST==` da regra tem de mudar junto.

    É o par que este arquivo existe para amarrar, aplicado à própria guarda: um
    sentinela que aponta para um caminho que a unit não usa mais deixa a regra
    inerte com a camada instalada e funcionando — pior que o defeito original,
    porque agora não há nem barulho.
    """
    for regra, alvos in sorted(_regras_cola().items()):
        texto = (ASSETS / regra).read_text(encoding="utf-8")
        for alvo in sorted(a for a in alvos if not a.startswith(CASA_DOS_ALVOS)):
            execstart = _execstart_da_unit(alvo)
            assert f'TEST=="{execstart}"' in texto, (
                f"{regra} dá start em {alvo} e o TEST== dela não confere o "
                f"ExecStart dessa unit ({execstart}).\n"
                f"Confira `assets/systemd/{alvo}`: quem mudou de lugar, o "
                "ExecStart ou o sentinela da regra?"
            )
            assert f'TEST=="{CASA_DAS_UNITS}/{alvo}"' not in texto, (
                f"{regra} confere o CAMINHO da unit em vez do ExecStart dela. "
                "Isso quebra no dia em que um pacote entregar a unit em "
                "/usr/lib/systemd/system: a regra fica inerte com tudo "
                "funcionando. O ExecStart está soldado dentro da unit."
            )


def _instaladores_que_poem_a_regra(regra: str) -> list[Path]:
    return [
        caminho
        for caminho in INSTALADORES
        if regra in _so_o_que_executa((RAIZ / caminho).read_text(encoding="utf-8"))
    ]


def test_quem_instala_a_regra_instala_o_alvo() -> None:
    """O alvo entra quando a regra entra — o espelho do gate do uninstall.

    `test_alvo_de_regra_preservada_sai_no_mesmo_gate_da_regra` já cobrava a
    metade que DESFAZ desde 31/07. A metade que FAZ ficou aberta um mês: o
    instalador copiava a regra-cola e ia embora, e a cura era um arquivo em
    /etc/udev/rules.d apontando para o nada.
    """
    for regra, alvos in sorted(_regras_cola().items()):
        instaladores = _instaladores_que_poem_a_regra(regra)
        assert instaladores, (
            f"nenhum instalador de {INSTALADORES} põe {regra} no disco — ou a "
            "regra ficou órfã de instalador, ou a lista `INSTALADORES` deste "
            "arquivo envelheceu."
        )
        # O sentinela entra na cobrança junto com o alvo: sem ele a regra fica
        # inerte, que é o mesmo resultado prático de não ter o alvo.
        exigidos = set(alvos) | {_sentinela_do_alvo(alvo) for alvo in alvos}
        for instalador in instaladores:
            texto = _so_o_que_executa((RAIZ / instalador).read_text(encoding="utf-8"))
            for exigido in sorted(exigidos):
                # O DESTINO POR EXTENSO, e não "cita a pasta e cita o nome".
                # A primeira versão desta cobrança separava as duas metades e
                # NÃO MORDEU: arrancado o `install` do `bt_nosniff_now.sh` do
                # `install_udev.sh`, o teste passou — a pasta continuava citada
                # pela linha do irmão `bt_bonds_snapshot.sh`, e o nome
                # continuava citado pela lista de pre-flight que confere a
                # ORIGEM. Duas metades verdadeiras em lugares diferentes não
                # provam uma instalação.
                caminho = (
                    exigido
                    if exigido.startswith(CASA_DOS_ALVOS)
                    else f"{CASA_DAS_UNITS}/{exigido}"
                )
                assert caminho in texto, (
                    f"{instalador} instala {regra} e não grava {caminho}.\n"
                    "Regra-cola sem alvo é enfeite: o arquivo vai para o disco, "
                    "o portão de paridade dá [OK] e a cura não existe. Foi o "
                    "achado do item 9 do estudo de 07/08/2026.\n"
                    "Se o destino passou a ser montado por variável (um laço "
                    "sobre os nomes, por exemplo), escreva-o por extenso ou "
                    "ensine esta régua a resolver a variável — mas não deixe a "
                    "cobrança cair para 'a pasta aparece em algum lugar', que "
                    "foi como esta mesma asserção nasceu sem morder."
                )


def test_a_camada_do_alvo_alcanca_os_dois_lados_da_cerca() -> None:
    """A camada ONDA-R2 inteira, não só os dois alvos, em TODO formato.

    O `install_udev.sh` e o `install-host-udev.sh` trazem o mínimo para as regras
    valerem. O resto — timers, watchdog, drop-in do bluetooth.service, restauro
    automático de bonds — é do `install.sh`, e até 22/08 o passo 3e-bis morava
    ~600 linhas ABAIXO do `exit 0` do ramo dos formatos: `--flatpak`,
    `--appimage` e `--deb` saíam sem a camada e sem uma linha dizendo isso.

    O portão geral (`test_install_serve_os_dois_lados_da_cerca.py`) pega isto
    para qualquer função `*_host`. Este aqui repete a cobrança com o nome do
    defeito, porque o dia em que alguém renomear a função para fora do sufixo
    `_host` o portão geral fica cego e este não.
    """
    corpos, _ = corpos_e_topo()
    assert "install_bt_resilience_host" in corpos, (
        "`install_bt_resilience_host` sumiu do install.sh. Se a camada ONDA-R2 "
        "voltou a ser um bloco de código de topo, ela voltou a servir um lado "
        "só da cerca — que é o defeito de 22/08/2026."
    )
    por_regiao = regioes()
    assert por_regiao, "não achei a cerca do install.sh (ver o teste da âncora)"
    for regiao, apelido in (
        ("formatos", "o lado dos FORMATOS (flatpak/appimage/deb, antes do `exit 0`)"),
        ("native", "o lado NATIVE (depois do `fi`)"),
    ):
        alcance = alcancadas_de(por_regiao[regiao], corpos) | alcancadas_de(
            por_regiao["preambulo"], corpos
        )
        assert "install_bt_resilience_host" in alcance, (
            f"a resiliência do bluetoothd não chega a {apelido}.\n"
            "Quem instala por pacote leva as regras 82 e 83 e fica sem os "
            "timers, sem o drop-in e sem o restauro automático de bonds — o "
            "crash do bluetoothd volta a comer pareamento sem cópia."
        )


def test_o_doctor_avisa_a_regra_cola_sem_alvo() -> None:
    """Inerte sem ninguém dizer é o defeito de novo, com outra cara.

    O `TEST==` compra silêncio; o silêncio só é aceitável com uma voz ao lado.
    O doctor tem de parear CADA regra-cola com o sentinela dela — na mesma
    linha, porque é o pareamento que prova que ele sabe qual alvo pertence a
    qual regra, e não que os dois nomes aparecem soltos no arquivo.
    """
    linhas = DOCTOR.read_text(encoding="utf-8").splitlines()
    for regra, alvos in sorted(_regras_cola().items()):
        sentinela = sorted({_sentinela_do_alvo(alvo) for alvo in alvos})[0]
        assert any(regra in linha and sentinela in linha for linha in linhas), (
            f"o doctor não pareia {regra} com o sentinela dela ({sentinela}).\n"
            "Sem esse par ele não sabe dizer 'a regra está instalada e o alvo "
            "não' — que é exatamente o estado que o TEST== torna silencioso."
        )


def test_o_doctor_nao_manda_repetir_o_que_ja_foi_feito() -> None:
    """A frase antiga mandava rodar o comando que não entregava.

    `warn ... rode ./install.sh (passo ONDA-R2 aplica por default)` era falsa
    para quem chegava ali: até 22/08 o 3e-bis ficava do lado errado da cerca, e
    quem instalou por `--flatpak`/`--appimage`/`--deb` tinha rodado o install e
    saído sem a camada. Mandar repetir gasta o tempo da pessoa e ainda a
    convence de que o problema é ela.

    Este teste morde só TEXTO, e é declarado como tal: prova que a mensagem
    conhece os dois endereços, não que algum deles funciona.
    """
    texto = DOCTOR.read_text(encoding="utf-8")
    aviso = next(
        (
            linha
            for linha in texto.splitlines()
            if "warn " in linha and "resiliência do bluetoothd não instalada" in linha
        ),
        None,
    )
    assert aviso is not None, (
        "não achei o aviso de resiliência do bluetoothd não instalada no doctor "
        "— se ele mudou de texto, atualize este teste no mesmo commit."
    )
    assert re.search(r"passo ONDA-R2 aplica por default", aviso) is None, (
        "o doctor voltou a mandar simplesmente 'rode ./install.sh (passo "
        "ONDA-R2 aplica por default)'. Diga TAMBÉM o caminho de quem instalou "
        f"por pacote e não tem checkout.\n  {aviso}"
    )
    assert "install-host-udev.sh" in aviso, (
        "o aviso não dá o endereço de quem instalou por pacote .deb/rpm/arch "
        f"(`install-host-udev.sh`), que é justamente quem não tem ./install.sh "
        f"à mão.\n  {aviso}"
    )
