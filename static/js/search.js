// static/js/search.js

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const foodGrid = document.getElementById('food-grid');
    const filterButtonsContainer = document.getElementById('filter-buttons');

    let currentQuery = '';
    let currentCategory = 'Semua';

    // --- Fungsi Utama untuk Mengambil Data & Merender ---
    const fetchAndRenderFoods = async () => {
        try {
            // Kirim query dan category ke server
            const response = await fetch(`/api/search?q=${currentQuery}&category=${currentCategory}`);
            const foods = await response.json();
            renderFoods(foods);
        } catch (error) {
            console.error('Error saat mengambil data:', error);
            foodGrid.innerHTML = '<p>Terjadi kesalahan saat memuat menu.</p>';
        }
    };

    // --- Fungsi untuk Menggambar Ulang Kartu Makanan ---
    const renderFoods = (foods) => {
        foodGrid.innerHTML = '';
        if (foods.length === 0) {
            foodGrid.innerHTML = '<p>Menu yang Anda cari tidak ditemukan.</p>';
            return;
        }
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

    // --- Event Listener untuk Input Pencarian ---
    searchInput.addEventListener('input', (event) => {
        currentQuery = event.target.value;
        fetchAndRenderFoods();
    });

    // --- Event Listener untuk Tombol Filter ---
    filterButtonsContainer.addEventListener('click', (event) => {
        if (event.target.tagName === 'BUTTON') {
            // Hapus kelas 'active' dari semua tombol
            filterButtonsContainer.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            // Tambahkan kelas 'active' ke tombol yang diklik
            event.target.classList.add('active');
            
            currentCategory = event.target.dataset.category;
            fetchAndRenderFoods();
        }
    });
});