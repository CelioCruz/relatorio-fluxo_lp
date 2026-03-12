import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    GooglePlanilha = None

def mostrar():
    st.title('🏪 Relatório por Loja')
    if GooglePlanilha is None: return

    try:
        gsheet = GooglePlanilha()
        dados_brutos = gsheet.aba_relatorio.get_all_records()
        if not dados_brutos: return

        coluna_loja = 'LOJA'
        lojas_unicas = sorted({str(row.get(coluna_loja, '')).strip() for row in dados_brutos if row.get(coluna_loja)})
        loja_selecionada = st.selectbox('Selecione a Loja:', lojas_unicas)

        col1, col2 = st.columns(2)
        data_de = col1.date_input('De:', datetime.now())
        data_ate = col2.date_input('Até:', datetime.now())

        resultado = defaultdict(lambda: defaultdict(float))
        for row in dados_brutos:
            if str(row.get(coluna_loja, '')).strip() != loja_selecionada: continue
            try:
                data_str = str(row.get('DATA', '')).split()[0]
                data_row = datetime.strptime(data_str, '%d/%m/%Y').date()
                if not (data_de <= data_row <= data_ate): continue
            except: continue

            vendedor = str(row.get('VENDEDOR', '')).strip() or '[SEM VENDEDOR]'
            campos = ['RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']
            for campo in campos:
                val = str(row.get(campo, 0)).replace(',', '.')
                try:
                    val_num = float(val)
                    if val_num != 0: resultado[vendedor][campo] += val_num
                except: pass

        lista_df = []
        for v, valores in resultado.items():
            linha = {'VENDEDOR': v}; linha.update(valores); lista_df.append(linha)

        df = pd.DataFrame(lista_df)
        colunas_ordem = ['VENDEDOR', 'RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']
        df = df.reindex(columns=colunas_ordem).fillna(0)

        # Resumos
        res_rec = int(df['RECEITAS'].sum())
        res_ven = int(df['VENDAS'].sum())
        res_per = int(df['PERDAS'].sum())
        res_goo = int(df['GOOGLE'].sum())

        # Inteiro Puro (1)
        for col in df.columns:
            if col != 'VENDEDOR':
                df[col] = df[col].apply(lambda x: str(int(x)) if x != 0 else '')

        st.dataframe(df)
        st.markdown('---')
        st.markdown('### Resumo')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Receitas', res_rec)
        c2.metric('Vendas', res_ven)
        c3.metric('Perdas', res_per)
        c4.metric('Google', res_goo)
    except Exception as e: st.error(f'Erro: {e}')