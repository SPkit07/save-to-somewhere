import pandas as pd
import numpy as np
import datetime
import math
import os
import re
from rapidfuzz import process, fuzz
from sklearn.ensemble import IsolationForest
import xgboost as xgb
from logger import logger

STRICT_IMPORT_BILL_PREFIXES = ('DM', 'IBK', 'IB')
OUTLIER_Z_THRESHOLD = 3
NORMAL_CYCLE_MULTIPLIER = 1.5
FLOAT_TOLERANCE = 1e-9

def _round_positive_qty_series(values):
    numeric = pd.to_numeric(values, errors='coerce')
    result = pd.Series(np.nan, index=numeric.index, dtype=float)
    valid = numeric.notna() & np.isfinite(numeric) & (numeric > 0)
    result.loc[valid] = np.floor(numeric.loc[valid] + 0.5)
    return result

def clean_series(series):
    def process_text(text):
        if not isinstance(text, str):
            text = str(text) if pd.notna(text) else ""
        text = text.lower()
        
        # Evaluate math like 6*4 or 6x4 to 24
        text = re.sub(r'(\d+)\s*[\*xX]\s*(\d+)', lambda m: str(int(m.group(1)) * int(m.group(2))), text)
        
        # Remove common Thai unit words that mess up matching
        text = re.sub(r'(แผง|แพ็ค|แพค|กล่อง|โหล|ลัง|ขวด|อัน|ชิ้น|ซอง|มัด)\s*', '', text)
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        
        # Reduce multiple spaces to single space
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    return series.apply(process_text)

def compute_isolation_forest_outliers(df_filtered, col='import'):
    group_cols = ['product_id']
    if 'unit' in df_filtered.columns:
        group_cols.append('unit')
        
    group_median = df_filtered.groupby(group_cols)[col].transform('median')
    
    # Create ratio feature
    ratio = df_filtered[col] / (group_median + 1e-9)
    X = pd.DataFrame({'val': df_filtered[col], 'ratio': ratio})
    
    # Fit Isolation Forest
    iso = IsolationForest(contamination='auto', random_state=42)
    iso.fit(X)
    
    # Negative score_samples gives higher anomaly score for outliers
    scores = -iso.score_samples(X)
    labels = iso.predict(X) # -1 for outlier, 1 for inlier
    
    return scores, labels, group_median

def compute_xgboost_expected_import(df_filtered, col='import', is_new_col=None):
    df = df_filtered.copy()
    group_cols = ['product_id']
    if 'unit' in df.columns:
        group_cols.append('unit')
        
    df['import_lag1'] = df.groupby(group_cols)[col].shift(1).fillna(0)
    df['import_lag2'] = df.groupby(group_cols)[col].shift(2).fillna(0)
    df['import_lag3'] = df.groupby(group_cols)[col].shift(3).fillna(0)
    
    X = df[['import_lag1', 'import_lag2', 'import_lag3']]
    y = df[col]
    
    model = xgb.XGBRegressor(n_estimators=100, max_depth=3, random_state=42)
    
    if is_new_col is not None and is_new_col in df.columns:
        train_mask = ~df[is_new_col].astype(bool)
        if train_mask.sum() >= 1:
            model.fit(X[train_mask], y[train_mask])
        else:
            return pd.Series(np.nan, index=df.index)
    else:
        model.fit(X, y)
    
    expected = model.predict(X)
    return pd.Series(expected, index=df.index)

