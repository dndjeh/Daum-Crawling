from pyspark.sql import Row
from pyspark.sql.functions import lit
from passlib.hash import bcrypt
import jwt
import datetime

def login(spark, id, password):
    """로그인 처리"""
    # 해당 ID의 사용자 검색
    user_df = spark.table("user_info").filter(f"id = '{id}'").collect()

    if not user_df:
        return "존재하지 않는 아이디입니다."
    
    user_row = user_df[0] # 해당 id가 1개이므로 0번째 행 선택
    hashed_password = user_row["password"]
    is_admin = user_row["is_admin"]
    nickname = user_row['nickname']

    # bcrypt.verify() 함수로 암호화된 패스워드와 입력한 패스워드 확인
    if bcrypt.verify(password, hashed_password):
        return {
            "id": id,
            "is_admin": is_admin,
            'nickname' : nickname
        }
    else:
        return "비밀번호가 일치하지 않습니다."


def generate_jwt(user_id, nickname, is_admin, secret_key, expire_minutes=60):
    '''토큰 생성'''
    payload = {
        "user_id": user_id,
        "is_admin": is_admin, # 관리자 계정 확인
        'nickname' : nickname,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=expire_minutes)
    }
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token