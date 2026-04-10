import streamlit as st
from datetime import datetime
import time
from streamlit_option_menu import option_menu
import pandas as pd
import altair as alt
from sqlalchemy import text 
import uuid
from supabase import create_client, Client

esconder_estilo = """
    <style>  
    [data-testid="stToolbarActions"] {display: none !important;}
    footer {display: none !important;}
    
    /* 1. Esconde APENAS o texto de instrução e limites (200MB, formatos) */
    div[data-testid="stFileUploader"] section > div[data-testid="stMarkdownContainer"] {
        display: none !important;
    }

    /* 2. Mantém a lista de arquivos e miniaturas visível */
    div[data-testid="stFileUploaderFileData"] {
        display: block !important;
        margin-top: 10px;
    }

    /* 3. Ajusta o botão de upload para não sumir o sinal de "+" */
    div[data-testid="stFileUploader"] section {
        padding: 10px !important;
    }

    /* 4. Estilo do rótulo (Label) */
    div[data-testid="stFileUploader"] label {
        font-weight: bold !important;
        color: #383838 !important;
    }
    </style>
    """
st.markdown(esconder_estilo, unsafe_allow_html=True)

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
    
    max_tentativas = 2
    
    for tentativa in range(max_tentativas):
        try:
            # Puxa a conexão (pode estar em cache ou ser uma nova)
            conn_db = st.connection("postgresql", type="sql")
            with conn_db.session as session:
                session.execute(query_sql, dados_dict)
                session.commit()
            
            # Se chegou aqui, salvou com sucesso. Quebra o loop e segue a vida.
            break 
            
        except Exception as e:
            erro_str = str(e).lower()
            # Verifica se o erro foi de conexão caída/banco dormindo
            if ("ssl" in erro_str or "closed" in erro_str or "operationalerror" in erro_str) and tentativa < max_tentativas - 1:
                # O banco estava dormindo. Limpamos a conexão velha da memória...
                st.cache_resource.clear()
                # ... damos 1 segundo para o Neon inicializar o servidor ...
                time.sleep(1)
                # ... e o loop (continue) fará a segunda tentativa automaticamente.
                continue 
            else:
                # Se for um erro real (ex: coluna não existe) ou se falhou nas 2 tentativas
                st.error(f"Erro crítico ao salvar no banco: {e}")
                raise e

def carregar_dados():
    """
    Busca os dados no banco com tolerância estendida para o 'Cold Start' do Neon.
    """
    query_sql = "SELECT * FROM inspecoes ORDER BY data_execucao DESC"
    max_tentativas = 3 # Aumentamos para 3 tentativas para cobrir o tempo do Neon
    
    for tentativa in range(max_tentativas):
        try:
            conn_db = st.connection("postgresql", type="sql")
            df = conn_db.query(query_sql, ttl=0)
            return df
        except Exception as e:
            # Se falhou, limpamos o motor viciado da memória
            st.cache_resource.clear()
            
            if tentativa < max_tentativas - 1:
                # O Neon pode levar 4~5 segundos para acordar. Esperamos 3s a cada falha.
                import time
                time.sleep(3)
                continue
            else:
                # 🚨 SE FALHAR AS 3 VEZES, MOSTRA O ERRO REAL NA TELA
                st.error(f"⚠️ Detalhe Técnico do Erro: {e}")
                return pd.DataFrame()

def processar_upload_imagem(arquivo_bytes, nome_arquivo):
    """
    Realiza o upload e trata erros de limite de armazenamento.
    """
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
        # Se o erro for de limite ou permissao, loga o erro e avisa o usuario
        st.error("⚠️ Erro ao enviar foto: Limite de armazenamento atingido ou falha na conexão. Inspeção salva sem imagem")
        st.info("ℹ️ Por favor, comunique o Vitor Barbeiro sobre o ocorrido.")
        return None # Retorna None para o sistema ignorar a foto e seguir com o salvamento do texto