def find_stock_card_file(folder_path: str, branch_code: str) -> str:
    if not os.path.exists(folder_path):
        raise Exception(f"โฟลเดอร์ {folder_path} ไม่มีอยู่จริง")
        
    branch_map = {
        "11": ["K1", "k1", "เค1", "11"],
        "21": ["K2", "k2", "เค2", "21"],
        "31": ["K3", "k3", "เค3", "31"],
        "41": ["K4", "k4", "เค4", "41"],
        "51": ["K5", "k5", "เค5", "51"],
        "SP": ["SP", "Sp", "sp", "SUPER", "Super", "00"],
        "00": ["SP", "Sp", "sp", "SUPER", "Super", "00"]
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
        
        if "EXPORT_PIECE" in recv_df.columns:
            recv_df["EXPORT_PIECE"] = pd.to_numeric(recv_df["EXPORT_PIECE"], errors='coerce').fillna(0)
            recv_df["is_mismatch"] = recv_df["RECEIVE_PIECE"] != recv_df["EXPORT_PIECE"]
        else:
            recv_df["is_mismatch"] = False
            
        recv_df = recv_df[recv_df["RECEIVE_PIECE"] > 0]
        
        # Aggregate by SKU_NAME
        agg_dict = {'RECEIVE_PIECE': 'sum', 'is_mismatch': 'any'}
        grouped_recv = recv_df.groupby(prod_name_col).agg(agg_dict).reset_index()
        grouped_recv.rename(columns={prod_name_col: 'product_id', 'RECEIVE_PIECE': 'import'}, inplace=True)
        
        # ==========================================
        # 2.5 Fuzzy Match Receive Products to Stock Card Products
        # ==========================================
        THRESHOLD = 90
        stock_unique_products = data['product_id'].dropna().unique()
        
        # Clean both lists for matching
        stock_clean = clean_series(pd.Series(stock_unique_products)).values
        
        # Create mapping from clean string to original stock product name
        clean_to_orig = {clean_val: orig_val for clean_val, orig_val in zip(stock_clean, stock_unique_products) if clean_val}
        choices = {i: val for i, val in enumerate(clean_to_orig.keys())}
        
        recv_products = grouped_recv['product_id'].unique()
        recv_clean = clean_series(pd.Series(recv_products)).values
        
        mapped_products = {}
        for orig_recv, clean_recv in zip(recv_products, recv_clean):
            if not clean_recv:
                mapped_products[orig_recv] = orig_recv
                continue
                
            result = process.extractOne(
                clean_recv,
                choices,
                scorer=fuzz.ratio,
                score_cutoff=THRESHOLD
            )
            
            if result is not None:
                matched_clean = result[0]
                matched_orig = clean_to_orig[matched_clean]
                mapped_products[orig_recv] = matched_orig
            else:
                mapped_products[orig_recv] = orig_recv
                
        # Apply the mapping so new entries use the exact stock card name if they match
        grouped_recv['product_id'] = grouped_recv['product_id'].map(mapped_products).fillna(grouped_recv['product_id'])
        
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
        if 'is_mismatch' in source.columns:
            required_columns.append('is_mismatch')
        df = source[required_columns + (['unit'] if 'unit' in source.columns else [])].copy()
        if 'is_mismatch' not in df.columns:
            df['is_mismatch'] = False
        else:
            df['is_mismatch'] = df['is_mismatch'].fillna(False)

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
        df['Isolation_Score'] = np.nan
        df['Robust_ZScore'] = np.nan
        df['Median_dynamic'] = np.nan
        df['MAD_dynamic'] = np.nan
        df['IQR_dynamic'] = np.nan
        df['is_outlier_import'] = False

        if not df_imp.empty:
            df_imp['Isolation_Score'], df_imp['_iso_label'], df_imp['_median_import'] = compute_isolation_forest_outliers(df_imp, 'import')
            
            # --- Dynamic IQR, MAD, Median, and Robust Z-Score per product ---
            group_cols = ['product_id', 'unit']
            # Median
            df_imp['Median_dynamic'] = df_imp.groupby(group_cols)['import'].transform('median')
            
            # MAD
            abs_dev = (df_imp['import'] - df_imp['Median_dynamic']).abs()
            df_imp['MAD_dynamic'] = abs_dev.groupby([df_imp['product_id'], df_imp['unit']]).transform('median')
            
            # IQR
            q75 = df_imp.groupby(group_cols)['import'].transform(lambda x: x.quantile(0.75))
            q25 = df_imp.groupby(group_cols)['import'].transform(lambda x: x.quantile(0.25))
            df_imp['IQR_dynamic'] = q75 - q25
            
            # Robust Z-Score Calculation
            # Fallback if MAD is 0 -> use IQR/1.349, if still 0 -> use 1.0
            mad_adj = df_imp['MAD_dynamic'].replace(0, np.nan)
            mad_adj = mad_adj.fillna(df_imp['IQR_dynamic'] / 1.349)
            mad_adj = mad_adj.replace(0, np.nan).fillna(1.0)
            
            df_imp['Robust_ZScore'] = 0.6745 * (df_imp['import'] - df_imp['Median_dynamic']) / mad_adj
            # ----------------------------------------------------------------

            df_imp['is_outlier_import'] = (
                (df_imp['_iso_label'] == -1)
                & ((df_imp['import'] - df_imp['_median_import']) >= 5)
            )
            df.loc[df_imp.index, 'Isolation_Score'] = df_imp['Isolation_Score']
            df.loc[df_imp.index, 'Robust_ZScore'] = df_imp['Robust_ZScore']
            df.loc[df_imp.index, 'Median_dynamic'] = df_imp['Median_dynamic']
            df.loc[df_imp.index, 'MAD_dynamic'] = df_imp['MAD_dynamic']
            df.loc[df_imp.index, 'IQR_dynamic'] = df_imp['IQR_dynamic']
            df.loc[df_imp.index, 'is_outlier_import'] = df_imp['is_outlier_import']

        # XGBoost Prediction
        df['_xgb_expected'] = np.nan
        valid_mask = df['import'] > 0
        valid_df = df.loc[valid_mask, ['product_id', 'unit', 'import', 'is_new_entry']].copy()

        if not valid_df.empty:
            df.loc[valid_mask, '_xgb_expected'] = compute_xgboost_expected_import(valid_df, 'import', 'is_new_entry')

        df['_xgb_expected'] = df.groupby(['product_id', 'unit'])['_xgb_expected'].ffill().bfill()
        df['Expected_Import'] = np.where(df['import'] > 0, df['_xgb_expected'], np.nan)
        
        expected_mask = (df['import'] > 0) & df['Expected_Import'].notna()
        df.loc[expected_mask, 'Expected_Import'] = _round_positive_qty_series(df.loc[expected_mask, 'Expected_Import'])
        
        # ==========================================
        # 4. Extract newly added entries & filter Outliers
        # ==========================================
        new_entries = df[df['is_new_entry'] == True].copy()
        
        outliers_only = new_entries[new_entries['is_outlier_import'] == True]
        
        # Format output
        output_df = outliers_only[['product_id', 'import', 'Robust_ZScore', 'Expected_Import', 'is_mismatch']].copy()
        output_df.rename(columns={
            'product_id': 'ชื่อสินค้า',
            'import': 'จำนวนล่าสุดที่นำเข้าไป',
            'Robust_ZScore': 'ค่า Robust Z-Score',
            'Expected_Import': 'Expect Import'
        }, inplace=True)
        
        output_df['ค่า Robust Z-Score'] = output_df['ค่า Robust Z-Score'].round(4)
        
        # Sort by Robust Z-Score descending (highest anomaly first)
        output_df = output_df.sort_values(by='ค่า Robust Z-Score', ascending=False)
        
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
