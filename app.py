import streamlit as st

# Importa os módulos diretamente da raiz
import relatorios_geral
import relatorios_por_loja
import relatorios_por_vendedor
import relatorios_loja_vendedor
import relatorios_acumulado
import relatorios_tempo_real
import relatorios_edicao

# Configuração inicial
st.set_page_config(
    page_title="Relatórios Fluxo",
    page_icon="📊",
    layout="centered"
)

# Estado de navegação
if "tela" not in st.session_state:
    st.session_state.tela = "principal"

# Função para voltar à tela principal
def ir_para_principal():
    st.session_state.tela = "principal"

# Tela principal: seleção de relatórios
if st.session_state.tela == "principal":
    st.title("📊 Relatórios Fluxo")
    st.markdown("### Selecione o relatório desejado:")

    # Lista de botões (título, chave)
    botoes = [
        ("📈 Relatório Geral", "geral"),
        ("🏢 Relatório por Loja", "loja"),
        ("👨‍💼 Relatório por Vendedor", "vendedor"),
        ("📊 Relatório por Loja e Vendedor", "loja_vendedor"),
        ("🔄 Relatório Acumulado (Loja/Vendedor)", "acumulado"),
        ("⏱️ Tempo Real por Vendedor", "tempo_real"),
        ("🛠️ Edição Avançada", "edicao"), 
    ]

    # Exibe os botões um abaixo do outro
    for texto, chave in botoes:
        if st.button(texto, use_container_width=True, key=f"btn_{chave}"):
            st.session_state.tela = chave

    # Botão "Sair" centralizado
    st.markdown("<br>", unsafe_allow_html=True)
    col_center = st.columns([1, 2, 1])
    with col_center[1]:
        if st.button("🚪 Sair", use_container_width=True, type="primary"):
            st.warning("Para sair, feche a aba do navegador.")

# Navegação para os relatórios
else:
    # Botão "Voltar" no topo
    if st.button("⬅️ Voltar", use_container_width=True):
        ir_para_principal()

    # Carrega o relatório selecionado
    if st.session_state.tela == "geral":
        relatorios_geral.mostrar()
    elif st.session_state.tela == "loja":
        relatorios_por_loja.mostrar()
    elif st.session_state.tela == "vendedor":
        relatorios_por_vendedor.mostrar()
    elif st.session_state.tela == "loja_vendedor":
        relatorios_loja_vendedor.mostrar()
    elif st.session_state.tela == "acumulado":
        relatorios_acumulado.mostrar()
    elif st.session_state.tela == "tempo_real":
        relatorios_tempo_real.mostrar()
    elif st.session_state.tela == "edicao":
        relatorios_edicao.mostrar()