# ==========================================
# COMPONENTE DE NAVEGACAO LATERAL (Visual Restaurado)
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
    with col1:
        col_mes, col_ano = st.columns(2)
        
        meses_lista = [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ]

        # Identifica o mês atual (hoje é Abril, então será 3)
        indice_mes_atual = datetime.now().month - 1
        ano_atual_texto = str(datetime.now().year)

        with col_mes:
            mes_escolhido = st.selectbox(
                "Mês de Referência", 
                meses_lista, 
                index=indice_mes_atual,
                key="nova_chave_mes_v1"  # Força o Streamlit a resetar o cache
            )
            
        with col_ano:
            ano_escolhido = st.selectbox(
                "Ano", 
                [ano_atual_texto], 
                index=0,
                key="nova_chave_ano_v1"  # Força o Streamlit a resetar o cache
            )
        
        mes_referencia = f"{mes_escolhido}/{ano_escolhido}"
        setor = st.selectbox("Setor Inspecionado", lista_setores)
        responsavel_area = st.selectbox("Responsável da Área", lista_responsaveis)

    with col2:
        data_visivel = st.date_input("Data da Realização", format="DD/MM/YYYY")
        usuario_atual = st.session_state.get("usuario_logado")
        nome_vinculado = mapa_logins.get(usuario_atual)
        cipeiro = st.selectbox("Cipeiro Responsável", [nome_vinculado] if nome_vinculado in lista_completa_cipeiros else lista_completa_cipeiros)
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
            fotos_capturadas[f"foto_q{i}"] = st.file_uploader(
                "📸 Toque para tirar foto ou anexar (opcional)", 
                type=["jpg", "jpeg", "png"], 
                key=f"up_q{i}", 
                accept_multiple_files=True,
                label_visibility="visible"
            )
            st.write("---")
        
        obs_geral = st.text_area("Observações Gerais")
        foto_geral = st.file_uploader("📸 Foto Geral", type=["jpg", "jpeg", "png"], key="u_g", accept_multiple_files=True)

    if st.button("Salvar Inspeção", type="primary"):
        if justificada and not motivo_justificativa.strip():
            st.error("É obrigatório preencher o motivo da não realização para salvar o registro.")
        else:
            with st.spinner("Processando dados..."):
                dados_para_salvar = {
                    "mes_referencia": mes_referencia,
                    "setor": setor,
                    "responsavel_area": responsavel_area,
                    "data_execucao": datetime.now(),
                    "cipeiro": cipeiro,
                    "acompanhantes": acompanhantes,
                    "status": "Justificada" if justificada else "Realizada"
                }
                
                # Loop para processar as 31 questões
                for i in range(1, len(lista_perguntas) + 1):
                    chave_foto = f"foto_q{i}"
                    
                    if justificada:
                        dados_para_salvar[f"q{i}"] = "Justificado"
                        dados_para_salvar[f"obs{i}"] = ""
                        dados_para_salvar[chave_foto] = ""
                    else:
                        dados_para_salvar[f"q{i}"] = respostas.get(f"q{i}", "N/A")
                        dados_para_salvar[f"obs{i}"] = observacoes.get(f"obs{i}", "")
                        
                        # LOGICA DAS FOTOS COM FILTRO DE ERRO (Vitor Barbeiro)
                        arquivos_foto = fotos_capturadas.get(chave_foto)
                        if arquivos_foto:
                            urls_geradas = []
                            for arq in arquivos_foto:
                                url = processar_upload_imagem(arq.getvalue(), arq.name)
                                if url: # Só adiciona se o upload funcionou
                                    urls_geradas.append(url)
                            dados_para_salvar[chave_foto] = ", ".join(urls_geradas)
                        else:
                            dados_para_salvar[chave_foto] = ""
                
                # Observação Geral
                dados_para_salvar["obs_geral"] = motivo_justificativa if justificada else obs_geral
                
                # Foto Geral com filtro de erro
                if not justificada and foto_geral:
                    urls_gerais = []
                    for arq in foto_geral:
                        url_g = processar_upload_imagem(arq.getvalue(), arq.name)
                        if url_g:
                            urls_gerais.append(url_g)
                    dados_para_salvar["foto_geral"] = ", ".join(urls_gerais)
                else:
                    dados_para_salvar["foto_geral"] = ""
                
                # Envio final ao Neon
                salvar_dados(dados_para_salvar)
                
                # Criamos um container vazio para as mensagens
        placeholder = st.empty()
        
        with placeholder.container():
            if justificada:
                st.warning(f"Justificativa salva com sucesso!")
            else:
                st.success(f"Inspeção registrada com sucesso!")
                st.balloons()
        
        # Importante: o sleep deve ser pequeno no mobile para não cair a conexão
        import time
        time.sleep(3)

        # Limpamos o aviso antes de resetar
        placeholder.empty()

        # Forçamos o reset total da sessão
        st.rerun()

