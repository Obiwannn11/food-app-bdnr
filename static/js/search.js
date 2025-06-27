// static/js/search.js

// Pastikan skrip berjalan setelah seluruh halaman HTML dimuat
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const foodGrid = document.getElementById('food-grid');

    // Fungsi untuk menggambar ulang kartu makanan berdasarkan data
    const renderFoods = (foods) => {
        // Kosongkan dulu grid yang ada
        foodGrid.innerHTML = '';

        if (foods.length === 0) {
            foodGrid.innerHTML = '<p>Menu yang Anda cari tidak ditemukan.</p>';
            return;
        }

        // Loop melalui data makanan dan buat elemen HTML untuk masing-masing
        foods.forEach(food => {
            const foodCard = document.createElement('div');
            foodCard.className = 'food-card';

            const price = new Intl.NumberFormat('id-ID').format(food.price);

            foodCard.innerHTML = `
                <img src="${food.image_url}" alt="${food.name}">
                <h4>${food.name}</h4>
                <p>${food.description}</p>
                <strong>Rp ${price}</strong>
                <br><br>
                <form action="/cart/add/${food._id}" method="post">
                    <button type="submit">Tambah ke Keranjang</button>
                </form>
            `;
            foodGrid.appendChild(foodCard);
        });
    };

    // Tambahkan event listener untuk setiap ketikan di kotak pencarian
    searchInput.addEventListener('input', async (event) => {
        const query = event.target.value;

        try {
            // "Berbisik" ke server menggunakan Fetch API
            const response = await fetch(`/api/search?q=${query}`);
            const foods = await response.json();
            
            // Perbarui tampilan dengan hasil dari server
            renderFoods(foods);

        } catch (error) {
            console.error('Error saat melakukan pencarian:', error);
            foodGrid.innerHTML = '<p>Terjadi kesalahan saat memuat menu.</p>';
        }
    });
});