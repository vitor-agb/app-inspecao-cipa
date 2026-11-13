import streamlit as st
from datetime import datetime, timedelta
import hashlib
import hmac
import io
import re
import time
import unicodedata
from PIL import Image, ImageOps
from streamlit_option_menu import option_menu
import pandas as pd
import altair as alt
from sqlalchemy import text 
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Limites de upload: tamanho máximo do arquivo original e parâmetros da versão redimensionada enviada ao Cloudinary.
LIMITE_BYTES = 10 * 1024 * 1024
LADO_MAXIMO_PX = 1600
QUALIDADE_JPEG = 80

# Janela (segundos) em que um novo registro do mesmo cipeiro, setor, mês e status é tratado como envio duplicado.
JANELA_DUPLICIDADE_SEGUNDOS = 120

# Sessão: encerramento por inatividade (segundos) e páginas liberadas por perfil.
SESSAO_INATIVIDADE_SEGUNDOS = 8 * 60 * 60
TODAS_AS_PAGINAS = ["Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências", "Histórico de Dados"]
ICONES_PAGINAS = {
    "Nova Inspeção": "clipboard-check",
    "Dashboard de Indicadores": "bar-chart-line",
    "Galeria de Evidências": "images",
    "Histórico de Dados": "archive",
}
PAGINAS_POR_PERFIL = {
    "cipeiro": ["Nova Inspeção", "Dashboard de Indicadores"],
    "gestor": TODAS_AS_PAGINAS,
    "admin": TODAS_AS_PAGINAS,
}

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
def verificar_senha(informada, armazenada):
    # Aceita hash "pbkdf2_sha256$iteracoes$sal_hex$hash_hex" ou, durante a transição, senha em texto puro.
    armazenada = str(armazenada)
    if armazenada.startswith("pbkdf2_sha256$"):
        try:
            _, iteracoes, sal, esperado = armazenada.split("$")
            calculado = hashlib.pbkdf2_hmac("sha256", informada.encode("utf-8"), bytes.fromhex(sal), int(iteracoes)).hex()
        except ValueError:
            return False
        return hmac.compare_digest(calculado, esperado)
    return hmac.compare_digest(informada.encode("utf-8"), armazenada.encode("utf-8"))

def obter_perfil(usuario):
    # Perfis em st.secrets["perfis"]. Sem a seção, todos operam como admin (compatibilidade); login não listado = cipeiro.
    perfis = st.secrets.get("perfis")
    if perfis is None:
        return "admin"
    perfil = str(perfis.get(usuario, "cipeiro")).strip().lower()
    return perfil if perfil in PAGINAS_POR_PERFIL else "cipeiro"

def encerrar_sessao():
    st.session_state.clear()

def check_password():
    if st.session_state.get("password_correct", False):
        agora = time.time()
        if agora - st.session_state.get("ultimo_acesso", agora) > SESSAO_INATIVIDADE_SEGUNDOS:
            encerrar_sessao()
            st.warning("Sessão encerrada por inatividade. Faça login novamente.")
        else:
            st.session_state["ultimo_acesso"] = agora
            return True
    st.title("🔒 Acesso Restrito - CIPA")
    with st.form("login_form"):
        usuario_digitado = st.text_input("Usuário")
        senha_digitada = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            dicionario_usuarios = st.secrets.get("usuarios", {})
            usuario_tratado = usuario_digitado.strip().lower()
            if usuario_tratado in dicionario_usuarios and verificar_senha(senha_digitada, dicionario_usuarios.get(usuario_tratado)):
                st.session_state["password_correct"] = True
                st.session_state["usuario_logado"] = usuario_tratado
                st.session_state["ultimo_acesso"] = time.time()
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

    # Idempotência: lock transacional por (cipeiro, setor, mês) e verificação de registro equivalente recente.
    # Cobre clique repetido, execuções sobrepostas e nova tentativa após falha de conexão pós-commit.
    chave_lock = f"{dados_dict['cipeiro']}|{dados_dict['setor']}|{dados_dict['mes_referencia']}"
    consulta_duplicidade = text(
        "SELECT 1 FROM inspecoes WHERE cipeiro = :cipeiro AND setor = :setor AND mes_referencia = :mes_referencia "
        "AND status = :status AND data_execucao BETWEEN :inicio AND :fim LIMIT 1"
    )
    janela = timedelta(seconds=JANELA_DUPLICIDADE_SEGUNDOS)
    parametros_duplicidade = {
        "cipeiro": dados_dict["cipeiro"], "setor": dados_dict["setor"],
        "mes_referencia": dados_dict["mes_referencia"], "status": dados_dict["status"],
        "inicio": dados_dict["data_execucao"] - janela, "fim": dados_dict["data_execucao"] + janela,
    }
    
    max_tentativas = 2
    insercao_tentada = False
    for tentativa in range(max_tentativas):
        try:
            conn_db = st.connection("postgresql", type="sql")
            with conn_db.session as session:
                session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:chave))"), {"chave": chave_lock})
                if session.execute(consulta_duplicidade, parametros_duplicidade).first() is not None:
                    # Registro equivalente já existe. Se foi gravado por tentativa anterior desta chamada, é o próprio envio.
                    return insercao_tentada
                insercao_tentada = True
                session.execute(query_sql, dados_dict)
                session.commit()
            return True 
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

