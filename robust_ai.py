import pandas as pd
import numpy as np
import datetime
import math
import os

from logger import logger

STRICT_IMPORT_BILL_PREFIXES = ('DM', 'IBK', 'IB')
OUTLIER_Z_THRESHOLD = 3.0
NORMAL_CYCLE_MULTIPLIER = 1.5
FLOAT_TOLERANCE = 1e-9

def _round_positive_qty_series(values):
    numeric = pd.to_numeric(values, errors='coerce')
    result = pd.Series(np.nan, index=numeric.index, dtype=float)
    valid = numeric.notna() & np.isfinite(numeric) & (numeric > 0)
    result.loc[valid] = np.floor(numeric.loc[valid] + 0.5)
    return result

def compute_robust_iqr_zscore_import_fast(df_filtered, col='import'):
    group_cols = ['product_id']
    if 'unit' in df_filtered.columns:
        group_cols.append('unit')

    grouped = df_filtered.groupby(group_cols)[col]

    group_median = grouped.transform('median')
    group_count = grouped.transform('count')

    q1 = grouped.transform('quantile', 0.25)
    q3 = grouped.transform('quantile', 0.75)
    iqr_scaled = (q3 - q1) * 0.7413

    mad_raw = (
        (df_filtered[col] - group_median)
        .abs()
        .groupby([df_filtered[c] for c in group_cols])
        .transform('median')
    )
    mad_scaled = mad_raw * 1.4826

    min_divisor = np.maximum(group_median * 0.3, 1.0)

    final_divisor = np.where(
        (iqr_scaled > 0) & (group_count >= 10), iqr_scaled, mad_scaled
    )
    final_divisor = np.maximum(final_divisor, min_divisor)

    diff = df_filtered[col] - group_median
    z_score = diff / final_divisor

    return z_score, group_median

def find_stock_card_file(folder_path: str, branch_code: str) -> str:
    if not os.path.exists(folder_path):
        raise Exception(f"โฟลเดอร์ {folder_path} ไม่มีอยู่จริง")
        
    branch_map = {
        "11": ["K1", "k1", "เค1", "11"],
        "21": ["K2", "k2", "เค2", "21"],
        "31": ["K3", "k3", "เค3", "31"],
        "41": ["K4", "k4", "เค4", "41"],
        "51": ["K5", "k5", "เค5", "51"],
        "SP": ["SP", "sp", "00"],
        "00": ["SP", "sp", "00"]
    }
    
    keywords = branch_map.get(branch_code, [branch_code])
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            for keyword in keywords:
                if keyword in filename:
                    return os.path.join(folder_path, filename)
    
    raise Exception(f"ไม่พบไฟล์สต็อกการ์ดสำหรับสาขา {branch_code} ในโฟลเดอร์ {folder_path} (คีย์เวิร์ดที่ค้นหา: {', '.join(keywords)})")

