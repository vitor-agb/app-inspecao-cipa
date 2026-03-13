import streamlit as st
from datetime import datetime
from streamlit_option_menu import option_menu
import pandas as pd
import altair as alt
from sqlalchemy import text 

# Configuração inicial da página
st.set_page_config(page_title="Inspeção CIPA", layout="wide")

esconder_estilo = """
    <style>  
    /* Oculta o atalho do GitHub (Fork) e o "Hosted with Streamlit" */
    [data-testid="stToolbarActions"] {display: none !important;}
    .viewerBadge_container {display: none !important;}
    .viewerBadge_link {display: none !important;}
    
    /* Oculta o rodapé inferior */
    footer {display: none !important;}
    </style>
    """
st.markdown(esconder_estilo, unsafe_allow_html=True)

# ==========================================
# SISTEMA DE LOGIN (TELA DE BLOQUEIO)
# ==========================================
def check_password():
    # Se a senha já foi validada antes, libera o acesso direto
    if st.session_state.get("password_correct", False):
        return True

    # Se não, exibe a tela de login
    st.title("🔒 Acesso Restrito - CIPA")
    senha_digitada = st.text_input("Digite a senha de acesso para continuar:", type="password")
    
    # Valida se o usuário clicou no botão OU apertou Enter
    if st.button("Entrar", type="primary") or senha_digitada:
        if senha_digitada == st.secrets["senha_acesso"]:
            st.session_state["password_correct"] = True
            st.rerun() # Atualiza a página instantaneamente para liberar o painel
        elif senha_digitada:
            st.error("😕 Senha incorreta. Tente novamente.")
            
    return False

# Se não estiver logado, bloqueia a leitura do resto do sistema
if not check_password():
    st.stop()


# ==========================================
# LISTA GLOBAL DE PERGUNTAS
# ==========================================
lista_perguntas = [
    "Os colaboradores atuam com comportamento seguro na operação?",
    "Os colaboradores estão usando os EPIs corretamente conforme sinalização?",
    "Existe procedimento para a atividade da área?",
    "Os colaboradores foram treinados na POP?",
    "Máquinas e Equipamentos estão com as proteções de segurança?",
    "Máquinas e Equipamentos estão com os sensores de segurança, se necessário?",
    "O local de trabalho se encontra organizado?",
    "As lixeiras do local estão identificadas e conservadas?",
    "O local de trabalho está limpo, organizado e livre de acúmulo de sujeira?",
    "Os materiais, paletes e equipamentos estão armazenados em seus locais corretos?",
    "A sinalização e as proteções de segurança do setor estão adequadas e em boas condições?",
    "As demarcações com faixa de segurança no piso estão conservadas?",
    "Os pisos, passarelas e áreas de circulação estão totalmente desobstruídos e seguros para o trânsito?",
    "As ferramentas estão adequadas para as atividades, estão conservadas?",
    "As extensões elétricas estão conservadas em condições de utilização?",
    "Corredores e saídas de emergência se encontram desobstruídos?",
    "Extintores/mangueiras de incêndio se encontram prontos para uso?",
    "Maca de emergência encontra-se pronto para uso?",
    "Os chuveiros e lava olhos de emergência estão funcionando e inspecionados?",
    "As instalações elétricas estão em boas condições de conservação?",
    "As tomadas elétricas estão identificadas (voltagem)?",
    "As iluminárias estão completas e sem lâmpadas queimadas?",
    "Os painéis elétricos estão fechados, desobstruídos, identificados?",
    "O kit de emergência encontra-se no local pronto para uso?",
    "Os funcionários estão realizando as tarefas sem a necessidade de esforço físico e com postura adequadas?",
    "O mobiliário está adequado ao posto de trabalho e a natureza da atividade?",
    "Os equipamentos de movimentação de materiais estão com os check list preenchidos?",
    "Os operadores de equipamento de movimentação de materiais com força motriz própria possuem curso de capacitação?",
    "Os produtos químicos, inflamáveis e tóxicos da área estão identificados e armazenados em local adequados?",
    "Os produtos estão armazenados sob bacia de contenção, embalagem adequada, local ventilado, afastado de fonte de ignição?",
    "As Fichas com Dados de Segurança (FDS) estão disponíveis nos setores / locais?"
]

