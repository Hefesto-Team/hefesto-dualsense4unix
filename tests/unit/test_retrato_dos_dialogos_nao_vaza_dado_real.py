"""O script que fotografa os DIÁLOGOS não pode fotografar dado REAL dela.

Portão irmão do `test_retrato_das_abas_nao_vaza_dado_real`, pelo mesmo motivo
de fundo: uma foto da interface **já vazou o endereço Bluetooth real** dos
controles desta máquina, e a cura foi um borrão feito à mão. Como
`scripts/gui-captura/retratar_dialogos.py` grava direto em
`docs/usage/assets/dialogos/`, o borrão manual deixou de ser possível —
ninguém revisa PNG a cada execução, e os portões de anonimato não varrem
imagens.

O QUE MUDA EM RELAÇÃO AO IRMÃO
------------------------------

Nas abas o dado perigoso era o MAC. Aqui é o **NOME DE PERFIL**: os três
diálogos da leva recebem nome de perfil como argumento, e a tentação é ler os
perfis dela do disco (ou pedi-los ao daemon) para "deixar a foto real". Os
nomes dela não são segredo de Estado, mas são a configuração da máquina dela —
e vão para o README sem revisão.

A segurança vem da CONSTRUÇÃO: o script usa dois perfis de FÁBRICA, que já
vivem versionados em `assets/profiles_default/`. Publicá-los não conta nada
sobre máquina nenhuma, porque já estão no repositório.

**A mordida:** trocar `PERFIL_EDITADO` por um nome lido do disco dela, ou por um
literal solto na chamada do diálogo, derruba estes testes. E é exatamente o
gesto tentador — a foto ficaria "mais real", e publicaria a configuração dela.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_dialogos.py"
PERFIS_DE_FABRICA = RAIZ / "assets" / "profiles_default"

#: O que denuncia conversa com o daemon vivo. A lista é a MESMA do portão das
#: abas de propósito: cada um destes traz, no payload, MAC, nome de máquina ou
#: caminho de arquivo do computador de quem rodar.
_PORTAS_DO_DAEMON = (
    "state_full",
    "ipc_bridge",
    "_safe_call",
    "call_async",
    "daemon.status",
    "IPCClient",
    "ipc_socket_path",
)

#: O que denuncia leitura dos perfis DELA do disco. Estes diálogos falam de
#: perfil, e o perfil dela mora em `~/.config` — um `ProfileManager` aqui
#: encheria a foto com os nomes que ela usa.
_PORTAS_DO_DISCO = (
    "ProfileManager",
    "profiles.loader",
    "profiles.manager",
    "load_profiles",
    "list_profiles",
    "Path.home",
    "expanduser",
    "XDG_CONFIG_HOME",
)

#: Os argumentos dos três diálogos que carregam NOME DE PERFIL. São os que não
#: podem receber literal solto nem valor vindo de leitura.
_ARGUMENTOS_COM_NOME_DE_PERFIL = ("name", "ativado", "editando")

#: As constantes forjadas que o script declara para alimentar os diálogos.
_CONSTANTES_FORJADAS = ("PERFIL_EDITADO", "PERFIL_ATIVADO")


def _fonte() -> str:
    assert SCRIPT.is_file(), (
        f"{SCRIPT} sumiu — o retrato dos diálogos é o que fecha o aceite da "
        "PROVA-DE-TELA-01 para a leva de perfis"
    )
    return SCRIPT.read_text(encoding="utf-8")


def _arvore() -> ast.Module:
    return ast.parse(_fonte())


def _codigo_sem_prosa(arvore: ast.Module) -> str:
    """Só o CÓDIGO: docstrings e comentários ficam de fora por construção.

    O cabeçalho do script cita `daemon.state_full` e `ProfileManager` de
    propósito, para explicar o que NÃO fazer — uma varredura por texto cru
    reprovaria a própria explicação.
    """
    return "\n".join(
        ast.unparse(no)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom))
    )


def _constantes_do_modulo(arvore: ast.Module) -> dict[str, str]:
    """Os `NOME = "literal"` de nível de módulo, como dicionário."""
    achadas: dict[str, str] = {}
    for no in arvore.body:
        if not isinstance(no, ast.Assign):
            continue
        if not isinstance(no.value, ast.Constant) or not isinstance(
            no.value.value, str
        ):
            continue
        for alvo in no.targets:
            if isinstance(alvo, ast.Name):
                achadas[alvo.id] = no.value.value
    return achadas


def _perfis_de_fabrica() -> set[str]:
    return {caminho.stem for caminho in PERFIS_DE_FABRICA.glob("*.json")}


def _chamadas_de_dialogo(
    arvore: ast.Module,
) -> dict[str, list[dict[str, str]]]:
    """{nome do diálogo: [ {argumento: valor como texto}, ... ]}.

    O valor vai como TEXTO (`ast.unparse`) porque o que interessa é distinguir
    um estado do outro — `None` de `LABEL_SO_MANUAL` —, não avaliar nada.
    """
    achadas: dict[str, list[dict[str, str]]] = {}
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        if not isinstance(no.func, ast.Name):
            continue
        if not no.func.id.startswith("confirm_"):
            continue
        palavras = {
            palavra.arg: ast.unparse(palavra.value)
            for palavra in no.keywords
            if palavra.arg is not None
        }
        achadas.setdefault(no.func.id, []).append(palavras)
    return achadas


def test_o_script_nao_fala_com_o_daemon() -> None:
    """A foto não pode nascer de estado real: ela vai direto para `docs/`."""
    codigo = _codigo_sem_prosa(_arvore())

    achados = [porta for porta in _PORTAS_DO_DAEMON if porta in codigo]

    assert not achados, (
        f"o retrato dos diálogos passou a falar com o daemon "
        f"({', '.join(achados)}). O estado real carrega o MAC dos controles e "
        "os nomes de perfil dela, e estas fotos vão DIRETO para "
        "docs/usage/assets/dialogos/ — sem revisão humana e sem portão que "
        "varra imagens."
    )


def test_o_script_nao_le_os_perfis_dela_do_disco() -> None:
    """O perfil dela mora em `~/.config`, e o diálogo fala de perfil.

    É a porta específica DESTE script: as abas vazariam MAC, os diálogos
    vazariam a lista de perfis que ela mantém.
    """
    codigo = _codigo_sem_prosa(_arvore())

    achados = [porta for porta in _PORTAS_DO_DISCO if porta in codigo]

    assert not achados, (
        f"o retrato dos diálogos passou a ler perfil de disco "
        f"({', '.join(achados)}). Os nomes das fotos têm de ser os perfis de "
        "fábrica versionados em assets/profiles_default/ — eles já estão no "
        "repositório, então publicá-los não conta nada sobre a máquina dela."
    )


def test_os_nomes_fotografados_sao_perfis_de_fabrica() -> None:
    """Ancora a premissa: se a constante deixar de ser de fábrica, tudo cai.

    Este teste olha o que o script DECLARA. O de baixo confere que é isso
    mesmo que chega nos diálogos.
    """
    constantes = _constantes_do_modulo(_arvore())
    de_fabrica = _perfis_de_fabrica()

    assert de_fabrica, (
        f"{PERFIS_DE_FABRICA} não tem perfil nenhum — a premissa deste portão "
        "é que os nomes fotografados já vivem no repositório"
    )

    for nome_da_constante in _CONSTANTES_FORJADAS:
        assert nome_da_constante in constantes, (
            f"o script perdeu a constante {nome_da_constante}. Ela existe para "
            "que o nome de perfil fotografado tenha UM dono conferível."
        )
        valor = constantes[nome_da_constante]
        assert valor in de_fabrica, (
            f"{nome_da_constante} virou {valor!r}, que não é um perfil de "
            f"fábrica ({sorted(de_fabrica)}). Se este nome veio da máquina "
            "dela, a foto o publica no repositório."
        )


def test_o_nome_de_perfil_chega_ao_dialogo_pelas_constantes() -> None:
    """Nenhum literal solto de nome de perfil nas chamadas dos diálogos.

    Sem esta asserção, a anterior seria contornável sem querer: bastaria
    alguém escrever `name="o_perfil_dela"` direto na chamada e as constantes
    forjadas continuariam lá, intocadas e inúteis.
    """
    arvore = _arvore()
    problemas: list[str] = []

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        funcao = no.func
        if not isinstance(funcao, ast.Name) or not funcao.id.startswith(
            "confirm_"
        ):
            continue
        for palavra in no.keywords:
            if palavra.arg not in _ARGUMENTOS_COM_NOME_DE_PERFIL:
                continue
            valor = palavra.value
            if isinstance(valor, ast.Name) and valor.id in _CONSTANTES_FORJADAS:
                continue
            # `editando=None` é um dos estados fotografados de propósito: é o
            # caso do travessão, em que a janela não sabe o nome do rascunho.
            if isinstance(valor, ast.Constant) and valor.value is None:
                continue
            problemas.append(
                f"{funcao.id}({palavra.arg}={ast.unparse(valor)})"
            )

    assert problemas == [], (
        "estas chamadas passam nome de perfil sem ser pelas constantes "
        f"forjadas {list(_CONSTANTES_FORJADAS)}: {problemas}. Um literal solto "
        "aqui escapa do portão que confere que o nome é de fábrica."
    )


def test_o_script_fotografa_os_cinco_estados() -> None:
    """Três diálogos, CINCO estados — e a diferença é a razão da leva.

    Dois deles têm dois textos, e fotografar só um lado esconderia justamente
    o defeito curado: a frase antiga do `match_to_any` MENTIRIA num perfil
    "Só manual", e o `discard_pending_edits` sem nome mostra o travessão.
    """
    chamadas = _chamadas_de_dialogo(_arvore())

    assert len(chamadas.get("confirm_downgrade_priority", [])) == 1

    # Contar as chamadas não basta: duas chamadas IGUAIS produziriam duas fotos
    # idênticas e o portão passaria sem que o segundo estado existisse. O que
    # importa é o argumento que MUDA O TEXTO, e ele tem de aparecer nos dois
    # valores — presente e ausente.
    for funcao, argumento, motivo in (
        (
            "confirm_downgrade_match_to_any",
            "regra_atual",
            "o parâmetro nasceu porque o texto antigo MENTIRIA no perfil "
            "'Só manual' — sem as duas fotos, a cura não aparece",
        ),
        (
            "confirm_discard_pending_edits",
            "editando",
            "sem nome de rascunho o diálogo mostra o travessão, e é o estado "
            "em que a janela não pode inventar um nome",
        ),
    ):
        valores = [
            palavras.get(argumento, "AUSENTE")
            for palavras in chamadas.get(funcao, [])
        ]
        assert len(valores) == 2, (
            f"`{funcao}` tem DOIS textos e este script fotografa "
            f"{len(valores)}: {motivo}."
        )
        assert "None" in valores and any(v != "None" for v in valores), (
            f"as duas fotos de `{funcao}` usam o mesmo `{argumento}` "
            f"({valores}) — são a MESMA foto duas vezes. {motivo.capitalize()}."
        )
