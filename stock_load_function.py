from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyperclip
import time
import pandas as pd
import re
import os 
from pyspark.sql import SparkSession
from pyspark.sql.functions import concat, lit, to_date, col, date_format
from selenium.webdriver.chrome.options import Options

def stock_load(spark, search):
    """다음 증권에서 주식 정보 수집"""
    # chrome_options = Options()
    # chrome_options.add_argument("--headless")  # 브라우저 창 없이 실행
    # driver = webdriver.Chrome(options=chrome_options)
    url = 'https://finance.daum.net/domestic'
    driver = webdriver.Chrome()
    driver.get(url)

    #검색창 로딩 대기 (최대 5초)
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="inpSearchStock"]'))
    )

    #검색 값 복사
    pyperclip.copy(search)

    #검색 값 검색창에 붙여넣기
    driver.find_element(By.XPATH, '//*[@id="inpSearchStock"]').send_keys(Keys.CONTROL + 'v')
    time.sleep(1)

    #검색 버튼 클릭
    driver.find_element(By.XPATH, '//*[@id="btnSearchStock"]').click()
    time.sleep(2)

    try:
        # 검색 후 들어간 페이지에서 "현재가" 클릭
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="boxTabs"]/td[2]'))
        )
        driver.find_element(By.XPATH, '//*[@id="boxTabs"]/td[2]').click()
        print("[INFO] boxTabs 2번 탭 클릭 성공")

    except:
        print("[INFO] boxTabs 탭 없음. 대체 경로 수행 중...")

        try:
        # 만약 검색을 했을 때, 여러 종목이 검색되는 경우 맨 위의 종목이 검색 되도록하기.
            WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="boxContents"]/div[2]/div/table/tbody/tr[1]/td[2]/a'))
            ).click()
            print("[INFO] 대체 링크 클릭 성공")
            time.sleep(1)

            # 검색 후 들어간 페이지에서 "현재가" 클릭
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="boxTabs"]/td[2]'))
            )
            driver.find_element(By.XPATH, '//*[@id="boxTabs"]/td[2]').click()

        except :
            print("대체 요소도 존재하지 않음. 페이지 구조 확인 필요")


    all_data = [] # 현재 주가 테이블의 정보를 담는 list
    
    #주식 종목 이름 크롤링
    stock_name = driver.find_element(By.XPATH, '//*[@id="favorite"]')
    stock_name = re.sub(r'\d+', '', stock_name.text)  # 정규식을 사용한 숫자(종목번호) 제거
    stock_name = stock_name.strip('-')  # 앞에 붙은 '-' 기호 제거

    '주식 현재가 일자별 정보 페이지 크롤링 과정'
    i=1 # 페이지 버튼 클릭을 위한 변수
    init = 0 # 현재 주가 테이블의 첫 페이지는 i가 0 부터 시작하지만 다음 페이지 부터는 3부터 시작하기 때문에 첫 페이지 구별을 위한 변수
    count = 1 # 총 크롤링 페이지 수 카운트

    while(True): #while (count<=int(page_count)):
        
        #마지막 전 페이지 까지만 크롤링 하도록 함
        next_page_btn = driver.find_elements(By.XPATH, '//*[@id="boxDayHistory"]/div/div[2]/div/div/a[13]')
        if init == 1 and not next_page_btn:
            print("다음 페이지 버튼이 더 이상 없습니다. 종료합니다.")
            break

        try:
            # 1. 현재 페이지의 테이블 행 수집
            rows = driver.find_elements(By.XPATH, '//*[@id="boxDayHistory"]/div/div[2]/div/table/tbody/tr')
            for row in rows:
                tds = row.find_elements(By.TAG_NAME, "td")
                record = [td.text.strip() for td in tds]
                if len(record) == 8:  # 유효한 데이터만
                    all_data.append(record) # 리스트에 정보 추가           
            print(f"[INFO] {count}페이지 데이터 수집 완료!")     
            
            # 2. 페이지 버튼 클릭
            if init == 0 : # 첫번 째 전체 페이지 인 경우 
                if i == 10 : # 첫번 째 페이지를 모두 크롤링 한 경우 다음 페이지 버튼 클릭하고 init과 i 변수 초기화
                    next_btn_xpath = '//*[@id="boxDayHistory"]/div/div[2]/div/div/a[10]' # 다음 페이지 버튼 클릭 
                    next_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, next_btn_xpath))
                    )
                    next_btn.click()            
                    i=2 # 두번 째 전체 페이지 부터는 두번째째 페이지가 인덱스가 3으로 시작
                    init = 1 # 첫 전체 페이지지 크롤링 완료 시 init 값 변경
                
                else : # 페이지를 전부 크롤링 하지 않은 경우, 다음 숫자 페이지 버튼 클릭
                    next_btn_xpath = f'//*[@id="boxDayHistory"]/div/div[2]/div/div/a[{i}]'
                    next_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, next_btn_xpath))
                    )
                    next_btn.click()

            elif init == 1 : # 첫번 째 전체 페이지를 모두 크롤링 한 다음 페이지 부터 적용
                if i>=3 and i <= 12 : # 두번 째 이상 전체 페이지에서 다음 페이지의 인덱스가 12이기때문에, 전체 다음 페이지로 넘어가서 1단계인 전체 테이블 행을 수집한 후 그 다음 페지이의 인덱스인 3부터 수집한다.
                    next_btn_xpath = f'//*[@id="boxDayHistory"]/div/div[2]/div/div/a[{i}]'
                    next_btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, next_btn_xpath))
                    )
                    next_btn.click()
                    if i==12 : # 두번 째 이상 페이지에서 해당 전체 페이지를 모두 크롤링 한 경우 i 초기화
                        i = 2
                        
            i += 1
            count += 1
            time.sleep(2)

        except Exception as e:
            print(f"[INFO] 더 이상 페이지 없음")
            break
    
    driver.close()
    
    # 3. DataFrame으로 변환
    df = pd.DataFrame(all_data, columns=["date", "open_price", "high_price", "low_price", "close_price",
                                          "price_change", "change_rate", "trading_volume"])

    # 4. int 타입으로 변환하기 위한 전처리
    for col in ["open_price", "high_price", "low_price", "close_price", "price_change", "trading_volume"]:
        df[col] = df[col].str.replace("▲", "").str.replace("▼", "").str.replace(",", "").astype(str)
    
    # 5.가격, 볼륨 등을 int 타입으로 변환
    for col in ['open_price', 'high_price', 'low_price','close_price','trading_volume']:
        df[col] = df[col].astype(int)
    
    # 6.DataFrame에 종목이름 추가
    df['name'] = stock_name 
    df = df[['name', "open_price", "high_price", "low_price", "close_price", "price_change", "change_rate", "trading_volume","date"]]

    save_financial_data_to_db(spark, df, stock_name)

    ## csv 파일 형식으로 변경 후 db에 저장
    # save_to_csv(df,f'daum_financial_{stock_name}.csv')
    # save_to_database_search_information(spark, stock_name)

    # pd.set_option('display.max_rows', None)
    # print(df)


