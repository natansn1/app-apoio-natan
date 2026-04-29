import streamlit as st
import xml.etree.ElementTree as ET
from xml.dom import minidom
import io
import zipfile
from PIL import Image
import json
import os
import re
from datetime import datetime, timedelta
import requests

# ========================
# CONFIGURAÇÃO INICIAL
# ========================
st.set_page_config(
    page_title="APOIO - NATAN",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

bg_color = "#0e1117"
text_color = "#fafafa"
logo_file = 'logolinx.png'

# ========================
# CSS GLOBAL
# ========================
st.markdown(f"""
    <style>
    header, footer, #MainMenu {{visibility: hidden !important;}}
    .stDeployButton {{display:none !important;}}
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    [data-testid="stImage"] {{ display: flex !important; justify-content: center !important; }}

    .stDownloadButton > button {{
        width: 100%; border-radius: 8px; border: none;
        background: linear-gradient(135deg, #28a745, #218838) !important;
        color: white !important; font-weight: 600; font-size: 0.95rem;
        padding: 0.6em 1.2em; transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.3);
    }}
    .stDownloadButton > button:hover {{
        background: linear-gradient(135deg, #218838, #1e7e34) !important;
        box-shadow: 0 6px 16px rgba(40, 167, 69, 0.5); transform: translateY(-1px);
    }}

    .zip-download .stDownloadButton > button {{
        background: linear-gradient(135deg, #0d6efd, #0a58ca) !important;
        box-shadow: 0 4px 14px rgba(13, 110, 253, 0.4);
        border-radius: 12px; font-size: 1.2rem; padding: 0.8em 1.5em;
        text-transform: uppercase; letter-spacing: 0.8px;
        border: 2px solid rgba(255,255,255,0.15);
    }}

    .streamlit-expanderHeader {{
        font-size: 1rem; font-weight: 600; background-color: #1a1c23;
        border-radius: 10px; border: 1px solid #2b2d35;
    }}

    .back-button > button {{
        background: transparent; border: 1px solid #6c757d;
        color: #fafafa !important; font-weight: 500; border-radius: 8px;
        padding: 0.4em 1em; transition: 0.2s;
    }}
    .back-button > button:hover {{ background: #1f2229; border-color: #adb5bd; }}

    .custom-footer {{
        position: fixed; left: 0; bottom: 0; width: 100%; text-align: center;
        padding: 10px; font-size: 12px; color: #6c757d;
        background: rgba(14, 17, 23, 0.85); backdrop-filter: blur(4px);
    }}

    .stTextInput > div > div > input {{
        background-color: #1f2229; color: #fafafa; border: 1px solid #2b2d35;
    }}
    </style>
    <div class="custom-footer">© 2026 | Developed by Natan</div>
    """, unsafe_allow_html=True)

# ========================
# CLIENTE SUPABASE VIA REST
# ========================
class SupabaseREST:
    """
    Cliente mínimo para a API REST do Supabase.
    Usa requests e não requer dependências pesadas.
    """
    def __init__(self, url, key):
        self.base_url = f"{url}/rest/v1"
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def select(self, table, query=None):
        url = f"{self.base_url}/{table}"
        params = query if query else {}
        r = requests.get(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r.json()

    def insert(self, table, data):
        url = f"{self.base_url}/{table}"
        headers = {**self.headers, "Prefer": "return=representation"}
        r = requests.post(url, headers=headers, json=data)
        r.raise_for_status()
        return r.json()

    def upsert(self, table, data):
        """Upsert usando on conflict (requer chave primária ou unique)"""
        url = f"{self.base_url}/{table}"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(url, headers=headers, json=data)
        r.raise_for_status()
        return r.json()

    def delete(self, table, conditions=None):
        """conditions: dict como {"coluna": "eq.valor"}"""
        url = f"{self.base_url}/{table}"
        params = conditions if conditions else {}
        r = requests.delete(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r

    def delete_all(self, table):
        """Apaga todos os registros da tabela (cuidado!)"""
        url = f"{self.base_url}/{table}"
        params = {"id": "gt.0"}  # condição que pega todos (se id > 0)
        r = requests.delete(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r

# ========================
# TENTAR CONECTAR AO SUPABASE
# ========================
try:
    supabase = SupabaseREST(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    usar_supabase = True
except:
    supabase = None
    usar_supabase = False
    # Fallback: usaremos JSON local

ARQUIVO_JSON = "cnpjs.json"

def carregar_cnpjs():
    """Retorna (lista_cnpjs, cnpj_ativo)"""
    if usar_supabase:
        try:
            dados = supabase.select("cnpjs", query={"select": "*", "order": "id"})
            cnpjs_lista = [{"nome": d["nome"], "cnpj": d["cnpj"]} for d in dados]
            cnpj_ativo = cnpjs_lista[0]["cnpj"] if cnpjs_lista else ""
            return cnpjs_lista, cnpj_ativo
        except Exception as e:
            st.error(f"Falha ao carregar CNPJs do banco: {e}")
            return [], ""
    else:
        if os.path.exists(ARQUIVO_JSON):
            with open(ARQUIVO_JSON, "r", encoding="utf-8") as f:
                dados = json.load(f)
            return dados.get("cnpjs", []), dados.get("cnpj_ativo", "")
        else:
            padrao = [
                {"nome": "CIELO", "cnpj": "01027058000191"},
                {"nome": "REDE", "cnpj": "03145212000133"},
                {"nome": "GETNET", "cnpj": "10440482000154"},
                {"nome": "STONE", "cnpj": "16501555000157"},
                {"nome": "PAGSEGURO", "cnpj": "08561701000101"}
            ]
            return padrao, "01027058000191"

def carregar_regras():
    """Carrega regras do banco ou fallback fixo"""
    if usar_supabase:
        try:
            dados = supabase.select("regras_promocoes", query={"select": "*"})
            regras = {item["id_deloitte"]: {"d": item["descricao"], "c": item["codigo_promo"]} for item in dados}
            return regras
        except Exception as e:
            st.error(f"Erro ao carregar regras: {e}")
            return {}
    else:
        # Regras padrão
        return {
            "6540930": {"d": "JAN26 PREM: HAMBURGÃO POR R$4,99 + 50 PTS", "c": "43873"},
            "6540919": {"d": "JAN26 PREM: PÃO DE QUEIJO TRAD POR R$0,99 + 50 PTS", "c": "43867"},
            "6540918": {"d": "JAN26 PREM: PÃO DE QUEIJO RECH POR R$0,99 + 50 PTS", "c": "43868"},
            "6540926": {"d": "JAN26 PREM: HEINEKEN ZERO LN POR R$6,59 + 50 PTS", "c": "43866"}
        }

# ========================
# INICIALIZAÇÃO DO ESTADO
# ========================
if "pagina" not in st.session_state:
    st.session_state.pagina = "home"

if "cnpjs" not in st.session_state or "cnpj_selecionado" not in st.session_state:
    lista, cnpj_ativo_str = carregar_cnpjs()
    st.session_state.cnpjs = lista
    idx = 0
    for i, c in enumerate(lista):
        if c["cnpj"] == cnpj_ativo_str:
            idx = i
            break
    st.session_state.cnpj_selecionado = idx

if "gerenciar_aberto" not in st.session_state:
    st.session_state.gerenciar_aberto = False

if "regras" not in st.session_state:
    st.session_state.regras = carregar_regras()

def obter_cnpj_ativo():
    idx = st.session_state.cnpj_selecionado
    return st.session_state.cnpjs[idx]["cnpj"]

def persistir_cnpjs_local():
    """Grava a lista de CNPJs no arquivo JSON (usado no modo offline)"""
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "cnpjs": st.session_state.cnpjs,
            "cnpj_ativo": st.session_state.cnpjs[st.session_state.cnpj_selecionado]["cnpj"]
        }, f, indent=2)

def atualizar_persistencia():
    """Salva a lista de CNPJs (banco ou JSON)"""
    if usar_supabase:
        try:
            supabase.delete_all("cnpjs")
            for c in st.session_state.cnpjs:
                supabase.insert("cnpjs", {"nome": c["nome"], "cnpj": c["cnpj"]})
        except Exception as e:
            st.error(f"Erro ao salvar CNPJs no banco: {e}")
    else:
        persistir_cnpjs_local()

def format_xml(element):
    raw_xml = ET.tostring(element, encoding='utf-8')
    reparsed = minidom.parseString(raw_xml)
    xml_str = reparsed.toprettyxml(indent="  ")
    return xml_str.replace('<?xml version="1.0" ?>', '').replace(' xmlns="http://www.portalfiscal.inf.br/nfe"', '').strip()

# ========================
# PÁGINA HOME
# ========================
if st.session_state.pagina == "home":
    try:
        logo = Image.open(logo_file)
        c1, c2, c3 = st.columns([1, 0.4, 1])
        with c2:
            st.image(logo, use_container_width=True)
    except:
        st.warning("⚠️ Logotipo não encontrado. Adicione 'logolinx.png' à pasta.")

    st.markdown("<h1 style='text-align: center; margin: 2rem 0;'>APOIO - NATAN</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd; font-size: 1.1rem;'>Ferramentas projetadas com o intuito de auxiliar no dia a dia.</p>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🛡️ Corretor de\nEstrutura de Cartão no XML", use_container_width=True):
            st.session_state.pagina = "cartao"
            st.rerun()
    with col2:
        if st.button("🎁 Ajustador de\nPromoções", use_container_width=True):
            st.session_state.pagina = "promocoes"
            st.rerun()
    with col3:
        if st.button("🕒 Corretor de\nTS_NULL", use_container_width=True):
            st.session_state.pagina = "tsnull"
            st.rerun()

    st.markdown("""
        <style>
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
            border: none; font-weight: 700; font-size: 1.1rem;
            padding: 0.7em 1.4em; border-radius: 12px;
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4); transition: 0.3s;
            height: 100%;
            white-space: pre-line;
        }
        </style>
    """, unsafe_allow_html=True)

# ========================
# PÁGINA CORRETOR DE CARTÃO NO XML
# ========================
elif st.session_state.pagina == "cartao":
    st.markdown('<div class="back-button">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar para tela Inicial"):
        st.session_state.pagina = "home"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    try:
        logo = Image.open(logo_file)
        col1, col2, col3 = st.columns([1, 0.2, 1])
        with col2:
            st.image(logo, use_container_width=True)
    except:
        pass

    st.markdown("<h1 style='text-align: center; margin-bottom: 0.5rem;'>Corretor de Estrutura de Cartão</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Ajusta automaticamente tags de pagamento com cartão (tPag 03/04)</p>", unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    with col1:
        opcoes_cnpj = [f"{c['nome']} – {c['cnpj']}" for c in st.session_state.cnpjs]
        idx_atual = st.session_state.cnpj_selecionado
        novo_idx = st.selectbox(
            "CNPJ ativo para os ajustes:",
            range(len(opcoes_cnpj)),
            format_func=lambda i: opcoes_cnpj[i],
            index=idx_atual,
            key="select_cnpj_ativo"
        )
        if novo_idx != idx_atual:
            st.session_state.cnpj_selecionado = novo_idx
            atualizar_persistencia()
    with col2:
        st.write("")
        if st.button("⚙️ Gerenciar"):
            st.session_state.gerenciar_aberto = not st.session_state.gerenciar_aberto

    cnpj_ativo = obter_cnpj_ativo()
    nome_ativo = st.session_state.cnpjs[st.session_state.cnpj_selecionado]["nome"]
    st.markdown(f"**CNPJ em uso:** `{cnpj_ativo}` ({nome_ativo})")

    # Gerenciador de CNPJs
    if st.session_state.gerenciar_aberto:
        with st.expander("Gerenciar CNPJs de Adquirentes", expanded=True):
            st.markdown("#### Lista de CNPJs cadastrados")
            if st.session_state.cnpjs:
                for i, c in enumerate(st.session_state.cnpjs):
                    cols = st.columns([3, 1])
                    with cols[0]:
                        st.write(f"🔹 {c['nome']} — {c['cnpj']}")
                    with cols[1]:
                        if st.button("🗑️ Remover", key=f"rem_cnpj_{c['cnpj']}"):
                            # Remove do estado e persiste
                            st.session_state.cnpjs.pop(i)
                            if st.session_state.cnpj_selecionado >= len(st.session_state.cnpjs):
                                st.session_state.cnpj_selecionado = 0
                            atualizar_persistencia()
                            st.rerun()
            else:
                st.info("Nenhum CNPJ cadastrado.")

            st.divider()
            st.markdown("#### Adicionar novo CNPJ")
            with st.form("add_cnpj", clear_on_submit=True):
                col_nome, col_cnpj = st.columns(2)
                with col_nome:
                    nome_adq = st.text_input("Nome (ex: STONE, PAGBANK)", max_chars=30)
                with col_cnpj:
                    cnpj_adq = st.text_input("CNPJ (apenas números)", max_chars=14)
                submitted = st.form_submit_button("➕ Adicionar CNPJ")
                if submitted:
                    if nome_adq and cnpj_adq and len(cnpj_adq) == 14 and cnpj_adq.isdigit():
                        # Verifica duplicata
                        if any(c["cnpj"] == cnpj_adq for c in st.session_state.cnpjs):
                            st.error("CNPJ já cadastrado.")
                        else:
                            st.session_state.cnpjs.append({"nome": nome_adq.upper(), "cnpj": cnpj_adq})
                            atualizar_persistencia()
                            st.success(f"{nome_adq} adicionado com sucesso!")
                            st.rerun()
                    else:
                        st.error("Preencha um nome e um CNPJ válido (14 dígitos numéricos).")
            if st.button("Fechar gerenciador"):
                st.session_state.gerenciar_aberto = False
                st.rerun()

    NS = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    ET.register_namespace('', "http://www.portalfiscal.inf.br/nfe")

    uploaded_files = st.file_uploader("📂 Arraste os arquivos XML aqui", type="xml", accept_multiple_files=True)

    if uploaded_files:
        ajustados_zip = io.BytesIO()
        arquivos_para_zip = []

        for uploaded_file in uploaded_files:
            try:
                tree = ET.parse(uploaded_file)
                root = tree.getroot()
                vNF_elem = root.find(".//ns:vNF", NS)
                valor_nota = vNF_elem.text if vNF_elem is not None else "0.00"
                pag_elem = root.find(".//ns:pag", NS)

                if pag_elem is not None:
                    xml_antes = format_xml(pag_elem)
                    houve_alteracao = False
                    for detPag in pag_elem.findall("ns:detPag", NS):
                        tPag_elem = detPag.find("ns:tPag", NS)
                        if tPag_elem is not None and tPag_elem.text in ["03", "04"]:
                            tipo = tPag_elem.text
                            for child in list(detPag):
                                detPag.remove(child)
                            ET.SubElement(detPag, "indPag").text = "1"
                            ET.SubElement(detPag, "tPag").text = tipo
                            ET.SubElement(detPag, "vPag").text = valor_nota
                            card = ET.SubElement(detPag, "card")
                            ET.SubElement(card, "tpIntegra").text = "2"
                            ET.SubElement(card, "CNPJ").text = cnpj_ativo
                            ET.SubElement(card, "tBand").text = "99"
                            ET.SubElement(card, "cAut").text = "000000"
                            houve_alteracao = True

                    if houve_alteracao:
                        with st.expander(f"✅ {uploaded_file.name} - Ajustado"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.caption("🔴 ORIGINAL")
                                st.code(xml_antes, language="xml")
                            with col2:
                                st.caption("🟢 CORRIGIDO")
                                st.code(format_xml(pag_elem), language="xml")

                            out = io.BytesIO()
                            tree.write(out, encoding="utf-8", xml_declaration=True)
                            xml_data = out.getvalue()
                            st.download_button(
                                label="📥 Baixar XML Corrigido",
                                data=xml_data,
                                file_name=f"FIX_{uploaded_file.name}",
                                key=uploaded_file.name
                            )
                            arquivos_para_zip.append((f"FIX_{uploaded_file.name}", xml_data))
                    else:
                        st.info(f"ℹ️ {uploaded_file.name}: Nenhuma tag de cartão (tPag 03/04) encontrada.")
                else:
                    st.warning(f"⚠️ {uploaded_file.name}: Tag <pag> não localizada.")
            except Exception as e:
                st.error(f"❌ Erro no arquivo {uploaded_file.name}: {e}")

        if arquivos_para_zip:
            st.divider()
            with zipfile.ZipFile(ajustados_zip, "w") as zf:
                for nome, dado in arquivos_para_zip:
                    zf.writestr(nome, dado)

            st.markdown('<div class="zip-download">', unsafe_allow_html=True)
            st.download_button(
                label="📦 BAIXAR TODOS OS CORRIGIDOS (.ZIP)",
                data=ajustados_zip.getvalue(),
                file_name="Pacote_XML_Ajustado.zip",
                use_container_width=True,
                key="zip_download"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Nenhum arquivo precisou de correção. ZIP não será gerado.")

# ========================
# PÁGINA AJUSTADOR DE PROMOÇÕES NAS EVENTS
# ========================
elif st.session_state.pagina == "promocoes":
    st.markdown('<div class="back-button">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar para tela Inicial"):
        st.session_state.pagina = "home"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center;'>Ajustador de Promoções</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Ajusta events de promoções com códigos e descrições incorretas.</p>", unsafe_allow_html=True)

    # Gerenciamento de regras
    with st.expander("⚙️ Configurações de Promoções", expanded=True):
        col1, col2, col3, col4, col5 = st.columns([2, 4, 2, 1, 1])
        with col1:
            id_deloitte = st.text_input("ID Deloitte", key="ent_id")
        with col2:
            descricao = st.text_input("Descrição", key="ent_desc")
        with col3:
            cod_promo = st.text_input("Cód. Promo", key="ent_promo")
        with col4:
            st.write("")
            st.write("")
            if st.button("➕ Add"):
                if id_deloitte and descricao and cod_promo:
                    # Adiciona ao estado e persiste
                    st.session_state.regras[id_deloitte] = {"d": descricao, "c": cod_promo}
                    if usar_supabase:
                        try:
                            supabase.upsert("regras_promocoes", {
                                "id_deloitte": id_deloitte,
                                "descricao": descricao,
                                "codigo_promo": cod_promo
                            })
                        except Exception as e:
                            st.error(f"Erro ao salvar regra no banco: {e}")
                            # Reverte para não ficar inconsistente
                            del st.session_state.regras[id_deloitte]
                            st.stop()
                    st.success("Regra adicionada!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")
        with col5:
            st.write("")
            st.write("")
            # Não há ação aqui, removemos via tabela

        # Exibir regras com opção de remover
        if st.session_state.regras:
            for key, val in list(st.session_state.regras.items()):
                cols = st.columns([2, 4, 2, 1])
                with cols[0]:
                    st.write(key)
                with cols[1]:
                    st.write(val['d'])
                with cols[2]:
                    st.write(val['c'])
                with cols[3]:
                    if st.button("🗑️", key=f"remove_regra_{key}"):
                        # Remove do estado e do banco
                        if usar_supabase:
                            try:
                                supabase.delete("regras_promocoes", conditions={"id_deloitte": f"eq.{key}"})
                            except Exception as e:
                                st.error(f"Erro ao remover regra: {e}")
                                st.stop()
                        del st.session_state.regras[key]
                        st.rerun()
        else:
            st.info("Nenhuma regra cadastrada.")

    uploaded_files = st.file_uploader("📂 Arraste os arquivos .txt aqui", type="txt", accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            try:
                conteudo = uploaded_file.read().decode("utf-8")
                padrao = re.compile(r'\{[^{]*?\"codigo_produto\":\s*\"(\d+)\".*?\}', re.DOTALL)
                if not padrao.search(conteudo):
                    st.warning(f"❌ {uploaded_file.name}: Estrutura 'codigo_produto' não encontrada.")
                    continue

                novo_conteudo = conteudo
                substituicoes = 0
                for m in padrao.finditer(conteudo):
                    bloco = m.group(0)
                    cod = m.group(1)
                    if cod in st.session_state.regras:
                        old_desc_m = re.search(r'\"descricao_promocao\":\s*\"(.*?)\"', bloco)
                        old_promo_m = re.search(r'\"codigo_promocao\":\s*\"(.*?)\"', bloco)
                        old_desc = old_desc_m.group(1) if old_desc_m else "N/A"
                        old_promo = old_promo_m.group(1) if old_promo_m else "N/A"

                        bloco_corrigido = bloco
                        bloco_corrigido = re.sub(r'\"descricao_promocao\":\s*\".*?\"',
                                                  f'"descricao_promocao": "{st.session_state.regras[cod]["d"]}"',
                                                  bloco_corrigido)
                        bloco_corrigido = re.sub(r'\"codigo_promocao\":\s*\".*?\"',
                                                  f'"codigo_promocao": "{st.session_state.regras[cod]["c"]}"',
                                                  bloco_corrigido)

                        novo_conteudo = novo_conteudo.replace(bloco, bloco_corrigido)
                        substituicoes += 1

                        st.write(f"**Produto {cod}**")
                        col_antes, col_depois = st.columns(2)
                        with col_antes:
                            st.caption("🔴 ANTES")
                            st.code(f"Descrição: {old_desc}\nCód. Promo: {old_promo}", language="text")
                        with col_depois:
                            st.caption("🟢 DEPOIS")
                            st.code(f"Descrição: {st.session_state.regras[cod]['d']}\nCód. Promo: {st.session_state.regras[cod]['c']}", language="text")

                if substituicoes > 0:
                    st.success(f"✅ {uploaded_file.name}: {substituicoes} alteração(ões) realizada(s).")
                    st.download_button(
                        label=f"📥 Baixar {uploaded_file.name} corrigido",
                        data=novo_conteudo.encode("utf-8"),
                        file_name=f"FIX_{uploaded_file.name}",
                        key=f"promo_{uploaded_file.name}"
                    )
                else:
                    st.info(f"ℹ️ {uploaded_file.name}: Nenhum código de produto corresponde às regras.")
            except Exception as e:
                st.error(f"❌ Erro ao processar {uploaded_file.name}: {e}")

# ========================
# PÁGINA CORRETOR DE TS_NULL NAS EVENTS
# ========================
elif st.session_state.pagina == "tsnull":
    st.markdown('<div class="back-button">', unsafe_allow_html=True)
    if st.button("⬅️ Voltar para tela Inicial"):
        st.session_state.pagina = "home"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<h1 style='text-align: center;'>Corretor de ts_abertura NULL</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Substitui os campos de ts_abertura NULL usando ts_fechamento ou ts_rec como base</p>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader("📂 Arraste os arquivos .txt aqui", type="txt", accept_multiple_files=True)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            try:
                conteudo = uploaded_file.read().decode("utf-8")
                match_base = None
                campo_encontrado = ""
                for campo in ["ts_fechamento", "ts_rec"]:
                    match = re.search(fr'\"{campo}\"\s*:\s*\"(\d{{4}}-\d{{2}}-\d{{2}}T\d{{2}}:\d{{2}}:\d{{2}})', conteudo)
                    if match:
                        match_base = match
                        campo_encontrado = campo
                        break

                if not match_base:
                    st.warning(f"⚠️ {uploaded_file.name}: Não encontrado ts_fechamento nem ts_rec.")
                    continue

                data_str = match_base.group(1)
                dt_objeto = datetime.strptime(data_str, "%Y-%m-%dT%H:%M:%S")
                dt_nova = (dt_objeto - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")

                padrao_null = r'\"ts_abertura\"\s*:\s*\"?[Nn]ull\"?'
                if not re.search(padrao_null, conteudo):
                    st.info(f"ℹ️ {uploaded_file.name}: Padrão 'ts_abertura': null não encontrado.")
                    continue

                novo_conteudo = re.sub(padrao_null, f'"ts_abertura": "{dt_nova}"', conteudo)

                st.markdown(f"**{uploaded_file.name}**")
                col1, col2 = st.columns(2)
                with col1:
                    st.caption(f"🟡 Base usada: {campo_encontrado} = {data_str}")
                    st.code(match_base.group(0), language="text")
                with col2:
                    st.caption(f"🟢 Novo ts_abertura: {dt_nova}")
                    st.code(f'"ts_abertura": "{dt_nova}"', language="text")

                st.download_button(
                    label=f"📥 Baixar {uploaded_file.name} corrigido",
                    data=novo_conteudo.encode("utf-8"),
                    file_name=f"FIX_{uploaded_file.name}",
                    key=f"tsnull_{uploaded_file.name}"
                )

            except Exception as e:
                st.error(f"❌ Erro ao processar {uploaded_file.name}: {e}")