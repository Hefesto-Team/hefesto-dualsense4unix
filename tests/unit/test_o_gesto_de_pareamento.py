"""PONTE-SEM-CHAMADOR-01 — o módulo Python que passou a chamar a ponte.

Até 20/09/2026 `scripts/bt_ponte_privilegiada.sh` estava instalado como root,
com `NOPASSWD` no `/etc/sudoers.d/49-hefesto-bt-ponte` e o
`hefesto-bt-agent.service` ativo — e **nenhuma linha de Python jamais chamou os
verbos `descobrir` e `parear`**. Resíduo de sudoers é o pior tipo de resíduo: é
privilégio concedido a um caminho que ninguém usa.

A RÉGUA QUE VALE É A DE PONTA A PONTA, E É A DE BAIXO
======================================================
`test_a_ponte_de_verdade_alimenta_a_janela` e
`test_o_parear_corre_dentro_da_janela_e_chama_o_pair` **não têm dublê de
processo**: o `JanelaDeBusca` dirige o `bt_ponte_privilegiada.sh` de verdade,
contra o BlueZ de mentira de `tests/unit/barramento_de_mentira.py`. É de
propósito — o emissor do TSV é o shell e o leitor é o Python, e uma régua que
dublasse o processo mediria o Python contra o Python. Foi assim que dez réguas
desta casa passaram verdes com a cura arrancada em 20/09: *o esperado era
montado com o mesmo dado que a função lia.*

O ORÁCULO DA CLASSE NÃO SAI DO CÓDIGO
======================================
`e_controle` decide pela *class of device* que o aparelho anuncia, não pelo
nome. O número contra o qual ela é medida — 9480 — foi lido na bancada em
20/09/2026 (`busctl get-property … org.bluez.Device1 Class` nos seis objetos de
DualSense do BlueZ, que também respondem `Icon` = `input-gaming`). Montar o
esperado a partir de `CLASSE_MAIOR_PERIFERICO` seria tautologia.

PROVA DE MORDIDA (20/09/2026), cada arrancada devolvida em seguida. Controle:
20 verdes neste arquivo.

  a) `mac_limpo` trocado por `partes[0].strip().lower()` em `ler_candidato`
     (aceita qualquer texto como endereço) — **1 reprovação**: `/dev/hidraw4`
     virou candidato, e o endereço aproximado iria como argumento de um comando
     privilegiado;
  b) a guarda `if not self.aberta` apagada de `parear` — **2 reprovações**: a
     ponte foi chamada com a janela já fechada, que é o `Pair()` contra um
     objeto D-Bus que o BlueZ já recolheu;
  c) `ESTADO_NINGUEM` devolvido no lugar de `ESTADO_NAO_DEU` quando a busca não
     abre — **1 reprovação**: "não consegui procurar" passaria a ser lido como
     "não havia ninguém", e a pessoa repetiria PS + Create contra uma varredura
     que nunca rodou;
  d) `e_controle` ignorando a classe MENOR (só a maior decide) — **1
     reprovação**: o teclado do usuário, que é periférico como o controle, entraria
     na lista de controles;
  e) o laço de candidatos arrancado da PONTE, do outro lado — **3 reprovações**
     aqui. É o que prova que as réguas de ponta a ponta medem o script, e não
     o dublê: um arquivo de teste só com dublê de processo ficaria verde.
"""

from __future__ import annotations

import dataclasses
import os
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations.conexao_zumbi import PedidoAPonte
from tests.unit.barramento_de_mentira import (
    ADAPTADOR,
    CLASSE_DO_DUALSENSE,
    CONTROLE,
    ICONE_DO_DUALSENSE,
    PONTE,
    VIZINHO,
    ainda_varrendo,
    ambiente,
    caminho_do,
    montar,
)

CLASSE_DO_TECLADO = 0x002540
CLASSE_DO_FONE = 0x240404
CLASSE_DO_CELULAR = 0x5A020C
CLASSE_DO_JOYSTICK = 0x002504


