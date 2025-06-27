# app.py

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
from functools import wraps

# Inisialisasi Aplikasi Flask
app = Flask(__name__)
app.secret_key = "kunci_rahasia_super_aman_milikmu" 

# Konfigurasi Koneksi MongoDB Lokal
MONGO_URI = "mongodb://localhost:27017/" 
DB_NAME = "food_app_db"

# Menyiapkan koneksi dan collections
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db.users
foods_collection = db.foods
carts_collection = db.carts # Koleksi baru untuk keranjang belanja


# --- DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Anda harus login untuk mengakses halaman ini.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Anda tidak memiliki izin untuk mengakses halaman ini!')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# --- RUTE AUTENTIKASI (Tetap sama) ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (kode tidak berubah) ...
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if users_collection.find_one({'username': username}):
            flash('Username sudah digunakan!')
            return redirect(url_for('register'))
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        users_collection.insert_one({'username': username, 'password': hashed_password, 'role': 'user'})
        flash('Registrasi berhasil! Silakan login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (kode tidak berubah) ...
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login berhasil!')
            return redirect(url_for('index'))
        else:
            flash('Login gagal. Cek kembali username dan password Anda.')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    # ... (kode tidak berubah) ...
    session.clear()
    flash('Anda telah berhasil logout.')
    return redirect(url_for('login'))


# --- RUTE UTAMA ---
@app.route('/')
@login_required
def index():
    all_foods = list(foods_collection.find())
    return render_template('index.html', foods=all_foods)


# --- RUTE KERANJANG BELANJA (CART) ---

@app.route('/cart/add/<food_id>', methods=['POST'])
@login_required
def add_to_cart(food_id):
    user_id = session['user_id']
    
    # Cari keranjang milik pengguna
    user_cart = carts_collection.find_one({'user_id': user_id})

    if not user_cart:
        # Jika pengguna belum punya keranjang, buatkan satu
        carts_collection.insert_one({
            'user_id': user_id,
            'items': [{'food_id': ObjectId(food_id), 'quantity': 1}]
        })
    else:
        # Jika keranjang sudah ada, cek apakah item sudah ada di keranjang
        item_exists = carts_collection.find_one({
            'user_id': user_id, 
            'items.food_id': ObjectId(food_id)
        })

        if item_exists:
            # Jika item sudah ada, tambah kuantitasnya (increment)
            carts_collection.update_one(
                {'user_id': user_id, 'items.food_id': ObjectId(food_id)},
                {'$inc': {'items.$.quantity': 1}}
            )
        else:
            # Jika item belum ada, tambahkan ke dalam keranjang (push)
            carts_collection.update_one(
                {'user_id': user_id},
                {'$push': {'items': {'food_id': ObjectId(food_id), 'quantity': 1}}}
            )

    flash('Item berhasil ditambahkan ke keranjang!')
    # Redirect kembali ke halaman sebelumnya
    return redirect(request.referrer or url_for('index'))


@app.route('/cart')
@login_required
def view_cart():
    user_id = session['user_id']

    # === MongoDB Aggregation Pipeline ===
    # Ini adalah query canggih untuk menggabungkan data dari 'carts' dan 'foods'
    pipeline = [
        # 1. Temukan keranjang yang sesuai dengan user yang sedang login
        {'$match': {'user_id': user_id}},
        # 2. Pecah array 'items' menjadi dokumen terpisah
        {'$unwind': '$items'},
        # 3. Gabungkan (lookup/join) dengan koleksi 'foods' berdasarkan 'food_id'
        {'$lookup': {
            'from': 'foods',
            'localField': 'items.food_id',
            'foreignField': '_id',
            'as': 'food_details'
        }},
        # 4. Pecah array 'food_details' yang baru terbentuk
        {'$unwind': '$food_details'},
        # 5. Bentuk ulang (project) dokumen agar sesuai dengan yang kita inginkan
        {'$project': {
            '_id': 0,
            'user_id': '$user_id',
            'food_id': '$items.food_id',
            'quantity': '$items.quantity',
            'name': '$food_details.name',
            'price': '$food_details.price',
            'image_url': '$food_details.image_url',
            # Hitung subtotal untuk setiap item
            'subtotal': {'$multiply': ['$items.quantity', '$food_details.price']}
        }}
    ]

    cart_items = list(carts_collection.aggregate(pipeline))
    
    # Hitung total keseluruhan
    grand_total = sum(item['subtotal'] for item in cart_items)
    
    return render_template('cart.html', cart_items=cart_items, grand_total=grand_total)


@app.route('/cart/update/<food_id>', methods=['POST'])
@login_required
def update_cart(food_id):
    quantity = int(request.form['quantity'])
    if quantity > 0:
        carts_collection.update_one(
            {'user_id': session['user_id'], 'items.food_id': ObjectId(food_id)},
            {'$set': {'items.$.quantity': quantity}}
        )
        flash('Kuantitas berhasil diperbarui.')
    else:
        # Jika kuantitas 0 atau kurang, hapus itemnya
        return remove_from_cart(food_id)
    return redirect(url_for('view_cart'))


@app.route('/cart/remove/<food_id>', methods=['POST'])
@login_required
def remove_from_cart(food_id):
    carts_collection.update_one(
        {'user_id': session['user_id']},
        {'$pull': {'items': {'food_id': ObjectId(food_id)}}}
    )
    flash('Item berhasil dihapus dari keranjang.')
    return redirect(url_for('view_cart'))


# --- RUTE ADMIN (Tidak berubah) ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    # ... (kode tidak berubah)
    all_foods = list(foods_collection.find().sort('name'))
    return render_template('admin_dashboard.html', foods=all_foods)

@app.route('/admin/add_food', methods=['POST'])
@admin_required
def add_food():
    # ... (kode tidak berubah)
    new_food = {"name": request.form['name'], "description": request.form['description'], "price": float(request.form['price']), "image_url": request.form['image_url']}
    foods_collection.insert_one(new_food)
    flash(f"Menu '{new_food['name']}' berhasil ditambahkan!")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_food/<food_id>', methods=['GET', 'POST'])
@admin_required
def edit_food(food_id):
    # ... (kode tidak berubah)
    food_object_id = ObjectId(food_id)
    if request.method == 'POST':
        updated_data = {"$set": {"name": request.form['name'],"description": request.form['description'],"price": float(request.form['price']),"image_url": request.form['image_url']}}
        foods_collection.update_one({'_id': food_object_id}, updated_data)
        flash("Menu berhasil diperbarui!")
        return redirect(url_for('admin_dashboard'))
    food_to_edit = foods_collection.find_one({'_id': food_object_id})
    return render_template('edit_food.html', food=food_to_edit)

@app.route('/admin/delete_food/<food_id>', methods=['POST'])
@admin_required
def delete_food(food_id):
    foods_collection.delete_one({'_id': ObjectId(food_id)})
    flash("Menu berhasil dihapus!")
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)