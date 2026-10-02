"""Regra-cola de udev não viaja sem o alvo do `RUN+=` dela."""
from __future__ import annotations

import re
from pathlib import Path

from tests.unit.test_install_serve_os_dois_lados_da_cerca import (
    alcancadas_de,
    corpos_das_duas_casas,
    regioes,
)
from tests.unit.test_uninstall_simetrico_ao_install import _alvos_run_das_regras

RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets"
SYSTEMD = ASSETS / "systemd"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

CASA_DOS_ALVOS = "/usr/local/lib/hefesto-dualsense4unix/"

CASA_DAS_UNITS = "/etc/systemd/system"

INSTALADORES = (
    Path("scripts/install_udev.sh"),
    Path("scripts/install-host-udev.sh"),
)


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
    """O caminho que o `TEST==` da regra tem de conferir, para cada tipo de alvo."""
    if alvo.startswith(CASA_DOS_ALVOS):
        return alvo
    return _execstart_da_unit(alvo)


def _regras_cola() -> dict[str, set[str]]:
    return _alvos_run_das_regras()


def test_a_ferramenta_de_alvos_ainda_enxerga_as_regras_cola() -> None:
    """O caso de vacuidade: extrator quebrado aprova o arquivo inteiro."""
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
    """A checagem é por LINHA, não por arquivo."""
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
    """Se a unit mudar de `ExecStart`, o `TEST==` da regra tem de mudar junto."""
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
    """O alvo entra quando a regra entra — o espelho do gate do uninstall."""
    for regra, alvos in sorted(_regras_cola().items()):
        instaladores = _instaladores_que_poem_a_regra(regra)
        assert instaladores, (
            f"nenhum instalador de {INSTALADORES} põe {regra} no disco — ou a "
            "regra ficou órfã de instalador, ou a lista `INSTALADORES` deste "
            "arquivo envelheceu."
        )
        exigidos = set(alvos) | {_sentinela_do_alvo(alvo) for alvo in alvos}
        for instalador in instaladores:
            texto = _so_o_que_executa((RAIZ / instalador).read_text(encoding="utf-8"))
            for exigido in sorted(exigidos):
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
    """A camada ONDA-R2 inteira, não só os dois alvos, em TODO formato."""
    corpos = corpos_das_duas_casas()
    assert "install_bt_resilience_host" in corpos, (
        "`install_bt_resilience_host` sumiu do instalador (procurei no "
        "install.sh e em scripts/lib/camada_de_maquina.sh). Se a camada "
        "ONDA-R2 voltou a ser um bloco de código de topo, ela voltou a servir "
        "um lado só da cerca — que é o defeito de 22/08/2026."
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
    """Inerte sem ninguém dizer é o defeito de novo, com outra cara."""
    linhas = DOCTOR.read_text(encoding="utf-8").splitlines()
    for regra, alvos in sorted(_regras_cola().items()):
        sentinela = sorted({_sentinela_do_alvo(alvo) for alvo in alvos})[0]
        assert any(regra in linha and sentinela in linha for linha in linhas), (
            f"o doctor não pareia {regra} com o sentinela dela ({sentinela}).\n"
            "Sem esse par ele não sabe dizer 'a regra está instalada e o alvo "
            "não' — que é exatamente o estado que o TEST== torna silencioso."
        )


def test_o_doctor_nao_manda_repetir_o_que_ja_foi_feito() -> None:
    """A frase antiga mandava rodar o comando que não entregava."""
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
