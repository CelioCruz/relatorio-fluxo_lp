import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    st.stop()

def eh_dia_util(data):
    return data.weekday() < 5

def obter_ultimo_dia_util(data_base):
    um_dia = timedelta(days=1)
    target = data_base - um_dia
    while not eh_dia_util(target):
        target -= um_dia
    return target

def mostrar():
    st.title('🛠️ Gestão de Dados (Editar / Excluir / Adicionar)')
    
    try:
        gsheet = GooglePlanilha()
        lista_completa = gsheet.aba_relatorio.get_all_values()
        if len(lista_completa) < 1:
            st.warning('📭 Planilha vazia.')
            return

        cabecalho_exato = ['LOJA', 'DATA', 'HORA', 'VENDEDOR', 'CLIENTE', 'ATENDIMENTOS', 'RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'PESQUISAS', 'EXAME DE VISTA', 'GOOGLE', 'USUARIO_ALTERACAO']
        
        df_base = pd.DataFrame(lista_completa[1:], columns=lista_completa[0])
        for col in cabecalho_exato:
            if col not in df_base.columns:
                df_base[col] = ''
        
        df_base = df_base[cabecalho_exato].copy()
        df_base['ID_REAL'] = range(2, len(df_base) + 2) 

    except Exception as e:
        st.error(f'❌ Erro ao carregar dados: {e}')
        return

    hoje = datetime.now().date()
    dia_anterior_util = obter_ultimo_dia_util(hoje)
    
    st.sidebar.subheader('📅 Filtro de Exibição')
    filtro_data = st.sidebar.date_input('Mostrar dados de:', dia_anterior_util)
    data_str_filtro = filtro_data.strftime('%d/%m/%Y')

    df_filtrado = df_base[df_base['DATA'] == data_str_filtro].copy()

    if df_filtrado.empty:
        st.info(f'📭 Nenhum dado encontrado para {data_str_filtro}.')
        df_filtrado = pd.DataFrame(columns=cabecalho_exato + ['ID_REAL'])

    st.subheader(f'📝 Editando registros de: {data_str_filtro}')
    
    df_editado = st.data_editor(
        df_filtrado,
        num_rows='dynamic',
        width="stretch",
        column_order=cabecalho_exato,
        key='data_editor_gestao'
    )

    if st.button('💾 Salvar Alterações no Google Sheets', type='primary'):
        try:
            timestamp = datetime.now().strftime('%d/%m %H:%M')
            ids_originais = set(df_filtrado['ID_REAL'].tolist())
            ids_mantidos = set(df_editado['ID_REAL'].dropna().tolist())
            ids_para_excluir = sorted([int(idx) for idx in list(ids_originais - ids_mantidos)], reverse=True)

            novas_linhas = df_editado[df_editado['ID_REAL'].isna() | (df_editado['ID_REAL'] == '')].copy()
            df_comum_orig = df_filtrado[df_filtrado['ID_REAL'].isin(ids_mantidos)].set_index('ID_REAL')
            df_comum_edit = df_editado[df_editado['ID_REAL'].isin(ids_mantidos)].set_index('ID_REAL')

            # 1. Excluir
            for idx in ids_para_excluir:
                gsheet.aba_relatorio.delete_rows(idx)

            # 2. Editar
            for idx in ids_mantidos:
                linha_orig = df_comum_orig.loc[idx]
                linha_edit = df_comum_edit.loc[idx]
                mudou = False
                for col in cabecalho_exato[:-1]:
                    if str(linha_orig[col]) != str(linha_edit[col]):
                        mudou = True
                        break
                if mudou:
                    valores = linha_edit.tolist()
                    valores[-1] = f'Editado em {timestamp}'
                    gsheet.aba_relatorio.update(f'A{idx}:N{idx}', [valores])

            # 3. Adicionar
            for _, row in novas_linhas.iterrows():
                valores = [row.get(c, '') for c in cabecalho_exato]
                valores[-1] = f'Adicionado em {timestamp}'
                if not valores[1]: valores[1] = data_str_filtro
                gsheet.aba_relatorio.append_row(valores)

            st.success('✅ Planilha atualizada com sucesso!')
            st.rerun()

        except Exception as e:
            st.error(f'❌ Erro ao salvar: {e}')