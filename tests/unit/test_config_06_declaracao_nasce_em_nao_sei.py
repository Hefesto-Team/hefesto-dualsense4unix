"""CONFIG-06 — todo campo do card nasce em "não sei", e "não sei" é resposta.

Teste PURO: nenhuma linha aqui precisa de GTK, de display ou de daemon. O que
ele guarda é a regra que a `D-A2` escreveu ao reabrir o escopo desta seção —
*"onde as quatro perguntas abertas mordem, o campo nasce em 'não sei' e a tela
diz que não sabe; nada de valor default chutado"*.

POR QUE ESTA REGRA TEM PORTÃO PRÓPRIO
--------------------------------------

Porque a casa já pagou por ela. O editor de perfis tinha um ``or "xbox"``
(``daemon/subsystems/external_mask.py:143-149``): quem nunca escolheu máscara
nenhuma recebia a de Xbox em silêncio, e a de Xbox APAGA giroscópio e touchpad.
Ninguém pediu, nada avisou, e o sintoma aparecia dentro do jogo. Um default
chutado é pior que campo vazio porque parece informação.

AS MORDIDAS, EXERCIDAS EM 22/08/2026
-------------------------------------

1. Troquei, em ``declaracoes_do_aparelho``, o ``_valor_declarado(...)`` por um
   ``_valor_declarado(...) or "xbox"``. Os três casos de
   ``test_todo_campo_nasce_sem_valor`` reprovaram, um por entrada.
2. Troquei o ``return ""`` final de ``modo_deduzido`` por ``return "dinput"``.
   ``test_modo_desconhecido_e_vazio_e_nao_um_chute`` reprovou.
3. Troquei o ``return None`` de ``chave_de_maquina`` para o endereço que começa
   em ``02`` por ``return limpo``. ``test_endereco_forjado_nao_vira_chave``
   reprovou — e essa é a mordida que importa mais: sem ela, dois clones do mesmo
   modelo dividiriam a mesma linha do ``maquina.json``, e a cor de um pintaria a
   borda do outro.
"""
from __future__ import annotations

import ast
from pathlib import Path

from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_NAO_SEI,
    ID_DE_OUTRA_COR,
    MODOS_DO_APARELHO,
    chave_de_maquina,
    cores_do_plastico_items,
    declaracoes_do_aparelho,
    dicas_das_cores,
    input_mode,
    marca_e_via,
    modo_deduzido,
    nome_oficial_da_cor,
)
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    NOMES_DE_FABRICA,
    TONS,
    cor_do_codigo,
    cor_do_nome,
    cor_do_serial,
    decodificar,
    tom_para_a_borda,
)

RAIZ = Path(__file__).resolve().parents[2]

#: O 8BitDo desta casa em modo Switch, por Bluetooth. MAC forjado na faixa
#: `e8:47:3a` que o portão de anonimato reconhece como sintética.
_8BITDO_SWITCH = {
    "name": "Nintendo Co., Ltd. Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "bluetooth",
    "uniq": "e8:47:3a:00:00:07",
    "driver": "nintendo",
    "identity": "e8473a000007",
}
#: Um Pro Controller GENUÍNO: mesmo VID:PID e mesmo driver do clone acima — é
#: exatamente por isso que ele está aqui. Se o "não sei" dependesse de o produto
#: distinguir os dois, ele já teria falhado nesta linha.
_PRO_GENUINO = {**_8BITDO_SWITCH, "uniq": "aa:bb:cc:00:00:11", "identity": "aabbcc000011"}
#: Marca que ninguém conhece: nem VID, nem OUI, nem driver.
_DESCONHECIDO = {
    "name": "Marca Xpto Pad",
    "vid": "abcd",
    "pid": "0001",
    "bus": "usb",
    "driver": "hid-generic",
}


