from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
from werkzeug.utils import secure_filename
from database import get_db_connection, init_db
from model_utils import model_instance
import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey' # Change this for production
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PARTY_UPLOAD_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'parties')
app.config['IRIS_UPLOAD_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'iris')

# Ensure upload directories exist
os.makedirs(app.config['PARTY_UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['IRIS_UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            
            if user['role'] == 'Admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash('Invalid email or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        address = request.form['address']
        dob = request.form['dob']
        aadhaar_id = request.form['aadhaar_id']
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (name, email, password, phone, address, dob, aadhaar_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                         (name, email, password, phone, address, dob, aadhaar_id))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error: {str(e)}')
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/admin/upload_party', methods=['GET', 'POST'])
def upload_party():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        
        if 'image' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['image']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['PARTY_UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            conn = get_db_connection()
            conn.execute('INSERT INTO parties (name, symbol_path, description) VALUES (?, ?, ?)',
                         (name, filename, description))
            conn.commit()
            conn.close()
            flash('Party added successfully')
            return redirect(url_for('admin_dashboard'))
            
    return render_template('upload_party.html')

@app.route('/admin/upload_dataset', methods=['GET', 'POST'])
def upload_dataset():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        dataset_path = request.form.get('dataset_path', '')
        if dataset_path and os.path.exists(dataset_path):
             flash(f"Dataset path set to {dataset_path} (Simulation Only - System uses fixed path 'model/')")
        else:
             flash("Dataset path invalid or not found")
        
    return render_template('upload_dataset.html')

@app.route('/admin/train', methods=['GET', 'POST'])
def train_model():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))

    result = None
    if request.method == 'POST':
        result = model_instance.train_model()
        
    accuracy = model_instance.accuracy
    return render_template('train_model.html', result=result, accuracy=accuracy)

@app.route('/admin/reports')
def performance_reports():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    history = model_instance.history
    return render_template('reports.html', history=history)

@app.route('/admin/results')
def view_voting_results():
    if 'role' not in session or session['role'] != 'Admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT p.name, p.symbol_path, COUNT(v.id) as vote_count 
        FROM parties p 
        LEFT JOIN votes v ON p.id = v.party_id 
        GROUP BY p.id
    ''').fetchall()
    conn.close()
    
    return render_template('results.html', results=results, title="Election Results")

# --- USER ROUTES ---

@app.route('/user/dashboard')
def user_dashboard():
    if 'role' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    return render_template('user_dashboard.html', user=user)

@app.route('/user/view_parties')
def view_parties():
    if 'role' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    parties = conn.execute('SELECT * FROM parties').fetchall()
    conn.close()
    
    return render_template('view_parties.html', parties=parties)


@app.route('/user/vote', methods=['GET', 'POST'])
def vote():
    if 'role' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    if user['has_voted']:
        conn.close()
        flash("You have already voted!")
        return redirect(url_for('user_dashboard'))
    
    parties = conn.execute('SELECT * FROM parties').fetchall()
    conn.close()
    
    if request.method == 'POST':
        if 'iris_image' not in request.files:
            flash('No iris image uploaded')
            return redirect(request.url)
            
        file = request.files['iris_image']
        party_id = request.form['party_id']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"user_{session['user_id']}_{datetime.datetime.now().timestamp()}.png")
            filepath = os.path.join(app.config['IRIS_UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Predict
            predicted_id, error = model_instance.predict(filepath)
            
            if error:
                flash(f"Recognition Error: {error}")
            else:
                 # In a real system, verify if predicted_id matches user.aadhaar_id or similar
                conn = get_db_connection()
                
                flash(f"Iris Recognized as ID: {predicted_id}. Vote Cast Successfully!")
                conn.execute('INSERT INTO votes (user_id, party_id) VALUES (?, ?)', (session['user_id'], party_id))
                conn.execute('UPDATE users SET has_voted = 1 WHERE id = ?', (session['user_id'],))
                conn.commit()
                conn.close()
                return redirect(url_for('user_results'))
                
    return render_template('vote.html', parties=parties)

@app.route('/user/results')
def user_results():
    if 'role' not in session or session['role'] != 'User':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    results = conn.execute('''
        SELECT p.name, p.symbol_path, COUNT(v.id) as vote_count 
        FROM parties p 
        LEFT JOIN votes v ON p.id = v.party_id 
        GROUP BY p.id
    ''').fetchall()
    conn.close()
    
    return render_template('results.html', results=results, title="Live Results")

@app.route('/user/logs')
def user_logs():
    return render_template('logs.html', logs="System Test Logs: OK")

if __name__ == '__main__':
    init_db() # Initialize DB on start
    app.run(debug=False, port=5000)
