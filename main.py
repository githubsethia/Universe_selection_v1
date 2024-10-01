
# region imports
from AlgorithmImports import *
from datetime import timedelta
import numpy as np
from inputs import CONFIG

# endregion

#learning1 - lower Market cap provides better returns

class Universeselectionv1(QCAlgorithm):

    def Initialize(self):
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        start_date = CONFIG["algorithm"]["start_date"]
        self.SetStartDate(start_date["year"], start_date["month"], start_date["day"])  # Set start date

        end_date = CONFIG["algorithm"]["end_date"]
        self.SetEndDate(end_date["year"], end_date["month"], end_date["day"])  # Set end date

        self.SetCash(CONFIG["algorithm"]["cash"])  # Set strategy cash

        # Universe config
        self.market_cap_filter = CONFIG["universe"]["market_cap_filter"]
        self.volume_filter = CONFIG["universe"]["volume_filter"]
        self.turnover_filter = CONFIG["universe"]["turnover_filter"]
        self.min_price = CONFIG["universe"]["min_price"]
        self.revenue_growth_year = CONFIG["universe"]["revenue_growth_year"]
        self.revenue_growth_quarter = CONFIG["universe"]["revenue_growth_quarter"]
        self.pe_ratio_min = CONFIG["universe"]["pe_ratio_min"]
        self.pe_ratio_max = CONFIG["universe"]["pe_ratio_max"]
        self.year_low_threshold = CONFIG["universe"]["year_low_threshold"]
        self.num_stocks = CONFIG["universe"]["num_stocks"]
        self.max_debt_to_equity = CONFIG["universe"]["max_debt_to_equity"]
        self.universe_history_bars = CONFIG["universe"]["universe_history_bars"]
        self.universe_history_resolution = CONFIG["universe"]["universe_history_resolution"]
        self.market_cap_descending = CONFIG["universe"]["market_cap_descending"]

        # Rebalance config
        self.rebalance_days = CONFIG["rebalance"]["rebalance_days"]
        self.next_rebalance = self.StartDate
        self.portfolioTargets = []
        self.activeStocks = set()  # To store our selected universe
        self.counter = 0

        # Logging flags
        self.coarse_logs = False
        self.fine_logs = False

    def CoarseSelectionFunction(self, coarse):
        if self.Time < self.next_rebalance:
            return Universe.Unchanged

        coarse_list = list(coarse)
        if len(coarse_list) == 0:
            return Universe.Unchanged

        if self.coarse_logs: self.Log(f"Initial universe size: {len(coarse_list)}")

        coarse = [c for c in coarse if c.MarketCap > self.market_cap_filter]
        if self.coarse_logs: self.Log(f"After market cap filter: {len(coarse)}")

        high_volume = [c for c in coarse if c.DollarVolume > self.volume_filter]
        if self.coarse_logs: self.Log(f"After high volume filter: {len(high_volume)}")

        high_turnover = [c for c in high_volume if c.DollarVolume / c.MarketCap > self.turnover_filter]
        if self.coarse_logs: self.Log(f"After high turnover filter: {len(high_turnover)}")

        price_filter = [c for c in high_turnover if c.Price > self.min_price]
        if self.coarse_logs: self.Log(f"After price filter: {len(price_filter)}")

        has_fundamental = [c for c in price_filter if c.has_fundamental_data]
        if self.coarse_logs: self.Log(f"After has fundamental data filter: {len(has_fundamental)}")

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
        if self.fine_logs: self.Log(f"After revenue growth filter: {len(high_growth)}")

        # Check if PERatio is available before filtering
        pe_filter = [f for f in high_growth if f.ValuationRatios.PERatio is not None and
                    self.pe_ratio_min < f.ValuationRatios.PERatio < self.pe_ratio_max]
        if self.fine_logs: self.Log(f"After P/E ratio filter: {len(pe_filter)}")

        # check for low debt to equity ratio
        low_debt_equity = [f for f in pe_filter if f.OperationRatios.TotalDebtEquityRatio.has_value
                           and f.OperationRatios.TotalDebtEquityRatio.value < self.max_debt_to_equity]

        # Use try-except for history to handle any potential issues
        try:
            history = self.History([f.Symbol for f in low_debt_equity], self.universe_history_bars, self.universe_history_resolution)
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
            
            if self.fine_logs: self.Log(f"After SMA filter: {len(sma_filter)}")
            if self.fine_logs: self.Log(f"After 52-week low filter: {len(year_low_filter)}")

        except Exception as e:
            self.Log(f"An error occurred: {str(e)}")

        # rank based on highest market cap
        ranked_stocks = sorted(year_low_filter, key=lambda x: x.MarketCap,reverse=self.market_cap_descending)

        final_selection = ranked_stocks[:self.num_stocks]
        # if self.fine_logs: 
        self.Log(f"Final selection: {len(final_selection)}")
        # if self.fine_logs: 
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

