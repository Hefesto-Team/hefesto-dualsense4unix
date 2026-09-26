"""A-09-SISTEMA-EM-TRES-SECOES-01 — a aba Sistema em três seções, com menos texto.

Pedido dela, 25/09/2026: *«praticamente vamos só mudar de lugar as coisas
dessa aba»*, com o Status em três colunas, as Configurações Avançadas em
quatro, e o registro sempre à vista. <!-- noqa-acento: citação literal dela -->

O que estas réguas prendem, cada uma com a mordida escrita:

1. o Status diz o estado na pílula, com a palavra certa em cada caso — a pausa
   deixou de ter linha própria e virou o PAUSADO do Serviço;
2. a linha do Bluetooth conta adaptadores e controles no rádio, e leva à aba
   Conexões;
3. os três ligáveis acendem pelo PRODUTO, nunca pelo clique;
4. o botão do serviço é um só e tem três caras;
5. a frase do exame sai curta, com a inteira no `title`;
6. o diário sai com os endereços mascarados, nas três formas;
7. o «Copiar» copia o painel inteiro, e recusa o vazio;
8. a linha longa do registro dobra, em vez de sair pela direita.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.gui import aba_sistema as tela

pytest_plugins = ["tests.unit.test_a_09_sistema_fecha_a_paridade"]

RAIZ = Path(__file__).resolve().parents[2]
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"


def _pilula(linha: dict[str, str]) -> tuple[str, str]:
    return linha["selo"], linha["cls"]


# ---------------------------------------------------------------------------
# 1. o Status diz o estado na pílula
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("status", "estado", "esperado"), [
    ("online_systemd", {"paused": False}, ("LIGADO", "ok")),
    ("online_systemd", {"paused": True}, ("PAUSADO", "aviso")),
    ("online_avulso", {"paused": False}, ("LIGADO", "aviso")),
    ("iniciando", {}, ("LIGANDO", "aviso")),
    ("offline", {}, ("PARADO", "aviso")),
    (None, None, (tela.NAO_DEU, "nt")),
])
def test_a_pilula_do_servico_diz_o_estado(status, estado, esperado) -> None:
    """LIGADO, PAUSADO ou PARADO — e o improvisado não sai verde.

    MORDIDA: tire o ramo da pausa de `status_do_servico` — o caso pausado
    reprova dizendo LIGADO.
    """
    assert _pilula(tela.status_do_servico(status, estado)) == esperado


def test_parado_com_pausa_gravada_diz_parado_e_nao_pausado() -> None:
    """A pausa é do serviço de pé; com ele parado, a palavra é PARADO."""
    assert tela.status_do_servico("offline", {"paused": True})["selo"] == "PARADO"


@pytest.mark.parametrize(("estado", "esperado"), [
    ({"window_detect_backend": "cosmic", "window_detect_seeing": True}, "LIGADO"),
    ({"window_detect_backend": "cosmic", "window_detect_seeing": False}, "SEM VER"),
    ({"window_detect_backend": None}, "NÃO DÁ"),
    (None, tela.NAO_DEU),
])
def test_a_troca_de_perfil_diz_se_ve_a_janela(estado, esperado) -> None:
    assert tela.status_da_troca(estado)["selo"] == esperado


def test_as_quatro_linhas_na_ordem_do_desenho() -> None:
    leitura = tela.Leitura(status="online_systemd", state={"paused": False},
                           sessao="Wayland · COSMIC", adaptadores=1)
    linhas = tela.linhas_do_status(leitura)
    assert [linha["id"] for linha in linhas] == [
        "hefesto-estado", "hefesto-troca-de-perfil", "hefesto-ambiente",
        "status-bluetooth"]
    assert linhas[2]["txt"] == "Ambiente gráfico: Wayland · COSMIC"


# ---------------------------------------------------------------------------
# 2. a linha do Bluetooth
# ---------------------------------------------------------------------------
def test_o_bluetooth_conta_adaptadores_e_controles_no_radio() -> None:
    """Dois no rádio e um no cabo: a linha diz os DOIS do rádio.

    MORDIDA: conte todos os conectados em `controles_no_radio` — reprova com 3.
    """
    estado = {"controllers": [
        {"transport": "bt", "connected": True},
        {"transport": "BT"},
        {"transport": "usb", "connected": True},
        {"transport": "bt", "connected": False},
    ]}
    linha = tela.status_do_bluetooth(2, estado)
    assert linha["txt"] == "Bluetooth: 2 adaptadores · 2 controles", linha
    assert linha["href"] == tela.ENDERECO_DO_RADIO


def test_sem_adaptador_e_nota_e_nao_aviso() -> None:
    """O PC de mesa sem dongle é o caso mais comum — não é defeito."""
    linha = tela.status_do_bluetooth(0, {"controllers": []})
    assert linha["cls"] == tela.PILULA_NOTA
    assert "nenhum adaptador" in linha["txt"]


def test_a_linha_do_bluetooth_leva_a_secao_do_radio_da_aba_08() -> None:
    """O âncora existe na página da aba Conexões — o clique não cai no vazio."""
    pagina, ancora = tela.ENDERECO_DO_RADIO.split("#", 1)
    conexoes = (RAIZ / "src/hefesto_dualsense4unix/interface/paginas" / pagina)
    assert f'id="{ancora}"' in conexoes.read_text(encoding="utf-8")


def test_o_status_publicado_e_um_link_na_linha_do_bluetooth(a09) -> None:
    html = a09.linha_do_status(tela.status_do_bluetooth(1, {"controllers": []}))
    assert html.startswith('<a class="saude vai"') and 'href="08-conexoes.html#rd-secao"' in html


# ---------------------------------------------------------------------------
# 3. os três ligáveis acendem pelo produto
# ---------------------------------------------------------------------------
def test_os_tres_ligaveis_tem_o_endereco_do_produto_na_pagina() -> None:
    """Cada pílula leva gesto, `data-campo` e o alvo `classe` com `ligada`.

    MORDIDA: tire o `data-hef-alvo="classe"` da `ligavel()` no gerador e
    publique — o gerador recusa antes (régua 2), e esta reprova na publicada.
    """
    pagina = PUBLICADA.read_text(encoding="utf-8")
    for gesto, campo in (("autostart", "hefesto-autostart"),
                         ("fixar-proton", "proton-fixado"),
                         ("corrigir-vulkan", "vulkan-corrigido")):
        tag = re.search(r'<button class="cadeado[^"]*"[^>]*data-gesto="'
                        + gesto + r'"[^>]*>', pagina)
        assert tag, f"o ligável `{gesto}` sumiu da página publicada"
        assert f'data-campo="{campo}" data-hef-alvo="classe" data-hef-classe="ligada"' \
            in tag.group(0), tag.group(0)


@pytest.mark.parametrize(("conteudo", "esperado"), [
    (None, False),
    ({"tool_name": "GE-Proton10-1", "changes": {"123": ""}}, True),
    ({"tool_name": "GE-Proton10-1", "changes": {}}, False),
    ("não é json", None),
])
def test_o_proton_fixado_le_o_registro_da_trava(monkeypatch, tmp_path, conteudo,
                                                esperado) -> None:
    """Ligado é «há o que o destravar desfaria» — as mesmas chaves do dono.

    MORDIDA: faça `proton_fixado` devolver `bool(dado)` — o caso das mudanças
    vazias reprova dizendo True.
    """
    from hefesto_dualsense4unix.integrations import proton_pin
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    estado = tmp_path / "proton-lock-state.json"
    if conteudo is not None:
        estado.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo),
                          encoding="utf-8")
    monkeypatch.setattr(proton_pin, "default_lock_state_path", lambda *a, **k: estado)
    assert a09.proton_fixado() is esperado


def test_o_tique_acende_os_ligaveis_pelo_que_leu(a09, ctx, monkeypatch) -> None:
    """A pílula mente se o pacote não escrever — e escreve o que LEU.

    MORDIDA: troque `fora["vulkan-corrigido"] = vulkan_corrigido()` por `True`.
    """
    monkeypatch.setattr(a09, "_leituras_baratas", lambda: (1, "Wayland · X", False))
    a09._VULKAN.clear()
    a09._VULKAN.update(tiradas=0, postas=2, prefixos=3)
    fora = a09.pacote(ctx)
    assert fora["proton-fixado"] is False
    assert fora["vulkan-corrigido"] is False
    a09._VULKAN.update(tiradas=1)
    assert a09.pacote(ctx)["vulkan-corrigido"] is True
    a09._VULKAN.clear()


def test_desligar_o_proton_destrava_pelo_dono(a09, ctx, monkeypatch, tmp_path) -> None:
    """Ligado, o clique DESTRAVA — pelo `unlock_games_from_pinned_proton`.

    MORDIDA: faça o ramo ligado chamar o `travar` de novo — reprova com a
    trava chamada e o destravar não.
    """
    from hefesto_dualsense4unix.integrations import proton_pin

    chamou: list[str] = []
    conf = tmp_path / "proton-pin.conf"
    conf.write_text("# prova\n", encoding="utf-8")
    monkeypatch.setattr(proton_pin, "default_pin_conf_path", lambda: conf)
    monkeypatch.setattr(proton_pin, "pino_instalado_nesta_maquina", lambda: True)
    monkeypatch.setattr(proton_pin, "steam_running", lambda: False)
    monkeypatch.setattr(proton_pin, "lock_proton_for_all_games",
                        lambda **k: chamou.append("travou") or {})
    monkeypatch.setattr(proton_pin, "unlock_games_from_pinned_proton",
                        lambda **k: chamou.append("destravou") or {"status": "unlocked"})
    monkeypatch.setattr(a09, "proton_fixado", lambda: True)
    a09.fixar_proton(ctx, {}, None)
    assert chamou == ["destravou"]


# ---------------------------------------------------------------------------
# 4. o botão do serviço é um só e tem três caras
# ---------------------------------------------------------------------------
def test_o_botao_do_servico_tem_tres_caras(a09) -> None:
    """De pé diz o desenho (Parar), pausado diz Retomar, parado diz Ativar.

    MORDIDA: tire o ramo `pausado` de `_rotulo_de_agora`.
    """
    seletor = '[data-gesto="parar-ou-retomar"]'
    assert a09.blocos_dos_botoes(True)[seletor] == a09._rotulo_do_desenho(a09.DESLIGAR)
    assert a09.blocos_dos_botoes(True, pausado=True)[seletor] == a09.RETOMAR
    assert a09.blocos_dos_botoes(False)[seletor] == a09.ATIVAR


def test_o_verde_acende_quando_o_clique_devolve_o_servico(a09, ctx) -> None:
    """Verde com a pausa ativa ou parado; vazio (vermelho) com ele de pé.

    MORDIDA: emita `CAMPO_DO_VERDE` sempre vazio.
    """
    import pacotes

    assert a09.pacote(ctx)[a09.CAMPO_DO_VERDE] == ""
    pausado = pacotes.Contexto(state={**ctx.state, "paused": True}, mesa=[],
                               conectados=list(ctx.conectados), estados={})
    assert a09.pacote(pausado)[a09.CAMPO_DO_VERDE] == a09.MODO_A_CORRIGIR


# ---------------------------------------------------------------------------
# 5. a frase do exame sai curta
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("frase", "cabeca"), [
    ("quirk anti-storm ativo (054c:0ce6 — áudio USB esp)", "Quirk anti-storm ativo"),
    ("regra áudio-off inativa — o mic e o fone do controle estão liberados.",
     "Regra áudio-off inativa"),
    ("WirePlumber configurado (51-hefesto-dualsense-n)", "WirePlumber configurado"),
    ("Sobreposição Vulkan: tirada em 1 jogo · posta em 2 · 3 prefixos vistos",
     "Sobreposição Vulkan: tirada em 1 jogo · posta em 2 · 3 prefixos vistos"),
])
def test_a_cabeca_da_frase_do_exame(a09, frase, cabeca) -> None:
    assert a09.cabeca_da_frase(frase) == cabeca


def test_a_linha_do_exame_guarda_a_frase_inteira_no_title(a09) -> None:
    """A tela mostra a frase curta; quem passa o mouse lê o resto.

    MORDIDA: escreva `txt` no `<span>` em vez de `frase_curta_do_exame(txt)`.
    """
    frase = "quirk anti-storm ativo (054c:0ce6 — áudio USB esp)"
    html = a09._linha_do_exame({"cls": "ok", "g": "✓", "selo": "OK", "txt": frase})
    assert "<span>Proteção do áudio USB ligada</span>" in html, html
    assert "054c:0ce6" in html.split("<span>Proteção", 1)[0], "o title perdeu a frase inteira"


@pytest.mark.parametrize(("frase", "curta"), [
    ("quirk anti-storm ativo (054c:0ce6 — áudio USB espaçado)",
     "Proteção do áudio USB ligada"),
    ("regra áudio-off inativa — o mic e o fone do controle estão liberados.",
     "Mic e fone do controle liberados"),
    ("WirePlumber configurado (51-hefesto-dualsense-no-default-source.conf)",
     "Ajuste de áudio instalado"),
    ("Steam Input: não encontrei a Steam nesta máquina (nenhum localconfig.vdf).",
     "Steam não encontrada"),
    ("o ajuste de áudio do Hefesto não está instalado — sem ele o controle",
     "Ajuste de áudio não instalado"),
    ("cura do travamento do USB ATIVA (mic e fone do controle preservados)",
     "Cura do travamento do USB ativa"),
    # o que a tabela não conhece cai na regra da cabeça, e nunca sai inteiro
    ("áudio presente nos 2 controles no cabo (mic+fone do DualSense ativos)",
     "Áudio presente nos 2 controles no cabo"),
])
def test_a_frase_do_doctor_sai_na_lingua_de_quem_joga(a09, frase, curta) -> None:
    """Conferência de 25/09/2026: a cabeça ainda era jargão do terminal.

    MORDIDA: esvazie `FRASES_CURTAS_DO_EXAME` — «Quirk anti-storm ativo» volta.
    """
    assert a09.frase_curta_do_exame(frase) == curta


def test_cada_frase_curta_tem_o_seu_achado_no_doctor(a09) -> None:
    """O começo de cada linha da tabela existe no dono das frases.

    Uma tabela que lê uma frase que o `doctor` deixou de escrever é uma lista
    digitada que envelheceu calada: a linha da tela cairia na regra da cabeça
    sem ninguém saber. E a frase curta cabe na coluna do exame.

    MORDIDA: troque um começo da tabela por um que o `doctor` não escreve.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/integrations/storm_doctor.py"
             ).read_text(encoding="utf-8").lower()
    orfas = [c for c, _ in a09.FRASES_CURTAS_DO_EXAME if c not in fonte]
    assert not orfas, f"começos que o storm_doctor não escreve mais: {orfas}"
    longas = [f for _, f in a09.FRASES_CURTAS_DO_EXAME if len(f) > 36]
    assert not longas, f"frases curtas que não cabem na coluna: {longas}"


