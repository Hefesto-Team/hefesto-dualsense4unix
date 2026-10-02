"""CONFIG-06 — todo campo do card nasce em "não sei", e "não sei" é resposta."""
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

_8BITDO_SWITCH = {
    "name": "Nintendo Co., Ltd. Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "bluetooth",
    "uniq": "e8:47:3a:00:00:07",
    "driver": "nintendo",
    "identity": "e8473a000007",
}
_PRO_GENUINO = {**_8BITDO_SWITCH, "uniq": "aa:bb:cc:00:00:11", "identity": "aabbcc000011"}
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
        """Instrumento válido: com valor gravado, o campo NÃO devolve `None`."""
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
        """`input_mode` virou projeção de `modo_deduzido` e NÃO mudou de resposta."""
        assert input_mode(_8BITDO_SWITCH) == "nintendo"
        assert input_mode({"vid": "045e", "pid": "028e"}) == "xbox"
        assert input_mode({"vid": "0000", "driver": "xpad"}) == "xbox"
        assert input_mode({"vid": "2dc8", "pid": "6001"}) == "outro"
        assert input_mode({"vid": "054c", "driver": "playstation"}) == "outro"
        assert input_mode(_DESCONHECIDO) == "outro"


class TestAChaveDoDisco:
    def test_endereco_forjado_nao_vira_chave(self) -> None:
        """O `02:` que o nosso DKMS sintetiza não pode indexar o `maquina.json`."""
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
        """O oitavo entrou em 23/08/2026: sem ele, "não sei" não era resposta."""
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
    def test_o_ensaio_e_o_produto_leem_o_mesmo_mapa(self) -> None:
        """Nenhum dos dois guarda cópia digitada — os dois leem o CSV dela."""
        fonte = (RAIZ / "scripts" / "ensaios" / "cor_do_plastico.py").read_text(
            encoding="utf-8"
        )
        arvore = ast.parse(fonte)
        literais = [
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.Assign)
            and getattr(no.targets[0], "id", "") == "CORES"
            and isinstance(no.value, ast.Dict)
        ]
        assert not literais, "o ensaio voltou a digitar a tabela de cores"
        assert "cores-do-dualsense.csv" in fonte
        mapa = {
            linha.split(",", 1)[0].strip()
            for linha in (RAIZ / "docs/data/cores-do-dualsense.csv")
            .read_text(encoding="utf-8")
            .splitlines()
            if linha.strip() and not linha.startswith(("#", "codigo_da_cor"))
        }
        assert set(NOMES_DE_FABRICA) == mapa

    def test_so_tem_tom_quem_tem_casca_amostrada(self) -> None:
        """Casca ``SEM-HEX`` (camuflado, iridescente, arte) não vira hexa inventado."""
        assert set(TONS) < set(NOMES_DE_FABRICA)
        assert "06" not in TONS and "ZC" not in TONS
        assert TONS["05"] == "#7eb8d4", "o casca_esq do Starlight Blue no mapa dela"

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
        """Pintado cru, o preto do plástico é a AUSÊNCIA de borda."""
        cru = TONS["01"]
        borda = tom_para_a_borda(cru)
        assert borda != cru
        assert int(borda[1:3], 16) + int(borda[3:5], 16) + int(borda[5:7], 16) > int(
            cru[1:3], 16
        ) + int(cru[3:5], 16) + int(cru[5:7], 16)

    def test_o_preto_clareado_continua_parecendo_preto(self) -> None:
        """A clareada é MISTURA com branco, não subida de luminosidade em HLS."""
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
        """Toda cor com hexa no mapa, contra o fundo do card, com o piso da borda."""
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


_SERIAL_05 = "AB1C05D1234567890"  # serial-de-mentira: prefixo forjado
_SERIAL_02 = "AB1C02D1234567890"  # serial-de-mentira: prefixo forjado


class TestARespostaDoAparelho:
    def test_resposta_boa_vira_cor(self) -> None:
        dados = bytes([0x81, 1, 19, 2]) + _SERIAL_02.encode()
        cor = decodificar(dados)
        assert cor is not None
        assert cor.nome == "Cosmic Red"

    def test_eco_errado_nao_vira_cor(self) -> None:
        """Sem o eco certo, o que vem depois não é o serial."""
        assert decodificar(bytes([0x81, 9, 9, 2]) + _SERIAL_02.encode()) is None
        assert decodificar(bytes([0x81, 1, 19, 0]) + _SERIAL_02.encode()) is None
        assert decodificar(bytes([0x81, 1, 19, 2]) + b"curto") is None


class TestOSubtitulo:
    def test_a_via_sai_como_no_desenho(self) -> None:
        assert marca_e_via(_8BITDO_SWITCH) == "Nintendo · Bluetooth"
        assert marca_e_via({"bus": "usb"}, marca="Sony") == "Sony · cabo"

    def test_sem_barramento_sobra_so_a_marca(self) -> None:
        assert marca_e_via({}, marca="Sony") == "Sony"