def slug_pasta(texto):
    # Normaliza o texto para segmento de pasta: ASCII minúsculo, separado por hífen.
    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") or "sem-setor"

def comprimir_imagem(conteudo):
    # Aplica a orientação EXIF, achata transparência em fundo branco, limita o maior lado e recodifica em JPEG.
    with Image.open(io.BytesIO(conteudo)) as origem:
        img = ImageOps.exif_transpose(origem)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            fundo = Image.new("RGB", img.size, (255, 255, 255))
            fundo.paste(img, mask=img.getchannel("A"))
            img = fundo
        else:
            img = img.convert("RGB")
        img.thumbnail((LADO_MAXIMO_PX, LADO_MAXIMO_PX))
        saida = io.BytesIO()
        img.save(saida, format="JPEG", quality=QUALIDADE_JPEG, optimize=True)
        return saida.getvalue()

def processar_upload_imagem(arquivo_bytes, pasta, tentativas=2):
    # Retorna (secure_url, public_id, erro). Os envios recebem a tag "pendente" até a confirmação do INSERT.
    try:
        conteudo = comprimir_imagem(arquivo_bytes)
    except Exception as e:
        return None, None, f"imagem inválida ({e})"
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            resposta = cloudinary.uploader.upload(
                conteudo, folder=pasta, tags=["cipa", "pendente"], resource_type="image"
            )
            return resposta.get("secure_url"), resposta.get("public_id"), None
        except Exception as e:
            ultimo_erro = str(e)
            if tentativa < tentativas - 1:
                time.sleep(1.5)
    return None, None, ultimo_erro

def enviar_anexos(anexos, pasta):
    # Envia em sequência. Após o primeiro erro os demais anexos não são enviados e seguem como pendentes de reenvio.
    urls_por_campo, enviados, pendentes, interrompido = {}, [], [], False
    for campo, rotulo, arquivo in anexos:
        conteudo = arquivo.getvalue()
        if not interrompido:
            url, public_id, erro = processar_upload_imagem(conteudo, pasta)
            if public_id:
                enviados.append(public_id)
            if not erro:
                urls_por_campo.setdefault(campo, []).append(url)
                continue
            interrompido = True
        pendentes.append({"campo": campo, "rotulo": rotulo, "nome": arquivo.name, "conteudo": conteudo})
    return urls_por_campo, enviados, pendentes

def anexar_foto(registro, campo, url):
    # Acrescenta a URL ao campo de foto de uma inspeção já gravada. Chave: data_execucao (tolerância de 1 s), setor e cipeiro.
    if not re.fullmatch(r"foto_geral|foto_q\d+", campo):
        return False
    consulta = text(
        f"UPDATE inspecoes SET {campo} = CASE WHEN COALESCE({campo}, '') = '' THEN :url ELSE {campo} || ', ' || :url END "
        "WHERE data_execucao BETWEEN :inicio AND :fim AND setor = :setor AND cipeiro = :cipeiro"
    )
    parametros = {
        "url": url, "setor": registro["setor"], "cipeiro": registro["cipeiro"],
        "inicio": registro["data_execucao"] - timedelta(seconds=1),
        "fim": registro["data_execucao"] + timedelta(seconds=1),
    }
    try:
        conn_db = st.connection("postgresql", type="sql")
        with conn_db.session as session:
            resultado = session.execute(consulta, parametros)
            session.commit()
        return resultado.rowcount > 0
    except Exception:
        return False

