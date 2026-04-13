import streamlit as st
import bcrypt
from google_planilha import GooglePlanilha

def verificar_senha(senha, hash_armazenado):
    """Verifica se a senha coincide com o hash."""
    return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))

def gerar_hash(senha):
    """Gera um hash para uma senha."""
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def login():
    """Exibe a tela de login e gerencia a sessão."""
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False

    if st.session_state.autenticado:
        return True

    st.title("🔐 Acesso Restrito")
    
    with st.form("login_form"):
        usuario_input = st.text_input("Usuário")
        senha_input = st.text_input("Senha", type="password")
        submetido = st.form_submit_button("Entrar", width="stretch")

        if submetido:
            try:
                gsheet = GooglePlanilha()
                if gsheet.aba_usuarios is None:
                    st.error("⚠️ Aba 'usuarios' não encontrada na planilha.")
                    return False

                usuarios_dados = gsheet.aba_usuarios.get_all_records()
                
                # Procura o usuário (ignora maiúsculas/minúsculas no nome)
                usuario_encontrado = next((u for u in usuarios_dados if str(u['USUARIOS']).strip().upper() == usuario_input.upper()), None)

                if usuario_encontrado and verificar_senha(senha_input, str(usuario_encontrado['SENHA'])):
                    st.session_state.autenticado = True
                    st.session_state.usuario_logado = usuario_encontrado['USUARIOS']
                    
                    # Processa as lojas permitidas
                    lojas_str = str(usuario_encontrado['LOJAS']).strip()
                    if lojas_str.upper() == 'TODAS':
                        st.session_state.lojas_permitidas = 'TODAS'
                    else:
                        # Limpa espaços e garante que sejam strings (ex: "01, 02" vira ["01", "02"])
                        st.session_state.lojas_permitidas = [l.strip() for l in lojas_str.split(',')]
                    
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos.")
            except Exception as e:
                st.error(f"Erro ao autenticar: {e}")
    
    return False

def logout():
    """Limpa a sessão de login."""
    st.session_state.autenticado = False
    st.session_state.usuario_logado = None
    st.session_state.lojas_permitidas = None
    st.rerun()

def formulario_alterar_senha():
    """Exibe um formulário para o usuário alterar sua própria senha."""
    st.markdown("### 🔑 Alterar Senha")
    with st.form("form_troca_senha"):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        confirma_senha = st.text_input("Confirme a Nova Senha", type="password")
        bt_alterar = st.form_submit_button("Atualizar Senha", width="stretch")

        if bt_alterar:
            if nova_senha != confirma_senha:
                st.error("❌ As novas senhas não coincidem.")
                return
            
            if len(nova_senha) < 4:
                st.error("❌ A nova senha deve ter pelo menos 4 caracteres.")
                return

            try:
                gsheet = GooglePlanilha()
                usuarios_dados = gsheet.aba_usuarios.get_all_records()
                
                # Busca o usuário logado na lista
                for i, u in enumerate(usuarios_dados):
                    if u['USUARIOS'] == st.session_state.usuario_logado:
                        # Verifica a senha atual
                        if verificar_senha(senha_atual, str(u['SENHA'])):
                            # Gera novo hash e atualiza a planilha
                            novo_hash = gerar_hash(nova_senha)
                            # O gspread usa índice 1 e tem cabeçalho, então a linha é i + 2
                            # A coluna SENHA é a segunda (B)
                            gsheet.aba_usuarios.update_cell(i + 2, 2, novo_hash)
                            
                            st.success("✅ Senha alterada com sucesso!")
                            return
                        else:
                            st.error("❌ Senha atual incorreta.")
                            return
                st.error("❌ Usuário não encontrado para atualização.")
            except Exception as e:
                st.error(f"❌ Erro ao atualizar senha: {e}")

# Para gerar um hash inicial, você pode usar isso em um script separado:
# print(gerar_hash("sua_senha_aqui"))