# ==========================================
# FUNÇÕES DO BANCO DE DADOS (SUPABASE NA NUVEM)
# ==========================================
def salvar_dados(dados_dict):
    # Conecta com a nuvem
    conn = st.connection("supabase", type="sql")
    
    colunas = ', '.join(dados_dict.keys())
    marcadores = ', '.join([f":{k}" for k in dados_dict.keys()])
    
    query_sql = text(f"INSERT INTO inspecoes ({colunas}) VALUES ({marcadores})")
    
    # Abre uma sessão segura, envia os dados e salva (commit)
    with conn.session as session:
        session.execute(query_sql, dados_dict)
        session.commit()

# ==========================================
# MENU LATERAL
# ==========================================
with st.sidebar:
    pagina = option_menu(
        menu_title="Menu CIPA",
        options=["Nova Inspeção", "Dashboard de Indicadores", "Histórico de Dados"],
        icons=["clipboard-check", "bar-chart-line", "archive"],
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
# PÁGINA 1: NOVA INSPEÇÃO
# ==========================================
if pagina == "Nova Inspeção":
    st.title("📝 Nova Inspeção CIPA")
    
    st.subheader("Dados da Inspeção")
    col1, col2 = st.columns(2)
    
    with col1:
        col_mes, col_ano = st.columns(2)
        with col_mes:
            mes_escolhido = st.selectbox("Mês de Referência", [
                "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ])
        with col_ano:
            ano_escolhido = st.selectbox("Ano", ["2026", "2027", "2028", "2029", "2030"])
            
        mes_referencia = f"{mes_escolhido}/{ano_escolhido}"

        setor = st.selectbox("Setor Inspecionado", [
            "Prédio Nº 01 - Produção de Sólido", 
            "Prédio Nº 01 - Produção de Líquido / ADM",
            "Prédio Nº 02 - Produção de Sólido",
            "Prédio Nº 02 - Produção de Líquido / ADM", 
            "Prédio Nº 03 - Logística / ADM",
            "Prédio Nº 04 - Produção de Líquido / Laboratório",
            "Prédio Nº 04 - Refeitório / Sanitários",
            "Prédio Nº 01 e 05 - Laboratórios",
            "Prédio Nº 05 - Produção de Sólido / ADM",
            "Prédio Nº 06 - Qualidade / ADM / Workstation",
            "Prédio Nº 06 - Pesquisa & Desenvolvimento",
            "Prédio Nº 07 - Logística / ADM"  
        ])
        responsavel_area = st.selectbox("Responsável da Área", [
            "Mariana Galvão / Felipe Malan / Fernando",
            "Taffarel",
            "Ueslley da Silva",
            "Pablo Oliveira",
            "Gustavo Recchia",
            "Caique Rozada"
        ])
        
    with col2:
        data_execucao = st.date_input("Data da Realização", format="DD/MM/YYYY")
        cipeiro = st.selectbox("Cipeiro Responsável", [
            "Ana Claudia","Clarissa Arthur","Daiana de Oliveira","Isaias de Oliveira","Keila Silva","Leandro Alves","Mirelen da Silva","Rafael Zompero","Rosangela Rezende","Ueslley da Silva","Vitor Barbeiro","Weslen dos Santos"
        ])
        acompanhantes = st.text_input("Acompanhantes")

    st.divider()
    
    justificada = st.checkbox("🚷 Inspeção não realizada por motivo de força maior")
    
    respostas = {}
    observacoes = {}
    obs_geral = ""
    motivo_justificativa = ""

    if justificada:
        st.info("O questionário de verificação foi ocultado. Por favor, detalhe o motivo.")
        motivo_justificativa = st.text_area("Motivo da não realização (Obrigatório):")
    else:
        st.subheader("Checklist de Verificação")
        st.write("Selecione S (Sim/Conforme), N (Não/Inconforme) ou N/A (Não Aplicável).")
        
        for i, pergunta in enumerate(lista_perguntas, start=1):
            respostas[f"q{i}"] = st.radio(f"**{i}.** {pergunta}", ["S", "N", "N/A"], horizontal=True, key=f"radio_q{i}")
            
            if respostas[f"q{i}"] in ["N", "N/A"]:
                observacoes[f"obs{i}"] = st.text_input(f"Observação do item {i} (Obrigatório):", key=f"texto_obs{i}")
            else:
                observacoes[f"obs{i}"] = "" 
                
            st.write("---")
            
        obs_geral = st.text_area("Observações Gerais da Inspeção (Opcional)")

    st.divider()
    
    if st.button("Salvar Inspeção", type="primary"):
        if justificada and not motivo_justificativa.strip():
            st.error("É obrigatório preencher o motivo da não realização para salvar o registro.")
        else:
            dados_para_salvar = {
                "mes_referencia": mes_referencia,
                "setor": setor,
                "responsavel_area": responsavel_area,
                "data_execucao": str(data_execucao),
                "cipeiro": cipeiro,
                "acompanhantes": acompanhantes,
                "status": "Justificada" if justificada else "Realizada"
            }
            
            for i in range(1, 32):
                if justificada:
                    dados_para_salvar[f"q{i}"] = "Justificado"
                    dados_para_salvar[f"obs{i}"] = ""
                else:
                    dados_para_salvar[f"q{i}"] = respostas[f"q{i}"]
                    dados_para_salvar[f"obs{i}"] = observacoes[f"obs{i}"]
                
            dados_para_salvar["obs_geral"] = motivo_justificativa if justificada else obs_geral
            
            salvar_dados(dados_para_salvar)
            
            if justificada:
                st.warning(f"Registro de justificativa para o setor '{setor}' salvo com sucesso!")
            else:
                st.success(f"Inspeção do setor '{setor}' registrada com sucesso com as 31 questões!")
                st.balloons()

# ==========================================
# PÁGINA 2: DASHBOARD
# ==========================================
elif pagina == "Dashboard de Indicadores":
    st.title("📊 Dashboard e Indicadores")
    
    try:
        # Conecta no Supabase e puxa a tabela inteira (ttl=0 garante que os dados vêm sempre atualizados)
        conn = st.connection("supabase", type="sql")
        df = conn.query("SELECT * FROM inspecoes", ttl=0)

        if df.empty:
            st.info("Ainda não existem dados suficientes para gerar os gráficos. Realize uma inspeção primeiro na aba 'Nova Inspeção'.")
        else:
            df['ano'] = df['mes_referencia'].apply(lambda x: x.split('/')[-1] if '/' in x else x)
            
            col_filtro1, col_filtro2 = st.columns(2)
            
            with col_filtro1:
                anos_disponiveis = sorted(df['ano'].unique().tolist())
                ano_selecionado = st.selectbox("📅 Filtrar por Ano:", ["Todos os Anos"] + anos_disponiveis)
                
            with col_filtro2:
                if ano_selecionado != "Todos os Anos":
                    meses_disponiveis = df[df['ano'] == ano_selecionado]['mes_referencia'].unique().tolist()
                else:
                    meses_disponiveis = df['mes_referencia'].unique().tolist()
                    
                mes_selecionado = st.selectbox("📆 Filtrar por Mês:", ["Todos os Meses"] + meses_disponiveis)
            
            df_filtrado = df.copy()
            if ano_selecionado != "Todos os Anos":
                df_filtrado = df_filtrado[df_filtrado['ano'] == ano_selecionado]
            if mes_selecionado != "Todos os Meses":
                df_filtrado = df_filtrado[df_filtrado['mes_referencia'] == mes_selecionado]
                
            st.divider()

            if df_filtrado.empty:
                st.warning("Nenhum registro encontrado para os filtros selecionados.")
            else:
                df_realizadas = df_filtrado[df_filtrado['status'] == 'Realizada'].copy()
                qtd_justificadas = len(df_filtrado[df_filtrado['status'] == 'Justificada'])

                st.subheader("Visão Geral")
                
                col1, col2, col3 = st.columns(3) 
                
                with col1:
                    st.metric("Total de Inspeções Realizadas", len(df_realizadas))
                with col2:
                    st.metric("Inspeções Justificadas", qtd_justificadas)

                if not df_realizadas.empty:
                    colunas_q = [f"q{i}" for i in range(1, 32)]
                    
                    def calcular_nota(linha):
                        respostas = linha[colunas_q]
                        qtd_s = (respostas == 'S').sum()
                        qtd_na = (respostas == 'N/A').sum()
                        total_valido = 31 - qtd_na
                        if total_valido == 0:
                            return 0
                        return (qtd_s / total_valido) * 100

                    df_realizadas['nota_porcentagem'] = df_realizadas.apply(calcular_nota, axis=1)
                    
                    media_geral = df_realizadas['nota_porcentagem'].mean()
                    df_medias_setor = df_realizadas.groupby('setor')['nota_porcentagem'].mean()
                    setor_campeao = df_medias_setor.idxmax()
                    nota_campeao = df_medias_setor.max()

                    with col3:
                        st.metric("Média de Conformidade", f"{media_geral:.1f}%")
                    
                    st.write("") 
                    
                    st.metric("🏆 Setor Destaque", setor_campeao, f"{nota_campeao:.1f}% de acerto")
                    
                    st.divider()

                    st.subheader("Desempenho por Setor")
                    st.write("Média de conformidade (%) de cada área.")
                    
                    df_grafico = df_medias_setor.reset_index()
                    df_grafico.columns = ['setor', 'nota_porcentagem']
                    df_grafico['nota_porcentagem'] = df_grafico['nota_porcentagem'].round(1)
                    df_grafico['rotulo'] = df_grafico['nota_porcentagem'].apply(lambda x: f"{x:.1f}%")

                    # Truque visual para encurtar o nome no gráfico
                    df_grafico['setor_curto'] = df_grafico['setor'].str.replace("Prédio Nº 0", "P").str.replace("Prédio Nº ", "P").str.replace("Produção de", "Prod.")

                    barras = alt.Chart(df_grafico).mark_bar(color="#4CAF50").encode(
                        y=alt.Y('setor_curto', title=None, sort='-x', axis=alt.Axis(labelLimit=0)),
                        x=alt.X('nota_porcentagem', title='Conformidade (%)', scale=alt.Scale(domain=[0, 115]))
                    )

                    textos = barras.mark_text(
                        align='left',
                        baseline='middle',
                        dx=5, 
                        fontSize=14,
                        fontWeight='bold',
                        color='gray'
                    ).encode(
                        text=alt.Text('rotulo:N')
                    )

                    st.altair_chart(barras + textos, use_container_width=True)

                else:
                    with col3:
                        st.metric("Média de Conformidade", "0%")
                    st.info("Todos os registros encontrados para este filtro são justificativas de não realização. Não há dados percentuais para exibir.")

    except Exception as e:
        st.error(f"Erro ao processar os dados do Dashboard: {e}")

# ==========================================
# PÁGINA 3: HISTÓRICO
# ==========================================
elif pagina == "Histórico de Dados":
    st.title("📂 Histórico e Gestão")
    st.write("Abaixo estão todas as inspeções salvas no banco de dados.")

    try:
        conn = st.connection("supabase", type="sql")
        df = conn.query("SELECT * FROM inspecoes", ttl=0)

        if df.empty:
            st.info("Ainda não foi registrada nenhuma inspeção no sistema.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            st.divider()
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar dados em CSV",
                data=csv,
                file_name='historico_inspecoes_cipa.csv',
                mime='text/csv',
            )
            
    except Exception as e:
        st.error(f"Erro ao acessar o banco de dados: {e}")