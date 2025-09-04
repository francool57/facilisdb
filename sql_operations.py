import pandas as pd
import mysql.connector.pooling

def userdbname(email):
    return email.split("@")[0] + "_db"

# Database configuration

db_config = {
    "host": "0.0.0.0",
    "user": "root",
    "password": "*******",  
    "ssl_disabled": True    # Should be turned ON for WSGI servers
}

users_db_config = {
    "host": "0.0.0.0",
    "user": "root",
    "password": "*******",
    "database": "websitedata",
    "ssl_disabled": True    # Should be turned ON for WSGI servers
}

# Database pool for easier and more stable connections

db_pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)
users_db_pool = mysql.connector.pooling.MySQLConnectionPool(pool_name="users_pool", pool_size=5, **users_db_config)

def get_db_connection():
    return db_pool.get_connection()

def get_users_db_connection():
    return users_db_pool.get_connection()

# Server-user ops

def get_user_databases(email):
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("USE " + userdbname(email))
        return userdbname(email)
    finally:
        cursor.close()
        connection.close()

def get_user(id):
    '''
        Gets information from logged in users
    '''

    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError(f"No user found with id {id}")
        return user
    
    except mysql.connector.Error as err:
        connection.reconnect(attempts=3, delay=5)
        cursor.execute("SELECT * FROM users WHERE id = %s", (id,))
        user = cursor.fetchone()
        if not user:
            raise ValueError(f"No user found with id {id}")
        return user
    
    finally:
        cursor.close()
        connection.close()

def get_user_by_email(email):
    '''
        Used for login/logon operations
    '''
    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()

def get_all_users():
    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM users")
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

def verify_admin(email):
    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT * FROM admins WHERE adminscol = %s", (email,))
        if cursor.fetchone():
            return True
        else:
            return False
    finally:
        cursor.close()
        connection.close()
    
def change_email(email, new_email):
    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        print("UPDATE users SET email = %s WHERE email = %s", (new_email, email))
        
        for table in get_database_tables(userdbname(email)):
            print(f"Altering table {table} to change database reference...")
            cursor.execute(f"RENAME TABLE {email.split('@')[0]}_db.{table} TO {new_email.split('@')[0]}_db.{table}")
            connection.commit()
        
        cursor.execute(f'DROP DATABASE {userdbname(email)}')
        cursor.execute("UPDATE users SET email = %s WHERE email = %s", (new_email, email))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def create_user(username, password, email):
    connection = get_db_connection()
    cursor = connection.cursor()
    users_connection = get_users_db_connection()
    users_cursor = users_connection.cursor()
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS " + userdbname(email))
        connection.commit()
        users_cursor.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", (username, password, email))
        users_connection.commit()
    finally:
        cursor.close()
        connection.close()
        users_cursor.close()
        users_connection.close()

def update_username(id, new_username):
    connection = get_users_db_connection()
    cursor = connection.cursor()
    try:
        print("UPDATE users SET username = %s WHERE id = %s", (new_username, id))
        cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, id))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

# Read operations

