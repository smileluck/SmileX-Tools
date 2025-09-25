from utils.mysql import UsingMysql


if __name__ == "__main__":
    
    with UsingMysql(log_time=True) as um:
        um.cursor.execute("select 1 from dual")
        result = um.cursor.fetchone()
        print(result)