def reenviar_pendentes(pendentes, registro):
    # Reenvia as fotos pendentes e vincula cada uma ao registro. Retorna as que continuam pendentes.
    restantes = []
    for item in pendentes:
        url, public_id, erro = processar_upload_imagem(item["conteudo"], registro["pasta"])
        if erro:
            restantes.append(item)
        elif anexar_foto(registro, item["campo"], url):
            confirmar_imagens([public_id])
        else:
            remover_imagens([public_id])
            restantes.append(item)
    return restantes

def remover_imagens(public_ids):
    # Compensação de INSERT/upload com falha. Em erro, as imagens permanecem com a tag "pendente" para varredura posterior.
    if public_ids:
        try:
            cloudinary.api.delete_resources(public_ids, resource_type="image")
        except Exception:
            pass

def confirmar_imagens(public_ids):
    # Remove a tag "pendente" após a persistência da inspeção.
    if public_ids:
        try:
            cloudinary.uploader.remove_tag("pendente", public_ids, resource_type="image")
        except Exception:
            pass

def validar_fotos(fotos_capturadas, foto_geral):
    # Fotos são opcionais; cada arquivo anexado respeita LIMITE_BYTES.
    erros = []
    arquivos = [a for lista in fotos_capturadas.values() for a in (lista or [])] + list(foto_geral or [])
    for arquivo in arquivos:
        if arquivo.size > LIMITE_BYTES:
            erros.append(f"{arquivo.name}: excede o limite de {LIMITE_BYTES // (1024 * 1024)} MB.")
    return erros

# ==========================================
# NAVEGAÇÃO
# ==========================================
perfil_atual = obter_perfil(st.session_state.get("usuario_logado"))
paginas_permitidas = PAGINAS_POR_PERFIL[perfil_atual]

with st.sidebar:
    pagina = option_menu("Menu CIPA",
        paginas_permitidas,
        icons=[ICONES_PAGINAS[p] for p in paginas_permitidas],
        menu_icon="shield-check", default_index=0)
    if st.button("Sair"):
        encerrar_sessao()
        st.rerun()

if pagina not in paginas_permitidas:
    st.error("Acesso não autorizado para o perfil atual.")
    st.stop()

