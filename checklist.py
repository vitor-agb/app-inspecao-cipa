import streamlit as st
from datetime import datetime
import time
from streamlit_option_menu import option_menu
import pandas as pd
import altair as alt
from sqlalchemy import text 
import cloudinary
import cloudinary.uploader

# ==========================================
# CONFIGURAÇÕES GERAIS E ESTILO
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
# AUTENTICAÇÃO
# ==========================================
def check_password():
    if st.session_state.get("password_correct", False):
        return True
    st.title("🔒 Acesso Restrito - CIPA")
    with st.form("login_form"):
        usuario_digitado = st.text_input("Usuário")
        senha_digitada = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            dicionario_usuarios = st.secrets.get("usuarios", {})
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
# VARIÁVEIS DE AMBIENTE
# ==========================================
lista_perguntas = st.secrets.get("lista_perguntas_cipa", [])
lista_setores = st.secrets.get("lista_setores", [])
lista_responsaveis = st.secrets.get("lista_responsaveis", [])
lista_completa_cipeiros = st.secrets.get("lista_todos_cipeiros", [])
mapa_logins = st.secrets.get("nomes_cipeiros", {})

# ==========================================
# CONFIGURAÇÃO CLOUDINARY
# ==========================================
cloudinary.config(
    cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
    api_key=st.secrets["CLOUDINARY_API_KEY"],
    api_secret=st.secrets["CLOUDINARY_API_SECRET"],
    secure=True
)

# ==========================================
# FUNÇÕES DE BANCO E STORAGE
# ==========================================
def salvar_dados(dados_dict):
    colunas = ', '.join(dados_dict.keys())
    marcadores = ', '.join([f":{k}" for k in dados_dict.keys()])
    query_sql = text(f"INSERT INTO inspecoes ({colunas}) VALUES ({marcadores})")
    
    max_tentativas = 2
    for tentativa in range(max_tentativas):
        try:
            conn_db = st.connection("postgresql", type="sql")
            with conn_db.session as session:
                session.execute(query_sql, dados_dict)
                session.commit()
            break 
        except Exception as e:
            erro_str = str(e).lower()
            if ("ssl" in erro_str or "closed" in erro_str or "operationalerror" in erro_str) and tentativa < max_tentativas - 1:
                st.cache_resource.clear()
                time.sleep(1.5)
                continue 
            else:
                st.error(f"Erro crítico ao salvar no banco de dados: {e}")
                raise e

def carregar_dados():
    query_sql = "SELECT * FROM inspecoes ORDER BY data_execucao DESC"
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        try:
            conn_db = st.connection("postgresql", type="sql")
            df = conn_db.query(query_sql, ttl=0)
            return df
        except Exception as e:
            st.cache_resource.clear()
            if tentativa < max_tentativas - 1:
                time.sleep(3)
                continue
            else:
                st.error(f"Falha de conexão com o banco de dados: {e}")
                return pd.DataFrame()

def processar_upload_imagem(arquivo_bytes, nome_arquivo):
    try:
        resposta = cloudinary.uploader.upload(arquivo_bytes)
        return resposta.get("secure_url"), None
    except Exception as e:
        return None, str(e)

