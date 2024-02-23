import os
import time
from datetime import datetime, timedelta
import requests
from pyupbit import WebSocketManager
import pyupbit


'''

'''


class AutoTrade():
    
    
    
    def __init__(self):
        ### basic setting
        self.except_coins = [] ## 혹시나 제외해야하는 ticker 있으면 추가.
        
        self.data_path = os.path.dirname(os.path.realpath(__file__)) 
        with open(f'{self.data_path}/key.txt','r') as f:    ## 절대경로로 바꾸기.        
            lines = [item.strip() for item in f.readlines()]
            self.access, self.secret = lines
        
        with open(f'{self.data_path}/webhook_url.txt','r') as f:    ## 절대경로로 바꾸기.        
            self.discord_webhook = [item.strip() for item in f.readlines()][0].strip()
        
        # self.discord_webhook= "https://discord.com/api/webhooks/1206416453302091847/SxN5qqf7PfWcnde2yD2eNZ-HJ4YJfVrtMYBhit_ikqb8gX4AHyLYOUinso6ab_u55KxS"
        
        self.upbit = pyupbit.Upbit(self.access, self.secret)
        self.buy_status= self.get_buy_status() ##  현재 매수상태 
        
        
        
        
        self.max_order_cnt = 3 ## 최대매수할 갯수.
        
        
        ##  최초 실행 그리고 매수매도마다 실행.
        
        self.remain_coin= self.get_remained_coin()
        
        self.order_able_cnt = self.max_order_cnt - len(self.remain_coin) # 주문 가능한 갯수.
        
        
        
        
        
        myToken = "xoxb-your-token"
        
    # def post_message(token, channel, text):
    #     """슬랙 메시지 전송"""
    #     response = requests.post("https://slack.com/api/chat.postMessage",
    #         headers={"Authorization": "Bearer "+token},
    #         data={"channel": channel,"text": text}
    #     )
    
    # discord send_message
    def send_message(self, text):
        now = datetime.now()
        message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(text)}"}
        requests.post(self.discord_webhook, data=message)
        print(message)
    
    
    # function
    
    def trading_status(self):
        self.remain_coin= self.get_remained_coin()
        self.order_able_cnt = self.max_order_cnt - len(self.remain_coin) # 주문 가능한 갯수.
        # self.매수중인코인리스트 
        # return 매수중인 코인ticker, 매수중인 ticker 개수.
        
    
    def get_new_balance(self):
        '''
        단순 except_coin 제외
        '''
        balances = self.upbit.get_balances() # 계좌정보
        self.balances = [item for item in balances if not f"{item['unit_currency']}-{item['currency']}" in self.except_coins] ## 종목 제외.
        return self.balances
    
    def get_buy_status(self):
        buy_status = False
        self.balances = self.get_new_balance()
        if len(self.get_remained_coin()):
            buy_status = True
        return buy_status
    
    def get_target_price(self, ticker, k):
        """변동성 돌파 전략으로 매수 목표가 조회"""
        df = pyupbit.get_ohlcv(ticker, interval="day", count=2)
        target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
        return target_price

    def get_start_time(self, ticker):
        """시작 시간 조회"""
        df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
        start_time = df.index[0]
        return start_time

    def get_ma15(self, ticker):
        """15일 이동 평균선 조회"""
        df = pyupbit.get_ohlcv(ticker, interval="day", count=15)
        ma15 = df['close'].rolling(15).mean().iloc[-1]
        return ma15

    def get_balance(self, ticker):
        """
        잔고 조회 매수가능 금액.
        """
        for b in self.balances:
            if b['currency'] == ticker:
                if b['balance'] is not None:
                    return float(b['balance'])
                else:
                    return 0
        return 0
    
    def get_remained_coin(self):
        '''
        매수중인 코인 리스트 반환
        '''
        ls = []
        # balance = self.get_new_balance()
        for b in self.balances:
            if b['currency'] != "KRW":
                if b['balance'] is not None:
                    ls.append(b)
        return ls
    
        
    
    def get_remained_balance(self):
        
        for b in self.balances:
            if b['currency'] == "KRW":
                if b['balance'] is not None:
                    return float(b['balance'])
                else:
                    return 0
        return 0
    
    def convert_min_to_day(self, df_min, start_hour= 9):
        '''
        pyupbit 에서 받은 분봉데이터 기준.
        '''
        df_min = df_min.reset_index(names='timestamp')
        df_min['timestamp']  = pd.to_datetime(df_min['timestamp'] )
        df_min['timestamp'] = df_min['timestamp'] - pd.Timedelta(hours = start_hour)
        # resample하여 일봉 데이터로 변환합니다.
        df_daily = df_min.resample('D', on='timestamp').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'value':'sum'})

        return df_daily
    
    ### 수익율 구하기. 
    def get_revenue_rate(self, ticker):
        '''
        수익율 구하기.
        
        currency: 코인의 이름(KRW는 원화)
        balance : 소유한 코인의 개수
        avg_buy_price : 평균 매입 단가
        unit_currency : 거래 화폐
        '''
        revenue_rate = 0.0
        for coin in  self.balances:
            # 티커 형태로 전환
            coin_ticker = coin['unit_currency'] + "-" + coin['currency']

            if ticker == coin_ticker:
                # 현재 시세
                now_price = pyupbit.get_current_price(coin_ticker)
                
                # 수익률 계산을 위한 형 변환
                try:
                    revenue_rate = (now_price - float(coin['avg_buy_price'])) / float(coin['avg_buy_price']) * 100.0
                except:
                    revenue_rate =0

        return round(revenue_rate,2)

    def get_my_revenue_rates(self):
        result_ls = []
        for item in self.balances:
            result_dict = {}
            ticker = f"{item['unit_currency']}-{item['currency']}"
            avg_buy_price = int(item['avg_buy_price'])
            if avg_buy_price !=0:
                result_dict['ticker'] = ticker
                revenue_rate = self.get_revenue_rate(ticker)
                result_dict['revenue_rate'] = revenue_rate
                result_ls.append(result_dict)
        return result_ls
            
    def is_변동성돌파_status_by_df(self, df, k = 0.5, option= "매수", interval = 'days'):
        '''
        dict [ status, target_price, close]
        days , minutes  구분. 
        '''
        
        df['vol20ma'] = df['volume'].rolling(20).mean()
        pre_open = df.iloc[-2]['open']
        pre_close = df.iloc[-2]['close']
        pre_high = df.iloc[-2]['high']
        pre_low = df.iloc[-2]['low']
        cur_open = df.iloc[-1]['open']
        cur_high = df.iloc[-1]['high']
        cur_close = df.iloc[-1]['close']
        # volume 오늘 거래량이 평균 20 거래량보다 큰게 몇개인지 확인하기. 오늘만.
        
        # k = 0.5
        
        result_dic = {}
        result = False

        # target_price 구하기.  매수는 대기, 매도 매도.
        if option =='매수':
            target_price = cur_open + ((pre_high - pre_low) * k)  ## 
            
            if cur_high>= target_price:
                result = True ## 매수대기.
                revenue_rate = ((cur_close / target_price)  - 1) * 100
                revenue_rate = round(revenue_rate,2)
            
        else: # 매도.
            # target_price = cur_open - ((pre_high - pre_low) * k)  ## 
            target_price = cur_open - (( max(pre_close, pre_open)  -  min(pre_close, pre_open) ) * k)  ##  매도는 보수적으로 몸통 기준으로 변동폭 설정.!!
            
            if cur_close <= target_price:
                result = True ##  매도
                revenue_rate = ((cur_close / target_price)  - 1) * 100
                revenue_rate = round(revenue_rate,2)
        # 현재 변동성돌파 상태 여부 확인. 
        revenue_rate = 0
        

        # print(f"target_price : {target_price}")
        # print("=============================================================")
        result_dic['status'] = result
        result_dic['target_price'] = target_price
        
        result_dic['volume'] = df.iloc[-1]['volume'] 
        result_dic['vol_ma_20'] = round(df.iloc[-1]['vol20ma'],2)
        result_dic['volume_rate_for_20'] = round(df.iloc[-1]['volume'] / df.iloc[-1]['vol20ma'] *100 ,1) 
        result_dic['revenue_rate'] = revenue_rate

        return result_dic
    
    ########################  종목 선정하기 ㅣ ############################
        
    def on_ma15(self, df, period = 15):
        '''
        ma 조건
        '''
        ## 최소 조건
        result = False
        ma15 = df['close'].rolling(period).mean().iloc[-1]
        close = df.iloc[-1]['close']
        if ma15 < close:
            result = True
        return result
    
    def on_volume(self, df, period=20):
        result = False
        vol20ma = df['volume'].rolling(period).mean()[-1]
        volume = df.iloc[-1]['volume']
        if vol20ma < volume:
            result = True
        return result
    
    def up_ma30(self, df):
        result = False
        df['ma30'] = df['close'].rolling(30).mean()
        cond3 = df['ma30'].iloc[-2] <= df['ma30'].iloc[-1]
        if cond3:
            result = True
        return result
    
    def up_bb(self, df):
        result = False
        df['ma360'] = df['close'].rolling(window=365).mean() # 365일 이동평균
        df['stddev'] = df['close'].rolling(window=365).std() # 20일 이동표준편차
        df['upper'] = df['ma360'] + 2*df['stddev'] # 상단밴드
        cond4 = df['close'].iloc[-1] > df['upper'][-2] 
        if cond4:
            result = True
        return result
    
    def find_status(self, test_mode =False):
        '''
        return (ticker :  target_price, current_revenue)
        '''
        result_ls = []
        tickers =  pyupbit.get_tickers('KRW')
        tickers = [item for item in tickers if not item in self.except_coins]
            
        for ticker in tickers:
            print(ticker, end=",")
            result_dict = {}
            try:
                df = pyupbit.get_ohlcv(ticker, interval="day", count=120)
                if not len(df):
                    print(ticker , '데이터가져오기 실패')
                    time.sleep(0.2)
                    continue
                self.today = df.index[-1]
                ticker_status = self.is_변동성돌파_status_by_df(df)
                
                # if ticker_status['status'] and self.on_ma15(df) and self.on_volume(df):
                if self.on_ma15(df) and (self.up_ma30 or self.up_bb(df)):
                    result_dict['ticker']= ticker
                    result_dict.update(ticker_status)
                    print(result_dict)
                    result_ls.append(result_dict)
                    if test_mode:
                        if len(result_ls):
                            break
                time.sleep(0.3)
                
            except Exception as e:
                print(ticker, e)
        
        if len(result_ls): ## 거래비율로 정렬.
            result_ls.sort(key = lambda x: x['volume_rate_for_20'], reverse=True)
        
        return result_ls

    def refresh_target_price(self, monitor_tickers, option ='매수'):
        '''
        1분되면 refresh. 매수되면 그종목만 taget_price 와 상태 변화.
        
        
        
        감시종목 target_price 생성하기.
        [{'ticker': 'KRW-EGLD',
        'status': False,
        'target_price': 77975.0,
        'volume': 1774.2154042,
        'volume_rate_for_20': 20.9,
        'revenue_rate': 0}, ... ] 
        
        '''
        ls = []
        for ticker in monitor_tickers:
            temp_dic = {}
            df_min  = pyupbit.get_ohlcv(ticker, interval="minutes60",count=50)
            if len(df_min):
                temp_dic['ticker'] = ticker
                dic = self.is_변동성돌파_status_by_df(df_min, option=option)
                temp_dic.update(dic)
                ls.append(temp_dic)
        ls.sort(key=lambda x: x['volume_rate_for_20'], reverse=True)
        return ls
    
    
    
    
