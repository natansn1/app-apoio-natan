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
from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import List, Optional
from dataclasses import dataclass, field

# Configuração de precisão decimal para evitar erros de arredondamento
getcontext().prec = 28

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
        url = f"{self.base_url}/{table}"
        headers = {**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(url, headers=headers, json=data)
        r.raise_for_status()
        return r.json()

    def delete(self, table, conditions=None):
        url = f"{self.base_url}/{table}"
        params = conditions if conditions else {}
        r = requests.delete(url, headers=self.headers, params=params)
        r.raise_for_status()
        return r

    def delete_all(self, table):
        url = f"{self.base_url}/{table}"
        params = {"id": "gt.0"}
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

ARQUIVO_JSON = "cnpjs.json"

def carregar_cnpjs():
    if usar_supabase:
        try:
            dados = supabase.select("cnpjs", query={"select": "*", "order": "id"})
            cnpjs_lista = [{"nome": d["nome"], "cnpj": d["cnpj"]} for d in dados]
            cnpj_ativo = cnpjs_lista[0]["cnpj"] if cnpjs_lista else ""
        except Exception as e:
            st.error(f"Falha ao carregar CNPJs do banco: {e}")
            cnpjs_lista = []
            cnpj_ativo = ""

        if not cnpjs_lista:
            padrao = [
                {"nome": "CIELO", "cnpj": "01027058000191"},
                {"nome": "REDE", "cnpj": "03145212000133"},
                {"nome": "GETNET", "cnpj": "10440482000154"},
                {"nome": "STONE", "cnpj": "16501555000157"},
                {"nome": "PAGSEGURO", "cnpj": "08561701000101"}
            ]
            cnpjs_lista = padrao
            cnpj_ativo = padrao[0]["cnpj"]
            try:
                for c in padrao:
                    supabase.insert("cnpjs", {"nome": c["nome"], "cnpj": c["cnpj"]})
            except:
                pass
        return cnpjs_lista, cnpj_ativo
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
    if usar_supabase:
        try:
            dados = supabase.select("regras_promocoes", query={"select": "*"})
            regras = {item["id_deloitte"]: {"d": item["descricao"], "c": item["codigo_promo"]} for item in dados}
            return regras
        except Exception as e:
            st.error(f"Erro ao carregar regras: {e}")
            return {}
    else:
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
    lista = st.session_state.cnpjs
    idx = st.session_state.cnpj_selecionado
    if lista and 0 <= idx < len(lista):
        return lista[idx]["cnpj"]
    return "01027058000191"

def persistir_cnpjs_local():
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "cnpjs": st.session_state.cnpjs,
            "cnpj_ativo": st.session_state.cnpjs[st.session_state.cnpj_selecionado]["cnpj"]
        }, f, indent=2)

def atualizar_persistencia():
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
# FUNÇÃO CORRETORA DE ICMSSN500 (tags faltantes)
# ========================
def corrigir_icmssn500(xml_bytes: bytes) -> tuple:
    ET.register_namespace('', 'http://www.portalfiscal.inf.br/nfe')
    tree = ET.parse(io.BytesIO(xml_bytes))
    root = tree.getroot()

    tags_adicionadas = set()

    for icms in root.findall('.//{*}ICMSSN500'):
        valores = {}
        for child in icms:
            tag = child.tag.split('}')[-1]
            valores[tag] = child.text if child.text is not None else ''

        orig = valores.get('orig', '0')
        csosn = valores.get('CSOSN', '500')
        vBCSTRet = valores.get('vBCSTRet', '0.00')
        vICMSSTRet = valores.get('vICMSSTRet', '0.00')

        tags_necessarias = ['pST', 'vICMSSubstituto', 'pRedBCEfet', 'vBCEfet', 'pICMSEfet', 'vICMSEfet']
        for tag in tags_necessarias:
            if tag not in valores:
                tags_adicionadas.add(tag)

        icms.clear()
        ET.SubElement(icms, 'orig').text = orig
        ET.SubElement(icms, 'CSOSN').text = csosn
        ET.SubElement(icms, 'vBCSTRet').text = vBCSTRet
        ET.SubElement(icms, 'pST').text = valores.get('pST', '0.00')
        ET.SubElement(icms, 'vICMSSubstituto').text = valores.get('vICMSSubstituto', '0.00')
        ET.SubElement(icms, 'vICMSSTRet').text = vICMSSTRet
        ET.SubElement(icms, 'pRedBCEfet').text = valores.get('pRedBCEfet', '0.00')
        ET.SubElement(icms, 'vBCEfet').text = valores.get('vBCEfet', '0.00')
        ET.SubElement(icms, 'pICMSEfet').text = valores.get('pICMSEfet', '0.00')
        ET.SubElement(icms, 'vICMSEfet').text = valores.get('vICMSEfet', '0.00')

    alteracoes = []
    if tags_adicionadas:
        for tag in sorted(tags_adicionadas):
            alteracoes.append(f"➕ Adicionada tag: {tag}=0.00")
    else:
        alteracoes.append("✅ Nenhuma alteração necessária (já estava completo).")

    xml_str = ET.tostring(root, encoding='unicode', method='xml')
    if xml_str.startswith('<?xml'):
        xml_str = xml_str[xml_str.find('?>')+2:].lstrip()
    xml_str = re.sub(r'>\s+<', '><', xml_str)
    xml_str = re.sub(r'\s+', ' ', xml_str)

    return xml_str.encode('utf-8'), alteracoes

