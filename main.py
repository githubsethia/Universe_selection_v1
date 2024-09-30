
# region imports
from AlgorithmImports import *
from datetime import timedelta
import numpy as np
# endregion

class Universeselectionv1(QCAlgorithm):

    def Initialize(self):
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.SetStartDate(2020, 1, 1)  # Set start date
        self.SetEndDate(2024, 8, 31)    # Set end date
        self.SetCash(100000)           # Set strategy cash

        # Move all hard-coded values here
        self.market_cap_filter = 1e9  # $1 billion
        self.volume_filter = 1e6  # $1 million daily volume
        self.turnover_filter = 1e-6  # 1.0% daily turnover (High liquidity),0.5%-1% is medium
        self.min_price = 10  # $10 minimum price
        self.revenue_growth_year = 0.1  # 10% yearly revenue growth
        self.revenue_growth_quarter = 0.025  # 2.5% quarterly revenue growth
        self.pe_ratio_min = 10
        self.pe_ratio_max = 99
        self.year_low_threshold = 0.5  # 50% above 52-week low
        self.num_stocks = 100  # Final number of stocks to select
        self.max_debt_to_equity = 1.5  # Maximum Debt-to-Equity ratio
        self.history_bars = 252  # Number of days for historical data

        # Rebalance parameters
        self.rebalance_days = 30
        self.next_rebalance = self.StartDate
        self.portfolioTargets = []
        self.activeStocks = set()  # To store our selected universe
        self.counter = 0

    def CoarseSelectionFunction(self, coarse):
        if self.Time < self.next_rebalance:
            return Universe.Unchanged

        coarse_list = list(coarse)
        if len(coarse_list) == 0:
            return Universe.Unchanged

        self.Log(f"Initial universe size: {len(coarse_list)}")

        coarse = [c for c in coarse if c.MarketCap > self.market_cap_filter]
        self.Log(f"After market cap filter: {len(coarse)}")

        high_volume = [c for c in coarse if c.DollarVolume > self.volume_filter]
        self.Log(f"After high volume filter: {len(high_volume)}")

        high_turnover = [c for c in high_volume if c.DollarVolume / c.MarketCap > self.turnover_filter]
        self.Log(f"After high turnover filter: {len(high_turnover)}")

        price_filter = [c for c in high_turnover if c.Price > self.min_price]
        self.Log(f"After price filter: {len(price_filter)}")

        has_fundamental = [c for c in price_filter if c.has_fundamental_data]
        self.Log(f"After has fundamental data filter: {len(has_fundamental)}")

        filtered_stocks = {c.Symbol: c for c in has_fundamental}

        return list(filtered_stocks.keys())

    def FineSelectionFunction(self, fine):
        if self.Time < self.next_rebalance:
            return Universe.Unchanged

        fine_list = list(fine)
        if len(fine_list) == 0:
            return Universe.Unchanged
        # Use RevenueGrowth
        high_growth = [f for f in fine if not np.isnan(f.OperationRatios.RevenueGrowth.OneYear)
                       and f.OperationRatios.RevenueGrowth.OneYear > self.revenue_growth_year
                       and not np.isnan(f.OperationRatios.RevenueGrowth.ThreeMonths)
                       and f.OperationRatios.RevenueGrowth.ThreeMonths > self.revenue_growth_quarter]
        self.Log(f"After revenue growth filter: {len(high_growth)}")

        # Check if PERatio is available before filtering
        pe_filter = [f for f in high_growth if f.ValuationRatios.PERatio is not None and
                    self.pe_ratio_min < f.ValuationRatios.PERatio < self.pe_ratio_max]
        self.Log(f"After P/E ratio filter: {len(pe_filter)}")

        # check for low debt to equity ratio
        low_debt_equity = [f for f in pe_filter if f.OperationRatios.TotalDebtEquityRatio.has_value
                           and f.OperationRatios.TotalDebtEquityRatio.value < self.max_debt_to_equity]

        # Use try-except for history to handle any potential issues
        try:
            history = self.History([f.Symbol for f in low_debt_equity], self.history_bars, Resolution.Daily)
            sma_filter = []
            year_low_filter = []
            
            for f in low_debt_equity:
                if f.Symbol in history.index.get_level_values('symbol'):
                    symbol_history = history.loc[f.Symbol]
                    if len(symbol_history) > 0:
                        sma = symbol_history['close'].mean()
                        year_low = symbol_history['close'].min()
                        
                        if f.Price > sma:
                            sma_filter.append(f)
                            
                            if f.Price > year_low * (1 + self.year_low_threshold):
                                year_low_filter.append(f)
            
            self.Log(f"After SMA filter: {len(sma_filter)}")
            self.Log(f"After 52-week low filter: {len(year_low_filter)}")

        except Exception as e:
            self.Log(f"An error occurred: {str(e)}")

        # rank based on highest market cap
        ranked_stocks = sorted(year_low_filter, key=lambda x: x.MarketCap,reverse=True)

        final_selection = ranked_stocks[:self.num_stocks]
        self.Log(f"Final selection: {len(final_selection)}")
        self.Log(f"Final selection: {[f.Symbol.Value for f in final_selection]}")

        self.next_rebalance = self.Time + timedelta(days=self.rebalance_days)

        return [f.Symbol for f in final_selection]

    
    def OnSecuritiesChanged(self, changes):
        # Remove securities that were removed from our universe
        for security in changes.RemovedSecurities:
            if security.Symbol in self.activeStocks:
                self.activeStocks.remove(security.Symbol)
            else:
                self.log(f"Security {security.Symbol} not in active stocks")
            if security.Invested:
                self.Liquidate(security.Symbol)

        # can't open positions here since data might not be added correctly yet
        for x in changes.AddedSecurities:
            self.activeStocks.add(x.Symbol)  
             
        # adjust targets if universe has changed
        self.portfolioTargets = [PortfolioTarget(symbol, 1/len(self.activeStocks)) 
                            for symbol in self.activeStocks]
        
    def OnData(self, data):
        if self.portfolioTargets == []:
            return
        activeStocks_truncated = self.activeStocks.copy()
        for symbol in self.activeStocks:
            if self.counter <= 1:
                self.counter += 1
                if symbol not in data:
                    return
            else:
                if symbol not in data:
                    activeStocks_truncated.remove(symbol)

        # adjust portfolio targets again
        self.portfolioTargets = [PortfolioTarget(symbol, 1/len(activeStocks_truncated)) 
                            for symbol in activeStocks_truncated]       

        self.SetHoldings(self.portfolioTargets)
        self.Log(f"Rebalanced portfolio on {self.Time}")
        
        self.portfolioTargets = []
        self.counter = 0
