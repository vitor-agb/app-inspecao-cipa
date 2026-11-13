import streamlit as st
from datetime import datetime, timedelta
import hashlib
import hmac
import io
import re
import secrets as aleatorio
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

# Sessão, bloqueio de login, política de senha e páginas liberadas por perfil.
SESSAO_INATIVIDADE_SEGUNDOS = 8 * 60 * 60
REVALIDACAO_SEGUNDOS = 5 * 60
MAX_TENTATIVAS_LOGIN = 5
BLOQUEIO_MINUTOS = 15
TAMANHO_MINIMO_SENHA = 6
ITERACOES_HASH = 600_000
ORDEM_PAGINAS = [
    "Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências",
    "Histórico de Dados", "Minha Conta", "Gerenciar Usuários",
]
ICONES_PAGINAS = {
    "Nova Inspeção": "clipboard-check",
    "Dashboard de Indicadores": "bar-chart-line",
    "Galeria de Evidências": "images",
    "Histórico de Dados": "archive",
    "Minha Conta": "person-circle",
    "Gerenciar Usuários": "people",
}
PAGINAS_POR_PERFIL = {
    "cipeiro": {"Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências", "Minha Conta"},
    "gestor": {"Nova Inspeção", "Dashboard de Indicadores", "Galeria de Evidências", "Histórico de Dados", "Minha Conta"},
    "admin": set(ORDEM_PAGINAS),
}

# ==========================================
# CONFIGURAÇÕES GERAIS E ESTILO
# ==========================================
st.set_page_config(page_title="Inspeção CIPA", layout="wide")

