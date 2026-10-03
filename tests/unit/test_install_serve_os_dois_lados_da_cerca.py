"""Toda cura de HOST do `install.sh` alcança os DOIS lados do `exit 0`."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
LIB = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"

ABERTURA_DA_CERCA = 'if [[ "${FORMAT}" != "native" ]]; then'

PISO_DE_FUNCOES = 7

SERVE_UM_LADO_SO: dict[str, str] = {}

_DEF_DE_UMA_LINHA = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{.*\}\s*$")
_DEF_QUE_ABRE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{\s*$")
_HELPER_EXECUTADO = re.compile(
    r"(?:^|[;&|(]|\s)(?:sudo\s+(?:-n\s+)?)?(?:bash|sh|python3?)\s+"
    r'["\']?(?:\$\{ROOT_DIR\}/|\$ROOT_DIR/)?["\']?(scripts/[\w./-]+\.(?:sh|py))'
)


def linhas_do_install() -> list[str]:
    return INSTALL.read_text(encoding="utf-8").splitlines()


def linhas_da_lib() -> list[str]:
    return LIB.read_text(encoding="utf-8").splitlines()


def _corpos(linhas: list[str]) -> tuple[dict[str, list[str]], list[bool]]:
    """O leitor de funções, sobre um arquivo qualquer."""
    corpos: dict[str, list[str]] = {}
    dentro = [False] * len(linhas)
    i = 0
    while i < len(linhas):
        de_uma_linha = _DEF_DE_UMA_LINHA.match(linhas[i])
        if de_uma_linha:
            miolo = linhas[i].split("{", 1)[1].rsplit("}", 1)[0]
            corpos[de_uma_linha.group(1)] = [miolo]
            dentro[i] = True
            i += 1
            continue
        que_abre = _DEF_QUE_ABRE.match(linhas[i])
        if que_abre:
            fim = i + 1
            while fim < len(linhas) and linhas[fim] != "}":
                fim += 1
            corpos[que_abre.group(1)] = linhas[i + 1 : fim]
            for k in range(i, min(fim + 1, len(linhas))):
                dentro[k] = True
            i = fim + 1
            continue
        i += 1
    return corpos, dentro


def corpos_das_duas_casas() -> dict[str, list[str]]:
    """Os corpos do `install.sh` MAIS os da lib da camada de máquina."""
    do_install, _ = _corpos(linhas_do_install())
    da_lib, _ = _corpos(linhas_da_lib())
    repetidas = sorted(set(do_install) & set(da_lib))
    assert not repetidas, (
        f"estas funções existem NOS DOIS arquivos: {repetidas}\n"
        "Duas definições com o mesmo nome fazem a última sourceada vencer, e "
        "qual é a última muda com a ordem do `source` — o pior tipo de bug, o "
        "que depende de posição. Apague uma."
    )
    return {**do_install, **da_lib}


def corpos_e_topo() -> tuple[dict[str, list[str]], list[bool]]:
    """Separa o corpo de cada função do código de TOPO do `install.sh`."""
    return _corpos(linhas_do_install())


def regioes() -> dict[str, list[str]]:
    """As três regiões de código de TOPO, cortadas pela cerca do `exit 0`."""
    linhas = linhas_do_install()
    _, dentro = corpos_e_topo()
    abertura = next(
        (k for k, linha in enumerate(linhas) if linha.startswith(ABERTURA_DA_CERCA)),
        -1,
    )
    if abertura < 0:
        return {}
    saida = next(
        (k for k in range(abertura, len(linhas)) if linhas[k].strip() == "exit 0"),
        -1,
    )
    fechamento = next(
        (k for k in range(max(saida, abertura), len(linhas)) if linhas[k] == "fi"),
        -1,
    )
    if saida < 0 or fechamento < 0:
        return {}

    def topo(inicio: int, fim: int) -> list[str]:
        return [linhas[k] for k in range(inicio, fim) if not dentro[k]]

    return {
        "preambulo": topo(0, abertura),
        "formatos": topo(abertura, saida + 1),
        "native": topo(fechamento + 1, len(linhas)),
    }


def sem_comentario(linhas: list[str]) -> str:
    """Junta as linhas descartando as que são só comentário."""
    return "\n".join(linha for linha in linhas if not linha.strip().startswith("#"))


_ABERTURA_DE_COMANDO = (
    r"(?:^|[;&|()]|\b(?:then|else|elif|do|if|while|until)\b|\{)"
    r"\s*(?:!\s*)*(?:sudo\s+(?:-n\s+)?)?"
)


def chamadas_diretas(linhas: list[str], conhecidas: set[str]) -> set[str]:
    """As funções conhecidas invocadas em POSIÇÃO DE COMANDO nestas linhas."""
    achadas = set()
    linhas_uteis = sem_comentario(linhas).split("\n")
    for nome in conhecidas:
        padrao = _ABERTURA_DE_COMANDO + re.escape(nome) + r"(?![\w.-])"
        if any(re.search(padrao, linha) for linha in linhas_uteis):
            achadas.add(nome)
    return achadas


def alcancadas_de(linhas: list[str], corpos: dict[str, list[str]]) -> set[str]:
    """Fecho transitivo das funções alcançáveis a partir destas linhas."""
    vistas: set[str] = set()
    pilha = list(chamadas_diretas(linhas, set(corpos)))
    while pilha:
        atual = pilha.pop()
        if atual in vistas:
            continue
        vistas.add(atual)
        pilha.extend(chamadas_diretas(corpos.get(atual, []), set(corpos)))
    return vistas


def helpers_executados(linhas: list[str]) -> set[str]:
    return set(_HELPER_EXECUTADO.findall(sem_comentario(linhas)))


def helpers_do_fecho(nomes: set[str], corpos: dict[str, list[str]]) -> set[str]:
    achados: set[str] = set()
    for nome in nomes:
        achados |= helpers_executados(corpos.get(nome, []))
    return achados


def curas_de_host() -> list[str]:
    """As funções `*_host` do `install.sh`, derivadas do arquivo."""
    return sorted(
        nome for nome in corpos_das_duas_casas() if nome.endswith("_host")
    )


def test_a_ancora_da_cerca_continua_de_pe() -> None:
    """Sem esta trava, uma reescrita do `install.sh` desligaria tudo calada."""
    achadas = regioes()
    assert achadas, (
        f"não achei a cerca do install.sh (`{ABERTURA_DA_CERCA}`, o `exit 0` "
        "do ramo dos formatos e o `fi` que o fecha).\n"
        "Se a bifurcação MUDOU DE FORMA, conserte `ABERTURA_DA_CERCA` e "
        "`regioes()` neste arquivo — sem elas todos os testes daqui passam "
        "sem olhar nada."
    )
    assert all(achadas[regiao] for regiao in ("preambulo", "formatos", "native")), (
        f"alguma região da cerca saiu vazia: "
        f"{ {regiao: len(ls) for regiao, ls in achadas.items()} }"
    )


def test_a_lista_de_curas_de_host_nao_encolheu() -> None:
    """Trava contra parser quebrado: lista derivada vazia passa por vacuidade."""
    achadas = curas_de_host()
    assert len(achadas) >= PISO_DE_FUNCOES, (
        f"achei {len(achadas)} funções `*_host` no install.sh, piso "
        f"{PISO_DE_FUNCOES}: {achadas}\n"
        "Se uma cura de host FOI EMBORA de propósito, baixe o piso no mesmo "
        "commit. Se não foi, o leitor de funções deste arquivo quebrou — e um "
        "portão que lê zero funções aprova qualquer coisa."
    )


def test_toda_cura_de_host_alcanca_os_dois_lados() -> None:
    corpos = corpos_das_duas_casas()
    por_regiao = regioes()
    alcance = {
        regiao: alcancadas_de(linhas, corpos) for regiao, linhas in por_regiao.items()
    }
    helpers_por_regiao = {
        regiao: helpers_do_fecho(alcance[regiao], corpos) | helpers_executados(linhas)
        for regiao, linhas in por_regiao.items()
    }

    for cura in curas_de_host():
        if cura in SERVE_UM_LADO_SO:
            continue
        if cura in alcance["preambulo"]:
            continue

        proprios = helpers_do_fecho({cura}, corpos)
        faltando = []
        for regiao, apelido in (
            ("formatos", "o lado dos FORMATOS (flatpak/appimage/deb, antes do `exit 0`)"),
            ("native", "o lado NATIVE (depois do `fi`)"),
        ):
            if cura in alcance[regiao]:
                continue
            if proprios and proprios <= helpers_por_regiao[regiao]:
                continue
            faltando.append(apelido)

        assert not faltando, (
            f"`{cura}` é cura de HOST e não chega a todos os formatos.\n"
            + "".join(f"  falta em {lado}\n" for lado in faltando)
            + f"  helpers que ela executa: {sorted(proprios) or 'nenhum'}\n"
            "FAÇA UMA das três:\n"
            f"  1. CHAME `{cura}` também do lado que falta — é o conserto do "
            "achado #7 da Onda S, do TECLADO-QUE-NAO-DIGITA-01 e do "
            "MIC-EM-TODO-FORMATO-01, todos o mesmo defeito;\n"
            "  2. MOVA a chamada para o preâmbulo comum, antes da cerca, se ela "
            "serve a todo formato de qualquer jeito — mas cuidado: chamada "
            "dentro de `format_flatpak`/`format_appimage` NÃO é preâmbulo, é o "
            "lado dos formatos;\n"
            "  3. DECLARE em `SERVE_UM_LADO_SO`, com data e com o motivo de o "
            "outro lado não precisar dela.\n"
            "Quem instala pelo .deb tem o mesmo aparelho que quem instala do "
            "fonte."
        )


def test_a_lista_de_lacunas_nao_envelhece_calada() -> None:
    """Sem isto, `SERVE_UM_LADO_SO` vira o lugar onde se esconde o que incomoda."""
    derivadas = curas_de_host()
    for chave, razao in SERVE_UM_LADO_SO.items():
        assert chave in derivadas, (
            f"{chave!r} está declarada como cura de um lado só e nem existe "
            "mais no install.sh — APAGUE a entrada."
        )
        assert len(razao) > 120, (
            f"a razão de {chave!r} não diz por que o outro lado dispensa a "
            f"cura: {razao!r}"
        )
        assert re.search(r"\d{2}/\d{2}/\d{4}", razao), (
            f"a lacuna {chave!r} não tem data. Sem data ninguém sabe se ela "
            "envelheceu — e uma lacuna sem idade vira paisagem."
        )


CURA_DE_MENTIRA = "install_exemplo_host"


def test_a_regua_enxerga_a_chamada_dentro_de_um_if() -> None:
    """`if minha_cura; then` é a forma idiomática, e era invisível."""
    linhas = [f"    if {CURA_DE_MENTIRA}; then", '        ok "instalado"', "    fi"]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == {CURA_DE_MENTIRA}


def test_a_regua_enxerga_a_chamada_negada_e_nos_lacos() -> None:
    """As outras quatro formas que faltavam: `if !`, `elif`, `while`, `until`."""
    for linha in (
        f"    if ! {CURA_DE_MENTIRA}; then",
        f"    elif {CURA_DE_MENTIRA}; then",
        f"    while {CURA_DE_MENTIRA}; do",
        f"    until {CURA_DE_MENTIRA}; do",
        f"    ! {CURA_DE_MENTIRA}",
        f"    if ! sudo {CURA_DE_MENTIRA}; then",
    ):
        assert chamadas_diretas([linha], {CURA_DE_MENTIRA}) == {CURA_DE_MENTIRA}, (
            f"a régua não enxergou a chamada em {linha!r} — a lista de "
            "aberturas de `_ABERTURA_DE_COMANDO` voltou a ficar incompleta."
        )


def test_a_regua_continua_cega_ao_nome_que_e_so_texto() -> None:
    """O outro lado: alargar a lista não pode virar "o nome aparece"."""
    for linha in (
        f'    warn "se falhar, rode {CURA_DE_MENTIRA} à mão"',
        f"    # se falhar, rode {CURA_DE_MENTIRA}",
        f'    echo "pulei o {CURA_DE_MENTIRA}"',
        f"    local doc={CURA_DE_MENTIRA}_doc",
    ):
        assert chamadas_diretas([linha], {CURA_DE_MENTIRA}) == set(), (
            f"a régua deu por chamada o que é só texto em {linha!r}."
        )


def test_a_regua_nao_inventa_chamada_onde_nao_ha() -> None:
    """Arrancada a chamada, a régua tem de dizer que não há. O caso de vacuidade."""
    linhas = ["    if true; then", '        ok "nada instalado"', "    fi"]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == set()


def test_a_abertura_nao_atravessa_a_quebra_de_linha() -> None:
    """A âncora por linha: um `if` lá em cima não abre um nome cá embaixo."""
    linhas = [
        '    warn "leia o manual e decida se",',
        f'          "{CURA_DE_MENTIRA} é o que você quer"',
    ]
    assert chamadas_diretas(linhas, {CURA_DE_MENTIRA}) == set()


