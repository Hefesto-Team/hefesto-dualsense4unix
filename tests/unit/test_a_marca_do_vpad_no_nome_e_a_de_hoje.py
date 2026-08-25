"""EMULACAO-UM-DONO-SO-01/E11 — a segunda regra da contagem estava morta.

O DEFEITO
==========
São DUAS as regras que separam "o nosso gamepad virtual" de "o gamepad virtual
de outro programa" na aba Emulação: o `uniq` forjado (`02:fe:…`) e a marca no
NOME. A segunda estava morta desde a BT-E-VPAD-01 (furo 1): a constante dizia
`"Hefesto Virtual"`, com docstring afirmando ser *"o nome que o vpad uhid
publica no evdev"*, e o vpad publica
`DualSense Wireless Controller (Hefesto P{n})` desde então — o nome mudou
porque jogos sob Proton casam pela substring "Wireless Controller".

**Ninguém soube porque o teste da contagem alimentava o dublê com o nome
antigo.** A contagem acertava só pela regra do `uniq`; num nó sem `uniq`
legível — que é exatamente o caso para o qual a segunda regra existe — o
produto acusaria o próprio vpad de ser de outro programa, e a suíte seguiria
verde.

POR QUE SUBSTRING, E NÃO O PREFIXO QUE A SPRINT PROPÔS
=======================================================
A sprint mandava trocar o prefixo pelo "nome de hoje". Fazer isso ao pé da
letra trocaria uma regra morta por uma regra ERRADA: o nome de hoje COMEÇA por
"DualSense Wireless Controller", que é o começo do nome que um aparelho de
verdade publica. O que só este produto escreve é `(Hefesto P` — e esta não é
uma redação nova: é a `VPAD_MARCA_NO_NOME` de `scripts/identidade_do_vpad.py`,
a régua única desta casa, cujo cabeçalho já registrava em 12/08 que *"há código
nesta casa que ainda procura o nome velho"*. Era este.

AS TRÊS PONTAS QUE ESTE PORTÃO AMARRA
======================================
1. o nome que `integrations/uhid_gamepad.py` REALMENTE publica;
2. a régua da aba (`emulation_actions._VPAD_MARCA_NO_NOME`);
3. a régua única de `scripts/identidade_do_vpad.py`.
Renomear qualquer uma das três sem as outras reprova.

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório do agente E1.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import emulation_actions as ea

_RAIZ = Path(__file__).resolve().parents[2]
_UHID = _RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "uhid_gamepad.py"
_IDENTIDADE = _RAIZ / "scripts" / "identidade_do_vpad.py"

_HID_UHID = "/devices/virtual/misc/uhid/0003:054C:0DF2.0011"
_HID_USB = "/devices/pci0000:00/0000:0d:00.3/usb1/1-4/1-4:1.0/0003:054C:0CE6.000A"


def _nome_publicado_pelo_vpad(jogador: int) -> str:
    """O nome de hoje, extraído do `return` da property `name` do vpad uhid.

    Por AST e não por instanciação: montar um `UhidGamepad` abriria
    `/dev/uhid`, e nenhum teste desta casa toca aparelho (a suíte já derrubou a
    sessão gráfica dela uma vez criando nós de verdade).
    """
    arvore = ast.parse(_UHID.read_text(encoding="utf-8"), filename=str(_UHID))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef) or no.name != "name":
            continue
        for interno in ast.walk(no):
            if isinstance(interno, ast.Return) and isinstance(
                interno.value, ast.JoinedStr
            ):
                partes = []
                for pedaco in interno.value.values:
                    if isinstance(pedaco, ast.Constant):
                        partes.append(str(pedaco.value))
                    else:
                        partes.append(str(jogador))
                return "".join(partes)
    raise AssertionError(
        "a property `name` do vpad uhid deixou de devolver uma f-string — o "
        "nome publicado mudou de forma e esta régua precisa acompanhar"
    )


def _constante_do_script(nome: str) -> str:
    """Uma constante de `scripts/identidade_do_vpad.py`, lida por AST.

    `scripts/` não é pacote importável a partir de `src/`; ler por AST evita
    mexer em `sys.path` só para conferir uma string.
    """
    arvore = ast.parse(_IDENTIDADE.read_text(encoding="utf-8"), filename=str(_IDENTIDADE))
    for no in arvore.body:
        alvos = list(no.targets) if isinstance(no, ast.Assign) else []
        if isinstance(no, ast.AnnAssign):
            alvos = [no.target]
        valor = no.value if isinstance(no, (ast.Assign, ast.AnnAssign)) else None
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and alvo.id == nome and valor is not None:
                return str(ast.literal_eval(valor))
    raise AssertionError(f"{nome} sumiu de {_IDENTIDADE.relative_to(_RAIZ)}")


def _no(dev: str, nome: str, uniq: str, sysfs: str) -> dict[str, str]:
    return {"path": dev, "name": nome, "uniq": uniq, "sys": sysfs}


# ---------------------------------------------------------------------------
# As três pontas
# ---------------------------------------------------------------------------
def test_a_marca_da_aba_esta_no_nome_que_o_vpad_publica_hoje() -> None:
    """ARRANQUE A CURA: devolva `"Hefesto Virtual"` e este caso REPROVA."""
    for jogador in (1, 2, 5):
        publicado = _nome_publicado_pelo_vpad(jogador)
        assert ea._VPAD_MARCA_NO_NOME in publicado, (
            f"a aba procura {ea._VPAD_MARCA_NO_NOME!r} e o vpad publica "
            f"{publicado!r} — a segunda regra da contagem não casa com nada"
        )


def test_a_marca_e_a_mesma_da_regua_unica_da_casa() -> None:
    """Duas redações da mesma marca é uma delas envelhecendo calada."""
    do_script = _constante_do_script("VPAD_MARCA_NO_NOME")
    assert do_script == ea._VPAD_MARCA_NO_NOME


def test_a_marca_nao_casa_com_o_nome_de_um_aparelho_de_verdade() -> None:
    """O erro que a redação óbvia cometeria.

    O nome de hoje COMEÇA por "DualSense Wireless Controller". Casar por
    prefixo — que foi o que a sprint propôs — acusaria de "nosso" um DualSense
    físico por rádio, cujo nome do evdev não traz o "Sony Interactive
    Entertainment" do cabo.
    """
    for alheio in (
        "Sony Interactive Entertainment DualSense Wireless Controller",
        "DualSense Wireless Controller",
        "Wireless Controller",
        "DualSense Edge Wireless Controller",
    ):
        assert ea._VPAD_MARCA_NO_NOME not in alheio, (
            f"a marca do vpad casa com {alheio!r}, que é nome de aparelho"
        )


# ---------------------------------------------------------------------------
# A regra viva, isolada — sem `uniq`, que é para isso que ela existe
# ---------------------------------------------------------------------------
def test_sem_uniq_o_vpad_de_hoje_continua_sendo_nosso() -> None:
    """A MORDIDA que a sprint pede: arranque a regra do `uniq` e sobra o nome.

    Antes desta cura o caso reprovava — o nó era classificado como "de outro
    programa", porque o nome que ele publica não começa por "Hefesto Virtual".
    """
    nome = _nome_publicado_pelo_vpad(1)
    nos = [
        _no("/dev/input/js0", nome, "", f"{_HID_UHID}/input/input325/js0"),
        _no(
            "/dev/input/js1",
            f"{nome} Motion Sensors",
            "",
            f"{_HID_UHID}/input/input326/js1",
        ),
    ]
    assert ea.classificar_joysticks(nos) == (0, 1, 0), (
        "sem `uniq` legível, o produto deixou de reconhecer o próprio vpad"
    )


def test_o_dualsense_fisico_por_radio_nao_vira_nosso_pelo_nome() -> None:
    """BLUEZ-UHID-01: o físico de rádio mora no MESMO lugar do sysfs.

    Sem este contrapeso, ampliar a regra do nome poderia engolir o aparelho
    dela — e a aba passaria a contar zero controles físicos.
    """
    nos = [
        _no(
            "/dev/input/js0",
            "DualSense Wireless Controller",
            "a1:b2:c3:00:00:d4",
            f"{_HID_UHID}/input/input300/js0",
        ),
    ]
    assert ea.classificar_joysticks(nos) == (1, 0, 0)


def test_o_nome_antigo_nao_e_regua_de_constante_nenhuma_desta_aba() -> None:
    """Fato errado sai de todos os lugares onde AINDA É RÉGUA.

    A régua deste caso é deliberadamente estreita, e vale escrever por quê: a
    outra regra da casa manda PRESERVAR a decisão medida numa nota datada, e as
    notas desta aba precisam citar o nome antigo para explicar o que mudou.
    Proibir a string no arquivo inteiro poria as duas regras em contradição e
    apagaria a explicação. O que não pode sobreviver é o nome antigo VALENDO —
    ou seja, sendo o valor de uma constante de módulo, que é o que o produto lê.

    ARRANQUE A CURA: devolva `_VPAD_MARCA_NO_NOME = "Hefesto Virtual"` e este
    caso REPROVA nomeando a constante.
    """
    fonte = Path(ea.__file__).read_text(encoding="utf-8")
    arvore = ast.parse(fonte, filename=ea.__file__)
    vivas: list[str] = []
    for no in arvore.body:
        alvos = list(no.targets) if isinstance(no, ast.Assign) else []
        if isinstance(no, ast.AnnAssign):
            alvos = [no.target]
        valor = no.value if isinstance(no, (ast.Assign, ast.AnnAssign)) else None
        if valor is None:
            continue
        try:
            conteudo = repr(ast.literal_eval(valor))
        except (ValueError, TypeError, SyntaxError):
            continue
        if re.search(r"Hefesto Virtual", conteudo):
            nomes = [a.id for a in alvos if isinstance(a, ast.Name)]
            vivas.append(f"  linha {no.lineno}: {nomes or '<sem nome>'} = {conteudo}")
    assert not vivas, (
        "o nome que a BT-E-VPAD-01 aposentou ainda é régua viva nesta aba:\n"
        + "\n".join(vivas)
    )