# ========================
# FUNÇÃO CORRETORA DE ICMS VAZIO (<ICMS />)
# ========================
def corrigir_icms_vazio(xml_bytes: bytes) -> tuple:
    ET.register_namespace('', 'http://www.portalfiscal.inf.br/nfe')
    try:
        tree = ET.parse(io.BytesIO(xml_bytes))
        root = tree.getroot()
    except ET.ParseError:
        return xml_bytes, ["⚠️ Não foi possível fazer parsing do XML."]

    icms_vazios = root.findall('.//*[local-name()="ICMS" and not(*)]')
    if not icms_vazios:
        return xml_bytes, ["✅ Nenhum ICMS vazio encontrado."]

    alteracoes = []
    for icms in icms_vazios:
        novo_icms = ET.Element('ICMS')
        icmssn500 = ET.SubElement(novo_icms, 'ICMSSN500')
        ET.SubElement(icmssn500, 'orig').text = '0'
        ET.SubElement(icmssn500, 'CSOSN').text = '500'
        ET.SubElement(icmssn500, 'vBCSTRet').text = '0.00'
        ET.SubElement(icmssn500, 'pST').text = '0.00'
        ET.SubElement(icmssn500, 'vICMSSubstituto').text = '0.00'
        ET.SubElement(icmssn500, 'vICMSSTRet').text = '0.00'
        ET.SubElement(icmssn500, 'pRedBCEfet').text = '0.00'
        ET.SubElement(icmssn500, 'vBCEfet').text = '0.00'
        ET.SubElement(icmssn500, 'pICMSEfet').text = '0.00'
        ET.SubElement(icmssn500, 'vICMSEfet').text = '0.00'

        parent = icms.getparent() if hasattr(icms, 'getparent') else None
        # ElementTree não tem getparent nativo - vamos usar abordagem alternativa
        # Procurando o pai percorrendo a árvore
        pai_encontrado = None
        for p in root.iter():
            for filho in list(p):
                if filho is icms:
                    pai_encontrado = p
                    break
            if pai_encontrado is not None:
                break

        if pai_encontrado is not None:
            idx = list(pai_encontrado).index(icms)
            pai_encontrado.remove(icms)
            pai_encontrado.insert(idx, novo_icms)
            alteracoes.append("➕ Substituído <ICMS /> por bloco ICMSSN500 completo.")
        else:
            alteracoes.append("⚠️ Elemento <ICMS /> sem pai – não foi possível substituir.")

    xml_str = ET.tostring(root, encoding='unicode', method='xml')
    if xml_str.startswith('<?xml'):
        xml_str = xml_str[xml_str.find('?>')+2:].lstrip()
    xml_str = re.sub(r'>\s+<', '><', xml_str)
    xml_str = re.sub(r'\s+', ' ', xml_str)

    return xml_str.encode('utf-8'), alteracoes

# ============================================================
# MOTOR DE CORREÇÃO DE NF-e — REJEIÇÕES SEFAZ + REFORMA TRIBUTÁRIA
# (Portado do corrector.py para Streamlit, trabalhando com bytes)
# ============================================================
NS_NFE = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
NS_URL_NFE = 'http://www.portalfiscal.inf.br/nfe'

ALIQ_CBS      = Decimal("0.90")
ALIQ_IBS_UF   = Decimal("0.10")
ALIQ_IBS_MUN  = Decimal("0.00")
PCT_REDUCAO   = Decimal("0.00")
MVA           = Decimal("0.00")

CST_ICMS60 = "60"
CSOSN_PADRAO = "500"

CCLASSTRIB_CST000_VALIDOS = {
    "000001", "000002", "000003", "000004",
}
CCLASSTRIB_CST000_PADRAO = "000001"

ORDEM_ICMSTOT = [
    'vBC', 'vICMS', 'vICMSDeson', 'vFCPUFDest', 'vICMSUFDest', 'vFCP',
    'vBCST', 'vST', 'vFCPST', 'vFCPSTRet',
    'qBCMono', 'vICMSMono', 'qBCMonoReten', 'vICMSMonoReten',
    'qBCMonoRet', 'vICMSMonoRet',
    'vProd', 'vFrete', 'vSeg', 'vDesc', 'vII', 'vIPI', 'vIPIDevol',
    'vPIS', 'vCOFINS', 'vOutro', 'vNF', 'vTotTrib'
]

REJEICOES_NFE = {
    "produto_valor_unitario": {
        "titulo": "Valor do produto difere do produto valor unitário de comercialização e quantidade comercial",
        "descricao": "Recalcula vProd (qCom × vUnCom), atualiza vItem, PIS, COFINS e totalizadores.",
        "icone": "💰"
    },
    "aliquota_ibs_uf": {
        "titulo": "Alíquota do IBS da UF inválida [nItem:1]",
        "descricao": "Força pIBSUF=0,10%, pIBSMun=0,00% e pCBS=0,90% (LC 214/2025), corrige vBC e recalcula valores e totalizadores.",
        "icone": "📊"
    },
    "icms_monofasico_total": {
        "titulo": "Total da quantidade tributada do ICMS monofásico retido anteriormente difere do somatório dos itens",
        "descricao": "Corrige qBCMonoRet=qCom, recalcula vICMSMonoRet e grava totalizadores no ICMSTot na ordem correta.",
        "icone": "🧾"
    },
    "schema_icms_vazio": {
        "titulo": "Falha no Schema XML da NFe (Elemento: enviNFe/NFe[1]/infNFe/det[1]/imposto/ICMS)",
        "descricao": "Substitui <ICMS/> vazio por ICMSSN500 (Simples Nacional) ou ICMS60 (Regime Normal), conforme o CRT do emitente.",
        "icone": "🛠️"
    },
    "classificacao_tributaria_ibscbs": {
        "titulo": "Classificação Tributária do IBS/CBS informada inexistente [nItem:1]",
        "descricao": "Substitui cClassTrib inexistente (ex.: 000000) por código válido (000001) conforme a tabela oficial do IBS/CBS.",
        "icone": "🏷️"
    },
}

@dataclass
class Modificacao:
    descricao: str
    detalhe: str = ""