# ---------------------------------------------------------------------------
# 6. o diário sai mascarado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("cru", "mascarado"), [
    ("uniq=aa:bb:cc:12:34:ff ok", "uniq=aa:bb:cc:00:00:ff ok"),
    ("uniq=aabbcc1234ff rota=2", "uniq=aabbcc0000ff rota=2"),
    ("fonte=hefesto_mic_1234ff volume=54", "fonte=hefesto_mic_0000ff volume=54"),
    ("x AA-BB-CC-12-34-FF y", "x AA-BB-CC-00-00-FF y"),
    ("pid=307606 t=19:58:13.683581", "pid=307606 t=19:58:13.683581"),
])
def test_o_diario_mascara_as_tres_formas(a09, cru, mascarado) -> None:
    """MORDIDA: tire o `_MAC_COLADO` — o `uniq=` colado sai inteiro."""
    assert a09.mascarar_o_diario(cru) == mascarado


# ---------------------------------------------------------------------------
# 7. o «Copiar»
# ---------------------------------------------------------------------------
def test_copiar_leva_o_painel_inteiro(a09, ctx, monkeypatch) -> None:
    """O que vai à área de transferência é o que está no painel, inteiro.

    MORDIDA: copie só a última linha do painel.
    """
    copiado: list[str] = []
    monkeypatch.setattr(a09, "_por_na_area_de_transferencia",
                        lambda texto: copiado.append(texto) or True)
    a09._para_o_painel("linha 1\nlinha 2\nlinha 3")
    a09.copiar_registro(ctx, {}, None)
    a09._limpar_o_painel()
    assert copiado == ["linha 1\nlinha 2\nlinha 3"]