# ==========================================
# NAVEGAÇÃO
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
    
    # 1. TELA DE SUCESSO / FEEDBACK
    if st.session_state.get("tela_sucesso", False):
        st.title("✅ Inspeção Concluída!")
        st.success("O formulário principal foi salvo com sucesso no banco de dados.")
        
        # Puxa os erros que guardamos na memória
        alertas = st.session_state.get("alertas_upload", [])
        
        if alertas:
            st.warning("⚠️ O formulário foi salvo, mas algumas imagens falharam e não foram anexadas:")
            for alerta in alertas:
                st.error(alerta)
            st.info("ℹ️ Você pode ignorar este aviso se as imagens não forem críticas, ou tentar fazer a inspeção novamente mais tarde.")
        else:
            # Só solta balões se TUDO deu 100% certo (dados + imagens)
            st.balloons()
            
        st.divider()
        if st.button("⬅️ Fazer Nova Inspeção", type="primary"):
            st.session_state["tela_sucesso"] = False
            st.session_state["alertas_upload"] = [] # Limpa os alertas
            st.rerun()
            
    # 2. FORMULÁRIO NORMAL
    else:
        if not lista_perguntas:
            st.error("Erro de configuração: 'lista_perguntas_cipa' não localizada.")
            st.stop()

        st.title("📝 Nova Inspeção CIPA")
        
        # ... (SEU CÓDIGO DE COLUNAS E PERGUNTAS CONTINUA IGUAL AQUI) ...
        col1, col2 = st.columns(2)
        with col1:
            c_mes, c_ano = st.columns(2)
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            with c_mes: mes_sel = st.selectbox("Mês de Referência", meses, index=datetime.now().month-1, key="m_v1")
            with c_ano: ano_sel = st.selectbox("Ano", [str(datetime.now().year)], index=0, key="a_v1")
            
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
                st.error("Preenchimento obrigatório: Motivo da não realização.")
            else:
                with st.spinner("Processando dados e enviando imagens. Por favor, aguarde..."):
                    dados = {
                        "mes_referencia": mes_referencia, "setor": setor, "responsavel_area": responsavel_area,
                        "data_execucao": datetime.now(), "cipeiro": cipeiro, "acompanhantes": acompanhantes,
                        "status": "Justificada" if justificada else "Realizada"
                    }
                    
                    lista_de_erros = [] # Vai guardar os erros de imagem

                    for i in range(1, len(lista_perguntas) + 1):
                        chave_foto = f"foto_q{i}"
                        if justificada:
                            dados[f"q{i}"], dados[f"obs{i}"], dados[chave_foto] = "Justificado", "", ""
                        else:
                            dados[f"q{i}"] = respostas.get(f"q{i}", "N/A")
                            dados[f"obs{i}"] = observacoes.get(f"obs{i}", "")
                            arqs = fotos_capturadas.get(chave_foto)
                            
                            urls = []
                            if arqs:
                                for a in arqs:
                                    url, erro = processar_upload_imagem(a.getvalue(), a.name)
                                    if url:
                                        urls.append(url)
                                    if erro:
                                        lista_de_erros.append(f"Erro na Questão {i} ({a.name}): {erro}")
                                        
                            dados[chave_foto] = ", ".join([u for u in urls if u])

                    dados["obs_geral"] = motivo_justificativa if justificada else obs_geral
                    if not justificada and foto_geral:
                        urls_g = []
                        for a in foto_geral:
                            url_g, erro_g = processar_upload_imagem(a.getvalue(), a.name)
                            if url_g:
                                urls_g.append(url_g)
                            if erro_g:
                                lista_de_erros.append(f"Erro na Foto Geral ({a.name}): {erro_g}")
                        dados["foto_geral"] = ", ".join([u for u in urls_g if u])
                    else:
                        dados["foto_geral"] = ""

                    salvar_dados(dados)

                # Salva os erros na memória para a tela seguinte
                st.session_state["alertas_upload"] = lista_de_erros
                st.session_state["tela_sucesso"] = True
                st.rerun()