class TestTodoCampoNasceSemValor:
    def test_todo_campo_nasce_sem_valor(self) -> None:
        """Sem declaração gravada, TODO campo vale `None` — nos três aparelhos."""
        for entrada in (_8BITDO_SWITCH, _PRO_GENUINO, _DESCONHECIDO):
            campos = declaracoes_do_aparelho(entrada)
            assert campos, "um controle não-Sony tem pelo menos duas declarações"
            for chave, rotulo, valor in campos:
                assert valor is None, (
                    f"{chave!r} nasceu valendo {valor!r} em {entrada['name']!r}. "
                    "Default chutado é pior que campo vazio: parece informação."
                )
                assert rotulo[:1].isupper(), f"{rotulo!r} não começa com maiúscula"

    def test_o_adotado_nao_pergunta_o_desenho_dos_botoes(self) -> None:
        """DualSense tem UM desenho de botão. Perguntar seria pergunta sem objeto."""
        chaves = [c for c, _r, _v in declaracoes_do_aparelho(_PRO_GENUINO, adotado=True)]
        assert chaves == ["cor"]

    def test_declaracao_gravada_aparece(self) -> None:
        """Instrumento válido: com valor gravado, o campo NÃO devolve `None`.

        Sem esta asserção o teste acima passaria com uma função que devolve
        `None` sempre — que é o defeito de portão que esta casa mais paga.
        """
        campos = dict(
            (chave, valor)
            for chave, _rotulo, valor in declaracoes_do_aparelho(
                _8BITDO_SWITCH, declarado={"botoes": "nintendo", "cor": "Cosmic Red"}
            )
        )
        assert campos == {"botoes": "nintendo", "cor": "Cosmic Red"}

    def test_valor_vazio_continua_sendo_nao_sei(self) -> None:
        """String vazia no disco não é escolha de ninguém — é ausência."""
        campos = dict(
            (chave, valor)
            for chave, _rotulo, valor in declaracoes_do_aparelho(
                _8BITDO_SWITCH, declarado={"botoes": "", "cor": None}
            )
        )
        assert campos == {"botoes": None, "cor": None}


class TestOModoEDeduzido:
    """T1 e T3: quatro modos, deduzidos e mostrados, nunca declarados."""

    def test_o_modo_nao_esta_entre_as_declaracoes(self) -> None:
        chaves = [c for c, _r, _v in declaracoes_do_aparelho(_8BITDO_SWITCH)]
        assert "modo" not in chaves, (
            "o modo voltou a ser campo declarado. Ele é DEDUZIDO (T1): uma "
            "declaração por identidade nasce órfã, porque o MAC do 8BitDo MUDA "
            "com o modo que a declaração descreve."
        )

    def test_sao_quatro_modos_e_os_quatro_da_canonica(self) -> None:
        assert [ident for ident, _ in MODOS_DO_APARELHO] == [
            "dinput",
            "xinput",
            "switch",
            "macos",
        ]

    def test_todo_rotulo_de_modo_comeca_em_maiuscula(self) -> None:
        """O portão de redação da aba cobra isto — e "macOS" o reprovaria."""
        for _ident, rotulo in MODOS_DO_APARELHO:
            assert rotulo[:1].isupper(), rotulo

    def test_deduz_os_quatro(self) -> None:
        assert modo_deduzido(_8BITDO_SWITCH) == "switch"
        assert modo_deduzido({"vid": "045e", "pid": "028e"}) == "xinput"
        assert modo_deduzido({"vid": "2dc8", "pid": "6001"}) == "dinput"
        assert modo_deduzido({"vid": "054c", "pid": "05c4"}) == "macos"

    def test_modo_desconhecido_e_vazio_e_nao_um_chute(self) -> None:
        assert modo_deduzido(_DESCONHECIDO) == ""

    def test_a_ficha_do_controle_continua_dizendo_o_que_dizia(self) -> None:
        """`input_mode` virou projeção de `modo_deduzido` e NÃO mudou de resposta.

        Duas leituras do mesmo fato só não são duas verdades enquanto elas
        concordam. Esta é a asserção que garante que a projeção não inventou
        estado novo para a ficha do controle.
        """
        assert input_mode(_8BITDO_SWITCH) == "nintendo"
        assert input_mode({"vid": "045e", "pid": "028e"}) == "xbox"
        assert input_mode({"vid": "0000", "driver": "xpad"}) == "xbox"
        assert input_mode({"vid": "2dc8", "pid": "6001"}) == "outro"
        assert input_mode({"vid": "054c", "driver": "playstation"}) == "outro"
        assert input_mode(_DESCONHECIDO) == "outro"


class TestAChaveDoDisco:
    def test_endereco_forjado_nao_vira_chave(self) -> None:
        """O `02:` que o nosso DKMS sintetiza não pode indexar o `maquina.json`.

        Ele é montado a partir de VID, PID e bus, então dois clones do MESMO
        modelo recebem o MESMO endereço. Gravar por ele funde dois aparelhos numa
        linha só — e a cor de um passa a pintar a borda do outro.

        O exemplo usa a faixa `02:fe`, que é o endereço que o nosso próprio vpad
        forja (`player_mac()`) e uma das faixas sintéticas que o
        `test_anonimato_de_fixtures` permite. Serve duas vezes: é forjado de
        verdade e é `02` de verdade.
        """
        assert chave_de_maquina({"uniq": "02:fe:00:00:00:02"}) is None
        assert chave_de_maquina({"identity": "02fe00000002"}) is None

    def test_endereco_bom_vira_chave_de_doze_hexa(self) -> None:
        assert chave_de_maquina(_8BITDO_SWITCH) == "e8473a000007"
        assert chave_de_maquina({"uniq": "AA:BB:CC:00:00:D8"}) == "aabbcc0000d8"

    def test_sem_endereco_nao_ha_chave(self) -> None:
        assert chave_de_maquina({"name": "sem endereço"}) is None
        assert chave_de_maquina({"uniq": "/dev/hidraw3"}) is None