@pytest.fixture()
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O BlueZ de mentira da bancada — ver `tests/unit/barramento_de_mentira.py`."""
    raiz = montar(tmp_path)
    for chave in ("SUDO_UID", "SUDO_USER"):
        monkeypatch.delenv(chave, raising=False)
    for chave, valor in ambiente(raiz).items():
        if os.environ.get(chave) != valor:
            monkeypatch.setenv(chave, valor)
    return raiz


def test_a_classe_do_dualsense_medida_na_mesa_dela_e_controle() -> None:
    """9480 (0x2508) — o que os seis objetos do BlueZ responderam em 20/09."""
    assert CLASSE_DO_DUALSENSE == 9480
    assert ICONE_DO_DUALSENSE == "input-gaming"
    assert gp.e_controle(CLASSE_DO_DUALSENSE) is True


def test_o_que_nao_e_controle_fica_de_fora() -> None:
    """Fone, celular e teclado não entram na lista de controles do usuário."""
    assert gp.e_controle(CLASSE_DO_FONE) is False
    assert gp.e_controle(CLASSE_DO_CELULAR) is False
    assert gp.e_controle(CLASSE_DO_TECLADO) is False


def test_o_joystick_tambem_entra() -> None:
    """O produto atende Pro Controller e 8BitDo, que não são DualSense."""
    assert gp.e_controle(CLASSE_DO_JOYSTICK) is True


def test_sem_classe_nao_se_chuta() -> None:
    """Ausência não é dúvida a favor: chutar poria o fone da vizinha na lista."""
    assert gp.e_controle(None) is False


def test_a_linha_da_ponte_vira_candidato() -> None:
    linha = f"{CONTROLE.upper()}\tDualSense Wireless Controller\tnovo\t{CLASSE_DO_DUALSENSE}"
    candidato = gp.ler_candidato(linha)
    assert candidato is not None
    assert candidato.endereco == CONTROLE
    assert candidato.nome == "DualSense Wireless Controller"
    assert candidato.ja_pareado is False
    assert candidato.classe == CLASSE_DO_DUALSENSE
    assert candidato.e_controle is True


def test_o_que_nao_e_endereco_nao_vira_candidato() -> None:
    """O endereço vira argumento de um comando privilegiado."""
    assert gp.ler_candidato("/dev/hidraw4\tx\tnovo\t9480") is None
    assert gp.ler_candidato("") is None
    assert gp.ler_candidato("aa:bb:cc:00:00\tcurto\tnovo\t") is None
    assert gp.ler_candidato("aa:bb:cc:00:00:2z\tnao-hexa\tnovo\t") is None


def test_a_classe_vazia_nao_vira_zero() -> None:
    """Coluna vazia é `None`, e `None` não é controle. Zero seria uma classe."""
    candidato = gp.ler_candidato(f"{VIZINHO.upper()}\tfone\tpareado\t")
    assert candidato is not None
    assert candidato.classe is None
    assert candidato.e_controle is False
    assert candidato.ja_pareado is True


def test_o_endereco_inteiro_nao_vai_para_a_tela() -> None:
    """A máscara zera os octetos 4 e 5 — há portão que a cobra."""
    candidato = gp.ler_candidato("aa:bb:cc:dd:ee:ff\tx\tnovo\t")
    assert candidato is not None
    assert candidato.endereco == "aa:bb:cc:dd:ee:ff"
    assert candidato.mascara == "aa:bb:cc:00:00:ff"


def test_nao_deu_nunca_e_ninguem() -> None:
    """A linha inteira deste módulo mora aqui."""
    assert gp.Resultado(gp.ESTADO_NINGUEM, gp.FRASE_NINGUEM).deu is True
    assert gp.Resultado(gp.ESTADO_NAO_DEU, gp.FRASE_NAO_DEU).deu is False
    assert gp.Resultado(gp.ESTADO_SEM_PORTA, "").deu is False
    assert gp.FRASE_NINGUEM != gp.FRASE_NAO_DEU


def test_sem_a_ponte_instalada_o_estado_e_sem_porta(tmp_path: Path) -> None:
    """Ausência é resposta com motivo, nunca uma exceção nem uma lista vazia."""
    resultado = gp.procurar(ADAPTADOR, 1, caminho=str(tmp_path / "nao-existe.sh"))
    assert resultado.estado == gp.ESTADO_SEM_PORTA
    assert resultado.candidatos == ()
    assert "nao-existe.sh" in resultado.porque


def test_a_busca_que_nao_abre_devolve_nao_deu() -> None:
    """Erro ao abrir o processo vira estado, e o módulo não levanta."""

    def explodir(_: Any) -> Any:
        raise OSError("sem processo")

    resultado = gp.procurar(
        ADAPTADOR, 1, abrir=explodir, conferir_a_porta=False
    )
    assert resultado.estado == gp.ESTADO_NAO_DEU


def test_o_adaptador_sem_forma_de_endereco_nao_chega_ao_sudo() -> None:
    """Recusar aqui poupa um `sudo` que a ponte recusaria com código 2."""
    chamou: list[Any] = []

    def anotar(argumentos: Any) -> Any:
        chamou.append(argumentos)
        raise AssertionError("não devia ter aberto processo nenhum")

    janela = gp.JanelaDeBusca("nao-e-endereco", 1, abrir=anotar)
    assert janela.abrir_a_janela() != ""
    assert chamou == []


def _sem_sudo(pedido: PedidoAPonte) -> PedidoAPonte:
    """O único dublê: o ``sudo -n --`` sai da frente do argv, e fica ``bash <ponte> <verbo>``."""
    assert pedido.argv[:3] == ("sudo", "-n", "--"), pedido.argv
    return dataclasses.replace(pedido, argv=("bash", *pedido.argv[3:]))


def _janela_contra_a_ponte(barramento: Path, segundos: int) -> gp.JanelaDeBusca:
    """Uma `JanelaDeBusca` que dirige o script de verdade, sem `sudo`."""
    assert (barramento / "bin").is_dir()
    return gp.JanelaDeBusca(
        ADAPTADOR,
        segundos,
        caminho=str(PONTE),
        abrir=lambda pedido: gp._abrir_de_verdade(_sem_sudo(pedido)),
        correr=lambda pedido: gp._correr_de_verdade(_sem_sudo(pedido)),
    )


def test_a_ponte_de_verdade_alimenta_a_janela(barramento: Path) -> None:
    """O contrato do TSV medido dos dois lados: shell emite, Python lê."""
    janela = _janela_contra_a_ponte(barramento, 3)
    with janela:
        janela.esperar()
    achados = {c.endereco: c for c in janela.candidatos()}
    assert set(achados) == {CONTROLE, VIZINHO}, achados

    controle = achados[CONTROLE]
    assert controle.nome == "DualSense Wireless Controller"
    assert controle.classe == CLASSE_DO_DUALSENSE
    assert controle.e_controle is True
    assert controle.ja_pareado is False

    vizinho = achados[VIZINHO]
    assert vizinho.ja_pareado is True
    assert vizinho.e_controle is False

    resultado = gp.Resultado(gp.ESTADO_ACHOU, "", janela.candidatos())
    assert [c.endereco for c in resultado.controles] == [CONTROLE]


def test_o_candidato_chega_antes_de_a_janela_fechar(barramento: Path) -> None:
    """É o que torna o `parear` possível — e é o do lado do Python."""
    varrendo = barramento / "varrendo"
    janela = _janela_contra_a_ponte(barramento, 6)
    with janela:
        limite = time.monotonic() + 5.0
        while not janela.candidatos() and time.monotonic() < limite:
            time.sleep(0.05)
        ainda_varrendo = varrendo.exists()
        assert janela.candidatos(), "nenhum candidato chegou em 5 s"
        assert ainda_varrendo, (
            "o candidato só chegou com a varredura JÁ FECHADA — o BlueZ pode "
            "ter recolhido o objeto, e o `parear` não teria o que alcançar"
        )
        assert janela.aberta


def test_o_parear_corre_dentro_da_janela_e_chama_o_pair(barramento: Path) -> None:
    """O gesto composto, de ponta a ponta — e o `Pair` no caminho certo."""
    janela = _janela_contra_a_ponte(barramento, 8)
    with janela:
        limite = time.monotonic() + 6.0
        while not janela.candidatos() and time.monotonic() < limite:
            time.sleep(0.05)
        assert janela.aberta
        resultado = janela.parear(CONTROLE)
    assert resultado.estado == gp.ESTADO_PAREOU, resultado.porque

    chamadas = (barramento / "chamadas").read_text(encoding="utf-8")
    assert f"call org.bluez {caminho_do(CONTROLE)} org.bluez.Device1 Pair" in chamadas
    assert "set-property" in chamadas and "Trusted" in chamadas


def test_o_controle_ja_pareado_nao_gasta_um_pair(barramento: Path) -> None:
    """Quem já tem bond neste adaptador não precisa de PS + Create de novo."""
    janela = _janela_contra_a_ponte(barramento, 8)
    with janela:
        limite = time.monotonic() + 6.0
        while len(janela.candidatos()) < 2 and time.monotonic() < limite:
            time.sleep(0.05)
        assert janela.aberta
        resultado = janela.parear(VIZINHO)
    assert resultado.estado == gp.ESTADO_JA_PAREADO
    assert not (barramento / "chamadas").exists(), "gastou um Pair à toa"


def test_o_parear_fora_da_janela_recusa_com_motivo(barramento: Path) -> None:
    """O segundo risco da sprint, virado guarda."""
    janela = _janela_contra_a_ponte(barramento, 2)
    with janela:
        janela.esperar()
    assert not janela.aberta
    resultado = janela.parear(CONTROLE)
    assert resultado.estado == gp.ESTADO_JANELA_FECHADA
    assert not (barramento / "chamadas").exists(), "chamou a ponte fora da janela"


def test_o_pair_que_falha_vira_nao_deu_com_a_frase_do_gesto(
    barramento: Path,
) -> None:
    """Falhar é caso normal: o controle pode ter saído do modo de pareamento."""
    (barramento / "pair-recusa").write_text("", encoding="utf-8")
    janela = _janela_contra_a_ponte(barramento, 8)
    with janela:
        limite = time.monotonic() + 6.0
        while not janela.candidatos() and time.monotonic() < limite:
            time.sleep(0.05)
        assert janela.aberta
        resultado = janela.parear(CONTROLE)
    assert resultado.estado == gp.ESTADO_NAO_DEU
    assert "PS + Create" in resultado.porque


def test_fechar_derruba_a_varredura(barramento: Path) -> None:
    """Sair do `with` fecha o rádio, não só o objeto."""
    janela = _janela_contra_a_ponte(barramento, 60)
    with janela:
        limite = time.monotonic() + 5.0
        while not ainda_varrendo(barramento) and time.monotonic() < limite:
            time.sleep(0.05)
        assert ainda_varrendo(barramento), "a janela nem chegou a abrir"
    limite = time.monotonic() + 5.0
    while ainda_varrendo(barramento) and time.monotonic() < limite:
        time.sleep(0.1)
    assert not ainda_varrendo(barramento), "a varredura ficou de pé depois do fechar"


def test_a_conta_da_janela_saiu_com_a_tela_que_nao_conta() -> None:
    assert not hasattr(gp, "segundos_ate")
    assert "segundos_ate" not in gp.__all__