# Identidade visual compartilhada com o Estoque 2.0: verde institucional, destaque âmbar, Ubuntu nos títulos e Lato no texto.
# Variáveis claras e escuras seguem o tema do Streamlit (claro ou escuro, conforme o sistema). Barra lateral escura nos dois temas.
st.markdown("""
    <style>
    @import url("https://fonts.googleapis.com/css2?family=Lato:wght@400;700&family=Ubuntu:wght@400;500;700&display=swap");
    :root {--c-brand:#2b7a2e; --c-brand-tx:#fff; --c-card:#fff; --c-tx:#161d25; --c-mut:#56616b; --c-bd:#dce2dd; --c-sel:#e1f2e7; --c-realce:#ffb200; --c-side:#161d25;}
    @media (prefers-color-scheme: dark) {
        :root {--c-brand:#a4e745; --c-brand-tx:#161d25; --c-card:#161d25; --c-tx:#eef2ef; --c-mut:#9aa6b0; --c-bd:#2a3540; --c-sel:#25341f; --c-side:#0a0e12;}
    }
    html, body, .stApp, [data-testid="stAppViewContainer"] {font-family: Lato, system-ui, "Segoe UI", Arial, sans-serif;}
    h1, h2, h3, h4, [data-testid="stMetricValue"] {font-family: Ubuntu, Lato, system-ui, Arial, sans-serif !important;}
    h1, h2, h3 {color: var(--c-brand) !important;}
    [data-testid="stHeader"] {border-top: 4px solid var(--c-brand);}
    [data-testid="stSidebar"] {border-right: 1px solid var(--c-bd);}
    .stButton > button, [data-testid^="stBaseButton"] {border-radius: 6px;}
    button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
        background: var(--c-brand) !important; border-color: var(--c-brand) !important; color: var(--c-brand-tx) !important;
    }
    button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
        filter: brightness(1.1); box-shadow: inset 0 -3px 0 var(--c-realce);
    }
    [data-testid="stMetric"] {background: var(--c-card); border: 1px solid var(--c-bd); border-radius: 8px; padding: 10px 14px;}
    [data-testid="stMetricValue"] {color: var(--c-brand); font-weight: 700;}
    [data-testid="stMetricLabel"] {color: var(--c-mut);}
    .destaque-setor {background: var(--c-card); border: 1px solid var(--c-bd); border-left: 4px solid var(--c-realce); border-radius: 8px; padding: 12px 14px;}
    .destaque-setor .rotulo {color: var(--c-mut); font-size: 12px; text-transform: uppercase; letter-spacing: .04em;}
    .destaque-setor .nome {color: var(--c-tx); font-family: Ubuntu, Lato, system-ui, Arial, sans-serif; font-size: 18px; font-weight: 700;}
    .destaque-setor .valor {color: var(--c-brand); font-family: Ubuntu, Lato, system-ui, Arial, sans-serif; font-size: 22px; font-weight: 700;}
    [data-testid="stSidebar"] {background: var(--c-side) !important; border-right: 0;}
    [data-testid="stSidebar"], [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {color: #e9eeea;}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #93a0ab !important;}
    [data-testid="stSidebar"] button {background: transparent; border: 1px solid #2a3540; color: #e9eeea;}
    [data-testid="stSidebar"] button:hover {border-color: #a4e745; color: #a4e745;}
    [data-testid="stSidebar"] button svg {color: #e9eeea;}
    .marca-lateral {font-family: Ubuntu, Lato, system-ui, Arial, sans-serif; font-weight: 700; font-size: 26px; letter-spacing: .12em; color: #e9eeea; line-height: 1.1;}
    .submarca-lateral {color: #a4e745; font-size: 12px; margin: 2px 0 14px 0;}
    [data-testid="stToolbarActions"] {display: none !important;}
    footer {display: none !important;}
    div[data-testid="stFileUploader"] section > div[data-testid="stMarkdownContainer"] {display: none !important;}
    div[data-testid="stFileUploaderFileData"] {display: block !important; margin-top: 10px;}
    div[data-testid="stFileUploader"] label {font-weight: bold !important; color: var(--c-tx) !important;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# AUTENTICAÇÃO
# ==========================================
def _transitorio(erro):
    mensagem = str(erro).lower()
    return any(termo in mensagem for termo in ("ssl", "closed", "operationalerror", "connection", "timeout"))

def executar_sql(sql, parametros=None, leitura=True):
    # Executa uma instrução; repete em falhas transitórias de conexão (banco serverless em repouso).
    for tentativa in range(3):
        try:
            conn_db = st.connection("postgresql", type="sql")
            with conn_db.session as session:
                resultado = session.execute(text(sql), parametros or {})
                if leitura:
                    return [dict(linha) for linha in resultado.mappings().all()]
                session.commit()
                return None
        except Exception as e:
            if tentativa < 2 and _transitorio(e):
                st.cache_resource.clear()
                time.sleep(2)
                continue
            raise

def gerar_hash_senha(senha):
    sal = aleatorio.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES_HASH)
    return f"pbkdf2_sha256${ITERACOES_HASH}${sal.hex()}${derivado.hex()}"

def gerar_senha_provisoria(tamanho=6):
    # Senha provisória numérica, de digitação simples; a troca é obrigatória no primeiro acesso.
    return "".join(aleatorio.choice("0123456789") for _ in range(tamanho))

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

def _normalizar_usuario(usuario):
    for campo in ("trocar_senha", "ativo", "inspetor", "bloqueado"):
        if campo in usuario:
            usuario[campo] = bool(usuario[campo])
    return usuario

_SELECT_BLOQUEADO = "CASE WHEN bloqueado_ate IS NOT NULL AND bloqueado_ate > :agora THEN 1 ELSE 0 END AS bloqueado"

def buscar_usuario(login):
    linhas = executar_sql(
        "SELECT login, nome, perfil, senha_hash, trocar_senha, ativo, inspetor, tentativas_falhas, "
        f"{_SELECT_BLOQUEADO} FROM usuarios_cipa WHERE login = :login",
        {"login": login, "agora": datetime.now()},
    )
    return _normalizar_usuario(linhas[0]) if linhas else None

def listar_usuarios():
    linhas = executar_sql(
        f"SELECT login, nome, perfil, ativo, inspetor, trocar_senha, {_SELECT_BLOQUEADO} FROM usuarios_cipa ORDER BY nome",
        {"agora": datetime.now()},
    )
    return [_normalizar_usuario(linha) for linha in linhas]

def ano_atual():
    return datetime.now().year

@st.cache_data(ttl=60)
def nomes_cipeiros_do_ano(ano, somente_ativos):
    # Nomes dos usuários com mandato no ano (lista do formulário e da matriz de engajamento).
    sql = ("SELECT u.nome FROM mandatos_cipa m JOIN usuarios_cipa u ON u.login = m.login WHERE m.ano = :ano"
           + (" AND u.ativo = :ativo" if somente_ativos else "") + " ORDER BY u.nome")
    parametros = {"ano": int(ano)}
    if somente_ativos:
        parametros["ativo"] = True
    try:
        linhas = executar_sql(sql, parametros)
    except Exception:
        return []
    return [linha["nome"] for linha in linhas]

def listar_mandatos():
    # Retorna {login: [anos]} em ordem crescente.
    linhas = executar_sql("SELECT login, ano FROM mandatos_cipa ORDER BY ano")
    mandatos = {}
    for linha in linhas:
        mandatos.setdefault(linha["login"], []).append(int(linha["ano"]))
    return mandatos

def definir_mandato(login, ano, presente):
    parametros = {"login": login, "ano": int(ano)}
    existe = executar_sql("SELECT 1 AS existe FROM mandatos_cipa WHERE login = :login AND ano = :ano", parametros)
    if presente and not existe:
        executar_sql("INSERT INTO mandatos_cipa (login, ano) VALUES (:login, :ano)", parametros, leitura=False)
    elif not presente and existe:
        executar_sql("DELETE FROM mandatos_cipa WHERE login = :login AND ano = :ano", parametros, leitura=False)
    nomes_cipeiros_do_ano.clear()

def renovar_gestao(ano, continuam):
    # Cria o mandato do ano para quem continua e desativa os demais usuários ativos com perfil cipeiro.
    # O histórico de mandatos é preservado; gestor e admin não são afetados.
    desativados = []
    for usuario in listar_usuarios():
        if usuario["perfil"] != "cipeiro" or not usuario["ativo"]:
            continue
        if usuario["login"] in continuam:
            definir_mandato(usuario["login"], ano, True)
        else:
            atualizar_usuario(usuario["login"], "ativo", False)
            desativados.append(usuario["login"])
    return desativados

def criar_usuario(login, nome, perfil, inspetor):
    senha = gerar_senha_provisoria()
    executar_sql(
        "INSERT INTO usuarios_cipa (login, nome, perfil, senha_hash, trocar_senha, ativo, inspetor, tentativas_falhas, atualizado_em) "
        "VALUES (:login, :nome, :perfil, :hash, :trocar, :ativo, :inspetor, 0, :agora)",
        {"login": login, "nome": nome, "perfil": perfil, "hash": gerar_hash_senha(senha),
         "trocar": True, "ativo": True, "inspetor": bool(inspetor), "agora": datetime.now()},
        leitura=False,
    )
    nomes_cipeiros_do_ano.clear()
    return senha

def redefinir_senha(login):
    senha = gerar_senha_provisoria()
    executar_sql(
        "UPDATE usuarios_cipa SET senha_hash = :hash, trocar_senha = :trocar, tentativas_falhas = 0, "
        "bloqueado_ate = NULL, atualizado_em = :agora WHERE login = :login",
        {"hash": gerar_hash_senha(senha), "trocar": True, "agora": datetime.now(), "login": login},
        leitura=False,
    )
    return senha

def alterar_senha(login, nova):
    executar_sql(
        "UPDATE usuarios_cipa SET senha_hash = :hash, trocar_senha = :trocar, tentativas_falhas = 0, "
        "bloqueado_ate = NULL, atualizado_em = :agora WHERE login = :login",
        {"hash": gerar_hash_senha(nova), "trocar": False, "agora": datetime.now(), "login": login},
        leitura=False,
    )

def atualizar_usuario(login, campo, valor):
    if campo not in ("ativo", "perfil", "inspetor", "nome"):
        raise ValueError(campo)
    executar_sql(
        f"UPDATE usuarios_cipa SET {campo} = :valor, atualizado_em = :agora WHERE login = :login",
        {"valor": valor, "agora": datetime.now(), "login": login},
        leitura=False,
    )
    nomes_cipeiros_do_ano.clear()

def desbloquear_usuario(login):
    executar_sql(
        "UPDATE usuarios_cipa SET tentativas_falhas = 0, bloqueado_ate = NULL, atualizado_em = :agora WHERE login = :login",
        {"agora": datetime.now(), "login": login},
        leitura=False,
    )

def migrar_usuarios_secrets():
    # Cria no banco os usuários definidos em st.secrets que ainda não existem, com senha provisória individual.
    usuarios_secrets = st.secrets.get("usuarios", {})
    nomes = st.secrets.get("nomes_cipeiros", {})
    perfis = st.secrets.get("perfis")
    lista_inspetores = st.secrets.get("lista_todos_cipeiros", [])
    existentes = {u["login"] for u in listar_usuarios()}
    geradas = []
    for login_bruto in usuarios_secrets:
        login = str(login_bruto).strip().lower()
        if login in existentes:
            continue
        nome = str(nomes.get(login, login))
        perfil = str(perfis.get(login, "cipeiro")).strip().lower() if perfis is not None else "cipeiro"
        if perfil not in PAGINAS_POR_PERFIL:
            perfil = "cipeiro"
        senha = criar_usuario(login, nome, perfil, nome in lista_inspetores)
        if nome in lista_inspetores:
            definir_mandato(login, ano_atual(), True)
        geradas.append((login, nome, perfil, senha))
    return geradas

def obter_perfil_secrets(usuario):
    # Perfis em st.secrets["perfis"] (contas ainda não migradas). Sem a seção, todos operam como admin; login não listado = cipeiro.
    perfis = st.secrets.get("perfis")
    if perfis is None:
        return "admin"
    perfil = str(perfis.get(usuario, "cipeiro")).strip().lower()
    return perfil if perfil in PAGINAS_POR_PERFIL else "cipeiro"

def _autenticar_secrets(login, senha):
    usuarios = st.secrets.get("usuarios", {})
    if login in usuarios and verificar_senha(senha, usuarios.get(login)):
        nome = st.secrets.get("nomes_cipeiros", {}).get(login)
        return {"login": login, "nome": nome, "perfil": obter_perfil_secrets(login),
                "trocar_senha": False, "origem": "secrets"}, None
    return None, "Credenciais incorretas."

def autenticar(login, senha):
    # Retorna (usuario, mensagem). Usuário ausente do banco, ou banco indisponível, usa as credenciais de st.secrets.
    try:
        usuario = buscar_usuario(login)
    except Exception:
        usuario = None
    if usuario is None:
        return _autenticar_secrets(login, senha)
    if not usuario["ativo"]:
        return None, "Usuário inativo. Procure o administrador."
    mensagem_bloqueio = f"Acesso bloqueado por excesso de tentativas. Tente novamente em {BLOQUEIO_MINUTOS} minutos."
    if usuario["bloqueado"]:
        return None, mensagem_bloqueio
    if verificar_senha(senha, usuario["senha_hash"]):
        if usuario["tentativas_falhas"]:
            try:
                desbloquear_usuario(login)
            except Exception:
                pass
        usuario["origem"] = "banco"
        return usuario, None
    tentativas = int(usuario["tentativas_falhas"] or 0) + 1
    try:
        if tentativas >= MAX_TENTATIVAS_LOGIN:
            executar_sql(
                "UPDATE usuarios_cipa SET tentativas_falhas = 0, bloqueado_ate = :ate WHERE login = :login",
                {"ate": datetime.now() + timedelta(minutes=BLOQUEIO_MINUTOS), "login": login},
                leitura=False,
            )
        else:
            executar_sql(
                "UPDATE usuarios_cipa SET tentativas_falhas = :tentativas WHERE login = :login",
                {"tentativas": tentativas, "login": login},
                leitura=False,
            )
    except Exception:
        pass
    return None, (mensagem_bloqueio if tentativas >= MAX_TENTATIVAS_LOGIN else "Credenciais incorretas.")

def iniciar_sessao(usuario):
    agora = time.time()
    st.session_state.update({
        "password_correct": True, "usuario_logado": usuario["login"], "nome_usuario": usuario.get("nome"),
        "perfil": usuario["perfil"], "origem": usuario["origem"], "trocar_senha": usuario.get("trocar_senha", False),
        "ultimo_acesso": agora, "ultima_validacao": agora,
    })

def sessao_valida():
    # Reavalia usuários do banco periodicamente: desativação e troca de perfil valem sem novo login.
    if st.session_state.get("origem") != "banco":
        return True
    agora = time.time()
    if agora - st.session_state.get("ultima_validacao", 0) < REVALIDACAO_SEGUNDOS:
        return True
    try:
        usuario = buscar_usuario(st.session_state["usuario_logado"])
    except Exception:
        return True
    if usuario is None or not usuario["ativo"]:
        return False
    st.session_state.update({
        "perfil": usuario["perfil"], "nome_usuario": usuario["nome"],
        "trocar_senha": usuario["trocar_senha"], "ultima_validacao": agora,
    })
    return True

def encerrar_sessao():
    st.session_state.clear()

def check_password():
    if st.session_state.get("password_correct", False):
        agora = time.time()
        if agora - st.session_state.get("ultimo_acesso", agora) > SESSAO_INATIVIDADE_SEGUNDOS:
            encerrar_sessao()
            st.warning("Sessão encerrada por inatividade. Faça login novamente.")
        elif not sessao_valida():
            encerrar_sessao()
            st.warning("Acesso desativado. Procure o administrador.")
        else:
            st.session_state["ultimo_acesso"] = agora
            return True
    st.title("🔒 Acesso Restrito - CIPA")
    with st.form("login_form"):
        usuario_digitado = st.text_input("Usuário")
        senha_digitada = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary"):
            usuario, mensagem = autenticar(usuario_digitado.strip().lower(), senha_digitada)
            if usuario:
                iniciar_sessao(usuario)
                st.rerun()
            else:
                st.error(mensagem)
    return False

def validar_nova_senha(login, nova, confirmacao):
    if nova != confirmacao:
        return "As senhas não conferem."
    if len(nova) < TAMANHO_MINIMO_SENHA:
        return f"A senha deve ter ao menos {TAMANHO_MINIMO_SENHA} caracteres."
    if nova.strip().lower() == login:
        return "A senha não pode ser igual ao usuário."
    return None

def tela_troca_senha(obrigatoria):
    login = st.session_state["usuario_logado"]
    st.title("🔑 Definir nova senha" if obrigatoria else "👤 Minha Conta")
    if st.session_state.get("origem") != "banco":
        st.info("Esta conta ainda usa a senha antiga. Solicite ao administrador a migração para alterar a senha.")
        return
    if obrigatoria:
        st.warning("Defina uma nova senha para continuar.")
    with st.form("form_troca_senha", clear_on_submit=True):
        atual = "" if obrigatoria else st.text_input("Senha atual", type="password")
        nova = st.text_input("Nova senha", type="password")
        confirmacao = st.text_input("Confirmar nova senha", type="password")
        if st.form_submit_button("Salvar nova senha", type="primary"):
            try:
                usuario = buscar_usuario(login)
            except Exception as e:
                st.error(f"Banco de dados indisponível: {e}")
                return
            erro = None
            if not obrigatoria and not verificar_senha(atual, usuario["senha_hash"]):
                erro = "Senha atual incorreta."
            else:
                erro = validar_nova_senha(login, nova, confirmacao)
            if not erro and verificar_senha(nova, usuario["senha_hash"]):
                erro = "A nova senha deve ser diferente da atual."
            if erro:
                st.error(erro)
            else:
                alterar_senha(login, nova)
                st.session_state["trocar_senha"] = False
                if obrigatoria:
                    st.rerun()
                st.success("Senha alterada com sucesso.")

def pagina_gerenciar_usuarios():
    st.title("👥 Gerenciar Usuários")
    try:
        usuarios = listar_usuarios()
    except Exception as e:
        st.error(f"Tabela de usuários indisponível: {e}")
        return
    try:
        mandatos = listar_mandatos()
    except Exception as e:
        mandatos = {}
        st.warning(f"Tabela de mandatos indisponível: {e}")

    aviso = st.session_state.pop("aviso_admin", None)
    if aviso:
        st.success(aviso)
    geradas = st.session_state.pop("senhas_geradas", None)
    if geradas:
        st.success("Senhas provisórias geradas. Anote agora: não serão exibidas novamente.")
        st.table(pd.DataFrame(geradas, columns=["Usuário", "Nome", "Perfil", "Senha provisória"]))

    anos_existentes = sorted({ano for anos in mandatos.values() for ano in anos}, reverse=True)
    if anos_existentes and ano_atual() not in anos_existentes:
        st.warning(f"Nenhum mandato cadastrado para {ano_atual()}. Use Renovar gestão.")

    if usuarios:
        filtro_ano = st.selectbox("Filtrar por ano de mandato", ["Todos"] + anos_existentes)
        linhas = [
            {"Usuário": u["login"], "Nome": u["nome"], "Perfil": u["perfil"], "Ativo": u["ativo"],
             "Mandatos": ", ".join(str(a) for a in mandatos.get(u["login"], [])),
             "Troca pendente": u["trocar_senha"], "Bloqueado": u["bloqueado"]}
            for u in usuarios if filtro_ano == "Todos" or filtro_ano in mandatos.get(u["login"], [])
        ]
        st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum usuário cadastrado no banco.")

    logins_banco = {u["login"] for u in usuarios}
    pendentes_secrets = [str(l).strip().lower() for l in st.secrets.get("usuarios", {}) if str(l).strip().lower() not in logins_banco]
    if pendentes_secrets:
        st.divider()
        st.subheader("Migrar usuários de st.secrets")
        st.caption(f"{len(pendentes_secrets)} usuário(s) ainda não estão no banco.")
        if st.button("Migrar usuários e gerar senhas provisórias"):
            with st.spinner("Criando usuários..."):
                st.session_state["senhas_geradas"] = migrar_usuarios_secrets()
            st.rerun()

    cipeiros_ativos = [u for u in usuarios if u["perfil"] == "cipeiro" and u["ativo"]]
    if cipeiros_ativos:
        st.divider()
        st.subheader("Renovar gestão")
        ano_novo_mandato = int(st.number_input(
            "Ano do novo mandato", min_value=2020, max_value=2100, step=1,
            value=(max(anos_existentes) + 1) if anos_existentes else ano_atual(),
        ))
        rotulos = {u["login"]: f"{u['nome']} ({u['login']})" for u in cipeiros_ativos}
        padrao = [u["login"] for u in cipeiros_ativos
                  if {ano_novo_mandato - 1, ano_novo_mandato} & set(mandatos.get(u["login"], []))]
        continuam = st.multiselect("Continuam no mandato", list(rotulos), default=padrao,
                                   format_func=lambda l: rotulos[l], key=f"continuam_{ano_novo_mandato}")
        saem = [rotulos[l] for l in rotulos if l not in continuam]
        if saem:
            st.caption("Serão desativados: " + ", ".join(saem))
        confirmou = st.checkbox("Confirmo a renovação da gestão", key=f"confirma_{ano_novo_mandato}")
        if st.button("Renovar gestão", disabled=not confirmou):
            desativados = renovar_gestao(ano_novo_mandato, set(continuam))
            st.session_state["aviso_admin"] = (
                f"Gestão {ano_novo_mandato} registrada: {len(continuam)} com mandato, {len(desativados)} desativado(s)."
            )
            st.rerun()

    st.divider()
    st.subheader("Novo usuário")
    with st.form("novo_usuario", clear_on_submit=True):
        c1, c2 = st.columns(2)
        login_novo = c1.text_input("Usuário (login)")
        nome_novo = c2.text_input("Nome completo")
        c3, c4, c5 = st.columns(3)
        perfil_novo = c3.selectbox("Perfil", ["cipeiro", "gestor", "admin"])
        com_mandato = c4.checkbox("Cipeiro com mandato", value=True)
        ano_mandato_novo = int(c5.number_input("Ano do mandato", min_value=2020, max_value=2100, step=1, value=ano_atual()))
        if st.form_submit_button("Criar usuário"):
            login = login_novo.strip().lower()
            if not re.fullmatch(r"[a-z0-9._-]{3,40}", login) or not nome_novo.strip():
                st.error("Informe um login (3 a 40 caracteres: letras minúsculas, números, ponto, hífen ou sublinhado) e o nome.")
            elif login in logins_banco:
                st.error("Usuário já cadastrado.")
            else:
                senha = criar_usuario(login, nome_novo.strip(), perfil_novo, com_mandato)
                if com_mandato:
                    definir_mandato(login, ano_mandato_novo, True)
                st.session_state["senhas_geradas"] = [(login, nome_novo.strip(), perfil_novo, senha)]
                st.rerun()

    if usuarios:
        st.divider()
        st.subheader("Gerenciar usuário existente")
        mapa = {u["login"]: u for u in usuarios}
        login_sel = st.selectbox("Usuário", list(mapa), format_func=lambda l: f"{mapa[l]['nome']} ({l})")
        sel = mapa[login_sel]
        proprio = login_sel == st.session_state.get("usuario_logado")
        b1, b2, b3 = st.columns(3)
        if proprio:
            st.caption("Para alterar a sua própria senha, use Minha Conta.")
        if b1.button("Redefinir senha", disabled=proprio):
            st.session_state["senhas_geradas"] = [(login_sel, sel["nome"], sel["perfil"], redefinir_senha(login_sel))]
            st.rerun()
        if b2.button("Desativar" if sel["ativo"] else "Ativar", disabled=proprio):
            atualizar_usuario(login_sel, "ativo", not sel["ativo"])
            st.rerun()
        if b3.button("Desbloquear", disabled=not sel["bloqueado"]):
            desbloquear_usuario(login_sel)
            st.rerun()
        perfis = ["cipeiro", "gestor", "admin"]
        c6, c7 = st.columns([3, 1])
        perfil_sel = c6.selectbox("Perfil", perfis, index=perfis.index(sel["perfil"]), disabled=proprio, key=f"perfil_{login_sel}")
        if c7.button("Salvar perfil", disabled=proprio or perfil_sel == sel["perfil"]):
            atualizar_usuario(login_sel, "perfil", perfil_sel)
            st.rerun()
        c8, c9, c10 = st.columns([2, 1, 1])
        ano_mandato = int(c8.number_input("Ano do mandato", min_value=2020, max_value=2100, step=1,
                                          value=ano_atual(), key=f"ano_mandato_{login_sel}"))
        if c9.button("Adicionar mandato"):
            definir_mandato(login_sel, ano_mandato, True)
            st.rerun()
        if c10.button("Remover mandato"):
            definir_mandato(login_sel, ano_mandato, False)
            st.rerun()

if not check_password():
    st.stop()

if st.session_state.get("trocar_senha"):
    tela_troca_senha(obrigatoria=True)
    st.stop()

# ==========================================
# VARIÁVEIS DE AMBIENTE
# ==========================================
lista_perguntas = st.secrets.get("lista_perguntas_cipa", [])
lista_setores = st.secrets.get("lista_setores", [])
lista_responsaveis = st.secrets.get("lista_responsaveis", [])
lista_completa_cipeiros = nomes_cipeiros_do_ano(ano_atual(), True) or st.secrets.get("lista_todos_cipeiros", [])

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
perfil_atual = st.session_state.get("perfil", "cipeiro")
paginas_permitidas = [p for p in ORDEM_PAGINAS if p in PAGINAS_POR_PERFIL.get(perfil_atual, PAGINAS_POR_PERFIL["cipeiro"])]

def tema_escuro():
    # Tema ativo no navegador; sem suporte na versão instalada, assume o tema claro.
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False

COR_LATERAL = "#0a0e12" if tema_escuro() else "#161d25"

with st.sidebar:
    st.markdown('<div class="marca-lateral">GÊNICA</div><div class="submarca-lateral">CIPA · Inspeções de Segurança</div>', unsafe_allow_html=True)
    pagina = option_menu(None,
        paginas_permitidas,
        icons=[ICONES_PAGINAS[p] for p in paginas_permitidas],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": COR_LATERAL},
            "nav": {"background-color": COR_LATERAL},
            "icon": {"color": "#e9eeea", "font-size": "16px"},
            "nav-link": {"color": "#e9eeea", "font-size": "15px", "border-radius": "10px", "margin": "2px 0", "--hover-color": "#232d38"},
            "nav-link-selected": {"background-color": "#a4e745", "color": "#161d25", "font-weight": "600"},
        })
    st.caption(f"{st.session_state.get('nome_usuario') or st.session_state.get('usuario_logado')} ({perfil_atual})")
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
            nome_cipeiro = st.session_state.get("nome_usuario")
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
                        <div class="destaque-setor">
                            <div class="rotulo">🏆 Setor destaque</div>
                            <div class="nome">{setor_campeao['setor']}</div>
                            <div class="valor">{setor_campeao['nota_porcentagem']:.1f}% de conformidade</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.divider()
                    df_medias_setor['setor_curto'] = df_medias_setor['setor'].str.replace("Prédio Nº ", "P").str.replace("Produção de ", "Prod. ")
                    df_medias_setor['rotulo'] = df_medias_setor['nota_porcentagem'].apply(lambda x: f"{x:.1f}%")

                    barras = alt.Chart(df_medias_setor).mark_bar(color="#4fb253" if tema_escuro() else "#359138").encode(
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
                
                if ano_matriz.isdigit():
                    lista_matriz = nomes_cipeiros_do_ano(int(ano_matriz), False)
                    if not lista_matriz and ano_matriz == ano_atual_sistema:
                        lista_matriz = st.secrets.get("lista_todos_cipeiros", [])
                    cipeiros_no_banco = tabela_dinamica.index.tolist()
                    cipeiros_faltantes = [c for c in lista_matriz if c not in cipeiros_no_banco]

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

# ==========================================
# MINHA CONTA E GESTÃO DE USUÁRIOS
# ==========================================
elif pagina == "Minha Conta":
    tela_troca_senha(obrigatoria=False)

elif pagina == "Gerenciar Usuários":
    pagina_gerenciar_usuarios()
