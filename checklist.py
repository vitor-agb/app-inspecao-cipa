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
# CONFIGURACOES GERAIS DA APLICACAO
# ==========================================
st.set_page_config(page_title="Inspeção CIPA", layout="wide")

esconder_estilo = """
    <style>  
    [data-testid="stToolbarActions"] {display: none !important;}
    .viewerBadge_container {display: none !important;}
    .viewerBadge_link {display: none !important;}
    footer {display: none !important;}
    
    /* Limpeza visual do uploader de fotos */
    div[data-testid="stFileUploader"] section > div[data-testid="stMarkdownContainer"] {
        display: none !important;
    }
    div[data-testid="stFileUploaderFileData"] {
        display: block !important;
        margin-top: 10px;
    }
    div[data-testid="stFileUploader"] section {
        padding: 10px !important;
    }
    div[data-testid="stFileUploader"] label {
        font-weight: bold !important;
        color: #383838 !important;
    }
    </style>
    """
st.markdown(esconder_estilo, unsafe_allow_html=True)

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
        botao_entrar = st.form_submit_button("Entrar", type="primary")
    if botao_entrar:
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
# CARREGAMENTO DE VARIAVEIS E CLIENTES API
# ==========================================
lista_perguntas = st.secrets.get("lista_perguntas_cipa", [])
lista_setores = st.secrets.get("lista_setores", [])
lista_responsaveis = st.secrets.get("lista_responsaveis", [])
lista_completa_cipeiros = st.secrets.get("lista_todos_cipeiros", [])
mapa_logins = st.secrets.get("nomes_cipeiros", {})

url_storage: str = st.secrets["SUPABASE_URL"]
key_storage: str = st.secrets["SUPABASE_KEY"]
cliente_supabase: Client = create_client(url_storage, key_storage)

# ==========================================
# INTEGRACOES COM BANCO DE DADOS E STORAGE
# ==========================================
def salvar_dados(dados_dict):
    colunas = ', '.join(dados_dict.keys())
    marcadores = ', '.join([f":{k}" for k in dados_dict.keys()])
    query_sql = text(f"INSERT INTO inspecoes ({colunas}) VALUES ({marcadores})")
    
    try:
        # Usamos uma conexão direta e limpa para evitar erro de SSL
        conn_db = st.connection("postgresql", type="sql")
        with conn_db.session as session:
            session.execute(query_sql, dados_dict)
            session.commit()
    except Exception as e:
        st.error(f"Erro ao salvar no banco de dados: {e}")
        if "SSL" in str(e) or "closed" in str(e):
             st.cache_resource.clear()
        raise e

def processar_upload_imagem(arquivo_bytes, nome_arquivo):
    try:
        extensao = nome_arquivo.split('.')[-1]
        nome_unico = f"{uuid.uuid4()}.{extensao}"
        cliente_supabase.storage.from_("evidencias").upload(
            file=arquivo_bytes,
            path=nome_unico,
            file_options={"content-type": f"image/{extensao}"}
        )
        return cliente_supabase.storage.from_("evidencias").get_public_url(nome_unico)
    except Exception as e:
        st.error(f"⚠️ Erro ao enviar foto: {e}")
        return None

# ==========================================
# COMPONENTE DE NAVEGACAO LATERAL
# ==========================================
with st.sidebar:
    pagina = option_menu(
        menu_title="Menu CIPA",
        options=["Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências", "Histórico de Dados"],
        icons=["clipboard-check", "bar-chart-line", "images", "archive"],
        menu_icon="shield-check",
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "gray", "font-size": "18px"}, 
            "nav-link": {
                "font-size": "16px", 
                "text-align": "left", 
                "margin":"0px", 
                "--hover-color": "#4CAF50"
            },
            "nav-link-selected": {
                "background-color": "#FFFFFF",
                "color": "black"
            },
        }
    )

