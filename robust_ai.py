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
    
    # Prepare features
    features = {'val': df_filtered[col], 'ratio': ratio}
    
    # Add time patterns if DATE is available
    if 'DATE' in df_filtered.columns:
        # Day of month (1-31)
        features['day_of_month'] = df_filtered['DATE'].dt.day
        # Identify typical peak periods: start of month (<=5) or end of month (>=25)
        features['is_peak_period'] = ((df_filtered['DATE'].dt.day <= 5) | (df_filtered['DATE'].dt.day >= 25)).astype(int)
        # Day of week (0=Monday, 6=Sunday)
        features['day_of_week'] = df_filtered['DATE'].dt.dayofweek
        
    X = pd.DataFrame(features)
    
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
    
    feature_cols = ['import_lag1', 'import_lag2', 'import_lag3']
    
    if 'DATE' in df.columns:
        df['day_of_month'] = df['DATE'].dt.day
        df['is_peak_period'] = ((df['DATE'].dt.day <= 5) | (df['DATE'].dt.day >= 25)).astype(int)
        df['day_of_week'] = df['DATE'].dt.dayofweek
        feature_cols.extend(['day_of_month', 'is_peak_period', 'day_of_week'])
        
    X = df[feature_cols]
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

def process_ai_stock(receive_file_path: str, stock_card_folder: str, branch_code: str, enable_export_analysis: bool = False, progress_callback=None) -> dict:
    try:
        if progress_callback: progress_callback(5, "กำลังค้นหาสต็อกการ์ดสำหรับสาขา...")
        
        if not branch_code or branch_code == "-" or branch_code == "ไม่พบ":
            raise Exception("ไม่สามารถระบุสาขาจากไฟล์รับเข้าได้")
            
        stock_card_path = find_stock_card_file(stock_card_folder, branch_code)
        
        if progress_callback: progress_callback(10, f"กำลังอ่านข้อมูลสต็อกการ์ด... (อาจใช้เวลาสักครู่)")
        # ==========================================
        # 1. Read Historical Data
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
        if progress_callback: progress_callback(30, "กำลังอ่านไฟล์รับเข้า...")
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
        if progress_callback: progress_callback(40, "กำลังจับคู่ชื่อสินค้าด้วย Fuzzy Match...")
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
        
        # --- OPTIMIZATION ---
        # Filter to only analyze products present in the receive file 
        # to prevent processing tens of thousands of untouched historical products
        target_product_ids = grouped_recv['product_id'].unique()
        combined_df = combined_df[combined_df['product_id'].isin(target_product_ids)]
        
        # ==========================================
        # 3. AI Robust Z-Score Processing
        # ==========================================
        if progress_callback: progress_callback(50, "กำลังกรองประวัติเฉพาะสินค้าที่นำเข้า...")
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
            if progress_callback: progress_callback(60, "กำลังวิเคราะห์ Isolation Forest & Robust Z-Score...")
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
        # 3.5 Export & Idle Pattern Analysis (Optimized)
        # ==========================================
        if enable_export_analysis:
            if progress_callback: progress_callback(75, "กำลังวิเคราะห์ Ghost Stock & Dead Stock...")
            max_global_date = df['DATE'].max()
            
            # --- Export Stats (by product_id) ---
            sales_events = df[df['export'] > 0].copy()
            if not sales_events.empty:
                sales_events = sales_events.sort_values(['product_id', 'DATE'])
                sales_events['prev_export_date'] = sales_events.groupby('product_id')['DATE'].shift(1)
                sales_events['inter_sale_days'] = (sales_events['DATE'] - sales_events['prev_export_date']).dt.days
                
                export_stats = sales_events.groupby('product_id').agg(
                    last_export_date=('DATE', 'max'),
                    median_inter_sale_days=('inter_sale_days', 'median')
                ).reset_index()
            else:
                export_stats = pd.DataFrame(columns=['product_id', 'last_export_date', 'median_inter_sale_days'])
            
            # --- Import Stats (Historical, by product_id) ---
            import_events = df[(df['import'] > 0) & (~df['is_new_entry'])].copy()
            if not import_events.empty:
                import_events = import_events.sort_values(['product_id', 'DATE'])
                import_events['prev_import_date'] = import_events.groupby('product_id')['DATE'].shift(1)
                import_events['inbound_gap_days'] = (import_events['DATE'] - import_events['prev_import_date']).dt.days
                
                import_stats = import_events.groupby('product_id').agg(
                    last_import_date=('DATE', 'max'),
                    expected_inbound_gap=('inbound_gap_days', 'median')
                ).reset_index()
            else:
                import_stats = pd.DataFrame(columns=['product_id', 'last_import_date', 'expected_inbound_gap'])
            
            # --- Extract Current State ---
            # Get historical balance
            historical_df = df[~df['is_new_entry']].sort_values(['product_id', 'DATE'])
            last_hist = historical_df.drop_duplicates(subset=['product_id'], keep='last')[['product_id', 'balances']].copy()
            last_hist.rename(columns={'balances': 'hist_balance'}, inplace=True)
            
            # Get new entry import amounts
            new_entries = df[df['is_new_entry']].groupby('product_id')['import'].sum().reset_index()
            
            stats_df = new_entries.merge(last_hist, on='product_id', how='left')
            stats_df['hist_balance'] = stats_df['hist_balance'].fillna(0)
            stats_df['DATE'] = max_global_date
            
            # Use historical balance + new import as current balance for anomaly detection
            stats_df['balances'] = stats_df['hist_balance']
            
            # Combine stats
            stats_df = stats_df.merge(export_stats, on='product_id', how='left')
            stats_df = stats_df.merge(import_stats, on='product_id', how='left')
            
            # Clean and fill NaNs
            stats_df['median_inter_sale_days'] = stats_df['median_inter_sale_days'].fillna(2.0)
            stats_df['median_inter_sale_days'] = np.maximum(stats_df['median_inter_sale_days'], 1.0)
            
            stats_df['expected_inbound_gap'] = stats_df['expected_inbound_gap'].fillna(3.0)
            stats_df['expected_inbound_gap'] = np.maximum(stats_df['expected_inbound_gap'], 1.0)
            
            # Calculate condition metrics
            stats_df['days_idle'] = (max_global_date - stats_df['last_export_date']).dt.days.fillna(0)
            stats_df['days_since_last_import'] = (stats_df['DATE'] - stats_df['last_import_date']).dt.days.fillna(0)
            
            dynamic_idle_threshold = np.maximum(90, np.ceil(stats_df['median_inter_sale_days'] * NORMAL_CYCLE_MULTIPLIER))
            dynamic_recent_sales_threshold = np.maximum(14, stats_df['median_inter_sale_days'] * 1.5)
            
            # Ghost Stock: idle > threshold, balance > 0, import > 0
            stats_df['is_suspected_ghost'] = (
                (stats_df['days_idle'] > dynamic_idle_threshold)
                & (stats_df['balances'] > 0)
                & (stats_df['import'] > 0)
            )
            
            # Dead Stock: idle > threshold, balance > 0, import == 0 (Should not trigger on new receives)
            stats_df['is_dead_last_item'] = (
                (stats_df['days_idle'] > dynamic_idle_threshold)
                & (stats_df['balances'] > 0)
                & (stats_df['import'] == 0)
            )
            
            # Missing Inbound Bill
            stats_df['is_missing_inbound_bill'] = (
                (stats_df['days_since_last_import'] > (stats_df['expected_inbound_gap'] * 2.0))
                & (stats_df['days_idle'] <= dynamic_recent_sales_threshold)
            )
            
            # Map back to main df (Flag the new entry row so it displays correctly)
            df['is_suspected_ghost'] = False
            df['is_dead_last_item'] = False
            df['is_missing_inbound_bill'] = False
            df['is_last_row'] = df['is_new_entry']
            
            # Merge flags back
            flags = stats_df.set_index('product_id')[['is_suspected_ghost', 'is_dead_last_item', 'is_missing_inbound_bill']]
            df = df.merge(flags, on='product_id', how='left')
            df['is_suspected_ghost'] = df['is_suspected_ghost_y'].fillna(False) & df['is_last_row']
            df['is_dead_last_item'] = df['is_dead_last_item_y'].fillna(False) & df['is_last_row']
            df['is_missing_inbound_bill'] = df['is_missing_inbound_bill_y'].fillna(False) & df['is_last_row']
            df = df.drop(columns=['is_suspected_ghost_x', 'is_dead_last_item_x', 'is_missing_inbound_bill_x', 'is_suspected_ghost_y', 'is_dead_last_item_y', 'is_missing_inbound_bill_y'], errors='ignore')

        else:
            df['is_suspected_ghost'] = False
            df['is_dead_last_item'] = False
            df['is_missing_inbound_bill'] = False
            df['is_last_row'] = df['is_new_entry']

        # ==========================================
        # 4. Extract anomalies
        # ==========================================
        anomaly_mask = (
            (df['is_new_entry'] & df['is_outlier_import']) |
            (df['is_last_row'] & df['is_suspected_ghost']) |
            (df['is_last_row'] & df['is_dead_last_item']) |
            (df['is_last_row'] & df['is_missing_inbound_bill'])
        )
        
        outliers_only = df[anomaly_mask].copy()
        
        conditions = [
            outliers_only['is_dead_last_item'] == True,
            outliers_only['is_suspected_ghost'] == True,
            outliers_only['is_missing_inbound_bill'] == True,
            outliers_only['is_outlier_import'] == True
        ]
        choices = [
            'Dead Stock (ค้างนานไร้การเคลื่อนไหว)',
            'Ghost Stock (ยอดเข้า/เบิก ขัดแย้งกัน)',
            'Missing Import Bill (ฟันหลอ/ลืมคีย์รับเข้า)',
            'Over-Import (รับเข้าสูงผิดปกติ)'
        ]
        outliers_only['Anomaly_Type'] = np.select(conditions, choices, default='Unknown')
        
        # Format output
        output_df = outliers_only[['product_id', 'import', 'Robust_ZScore', 'Expected_Import', 'is_mismatch', 'Anomaly_Type']].copy()
        output_df.rename(columns={
            'product_id': 'ชื่อสินค้า',
            'import': 'จำนวนล่าสุดที่นำเข้าไป',
            'Robust_ZScore': 'ค่า Robust Z-Score',
            'Expected_Import': 'Expect Import',
            'Anomaly_Type': 'ประเภทความผิดปกติ'
        }, inplace=True)
        
        output_df['ค่า Robust Z-Score'] = output_df['ค่า Robust Z-Score'].fillna(0).round(4)
        
        # Sort by Anomaly_Type and then Robust Z-Score
        output_df = output_df.sort_values(by=['ประเภทความผิดปกติ', 'ค่า Robust Z-Score'], ascending=[True, False])
        
        # FIX: Replace NaN with None so Python json.dumps outputs 'null' instead of 'NaN'.
        # JavaScript's JSON.parse crashes on 'NaN', which silently hangs Eel!
        output_df = output_df.replace({np.nan: None})
        
        records = output_df.to_dict(orient='records')
        
        # --- Add History and Robust Parameters for Graph ---
        if progress_callback: progress_callback(90, "กำลังดึงประวัติเพื่อสร้างกราฟ...")
        
        # Build robust parameters mapping
        robust_params_dict = {}
        outliers_only_records = outliers_only[['product_id', 'unit', 'Median_dynamic', 'MAD_dynamic', 'IQR_dynamic']].to_dict('records')
        for r in outliers_only_records:
            robust_params_dict[r['product_id']] = {
                'median': float(r['Median_dynamic']) if pd.notna(r['Median_dynamic']) else 0.0,
                'mad': float(r['MAD_dynamic']) if pd.notna(r['MAD_dynamic']) else 0.0,
                'iqr': float(r['IQR_dynamic']) if pd.notna(r['IQR_dynamic']) else 0.0
            }
        
        # Optimize History building using vectorization instead of iterrows
        # 1. Filter df to only the products that are actually outliers to save time
        outlier_pids = outliers_only['product_id'].unique()
        df_hist = df[df['product_id'].isin(outlier_pids)].copy()
        
        if not df_hist.empty:
            df_hist['_orig_idx'] = df_hist.index
            df_hist = df_hist.sort_values(['product_id', 'unit', 'DATE', '_orig_idx'])
            
            # Fast bill_detail creation
            def make_detail(b, i, e):
                if i <= 0 and e <= 0: return ""
                s = f"[{str(b).strip() if pd.notna(b) else '-'}]"
                if i > 0: s += f" รับ:{float(i):g}"
                if e > 0: s += f" ขาย:{float(e):g}"
                return s
                
            df_hist['bill_detail'] = [make_detail(b, i, e) for b, i, e in zip(df_hist['Bill'], df_hist['import'], df_hist['export'])]
            df_hist['is_anomaly_point'] = df_hist['is_new_entry'] & df_hist['is_outlier_import']
            
            # Group by Date
            date_groups = df_hist.groupby(['product_id', 'unit', 'DATE'], sort=False).agg(
                import_sum=('import', 'sum'),
                export_sum=('export', 'sum'),
                last_balance=('balances', 'last'),
                is_outlier=('is_anomaly_point', 'any'),
                bill_details=('bill_detail', lambda x: [d for d in x if d])
            ).reset_index()
            
            # Format outputs
            date_groups['date_str'] = date_groups['DATE'].dt.strftime('%Y-%m-%d')
            
            history_objs = [
                {
                    'date': d_str if pd.notna(d_str) else '',
                    'bill_details': bd,
                    'import': float(i_sum),
                    'export': float(e_sum),
                    'balance': float(bal),
                    'is_outlier': bool(iso)
                } 
                for d_str, bd, i_sum, e_sum, bal, iso in zip(
                    date_groups['date_str'], date_groups['bill_details'], 
                    date_groups['import_sum'], date_groups['export_sum'], 
                    date_groups['last_balance'], date_groups['is_outlier']
                )
            ]
            
            date_groups['history_obj'] = history_objs
            
            # Group back to product level
            final_hist = date_groups.groupby('product_id')['history_obj'].apply(list).to_dict()
        else:
            final_hist = {}
            
        for record in records:
            pid = record['ชื่อสินค้า']
            record['history'] = final_hist.get(pid, [])
            record['robust_params'] = robust_params_dict.get(pid, {})
        # ---------------------------------------------------
        
        return {
            "success": True,
            "count": len(records),
            "data": records,
            "output_path": None,
            "stock_card_path": stock_card_path,
            "message": f"วิเคราะห์เสร็จสิ้น พบสินค้าผิดปกติ (Outlier) {len(records)} รายการ"
        }
        
    except Exception as e:
        logger.error(f"Error in process_ai_stock: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e),
            "data": [],
            "count": 0
        }
