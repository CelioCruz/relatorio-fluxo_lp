import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    GooglePlanilha = None

def mostrar():
    st.title('👤 Relatório por Vendedor')
    if GooglePlanilha is None: return

    try:
        gsheet = GooglePlanilha()
        dados_brutos = gsheet.aba_relatorio.get_all_records()
        vendedores = sorted(list(set([str(row.get('VENDEDOR', '')).strip() for row in dados_brutos if row.get('VENDEDOR')])))
        vendedor_selecionado = st.selectbox('Selecione o Vendedor:', vendedores)
        
        col1, col2 = st.columns(2)
        data_de = col1.date_input('De:', datetime.now())
        data_ate = col2.date_input('Até:', datetime.now())

        dados_filtrados = []
        for row in dados_brutos:
            if str(row.get('VENDEDOR', '')).strip() == vendedor_selecionado:
                try:
                    data_row = datetime.strptime(str(row.get('DATA', '')).split()[0], '%d/%m/%Y').date()
                    if data_de <= data_row <= data_ate: dados_filtrados.append(row)
                except: continue

        df = pd.DataFrame(dados_filtrados)
        colunas_exatas = ['DATA', 'LOJA', 'CLIENTE', 'RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']
        df = df.reindex(columns=colunas_exatas).fillna(0)
        
        # Somas para o resumo (antes de formatar)
        res_rec = int(pd.to_numeric(df['RECEITAS'], errors='coerce').sum())
        res_per = int(pd.to_numeric(df['PERDAS'], errors='coerce').sum())
        res_ven = int(pd.to_numeric(df['VENDAS'], errors='coerce').sum())        
        res_res = int(pd.to_numeric(df['RESERVAS'], errors='coerce').sum())
        res_goo = int(pd.to_numeric(df['GOOGLE'], errors='coerce').sum())

        # Formatação para Inteiro (1 em vez de 1.0) e Vazio
        for col in df.columns:
            if col not in ['DATA', 'LOJA', 'CLIENTE']:
                df[col] = df[col].apply(lambda x: str(int(float(str(x).replace(',', '.')))) if str(x) not in ['0', '0.0', ''] else '')

        st.dataframe(df, width="stretch")
        st.markdown('---')
        st.markdown('### Resumo')
        cols = st.columns(5)
        cols[0].metric('Receitas', res_rec)        
        cols[1].metric('Perdas', res_per)
        cols[2].metric('Vendas', res_ven)
        cols[3].metric('Reservas', res_res)
        cols[4].metric('Google', res_goo)
    except Exception as e: st.error(f'Erro: {e}')