# ==========================================
# INTERFACE: FORMULARIO DE INSERCAO DE DADOS
# ==========================================
if pagina == "Nova Inspeção":
    st.title("📝 Nova Inspeção CIPA")
    
    col1, col2 = st.columns(2)
    with col1:
        col_mes, col_ano = st.columns(2)
        meses_lista = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        indice_mes_atual = datetime.now().month - 1
        ano_atual_texto = str(datetime.now().year)

        with col_mes:
            mes_escolhido = st.selectbox("Mês de Referência", meses_lista, index=indice_mes_atual, key="sel_mes_v2")
        with col_ano:
            ano_escolhido = st.selectbox("Ano", [ano_atual_texto], index=0, key="sel_ano_v2")
        
        mes_referencia = f"{mes_escolhido}/{ano_escolhido}"
        setor = st.selectbox("Setor Inspecionado", lista_setores)
        responsavel_area = st.selectbox("Responsável da Área", lista_responsaveis)

    with col2:
        data_visivel = st.date_input("Data da Realização", format="DD/MM/YYYY")
        usuario_atual = st.session_state.get("usuario_logado")
        nome_vinculado = mapa_logins.get(usuario_atual)
        opcoes_cipeiro = [nome_vinculado] if nome_vinculado in lista_completa_cipeiros else lista_completa_cipeiros
        cipeiro = st.selectbox("Cipeiro Responsável", opcoes_cipeiro)
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
            fotos_capturadas[f"foto_q{i}"] = st.file_uploader("📸 Foto/Anexo", type=["jpg", "jpeg", "png"], key=f"up_q{i}", accept_multiple_files=True)
            st.write("---")
        
        obs_geral = st.text_area("Observações Gerais")
        foto_geral = st.file_uploader("📸 Foto Geral", type=["jpg", "jpeg", "png"], key="u_g", accept_multiple_files=True)
    lista_perguntas = st.secrets.get("lista_perguntas_cipa", [])

    # LINHAS DE TESTE (TERMÔMETRO):
    if not lista_perguntas:
        st.error("🚨 ATENÇÃO: A lista de perguntas nos Secrets está VAZIA ou com ERRO de formato!")
    else:
        st.info(f"✅ Sucesso: {len(lista_perguntas)} perguntas carregadas dos Secrets.")

    if st.button("Salvar Inspeção", type="primary"):
        if justificada and not motivo_justificativa.strip():
            st.error("É obrigatório preencher o motivo da não realização.")
        else:
            with st.spinner("Processando dados e enviando evidências..."):
                dados_para_salvar = {
                    "mes_referencia": mes_referencia, "setor": setor, "responsavel_area": responsavel_area,
                    "data_execucao": datetime.now(), "cipeiro": cipeiro, "acompanhantes": acompanhantes,
                    "status": "Justificada" if justificada else "Realizada"
                }
                
                for i in range(1, len(lista_perguntas) + 1):
                    chave_foto = f"foto_q{i}"
                    if justificada:
                        dados_para_salvar[f"q{i}"], dados_para_salvar[f"obs{i}"], dados_para_salvar[chave_foto] = "Justificado", "", ""
                    else:
                        dados_para_salvar[f"q{i}"] = respostas.get(f"q{i}", "N/A")
                        dados_para_salvar[f"obs{i}"] = observacoes.get(f"obs{i}", "")
                        arquivos = fotos_capturadas.get(chave_foto)
                        urls = [processar_upload_imagem(a.getvalue(), a.name) for a in arquivos] if arquivos else []
                        dados_para_salvar[chave_foto] = ", ".join([u for u in urls if u])

                dados_para_salvar["obs_geral"] = motivo_justificativa if justificada else obs_geral
                if not justificada and foto_geral:
                    urls_g = [processar_upload_imagem(a.getvalue(), a.name) for a in foto_geral]
                    dados_para_salvar["foto_geral"] = ", ".join([u for u in urls_g if u])
                else:
                    dados_para_salvar["foto_geral"] = ""

                salvar_dados(dados_para_salvar)
            
            # Feedback fora do spinner para sumir a mensagem de "Processando"
            placeholder = st.empty()
            with placeholder.container():
                if justificada: st.warning("✅ Justificativa salva com sucesso!")
                else:
                    st.success("🚀 Inspeção registrada com sucesso!")
                    st.balloons()
            
            time.sleep(3)
            placeholder.empty()
            st.rerun()