def save_financial_data_to_db(spark, financial_data, stock_name):
    """CSV 저장 없이 판다스 DataFrame을 Spark DataFrame으로 변환하고 DB에 저장"""
    
    # 판다스 → 스파크 데이터프레임 변환
    sdf = spark.createDataFrame(financial_data)

    # 날짜 컬럼 전처리
    sdf = sdf.withColumn("date", concat(lit("20"), col("date")))  # 20 + 25.06.06 형태 처리
    sdf = sdf.withColumn("date", to_date(col("date"), "yyyy.MM.dd"))
    sdf = sdf.withColumn("date", date_format("date", "yyyy-MM-dd"))

    # DB에 적재
    sdf.write.format("jdbc").options(
        url="jdbc:mysql://localhost:3306/news_project",
        driver="com.mysql.cj.jdbc.Driver",
        dbtable="daum_financial_stock_table",
        user="root",
        password="5941"
    ).mode("append").save()

    print(f"[INFO] {stock_name} 데이터가 DB에 성공적으로 적재되었습니다.")


def save_to_csv(df, filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(base_dir, "csv_folder/financial_data")
    os.makedirs(folder_path, exist_ok=True)

    full_path = os.path.join(folder_path, filename)

    df.to_csv(full_path, index=False, encoding="utf-8-sig")
    print(f"[INFO] CSV 저장 완료: {full_path}")

def save_to_database_search_information(spark, stock_name):
    '''MySQL의 DB에 저장하는 함수'''
    os.environ["PYSPARK_PYTHON"] = "C:/Users/jaehy/anaconda3/python.exe" # 파이썬 경로를 지정하니까 코드가 돌아감

    #읽어올 csv 파일 설정
    file_path = f'C:/JaeHyeok/Crawling/csv_folder/financial_data/daum_financial_{stock_name}.csv'
    sdf = spark.read.option("header", True).csv(file_path) #spark DataFrame으로 변환
    
    # DB에 적재하기 위한 date 형식 변환
    sdf = sdf.withColumn("date", concat(lit("20"), col("date")))
    sdf = sdf.withColumn("date", to_date(col("date"), "yyyy.MM.dd"))
    sdf = sdf.withColumn("date", date_format("date", "yyyy-MM-dd"))

    #jdbc를 사용하여 MySQL 연결
    sdf.write.format("jdbc").options(
        url="jdbc:mysql://localhost:3306/news_project",  # DB 정보
        driver="com.mysql.cj.jdbc.Driver",
        dbtable="daum_financial_stock_table",  # 저장할 테이블 이름
        user="root",
        password= 5941
    ).mode("append").save()

