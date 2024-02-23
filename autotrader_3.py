import json
import os
import sys
import time
from datetime import datetime, timedelta
import requests
import numpy as np
import pandas as pd
from pyupbit import WebSocketManager
import pyupbit
import cufflinks as cf

import warnings
warnings.filterwarnings('ignore')


class My_discord:
    
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        
    # discord send_message
    def send_message(self, text):
        # now = datetime.now()
        # message = {"content": f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] {str(text)}"}
        message = str(text)
        resp = requests.post(self.webhook_url, data=message)
        return resp
        

class AutoTrade():
    
    def __init__(self, except_coins = [], test_mode=False):
        ### basic setting
        ## 최초 설정
        self.test_mode= test_mode
        self.max_order_cnt = 3 ## 최대매수할 갯수.
        self.except_coins = except_coins ## 혹시나 제외해야하는 ticker 있으면 추가.
        self.data_path = os.path.dirname(os.path.realpath(__file__)) 
       
        with open(".config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        self.__access = config['upbit_access']
        self.__secret = config['upbit_secret']
        self.__discord_webhook = config['discord_webhook_url']
        
        ## 인스턴스 생성
        self.upbit = pyupbit.Upbit(self.__access, self.__secret)
        self.my_discord = My_discord(self.__discord_webhook)


        ## 초기작업
        self.find_new_coins()  ## self.비보유감시종목 설정
        self.get_my_balances() ## self.보유종목 . self.buy_able_cnt(주문가능한 코인종목개수)   ,  self.able_buy_balance_for_one_coin(개당 매수가능핳 매수금(수수료포함))   설정

        
        ## start_send_message
        text = "== auto trading start! =="
        self.my_discord.send_message(text)
    
    
    
    # function
    
    def get_ohlcv(self, ticker, interval, count=200):
        '''
        interval : day, minutes60 , minutes5
        모든 데이터 가져오기는 이함수로 대체하고. 
        columns.name 활용. 
        ticker, type = columns.name.split("_")
        '''
        df = pyupbit.get_ohlcv(ticker=ticker, interval=interval, count=count )
        ## df 에 따라 dict key 지정. df_d, df_min60, df_min5 .. 
        if "minutes" in interval:
            split_t = interval.split("minutes")
            df_key_word= f"min{split_t[-1]}"
        elif "days" in interval:
            df_key_word= "day"
        elif "week" in interval:
            df_key_word= "week"
        elif "month" in interval:
            df_key_word= "month"
        else:
            df_key_word = 'df'
        name = f"{ticker}_{df_key_word}"
        df.columns.name = name
        return df
    
    def get_my_balances(self):
        
        new_balances = self.upbit.get_balances() # 계좌정보
        self.new_balances = [item for item in new_balances if not f"{item['unit_currency']}-{item['currency']}" in self.except_coins] ## 종목 제외.
        
        ls = []
        for b in self.new_balances:
            if b['currency'] != "KRW":
                if b['balance'] is not None:
                    ls.append(b)
            else:
                if b['balance'] is not None:
                    self.현재매수가능총액 = float(b['balance'])
                else:
                    self.현재매수가능총액 = 0
                    
        
        
        cur_my_coin_dict = {}
        if len(ls):
            # cur_my_coin_dict[ticker]['trade_status'] = "비매수"
            # cur_my_coin_dict['vol_ma_20'] = item['vol_ma_20']
            # cur_my_coin_dict[ticker]['target_price'] = item['target_price']
            # cur_my_coin_dict[ticker]['volume'] = item['volume']
            for item in ls:
                ticker = f"{item['unit_currency']}-{item['currency']}"
                
                cur_my_coin_dict[ticker] = {}
                cur_my_coin_dict[ticker]['balance'] = float(item['balance'])
                
                # df = pyupbit.get_ohlcv(ticker, interval="day", count=120)
                df = self.get_ohlcv(ticker, interval="day")
                now = datetime.now()
                
                # 데이터 받아오는것
                cur_my_coin_dict[ticker]['df_d'] = df
                time.sleep(0.5)
                # df_min = pyupbit.get_ohlcv(ticker, interval="minutes60", count=200)
                
                df_min = self.get_ohlcv(ticker, interval="minutes60")
                cur_my_coin_dict[ticker]['df_min60'] = df_min

                
                cur_my_coin_dict[ticker]['avg_buy_price'] = float(item['avg_buy_price'])
                
                cur_my_coin_dict[ticker]['trade_status'] = "보유"
                
                cur_my_coin_dict[ticker]['vol_ma_20'] = 0
                cur_my_coin_dict[ticker]['target_price'] = 0
                cur_my_coin_dict[ticker]['volume'] = 0
                
                cur_my_coin_dict[ticker]['high_price'] = None  ## 최초는 현재가.
                cur_my_coin_dict[ticker]['high_price_time'] = None ## 최고가 갱신때마다 값 넣어줌.
                cur_my_coin_dict[ticker]['update_time'] = now ## 최고가 갱신때마다 값 넣어줌.
        else:
            pass
        
        
        ## 새로 매수 가능한 종목수와 종목당 매수가능금액 설정.
        self.buy_able_cnt = self.max_order_cnt - len(cur_my_coin_dict)
        
        if self.buy_able_cnt !=0:
            self.able_buy_balance_for_one_coin =  (self.현재매수가능총액  / self.buy_able_cnt) * 0.9995
            minimum_order_amount = 5050
            if self.able_buy_balance_for_one_coin < minimum_order_amount:
                while self.able_buy_balance_for_one_coin <= minimum_order_amount: 
                    if self.buy_able_cnt <= 0:
                        self.able_buy_balance_for_one_coin =0
                        self.buy_able_cnt = 0
                        break
                    self.able_buy_balance_for_one_coin =  (self.현재매수가능총액  / self.buy_able_cnt) * 0.9995
                    self.buy_able_cnt = self.buy_able_cnt -1
        else:
            self.able_buy_balance_for_one_coin = 0
        
        ## refresh_target_price 하기.(최초)
        cur_my_coin_dict = self.refresh_target_price(cur_my_coin_dict)
        
        self.보유종목 = cur_my_coin_dict 
        
        text = "== 보유종목! \n"
        text = text + f"{self.보유종목}"
        print(f"print5 {text}")
        
        self.my_discord.send_message(text)
        
        return cur_my_coin_dict
        
        
        
        ## 매수대기종목 찾아서 위와같은형태의 딕셔너리 생성후. 그 아래 refresh 함수 정의해야함.
          

    def refresh_target_price(self,  temp_dic, intervals='minutes60'):                 ### refresh 할때도 df refresh 되어야함.!! 최소 분봉.
        '''
        보유는 변경되고 비보유는 특정 기간 마다 변경.
        1분되면 refresh. 매수되면 그종목만 taget_price 와 상태 변화.
        
        
        {'KRW-T': {'balance': 0,
        'avg_buy_price': 0,
        'trade_status': '비보유',
        'vol_ma_20': 287726876.18,
        'target_price': 36.945,
        'volume': 1447609531.2855675,
        'high_price': None,
        'high_price_time': None,
        'update_time': datetime.datetime(2024, 2, 14, 21, 17, 33, 135796)},
        
        
        {'KRW-AQT': {'balance': 12.48793221,
        'avg_buy_price': 1848.65466644,
        'trade_status': '보유',
        'vol_ma_20': 0,  ##
        'target_price': 0, ##
        'volume': 0, ##
        'high_price': None,##
        'high_price_time': None,
        'update_time': datetime.datetime(2024, 2, 14, 21, 17, 33, 262316)}}

        '''    
        now = datetime.now()
        new_temp_dict = {}
        for ticker, item in temp_dic.items():
            ## df 에 따라 dict key 지정. df_d, df_min60, df_min5 .. 
            if "minutes" in intervals:
                split_t = intervals.split("minutes")
                df_key_word= f"df_min{split_t[-1]}"
            elif "days" in intervals:
                df_key_word= "df_d"
            else:
                df_key_word = 'df'
                
            # df  = pyupbit.get_ohlcv(ticker, interval=intervals, count=200)
            df  = self.get_ohlcv(ticker, interval=intervals, count=200)
            
            new_temp_dict[ticker] = {}
            if len(df):
                if item['trade_status'] == '보유':
                    dic = self.is_변동성돌파_status_by_df(df,  option='보유')
                elif item['trade_status'] == '미보유':
                    dic = self.is_변동성돌파_status_by_df(df,  option='미보유')
                else:
                    pass
                '''
                is_변동성돌파_status_by_df 함수 결과 
                
                {'status': True,
                'target_price': 68258000.0,
                'volume': 4161.03323057,
                'vol_ma_20': 3738.113882685501,
                'volume_rate_for_20': 111.3,
                'revenue_rate': 0}
                '''
                
                new_dict = dict(item, **dic)
                new_dict[df_key_word] = df   ## df update
                new_dict["update_time"] = now
                
                new_temp_dict[ticker] = new_dict
                
        return new_temp_dict
    
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
        for ticker_key, info_dic in  self.보유종목.items():
            # 티커 형태로 전환
            # coin_ticker = coin['unit_currency'] + "-" + coin['currency']

            if ticker == ticker_key:
                # 현재 시세
                now_price = pyupbit.get_current_price(ticker_key)
                # 수익률 계산을 위한 형 변환
                try:
                    revenue_rate = (now_price - float(info_dic['avg_buy_price'])) / float(info_dic['avg_buy_price']) * 100.0
                except:
                    revenue_rate =0

        return round(revenue_rate,2)


    def get_my_revenue_rates(self):
        '''
        전체종목 수익율
        '''
        result_ls = []
        for ticker, info_dic in self.보유종목.items():
            result_dict = {}
            # ticker = f"{item['unit_currency']}-{item['currency']}"
            avg_buy_price = int(info_dic['avg_buy_price'])
            if avg_buy_price !=0:
                result_dict['ticker'] = ticker
                revenue_rate = self.get_revenue_rate(ticker)
                result_dict['revenue_rate'] = revenue_rate
                result_ls.append(result_dict)
        return result_ls
                        
    def is_변동성돌파_status_by_df(self, df, k = 0.5, option= "미보유"):
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
        if option =='미보유':
            target_price = cur_open + ((pre_high - pre_low) * k)  ## 
            
            if cur_high>= target_price:
                result = True ## 매수대기.
                revenue_rate = ((cur_close / target_price)  - 1) * 100
                revenue_rate = round(revenue_rate,2)
            
        else: # 보유
            target_price = cur_open - ((pre_high - pre_low) * k)  ## 
            # target_price = cur_open - (( max(pre_close, pre_open)  -  min(pre_close, pre_open) ) * k)  ##  매도는 보수적으로 몸통 기준으로 변동폭 설정.!!
            
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
    
    
    def cnt_better_volume(self, df, period=30, rate=1.5, checking_period=5, cnt=2): ## 현재 큰건지는 실시간으로 체킹하고 이건 그냥 최근 몇봉간 평균거래량보다 큰거래량이 몇개인지 확인하기.
        '''
        period 기간평균거래량보다 큰거래량이  checking_period 기간내 몇개?
        period 평균거래량
        rate : 평균거래량대비 rate 배거래량
        checking_period : 최근 n봉만 체크하기 (위 조건 만족)
        cnt : 최소 만족해야하는 갯수. 이 이상만 True 반환
        '''
        result = False
        vol20ma = df['volume'].rolling(period).mean()
        temp_s  = df['volume'] >= vol20ma * rate
        result = sum(temp_s.iloc[-checking_period:]) >= cnt
        
        
        return result
    
    
    def up_ma30(self, df):
        '''
        30일선 우상향인지.
        '''
        result = False
        df['ma30'] = df['close'].rolling(30).mean()
        cond = df['ma30'].iloc[-2] <= df['ma30'].iloc[-1]
        if cond:
            result = True
        return result
    
    
    def up_bb(self, df, bb_period = None):
        '''
        new_phase?
        '''
        
        if bb_period == None:
            cnt = len(df)
            arr = np.array([15, 30, 90, 180, 360])
            try:
                bb_period = arr[arr <= cnt][-1]
            except:
                print(f'캔들 15개 이하')
                return False
            
        result = False
        df[f'ma{bb_period}'] = df['close'].rolling(window=bb_period).mean() # 365일 이동평균
        df['stddev'] = df['close'].rolling(window=bb_period).std() # 20일 이동표준편차
        df[f'upper{bb_period}'] = df[f'ma{bb_period}'] + 2*df['stddev'] # 상단밴드
        cond = df['close'].iloc[-1] > df[f'upper{bb_period}'][-2] 
        if cond:
            result = True
        return result
    
    
        
    ######################### anal tech ##############################################
    
    
    def is_w(self, df, ma=5, option="w"):
        '''
        option w: 완성 n:대기
        result, return df
        ex) '5ma', '5ma_p' columns 추가됨.
        '''
        result = False
        str_ma = f"ma{ma}"
        # df = my_checking_dict['KRW-XRP']['df_d']
        ma_s = df['close'].rolling(ma).mean()
        df[str_ma] = ma_s
        ma_s1 = ma_s.drop_duplicates(keep='first')
        df[str_ma] = ma_s1
        low_p = (ma_s1.shift(1) > ma_s1) & (ma_s1 < ma_s1.shift(-1)) 
        high_p = (ma_s1.shift(1) < ma_s1) & (ma_s1 > ma_s1.shift(-1))
        low_p.loc[low_p ==True] = 'low'
        high_p.loc[high_p ==True] = 'high'
        inflection_p = pd.concat([low_p.loc[low_p =="low"] ,high_p.loc[high_p =="high"] ])
        df[f'{str_ma}_p'] = inflection_p


        ## w 조건
        lowhigh_df = df.loc[df[f'{str_ma}_p'].notnull()]  ## low high 만 있는 데이터.
        try:
            if option =='w':
                cond1 = lowhigh_df.iloc[-1][f'{str_ma}_p'] == 'low'
                cond2 = lowhigh_df.iloc[-1][str_ma] >= lowhigh_df.iloc[-3][str_ma]
            
            elif option =='n':
                cond1 = lowhigh_df.iloc[-1][f'{str_ma}_p'] == 'high'
                cond2 = df.iloc[-1][str_ma] > lowhigh_df.iloc[-2][str_ma]  # 현재이평이 전저점보다 높은상태.
        
            if cond1 & cond2:
                result  = True    
        except:
            # print(f'lowhigh_df cnt : {len(lowhigh_df)}, df cnt : {len(df)}')
            pass
        
        
        return result, df
    
    
    

    ## find coins
    def find_status(self):
        '''
        return (ticker :  target_price, current_revenue)
        '''
        result_ls = []
        tickers =  pyupbit.get_tickers('KRW')
        tickers = [item for item in tickers if not item in self.except_coins]
        
        if self.test_mode:
            tickers= tickers[:5] ## test mode    
        
        print(f'tickers cnt : {len(tickers)}')
        
        for ticker in tickers:
            print(ticker, end=",")
            result_dict = {}
            try:
                # df = pyupbit.get_ohlcv(ticker, interval="day", count=120)
                df = self.get_ohlcv(ticker, interval="day")
                if not len(df):
                    print(ticker , '데이터가져오기 실패')
                    time.sleep(0.2)
                    continue
                self.today = df.index[-1]
                
                cond1 = self.is_w(df) # 일봉 w
                
                # if ticker_status['status'] and self.on_ma15(df) and self.on_volume(df):
                
                cond_w5, df = self.is_w(df, 5, option='w')
                cond_w30, df = self.is_w(df, 30, option = 'w')
                cond_n30, df = self.is_w(df, 30, option = 'n')
                cond_new_phase = self.up_bb(df)
                cond_v = self.cnt_better_volume(df,period=30, rate=1.5,  checking_period=7, cnt=1)  ## 예민함. 한번더 체크.
                if (cond_new_phase | cond_w5) & (cond_w30 | (cond_n30 & cond_w5)) & cond_v :
                    df_min = self.get_ohlcv(ticker, interval="minutes60", count=200)
                    ticker_status = self.is_변동성돌파_status_by_df(df_min)
                    result_dict['ticker']= ticker
                    result_dict.update(ticker_status)
                    
                    ## 데이터 받아오는것.
                    result_dict['df_d'] = df
                    result_dict['df_min60'] = df_min
                    
                    
                    result_ls.append(result_dict)
                    if self.test_mode:
                        if len(result_ls):
                            break
                time.sleep(0.3)
                
            except Exception as e:
                print(ticker, e)
        
        if len(result_ls): ## 거래비율로 정렬.
            result_ls.sort(key = lambda x: x['volume_rate_for_20'], reverse=True)
        
        return result_ls

    
    def find_new_coins(self, check_cnt = 10):
        '''
        check_cnt : 감시할 종목 수 지정. (현재는 거래량순이 됨.)
        
        아래와 같은 형태로 작성해야함. 
        find_status 결과를 아래형태로 변경함.(거래량 순으로 소팅된 데이터..)
        
        
        my_checking_dict 내용
        cur_my_coin_dict[ticker]['balance'] = float(item['balance'])
        cur_my_coin_dict[ticker]['avg_buy_price'] = float(item['avg_buy_price'])
        
        cur_my_coin_dict[ticker]['status'] = "비보유"
        cur_my_coin_dict[ticker]['high_price'] = None  ## 최초는 현재가.
        cur_my_coin_dict[ticker]['high_price_time'] = None ## 최고가 갱신때마다 값 넣어줌.
        '''
        result_ls = self.find_status()  ## 여기에 검색조건 들어가있음.
        
        # 단순 형변환.
        now = datetime.now()
        
        cur_my_coin_dict = {}
        for item in result_ls[:check_cnt]:
            ticker = item['ticker']
            cur_my_coin_dict[ticker] = {}
            
            cur_my_coin_dict[ticker]['balance'] = 0
            
            ## df_ 인것 모두 이전하기 df_min5 min30 min60 이 모두 존재하면 다 가져오기.
            for key , _ in item.items():
                if 'df_' in key:
                    cur_my_coin_dict[ticker][key] = item[key]
            
            
            cur_my_coin_dict[ticker]['avg_buy_price'] = 0
            cur_my_coin_dict[ticker]['trade_status'] = "비보유"
            cur_my_coin_dict[ticker]['vol_ma_20'] = item['vol_ma_20']
            cur_my_coin_dict[ticker]['target_price'] = item['target_price']
            cur_my_coin_dict[ticker]['volume'] = item['volume']
            cur_my_coin_dict[ticker]['high_price'] = None  ## 최초는 현재가.
            cur_my_coin_dict[ticker]['high_price_time'] = None ## 최고가 갱신때마다 값 넣어줌
            cur_my_coin_dict[ticker]['update_time'] = now ## 최고가 갱신때마다 값 넣어줌
            
        self.비보유감시종목 = cur_my_coin_dict
        print("===================================================")
        text = "= 비보유 감시종목 =  \n"
        text = text + f"{list(self.비보유감시종목.keys())}"
        print(text)
        
        self.my_discord.send_message(text)
        
        return cur_my_coin_dict
            
    
    
        ## real_time func ################################
    def real_data_add_df(self, data, df):
        '''
        최초 ohlcv 데이터 받아놓고 실시간데이터와 넣어주면 업데이트한 df 반환.
        전체데이터 감지하는시간 감안해서 최소 5분봉이상만 사용
        '''
        # 1. data 간격. 
        diff = df.index[1] - df.index[0]
        # 현재시간. 에 따라 데이터 처리방법.
        
        ts = data['trade_timestamp'] 
        dt = datetime.fromtimestamp( ts / 1000 ) # data 가져온시간
        cur_diff_time = dt - df.index[-1] 
        
        # data
        # 데이터 처리. '
        open = data['opening_price']
        high = data['high_price']
        low = data['low_price']
        close = data['trade_price']
        acc_volume = data['acc_trade_volume']  # 순간거래량.
        acc_value = data['acc_trade_price']  # 순간거래대금 .
        
        df= df.copy()
        
        if cur_diff_time < diff:
            # print('last data update')
            df.iloc[-1]["open"] = open
            df.iloc[-1]["high"] = high
            df.iloc[-1]["low"] = low
            df.iloc[-1]["close"] = close
            vol = df.iloc[-1]["volume"] + acc_volume
            df.iloc[-1]["volume"] = vol
            value = df.iloc[-1]["value"] + acc_value
            df.iloc[-1]["value"] =  value
            
        elif cur_diff_time >=diff:
            # print('last data add')
            idx = df.index[-1] + diff
            df.loc[idx, "open"] = open
            df.loc[idx, "high"] = high
            df.loc[idx, "low"] = low
            df.loc[idx, "close"] = close
            df.loc[idx, "volume"] = acc_volume
            df.loc[idx, "value"] = acc_value
            
        return df
    
    
    def iplot(self, df, title=None, mas=[], bb_period=None, cnt = None):
        '''
        
        '''
        if title == None:
            title = df.columns.name
        qf = cf.QuantFig(df, title=title, legend='top',name='name',up_color='red',down_color='blue')
        
        # ma
        for ma in mas:
            qf.add_sma(ma)
        
        # bb
        if bb_period == None:
            arr = np.array([10, 20, 60,120,240,365])
            bb_period = list(arr[arr < len(df)])[-1]
            
        qf.add_bollinger_bands(periods=int(bb_period), boll_std=2,colors=['grey','skyblue'],fill=True)
        
        qf.add_rsi(periods=9, name='RSI')
        qf.add_volume()
        # qf.add_trendline(str(df_min.index[-20]),str(df_min.index[-1]), )
        f = qf.iplot()
        return f  
        
        
        
        ######################################## 시장가 매수 매도. ==================================

    def buy(self, ticker):
        ## 시장가 매수
        result - False
        잔여금 = 0
        try:
            매수금액 = self.able_buy_balance_for_one_coin
            self.upbit.buy_market_order(ticker, 매수금액)
            time.sleep(1)
            self.get_my_balances()  ## able_cnt able_buy_balance 등등 설정까지완료.
            print('매수 성공!')
            result = True
        except:
            print('매수 실패')
        
        msg = f"[매수] 종목: {ticker}, 매수금액 : {매수금액:,.1f}"
        return msg
        
    
    def sell(self, ticker):
        '''
        ticker , 잔여금 , 수익율
        '''
        # currency , unit_currency = ticker.split("-")
        result = False
        try:
            info_dic = self.보유종목.get(ticker)
            if len(info_dic):
                balance = info_dic.get('balance')
                revenue_rate = self.get_revenue_rate(ticker)
                self.upbit.sell_market_order(ticker, float(balance))  ## 매도
                        
                time.sleep(1)
                self.get_my_balances()  ## able_cnt able_buy_balance 등등 설정까지완료.
                result = True
                
        except Exception as e:
            print(f'매도 실패 {e}')
            self.my_discord.send_message(f"매도실패 {e}")
        
        msg = f"[매도] 종목: {ticker}, 매도금액 : {float(balance):,.1f}({revenue_rate}%)"
        
        return msg

    
if __name__ == "__main__":
    
    # start 시 start 알림 메세지 보내기.
    # trader = AutoTrade(test_mode=True)
    trader = AutoTrade()
    now = datetime.now()
    
    ###############   시작시간이 refresh, reset 시간이면 mode = False
    # n분 마다 target_price 변동
    # 하루마다 추적종목 갱신.
    refresh_mode = True
    reset_mode = True
    
    if 1 < now.minute < 5:
        refresh_mode = False 
        if now.hour == 9:
            reset_mode == False 
    
    my_checking_dict = dict(trader.비보유감시종목, **trader.보유종목) # 감시종목리스트
    
    text = f"감시종목 : {','.join(my_checking_dict.keys())}"
    trader.my_discord.send_message(text)
    
    wm = WebSocketManager("ticker", list(my_checking_dict.keys()))
    
    while True:
        try:
            data = wm.get()
            ## data 값 내용
            # data = {'type': 'ticker', 'code': 'KRW-IMX', 
            # 'opening_price': 3329.0, 'high_price': 3721.0, 'low_price': 3324.0, 'trade_price': 3674.0, 
            # 'prev_closing_price': 3330.0,  #전봉 종가.
            # 'acc_trade_price': 33307997285.307644, 
            # 'change': 'RISE', 'change_price': 344.0, 'signed_change_price': 344.0, 
            # 'change_rate': 0.1033033033, 'signed_change_rate': 0.1033033033, 
            # 'ask_bid': 'ASK', 'trade_volume': 225.31642931, 'acc_trade_volume': 9267659.86053631, 
            # 'trade_date': '20240210', 'trade_time': '065849', 
            # 'trade_timestamp': 1707548329322, 'acc_ask_volume': 5065519.75400188, 'acc_bid_volume': 4202140.10653443, 
            # 'highest_52_week_price': 3721.0, 'highest_52_week_date': '2024-02-10', 'lowest_52_week_price': 655.0, 'lowest_52_week_date': '2023-09-13', 
            # 'market_state': 'ACTIVE', 'is_trading_suspended': False, 'delisting_date': None, 'market_warning': 'NONE', 
            # 'timestamp': 1707548329350, 'acc_trade_price_24h': 46258976476.02135, 'acc_trade_volume_24h': 13239564.09856163, 
            # 'stream_type': 'REALTIME'}
            if len(data):
                
                # txt = f"{data.get("code")} : {data.get("trade_price")} ({data.get('change_rate'):.2f}%)"
                print(data.get("code"), "",  data.get("trade_price"), "",  data.get('change_rate'), "")
                
                
                
                now =  datetime.fromtimestamp(int(data['timestamp'] / 1000))
                '''
                checking_dict 내용 ==========
                {'KRW-XRP': {'balance': 27.45744096,
                'avg_buy_price': 728.4,
                'trade_status': '보유',
                'vol_ma_20': 16536034.07,
                'target_price': 752.3000000000001,
                'volume': 10770405.58272314,
                'high_price': None,
                'high_price_time': None,
                'update_time': datetime.datetime(2024, 2, 15, 22, 50, 38, 60235)}}
                '''
                # data 종목 정보 가져오기
                checking_dict = my_checking_dict.get(data['code'])
                if checking_dict != None:
                    # checking데이터 업데이트 : 거래량, 현재가, 최고가 최고가일때 시간. target_price 비교, 
                    checking_dict['volume'] = data['trade_volume']
                    checking_dict['high_price'] = data['high_price']
                    checking_dict['cur_price'] = data['trade_price']
                    checking_dict['update_time'] = datetime.fromtimestamp( int(data['timestamp'] / 1000) )  # datetime.fromtimestamp(int(trade_timestamp/ 1000))
                    
                    
                    ## checking_dict['df_'] update
                    for key , df in checking_dict.items():
                        if 'df_' in key :
                            temp_df  = trader.real_data_add_df(data, df)
                            checking_dict[key] = temp_df
                    
                    
                    ## df 로 단기이평 판단하고 매도 하기.
                    
                    
                    if checking_dict['trade_status']== '미보유':
                        
                        # 현재가가 전봉 종가보다 크고. target_price 보다 크면. 매수.
                        target_buy_cond = checking_dict['target_price'] <= checking_dict['cur_price']
                        if target_buy_cond:
                            print('매수')
                            msg = trader.buy(ticker=data['code'])
                            trader.my_discord.send_message(msg)
                            my_checking_dict = dict(trader.비보유감시종목, **trader.보유종목)
                    
                    elif checking_dict['trade_status']== '보유':
                        
                        target_sell_cond = checking_dict['target_price'] <= checking_dict['cur_price']
                        # 매도하기 ( 봉의 종가 기준(봉시간의 3/4 이후에만 적용). , 또는 급락(정의필요)
                            
                            ## 보유종목종 여기서 최고가에서 현재가까지 떨어지는 시간체크해서 급락이면 매도.
                            
                            ## 보유종목중 여기서 거래빈도가 극심하게 낮으면 매도.??? 어떻게 처리.?
                        if target_sell_cond:
                            print('매도')
                            msg = trader.sell(ticker=data['code'],)
                            trader.my_discord.send_message(msg)
                            my_checking_dict = dict(trader.비보유감시종목, **trader.보유종목)
                            
                            text = f"감시종목 : {','.join(my_checking_dict.keys())}"
                            trader.my_discord.send_message(text)
                    else:
                        continue
                        
                    # checking종목의 trade_stauts 에따라 처리
                            ## 보유이면 target_price 보유로 처리.
                    
                    
                    
                    
                    
                    ## 현재시간이 1분이면(60분봉 기준) refresh target_price 지정.
                    if 1 < checking_dict['update_time'].minute < 5:
                        ## 날이 지나면.. 08시 50분이면  또는 6시간마다  새로운 종목 선정. 
                        if checking_dict['update_time'].hour == 9 and reset_mode == True:  # reset
                            trader.find_new_coins()
                            my_checking_dict = dict(trader.비보유감시종목, **trader.보유종목)
                            
                            # 선정되면 wm 정지하고 새로 지정.
                            # terminate
                            wm.terminate()
                            print('terminate status', wm.is_alive())
                            # wait till proc dead
                            wm.join()
                            print('after join status' , wm.is_alive())
                            
                            print('reset')
                            reset_mode = False
                            
                            
                            wm = WebSocketManager("ticker", list(my_checking_dict.keys()))
                            
                            trader.my_discord.send_message("reset tartget coins")
                    
                        elif refresh_mode == True:  ## refresh
                            my_checking_dict = trader.refresh_target_price(my_checking_dict)
                            refresh_mode == False
                            print('refresh target_price')
                            
                            
                            trader.my_discord.send_message("refresh target_price")
                    
                        else:
                            pass
                        
                    
                    if 5 < checking_dict['update_time'].minute > 10 :
                        refresh_mode = True 
                        reset_mode = True
                        
                
        except Exception as e:
            print('err1', e)
            print('===data===', data)
            # terminate
            wm.terminate()
            print('terminate status', wm.is_alive())
            # wait till proc dead
            wm.join()
            print('after join status' , wm.is_alive())
            print('err 발생으로 wm terminated!! ')
            print('프로세스 종료')
            sys.exit()
  
        