class TestAListaDeCor:
    def test_oito_botoes_seis_cores_outra_e_nao_sei(self) -> None:
        """O oitavo entrou em 23/08/2026: sem ele, "não sei" não era resposta.

        Grupo de rádio ignora o clique no botão já afundado — quem declarasse a
        cor errada não tinha gesto nenhum para desfazer (`D-A1`).
        """
        itens = cores_do_plastico_items()
        assert len(itens) == 8
        assert [ident for ident, _ in itens[:6]] == ["00", "01", "02", "03", "04", "05"]
        assert itens[6][0] == ID_DE_OUTRA_COR
        assert itens[-1][0] == ID_DE_NAO_SEI

    def test_todo_rotulo_de_cor_comeca_em_maiuscula(self) -> None:
        for _ident, rotulo in cores_do_plastico_items():
            assert rotulo[:1].isupper(), rotulo

    def test_a_dica_de_cada_cor_e_o_nome_de_fabrica(self) -> None:
        """O rótulo é o que ela lê; a dica é o que está escrito na caixa."""
        dicas = dicas_das_cores()
        assert dicas["02"] == "Cosmic Red"
        assert dicas["05"] == "Starlight Blue"
        assert dicas[ID_DE_OUTRA_COR].startswith("Para um modelo fora da lista")

    def test_o_que_vai_para_o_disco_e_o_nome_e_nao_o_codigo(self) -> None:
        assert nome_oficial_da_cor("02") == "Cosmic Red"
        assert nome_oficial_da_cor(ID_DE_OUTRA_COR) is None


class TestATabelaDeCores:
    def test_as_duas_copias_da_tabela_concordam(self) -> None:
        """A do produto e a do ensaio, confrontadas — não copiadas às cegas.

        O ensaio guarda a tabela por um motivo bom (rodar num checkout sem o
        pacote instalado), e o preço de uma segunda cópia é este confronto. Esta
        casa já pagou três vezes por medir contra a régua errada.
        """
        fonte = (RAIZ / "scripts" / "ensaios" / "cor_do_plastico.py").read_text(
            encoding="utf-8"
        )
        arvore = ast.parse(fonte)
        do_ensaio = next(
            ast.literal_eval(no.value)
            for no in ast.walk(arvore)
            if isinstance(no, ast.Assign)
            and getattr(no.targets[0], "id", "") == "CORES"
        )
        assert do_ensaio == NOMES_DE_FABRICA

    def test_todo_codigo_tem_tom(self) -> None:
        assert set(TONS) == set(NOMES_DE_FABRICA)

    def test_codigo_fora_da_tabela_devolve_nada(self) -> None:
        assert cor_do_codigo("ZZ") is None
        assert cor_do_nome("Verde Abacate") is None

    def test_o_serial_entrega_a_cor_nos_caracteres_cinco_e_seis(self) -> None:
        """`AB1C05...` -> Starlight Blue. Serial forjado, com o `05` no lugar."""
        cor = cor_do_serial(_SERIAL_05)
        assert cor is not None
        assert (cor.codigo, cor.nome) == ("05", "Starlight Blue")

    def test_serial_curto_nao_inventa_cor(self) -> None:
        assert cor_do_serial("AB1C") is None


