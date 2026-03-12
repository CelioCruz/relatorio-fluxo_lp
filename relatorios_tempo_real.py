import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import sys
import os
from collections import defaultdict
import pandas as pd
import io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    GooglePlanilha = None

def mostrar():
    st.title('⏱️ Relatório em Tempo Real')
    st_autorefresh(interval=30000, key='tempo_real_refresh')

    if GooglePlanilha is None:
        st.warning('⚠️ Módulo GooglePlanilha não carregado.')
        return

    try:
        gsheet = GooglePlanilha()
        dados_brutos = gsheet.aba_relatorio.get_all_records()
        if not dados_brutos: return
        
        coluna_loja = 'LOJA'
        lojas_unicas = sorted({str(row[coluna_loja]).strip() for row in dados_brutos if row.get(coluna_loja)})
        loja = st.selectbox('Selecione a loja:', lojas_unicas)

        hoje_str = datetime.now().strftime('%d/%m/%Y')
        dados_hoje = [row for row in dados_brutos if str(row.get('LOJA')).strip().upper() == str(loja).upper() and str(row.get('DATA', '')).strip().split()[0] == hoje_str]

        resultado = defaultdict(lambda: defaultdict(int))
        for row in dados_hoje:
            vendedor = str(row.get('VENDEDOR', '')).strip() or '[SEM VENDEDOR]'
            for c in ['RECEITAS', 'VENDAS', 'PERDAS', 'PESQUISAS', 'EXAME DE VISTA', 'RESERVAS', 'GOOGLE']:
                try:
                    val = int(float(str(row.get(c, 0)).replace(',', '.')))
                    if val != 0: resultado[vendedor][c] += val
                except: pass

        lista_df = []
        for v, m in resultado.items():
            linha = {'Vendedor': v}
            linha.update(m)
            lista_df.append(linha)

        df = pd.DataFrame(lista_df)
        colunas_ordem = ['Vendedor', 'RECEITAS', 'VENDAS', 'PERDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']
        df = df.reindex(columns=colunas_ordem).fillna(0)
        
        # Limpeza e formatação para Inteiro sem .0
        for col in df.columns:
            if col != 'Vendedor':
                df[col] = df[col].apply(lambda x: str(int(x)) if x != 0 else '')

        st.markdown(f'### 🏪 **{loja}**')
        st.dataframe(df)
    except Exception as e: st.error(f'Erro: {e}')