def get_table_columns(database, table):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        cursor.execute(f"DESCRIBE {table}")
        return [col[0] for col in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

# Write operations

def create_table(database, table, columns):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        column_definitions = ""
        for col in columns:
            column_definitions += f"`{col[0]}` VARCHAR(255), "

        cursor.execute(f"CREATE TABLE {table} (id int PRIMARY KEY AUTO_INCREMENT, {column_definitions.strip(', ')})")
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def delete_table(table, database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        cursor.execute(f"DROP TABLE {table}")
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def insert_data(table, data, database):
    connection = get_db_connection()
    cursor = connection.cursor()

    columns = get_table_columns(database, table)
    columns = [col for col in columns if col != 'id']  # Exclude 'id' column
    
    placeholders = ", ".join(["%s"] * len(columns))
    values = [data[col] for col in columns]
    
    columns = [("`" + col + "`") for col in columns if col != 'id']  # Exclude 'id' column
    columns_str = ", ".join(columns)

    cursor.execute(f"USE {database}")
    query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
    print(query)

    
    cursor.execute(query, values)
    connection.commit()
    cursor.close()
    connection.close()

def delete_data(table, data, database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        cursor.execute(f"DELETE FROM {table} WHERE id = %s", (data['id'],))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def get_data_range(database, table, start_row, end_row):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        query = f"SELECT * FROM {table} LIMIT {start_row - 1}, {end_row - start_row + 1}"
        cursor.execute(query)
        df = pd.DataFrame(cursor.fetchall(), columns=get_table_columns(database, table))
        return df.to_html(classes='mystyle', index=False)
    finally:
        cursor.close()
        connection.close()

def get_user_tables_preview(database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        tables = get_database_tables2(database)
        previews = []
        for table_info in tables:
            table_name = table_info['name']
            columns = get_table_columns(database, table_name)
            cursor.execute(f"USE {database}")
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            if table_name != "user_charts":
                previews.append({
                    'name': table_name,
                    'columns': columns,
                    'rows': rows,
                    'row_count': table_info['row_count']
                })
        return previews
    finally:
        cursor.close()
        connection.close()

def get_database_tables(database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        cursor.execute("SHOW TABLES WHERE Tables_in_" + database + " NOT LIKE 'user_charts'")
        return [table[0] for table in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

def get_database_tables2(database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        table_info = []
        for table in tables:
            if table != "user_charts":  
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                table_info.append({'name': table, 'row_count': row_count})
        return table_info
    finally:
        cursor.close()
        connection.close()

def get_data(db_name, table_name):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {db_name}")
        cursor.execute(f"SELECT * FROM {table_name}")
        
        # Fetch column names
        column_names = [description[0] for description in cursor.description]
        # Fetch all rows
        rows = cursor.fetchall()
        
        # Return column names as the first row, followed by data rows
        return [[column for column in column_names]] + list(rows)
    finally:
        cursor.close()
        connection.close()

def get_data_html(database, table):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        query = f"SELECT * FROM {table}"  # Limit to 10 rows for preview
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        html = "<table class='table'><thead><tr>"
        for col in columns:
            html += f"<th>{col}</th>"
        html += "</tr></thead><tbody>"
        
        for row in rows:
            html += "<tr>"
            for cell in row:
                html += f"<td>{cell}</td>"
            html += "</tr>"
        
        html += "</tbody></table>"
        
        if not rows:
            html += "<p>No data available. You can add data using the 'Update Table' feature.</p>"
        
        return html
    finally:
        cursor.close()
        connection.close()

'''

    USER CHARTS

'''

def save_chart(database, chart_data):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        create_user_charts_table(database)  # Ensure the table exists
        cursor.execute(f"USE {database}")
        query = """
        INSERT INTO user_charts (name, type, table_name, x_axis, y_axis)
        VALUES (%s, %s, %s, %s, %s)
        """
        values = (

            chart_data['name'], chart_data['type'], chart_data['table'], 
            chart_data['x_axis'], chart_data['y_axis'] 
        )
        cursor.execute(query, values)
        connection.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        connection.close()

def create_user_charts_table(database):
    
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_charts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(50) NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            x_axis VARCHAR(255) NOT NULL,
            y_axis VARCHAR(255) NOT NULL,
            color VARCHAR(20),
            border_color VARCHAR(20),
            border_width INT,
            fill BOOLEAN,
            tension FLOAT
        )
        """
        cursor.execute(create_table_query)
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def get_saved_charts(database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        create_user_charts_table(database)  # Ensure the table exists
        cursor.execute(f"USE {database}")
        query = "SELECT * FROM user_charts"
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    finally:
        cursor.close()
        connection.close()

def get_chart_data(database, chart_data):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        query = f"SELECT {chart_data['x_axis']}, {chart_data['y_axis']} FROM {chart_data['table']}"
        cursor.execute(query)
        result = cursor.fetchall()
        
        labels = []
        values = []
        for row in result:
            if row[0] is not None:
                labels.append(str(row[0]))
            else:
                labels.append('')
            
            if row[1] is not None:
                try:
                    values.append(float(row[1]))
                except ValueError:
                    values.append(0)  # or any default value you prefer
            else:
                values.append(0)  # or any default value you prefer
        return {"labels": labels, "values": values}
    except mysql.connector.Error as err:
        return {"error": str(err)}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        connection.close()

def delete_chart(database, chart_id):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        query = "DELETE FROM user_charts WHERE id = %s"
        cursor.execute(query, (chart_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        connection.close()

def create_user_charts_table(database):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(f"USE {database}")
        create_table_query = """
        CREATE TABLE IF NOT EXISTS user_charts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            type VARCHAR(50) NOT NULL,
            table_name VARCHAR(255) NOT NULL,
            x_axis VARCHAR(255) NOT NULL,
            y_axis VARCHAR(255) NOT NULL
        )
        """
        cursor.execute(create_table_query)
        connection.commit()
    finally:
        cursor.close()
        connection.close()

def ensure_database_structure():
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS websitedata")
        cursor.execute("USE websitedata")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE
            )
        """)
        connection.commit()
    except mysql.connector.Error as err:
        print(f"Error ensuring database structure: {err}")
        raise
    finally:
        cursor.close()
        connection.close()
