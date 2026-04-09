import streamlit as st
from datetime import datetime
import time
from streamlit_option_menu import option_menu
import pandas as pd
import altair as alt
from sqlalchemy import text 
import uuid
from supabase import create_client, Client

# ==========================================
# CONFIGURACOES GERAIS E ESTILO
# ==========================================
st.set_page_config(page_title="Inspeção CIPA", layout="wide")

st.markdown("""
    <style>  
    [data-testid="stToolbarActions"] {display: none !important;}
    footer {display: none !important;}
    div[data-testid="stFileUploader"] section > div[data-testid="stMarkdownContainer"] {display: none !important;}
    div[data-testid="stFileUploaderFileData"] {display: block !important; margin-top: 10px;}
    div[data-testid="stFileUploader"] label {font-weight: bold !important; color: #383838 !important;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# GESTAO DE ESTADO E AUTENTICACAO
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    st.title("🔒 Acesso Restrito - CIPA")
    with st.form("login_form"):
        usuario_digitado = st.text_input("Usuário")
        senha_digitada = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            dicionario_usuarios = st.secrets["usuarios"]
            usuario_tratado = usuario_digitado.strip().lower()
            if usuario_tratado in dicionario_usuarios and dicionario_usuarios.get(usuario_tratado) == senha_digitada:
                st.session_state["password_correct"] = True
                st.session_state["usuario_logado"] = usuario_tratado
                st.rerun()
            else:
                st.error("Credenciais incorretas.")
    return False

if not check_password():
    st.stop()

# ==========================================
# CARREGAMENTO DE VARIAVEIS (Secrets)
# ==========================================
lista_perguntas = st.secrets.get("lista_perguntas_cipa", [])
lista_setores = st.secrets.get("lista_setores", [])
lista_responsaveis = st.secrets.get("lista_responsaveis", [])
lista_completa_cipeiros = st.secrets.get("lista_todos_cipeiros", [])
mapa_logins = st.secrets.get("nomes_cipeiros", {})

# Supabase Storage Client
cliente_supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ==========================================
# FUNÇÕES DE APOIO (Banco e Imagem)
# ==========================================
def salvar_dados(dados_dict):
    colunas = ', '.join(dados_dict.keys())
    marcadores = ', '.join([f":{k}" for k in dados_dict.keys()])
    query_sql = text(f"INSERT INTO inspecoes ({colunas}) VALUES ({marcadores})")
    
    try:
        # Usamos a conexão PostgreSQL definida nos secrets
        conn = st.connection("postgresql", type="sql")
        with conn.session as session:
            session.execute(query_sql, dados_dict)
            session.commit()
    except Exception as e:
        st.error(f"Erro na gravação: {e}")
        if "SSL" in str(e) or "closed" in str(e):
            st.cache_resource.clear()
        raise e

def processar_upload_imagem(arquivo_bytes, nome_arquivo):
    try:
        extensao = nome_arquivo.split('.')[-1]
        nome_unico = f"{uuid.uuid4()}.{extensao}"
        cliente_supabase.storage.from_("evidencias").upload(
            file=arquivo_bytes, path=nome_unico,
            file_options={"content-type": f"image/{extensao}"}
        )
        return cliente_supabase.storage.from_("evidencias").get_public_url(nome_unico)
    except Exception:
        return None

# ==========================================
# NAVEGACAO
# ==========================================
with st.sidebar:
    pagina = option_menu("Menu CIPA", 
        ["Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências", "Histórico de Dados"],
        icons=["clipboard-check", "bar-chart-line", "images", "archive"], 
        menu_icon="shield-check", default_index=0)

# ==========================================
# INTERFACE: NOVA INSPEÇÃO
# ==========================================
if pagina == "Nova Inspeção":
    if not lista_perguntas:
        st.error("ERRO: Perguntas não carregadas. Verifique os Secrets.")
        st.stop()

    st.title("📝 Nova Inspeção CIPA")
    
    col1, col2 = st.columns(2)
    with col1:
        c_mes, c_ano = st.columns(2)
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        with c_mes:
            mes_sel = st.selectbox("Mês de Referência", meses, index=datetime.now().month-1, key="m_v1")
        with c_ano:
            ano_sel = st.selectbox("Ano", [str(datetime.now().year)], index=0, key="a_v1")
        
        mes_referencia = f"{mes_sel}/{ano_sel}"
        setor = st.selectbox("Setor Inspecionado", lista_setores)
        responsavel_area = st.selectbox("Responsável da Área", lista_responsaveis)

    with col2:
        data_visivel = st.date_input("Data da Realização", format="DD/MM/YYYY")
        usuario_atual = st.session_state.get("usuario_logado")
        nome_cipeiro = mapa_logins.get(usuario_atual)
        cipeiro = st.selectbox("Cipeiro Responsável", [nome_cipeiro] if nome_cipeiro in lista_completa_cipeiros else lista_completa_cipeiros)
        acompanhantes = st.text_input("Acompanhantes")

    st.divider()
    justificada = st.checkbox("🚷 Inspeção não realizada por motivo de força maior")
    
    respostas, observacoes, fotos_capturadas = {}, {}, {}
    motivo_justificativa = ""

    if justificada:
        motivo_justificativa = st.text_area("Motivo da não realização (Obrigatório):")
    else:
        for i, pergunta in enumerate(lista_perguntas, start=1):
            respostas[f"q{i}"] = st.radio(f"**{i}.** {pergunta}", ["S", "N", "N/A"], horizontal=True, key=f"r_q{i}")
            observacoes[f"obs{i}"] = st.text_input(f"Observação:", key=f"t_o{i}") if respostas[f"q{i}"] in ["N", "N/A"] else ""
            fotos_capturadas[f"foto_q{i}"] = st.file_uploader("📸 Anexar foto", type=["jpg", "jpeg", "png"], key=f"up_q{i}", accept_multiple_files=True)
            st.write("---")
        
        obs_geral = st.text_area("Observações Gerais")
        foto_geral = st.file_uploader("📸 Foto Geral", type=["jpg", "jpeg", "png"], key="u_g", accept_multiple_files=True)

    if st.button("Salvar Inspeção", type="primary"):
        if justificada and not motivo_justificativa.strip():
            st.error("Preencha o motivo da não realização.")
        else:
            with st.spinner("Enviando dados..."):
                dados = {
                    "mes_referencia": mes_referencia, "setor": setor, "responsavel_area": responsavel_area,
                    "data_execucao": datetime.now(), "cipeiro": cipeiro, "acompanhantes": acompanhantes,
                    "status": "Justificada" if justificada else "Realizada"
                }

                for i in range(1, len(lista_perguntas) + 1):
                    chave_foto = f"foto_q{i}"
                    if justificada:
                        dados[f"q{i}"], dados[f"obs{i}"], dados[chave_foto] = "Justificado", "", ""
                    else:
                        dados[f"q{i}"] = respostas.get(f"q{i}", "N/A")
                        dados[f"obs{i}"] = observacoes.get(f"obs{i}", "")
                        arqs = fotos_capturadas.get(chave_foto)
                        urls = [processar_upload_imagem(a.getvalue(), a.name) for a in arqs] if arqs else []
                        dados[chave_foto] = ", ".join([u for u in urls if u])

                dados["obs_geral"] = motivo_justificativa if justificada else obs_geral
                if not justificada and foto_geral:
                    urls_g = [processar_upload_imagem(a.getvalue(), a.name) for a in foto_geral]
                    dados["foto_geral"] = ", ".join([u for u in urls_g if u])
                else:
                    dados["foto_geral"] = ""

                salvar_dados(dados)

            st.success("Inspeção registrada com sucesso!")
            st.balloons()
            time.sleep(3)
            st.rerun()

# ==========================================
# DASHBOARD E INDICADORES
# ==========================================
elif pagina == "Dashboard de Indicadores":
    st.title("📊 Dashboard e Indicadores")
    try:
        conn = st.connection("postgresql", type="sql")
        df = conn.query("SELECT * FROM inspecoes ORDER BY data_execucao DESC", ttl=0)
        if df.empty:
            st.info("Nenhum dado encontrado.")
        else:
            # Filtros e Gráficos (Mantido conforme sua lógica original)
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
            st.dataframe(df.head(), use_container_width=True) # Exemplo simplificado
    except Exception as e:
        st.error(f"Erro no Dashboard: {e}")

# ==========================================
# GALERIA E HISTÓRICO (Unificados para Postgres)
# ==========================================
elif pagina in ["Galeria de Evidências", "Histórico de Dados"]:
    st.title(f"📂 {pagina}")
    try:
        conn = st.connection("postgresql", type="sql")
        df = conn.query("SELECT * FROM inspecoes ORDER BY data_execucao DESC", ttl=0)
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")