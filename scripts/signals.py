from pathlib import Path
import click
from tqdm import tqdm

import numpy as np
import pandas as pd

from service.App import *
from common.model_store import *
from common.generators import generate_feature_set

"""
Generate new derived columns according to the signal definitions.
The transformations are applied to the results of ML predictions.
"""

@click.command()
@click.option('--config_file', '-c', type=click.Path(), default='', help='Configuration file name')
def main(config_file):
    """
    """
    load_config(config_file)
    config = App.config

    App.model_store = ModelStore(config)
    App.model_store.load_models()

    time_column = config["time_column"]

    now = datetime.now()

    symbol = config["symbol"]
    data_path = Path(config["data_folder"]) / symbol

    # Determine desired data length depending on train/predict mode
    is_train = config.get("train")
    if is_train:
        window_size = config.get("train_length")
    else:
        window_size = config.get("predict_length")
    features_horizon = config.get("features_horizon")
    if window_size:
        window_size += features_horizon

    #
    # Load data
    #
    file_path = data_path / config.get("predict_file_name")
    if not file_path.exists():
        print(f"ERROR: Input file does not exist: {file_path}")
        return

    print(f"Loading data from source data file {file_path}...")
    if file_path.suffix == ".parquet":
        df = pd.read_parquet(file_path)
    elif file_path.suffix == ".csv":
        df = pd.read_csv(file_path, parse_dates=[time_column], date_format="ISO8601")
    else:
        print(f"ERROR: Unknown extension of the input file '{file_path.suffix}'. Only 'csv' and 'parquet' are supported")
        return

    print(f"Finished loading {len(df)} records with {len(df.columns)} columns from the source file {file_path}")

    # Select only the data necessary for analysis
    if window_size:
        df = df.tail(window_size)
        df = df.reset_index(drop=True)

    print(f"Input data size {len(df)} records. Range: [{df.iloc[0][time_column]}, {df.iloc[-1][time_column]}]")

    #
    # Apply signal generators
    #
    feature_sets = config.get("signal_sets", [])
    if not feature_sets:
        print(f"ERROR: no signal sets defined. Nothing to process.")
        return

    print(f"Start generating features for {len(df)} input records.")

    all_features = []
    for i, fs in enumerate(feature_sets):
        fs_now = datetime.now()
        print(f"Start feature set {i}/{len(feature_sets)}. Generator {fs.get('generator')}...")

        df, new_features = generate_feature_set(df, fs, config, App.model_store, last_rows=0)

        all_features.extend(new_features)

        fs_elapsed = datetime.now() - fs_now
        print(f"Finished feature set {i}/{len(feature_sets)}. Generator {fs.get('generator')}. Features: {len(new_features)}. Time: {str(fs_elapsed).split('.')[0]}")

    print(f"Finished generating features.")

    #
    # === AI AGENT INTEGRATION ===
    #
    print("Initializing AI Agent for Signal Refinement...")
    try:
        from service.ai_agent import AIAgent
        agent = AIAgent(config)
        
        # We only want to run AI on the most recent rows to save time/cost, or all if specified
        # For now, let's run on the last 5 rows as a showcase
        ai_rows = 5 
        print(f"Running AI Refinement on last {ai_rows} rows...")
        
        # Ensure we have the necessary context columns
        # We need 'trade_score' (generated above) and 'close_RSI_14', 'high_low_close_ATR_14' (from input df)
        # Note: Column names might vary based on config, but we hardcode for this integration
        
        # Create new columns
        df['ai_action'] = "WAIT"
        df['ai_reasoning'] = ""
        
        for i in range(len(df) - ai_rows, len(df)):
            if i < 0: continue
            
            row = df.iloc[i]
            
            # Extract Context
            rsi = row.get('close_RSI_14', 50.0)
            atr = row.get('high_low_close_ATR_14', 0.0)
            score = row.get('trade_score', 0.0)
            
            context = {"rsi": float(rsi), "atr": float(atr)}
            
            # Ask AI
            response = agent.get_market_sentiment(float(score), context)
            
            # Simple parsing (In production, use structured JSON output)
            # Assuming format: "Action: BUY\nReasoning: ..."
            action = "HOLD"
            reasoning = response
            
            if "Action: BUY" in response: action = "BUY"
            elif "Action: SELL" in response: action = "SELL"
            
            df.at[i, 'ai_action'] = action
            df.at[i, 'ai_reasoning'] = reasoning.replace("\n", " | ")
            
            print(f"Row {i}: Score={score:.2f} -> AI says {action}")

        all_features.extend(['ai_action', 'ai_reasoning'])
            
    except Exception as e:
        print(f"AI Agent failed: {e}")
        import traceback
        traceback.print_exc()

    print("AI Agent Refinement Complete.")

    # Handle NULLs
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    na_df = df[ df[all_features].isna().any(axis=1) ]
    if len(na_df) > 0:
        print(f"WARNING: There exist {len(na_df)} rows with NULLs in some columns")
        print(f"Number of NULL values:")
        print(df[all_features].isnull().sum().sort_values(ascending=False))

    #
    # Choose columns to stored
    #
    out_columns = [time_column, "open", "high", "low", "close"]  # Source data
    out_columns.extend(config.get('labels'))  # True labels
    out_columns = [x for x in out_columns if x in df.columns]
    out_columns.extend(all_features)

    out_df = df[out_columns]

    #
    # Store data
    #
    out_path = data_path / config.get("signal_file_name")

    print(f"Storing signals with {len(out_df)} records and {len(out_df.columns)} columns in output file {out_path}...")
    if out_path.suffix == ".parquet":
        out_df.to_parquet(out_path, index=False)
    elif out_path.suffix == ".csv":
        out_df.to_csv(out_path, index=False, float_format='%.6f')
    else:
        print(f"ERROR: Unknown extension of the output file '{out_path.suffix}'. Only 'csv' and 'parquet' are supported")
        return

    print(f"Signals stored in file: {out_path}. Length: {len(out_df)}. Columns: {len(out_df.columns)}")

    elapsed = datetime.now() - now
    print(f"Finished signal generation in {str(elapsed).split('.')[0]}")


if __name__ == '__main__':
    main()
