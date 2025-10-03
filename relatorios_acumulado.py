import streamlit as st
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import io


try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar 'google_planilha.py': {e}")
    st.stop()

def parse_date(date_str):
    """Converte string no formato dd/mm/yyyy para datetime.date ou None se inválido."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None

def mostrar():
    st.title("📊 Relatório Completo por Loja e Vendedor")

    try:
        gsheet = GooglePlanilha()
    except Exception as e:
        st.error(f"Não foi possível conectar ao Google Sheets:\n{e}")
        return

    try:
        dados = gsheet.aba_relatorio.get_all_records()
        if not dados:
            st.warning("Nenhum dado encontrado na planilha.")
            return
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # Detectar colunas essenciais
    coluna_loja = coluna_data = coluna_vendedor = coluna_reserva = None
    for key in dados[0].keys():
        k = key.strip().lower()
        if not coluna_loja and k in ['loja', 'unidade', 'filial', 'local']:
            coluna_loja = key
        if not coluna_data and k in ['data', 'datas', 'dt']:
            coluna_data = key
        if not coluna_vendedor and k in ['vendedor', 'vendedora', 'funcionário', 'vend']:
            coluna_vendedor = key
        if not coluna_reserva and any(p in k for p in ['reserva', 'reservas', 'agendamento']):
            coluna_reserva = key

    if not all([coluna_loja, coluna_data, coluna_vendedor, coluna_reserva]):
        st.error("Colunas essenciais não encontradas: Loja, Data, Vendedor ou Reserva.")
        return

    # Data de referência (padrão = hoje)
    hoje = datetime.now().date()
    data_selecionada = st.date_input("Selecione a data do relatório", value=hoje)
    ontem = data_selecionada - timedelta(days=1)

    # Filtrar dados válidos
    dados_validos = [
        row for row in dados
        if row.get(coluna_loja) and row.get(coluna_vendedor)
    ]

    if not dados_validos:
        st.warning("Nenhum registro com loja e vendedor válido.")
        return

    # === 1. Acumular reservas até ontem ===
    reserva_acumulada = defaultdict(float)
    for row in dados_validos:
        data_row = parse_date(row.get(coluna_data, ""))
        if data_row is None:
            continue
        if data_row <= ontem:
            loja = str(row[coluna_loja]).strip()
            vendedor = str(row[coluna_vendedor]).strip() or "[SEM VENDEDOR]"
            chave = f"{loja} - {vendedor}"
            valor = row.get(coluna_reserva, 0)
            try:
                valor = float(str(valor).replace(",", "."))
                reserva_acumulada[chave] += valor
            except (ValueError, TypeError):
                continue

    # === 2. Coletar todos os pares únicos (loja, vendedor)
    todos_pares = set()
    for row in dados_validos:
        loja = str(row[coluna_loja]).strip()
        vendedor = str(row[coluna_vendedor]).strip() or "[SEM VENDEDOR]"
        todos_pares.add((loja, vendedor))

    # === 3. Métricas do dia selecionado ===
    metricas_dia = defaultdict(lambda: defaultdict(float))
    for row in dados_validos:
        data_row = parse_date(row.get(coluna_data, ""))
        if data_row != data_selecionada:
            continue
        loja = str(row[coluna_loja]).strip()
        vendedor = str(row[coluna_vendedor]).strip() or "[SEM VENDEDOR]"
        chave = (loja, vendedor)

        # Mapear campos
        mapeamento_campos = {
            'receita': ['receita', 'receitas', 'faturamento'],
            'perda': ['perda', 'perdas', 'cancelamentos'],
            'venda': ['venda', 'vendas', 'pedidos'],
            'reserva': ['reserva', 'reservas', 'agendamento']
        }

        for campo, palavras in mapeamento_campos.items():
            for key in row.keys():
                if any(p in key.lower() for p in palavras):
                    val = row.get(key, 0)
                    try:
                        val = float(str(val).replace(",", "."))
                        metricas_dia[chave][campo] += val
                    except (ValueError, TypeError):
                        pass
                    break  # evita contar mais de uma coluna por campo

    # === 4. Montar relatório final ===
    relatorio = []
    for (loja, vendedor) in sorted(todos_pares):
        chave_str = f"{loja} - {vendedor}"
        metricas = metricas_dia[(loja, vendedor)]
        reserva_acc = reserva_acumulada.get(chave_str, 0.0)

        linha = {
            "DATA": data_selecionada.strftime("%d/%m/%Y"),
            "LOJA": loja,
            "Vendedor": vendedor,
            "RECEITA": int(round(metricas.get('receita', 0))),
            "PERDA": int(round(metricas.get('perda', 0))),
            "VENDA": int(round(metricas.get('venda', 0))),            
            "RESERVA": int(round(metricas.get('reserva', 0))),
            "RESERVA_ACUMULADA": int(round(reserva_acc))
        }
        relatorio.append(linha)

    if not relatorio:
        st.info("Nenhum dado encontrado para o período.")
        return

    df = pd.DataFrame(relatorio)
    df = df.sort_values(by=["LOJA", "Vendedor"]).reset_index(drop=True)

    st.dataframe(
        df.style.format({
            "RECEITA": "{:.0f}",
            "PERDA": "{:.0f}",
            "VENDA": "{:.0f}",
            "RESERVA": "{:.0f}",
            "RESERVA_ACUMULADA": "{:.0f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # Botão de download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatório")
    output.seek(0)
    st.download_button(
        label="📥 Baixar Relatório em Excel",
        data=output,
        file_name=f"relatorio_completo_{data_selecionada.strftime('%d-%m-%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
