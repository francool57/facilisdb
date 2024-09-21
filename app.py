from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sql_operations
from functools import wraps
from werkzeug.security import check_password_hash
from datetime import timedelta
import os
port=int(os.environ.get('PORT', 10000))
app = Flask(__name__)
#app.secret_key = str(os.urandom(12).hex())  # Set a secret key for session management
app.secret_key = 'dawdad'
app.testing = True

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/about-us')
def about_us():
    return render_template('about_us.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    email = request.form['email']

    if sql_operations.get_user_by_email(email):
        return jsonify({"success": False, "error": 'Email is already registered'})
    
    sql_operations.create_user(username, password, email)
    user = sql_operations.get_user_by_email(email)
    session['user_id'] = user[0]
    return jsonify({"success": True, "redirect": url_for('index')})

@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']
    user = sql_operations.get_user_by_email(email)

    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        return jsonify({"success": True, "redirect": url_for('index')})
    else:
        return jsonify({"success": False, "error": 'Invalid credentials'})

@app.route('/')
def welcome():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('main.html')

@app.route('/index')
@login_required
def index():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    tables = sql_operations.get_user_tables_preview(user_db)
    if str(tables) == '[]':
        return render_template('index.html', tables=tables, error='No tables found. Would you like to ')
    else:   
        return render_template('index.html', tables=tables)

@app.route('/create_table', methods=['GET', 'POST'])
@login_required
def table_creator():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    
    if request.method == 'POST':
        table_name = request.form['table_name']
        num_columns = int(request.form['num_columns'])
        columns = []
        for i in range(1, num_columns + 1):
            column_name = request.form[f'column_name_{i}']
            column_type = 'text'
            columns.append((column_name, column_type))
        try:
            false_columns = ["id", "ids", "id_user", "id_user_chart", 'order']
            error_message = []
            for column in columns:
                if column[0].lower() in false_columns:
                    error_message = f"Column name cannot be '{column[0]}'."
                    return jsonify({"success": False, "message": error_message})
            sql_operations.create_table(user_db, table_name, columns)
            # Insert data if provided
            data_rows = []
            row_index = 0
            while True:
                row_data = {}
                for column in columns:
                    key = f"data_row_{row_index}_data_{column[0]}"
                    if key in request.form:
                        row_data[column[0]] = request.form[key]
                    else:
                        break
                if row_data:
                    data_rows.append(row_data)
                    row_index += 1
                else:
                    break

            for row_data in data_rows:
                sql_operations.insert_data(table_name, row_data, user_db)
            
            # Fetch the newly created table data
            table_html = sql_operations.get_data2(user_db, table_name)
            
            return jsonify({
                "success": True, 
                "message": f"Table '{table_name}' created successfully in users database.",
                "table_html": table_html
            })
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    
    return render_template('table_creation.html', user_db=user_db)


@app.route('/delete_table', methods=['POST'])
@login_required
def delete_table():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    table = request.form['table']
    try:
        sql_operations.delete_table(table, user_db)
        return jsonify({"success": True, "message": f"Table '{table}' has been deleted from database '{user_db}'"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error deleting table: {str(e)}"})

@app.route('/get_tables')
@login_required
def get_tables():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    tables = sql_operations.get_database_tables(user_db)
    return jsonify(tables)

@app.route('/get_columns/<table>')
@login_required
def get_columns(table):
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    columns = sql_operations.get_table_columns(user_db, table)
    return jsonify(columns)

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect('/')

@app.route('/update_table', methods=['GET', 'POST'])
@login_required
def update_table():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    if request.method == 'POST':
        data = request.json
        
        table = next(item['value'] for item in data if item['name'] == 'table')
        
        # Extract column names and data
        columns = [item['name'].rstrip('[]') for item in data if item['name'] != 'table']
        columns = list(dict.fromkeys(columns))  # Remove duplicates while preserving order

        # Group data by columns
        column_data = {col: [] for col in columns}
        for item in data:
            if item['name'].rstrip('[]') in columns:
                column_data[item['name'].rstrip('[]')].extend(item['value'])
        # Determine the number of rows
        num_rows = len(next(iter(column_data.values())))

        try:
            formatted_rows = []
            for i in range(num_rows):
                row_data = {col: column_data[col][i] for col in columns}
                formatted_row = " ".join([f"{col}:{row_data[col]}" for col in columns])
                formatted_rows.append(formatted_row)
                sql_operations.insert_data(table, row_data, user_db)
            
            formatted_output = "\n".join(formatted_rows)
            
            return jsonify({
                "success": True, 
                "message": f"Data inserted successfully into table '{table}' in database '{user_db}'",
                "formatted_data": formatted_output
            })
        except Exception as e:
            if "01000" in str(e):
                column = str(e).split("'")[1].split("'")[0]
                return jsonify({"success": False, "message": "Column: '" + column + "' should not have special characters: ()+-*/=<>$#@!~`%^&*?;:[]\\{}|"})
            else:
                print("Error:", str(e))  # Debug print
                return jsonify({"success": False, "message": f"Error inserting data: {str(e)}"})
    
    return render_template('update_table.html', user_db=user_db)

@app.route('/delete_chart', methods=['POST'])
@login_required
def delete_chart():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    chart_id = request.form['chart_id']
    success = sql_operations.delete_chart(user_db, chart_id)
    return jsonify({"success": success})

@app.route('/custom_query', methods=['GET', 'POST'])
@login_required
def custom_query():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    if request.method == 'POST':
        query = request.form['query']
        try:
            result = sql_operations.execute_custom_query(user_db, query)
            return result
        except Exception as e:
            return str(e), 400
    return render_template('custom_query.html', user_db=user_db)

@app.route('/get_table_data', methods=['POST'])
@login_required
def get_table_data():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    table_name = request.form['table']
    result = sql_operations.get_data(user_db, table_name)
    
    # Ensure result is a list of lists (or tuples)
    if result and isinstance(result[0], (list, tuple)):
        headers = result[0]
        rows = result[1:]
    else:
        headers = []
        rows = []
    
    return render_template('table_data.html', headers=headers, rows=rows, table_name=table_name)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = sql_operations.get_user(session['user_id'])
    if request.method == 'POST':
        new_username = request.form['username']
        if new_username != user[1]:
            sql_operations.update_username(user[0], new_username)
            return render_template('profile.html', user=user, success=True)
        else:
            return render_template('profile.html', user=user, success=False)
    return render_template('profile.html', user=user)


@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    sql_operations.delete_user(user_id)
    session.pop('user_id', None)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/custom_charts', methods=['GET', 'POST'])
@login_required
def custom_charts():
    user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
    tables = sql_operations.get_database_tables(user_db)
    
    if request.method == 'POST':
        data = request.json
        # Save the chart configuration to the database
        chart_id = sql_operations.save_chart(user_db, data)
        return jsonify({"success": True, "chart_id": chart_id})
    
    # Fetch saved charts
    saved_charts = sql_operations.get_saved_charts(user_db)
    
    return render_template('custom_charts.html', tables=tables, saved_charts=saved_charts)

@app.route('/get_chart_data', methods=['POST'])
@login_required
def get_chart_data():
    try:
        user_db = str(sql_operations.get_user(session['user_id'])[3].split('@')[0]) + '_db'
        data = request.json
        chart_data = sql_operations.get_chart_data(user_db, data)
        if "error" in chart_data:
            print(chart_data["error"])
            return jsonify({"error": chart_data["error"]}), 500
        return jsonify(chart_data)
    except Exception as e:
        print(f"Error fetching chart data: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    sql_operations.ensure_database_structure()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