# ==========================================
# INTERFACE: NOVA INSPEÇÃO
# ==========================================
if pagina == "Nova Inspeção":
    
    # 1. TELA DE SUCESSO / FEEDBACK
    if st.session_state.get("tela_sucesso", False):
        st.title("✅ Inspeção Concluída!")
        st.success("O formulário principal foi salvo com sucesso no banco de dados.")
        
        pendentes = st.session_state.get("fotos_pendentes", [])
        if pendentes:
            st.warning("⚠️ A inspeção foi salva, mas algumas fotos não foram enviadas:")
            for item in pendentes:
                st.write(f"- {item['rotulo']}: {item['nome']}")
            st.caption("As fotos pendentes só podem ser reenviadas enquanto esta tela estiver aberta.")
            if st.button("🔄 Reenviar fotos pendentes"):
                with st.spinner("Reenviando fotos..."):
                    st.session_state["fotos_pendentes"] = reenviar_pendentes(pendentes, st.session_state["registro_salvo"])
                st.rerun()
        else:
            st.balloons()

        st.divider()
        if st.button("⬅️ Fazer Nova Inspeção", type="primary"):
            st.session_state["tela_sucesso"] = False
            st.session_state["fotos_pendentes"] = []
            st.rerun()
            
    # 2. FORMULÁRIO NORMAL
    else:
        if not lista_perguntas:
            st.error("Erro de configuração: 'lista_perguntas_cipa' não localizada.")
            st.stop()

        st.title("📝 Nova Inspeção CIPA")
        
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
        obs_geral, foto_geral = "", []

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
            erros_validacao = []
            if justificada and not motivo_justificativa.strip():
                erros_validacao.append("Preenchimento obrigatório: Motivo da não realização.")
            elif not justificada:
                erros_validacao = validar_fotos(fotos_capturadas, foto_geral)

            if erros_validacao:
                for mensagem in erros_validacao:
                    st.error(mensagem)
            else:
                falha_banco = False
                with st.spinner("Processando dados e enviando imagens. Por favor, aguarde..."):
                    pasta = f"cipa/{ano_sel}-{meses.index(mes_sel) + 1:02d}/{slug_pasta(setor)}"
                    dados = {
                        "mes_referencia": mes_referencia, "setor": setor, "responsavel_area": responsavel_area,
                        # Data informada no formulário + hora corrente: preserva a ordenação intradiária e a unicidade do rótulo da Galeria.
                        "data_execucao": datetime.combine(data_visivel, datetime.now().time()), "cipeiro": cipeiro, "acompanhantes": acompanhantes,
                        "status": "Justificada" if justificada else "Realizada"
                    }

                    anexos = []
                    for i in range(1, len(lista_perguntas) + 1):
                        chave_foto = f"foto_q{i}"
                        dados[chave_foto] = ""
                        if justificada:
                            dados[f"q{i}"], dados[f"obs{i}"] = "Justificado", ""
                        else:
                            dados[f"q{i}"] = respostas.get(f"q{i}", "N/A")
                            dados[f"obs{i}"] = observacoes.get(f"obs{i}", "")
                            anexos += [(chave_foto, f"Questão {i}", a) for a in fotos_capturadas.get(chave_foto) or []]

                    dados["obs_geral"] = motivo_justificativa if justificada else obs_geral
                    dados["foto_geral"] = ""
                    if not justificada:
                        anexos += [("foto_geral", "Foto Geral", a) for a in foto_geral or []]

                    # Fotos são opcionais: falha de envio não impede a gravação; as não enviadas ficam pendentes de reenvio.
                    urls_por_campo, enviados, pendentes = enviar_anexos(anexos, pasta)
                    for campo, urls in urls_por_campo.items():
                        dados[campo] = ", ".join(urls)

                    try:
                        inserido = salvar_dados(dados)
                    except Exception:
                        # salvar_dados já exibe o erro; imagens enviadas são removidas para evitar órfãs.
                        falha_banco = True
                        remover_imagens(enviados)
                    else:
                        # Envio duplicado suprimido: as imagens desta execução não estão vinculadas a nenhum registro.
                        if inserido:
                            confirmar_imagens(enviados)
                        else:
                            remover_imagens(enviados)
                        # Estado de conclusão gravado imediatamente após o INSERT, antes de qualquer elemento de UI:
                        # uma nova execução disparada por clique repetido renderiza a tela de sucesso e não reenvia o formulário.
                        st.session_state["fotos_pendentes"] = pendentes
                        st.session_state["registro_salvo"] = {
                            "data_execucao": dados["data_execucao"], "setor": setor, "cipeiro": cipeiro, "pasta": pasta
                        }
                        st.session_state["tela_sucesso"] = True

                if not falha_banco:
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
            
            ano_atual_sistema = str(datetime.now().year)
            ano_matriz = ano_atual_sistema if ano_sel == "Todos" else ano_sel
            
            st.subheader(f"Matriz de Engajamento Anual ({ano_matriz})")
            
            df_matriz = df[df['ano'] == ano_matriz].copy()

            if df_matriz.empty:
                st.info(f"Nenhuma inspeção registrada no sistema para o ano de {ano_matriz}.")
            else:
                df_matriz['mes_nome'] = df_matriz['mes_referencia'].apply(lambda x: str(x).split('/')[0])
                
                tabela_dinamica = df_matriz.groupby(['cipeiro', 'mes_nome'])['status'].apply(
                    lambda x: '✅' if 'Realizada' in x.values else '🚷'
                ).unstack(fill_value='❌')
                
                for mes in ordem_meses:
                    if mes not in tabela_dinamica.columns:
                        tabela_dinamica[mes] = '❌'
                        
                tabela_dinamica = tabela_dinamica[ordem_meses]
                
                if ano_matriz == ano_atual_sistema:
                    cipeiros_no_banco = tabela_dinamica.index.tolist()
                    cipeiros_faltantes = [c for c in lista_completa_cipeiros if c not in cipeiros_no_banco]
                    
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
            if perfil_atual == "admin":
                st.download_button("📥 Baixar CSV", csv, 'historico_cipa.csv', 'text/csv')
    except Exception as e:
        st.error(f"Erro de processamento: {e}")