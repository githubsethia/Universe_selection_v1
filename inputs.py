# config.py
import AlgorithmImports as AI

CONFIG = {
    "algorithm": {
        "start_date": {  # The start date of the backtest
            "year": 2023,
            "month": 1,
            "day": 1
        },
        "end_date": {  # The end date of the backtest
            "year": 2023,
            "month": 2,
            "day": 1
        },
        "cash": 100000,  # The starting cash for the algorithm
        "universe_resolution": AI.Resolution.DAILY, # Resolution for universe selection (e.g., HOUR, MINUTE, DAILY)
        "test_one_symbol": True, # Set to True to test only one symbol
        "test_symbol": "MSFT" # Symbol to test
    },
    "universe": {
            "market_cap_filter": 1e9/2,  # $1 billion
            "volume_filter": 1e6,  # $1 million daily volume
            "turnover_filter": 1e-6,  # 1.0% daily turnover (High liquidity),0.5%-1% is medium,1e-6 means not using it
            "min_price": 10,  # $10 minimum price
            "revenue_growth_year": 0.1,  # 10% yearly revenue growth
            "revenue_growth_quarter": 0.025,  # 2.5% quarterly revenue growth
            "pe_ratio_min": 10,
            "pe_ratio_max": 200,  # keep it high to avoid filtering out stocks with no P/E ratio
            "year_low_threshold": 0.5,  # 50% above 52-week low
            "num_stocks": 100,  # Final number of stocks to select
            "max_debt_to_equity": 1.5,  # Maximum Debt-to-Equity ratio
            "universe_history_bars": 252,  # Number of days for Universe historical data
            "universe_history_resolution":AI.Resolution.Daily,  # Resolution for Universe historical data
            "market_cap_descending": False,  # Sort by market cap ascending
    },
    "rebalance": {
        "rebalance_days": 30
    }
}