def test_copiar_recusa_o_painel_vazio(a09, ctx, monkeypatch) -> None:
    monkeypatch.setattr(a09, "_por_na_area_de_transferencia", lambda texto: True)
    monkeypatch.setattr(a09, "_faixa_lenta",
                        lambda *a, **k: (None, None, None, "online_systemd", None))
    a09._limpar_o_painel()
    with pytest.raises(RuntimeError):
        a09.copiar_registro(ctx, {}, None)


def test_o_ver_detalhes_saiu_da_pagina_e_do_contrato() -> None:
    """O registro está sempre à vista; o gesto que sobra é o de copiar."""
    pagina = PUBLICADA.read_text(encoding="utf-8")
    assert 'data-gesto="ver-detalhes"' not in pagina
    assert "ver-detalhes" not in tela.GESTOS
    assert 'data-gesto="copiar-registro"' in pagina


def test_a_linha_do_registro_dobra_e_nao_sai_pela_direita() -> None:
    """A linha do journal tem uns 200 caracteres: com `pre` ela saía cortada.

    Medido no clique do lar de mentira (25/09/2026): para ler uma linha
    inteira era preciso rolar de lado. A regra do painel na página publicada
    tem de dobrar (`pre-wrap`) e quebrar a palavra longa.
    """
    pagina = PUBLICADA.read_text(encoding="utf-8")
    regra = re.search(r"\n\s*\.log\{([^}]*)\}", pagina)
    assert regra, "a regra do painel do registro sumiu da página"
    corpo = re.sub(r"\s+", "", regra.group(1))
    assert "white-space:pre-wrap" in corpo, corpo
    assert "overflow-wrap:anywhere" in corpo, corpo


def test_o_diario_pede_so_a_linha_do_daemon(a09, monkeypatch) -> None:
    """O diário lê `--output cat`: sem o nome da máquina e sem o segundo carimbo.

    Conferência de 25/09/2026: o painel saía em `short-iso`, e cada linha
    começava com a data, o NOME DA MÁQUINA e `unidade[pid]:` antes do carimbo
    que o daemon já escreve — o «Copiar» levava o nome da máquina para o
    relato, e a linha dobrava duas vezes antes de chegar à mensagem.

    MORDIDA: volte o `--output` do `_diario` para `short-iso`.
    """
    import subprocess

    pedidos: list[list[str]] = []

    class _Saida:
        stdout = "2026-09-25T22:11:08.392690 [info     ] daemon_pronto uniq=aabbcc1234ff"
        stderr = ""

    def _run(argv, **_k):
        pedidos.append(list(argv))
        return _Saida()

    monkeypatch.setattr(subprocess, "run", _run)
    texto = a09._diario()
    assert pedidos and pedidos[0][0] == "journalctl", pedidos
    argv = pedidos[0]
    assert argv[argv.index("--output") + 1] == "cat", argv
    assert texto.endswith("uniq=aabbcc0000ff"), texto
