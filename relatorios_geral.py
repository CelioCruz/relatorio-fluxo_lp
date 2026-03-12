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
    st.title('📊 Relatório Geral (Todas as Lojas)')
    if GooglePlanilha is None: return

    try:
        gsheet = GooglePlanilha()
        dados_brutos = gsheet.aba_relatorio.get_all_records()
        if not dados_brutos: return

        col1, col2 = st.columns(2)
        data_de = col1.date_input('De:', datetime.now())
        data_ate = col2.date_input('Até:', datetime.now())

        resultado = defaultdict(lambda: defaultdict(float))
        for row in dados_brutos:
            try:
                data_str = str(row.get('DATA', '')).split()[0]
                data_row = datetime.strptime(data_str, '%d/%m/%Y').date()
                if not (data_de <= data_row <= data_ate): continue
            except: continue

            loja = str(row.get('LOJA', '')).strip() or '[SEM LOJA]'
            for campo in ['RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']:
                val = str(row.get(campo, 0)).replace(',', '.')
                try:
                    val_num = float(val)
                    if val_num != 0: resultado[loja][campo] += val_num
                except: pass

        lista_df = []
        for loja, valores in resultado.items():
            linha = {'LOJA': loja}; linha.update(valores); lista_df.append(linha)

        df = pd.DataFrame(lista_df)
        ordem = ['LOJA', 'RECEITAS', 'PERDAS', 'VENDAS', 'RESERVAS', 'GOOGLE', 'PESQUISAS', 'EXAME DE VISTA']
        df = df.reindex(columns=ordem).fillna(0)

        # Resumo Numérico
        res_rec = int(df['RECEITAS'].sum())
        res_ven = int(df['VENDAS'].sum())
        res_per = int(df['PERDAS'].sum())
        res_goo = int(df['GOOGLE'].sum())

        # Formatação da Tabela: Inteiro ou Vazio
        for col in df.columns:
            if col != 'LOJA':
                df[col] = df[col].apply(lambda x: str(int(x)) if x != 0 else '')

        st.dataframe(df)
        st.markdown('---')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Receitas', res_rec)
        c2.metric('Vendas', res_ven)
        c3.metric('Perdas', res_per)
        c4.metric('Google', res_goo)
    except Exception as e: st.error(f'Erro: {e}')