class NFeCorrector:
    """Motor de correção de NF-e (adaptado para trabalhar com bytes em Streamlit)."""

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg, lvl="info": None)
        ET.register_namespace('', NS_URL_NFE)

    def _dec(self, valor) -> Decimal:
        try:
            return Decimal(str(valor).replace(',', '.').strip())
        except Exception:
            return Decimal('0')

    def _fmt(self, valor: Decimal) -> str:
        return f"{valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"

    def _fmt4(self, valor: Decimal) -> str:
        return f"{valor.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP):.4f}"

    def _find(self, parent, path):
        return parent.find(path, NS_NFE)

    def _inserir_ordenado(self, parent, tag: str, valor: str):
        existente = parent.find(f'nfe:{tag}', NS_NFE)
        if existente is not None:
            parent.remove(existente)

        novo = ET.Element(f'{{{NS_URL_NFE}}}{tag}')
        novo.text = valor

        if tag not in ORDEM_ICMSTOT:
            parent.append(novo)
            return

        pos_alvo = ORDEM_ICMSTOT.index(tag)
        for idx, filho in enumerate(list(parent)):
            tag_filho = filho.tag.split('}', 1)[-1]
            if tag_filho in ORDEM_ICMSTOT:
                if ORDEM_ICMSTOT.index(tag_filho) > pos_alvo:
                    parent.insert(idx, novo)
                    return
        parent.append(novo)

    # -------- Rejeição 1 --------
    def _corrigir_vprod(self, root) -> List[Modificacao]:
        mods = []
        for item in root.findall('.//nfe:det', NS_NFE):
            prod = self._find(item, 'nfe:prod')
            if prod is None:
                continue
            qcom_e = self._find(prod, 'nfe:qCom')
            vuncom_e = self._find(prod, 'nfe:vUnCom')
            vprod_e = self._find(prod, 'nfe:vProd')
            vitem_e = self._find(item, 'nfe:vItem')

            if None in (qcom_e, vuncom_e, vprod_e):
                continue

            qcom = self._dec(qcom_e.text)
            vuncom = self._dec(vuncom_e.text)
            vprod_atual = self._dec(vprod_e.text)
            vprod_correto = (qcom * vuncom).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if vprod_atual != vprod_correto:
                vprod_e.text = self._fmt(vprod_correto)
                if vitem_e is not None:
                    vitem_e.text = self._fmt(vprod_correto)
                self._recalcular_pis_cofins(item, vprod_atual, vprod_correto)
                nitem = item.get('nItem', '?')
                mods.append(Modificacao(
                    f"Item {nitem}: vProd {self._fmt(vprod_atual)} → {self._fmt(vprod_correto)}",
                    f"qCom={qcom} × vUnCom={vuncom}"
                ))
        return mods

    def _recalcular_pis_cofins(self, item, vprod_antigo, vprod_novo):
        imposto = self._find(item, 'nfe:imposto')
        if imposto is None:
            return
        for grupo, tag_aliq, tag_val in (('PISAliq', 'pPIS', 'vPIS'),
                                          ('COFINSAliq', 'pCOFINS', 'vCOFINS')):
            g = imposto.find(f'.//nfe:{grupo}', NS_NFE)
            if g is None:
                continue
            vbc = self._find(g, 'nfe:vBC')
            if vbc is None or vbc.text != self._fmt(vprod_antigo):
                continue
            vbc.text = self._fmt(vprod_novo)
            pa = self._find(g, f'nfe:{tag_aliq}')
            va = self._find(g, f'nfe:{tag_val}')
            if pa is not None and va is not None:
                novo = (vprod_novo * self._dec(pa.text)) / Decimal('100')
                va.text = self._fmt(novo)

    # -------- Rejeição 2 --------
    def _corrigir_aliquota_ibs_uf(self, root) -> List[Modificacao]:
        mods = []
        for item in root.findall('.//nfe:det', NS_NFE):
            nitem = item.get('nItem', '?')
            gibscbs = item.find('.//nfe:IBSCBS/nfe:gIBSCBS', NS_NFE)
            if gibscbs is None:
                continue

            prod = self._find(item, 'nfe:prod')
            if prod is not None:
                vprod_e = self._find(prod, 'nfe:vProd')
                vbc_e = self._find(gibscbs, 'nfe:vBC')
                if vprod_e is not None and vbc_e is not None:
                    vprod = self._dec(vprod_e.text)
                    vbc_atual = self._dec(vbc_e.text)
                    if vbc_atual != vprod:
                        vbc_e.text = self._fmt(vprod)
                        mods.append(Modificacao(
                            f"Item {nitem}: vBC IBS/CBS {self._fmt(vbc_atual)} → {self._fmt(vprod)}",
                            "vBC deve ser igual ao vProd do item"
                        ))

            vbc_e = self._find(gibscbs, 'nfe:vBC')
            if vbc_e is None:
                continue
            vbc = self._dec(vbc_e.text)

            gibsuf = self._find(gibscbs, 'nfe:gIBSUF')
            novo_vibsuf = Decimal('0')
            if gibsuf is not None:
                p_elem = self._find(gibsuf, 'nfe:pIBSUF')
                v_elem = self._find(gibsuf, 'nfe:vIBSUF')

                if p_elem is not None:
                    p_atual = self._dec(p_elem.text)
                    if p_atual != ALIQ_IBS_UF:
                        p_elem.text = f"{ALIQ_IBS_UF:.2f}"
                        mods.append(Modificacao(
                            f"Item {nitem}: pIBSUF {p_atual:.2f}% → {ALIQ_IBS_UF:.2f}%",
                            "Alíquota de referência LC 214/2025"
                        ))

                novo_vibsuf = (vbc * ALIQ_IBS_UF / Decimal('100')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                if v_elem is not None:
                    if self._dec(v_elem.text) != novo_vibsuf:
                        mods.append(Modificacao(
                            f"Item {nitem}: vIBSUF {self._fmt(self._dec(v_elem.text))} → {self._fmt(novo_vibsuf)}"
                        ))
                    v_elem.text = self._fmt(novo_vibsuf)

            gibsmun = self._find(gibscbs, 'nfe:gIBSMun')
            novo_vibsmun = Decimal('0')
            if gibsmun is not None:
                p_elem = self._find(gibsmun, 'nfe:pIBSMun')
                v_elem = self._find(gibsmun, 'nfe:vIBSMun')

                if p_elem is not None:
                    p_atual = self._dec(p_elem.text)
                    if p_atual != ALIQ_IBS_MUN:
                        p_elem.text = f"{ALIQ_IBS_MUN:.2f}"
                        mods.append(Modificacao(
                            f"Item {nitem}: pIBSMun {p_atual:.2f}% → {ALIQ_IBS_MUN:.2f}%",
                            "Alíquota de referência LC 214/2025"
                        ))

                novo_vibsmun = (vbc * ALIQ_IBS_MUN / Decimal('100')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                if v_elem is not None:
                    if self._dec(v_elem.text) != novo_vibsmun:
                        mods.append(Modificacao(
                            f"Item {nitem}: vIBSMun {self._fmt(self._dec(v_elem.text))} → {self._fmt(novo_vibsmun)}"
                        ))
                    v_elem.text = self._fmt(novo_vibsmun)

            vibs_elem = self._find(gibscbs, 'nfe:vIBS')
            if vibs_elem is not None:
                vibs_elem.text = self._fmt(novo_vibsuf + novo_vibsmun)

            gcbs = self._find(gibscbs, 'nfe:gCBS')
            if gcbs is not None:
                p_elem = self._find(gcbs, 'nfe:pCBS')
                v_elem = self._find(gcbs, 'nfe:vCBS')

                if p_elem is not None:
                    p_atual = self._dec(p_elem.text)
                    if p_atual != ALIQ_CBS:
                        p_elem.text = f"{ALIQ_CBS:.2f}"
                        mods.append(Modificacao(
                            f"Item {nitem}: pCBS {p_atual:.2f}% → {ALIQ_CBS:.2f}%",
                            "Alíquota de referência LC 214/2025"
                        ))

                novo_vcbs = (vbc * ALIQ_CBS / Decimal('100')).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
                if v_elem is not None:
                    if self._dec(v_elem.text) != novo_vcbs:
                        mods.append(Modificacao(
                            f"Item {nitem}: vCBS {self._fmt(self._dec(v_elem.text))} → {self._fmt(novo_vcbs)}"
                        ))
                    v_elem.text = self._fmt(novo_vcbs)

        return mods

    # -------- Rejeição 5 --------
    def _corrigir_classificacao_tributaria_ibscbs(self, root) -> List[Modificacao]:
        mods = []
        for item in root.findall('.//nfe:det', NS_NFE):
            nitem = item.get('nItem', '?')
            ibscbs = item.find('.//nfe:IBSCBS', NS_NFE)
            if ibscbs is None:
                continue

            cst_elem = self._find(ibscbs, 'nfe:CST')
            cclasstrib_elem = self._find(ibscbs, 'nfe:cClassTrib')

            if cclasstrib_elem is None:
                continue

            cst = (cst_elem.text or '').strip() if cst_elem is not None else ''
            cclasstrib_atual = (cclasstrib_elem.text or '').strip()

            if cst == '000':
                if cclasstrib_atual not in CCLASSTRIB_CST000_VALIDOS:
                    cclasstrib_elem.text = CCLASSTRIB_CST000_PADRAO
                    mods.append(Modificacao(
                        f"Item {nitem}: cClassTrib {cclasstrib_atual or '(vazio)'} → {CCLASSTRIB_CST000_PADRAO}",
                        f"CST {cst} — código inexistente na tabela IBS/CBS"
                    ))
                continue

            if cclasstrib_atual in ('000000', ''):
                cclasstrib_elem.text = CCLASSTRIB_CST000_PADRAO
                mods.append(Modificacao(
                    f"Item {nitem}: cClassTrib {cclasstrib_atual or '(vazio)'} → {CCLASSTRIB_CST000_PADRAO}",
                    f"CST {cst} — código 000000 é inválido"
                ))

        return mods

    # -------- Rejeição 3 --------
    def _corrigir_icms_monofasico(self, root) -> List[Modificacao]:
        mods = []
        total_qbc = Decimal('0')
        total_vicms = Decimal('0')
        encontrados = 0

        for item in root.findall('.//nfe:det', NS_NFE):
            icms61 = item.find('.//nfe:ICMS61', NS_NFE)
            if icms61 is None:
                continue
            encontrados += 1
            nitem = item.get('nItem', '?')

            prod = self._find(item, 'nfe:prod')
            qcom_elem = self._find(prod, 'nfe:qCom') if prod is not None else None

            qbc_elem = self._find(icms61, 'nfe:qBCMonoRet')
            adrem_elem = self._find(icms61, 'nfe:adRemICMSRet')
            vicms_elem = self._find(icms61, 'nfe:vICMSMonoRet')

            if qbc_elem is not None and qcom_elem is not None:
                qcom = self._dec(qcom_elem.text)
                qbc_atual = self._dec(qbc_elem.text)
                if qbc_atual != qcom:
                    qbc_elem.text = self._fmt4(qcom)
                    mods.append(Modificacao(
                        f"Item {nitem}: qBCMonoRet {qbc_atual} → {qcom}",
                        "qBCMonoRet deve ser igual à qCom"
                    ))
                else:
                    qbc_elem.text = self._fmt4(qbc_atual)

            if qbc_elem is not None and adrem_elem is not None and vicms_elem is not None:
                qbc = self._dec(qbc_elem.text)
                adrem = self._dec(adrem_elem.text)
                novo_vicms = (qbc * adrem).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if self._dec(vicms_elem.text) != novo_vicms:
                    mods.append(Modificacao(
                        f"Item {nitem}: vICMSMonoRet {self._fmt(self._dec(vicms_elem.text))} → {self._fmt(novo_vicms)}",
                        f"{qbc} × {adrem}"
                    ))
                    vicms_elem.text = self._fmt(novo_vicms)

            if qbc_elem is not None and qbc_elem.text:
                total_qbc += self._dec(qbc_elem.text)
            if vicms_elem is not None and vicms_elem.text:
                total_vicms += self._dec(vicms_elem.text)

        icms_tot = root.find('.//nfe:ICMSTot', NS_NFE)
        if icms_tot is None:
            return mods

        self._inserir_ordenado(
            icms_tot, 'qBCMonoRet',
            f"{total_qbc.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"
        )
        self._inserir_ordenado(icms_tot, 'vICMSMonoRet', self._fmt(total_vicms))

        if encontrados:
            mods.append(Modificacao(
                f"Totalizadores ICMS Monofásico atualizados ({encontrados} itens)",
                f"qBCMonoRet={total_qbc.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f} | vICMSMonoRet={self._fmt(total_vicms)}"
            ))
        return mods

    # -------- Rejeição 4 --------
    def _corrigir_icms_vazio(self, root) -> List[Modificacao]:
        mods = []
        emit = root.find('.//nfe:emit', NS_NFE)
        crt = "1"
        if emit is not None:
            crt_elem = self._find(emit, 'nfe:CRT')
            if crt_elem is not None and crt_elem.text:
                crt = crt_elem.text.strip()

        usa_csosn = crt in ("1", "4")

        for item in root.findall('.//nfe:det', NS_NFE):
            imposto = self._find(item, 'nfe:imposto')
            if imposto is None:
                continue
            icms = self._find(imposto, 'nfe:ICMS')
            if icms is None:
                continue
            if len(list(icms)) > 0:
                continue

            nitem = item.get('nItem', '?')

            if usa_csosn:
                grupo = ET.SubElement(icms, f'{{{NS_URL_NFE}}}ICMSSN500')

                def _add(parent, tag, txt):
                    el = ET.SubElement(parent, f'{{{NS_URL_NFE}}}{tag}')
                    el.text = txt

                _add(grupo, 'orig', '0')
                _add(grupo, 'CSOSN', CSOSN_PADRAO)

                mods.append(Modificacao(
                    f"Item {nitem}: <ICMS/> vazio → ICMSSN500 (CSOSN {CSOSN_PADRAO})",
                    f"emitente CRT={crt}"
                ))
            else:
                grupo = ET.SubElement(icms, f'{{{NS_URL_NFE}}}ICMS60')

                def _add(parent, tag, txt):
                    el = ET.SubElement(parent, f'{{{NS_URL_NFE}}}{tag}')
                    el.text = txt

                _add(grupo, 'orig', '0')
                _add(grupo, 'CST', CST_ICMS60)
                _add(grupo, 'vBCSTRet', '0.00')
                _add(grupo, 'pST', '0.0000')
                _add(grupo, 'vICMSSubstituto', '0.00')
                _add(grupo, 'vICMSSTRet', '0.00')

                mods.append(Modificacao(
                    f"Item {nitem}: <ICMS/> vazio → ICMS60 (CST {CST_ICMS60})",
                    f"emitente CRT={crt}"
                ))

        return mods

    # -------- IBSCBSTot --------
    def _atualizar_ibscbs_tot(self, root) -> List[Modificacao]:
        mods = []

        tem_ibscbs = False
        for item in root.findall('.//nfe:det', NS_NFE):
            if item.find('.//nfe:IBSCBS', NS_NFE) is not None:
                tem_ibscbs = True
                break

        if not tem_ibscbs:
            return mods

        total = root.find('.//nfe:total', NS_NFE)
        if total is None:
            return mods

        total_vbc = Decimal('0')
        total_vibsuf = Decimal('0')
        total_vibsmun = Decimal('0')
        total_vibs = Decimal('0')
        total_vcbs = Decimal('0')

        for item in root.findall('.//nfe:det', NS_NFE):
            gibscbs = item.find('.//nfe:IBSCBS/nfe:gIBSCBS', NS_NFE)
            if gibscbs is None:
                continue

            vbc = self._find(gibscbs, 'nfe:vBC')
            if vbc is not None and vbc.text:
                total_vbc += self._dec(vbc.text)

            gibsuf = self._find(gibscbs, 'nfe:gIBSUF')
            if gibsuf is not None:
                v = self._find(gibsuf, 'nfe:vIBSUF')
                if v is not None and v.text:
                    total_vibsuf += self._dec(v.text)

            gibsmun = self._find(gibscbs, 'nfe:gIBSMun')
            if gibsmun is not None:
                v = self._find(gibsmun, 'nfe:vIBSMun')
                if v is not None and v.text:
                    total_vibsmun += self._dec(v.text)

            vibs = self._find(gibscbs, 'nfe:vIBS')
            if vibs is not None and vibs.text:
                total_vibs += self._dec(vibs.text)

            gcbs = self._find(gibscbs, 'nfe:gCBS')
            if gcbs is not None:
                v = self._find(gcbs, 'nfe:vCBS')
                if v is not None and v.text:
                    total_vcbs += self._dec(v.text)

        ibscbs_tot_antigo = total.find('nfe:IBSCBSTot', NS_NFE)
        if ibscbs_tot_antigo is not None:
            total.remove(ibscbs_tot_antigo)

        ibscbs_tot = ET.Element(f'{{{NS_URL_NFE}}}IBSCBSTot')

        vbc_elem = ET.SubElement(ibscbs_tot, f'{{{NS_URL_NFE}}}vBCIBSCBS')
        vbc_elem.text = self._fmt(total_vbc)

        gibs = ET.SubElement(ibscbs_tot, f'{{{NS_URL_NFE}}}gIBS')

        gibsuf_elem = ET.SubElement(gibs, f'{{{NS_URL_NFE}}}gIBSUF')
        for tag, val in (('vDif', '0.00'),
                         ('vDevTrib', '0.00'),
                         ('vIBSUF', self._fmt(total_vibsuf))):
            el = ET.SubElement(gibsuf_elem, f'{{{NS_URL_NFE}}}{tag}')
            el.text = val

        gibsmun_elem = ET.SubElement(gibs, f'{{{NS_URL_NFE}}}gIBSMun')
        for tag, val in (('vDif', '0.00'),
                         ('vDevTrib', '0.00'),
                         ('vIBSMun', self._fmt(total_vibsmun))):
            el = ET.SubElement(gibsmun_elem, f'{{{NS_URL_NFE}}}{tag}')
            el.text = val

        vibs_elem = ET.SubElement(gibs, f'{{{NS_URL_NFE}}}vIBS')
        vibs_elem.text = self._fmt(total_vibs if total_vibs else (total_vibsuf + total_vibsmun))

        for tag in ('vCredPres', 'vCredPresCondSus'):
            el = ET.SubElement(gibs, f'{{{NS_URL_NFE}}}{tag}')
            el.text = '0.00'

        gcbs_elem = ET.SubElement(ibscbs_tot, f'{{{NS_URL_NFE}}}gCBS')
        for tag, val in (('vDif', '0.00'),
                         ('vDevTrib', '0.00'),
                         ('vCBS', self._fmt(total_vcbs)),
                         ('vCredPres', '0.00'),
                         ('vCredPresCondSus', '0.00')):
            el = ET.SubElement(gcbs_elem, f'{{{NS_URL_NFE}}}{tag}')
            el.text = val

        vnftot = total.find('nfe:vNFTot', NS_NFE)
        if vnftot is not None:
            idx = list(total).index(vnftot)
            total.insert(idx, ibscbs_tot)
        else:
            total.append(ibscbs_tot)

        mods.append(Modificacao(
            "Grupo IBSCBSTot criado/atualizado",
            f"vBCIBSCBS={self._fmt(total_vbc)} | vIBS={self._fmt(total_vibs)} | vCBS={self._fmt(total_vcbs)}"
        ))
        return mods

    # -------- Totais --------
    def _atualizar_totais(self, root):
        total = root.find('.//nfe:total', NS_NFE)
        if total is None:
            return

        total_vprod = Decimal('0')
        total_pis = Decimal('0')
        total_cofins = Decimal('0')

        for item in root.findall('.//nfe:det', NS_NFE):
            vprod = item.find('nfe:prod/nfe:vProd', NS_NFE)
            if vprod is not None:
                total_vprod += self._dec(vprod.text)

            pis = item.find('.//nfe:PISAliq/nfe:vPIS', NS_NFE)
            if pis is not None:
                total_pis += self._dec(pis.text)
            cofins = item.find('.//nfe:COFINSAliq/nfe:vCOFINS', NS_NFE)
            if cofins is not None:
                total_cofins += self._dec(cofins.text)

        icms_tot = total.find('nfe:ICMSTot', NS_NFE)
        if icms_tot is not None:
            def _set(parent, tag, valor):
                el = parent.find(f'nfe:{tag}', NS_NFE)
                if el is not None:
                    el.text = valor

            _set(icms_tot, 'vProd', self._fmt(total_vprod))
            _set(icms_tot, 'vNF', self._fmt(total_vprod))
            _set(icms_tot, 'vPIS', self._fmt(total_pis))
            _set(icms_tot, 'vCOFINS', self._fmt(total_cofins))

        vnftot = total.find('nfe:vNFTot', NS_NFE)
        if vnftot is not None:
            vnftot.text = self._fmt(total_vprod)

    # ==========================================================
    # API Pública (trabalha com bytes)
    # ==========================================================
    def corrigir_bytes(self, xml_bytes: bytes, rejeicoes_ativas: List[str]) -> dict:
        """
        Retorna dict:
          {
            'success': bool,
            'xml_bytes': bytes (só se success e houve modificação),
            'modificacoes': List[Modificacao],
            'mensagem': str,
            'erro': str,
          }
        """
        try:
            tree = ET.parse(io.BytesIO(xml_bytes))
            root = tree.getroot()
            todas_mods: List[Modificacao] = []

            if "produto_valor_unitario" in rejeicoes_ativas:
                self.log("[1/5] Verificando vProd × qCom × vUnCom...", "info")
                todas_mods += self._corrigir_vprod(root)

            if "aliquota_ibs_uf" in rejeicoes_ativas:
                self.log("[2/5] Verificando alíquota do IBS da UF...", "info")
                todas_mods += self._corrigir_aliquota_ibs_uf(root)

            if "icms_monofasico_total" in rejeicoes_ativas:
                self.log("[3/5] Verificando totais ICMS monofásico...", "info")
                todas_mods += self._corrigir_icms_monofasico(root)

            if "schema_icms_vazio" in rejeicoes_ativas:
                self.log("[4/5] Verificando ICMS vazio...", "info")
                todas_mods += self._corrigir_icms_vazio(root)

            if "classificacao_tributaria_ibscbs" in rejeicoes_ativas:
                self.log("[5/5] Verificando cClassTrib IBS/CBS...", "info")
                todas_mods += self._corrigir_classificacao_tributaria_ibscbs(root)

            # Sempre tenta criar/atualizar IBSCBSTot se houver IBSCBS nos itens
            todas_mods += self._atualizar_ibscbs_tot(root)

            if not todas_mods:
                return {
                    'success': True,
                    'xml_bytes': None,
                    'modificacoes': [],
                    'mensagem': "Nenhuma correção necessária — XML já está correto.",
                    'erro': ""
                }

            self._atualizar_totais(root)

            out = io.BytesIO()
            tree.write(out, encoding='utf-8', xml_declaration=True)

            return {
                'success': True,
                'xml_bytes': out.getvalue(),
                'modificacoes': todas_mods,
                'mensagem': "",
                'erro': ""
            }
        except Exception as e:
            return {
                'success': False,
                'xml_bytes': None,
                'modificacoes': [],
                'mensagem': "",
                'erro': str(e)
            }

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

    col1, col2, col3, col4, col5, col6 = st.columns(6)
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
    with col4:
        if st.button("🧾 Corretor de\nTotal NF-e", use_container_width=True):
            st.session_state.pagina = "total"
            st.rerun()
    with col5:
        if st.button("📑 Corretor de\nICMSSN500", use_container_width=True):
            st.session_state.pagina = "icms"
            st.rerun()
    with col6:
        if st.button("⚡ Corretor de\nRejeições NF-e", use_container_width=True):
            st.session_state.pagina = "rejeicoes"
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
                            del st.session_state.regras[id_deloitte]
                            st.stop()
                    st.success("Regra adicionada!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")
        with col5:
            st.write("")
            st.write("")

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
# PÁGINA CORRETOR DE TOTAL NF-e
# ========================
elif st.session_state.pagina == "total":
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

    st.markdown("<h1 style='text-align: center; margin-bottom: 0.5rem;'>Corretor total do XML</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Recalcula a soma dos itens e ajusta os campos vProd, vNF e vNFTot (se existir).</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Evita a Rejeicao: Total do Produto / Servico difere do somatório dos itens</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>(Para os casos onde foi verificado que o imposto do produto não está duplicado e mesmo assim a rejeição segue.)</p>", unsafe_allow_html=True)

    NS = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    ET.register_namespace('', "http://www.portalfiscal.inf.br/nfe")

    uploaded_files = st.file_uploader("📂 Selecione um ou mais arquivos XML", type="xml", accept_multiple_files=True)

    if uploaded_files:
        ajustados_zip = io.BytesIO()
        arquivos_para_zip = []

        for uploaded_file in uploaded_files:
            try:
                tree = ET.parse(uploaded_file)
                root = tree.getroot()

                soma_total = Decimal('0')
                for det in root.findall(".//ns:det", NS):
                    vprod_elem = det.find(".//ns:vProd", NS)
                    if vprod_elem is not None and vprod_elem.text:
                        try:
                            valor = Decimal(vprod_elem.text.strip())
                            soma_total += valor
                        except:
                            pass
                total_corrigido = soma_total.quantize(Decimal('0.01'))

                icms_tot = root.find(".//ns:ICMSTot", NS)
                if icms_tot is None:
                    st.warning(f"⚠️ {uploaded_file.name}: Tag <ICMSTot> não encontrada. Ignorado.")
                    continue

                vProd_elem = icms_tot.find("ns:vProd", NS)
                vProd_original = vProd_elem.text.strip() if vProd_elem is not None and vProd_elem.text else None

                ns = NS['ns']
                vNF_original = None
                for child in list(icms_tot):
                    if child.tag.lower() == f"{{{ns}}}vnf":
                        vNF_original = child.text.strip() if child.text else None
                        icms_tot.remove(child)
                        break

                precisa = False
                try:
                    if vProd_original is None or abs(Decimal(vProd_original) - total_corrigido) > Decimal('0.01'):
                        precisa = True
                    if vNF_original is None or abs(Decimal(vNF_original) - total_corrigido) > Decimal('0.01'):
                        precisa = True
                except:
                    precisa = True

                if not precisa:
                    st.info(f"ℹ️ {uploaded_file.name}: Total já está correto (R$ {total_corrigido:.2f}).")
                    continue

                if vProd_elem is None:
                    vProd_elem = ET.SubElement(icms_tot, "vProd")
                vProd_elem.text = f"{total_corrigido:.2f}"

                vNF_novo = ET.SubElement(icms_tot, "vNF")
                vNF_novo.text = f"{total_corrigido:.2f}"

                for elem in root.iter():
                    if 'vnftot' in elem.tag.lower():
                        elem.text = f"{total_corrigido:.2f}"

                out = io.BytesIO()
                tree.write(out, encoding="utf-8", xml_declaration=True)
                xml_data = out.getvalue()

                with st.expander(f"✅ {uploaded_file.name} - Corrigido"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption("🔴 VALORES ORIGINAIS")
                        st.code(f"vProd (ICMSTot): {vProd_original}\nvNF (ICMSTot): {vNF_original}", language="text")
                    with col2:
                        st.caption("🟢 VALORES CORRIGIDOS")
                        st.code(f"vProd (ICMSTot): {total_corrigido:.2f}\nvNF (ICMSTot): {total_corrigido:.2f}", language="text")
                    st.download_button(
                        label="📥 Baixar XML Corrigido",
                        data=xml_data,
                        file_name=f"XML_Corrigido_{uploaded_file.name}",
                        key=f"total_{uploaded_file.name}"
                    )
                arquivos_para_zip.append((f"XML_Corrigido_{uploaded_file.name}", xml_data))

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
                file_name="Pacote_Total_XML_Corrigido.zip",
                use_container_width=True,
                key="zip_total"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Nenhum arquivo precisou de correção. ZIP não será gerado.")

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

# ========================
# PÁGINA CORRETOR DE ICMSSN500 (UNIFICADA)
# ========================
elif st.session_state.pagina == "icms":
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

    st.markdown("<h1 style='text-align: center; margin-bottom: 0.5rem;'>Corretor de ICMSSN500</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Corrige duas rejeições relacionadas ao ICMS:</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>1) <code>&lt;ICMS /&gt;</code> vazio → substitui pelo bloco completo</p>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>2) Bloco ICMSSN500 com tags faltantes → adiciona campos obrigatórios zerados</p>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader("📂 Selecione um ou mais arquivos XML", type="xml", accept_multiple_files=True)

    if uploaded_files:
        ajustados_zip = io.BytesIO()
        arquivos_para_zip = []

        for uploaded_file in uploaded_files:
            try:
                xml_bytes = uploaded_file.read()

                xml_bytes, alteracoes_vazio = corrigir_icms_vazio(xml_bytes)
                xml_bytes, alteracoes_icmssn500 = corrigir_icmssn500(xml_bytes)

                alteracoes = alteracoes_vazio + alteracoes_icmssn500

                xml_str = xml_bytes.decode('utf-8').strip()

                try:
                    tree_temp = ET.parse(io.BytesIO(xml_bytes))
                    root_temp = tree_temp.getroot()
                    ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
                    nNF_elem = root_temp.find('.//ns:nNF', ns)
                    serie_elem = root_temp.find('.//ns:serie', ns)
                    numero_nota = nNF_elem.text if nNF_elem is not None else "N/A"
                    serie_nota = serie_elem.text if serie_elem is not None else "N/A"
                except:
                    numero_nota = "N/A"
                    serie_nota = "N/A"

                titulo_expander = f"📄 {uploaded_file.name}  |  NF {numero_nota}  |  Série {serie_nota}"
                with st.expander(titulo_expander, expanded=True):
                    st.markdown("**🔧 Alterações realizadas:**")
                    if not alteracoes:
                        st.code("✅ Nenhuma correção necessária.", language="text")
                    else:
                        st.code("\n".join(alteracoes), language="text")

                    st.divider()
                    st.markdown(f"**📌 Nota Fiscal:** {numero_nota}  |  **Série:** {serie_nota}")
                    st.markdown("**📝 XML corrigido (passe o mouse para copiar):**")
                    st.code(xml_str, language='xml')

                    st.download_button(
                        label="📥 Baixar XML corrigido",
                        data=xml_bytes,
                        file_name=f"ICMS_FIX_{uploaded_file.name}",
                        key=f"icms_download_{uploaded_file.name}"
                    )

                arquivos_para_zip.append((f"ICMS_FIX_{uploaded_file.name}", xml_bytes))

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
                file_name="Pacote_ICMS_FIX.zip",
                use_container_width=True,
                key="zip_icms"
            )
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Nenhum arquivo foi processado. ZIP não será gerado.")

# ========================
# PÁGINA CORRETOR DE REJEIÇÕES NF-e (SEFAZ + Reforma Tributária)
# ========================
elif st.session_state.pagina == "rejeicoes":
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

    st.markdown("<h1 style='text-align: center; margin-bottom: 0.5rem;'>Corretor de Rejeições NF-e</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #adb5bd;'>Correção automatizada de rejeições SEFAZ + Reforma Tributária (LC 214/2025)</p>", unsafe_allow_html=True)

    st.markdown("### 🎯 Selecione as rejeições a corrigir")
    st.caption("Marque uma ou mais rejeições. Apenas as selecionadas serão aplicadas em cada XML.")

    rejeicoes_selecionadas = []
    cols = st.columns(2)
    for idx, (chave, dados) in enumerate(REJEICOES_NFE.items()):
        with cols[idx % 2]:
            marcado = st.checkbox(
                f"{dados['icone']} {dados['titulo']}",
                key=f"rej_{chave}",
                help=dados['descricao']
            )
            if marcado:
                rejeicoes_selecionadas.append(chave)
            st.caption(dados['descricao'])
            st.markdown("---")

    uploaded_files = st.file_uploader("📂 Selecione um ou mais arquivos XML", type="xml", accept_multiple_files=True)

    if uploaded_files and rejeicoes_selecionadas:
        if st.button("▶  Corrigir XMLs", type="primary"):
            corretor = NFeCorrector()
            ajustados_zip = io.BytesIO()
            arquivos_para_zip = []

            for uploaded_file in uploaded_files:
                try:
                    xml_bytes = uploaded_file.read()

                    resultado = corretor.corrigir_bytes(xml_bytes, rejeicoes_selecionadas)

                    if not resultado['success']:
                        st.error(f"❌ {uploaded_file.name}: {resultado['erro']}")
                        continue

                    if resultado['xml_bytes'] is None:
                        with st.expander(f"○ {uploaded_file.name}", expanded=False):
                            st.info(resultado['mensagem'])
                        continue

                    mods = resultado['modificacoes']
                    xml_data = resultado['xml_bytes']

                    numero_nota = "N/A"
                    serie_nota = "N/A"
                    try:
                        tree_temp = ET.parse(io.BytesIO(xml_data))
                        root_temp = tree_temp.getroot()
                        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
                        nNF_elem = root_temp.find('.//ns:nNF', ns)
                        serie_elem = root_temp.find('.//ns:serie', ns)
                        if nNF_elem is not None and nNF_elem.text:
                            numero_nota = nNF_elem.text
                        if serie_elem is not None and serie_elem.text:
                            serie_nota = serie_elem.text
                    except:
                        pass

                    titulo = f"✅ {uploaded_file.name}  |  NF {numero_nota}  |  Série {serie_nota}  |  {len(mods)} ajuste(s)"

                    with st.expander(titulo, expanded=True):
                        st.markdown("**🔧 Alterações realizadas:**")
                        for m in mods:
                            linha = f"• {m.descricao}"
                            if m.detalhe:
                                linha += f"\n    {m.detalhe}"
                            st.code(linha, language="text")

                        st.divider()
                        st.download_button(
                            label="📥 Baixar XML Corrigido",
                            data=xml_data,
                            file_name=f"FIX_{uploaded_file.name}",
                            key=f"rej_dl_{uploaded_file.name}"
                        )

                    arquivos_para_zip.append((f"FIX_{uploaded_file.name}", xml_data))

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
                    file_name="Pacote_Rejeicoes_NFe_FIX.zip",
                    use_container_width=True,
                    key="zip_rejeicoes"
                )
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("ℹ️ Nenhum arquivo pôde ser processado.")

    elif uploaded_files and not rejeicoes_selecionadas:
        st.warning("⚠️ Marque pelo menos uma rejeição para continuar.")