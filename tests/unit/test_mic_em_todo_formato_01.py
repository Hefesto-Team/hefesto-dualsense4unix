"""MIC-EM-TODO-FORMATO-01 — a voz dela ficava para trás no `exit 0` da linha 941.

O DEFEITO
=========
O `install.sh` bifurca por formato e dá `exit 0` antes do caminho nativo. Doze
passos de cura ficavam para trás, e ao longo do tempo os mais graves foram sendo
resgatados um a um — broker, DKMS do hid-nintendo, do rtw88 e do hid-playstation,
initramfs, quirk de áudio USB, e o teclado na tela (352237c).

O microfone não tinha sido. E ele é ortogonal ao formato pelo mesmo motivo que os
outros: os drop-ins do WirePlumber vivem em `~/.config/wireplumber/` — o HOME
dela, não o prefixo do pacote — e **nenhum formato os empacota** (conferido: zero
ocorrências de "wireplumber" em `packaging/` e `flatpak/`; há teste abaixo).

Instalando por `--flatpak`, `--appimage` ou `--deb`, o microfone do controle
ficava sem o **promotor** (o drop-in 51): a entrada nasce com
`priority.session = 50`, o monitor da saída ganha a eleição, e o que qualquer
aplicativo grava é o eco do que sai — não a voz dela. Foi medido em 08/08 e
curado no MONITOR-QUE-VENCE-01, mas só no caminho nativo.

A REGRA DA CASA QUE ISTO ATENDE
===============================
*"tudo tem que focar em funcionar na interface do app e no install"*, e a de
08/08: **toda cura entra no install, sem flag**. Uma cura que só existe num dos
quatro formatos não está entregue.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DONO_DO_MIC = "scripts/fix_wireplumber_default_source.sh"


def _texto() -> str:
    return INSTALL.read_text(encoding="utf-8")


def _linha_do_exit_da_bifurcacao() -> int:
    """A linha do `exit 0` que encerra o ramo dos formatos não-nativos."""
    linhas = _texto().splitlines()
    inicio = next(
        i for i, s in enumerate(linhas) if s.strip() == 'if [[ "${FORMAT}" != "native" ]]; then'
    )
    for i in range(inicio, len(linhas)):
        if linhas[i].strip() == "exit 0":
            return i + 1
    raise AssertionError("não achei o `exit 0` da bifurcação de formato")


#: Os modos do dono que DECIDEM O MICROFONE — e só eles respondem às flags
#: dela. A lista é a do `case` de `scripts/fix_wireplumber_default_source.sh`.
#: `--status` não escreve nada; `--nunca-dorme` escreve, mas sobre o
#: ALTO-FALANTE (ver `_MODOS_FORA_DO_MIC`).
_MODOS_DO_MIC = (
    "--install",
    "--disable-source",
    "--reset-only",
    "--enable-mic",
    "--promote-source",
    "--unmute-routes",
)

#: SOM-QUE-NAO-DORME-01 (16/08/2026): modos do MESMO script que não são uma
#: decisão sobre o microfone e por isso NÃO podem ficar sob flag de mic.
#: `--nunca-dorme` instala o drop-in 54, que impede o WirePlumber de suspender
#: o SINK do controle — medido na orelha dela em 15/08 23h45: com o nó
#: suspenso, o religar do hardware come o começo do som. Quem pediu
#: `--keep-dualsense-mic` pediu para não rebaixarem a ENTRADA dele; não pediu
#: para perder o início de cada efeito sonoro.
_MODOS_FORA_DO_MIC = ("--nunca-dorme",)


def _linhas_que_chamam_o_dono() -> list[int]:
    return [
        i + 1
        for i, s in enumerate(_texto().splitlines())
        if DONO_DO_MIC in s and s.strip().startswith("bash ")
    ]


def _modo_da_chamada(linha: int) -> str | None:
    """O `--modo` passado na chamada da linha 1-indexada (None se não achar)."""
    texto = _texto().splitlines()[linha - 1]
    for modo in (*_MODOS_DO_MIC, *_MODOS_FORA_DO_MIC):
        if modo in texto:
            return modo
    return None


def test_o_mic_e_curado_antes_do_exit_dos_formatos_nao_nativos() -> None:
    """A cura. Morde ao apagar o bloco do mic do ramo não-nativo.

    Arranque para ver reprovar: tirar as chamadas de
    `fix_wireplumber_default_source.sh` de antes do `exit 0`. É o estado do
    produto até 10/08/2026 — e o efeito é a voz dela perder para o eco em
    flatpak, appimage e deb.
    """
    exit_linha = _linha_do_exit_da_bifurcacao()
    chamadas = _linhas_que_chamam_o_dono()
    assert chamadas, "ninguém chama mais o dono dos drop-ins do WirePlumber"
    assert any(linha < exit_linha for linha in chamadas), (
        f"o mic só é curado depois do `exit 0` da linha {exit_linha} — "
        "flatpak/appimage/deb saem sem o promotor, e o monitor vence a voz dela"
    )


def test_o_ramo_nao_nativo_respeita_as_flags_dela() -> None:
    """A cura não pode decidir no lugar dela.

    `--keep-dualsense-mic` (que zera `WITH_WIREPLUMBER_FIX`) e
    `--with-wireplumber-disable-mic` valem em QUALQUER formato. Chamar o dono
    incondicionalmente mexeria no áudio de quem pediu para não mexer — e "a
    vontade na GUI prevalece sempre" vale também para a linha de comando.

    Morde ao trocar o `if` por uma chamada solta.

    O ESCOPO ESTREITOU EM 16/08/2026, e o motivo é um fato novo, não uma
    conveniência: até 15/08 toda chamada deste script era uma decisão sobre o
    MICROFONE, e "chamada sob flag de mic" e "chamada legítima" eram a mesma
    coisa. O `--nunca-dorme` desfez a coincidência — é o mesmo script agindo
    sobre o ALTO-FALANTE. A regra que este teste guarda sempre foi *"a decisão
    sobre o mic é dela"*, e não *"tudo que este script faz é sobre o mic"*;
    quem passa a ser aferido é o conjunto explícito `_MODOS_DO_MIC`. O irmão
    `test_a_cura_do_alto_falante_nao_fica_sob_flag_de_mic` fecha a outra ponta,
    para que estreitar aqui não vire porta aberta.
    """
    linhas = _texto().splitlines()
    exit_linha = _linha_do_exit_da_bifurcacao()
    trecho = "\n".join(linhas[:exit_linha])
    assert "WITH_WIREPLUMBER_DISABLE_MIC" in trecho
    assert "WITH_WIREPLUMBER_FIX" in trecho
    conferidas = 0
    for linha in _linhas_que_chamam_o_dono():
        if linha >= exit_linha:
            continue
        modo = _modo_da_chamada(linha)
        assert modo is not None, (
            f"a chamada da linha {linha} não passa nenhum modo conhecido de "
            f"{DONO_DO_MIC} — modo novo entra em `_MODOS_DO_MIC` ou em "
            "`_MODOS_FORA_DO_MIC`, com o porquê escrito, para não escapar "
            "destas duas travas por omissão"
        )
        if modo in _MODOS_FORA_DO_MIC:
            continue
        # A chamada tem de estar sob um `if` de flag: procura para trás a
        # condição mais próxima, dentro de poucas linhas.
        antes = "\n".join(linhas[max(0, linha - 6) : linha])
        assert re.search(r"WITH_WIREPLUMBER_(FIX|DISABLE_MIC)", antes), (
            f"a chamada da linha {linha} ({modo}) não está sob a flag dela"
        )
        conferidas += 1
    assert conferidas, (
        "nenhuma chamada de modo de MICROFONE antes do `exit 0` — se todas "
        "sumiram, é o defeito do MIC-EM-TODO-FORMATO-01 de volta; se todas "
        "viraram `_MODOS_FORA_DO_MIC`, este teste parou de aferir o que "
        "promete"
    )


def test_a_cura_do_alto_falante_nao_fica_sob_flag_de_mic() -> None:
    """SOM-QUE-NAO-DORME-01: sem flag, e nem de carona na flag de outro.

    A regra da casa de 08/08 é *toda cura entra no install, SEM FLAG*, e o
    MIC-EM-TODO-FORMATO-01 é justamente o que ela custou quando foi violada por
    acidente de POSIÇÃO. O jeito de repetir o erro aqui é fácil e parece
    arrumação: encostar a chamada do `--nunca-dorme` dentro do `if` do mic que
    vive logo abaixo dela. Ninguém veria — o install continuaria verde para
    quem não passa flag nenhuma — e quem pedisse `--keep-dualsense-mic`
    perderia o começo de cada efeito sonoro sem nunca ter pedido isso.

    Morde ao mover a chamada do `--nunca-dorme` para dentro do `if` de mic.
    """
    linhas = _texto().splitlines()
    fora = [
        linha
        for linha in _linhas_que_chamam_o_dono()
        if _modo_da_chamada(linha) in _MODOS_FORA_DO_MIC
    ]
    assert fora, (
        "ninguém mais chama o `--nunca-dorme` no install — o sink do controle "
        "volta a ser suspenso pelo WirePlumber a cada 5 s de ociosidade, e o "
        "religar do hardware come o começo do som (medido em 15/08 23h45)"
    )
    exit_linha = _linha_do_exit_da_bifurcacao()
    assert any(linha < exit_linha for linha in fora), (
        "o `--nunca-dorme` só roda depois do `exit 0` da bifurcação — "
        "flatpak/appimage/deb saem com o alto-falante dormindo. É a MESMA "
        "forma do defeito que este arquivo inteiro existe para lembrar"
    )
    for linha in fora:
        antes = "\n".join(linhas[max(0, linha - 6) : linha])
        assert not re.search(r"WITH_WIREPLUMBER_(FIX|DISABLE_MIC)", antes), (
            f"a chamada da linha {linha} caiu sob uma flag de MICROFONE — o "
            "sono do alto-falante não é uma decisão sobre o microfone, e "
            "nenhuma flag de mic pode decidir por ele"
        )


def test_as_flags_sao_definidas_antes_da_bifurcacao() -> None:
    """Guarda contra a armadilha de ORDEM em bash.

    O ramo não-nativo roda antes do grosso do arquivo. Se as flags fossem
    definidas depois, o `if` leria vazio e, sob `set -u`, o install morreria —
    trocando "microfone fraco" por "install quebrado".
    """
    linhas = _texto().splitlines()
    definicoes = [
        i + 1
        for i, s in enumerate(linhas)
        if re.match(r"^WITH_WIREPLUMBER_(FIX|DISABLE_MIC)=", s.strip())
    ]
    assert len(definicoes) >= 2, "as duas flags precisam de default"
    assert max(definicoes) < _linha_do_exit_da_bifurcacao()


def test_nenhum_formato_empacota_os_dropins_do_wireplumber() -> None:
    """A PREMISSA da cura, travada — se ela cair, a cura vira ruído.

    Este teste existe para o dia em que alguém empacotar os drop-ins: aí a
    chamada daqui passa a ser redundante no formato empacotado, e quem estiver
    lendo precisa saber que a premissa mudou. Ele NÃO reprova por a cura existir;
    reprova por a justificativa dela ter caducado em silêncio.
    """
    # As RECEITAS, não o código-fonte que mora ao lado delas. A primeira versão
    # deste teste varria `packaging/` inteiro e acusou
    # `packaging/cosmic-applet/src/app.rs` — que apenas LÊ os drop-ins para
    # desenhar o estado do microfone no applet. Ler não é empacotar, e uma régua
    # que não distingue os dois produz alarme convincente e falso, que é a
    # armadilha mais cara desta casa.
    receitas = [
        RAIZ / "packaging" / "debian" / "control",
        RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec",
        RAIZ / "packaging" / "arch" / "PKGBUILD",
        RAIZ / "packaging" / "nix" / "package.nix",
        RAIZ / "flatpak" / "br.andrefarias.Hefesto.yml",
    ]
    achados: list[str] = []
    conferidas = 0
    for caminho in receitas:
        if not caminho.is_file():
            continue
        conferidas += 1
        if "wireplumber" in caminho.read_text(encoding="utf-8", errors="ignore").lower():
            achados.append(str(caminho.relative_to(RAIZ)))
    assert conferidas >= 4, (
        "as receitas de empacotamento mudaram de caminho — este teste ficou "
        f"cego (conferiu só {conferidas})"
    )
    assert not achados, (
        "algum formato passou a empacotar drop-ins do WirePlumber: "
        f"{achados}. A premissa da MIC-EM-TODO-FORMATO-01 mudou — releia o "
        "bloco do mic no ramo não-nativo do install.sh antes de mexer."
    )


#: O drop-in PROMOTOR — quem põe a entrada do controle acima de qualquer monitor.
#: O nome aparece LITERAL em cinco superfícies que precisam concordar.
PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"

#: As cinco, e o que cada uma faz com ele.
_SUPERFICIES_DO_PROMOTOR = (
    ("scripts/fix_wireplumber_default_source.sh", "instala e mantém"),
    ("scripts/doctor.sh", "confere"),
    ("src/hefesto_dualsense4unix/app/actions/emulation_actions.py", "a janela lê"),
    ("src/hefesto_dualsense4unix/integrations/storm_doctor.py", "o diagnóstico lê"),
    ("packaging/cosmic-applet/src/app.rs", "o applet lê"),
)


def test_as_cinco_superficies_falam_do_mesmo_drop_in_promotor() -> None:
    """O nome do promotor é literal em cinco lugares e ninguém os amarrava.

    LIGAR-QUE-APAGAVA-A-CURA-01 (10/08/2026) mostrou o preço de superfícies que
    discordam sobre microfone: a janela dizia "Ligado" olhando só o 52/53
    enquanto o promotor tinha sido apagado, e o applet do COSMIC tinha o MESMO
    furo. Curados os dois no mesmo dia — e este portão existe para que a próxima
    renomeação do arquivo não deixe uma das cinco para trás em silêncio.

    É a mesma família do portão que amarra `wvkbd-mobintl`/`onboard` entre
    instalador, doctor e daemon: quando um produto escreve um caminho literal em
    N lugares, o teste é quem impede o N-ésimo de divergir.

    Morde ao trocar o nome em qualquer uma das cinco.
    """
    faltando = [
        f"{caminho} ({papel})"
        for caminho, papel in _SUPERFICIES_DO_PROMOTOR
        if PROMOTOR not in (RAIZ / caminho).read_text(encoding="utf-8", errors="ignore")
    ]
    assert not faltando, (
        f"estas superfícies não citam o promotor {PROMOTOR!r}: {faltando}. "
        "Se ele foi renomeado, as cinco têm de mudar juntas."
    )


def test_o_applet_nao_chama_de_ligado_um_mic_sem_o_promotor() -> None:
    """O applet do COSMIC tinha o mesmo furo da janela, e foi curado junto.

    Sem o promotor a entrada do controle nasce em `priority.session = 50` e o
    monitor da saída vence: o que qualquer aplicativo grava é o eco do que sai.
    Um applet tem um ícone, não três estados, então ele erra para o lado
    conservador — mas não pode afirmar "ligado".

    Morde ao devolver o `!suppressed` puro ao `mic_is_on` do Rust.
    """
    fonte = (RAIZ / "packaging/cosmic-applet/src/app.rs").read_text(encoding="utf-8")
    corpo = fonte[fonte.index("fn mic_is_on()") :]
    corpo = corpo[: corpo.index("\n}\n") + 2]
    assert PROMOTOR in corpo, "o applet decide sem olhar o promotor"
    assert "!suppressed && promoted" in corpo, (
        "o applet voltou a chamar de 'ligado' um microfone que perde para o eco"
    )