# ==========================================
# INTERFACE: DASHBOARD
# ==========================================
elif pagina == "Dashboard de Indicadores":
    st.title("📊 Dashboard e Indicadores")
    
    try:
        df = carregar_dados()

        if df.empty:
            st.info("Ainda não existem dados suficientes para gerar os gráficos. Realize uma inspeção primeiro.")
        else:
            # Tratamento de datas
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
            df['ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in str(x) else "Sem Ano")
            
            # --- LINHA DE FILTROS ---
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                anos_disp = sorted(df['ano'].unique().tolist(), reverse=True)
                ano_sel = st.selectbox("📅 Filtrar por Ano:", ["Todos"] + anos_disp)
            with col_f2:
                df_meses = df[df['ano'] == ano_sel] if ano_sel != "Todos" else df
                meses_brutos = df_meses['mes_referencia'].unique().tolist()
                
                # Lista de referência para forçar a ordem cronológica
                ordem_meses = [
                    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
                ]
                
                # Ordena a lista de meses brutos baseando-se na ordem do calendário
                # O split('/')[0] isola a palavra "Abril" de "Abril/2026" para achar a posição certa
                meses_disp = sorted(
                    meses_brutos, 
                    key=lambda x: ordem_meses.index(x.split('/')[0]) if x.split('/')[0] in ordem_meses else 99
                )
                
                mes_sel = st.selectbox("📆 Filtrar por Mês:", ["Todos"] + meses_disp)
            
            # Aplicação dos Filtros
            df_filtrado = df.copy()
            if ano_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['ano'] == ano_sel]
            if mes_sel != "Todos": df_filtrado = df_filtrado[df_filtrado['mes_referencia'] == mes_sel]
            
            st.divider()

            if not df_filtrado.empty:
                df_realizadas = df_filtrado[df_filtrado['status'] == 'Realizada'].copy()
                qtd_justificadas = len(df_filtrado[df_filtrado['status'] == 'Justificada'])

                st.subheader("Visão Geral do Período")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    st.metric("Inspeções Realizadas", len(df_realizadas))
                with c2:
                    st.metric("Inspeções Justificadas", qtd_justificadas)

                if not df_realizadas.empty:
                    # Cálculo de conformidade por linha (questões q1 a q31)
                    colunas_q = [f"q{i}" for i in range(1, len(lista_perguntas) + 1)]
                    
                    def calcular_nota(linha):
                        respostas = linha[colunas_q]
                        qtd_s = (respostas == 'S').sum()
                        qtd_na = (respostas == 'N/A').sum()
                        total_valido = len(lista_perguntas) - qtd_na
                        return (qtd_s / total_valido * 100) if total_valido > 0 else 0

                    df_realizadas['nota_porcentagem'] = df_realizadas.apply(calcular_nota, axis=1)
                    
                    # Médias e Destaque
                    media_geral = df_realizadas['nota_porcentagem'].mean()
                    df_medias_setor = df_realizadas.groupby('setor')['nota_porcentagem'].mean().reset_index()
                    setor_campeao = df_medias_setor.loc[df_medias_setor['nota_porcentagem'].idxmax()]

                    with c3:
                        st.metric("Média de Conformidade", f"{media_geral:.1f}%")
                    
                    st.write("") # Espaçador
                    st.markdown(f"""
                        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50;">
                            <span style="font-size: 14px; color: #5f6368;">🏆 SETOR DESTAQUE</span><br>
                            <span style="font-size: 18px; font-weight: bold; color: #1a1c1f; word-wrap: break-word;">
                                {setor_campeao['setor']}
                            </span><br>
                            <span style="font-size: 16px; color: #4CAF50;">{setor_campeao['nota_porcentagem']:.1f}% de conformidade</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.divider()
                    st.subheader("Desempenho por Setor")

                    # --- Lógica de Resumo de Nomes (P1, P2...) ---
                    df_medias_setor['setor_curto'] = df_medias_setor['setor'].str.replace("Prédio Nº 0", "P").str.replace("Prédio Nº ", "P").str.replace("Produção de ", "Prod. ")
                    df_medias_setor['rotulo'] = df_medias_setor['nota_porcentagem'].apply(lambda x: f"{x:.1f}%")

                    # Gráfico Altair com porcentagem visível
                    barras = alt.Chart(df_medias_setor).mark_bar(color="#4CAF50").encode(
                        y=alt.Y('setor_curto', title=None, sort='-x'),
                        x=alt.X('nota_porcentagem', title='Conformidade (%)', scale=alt.Scale(domain=[0, 115]))
                    )

                    textos = barras.mark_text(
                        align='left',
                        baseline='middle',
                        dx=5, 
                        fontSize=13,
                        fontWeight='bold',
                        color='gray'
                    ).encode(
                        text=alt.Text('rotulo:N')
                    )

                    st.altair_chart(barras + textos, use_container_width=True)
                else:
                    st.info("Nenhuma inspeção 'Realizada' no período filtrado (apenas justificativas).")
            else:
                st.warning("Nenhum registro encontrado para os filtros selecionados.")

    except Exception as e:
        st.error(f"Erro ao processar Dashboard: {e}")

# ==========================================
# INTERFACE: GALERIA DE EVIDENCIAS (Corrigida)
# ==========================================
elif pagina == "Galeria de Evidências":
    st.title("📸 Galeria de Evidências")
    try:
        df = carregar_dados()
        if df.empty:
            st.info("Ainda não foi registrada nenhuma inspeção.")
        else:
            df['data_execucao'] = pd.to_datetime(df['data_execucao'])
            # Mantém nomes completos nos filtros
            df['ref_ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in str(x) else "Sem Ano")
            df['ref_mes'] = df['mes_referencia'].apply(lambda x: x.split('/')[0] if '/' in str(x) else "Sem Mês")
            
            col1, col2 = st.columns(2)
            with col1:
                ano_sel = st.selectbox("Filtrar por Ano:", ["Todos"] + sorted(df['ref_ano'].unique().tolist(), reverse=True))
            with col2:
                ordem_meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                meses_no_df = [m for m in ordem_meses if m in df['ref_mes'].unique().tolist()]
                mes_sel = st.selectbox("Filtrar por Mês:", ["Todos"] + meses_no_df)

            df_f = df.copy()
            if ano_sel != "Todos": df_f = df_f[df_f['ref_ano'] == ano_sel]
            if mes_sel != "Todos": df_f = df_f[df_f['ref_mes'] == mes_sel]

            df_f['id_menu'] = df_f['data_execucao'].dt.strftime('%d/%m/%Y') + " | " + df_f['setor'] + " (" + df_f['cipeiro'] + ")"
            inspecao_sel = st.selectbox("Selecione a Inspeção:", ["-- Selecione --"] + df_f['id_menu'].tolist()[::-1])
            
            if inspecao_sel != "-- Selecione --":
                dados_linha = df_f[df_f['id_menu'] == inspecao_sel].iloc[0]
                tem_foto = False
                
                def renderizar_fotos_nativas(links_string):
                    links = [l.strip() for l in str(links_string).split(',') if l.strip() and "http" in l]
                    if links:
                        cols = st.columns(4)
                        for idx, link in enumerate(links):
                            with cols[idx % 4]:
                                st.image(link, use_container_width=True)
                                st.markdown(f'<a href="{link}" target="_blank" style="text-decoration:none; font-size:11px; color:gray;">🔍 Original</a>', unsafe_allow_html=True)

                if pd.notna(dados_linha.get('foto_geral')) and str(dados_linha['foto_geral']).strip() != "":
                    st.markdown("#### 📸 Foto Geral da Área")
                    renderizar_fotos_nativas(dados_linha['foto_geral'])
                    tem_foto = True
                    st.write("---")
                
                for i in range(1, len(lista_perguntas) + 1):
                    col_foto = f"foto_q{i}"
                    if pd.notna(dados_linha.get(col_foto)) and str(dados_linha[col_foto]).strip() != "":
                        st.markdown(f"**Item {i}:** {lista_perguntas[i-1]}")
                        if pd.notna(dados_linha.get(f"obs{i}")) and str(dados_linha[f"obs{i}"]).strip() != "":
                            st.caption(f"📝 *Obs:* {dados_linha[f'obs{i}']}")
                        renderizar_fotos_nativas(dados_linha[col_foto])
                        tem_foto = True
                        st.write("")
                        
                if not tem_foto:
                    st.info("Nenhuma evidência fotográfica nesta inspeção.")
    except Exception as e:
        st.error(f"Erro Galeria: {e}")

# ==========================================
# INTERFACE: HISTORICO
# ==========================================
elif pagina == "Histórico de Dados":
    st.title("📂 Histórico e Gestão")
    try:
        df = carregar_dados()
        if not df.empty:
            df_exibicao = df.copy()
            df_exibicao['data_execucao'] = pd.to_datetime(df_exibicao['data_execucao']).dt.strftime('%d/%m/%Y %H:%M')
            st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False, sep=';', decimal=',', encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(label="📥 Baixar dados em CSV", data=csv, file_name='historico_cipa.csv', mime='text/csv')
    except Exception as e:
        st.error(f"Erro Histórico: {e}")