def process_ai_stock(receive_file_path: str, stock_card_folder: str, branch_code: str) -> dict:
    try:
        if not branch_code or branch_code == "-" or branch_code == "ไม่พบ":
            raise Exception("ไม่สามารถระบุสาขาจากไฟล์รับเข้าได้")
            
        stock_card_path = find_stock_card_file(stock_card_folder, branch_code)
        
        # ==========================================
        # 1. Read Stock Card Data (Base)
        # ==========================================
        logger.info(f"Reading stock card from {stock_card_path}")
        try:
            data = pd.read_excel(
                stock_card_path, 
                engine='calamine', 
                header=11, 
                usecols="A:F",
                dtype={'Unnamed: 3': str, 'ลด ': str, 'คงเหลือ ': str}
            )
        except Exception as e:
            # Fallback to standard openpyxl if calamine fails or layout is different
            data = pd.read_excel(stock_card_path, header=11, usecols="A:F")
            
        data.rename(columns={
            'Unnamed: 0': 'DATE',
            'Unnamed: 1': 'Bill',
            'เพิ่ม ': 'details',
            'Unnamed: 3': 'value',
            'ลด ': 'sale',
            'คงเหลือ ': 'balance'
        }, inplace=True)

        data['product_id'] = data.loc[data['DATE'] == 'รหัสสินค้า', 'sale']
        data['product_id'] = data['product_id'].ffill()

        data['unit'] = data.loc[data['DATE'].astype(str).str.strip() == 'คลัง', 'balance']
        data['unit'] = data['unit'].ffill()
        data['unit'] = data['unit'].str.extract(r'(\d+)').fillna(0).astype(int)

        data['DATE'] = pd.to_datetime(data['DATE'], format='%d/%m/%Y', errors='coerce')
        data['DATE'] = data['DATE'] - pd.DateOffset(years=543)
        data['DATE'] = pd.to_datetime(data['DATE'])
        data.dropna(subset=['DATE'], inplace=True)

        def parse_pack_piece(series_val, series_unit):
            def format_by_unit(v, u):
                try:
                    val_float = float(v)
                    unit_int = int(float(u))
                    if unit_int <= 1: return f'{val_float:.1f}'
                    decimals = len(str(unit_int - 1))
                    return f'{val_float:.{decimals}f}'
                except:
                    return '0.0'
            s_clean = pd.Series([format_by_unit(v, u) for v, u in zip(series_val, series_unit)], index=series_val.index)
            split_df = s_clean.str.split('.', expand=True)
            front = pd.to_numeric(split_df[0], errors='coerce').fillna(0).astype(int)
            back = pd.to_numeric(split_df[1], errors='coerce').fillna(0).astype(int)
            return front, back

        unit_num = pd.to_numeric(data['unit'], errors='coerce').fillna(1).astype(int)
        data['front_value'], data['back_value'] = parse_pack_piece(data['value'], data['unit'])
        data['front_sale'], data['back_sale'] = parse_pack_piece(data['sale'], data['unit'])
        data['front_balance'], data['back_balance'] = parse_pack_piece(data['balance'], data['unit'])
        
        data['import'] = data['back_value'] + (unit_num * data['front_value'])
        data['export'] = data['back_sale'] + (unit_num * data['front_sale'])
        data['balances'] = data['back_balance'] + (unit_num * data['front_balance'])

        # ==========================================
        # 2. Read Receiving Data (New Data)
        # ==========================================
        logger.info(f"Reading receiving file from {receive_file_path}")
        try:
            recv_df = pd.read_excel(receive_file_path, engine='calamine')
        except:
            recv_df = pd.read_excel(receive_file_path)
        
        # Clean RECEIVE_PIECE
        if "RECEIVE_PIECE" in recv_df.columns:
            recv_df.loc[recv_df["RECEIVE_PIECE"] == 0, "ReBplus"] = np.nan
            recv_df = recv_df[~recv_df["RECEIVE_PIECE"].isin([0, "0", 0.0])]
            
        prod_name_col = None
        for candidate in ["SKU_NAME", "GOODS_NAME", "PRODUCT_NAME", "ITEM_NAME", "ชื่อสินค้า"]:
            if candidate in recv_df.columns:
                prod_name_col = candidate
                break
        if not prod_name_col and len(recv_df.columns) > 5:
            prod_name_col = recv_df.columns[5]
            
        recv_df["RECEIVE_PIECE"] = pd.to_numeric(recv_df["RECEIVE_PIECE"], errors='coerce').fillna(0)
        recv_df = recv_df[recv_df["RECEIVE_PIECE"] > 0]
        
        # Aggregate by SKU_NAME
        grouped_recv = recv_df.groupby(prod_name_col)['RECEIVE_PIECE'].sum().reset_index()
        grouped_recv.rename(columns={prod_name_col: 'product_id', 'RECEIVE_PIECE': 'import'}, inplace=True)
        
        # Format as new data rows
        today = pd.to_datetime(datetime.datetime.now().date())
        grouped_recv['DATE'] = today
        grouped_recv['Bill'] = 'IBK-NEW' # Valid import bill prefix
        grouped_recv['details'] = ''
        grouped_recv['unit'] = 1
        grouped_recv['export'] = 0
        grouped_recv['balances'] = grouped_recv['import']
        grouped_recv['is_new_entry'] = True
        
        data['is_new_entry'] = False
        
        # Merge datasets
        combined_df = pd.concat([data, grouped_recv], ignore_index=True)
        
        # ==========================================
        # 3. AI Robust Z-Score Processing
        # ==========================================
        source = combined_df.copy()
        required_columns = ['DATE', 'Bill', 'details', 'product_id', 'import', 'export', 'balances', 'is_new_entry']
        df = source[required_columns + (['unit'] if 'unit' in source.columns else [])].copy()

        df['product_id'] = df['product_id'].astype(str).str.strip()
        df['Bill'] = df['Bill'].astype(str).str.strip()
        df['DATE'] = pd.to_datetime(df['DATE'])
        if 'unit' not in df.columns:
            df['unit'] = 'BASE'
        df['unit'] = df['unit'].astype(str).str.strip().replace('', 'BASE')
        
        for col in ['import', 'export', 'balances']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df = df.sort_values(by=['product_id', 'unit', 'DATE']).reset_index(drop=True)

        bill_upper = df['Bill'].fillna('').astype(str).str.upper().str.strip()
        df['is_valid_import_bill'] = bill_upper.str.startswith(STRICT_IMPORT_BILL_PREFIXES)

        df_imp = df[df['is_valid_import_bill'] & (df['import'] > 0)].copy()

        df['Expected_Import'] = np.nan
        df['ZScore_Import'] = np.nan
        df['is_outlier_import'] = False

        if not df_imp.empty:
            df_imp['ZScore_Import'], df_imp['_median_import'] = compute_robust_iqr_zscore_import_fast(df_imp, 'import')
            df_imp['is_outlier_import'] = (
                (df_imp['ZScore_Import'] > OUTLIER_Z_THRESHOLD)
                & ((df_imp['import'] - df_imp['_median_import']) >= 5)
            )
            df.loc[df_imp.index, 'ZScore_Import'] = df_imp['ZScore_Import']
            df.loc[df_imp.index, 'is_outlier_import'] = df_imp['is_outlier_import']

        # EWMA Prediction
        df['_ewma_expected'] = np.nan
        valid_mask = df['import'] > 0
        valid_df = df.loc[valid_mask, ['product_id', 'unit', 'import']].copy()

        if not valid_df.empty:
            valid_counts = valid_df.groupby(['product_id', 'unit'])['import'].transform('count')
            valid_df['dynamic_span'] = np.clip(valid_counts // 2, 3, 10)
            
            ewma_results = []
            for span_val in range(3, 11):
                span_subset = valid_df[valid_df['dynamic_span'] == span_val]
                if not span_subset.empty:
                    span_ewma = span_subset.groupby(['product_id', 'unit'])['import'].ewm(span=span_val, min_periods=1).mean()
                    span_ewma = span_ewma.reset_index(level=[0, 1], drop=True)
                    ewma_results.append(span_ewma)
            if ewma_results:
                all_ewma = pd.concat(ewma_results)
                df.loc[all_ewma.index, '_ewma_expected'] = all_ewma

        df['_ewma_expected'] = df.groupby(['product_id', 'unit'])['_ewma_expected'].ffill().bfill()
        df['Expected_Import'] = np.where(df['import'] > 0, df['_ewma_expected'], np.nan)
        
        expected_mask = (df['import'] > 0) & df['Expected_Import'].notna()
        df.loc[expected_mask, 'Expected_Import'] = _round_positive_qty_series(df.loc[expected_mask, 'Expected_Import'])
        
        # ==========================================
        # 4. Extract newly added entries & filter Outliers
        # ==========================================
        new_entries = df[df['is_new_entry'] == True].copy()
        
        outliers_only = new_entries[new_entries['is_outlier_import'] == True]
        
        # Format output
        output_df = outliers_only[['product_id', 'import', 'ZScore_Import', 'Expected_Import']].copy()
        output_df.rename(columns={
            'product_id': 'ชื่อสินค้า',
            'import': 'จำนวนล่าสุดที่นำเข้าไป',
            'ZScore_Import': 'ค่า Robust Zscore',
            'Expected_Import': 'Expect Import'
        }, inplace=True)
        
        output_df['ค่า Robust Zscore'] = output_df['ค่า Robust Zscore'].round(2)
        
        # Sort by Robust Zscore descending (highest anomaly first)
        output_df = output_df.sort_values(by='ค่า Robust Zscore', ascending=False)
        
        records = output_df.to_dict(orient='records')
        
        # Save output Excel in the same directory as receive file
        output_dir = os.path.dirname(receive_file_path)
        output_name = f"AI_Outlier_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        output_path = os.path.join(output_dir, output_name)
        
        output_df.to_excel(output_path, index=False)
        logger.info(f"Saved AI Outlier Report to {output_path}")
        
        return {
            "success": True,
            "count": len(records),
            "data": records,
            "output_path": output_path,
            "stock_card_path": stock_card_path,
            "message": f"วิเคราะห์เสร็จสิ้น พบสินค้าผิดปกติ (Outlier) {len(records)} รายการ (บันทึกไฟล์: {output_name})"
        }
        
    except Exception as e:
        logger.error(f"Error in process_ai_stock: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e),
            "data": [],
            "count": 0
        }
