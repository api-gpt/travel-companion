import psycopg2
import os

DATABASE_URL = os.getenv('DATABASE_URL')


def connect_pg():
    try:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    except Exception as err:
        print(f'Error connecting to database: {err}')


class Database():
    def __init__(self) -> None:
        self.connection = connect_pg()

    def create_user_table(self):
        try:
            sql = """
            CREATE TABLE IF NOT EXISTS users (
                id            VARCHAR(255) PRIMARY KEY,
                provider      VARCHAR(50),
                access_token  VARCHAR(255),
                first_name    VARCHAR(50),
                last_name     VARCHAR(50),
                email         VARCHAR(255),
                url           VARCHAR(255),
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                self.connection.commit()
        except Exception as err:
            print(f'Error running query: {err}')

    def insert_user(self, user_data):
        try:
            sql = """
            INSERT INTO users (id, provider, access_token, first_name, last_name, email, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET 
                access_token = EXCLUDED.access_token,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                email = EXCLUDED.email,
                url = EXCLUDED.url
            RETURNING id;
            """
            with self.connection.cursor() as cursor:
                cursor.execute(sql, (
                    user_data['id'],
                    user_data['provider'],
                    user_data['access_token'],
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data['email'],
                    user_data['url']
                ))
                self.connection.commit()
            return cursor.fetchone()[0]
        except Exception as err:
            print(f'Error inserting user: {err}')
            return None

    def drop_table(self, table_name):
        try:
            # Step 1: Check if the table exists
            check_table_sql = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            );
            """
            with self.connection.cursor() as cursor:
                cursor.execute(check_table_sql, (table_name,))
                exists = cursor.fetchone()[0]

                if exists:
                    # Step 2: Drop the table if it exists
                    drop_table_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE;"
                    cursor.execute(drop_table_sql)
                    self.connection.commit()
                    print(f"Table {table_name} has been dropped.")
                else:
                    print(f"Table {table_name} does not exist.")
        except Exception as err:
            print(f"Error dropping table {table_name}: {err}")