class TestOPretoNaoSome:
    def test_midnight_black_e_clareado_para_a_borda(self) -> None:
        """Pintado cru, o preto do plástico é a AUSÊNCIA de borda.

        `#00040d` é MAIS ESCURO que o fundo da janela. O desenho já previa e a
        dica dele está na tela: *"Preto puro sumiria no fundo escuro da janela,
        então a borda usa um tom clareado do mesmo plástico."*
        """
        cru = TONS["01"]
        borda = tom_para_a_borda(cru)
        assert borda != cru
        assert int(borda[1:3], 16) + int(borda[3:5], 16) + int(borda[5:7], 16) > int(
            cru[1:3], 16
        ) + int(cru[3:5], 16) + int(cru[5:7], 16)

    def test_o_preto_clareado_continua_parecendo_preto(self) -> None:
        """A clareada é MISTURA com branco, não subida de luminosidade em HLS.

        MEDIDO em 22/08/2026: o `ensure_min_contrast` da casa preserva matiz E
        saturação, e o Midnight Black tem saturação HLS de 100 % (o canal
        vermelho é zero). Subir a luminosidade dele devolve `#0a56ff` — um AZUL
        ELÉTRICO no lugar do preto do plástico. Misturar com branco não pode
        aumentar saturação; subir luminosidade pode, e justamente nas cores
        quase pretas, que são as que precisam da correção.

        O desenho aprovado pinta aquele card de `#5a5c6b`, um cinza-azulado.
        """
        import colorsys

        def saturacao(hexa: str) -> float:
            r, g, b = (int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5))
            return colorsys.rgb_to_hls(r, g, b)[2]

        borda = tom_para_a_borda(TONS["01"])
        assert saturacao(borda) < saturacao(TONS["01"]), (
            f"o preto do plástico virou {borda}, mais saturado que o "
            f"{TONS['01']} de origem — é a subida de luminosidade em HLS "
            "voltando, e ela devolve azul elétrico."
        )

    def test_toda_cor_da_tabela_se_le_sobre_o_card(self) -> None:
        """As vinte e uma, contra o fundo do card, com o piso da borda."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            FUNDO_DO_CARD,
            RAZAO_DA_BORDA,
        )
        from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

        for codigo, hexa in TONS.items():
            borda = tom_para_a_borda(hexa)
            rgb = tuple(int(borda[i : i + 2], 16) for i in (1, 3, 5))
            assert razao_contraste(rgb, FUNDO_DO_CARD) >= RAZAO_DA_BORDA, (
                f"{codigo} ({hexa} -> {borda}) some no fundo do card"
            )

    def test_cor_ja_clara_passa_intacta(self) -> None:
        """Instrumento válido: quem já se lê não é mexido."""
        assert tom_para_a_borda(TONS["05"]) == TONS["05"]

    def test_tom_vazio_ou_torto_nao_vira_cor(self) -> None:
        assert tom_para_a_borda("") == ""
        assert tom_para_a_borda("#nope") == ""


#: OS DOIS SERIAIS FORJADOS DESTE ARQUIVO. Eles vivem em constante, e não
#: soltos na linha do `assert`, por uma razão medida em 03/09/2026: com a marca
#: de isenção do portão `serial-de-aparelho` na mesma linha, quatro `assert`
#: passavam de cem caracteres e o `ruff` reprovava. A constante paga a marca uma
#: vez só.
#:
#: O prefixo `AB1C` não sai de fábrica nenhuma; o que eles preservam é a FORMA —
#: dezessete caracteres, com o CÓDIGO DA COR nos caracteres cinco e seis, que é
#: o que estes testes medem.
_SERIAL_05 = "AB1C05D1234567890"  # serial-de-mentira: prefixo forjado
_SERIAL_02 = "AB1C02D1234567890"  # serial-de-mentira: prefixo forjado


class TestARespostaDoAparelho:
    def test_resposta_boa_vira_cor(self) -> None:
        dados = bytes([0x81, 1, 19, 2]) + _SERIAL_02.encode()
        cor = decodificar(dados)
        assert cor is not None
        assert cor.nome == "Cosmic Red"

    def test_eco_errado_nao_vira_cor(self) -> None:
        """Sem o eco certo, o que vem depois não é o serial.

        Aceitar assim mesmo decodificaria a cor a partir de OUTRO report — que é
        a medição falsa que esta casa pegou em 15/08/2026, com um pedido de
        `0x20` voltando com `0x80` no byte 0.
        """
        assert decodificar(bytes([0x81, 9, 9, 2]) + _SERIAL_02.encode()) is None
        assert decodificar(bytes([0x81, 1, 19, 0]) + _SERIAL_02.encode()) is None
        assert decodificar(bytes([0x81, 1, 19, 2]) + b"curto") is None


class TestOSubtitulo:
    def test_a_via_sai_como_no_desenho(self) -> None:
        # "Nintendo" e não "8BitDo": o MAC daqui é FORJADO (faixa `e8:47:3a` do
        # portão de anonimato), e o OUI real da 8BitDo não pode entrar em
        # arquivo versionado. Sem o OUI, `brand_of` cai no VID — que é o
        # primeiro dos três erros de rótulo medidos em
        # `docs/protocol/externos-firmware-e-modos.md:230-246`, e que esta leva
        # não conserta: consertar é outra frente.
        assert marca_e_via(_8BITDO_SWITCH) == "Nintendo · Bluetooth"
        assert marca_e_via({"bus": "usb"}, marca="Sony") == "Sony · cabo"

    def test_sem_barramento_sobra_so_a_marca(self) -> None:
        assert marca_e_via({}, marca="Sony") == "Sony"