# ==========================================
# DASHBOARD E INDICADORES
# ==========================================
elif pagina == "Dashboard de Indicadores":
    st.title("📊 Dashboard e Indicadores")
    try:
        df = carregar_dados()
        if df.empty:
            st.info("Aguardando inserção de dados no sistema.")
        else:
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
            df['ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in str(x) else "Sem Ano")
            
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                anos_disp = sorted(df['ano'].unique().tolist(), reverse=True)
                ano_sel = st.selectbox("📅 Filtrar por Ano:", ["Todos"] + anos_disp)
            with col_f2:
                df_meses = df[df['ano'] == ano_sel] if ano_sel != "Todos" else df
                meses_brutos = df_meses['mes_referencia'].unique().tolist()
                
                # Ordenação cronológica
                ordem_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                meses_disp = sorted(meses_brutos, key=lambda x: ordem_meses.index(x.split('/')[0]) if x.split('/')[0] in ordem_meses else 99)
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
            else:
                st.info("Registros insuficientes para aplicação dos filtros selecionados.")
            
            # MATRIZ DE PARTICIPAÇÃO
            st.divider()
            st.subheader(f"Matriz de Engajamento Anual ({ano_sel})")
            
            df_matriz = df[df['ano'] == ano_sel].copy() if ano_sel != "Todos" else df.copy()

            if not df_matriz.empty:
                df_matriz['mes_nome'] = df_matriz['mes_referencia'].apply(lambda x: str(x).split('/')[0])
                
                tabela_dinamica = df_matriz.groupby(['cipeiro', 'mes_nome'])['status'].apply(
                    lambda x: '✅' if 'Realizada' in x.values else '🚷'
                ).unstack(fill_value='❌')
                
                for mes in ordem_meses:
                    if mes not in tabela_dinamica.columns:
                        tabela_dinamica[mes] = '❌'
                        
                tabela_dinamica = tabela_dinamica[ordem_meses]
                
                cipeiros_faltantes = [c for c in lista_completa_cipeiros if c not in tabela_dinamica.index]
                for c in cipeiros_faltantes:
                    tabela_dinamica.loc[c] = ['❌'] * 12
                    
                tabela_dinamica = tabela_dinamica.sort_index().reset_index()
                tabela_dinamica.rename(columns={'cipeiro': 'Nome do Cipeiro'}, inplace=True)
                
                st.dataframe(
                    tabela_dinamica, 
                    use_container_width=True, 
                    hide_index=True
                )
                st.caption("**Legenda:** ✅ Inspeção Realizada | 🚷 Ausência Justificada | ❌ Pendente / Não Realizada")

    except Exception as e:
        st.error(f"Erro de processamento: {e}")

# ==========================================
# GALERIA DE EVIDENCIAS
# ==========================================
elif pagina == "Galeria de Evidências":
    st.title("📸 Galeria de Evidências")
    try:
        df = carregar_dados()
        if df.empty:
            st.info("Galeria vazia.")
        else:
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
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

            df_f['id_menu'] = df_f['data_execucao'].dt.strftime('%d/%m/%Y %H:%M') + " | " + df_f['setor'] + " (" + df_f['cipeiro'] + ")"
            inspecao_sel = st.selectbox("Selecione a Inspeção:", ["-- Selecione --"] + df_f['id_menu'].tolist())
            
            if inspecao_sel != "-- Selecione --":
                linha = df_f[df_f['id_menu'] == inspecao_sel].iloc[0]
                def renderizar(links):
                    lks = [l.strip() for l in str(links).split(',') if "http" in l]
                    if lks:
                        cols = st.columns(4)
                        for idx, lk in enumerate(lks):
                            with cols[idx % 4]:
                                st.image(lk, use_container_width=True)
                                st.markdown(f'<a href="{lk}" target="_blank" style="text-decoration:none; font-size:11px; color:gray;">🔍 Original</a>', unsafe_allow_html=True)

                if str(linha.get('foto_geral')).strip():
                    st.markdown("#### 📸 Foto Geral")
                    renderizar(linha['foto_geral'])
                
                for i in range(1, len(lista_perguntas) + 1):
                    col_f = f"foto_q{i}"
                    if str(linha.get(col_f)).strip():
                        st.markdown(f"**Item {i}:** {lista_perguntas[i-1]}")
                        if pd.notna(linha.get(f"obs{i}")) and str(linha[f"obs{i}"]).strip() != "":
                            st.caption(f"📝 *Obs:* {linha[f'obs{i}']}")
                        renderizar(linha[col_f])
    except Exception as e:
        st.error(f"Erro de processamento: {e}")

# ==========================================
# HISTÓRICO DE DADOS
# ==========================================
elif pagina == "Histórico de Dados":
    st.title("📂 Histórico e Gestão")
    try:
        df = carregar_dados()
        if not df.empty:
            df_ex = df.copy()
            df_ex['data_execucao'] = pd.to_datetime(df_ex['data_execucao']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df_ex, use_container_width=True, hide_index=True)
            csv = df.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Baixar CSV", csv, 'historico_cipa.csv', 'text/csv')
    except Exception as e:
        st.error(f"Erro de processamento: {e}")