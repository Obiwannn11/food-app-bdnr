# app.py

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
from functools import wraps
import datetime # Import modul datetime untuk tanggal pesanan

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
carts_collection = db.carts
orders_collection = db.orders # Koleksi baru untuk pesanan


# --- DECORATORS (Tidak berubah) ---
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


# --- RUTE AUTENTIKASI (Tidak berubah) ---
# ... (semua rute /register, /login, /logout tetap sama)
@app.route('/register', methods=['GET', 'POST'])
def register():
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
    session.clear()
    flash('Anda telah berhasil logout.')
    return redirect(url_for('login'))

# --- RUTE UTAMA (Tidak berubah) ---
@app.route('/')
@login_required
def index():
    all_foods = list(foods_collection.find())
    return render_template('index.html', foods=all_foods)


# --- RUTE KERANJANG BELANJA (Tidak berubah) ---
# ... (semua rute /cart/add, /cart, /cart/update, /cart/remove tetap sama)
@app.route('/cart/add/<food_id>', methods=['POST'])
@login_required
def add_to_cart(food_id):
    user_id = session['user_id']
    user_cart = carts_collection.find_one({'user_id': user_id})
    if not user_cart:
        carts_collection.insert_one({'user_id': user_id, 'items': [{'food_id': ObjectId(food_id), 'quantity': 1}]})
    else:
        item_exists = carts_collection.find_one({'user_id': user_id, 'items.food_id': ObjectId(food_id)})
        if item_exists:
            carts_collection.update_one({'user_id': user_id, 'items.food_id': ObjectId(food_id)},{'$inc': {'items.$.quantity': 1}})
        else:
            carts_collection.update_one({'user_id': user_id},{'$push': {'items': {'food_id': ObjectId(food_id), 'quantity': 1}}})
    flash('Item berhasil ditambahkan ke keranjang!')
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
@login_required
def view_cart():
    user_id = session['user_id']
    pipeline = [{'$match': {'user_id': user_id}},{'$unwind': '$items'},{'$lookup': {'from': 'foods','localField': 'items.food_id','foreignField': '_id','as': 'food_details'}},{'$unwind': '$food_details'},{'$project': {'_id': 0,'user_id': '$user_id','food_id': '$items.food_id','quantity': '$items.quantity','name': '$food_details.name','price': '$food_details.price','image_url': '$food_details.image_url','subtotal': {'$multiply': ['$items.quantity', '$food_details.price']}}}]
    cart_items = list(carts_collection.aggregate(pipeline))
    grand_total = sum(item['subtotal'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, grand_total=grand_total)

@app.route('/cart/update/<food_id>', methods=['POST'])
@login_required
def update_cart(food_id):
    quantity = int(request.form['quantity'])
    if quantity > 0:
        carts_collection.update_one({'user_id': session['user_id'], 'items.food_id': ObjectId(food_id)},{'$set': {'items.$.quantity': quantity}})
        flash('Kuantitas berhasil diperbarui.')
    else:
        return remove_from_cart(food_id)
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<food_id>', methods=['POST'])
@login_required
def remove_from_cart(food_id):
    carts_collection.update_one({'user_id': session['user_id']},{'$pull': {'items': {'food_id': ObjectId(food_id)}}})
    flash('Item berhasil dihapus dari keranjang.')
    return redirect(url_for('view_cart'))


# --- RUTE CHECKOUT & RIWAYAT PESANAN (BARU) ---

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    user_id = session['user_id']
    
    # Ambil data dari keranjang menggunakan pipeline yang sama
    pipeline = [{'$match': {'user_id': user_id}}, {'$unwind': '$items'}, {'$lookup': {'from': 'foods', 'localField': 'items.food_id', 'foreignField': '_id', 'as': 'food_details'}}, {'$unwind': '$food_details'}, {'$project': {'_id': 0, 'food_id': '$items.food_id', 'name': '$food_details.name', 'quantity': '$items.quantity', 'price': '$food_details.price'}}]
    cart_items = list(carts_collection.aggregate(pipeline))

    # Cek jika keranjang kosong
    if not cart_items:
        flash('Keranjang Anda kosong, tidak bisa checkout.')
        return redirect(url_for('view_cart'))

    # Hitung total harga
    total_price = sum(item['quantity'] * item['price'] for item in cart_items)
    
    # Buat dokumen pesanan baru
    new_order = {
        'user_id': ObjectId(user_id),
        'produk': cart_items,
        'total_price': total_price,
        'order_date': datetime.datetime.now(),
        'status': 'Diproses'
    }
    orders_collection.insert_one(new_order)
    
    # Kosongkan keranjang pengguna setelah checkout
    carts_collection.delete_one({'user_id': user_id})
    
    flash('Pesanan Anda telah berhasil dibuat!')
    return redirect(url_for('order_history'))


@app.route('/orders')
@login_required
def order_history():
    # Ambil semua pesanan milik pengguna yang login, urutkan dari yang terbaru
    user_orders = list(orders_collection.find({
        'user_id': ObjectId(session['user_id'])
    }).sort('order_date', -1))
    
    return render_template('order_history.html', orders=user_orders)


# --- RUTE ADMIN (Tidak berubah) ---
# ... (semua rute /admin/... tetap sama)
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    all_foods = list(foods_collection.find().sort('name'))
    return render_template('admin_dashboard.html', foods=all_foods)

@app.route('/admin/add_food', methods=['POST'])
@admin_required
def add_food():
    new_food = {"name": request.form['name'], "description": request.form['description'], "price": float(request.form['price']), "image_url": request.form['image_url']}
    foods_collection.insert_one(new_food)
    flash(f"Menu '{new_food['name']}' berhasil ditambahkan!")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit_food/<food_id>', methods=['GET', 'POST'])
@admin_required
def edit_food(food_id):
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