# ==========================================
# INTERFACE: DASHBOARD
# ==========================================
elif pagina == "Dashboard de Indicadores":
    st.title("📊 Dashboard e Indicadores")
    try:
        conn_db = st.connection("postgresql", type="sql")
        df = conn_db.query("SELECT * FROM inspecoes ORDER BY data_execucao DESC", ttl=0)

        if df.empty:
            st.info("Ainda não existem dados suficientes.")
        else:
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
            df['ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in str(x) else "Sem Ano")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                anos_disp = sorted(df['ano'].unique().tolist(), reverse=True)
                ano_sel = st.selectbox("📅 Filtrar por Ano:", ["Todos"] + anos_disp)
            with col_f2:
                df_meses = df[df['ano'] == ano_sel] if ano_sel != "Todos" else df
                meses_disp = df_meses['mes_referencia'].unique().tolist()
                mes_sel = st.selectbox("📆 Filtrar por Mês:", ["Todos"] + meses_disp)
            
            df_filtrado = df.copy()
            if ano_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['ano'] == ano_sel]
            if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['mes_referencia'] == mes_sel]
            
            st.divider()

            if not df_filtrado.empty:
                df_realizadas = df_filtrado[df_filtrado['status'] == 'Realizada'].copy()
                qtd_justificadas = len(df_filtrado[df_filtrado['status'] == 'Justificada'])

                st.subheader("Visão Geral do Período")
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("Inspeções Realizadas", len(df_realizadas))
                with c2: st.metric("Inspeções Justificadas", qtd_justificadas)

                if not df_realizadas.empty:
                    colunas_q = [f"q{i}" for i in range(1, len(lista_perguntas) + 1)]
                    def calcular_nota(linha):
                        res = linha[colunas_q]
                        qtd_s = (res == 'S').sum()
                        qtd_na = (res == 'N/A').sum()
                        total = len(lista_perguntas) - qtd_na
                        return (qtd_s / total * 100) if total > 0 else 0

                    df_realizadas['nota_porcentagem'] = df_realizadas.apply(calcular_nota, axis=1)
                    media_geral = df_realizadas['nota_porcentagem'].mean()
                    df_medias_setor = df_realizadas.groupby('setor')['nota_porcentagem'].mean().reset_index()
                    setor_campeao = df_medias_setor.loc[df_medias_setor['nota_porcentagem'].idxmax()]

                    with c3: st.metric("Média de Conformidade", f"{media_geral:.1f}%")
                    
                    st.markdown(f"""
                        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                            <span style="font-size: 14px; color: #5f6368;">🏆 SETOR DESTAQUE</span><br>
                            <span style="font-size: 18px; font-weight: bold; color: #1a1c1f;">{setor_campeao['setor']}</span><br>
                            <span style="font-size: 16px; color: #4CAF50;">{setor_campeao['nota_porcentagem']:.1f}% de conformidade</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.divider()
                    df_medias_setor['setor_curto'] = df_medias_setor['setor'].str.replace("Prédio Nº ", "P").str.replace("Produção de ", "Prod. ")
                    df_medias_setor['rotulo'] = df_medias_setor['nota_porcentagem'].apply(lambda x: f"{x:.1f}%")

                    barras = alt.Chart(df_medias_setor).mark_bar(color="#4CAF50").encode(
                        y=alt.Y('setor_curto', title=None, sort='-x'),
                        x=alt.X('nota_porcentagem', title='Conformidade (%)', scale=alt.Scale(domain=[0, 115]))
                    )
                    textos = barras.mark_text(align='left', dx=5, fontWeight='bold', color='gray').encode(text='rotulo:N')
                    st.altair_chart(barras + textos, use_container_width=True)
    except Exception as e: st.error(f"Erro Dashboard: {e}")

# ==========================================
# INTERFACE: GALERIA DE EVIDENCIAS
# ==========================================
elif pagina == "Galeria de Evidências":
    st.title("📸 Galeria de Evidências")
    try:
        conn_db = st.connection("postgresql", type="sql")
        df = conn_db.query("SELECT * FROM inspecoes ORDER BY data_execucao DESC", ttl=0)
        if df.empty: st.info("Sem inspeções registradas.")
        else:
            df['ref_ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in str(x) else "Sem Ano")
            df['ref_mes'] = df['mes_referencia'].apply(lambda x: x.split('/')[0] if '/' in str(x) else "Sem Mês")
            
            c1, c2 = st.columns(2)
            with c1: ano_sel = st.selectbox("Ano:", ["Todos"] + sorted(df['ref_ano'].unique().tolist(), reverse=True))
            with c2: 
                ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                meses_df = [m for m in ordem if m in df['ref_mes'].unique().tolist()]
                mes_sel = st.selectbox("Mês:", ["Todos"] + meses_df)

            df_f = df.copy()
            if ano_sel != "Todos": df_f = df_f[df_f['ref_ano'] == ano_sel]
            if mes_sel != "Todos": df_f = df_f[df_f['ref_mes'] == mes_sel]

            df_f['id_menu'] = pd.to_datetime(df_f['data_execucao']).dt.strftime('%d/%m/%Y') + " | " + df_f['setor']
            inspecao_sel = st.selectbox("Selecione a Inspeção:", ["-- Selecione --"] + df_f['id_menu'].tolist())
            
            if inspecao_sel != "-- Selecione --":
                linha = df_f[df_f['id_menu'] == inspecao_sel].iloc[0]
                def renderizar(links):
                    lks = [l.strip() for l in str(links).split(',') if "http" in l]
                    if lks:
                        cols = st.columns(4)
                        for idx, lk in enumerate(lks):
                            with cols[idx % 4]: st.image(lk, use_container_width=True)

                if str(linha.get('foto_geral')).strip():
                    st.markdown("#### 📸 Foto Geral")
                    renderizar(linha['foto_geral'])
                
                for i in range(1, len(lista_perguntas) + 1):
                    col_f = f"foto_q{i}"
                    if str(linha.get(col_f)).strip():
                        st.markdown(f"**Item {i}:** {lista_perguntas[i-1]}")
                        renderizar(linha[col_f])
    except Exception as e: st.error(f"Erro Galeria: {e}")

# ==========================================
# INTERFACE: HISTORICO
# ==========================================
elif pagina == "Histórico de Dados":
    st.title("📂 Histórico e Gestão")
    try:
        conn_db = st.connection("postgresql", type="sql")
        df = conn_db.query("SELECT * FROM inspecoes ORDER BY data_execucao DESC", ttl=0)
        if not df.empty:
            df_ex = df.copy()
            df_ex['data_execucao'] = pd.to_datetime(df_ex['data_execucao']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df_ex, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Baixar CSV", csv, 'historico_cipa.csv', 'text/csv')
    except Exception as e: st.error(f"Erro Histórico: {e}")