######################################## 시장가 매수 매도. ==================================

    def buy(self, ticker):
        ## 시장가 매수
        ## 전체 잔여금 가져오기. 
        잔여금 = self.get_remained_balance()
        ## 잔여금만큼 매수하기. 
        매수금액 = 잔여금 * 0.9995
        
        try:
            self.upbit.buy_market_order(ticker,매수금액)
            self.get_buy_status()  ## 계좌정보 새로고침.
            매수후잔여금 = self.get_remained_balance()
            print('매수 성공!')
        except:
            print('매수 실패')
        # return ticker, 매수후잔여금, # 평균매수가, 총매수금
        
    
    def sell(self, ticker):
        '''
        ticker , 잔여금 , 수익율
        '''
        # currency , unit_currency = ticker.split("-")
        unit_currency , currency  = ticker.split("-")
        print(unit_currency , currency )
        try:
            my_balances =self.upbit.get_balances()
            my_balances = [item for item in my_balances if not f"{item['unit_currency']}-{item['currency']}" in self.except_coins] # except coins 제외
            
            for b in my_balances: # 계좌정보
                if b['currency'] == currency and b['unit_currency']==unit_currency:
                    balance = b['balance']
                    revenue_rate = self.get_revenue_rate(ticker)
                    self.upbit.sell_market_order(f"{unit_currency}-{currency}", float(balance))  ## 매도
                    
                    print(f"balance : {balance}, 수익율 : {revenue_rate}% ")
                    print(f"{unit_currency}-{currency} 매도 성공!")
                    self.get_buy_status()  ## 계좌정보 갱신
                    매도후잔여금 = self.get_remained_balance()
                    
        except Exception as e:
            print(f'매도 실패 {e}')
            self.send_message(f"매도실패 {e}")
            
        # return ticker,매도후잔여금, revenue_rate
        
        # 매도금액 잔여금 return 
     
      
        
        
        
        
        pass
    
