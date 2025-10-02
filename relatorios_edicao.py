import streamlit as st
import pandas as pd
from google_planilha import GooglePlanilha
from datetime import datetime, timedelta

NOME_COLUNA_USUARIO = "USUARIO_ALTERACAO"
NOME_COLUNA_DATA = "DATA"  # ← Ajuste se sua coluna tiver outro nome

COLUNAS_NUMERICAS = {
    "ATENDIMENTOS", "RECEITAS", "PERDAS", "VENDAS",
    "RESERVAS", "PESQUISAS", "EXAME DE VISTA"
}

def preparar_valor(val, eh_numerica: bool):
    if pd.isna(val) or val is None or str(val).strip().lower() in ['nan', 'none', '']:
        return ""
    val_str = str(val).strip()
    if eh_numerica:
        try:
            num = float(val_str.replace(",", "."))
            return int(num) if num.is_integer() else num
        except:
            return val_str
    return val_str

def parse_data_brasil(data_str):
    """Converte string dd/mm/YYYY para datetime."""
    try:
        return datetime.strptime(data_str.strip(), "%d/%m/%Y")
    except:
        return None

def mostrar():
    st.title("🛠️ Edição e Exclusão de Linhas")
    st.info("✏️ Edite células em um período específico. **Não é possível adicionar novas linhas.**")

    try:
        gsheet = GooglePlanilha()
        lista = gsheet.aba_relatorio.get_all_values()
        if len(lista) < 2:
            st.warning("Nenhum dado para editar.")
            return

        cabecalho = lista[0]
        dados = lista[1:]

        # Garantir coluna de usuário
        if NOME_COLUNA_USUARIO not in cabecalho:
            cabecalho.append(NOME_COLUNA_USUARIO)
            for linha in dados:
                linha.append("")

        df_completo = pd.DataFrame(dados, columns=cabecalho)
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return

    # --- Verificar se coluna de data existe ---
    if NOME_COLUNA_DATA not in df_completo.columns:
        st.error(f"Coluna de data '{NOME_COLUNA_DATA}' não encontrada.")
        return

    # --- Converter coluna de data para datetime ---
    df_completo['_data_parsed'] = df_completo[NOME_COLUNA_DATA].apply(parse_data_brasil)
    df_valido = df_completo.dropna(subset=['_data_parsed']).copy()

    if df_valido.empty:
        st.warning("Nenhuma data válida encontrada.")
        return

    # --- Definir intervalo de datas ---
    datas_validas = df_valido['_data_parsed']
    data_min = datas_validas.min().date()
    data_max = datas_validas.max().date()

    # --- Filtros de data ---
    st.subheader("📅 Filtrar por Período")
    col_dt1, col_dt2 = st.columns(2)
    with col_dt1:
        data_inicio = st.date_input("Data Inicial", value=data_max - timedelta(days=7), min_value=data_min, max_value=data_max)
    with col_dt2:
        data_fim = st.date_input("Data Final", value=data_max, min_value=data_min, max_value=data_max)

    if data_inicio > data_fim:
        st.error("⚠️ Data inicial não pode ser maior que a final.")
        return

    # --- Filtrar dados ---
    mascara = (df_valido['_data_parsed'].dt.date >= data_inicio) & (df_valido['_data_parsed'].dt.date <= data_fim)
    df_filtrado = df_valido[mascara].copy()
    df_filtrado = df_filtrado.drop(columns=['_data_parsed'])  # remover coluna auxiliar

    if df_filtrado.empty:
        st.info("Nenhum dado encontrado no período selecionado.")
        return

    st.success(f"Mostrando {len(df_filtrado)} linhas do período {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}")

    # --- Editor ---
    df_editado = st.data_editor(
        df_filtrado,
        num_rows="fixed",
        use_container_width=True,
        key="editor"
    )

    if st.button("💾 Salvar Alterações", type="primary"):
        try:
            timestamp = datetime.now().strftime('%d/%m %H:%M')
            cabecalho_final = df_editado.columns.tolist()

            # Atualizar cabeçalho se necessário
            if gsheet.aba_relatorio.row_values(1) != cabecalho_final:
                gsheet.aba_relatorio.update('1:1', [cabecalho_final])

            # Mapear índices originais das linhas filtradas
            indices_originais = df_filtrado.index.tolist()

            # Preparar atualizações
            for idx_pos, (idx_orig, row_edit) in enumerate(zip(indices_originais, df_editado.itertuples(index=False))):
                linha_editada = list(row_edit)
                linha_original = df_completo.loc[idx_orig].copy()

                # Verificar alteração
                alterado = False
                for j, col in enumerate(cabecalho_final):
                    if col == NOME_COLUNA_USUARIO:
                        continue
                    eh_num = col in COLUNAS_NUMERICAS
                    val_orig = preparar_valor(linha_original[col], eh_num)
                    val_edit = preparar_valor(linha_editada[j], eh_num)
                    if val_orig != val_edit:
                        alterado = True
                        break

                if alterado:
                    # Atualizar coluna de usuário
                    usuario_idx = cabecalho_final.index(NOME_COLUNA_USUARIO)
                    linha_editada[usuario_idx] = f"Editado em {timestamp}"
                    # Atualizar no Google Sheets (linha = idx_orig + 2)
                    gsheet.aba_relatorio.update(f"{idx_orig + 2}:{idx_orig + 2}", [linha_editada])

            st.success("✅ Alterações salvas com sucesso!")
        except Exception as e:
            st.error(f"❌ Erro ao salvar: {e}")