if __name__ == "__main__":
    '''
    매수는 1.02 이하만 매수
    매도
    
    '''
    
    trader = AutoTrade()
    
    # ## test 용 
    # test_mode = True
    # if test_mode:
    #     trader.buy_status = False # 임시로 False 지정 
    
    while True:
        ## buy_status 가 True 면 매도 감시. 
        if trader.buy_status: ## 매수중인상태. 매도감시.....
            ## 변동성 하향돌파 이면 매도. - Buy status 새로고침.
            # 최초 매도 target_price 설정. 
            remained_coins = trader.get_remained_coin() ## [{'currency': 'BTC','balance': '0.00015178','locked': '0','avg_buy_price': '64301000','avg_buy_price_modified': False,'unit_currency': 'KRW'},...]
            monitor_tickers = [f"{item['unit_currency']}-{item['currency']}" for item in remained_coins]
            if not len(monitor_tickers):
                print('매도할 monitor_tickers 가 없습니다.')
                trader.buy_status = False
                continue
            sell_target_price_dict = trader.refresh_target_price(monitor_tickers, option='매도') # [{'ticker': 'KRW-EGLD','status': False,'target_price': 77975.0,'volume': 1774.2154042,'volume_rate_for_20': 20.9,'revenue_rate': 0},
            # 00시마다 매도 target_Price 설정
            
            print("===========================")
            print('sell monitoring start! !')
            print(monitor_tickers)
            print("===========================")
            wm = WebSocketManager("ticker", monitor_tickers)
            refresh = False
            while True:
                try:
                    data = wm.get()
                    
                    trade_timestamp =  data['trade_timestamp']
                    cur_time = datetime.fromtimestamp(int(trade_timestamp/ 1000))

                    if cur_time.minute ==1 and not refresh:
                        sell_target_price_dict = trader.refresh_target_price(monitor_tickers,  option='매도')
                        trader.send_message(f"every 1miniute target_price refresh sell !!")
                        refresh = True
                    if cur_time.minute ==3 :
                        refresh = False
                        
                    target_price = [item['target_price'] for item in sell_target_price_dict if item['ticker'] == data['code']][0]
                    
                    print(f"[{cur_time}] {data['code']} sell_target_price:{target_price:,.1f}, current_price:{data['trade_price']:,.1f}({data['trade_price']/target_price:,.3f}%) sell monitoring..  ") 
                    
                    if data['trade_price'] < target_price : 
                        수익률 = trader.get_revenue_rate(data['code'])
                        ticker = data['code']
                        
                        # 실제 매도. (매도매수시 계자정보 갱신됨.)
                        trader.sell(ticker)
                        
                        
                        txt = f"{data['code']} price: {data['trade_price']:,.1f} Sale complete!! revenue_rate {수익률:,.1f}%"
                        print("==============="*5)
                        print(txt)
                        print("==============="*5)
                        
                        # message
                        trader.send_message(txt)
                        
                        wm.terminate()
                        # terminate
                        print('terminate status', wm.is_alive())
                        # wait till proc dead
                        wm.join()
                        print('after join status' , wm.is_alive())
                        
                        print("==============="*5)
                        
                        trader.buy_status = True
                        break
                except Exception as e:
                    trader.send_message(f'오류발생1 {e} {data}')
                    
                # data = {'type': 'ticker', 'code': 'KRW-IMX', 'opening_price': 3329.0, 'high_price': 3721.0, 'low_price': 3324.0, 'trade_price': 3674.0, 'prev_closing_price': 3330.0, 'acc_trade_price': 33307997285.307644, 'change': 'RISE', 'change_price': 344.0, 'signed_change_price': 344.0, 'change_rate': 0.1033033033, 'signed_change_rate': 0.1033033033, 'ask_bid': 'ASK', 'trade_volume': 225.31642931, 'acc_trade_volume': 9267659.86053631, 'trade_date': '20240210', 'trade_time': '065849', 'trade_timestamp': 1707548329322, 'acc_ask_volume': 5065519.75400188, 'acc_bid_volume': 4202140.10653443, 'highest_52_week_price': 3721.0, 'highest_52_week_date': '2024-02-10', 'lowest_52_week_price': 655.0, 'lowest_52_week_date': '2023-09-13', 'market_state': 'ACTIVE', 'is_trading_suspended': False, 'delisting_date': None, 'market_warning': 'NONE', 'timestamp': 1707548329350, 'acc_trade_price_24h': 46258976476.02135, 'acc_trade_volume_24h': 13239564.09856163, 'stream_type': 'REALTIME'}
            
        
        else: ## 매수안된상태.  매수 감시 
            # 매수대기종목 5종목만 가져옴.
            
            my_coin_list = trader.find_status(test_mode=False)[:5]  # {'ticker': 'KRW-IMX', 'status': True, 'target_price': 3443.0, 'volume': 8850397.18760984,'volume_rate_for_20': 211.8,'revenue_rate': 0},
            
            # 추적코인이 없으면 30분후 다시 실행하고 있으면 빠져나오기. 
            if not len(my_coin_list):
                while True:
                    time.sleep(60 * 30)
                    my_coin_list = trader.find_status(test_mode=False)[:5]
                    if len(my_coin_list):
                        break
                    
            monitor_tickers = [item['ticker'] for item in my_coin_list]
            
            print("=========================================")
            print('Buy monitoring start!')
            print(monitor_tickers)
            print("=========================================")
            ## 00분마다 분봉 taget price 갱신하기. 
            
            target_price_dict = trader.refresh_target_price(monitor_tickers) ## [{'ticker': 'KRW-EGLD','status': False,'target_price': 77975.0,'volume': 1774.2154042,'volume_rate_for_20': 20.9,'revenue_rate': 0},
            
            wm = WebSocketManager("ticker", monitor_tickers)
            refresh = False
            
            while True:
                try:
                    data = wm.get()
                    trade_timestamp =  data['trade_timestamp']
                    cur_time = datetime.fromtimestamp(int(trade_timestamp/ 1000))
                    
                    if cur_time.minute ==1 and not refresh:
                        target_price_dict = trader.refresh_target_price(monitor_tickers) ## 딕셔너리 형태로 받아노는게 좋을듯.
                        trader.send_message(f"every 1miniute target_price refresh buy !!")
                        refresh = True
                    
                    if cur_time.minute ==2:
                        refresh = False
                    
                    target_prices = [item['target_price'] for item in target_price_dict if item['ticker'] == data['code']]
                    if len(target_prices):
                        target_price= target_prices[0]
                    else:
                        print('목표주가 정보 없음 ', data)
                        continue
                    
                    print(f"monitor_tickers: {monitor_tickers}")
                    price_for_target = data['trade_price'] / target_price  # 목표가대비현재가
                    
                    print(f"[{cur_time}] {data['code']} buy_target_price:{target_price:,.1f}, current_price:{data['trade_price']:,.1f}({price_for_target:,.3f}%) Buy monitoring.. ") 
                    if data['trade_price'] >= target_price and data['prev_closing_price'] < target_price : # and price_for_target < 1.01: 
                        ticker = data['code']
                        # 실제 매수
                        trader.buy(ticker)
                        
                        ## 계좌정보가져와서 정보 txt에 추가하기. 
                        
                        txt = f" {data['code']} price : {data['trade_price']:,.1f} Purchase completed"
                        print("**************"*5)
                        print(txt)
                        print("**************"*5)

                        # 메세지 알림. 매수내용.
                        trader.send_message(txt)
                        
                        wm.terminate()
                        # terminate
                        print('terminate status', wm.is_alive())
                        # wait till proc dead
                        wm.join()
                        print('after join status' , wm.is_alive())
                        
                        
                        
                        print("**************"*5)
                        remained_coins = trader.get_remained_coin() ## [{'currency': 'BTC','balance': '0.00015178','locked': '0','avg_buy_price': '64301000','avg_buy_price_modified': False,'unit_currency': 'KRW'},...]
                        monitor_tickers = [f"{item['unit_currency']}-{item['currency']}" for item in remained_coins]
                        if len(remained_coins):
                            trader.buy_status = True
                            break
                except Exception as e:
                    trader.send_message(f'오류발생2 {e} {data}')
                # data = {'type': 'ticker', 'code': 'KRW-IMX', 'opening_price': 3329.0, 'high_price': 3721.0, 'low_price': 3324.0, 'trade_price': 3674.0, 'prev_closing_price': 3330.0, 'acc_trade_price': 33307997285.307644, 'change': 'RISE', 'change_price': 344.0, 'signed_change_price': 344.0, 'change_rate': 0.1033033033, 'signed_change_rate': 0.1033033033, 'ask_bid': 'ASK', 'trade_volume': 225.31642931, 'acc_trade_volume': 9267659.86053631, 'trade_date': '20240210', 'trade_time': '065849', 'trade_timestamp': 1707548329322, 'acc_ask_volume': 5065519.75400188, 'acc_bid_volume': 4202140.10653443, 'highest_52_week_price': 3721.0, 'highest_52_week_date': '2024-02-10', 'lowest_52_week_price': 655.0, 'lowest_52_week_date': '2023-09-13', 'market_state': 'ACTIVE', 'is_trading_suspended': False, 'delisting_date': None, 'market_warning': 'NONE', 'timestamp': 1707548329350, 'acc_trade_price_24h': 46258976476.02135, 'acc_trade_volume_24h': 13239564.09856163, 'stream_type': 'REALTIME'}
                
                
  
        